"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE REAL DISPATCHER (O-7) -- the one file that knows both the
         scheduler's nouns and operations' machinery, and nothing
         else does.

    run_script    -> a procsitter-supervised shell command in the
                     directory (the frame)
    run_build     -> operations/build_action, one action
    open_session  -> operations/run MultiExecute stands up
    run_test      -> the per-choice ceremony, 'run_test_held':
                     provision -> compare -> Bookkeeper record; for a
                     session's choice, the provision is the session's
                     own ChoiceExecute
    close_session -> spend and shut down

ONE LOCK, ONE STORE, ONE LIFETIME: the dispatcher takes the directory
lock at construction and holds it until 'close()' -- the mutex is
non-recursive, so the per-choice ceremony enters through the HELD door
('run_test_held'), never the standalone one.

THE FINER WORD: beside the boolean the scheduler consumes, the
dispatcher keeps each failed node's E_TestRunResult word in
'report_db'; the tree scheduler reads it through 'report_of' and puts
it on the wire as 'run-ended.report' (O-6).
______________________________________________________________________________
"""
from ...operations.build_action     import build
from ...operations.run.multi_execute import MultiExecute
from ...operations.run.stage_canonicalise import StageCanonicalise
from ...operations.run.core         import Provision
from ...operations.session          import Request, run_test_held
from ...operations.result           import E_TestRunResult
from ...bookkeeper.api   import Bookkeeper

from ...bookkeeper.api import Store, DirectoryBusy, unstable_f
from ...procsitter.api       import Procsitter
from ..scheduler.scheduler          import I_Dispatcher
from ..scheduler.disk_guard         import HOST_DISK_GUARD
from ...operations.configuration    import caps_of
from ...bookkeeper.api import ObservationDb, ObservationFault
from .adapter                       import (naming_of,
                                            test_configuration_of,
                                            script_config_of,
                                            SCRIPT_CAPS)


#  THE FRAME'S CAPS WHERE THE DIRECTORY STATES NO 'script_caps' (B-17).
FRAME_CAPS = SCRIPT_CAPS


class TestRunDispatcher(I_Dispatcher):
    """Drives one directory's plan against the real machinery."""

    def __init__(self, directory, entry, record=None, variant_tuple=(),
                 timing_f=False,
                 despite_stain_f=False, force_run_f=False):
        """
        RETURN: TestRunDispatcher holding 'directory': its Bookkeeper
                and Store made here, the directory LOCK taken here and
                held to 'close()'.

        'entry'    the directory's CTreePlanEntry: its app_set names
                   what exists; the plan's nodes are resolved against
                   it.
        'record'   THE STORE KNOB (n-1): None or True stores every
                   subject; False stores nothing; '--no-store' is a
                   later word over it.
        'variant_tuple' the alternatives named by '--variant' (E-9):
                   what each states is merged over every application's
                   configuration, one alternative per variant group.
        'despite_stain_f' runs a STAINED choice anyway. THE PROVER'S
                   SEAM ALONE: 'hwut.run.stability' must be able to run
                   what it disqualified, or a stain could never be
                   answered. No command line reaches it.
        'timing_f' asks every configuration for the run's CADENCE
                   ('--timing'): per-line delta times kept beside the
                   candidate, for an analyst and for 'hwut.run.stability'.

        Raises DirectoryBusy where another live process holds the
        directory -- refused at the door, never queued.
        """
        self.directory  = directory
        self.record     = True if record is None else record
        #  ONE BOOKKEEPER FOR THE DIRECTORY (B-30): 'same' -- all
        #  choices share one nominal -- is an application's word, and
        #  the naming law names the applications that state it. There
        #  was a second bookkeeper per such application, made here and
        #  nowhere else; every other face named a nominal per choice.
        self.bookkeeper = Bookkeeper(directory, naming_of(entry.app_set))
        self.store      = Store(self.bookkeeper)
        #  THE DIRECTORY IS HELD THROUGH THE BOOKKEEPER (B-9): it is
        #  the locking proxy; every write it makes inside the session
        #  sees the lock held and does not take it again.
        self.lock       = self.store.bookkeeper.held()
        try:
            self.lock.__enter__()
        except DirectoryBusy:
            raise DirectoryBusy(
                "the directory '%s' is held by a live process"
                % directory)
        self.despite_stain_f = despite_stain_f
        self.force_run_f    = force_run_f
        #  THE REGISTER, for the E-41 attention: a test that runs here
        #  passed the nominal gate, so something was accepted for it;
        #  where the register has no entry, one is made and the run
        #  says so ('notice_list', emitted as NOTE by the orchestrator).
        #  'hwut.sanitize.propose --books' reads the same disagreement.
        self.register    = self.store.bookkeeper
        self.notice_list = []
        directory_spec  = getattr(getattr(entry, "app_set", None),
                                  "directory_spec", None)
        self.directory_spec = directory_spec
        variant_db      = getattr(directory_spec, "variant_db", None)
        language_setup  = getattr(directory_spec, "language_setup", None)
        free_disk_min_mb = getattr(directory_spec, "free_disk_min_mb", None)
        self.config_db  = {app.source_file:
                               test_configuration_of(app, directory,
                                                     variant_tuple,
                                                     variant_db,
                                                     timing_f,
                                                     language_setup,
                                                     free_disk_min_mb)
                           for app in entry.app_set}
        #  BUILD action name -> the configuration whose build it is.
        self.build_db   = {}
        for app in entry.app_set:
            build = None
            for parameters in app.choice_db.values():
                if parameters.build is not None \
                   and parameters.build.framework is not None:
                    build = parameters.build
                    break
            if build is None: continue
            action = "%s %s" % (build.framework, app.source_file)
            self.build_db[action] = self.config_db[app.source_file]
        self.session_db = {}
        self.report_db  = {}
        self.detail_db = {}
        self.frame_exit_db = {}       # role -> 'exited <n>' | 'ended: <how>'
        self.disk_db    = {}          # session file -> its disk reservation

    async def close(self):
        """RETURN: None. Any standing session shut down; the lock
        released."""
        for multi in self.session_db.values():
            await multi.close()
        self.session_db = {}
        for answer in self.disk_db.values():
            HOST_DISK_GUARD.release(answer)
        self.disk_db = {}
        self.lock.__exit__(None, None, None)

    def report_of(self, node_name):
        """
        RETURN: str, the operation's own word for the node's failure
                (E_TestRunResult, verbatim); 'None' where none stands.
        """
        return self.report_db.get(node_name)

    def detail_of(self, node_name):
        """
        RETURN: str, the report's numbers (O-19) -- which cap, the cap,
                the peak; 'None' where the report carries none.
        """
        return self.detail_db.get(node_name)

    async def _room(self, node, configuration, choice):
        """
        RETURN: CDiskAnswer -- room held on the directory's disk for the
                case, or the refusal; on refusal the node's report and
                detail are said here.

        THE NEED (D-24): twice the case's 'disk_mb', or what this
        machine last saw it hold, where that is more; above the disk's
        floor. Where the disk has no room yet, it waits for a case
        running there to end.
        """
        caps = caps_of(configuration, choice)
        need = 2.0 * caps.max_disk_mb
        try:
            observed = ObservationDb(self.directory).get(
                           configuration.key_name, choice, "Run")
        except (ObservationFault, OSError):
            observed = None
        if observed is not None and observed.peak_disk_mb is not None:
            need = max(need, observed.peak_disk_mb)
        answer = await HOST_DISK_GUARD.reserve(self.directory, need,
                                               caps.min_free_disk_mb)
        if not answer.granted_f:
            self.report_db[node.name()] = E_TestRunResult.DISK_SHORT.value
            self.detail_db[node.name()] = answer.text()
        return answer

    # -- the five doors ------------------------------------------------
    async def run_script(self, role, command):
        """
        RETURN: bool, whether the frame command ran to a good end:
                supervised, in the directory, 'bash -c <command>'.
        """
        how = await self._script(command)
        #  HOW IT ENDED, for the closing note: the exit status, or the
        #  containment where the supervisor ended it.
        if how is not None: self.frame_exit_db[role] = how
        return how is None

    async def _script(self, command, env=None):
        """
        RETURN: None, the script ran to exit 0
                str, how it ended else -- 'exited <n>', or 'ended: <how>'
                     where the supervisor ended it

        EVERY SCRIPT OF THE DIRECTORY IS SUPERVISED (B-17): 'bash -c
        <command>' in the directory, under the directory's
        'script_caps' ('adapter.script_config_of').
        """
        procsitter = Procsitter(script_config_of(self.directory_spec, env),
                                work_dir=self.directory)
        record = await procsitter.run(["bash", "-c", command])
        name   = record.containment.name
        if name == "OK_COMPLETED" and record.exit_code == 0: return None
        if name in ("OK_COMPLETED", "FAIL_COMPLETED"):
            return "exited %s" % record.exit_code
        return "ended: %s" % name[len("FAIL_"):].lower().replace("_", " ")

    async def _helper(self, role, node):
        """
        RETURN: None. The directory's 'on_before_test' or 'on_after_test'
                run for the test run 'node' -- the author's helper, NO
                VERDICT (B-17, as the frame, E-158): an end other than
                exit 0 is said, '<role> of <run> exited <n>: <command>',
                as the frame's is: a FRAME line, a NOTE at the end, by
                'frame_emit' where the orchestrator set it, among the
                run's NOTEs else. The run is told by environment:
                'HWUT_TEST', 'HWUT_CHOICE' ('' for none).
        """
        command = getattr(self.directory_spec, role, None)
        if not command: return
        how = await self._script(command, {"HWUT_TEST":   node.file,
                                           "HWUT_CHOICE": node.choice or ""})
        if how is None: return
        said = "%s of %s" % (role, node.name())
        emit = getattr(self, "frame_emit", None)
        if emit is not None: emit(said, how, command)
        else:                self.notice_list.append("%s %s: %s"
                                                     % (said, how, command))

    async def run_build(self, node):
        """
        RETURN: bool, the one build action's own good end AND every
                declared target standing; the finer word kept for the
                wire.
        """
        configuration = self.build_db.get(node.action)
        if configuration is None:
            self.report_db[node.name()] = "build-tool-not-found"
            return False
        outcome = await build(configuration)
        if not outcome.succeeded:
            self.report_db[node.name()] = outcome.report.value
        return outcome.succeeded

    async def open_session(self, node):
        """
        RETURN: bool, the session stood up. The application call is
                LAZY (R-46): a dead command surfaces as the first
                choice's launch failure, which the wire lifts back to
                'launch-failed' (O-6). The process itself starts with
                the first choice (services E-196).
        """
        configuration = self.config_db[node.file]
        #  ONE PROCESS SERVES THE SESSION: its room is held as long.
        answer = await self._room(node, configuration, None)
        if not answer.granted_f: return False
        self.disk_db[node.file] = answer
        #  OPENED, NOT LAUNCHED (E-196): the process starts with the
        #  first choice, so its wall clock measures the run, not the
        #  queue the choices wait in.
        multi = MultiExecute(configuration)
        multi.held_f = True
        self.session_db[node.file] = multi
        return True

    async def close_session(self, node):
        """RETURN: None. The session spent: shut down and forgotten."""
        multi = self.session_db.pop(node.file, None)
        if multi is not None:
            await multi.close()
        answer = self.disk_db.pop(node.file, None)
        if answer is not None: HOST_DISK_GUARD.release(answer)

    async def run_test(self, node):
        """
        RETURN: bool, the choice's VERDICT from the full ceremony:
                provision (the session's own ChoiceExecute where one
                stands), canonicalise, compare against the nominal,
                record to the Bookkeeper.

        A STAINED CHOICE IS NOT RUN. It came out 'ok' in one repeat and
        not in another, so its testimony is worthless and asking it
        again would only produce more of it. The verdict is False and
        the report 'unstable' -- which fails the choice, fails its
        directory, and fails the run: what the run says about the
        component under test is that the component cannot be relied
        upon to have been tested.
        """
        configuration = self.config_db[node.file]
        stain = None if self.despite_stain_f \
                else self.bookkeeper.stain(configuration.key_name,
                                           node.choice)
        if unstable_f(stain):
            self.report_db[node.name()] = E_TestRunResult.UNSTABLE.value
            return False
        if self.register.run_id_of(configuration.key_name,
                                   node.choice) is None:
            self.register.run_id_of(configuration.key_name, node.choice,
                                    allocate_f=True)
            self.notice_list.append(
                "REGISTERED %s%s: a nominal stands and the register "
                "had no entry -- accepted outside the book (E-41)"
                % (configuration.key_name,
                   "" if node.choice is None else " " + node.choice))
        provision     = None
        answer        = None
        multi         = self.session_db.get(node.file)
        if multi is not None:
            provision = Provision(
                stage_execute      = multi.provider(node.choice),
                stage_canonicalise = StageCanonicalise(configuration,
                                                       node.choice))
        else:
            answer = await self._room(node, configuration, node.choice)
            if not answer.granted_f: return False
        try:
            await self._helper("on_before_test", node)
            try:
                outcome = await run_test_held(
                    configuration,
                    Request(choice=node.choice, record=self.record,
                            force_run=self.force_run_f),
                    store=self.store,
                    provision=provision)
            finally:
                await self._helper("on_after_test", node)
        finally:
            if answer is not None: HOST_DISK_GUARD.release(answer)
        if not outcome.verdict:
            self.report_db[node.name()] = outcome.result.report.value
            detail = getattr(outcome.result.provision, "detail", None)
            #  WHAT THE CONSTRAINTS FOUND is said in full (E-123).
            comparison = outcome.result.comparison
            if not detail and comparison is not None:
                detail = comparison.detail
            if detail: self.detail_db[node.name()] = detail
        return bool(outcome.verdict)


def test_run_dispatcher_factory(record=None, variant_tuple=(),
                                timing_f=False,
                                despite_stain_f=False,
                                force_run_f=False):
    """
    RETURN: callable(directory, entry) -> TestRunDispatcher -- the
            factory 'orchestrator()' consumes, the store knob, the
            variant selection and the cadence demand bound.
    """
    return lambda directory, entry: TestRunDispatcher(
                                        directory, entry, record=record,
                                        variant_tuple=variant_tuple,
                                        timing_f=timing_f,
                                        despite_stain_f=despite_stain_f,
                                        force_run_f=force_run_f)
