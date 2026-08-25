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
from dataclasses import replace
from ...bookkeeper.bookkeeper   import Bookkeeper
from ...bookkeeper.test_id_db   import TestIdDb
from ...bookkeeper.stream_store import Store, DirectoryBusy
from ...procsitter.procsitter       import Procsitter, ProcsitterConfig
from ..scheduler.scheduler          import I_Dispatcher
from .adapter                       import (naming_of,
                                            test_configuration_of)


FRAME_CAPS = ProcsitterConfig(max_wall_clock_sec=60.0)


class TestRunDispatcher(I_Dispatcher):
    """Drives one directory's plan against the real machinery."""

    def __init__(self, directory, entry, record=None, coverage=None):
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
        'coverage' a CoverageConfig where coverage is asked (coverage
                   D-19): every configuration is then made for the
                   coverage target, and every run harvests. The run id
                   comes from the directory's register; a run of an
                   unregistered choice harvests under NO id and is
                   noted 'NOT_ASKED' -- coverage is measured for
                   accepted tests.

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
        self.coverage   = coverage
        self.id_db      = None if coverage is None else TestIdDb(directory)
        self.config_db  = {app.source_file:
                               test_configuration_of(app, directory,
                                                     coverage)
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
        """
        RETURN: bool, the choice's VERDICT from the full ceremony:
                provision (the session's own ChoiceExecute where one
                stands), canonicalise, compare against the nominal,
                record to the Bookkeeper.
        """
        configuration = self.config_db[node.file]
        provision     = None
        multi         = self.session_db.get(node.file)
        if multi is not None:
            provision = Provision(
                stage_execute      = multi.provider(node.choice),
                stage_canonicalise = StageCanonicalise(configuration,
                                                       node.choice))
        run_id = None
        if self.id_db is not None:
            run_id = self.id_db.run_id_of(configuration.stem, node.choice)
            if run_id is None:
                #  Unregistered: never accepted, so no id to seat. The
                #  run proceeds as a plain run; the entry says NOT_ASKED.
                configuration = replace(configuration, coverage=None)
        outcome = await run_test_held(
            configuration,
            Request(choice=node.choice, record=self.record),
            store=self.store_db.get(node.file, self.store),
            provision=provision, run_id=run_id)
        if not outcome.verdict:
            self.report_db[node.name()] = outcome.result.report.value
        return bool(outcome.verdict)


def test_run_dispatcher_factory(record=None, coverage=None):
    """
    RETURN: callable(directory, entry) -> TestRunDispatcher -- the
            factory 'orchestrator()' consumes, the store knob and the
            coverage demand bound.
    """
    return lambda directory, entry: TestRunDispatcher(directory, entry,
                                                      record=record,
                                                      coverage=coverage)
