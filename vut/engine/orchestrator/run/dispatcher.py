"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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
import asyncio

from ...operations.build_action     import build
from ...operations.run.multi_execute import MultiExecute
from ...operations.run.stage_canonicalise import StageCanonicalise
from ...operations.run.core         import Provision
from ...operations.session          import Request, run_test_held
from ...operations.result           import E_TestRunResult
from ...bookkeeper.api   import Bookkeeper
from ...bookkeeper.api   import TestIdDb
from ...bookkeeper.api import Store, DirectoryBusy
from ...procsitter.api       import Procsitter, ProcsitterConfig
from ..scheduler.scheduler          import I_Dispatcher
from .adapter                       import (naming_of,
                                            test_configuration_of)


FRAME_CAPS = ProcsitterConfig(max_wall_clock_sec=60.0)


class TestRunDispatcher(I_Dispatcher):
    """Drives one directory's plan against the real machinery."""

    def __init__(self, directory, entry, record=None, coverage=None,
                 variant_tuple=(), timing_f=False,
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
        'coverage' a CoverageConfig where coverage is asked (coverage
                   D-19): every configuration is then made for the
                   coverage target, and every run harvests. The run id
                   comes from the directory's register -- and every
                   run here HAS one: the gate admitted the case on its
                   nominal's word (E-41), and a case the register did
                   not name is registered before it runs, said so.
        'despite_stain_f' runs a STAINED choice anyway. THE PROVER'S
                   SEAM ALONE: 'hwut.stability' must be able to run
                   what it disqualified, or a stain could never be
                   answered. No command line reaches it.
        'timing_f' asks every configuration for the run's CADENCE
                   ('--timing'): per-line delta times kept beside the
                   candidate, for an analyst and for 'hwut.stability'.

        Raises DirectoryBusy where another live process holds the
        directory -- refused at the door, never queued.
        """
        self.directory  = directory
        self.record     = True if record is None else record
        #  ONE bookkeeper per NAMING LAW: 'same' (all choices share one
        #  nominal) is an application's word, so an application that
        #  states it gets its own book; the directory's default book
        #  serves the rest. The LOCK is the directory's, taken once.
        self.bookkeeper = Bookkeeper(directory)
        self.store      = Store(self.bookkeeper)
        self.store_db   = {}
        for app in entry.app_set:
            naming = naming_of(app)
            if not naming.same_nominal_f: continue
            self.store_db[app.source_file] = Store(
                                    Bookkeeper(directory, naming))
        self.lock       = self.store.lock()
        if not self.lock.acquire():
            raise DirectoryBusy(
                "the directory '%s' is held by a live process"
                % directory)
        self.despite_stain_f = despite_stain_f
        self.force_run_f    = force_run_f
        self.coverage   = coverage
        self.id_db      = None if coverage is None else TestIdDb(directory)
        #  THE REGISTER, for the E-41 attention: a test that runs here
        #  passed the nominal gate, so something was accepted for it;
        #  where the register has no entry, one is made and the run
        #  says so ('notice_list', emitted as NOTE by the orchestrator).
        #  'hwut.sanitize --books' reads the same disagreement.
        self.register    = self.id_db if self.id_db is not None \
                           else TestIdDb(directory)
        self.notice_list = []
        #  ONE RUN AT A TIME per directory under coverage (coverage D-22):
        #  every tool leaves its artefact in the directory's OUT/COVERAGE.
        self.cov_lock   = None if coverage is None else asyncio.Lock()
        directory_spec  = getattr(getattr(entry, "app_set", None),
                                  "directory_spec", None)
        variant_db      = getattr(directory_spec, "variant_db", None)
        language_setup  = getattr(directory_spec, "language_setup", None)
        self.config_db  = {app.source_file:
                               test_configuration_of(app, directory,
                                                     coverage,
                                                     variant_tuple,
                                                     variant_db,
                                                     timing_f,
                                                     language_setup)
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

    async def close(self):
        """RETURN: None. Any standing session shut down; the lock
        released."""
        for multi in self.session_db.values():
            await multi.close()
        self.session_db = {}
        self.lock.release()

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

    # -- the five doors ------------------------------------------------
    async def run_script(self, role, command):
        """
        RETURN: bool, whether the frame command ran to a good end:
                supervised, in the directory, 'bash -c <command>'.
        """
        procsitter = Procsitter(FRAME_CAPS, work_dir=self.directory)
        record = await procsitter.run(["bash", "-c", command])
        return record.containment.name.startswith("OK") \
               and record.exit_code == 0

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
                'launch-failed' (O-6).
        """
        configuration = self.config_db[node.file]
        multi = MultiExecute(configuration)
        await multi.start()
        self.session_db[node.file] = multi
        return True

    async def close_session(self, node):
        """RETURN: None. The session spent: shut down and forgotten."""
        multi = self.session_db.pop(node.file, None)
        if multi is not None:
            await multi.close()

    async def run_test(self, node):
        """RETURN: bool, the verdict; under coverage, one run at a time
        in this directory (coverage D-22)."""
        if self.cov_lock is None:
            return await self._run_test(node)
        async with self.cov_lock:
            return await self._run_test(node)

    async def _run_test(self, node):
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
        if stain is not None:
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
        multi         = self.session_db.get(node.file)
        if multi is not None:
            provision = Provision(
                stage_execute      = multi.provider(node.choice),
                stage_canonicalise = StageCanonicalise(configuration,
                                                       node.choice))
        run_id = None
        if self.id_db is not None:
            from ...operations.coverage_action import prepare
            prepare(configuration)
            run_id = self.id_db.run_id_of(configuration.key_name,
                                          node.choice)
        outcome = await run_test_held(
            configuration,
            Request(choice=node.choice, record=self.record,
                    force_run=self.force_run_f),
            store=self.store_db.get(node.file, self.store),
            provision=provision, run_id=run_id)
        if not outcome.verdict:
            self.report_db[node.name()] = outcome.result.report.value
            detail = getattr(outcome.result.provision, "detail", None)
            if detail: self.detail_db[node.name()] = detail
        return bool(outcome.verdict)


def test_run_dispatcher_factory(record=None, coverage=None,
                                variant_tuple=(), timing_f=False,
                                despite_stain_f=False,
                                force_run_f=False):
    """
    RETURN: callable(directory, entry) -> TestRunDispatcher -- the
            factory 'orchestrator()' consumes, the store knob, the
            coverage demand, the variant selection and the cadence
            demand bound.
    """
    return lambda directory, entry: TestRunDispatcher(
                                        directory, entry, record=record,
                                        coverage=coverage,
                                        variant_tuple=variant_tuple,
                                        timing_f=timing_f,
                                        despite_stain_f=despite_stain_f,
                                        force_run_f=force_run_f)
