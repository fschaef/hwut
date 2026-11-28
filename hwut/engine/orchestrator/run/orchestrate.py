"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE OUTER FACE (O-1) --

    orchestrate(root, wish, ...)  -> CTreePlan          determination
    orchestrator(root, wish, ...) -> asyncio.Queue      the run

'orchestrator' explores the tree, determines the plans, and sets a
CTreeScheduler running as an asyncio task; the queue carries the
report stream of 'vocabulary.py' and one 'None' after 'tree-done'
closes it. The caller reads the queue; the summary is a fold over it
(summary.py); nothing else is returned -- one truth, one carrier
(O-4).

CTreeScheduler runs the directories under ONE host-global budget (O-11,
O-12); a STRATEGY (strategy.py, O-15) says when each one starts --
linear by default. Each directory is a CDirectoryWork -- the unit of placeable
work (O-13): its own frame, its own dispatcher, its own lock; it
answers 'events + CDirDone' and nothing crosses its edge but the
budget and the queue. Everything that leads to the executability of a
test is the test: a [MISDEP] node and an UNSUPPORTED node each get
their 'run-ended', verdict and cause named (O-3).
______________________________________________________________________________
"""
import asyncio
import os
from dataclasses import dataclass, replace
from datetime    import datetime, timezone

from ...bookkeeper.api       import Bookkeeper
from ..exploration.task_list_query import dir_wanted_f
from ..exploration.tree_explorer   import (explore_tree, GATE_RUN,
                                           test_directory_name_tuple)
from ..plan.bubble                 import (HANDED, NOT_RUN, RUN,
                                           case_refusal, decider,
                                           decision_tuple, missing_text,
                                           owner_of, PlatformMissing,
                                           tool_absent_refusal_f)
from ...                           import platforms
from ..plan.wish                   import unrequired_platform_note_tuple
from ..plan.label                  import parse_expression, selects_below_f
from ..plan.form                   import E_NodeKind
from ..plan.confinement            import uncapped_refusal_f
from ..plan.determine              import EMPTY_SELECTION_STR
from ..plan.tree                   import (determine_tree,
                                           NOT_ACCEPTED_REASON,
                                           UNACCEPTED_REASON)
from ..scheduler.budget            import CBudget
from ..scheduler.scheduler         import Scheduler
from ..scheduler.state             import E_NodeState
from .strategy                     import CLinear
from ...bookkeeper.traces import duration_db_of
from .strategy                     import sort_key_of
from ...protocol.vocabulary        import event


#  E_NodeState x kind -> the verdict word (O-3). ENDED_BAD names the
#  kind's own breaking; the rest name themselves.
def _verdict(state, node_kind):
    """
    RETURN: str, the verdict word of the vocabulary for a node of that
            kind ending in that state.
    """
    match state:
        case E_NodeState.ENDED_GOOD:  return "ok"
        case E_NodeState.UNSUPPORTED: return "unsupported"
        case E_NodeState.MISDEP:      return "misdep"
        case _:
            return {E_NodeKind.TEST:    "test-failed",
                    E_NodeKind.BUILD:   "build-failed",
                    E_NodeKind.DEPLOY:  "deploy-failed",
                    E_NodeKind.SESSION: "launch-failed"}[node_kind]


def _utc_now():
    """RETURN: str, the current UTC instant, millisecond resolution,
    ISO-8601 -- fine enough for the event line's two decimals
    (O-23); a consumer that wants seconds truncates."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class CDirDone:
    """What one unit of directory work comes to."""
    good_f: bool        # frame good, no fault, no failed node
    fail_n: int         # how many of its nodes failed


class CDirectoryWork:
    """ONE test directory's run -- the unit of placeable work (O-13).

    Constructed over the root and the directory's CTreePlanEntry; 'run'
    makes the dispatcher (bookkeeper, store, lock) INSIDE, drives the
    node-level Scheduler, and closes the dispatcher again. Events go to
    'emit'; the outcome is a CDirDone. A placement backend (stage 2)
    answers a different 'run' for the same unit."""

    def __init__(self, root, entry, dispatcher_factory,
                 selection_order=None):
        """
        RETURN: CDirectoryWork for 'entry' below the absolute 'root'.

        'selection_order' says which of the ADMISSIBLE nodes starts
        where more than one may (O-27); 'None' is plan order. It
        travels to the node-level Scheduler this unit drives.
        """
        self.root               = root
        self.entry              = entry
        self.dispatcher_factory = dispatcher_factory
        self.selection_order    = selection_order
        self._scheduler         = None      # stands while 'run' runs

    def ready_n(self):
        """
        RETURN: int,  how many nodes this unit could start NOW (the
                      Scheduler's 'ready_n', intend 20).
                None, where the Scheduler does not stand -- before the
                      unit built it, or after the unit ended. A caller
                      deciding whether the open units can fill the
                      budget treats None as 'unknown, assume it can':
                      a unit started a moment ago has said nothing yet.
        """
        if self._scheduler is None: return None
        return self._scheduler.ready_n()

    @property
    def directory(self):
        """RETURN: str, the root-relative directory the unit runs."""
        return self.entry.directory

    async def run(self, emit, budget):
        """
        RETURN: CDirDone, the directory's outcome; every event of the
                run went through 'emit(kind, **field_db)' on the way.

        Raises what the dispatcher's construction or run raises; the
        caller (CTreeScheduler) turns that into 'fault' + 'dir-done'.
        """
        entry     = self.entry
        directory = entry.directory
        #  A SPECIFICATION THAT DOES NOT PARSE IS A FAILING TEST, not
        #  merely a fault beside the run. The application named by
        #  the fault never became a node -- it could not be
        #  determined -- so it is reported here, terminal before
        #  anything runs, exactly as a [MISDEP] node is: the same law
        #  that makes a failed BUILD a test result rather than a
        #  suite-aborting precondition. Without this the directory
        #  says '0 of 1 ok' and the broken application is invisible
        #  in the count.
        for fault in entry.fault_tuple:
            emit("fault", directory=directory, text=str(fault))
        unstood = unstood_tuple(
                      os.path.normpath(os.path.join(self.root, directory)),
                      entry.app_set, entry.fault_tuple,
                      entry.conf_fault_tuple)
        for report in entry.report_tuple:
            #  NOT EMPTY WHERE THE BOOK ANSWERS: a test or choice the book
            #  records and the tree no longer declares is a case of the
            #  selection -- it fails, and is shown (2026-10-19, "the
            #  selection is not empty, but fail is true").
            if str(report) == EMPTY_SELECTION_STR and unstood: continue
            emit("report", directory=directory, text=str(report))
        #  NOT RUN, AND SAID SO (E-41): exploration's refusals, one
        #  event each, collected by the display into the closing REFUSED
        #  block. None is a node of the plan and none is counted.
        #  A CASE WHOSE NOMINAL CANNOT SERVE IS NOT RUN EITHER, and it
        #  FAILS, counted, below: no GOOD file (display D-32), and a GOOD
        #  carrying '##! unaccepted' (O-25) -- 'unaccepted [FAIL]'.
        no_good_tuple    = no_good_file_tuple(entry.refused_tuple)
        unaccepted_tuple = unaccepted_tuple_of(entry.refused_tuple)
        #  A CAP NOBODY CAN WATCH HERE IS A FAILURE (ruled 2026-10-17,
        #  services E-159): the test states a promise this machine cannot
        #  keep, unacknowledged -- not run, counted, the remedy beside it.
        uncapped_db = {name: reason for name, reason in entry.refused_tuple
                       if uncapped_refusal_f(reason)}
        #  A PLATFORM LACKING WHAT IT DECLARES (intend/45 R-5): the case
        #  fails, not run, the reason beside it.
        absent_db = {name: reason for name, reason in entry.refused_tuple
                     if tool_absent_refusal_f(reason)}
        for name, reason in entry.refused_tuple:
            if name in no_good_tuple or name in unaccepted_tuple \
               or name in uncapped_db or name in absent_db: continue
            emit("refused", directory=directory, node=name, text=reason)
        #  SILENT, NOT REFUSED (X-SILENT): a candidate carrying no
        #  'hwut { }' and named under no 'apps'. Ordinary -- a helper,
        #  a log -- so it is no fault and no refusal; the display says
        #  so ONCE at the end, lest a test that stopped being seen
        #  vanish without a word.
        for name in entry.app_set.silent_tuple:
            emit("silent", directory=directory, node=name)
        emit("dir-begun", directory=directory,
             node_n=len(entry.plan) + len(unstood) + len(no_good_tuple)
                    + len(unaccepted_tuple) + len(uncapped_db)
                    + len(absent_db))
        #  THE BOOK DOCUMENTS WHAT TESTS EXIST, and a test it records
        #  that no longer stands is a FAILING TEST, not a silence: the
        #  documentation and the tree disagree, and only a person can
        #  say which of the two is wrong. Reported exactly as a broken
        #  specification is -- terminal before anything runs, counted,
        #  and named in HINTS.
        for name, verdict in unstood:
            emit("run-ended", directory=directory, node=name,
                 node_kind="TEST", good=False, verdict=verdict)
        for name in no_good_tuple:
            emit("run-ended", directory=directory, node=name,
                 node_kind="TEST", good=False, verdict="no-good-file")
        for name in unaccepted_tuple:
            emit("run-ended", directory=directory, node=name,
                 node_kind="TEST", good=False, verdict="unaccepted")
        for name, reason in uncapped_db.items():
            emit("run-ended", directory=directory, node=name,
                 node_kind="TEST", good=False, verdict="uncapped",
                 detail=reason)
        for name, reason in absent_db.items():
            emit("run-ended", directory=directory, node=name,
                 node_kind="TEST", good=False, verdict="tool-not-provided",
                 detail=reason)

        #  [MISDEP] nodes are terminal before anything runs (P-6):
        #  their 'run-ended' comes first, verdict named.
        for node in entry.plan:
            if not node.misdep_f: continue
            emit("run-ended", directory=directory, node=node.name(),
                 node_kind=node.kind.name, good=False,
                 verdict="misdep")

        def notify(kind, **field_db):
            if kind == "frame":
                role  = field_db["role"]
                extra = {}
                if not field_db["good_f"]:
                    extra["command"] = (entry.on_entry if role == "on_entry"
                                        else entry.on_exit) or ""
                    extra["exit"] = getattr(dispatcher, "frame_exit_db",
                                            {}).get(role, "failed")
                emit("frame", directory=directory, role=role,
                     good=bool(field_db["good_f"]), **extra)
            elif kind == "started":
                node = field_db["node"]
                emit("run-begun", directory=directory,
                     node=node.name(), node_kind=node.kind.name)
            else:
                node  = field_db["node"]
                state = field_db["state"]
                cause = field_db["cause"]
                extra = {} if cause is None else {"cause": cause}
                report = report_of(node.name())
                if report is not None: extra["report"] = report
                detail = detail_of(node.name())
                if detail is not None: extra["detail"] = detail
                label  = label_of(node.name()) \
                         if node.kind.name == "TEST" else None
                if label is not None:
                    extra["book"]     = label[0] or ""
                    extra["deviates"] = label[1]
                good_f  = state is E_NodeState.ENDED_GOOD
                verdict = _verdict(state, node.kind)
                if not good_f and report == "test-app-launch-failed":
                    verdict = "launch-failed"
                #  BY ITS NAME (C-9, O-25): the nominal carries lines
                #  nobody decided; the verdict says 'unaccepted'.
                if not good_f and report == "unaccepted":
                    verdict = "unaccepted"
                emit("run-ended", directory=directory,
                     node=node.name(), node_kind=node.kind.name,
                     good=good_f, verdict=verdict, **extra)

        dispatcher = self.dispatcher_factory(
                         os.path.normpath(os.path.join(self.root,
                                                       directory)),
                         entry)
        #  THE HELPERS AROUND EACH TEST RUN (B-17) speak as the frame
        #  does: a FRAME line in the flow, a NOTE at the end.
        dispatcher.frame_emit = lambda role, exit, command: emit(
            "frame", directory=directory, role=role, good=False,
            command=command, exit=exit)
        report_of  = getattr(dispatcher, "report_of",
                             lambda name: None)
        detail_of  = getattr(dispatcher, "detail_of",
                             lambda name: None)
        #  THE COVERAGE RUN'S LABEL (coverage D-48); a test run has none.
        label_of   = getattr(dispatcher, "label_of",
                             lambda name: None)
        #  WHAT THE MACHINE LAST MEASURED, read per directory because
        #  'hwut-traces.csv' is per directory. A directory nobody has
        #  run yields {}, and the selection falls back to plan order
        #  of its own accord (O-27).
        directory_path = os.path.normpath(os.path.join(self.root,
                                                       directory))
        scheduler  = Scheduler(dispatcher,
                               on_entry        = entry.on_entry,
                               on_exit         = entry.on_exit,
                               worker_max_n    = budget,
                               notify          = notify,
                               selection_order = self.selection_order,
                               duration_db     = duration_db_of(
                                                     directory_path))
        self._scheduler = scheduler
        try:
            report = await scheduler.run(entry.plan)
        finally:
            self._scheduler = None
        close  = getattr(dispatcher, "close", None)
        if close is not None: await close()
        #  BROUGHT TO ATTENTION (E-41): a test that ran on a nominal's
        #  word and had no register entry got one; the run says so.
        for text in getattr(dispatcher, "notice_list", ()):
            emit("report", directory=directory, text=text)
        fail_db = {name: state.name for name, state
                   in sorted(report.failure_db().items())}
        good_f  = report.good_f() and not entry.fault_tuple \
                  and not unstood and not no_good_tuple and not uncapped_db \
                  and not unaccepted_tuple and not absent_db
        emit("dir-done", directory=directory, good=good_f,
             fail_db=fail_db)
        return CDirDone(good_f, len(fail_db) + len(absent_db))


class CTreeScheduler:
    """Executes a CTreePlan -- its directories in parallel under one
    budget, or one after another -- emitting the report stream into a
    queue."""

    def __init__(self, dispatcher_factory, worker_max_n=None,
                 clock=None, strategy=None, selection_order=None):
        """
        RETURN: CTreeScheduler, ready to run a tree plan.

        'dispatcher_factory'  takes the ABSOLUTE directory path and
                              the directory's CTreePlanEntry, and
                              answers the I_Dispatcher for its work --
                              made above, handed down. A double may
                              ignore the entry.
        'worker_max_n'        the HOST-GLOBAL bound on work standing
                              at once, across every directory; 'None'
                              is no bound.
        'clock'               answers the 'when' string of an event;
                              the UTC instant where none is given. A
                              parameter so that a test may state the
                              clock.
        'strategy'            the CStrategy saying when a directory's
                              unit starts; CLinear where none is given.
        """
        self.dispatcher_factory = dispatcher_factory
        self.worker_max_n       = worker_max_n
        self.clock              = clock or _utc_now
        self.strategy           = strategy or CLinear()
        self.selection_order    = selection_order

    async def run(self, tree_plan, queue):
        """
        RETURN: None. Runs every entry of 'tree_plan' under the budget,
                each started when the strategy says; the report stream
                goes into 'queue'; one 'None' after 'tree-done' closes
                it.
        """
        def emit(kind, **field_db):
            queue.put_nowait(event(kind, self.clock(), **field_db))

        #  THE WHOLE PLAN'S SIZE, counted exactly as each 'dir-begun'
        #  counts its own: what a progress display divides by.
        #  A BUBBLE HANDED TO A PLATFORM names its TEST directories here,
        #  found by the walk alone, so a viewer knows them before they
        #  report (spec/42 section 5).
        far_directory_list = [
            directory for decision, _ in tree_plan.handed_tuple
            for directory in decision.directory_tuple]
        emit("tree-begun",
             directory_list=[entry.directory for entry in tree_plan]
                            + far_directory_list
                            + list(tree_plan.gone_tuple),
             node_n=sum(len(entry.plan)
                        + len(no_good_file_tuple(entry.refused_tuple))
                        + len(unstood_tuple(
                              os.path.normpath(os.path.join(tree_plan.root,
                                                            entry.directory)),
                              entry.app_set, entry.fault_tuple,
                              entry.conf_fault_tuple))
                        for entry in tree_plan)
                    + len(tree_plan.gone_tuple))
        for fault in tree_plan.fault_tuple:
            emit("fault", directory=".", text=str(fault))
        #  A FINDING THAT DECIDES NOTHING still belongs before the
        #  thing it is about: on the same road as a fault, one event
        #  each, before the first run.
        for text in tree_plan.warning_tuple:
            emit("warning", text=text)
        #  A BUBBLE NOT RUN HERE stands in the stream once, before the
        #  first run (spec/42 section 3); the fold counts nothing of it.
        for decision in tree_plan.not_run_tuple:
            emit("not-run", directory=decision.name,
                 platform=decision.platform, reason=decision.reason,
                 text=decision.text)

        budget    = CBudget(self.worker_max_n)
        unit_list = [CDirectoryWork(tree_plan.root, entry,
                                    self.dispatcher_factory,
                                    self.selection_order)
                     for entry in tree_plan]
        unit_list = self._ordered(unit_list, tree_plan.root)
        self.strategy.bind(budget, unit_list)
        done_list = await self.strategy.run(
                        [(lambda unit=unit:
                              self._guarded(unit, emit, budget))
                         for unit in unit_list])

        #  A DIRECTORY THE ROSTER RECORDS AND THE DISK DOES NOT HOLD
        #  FAILS (CR-2, ruled 2026-11-20): one case, terminal, after the
        #  directories that ran -- a run must not stay green while tests
        #  disappear.
        for directory in tree_plan.gone_tuple:
            emit("dir-begun", directory=directory, node_n=1)
            emit("run-ended", directory=directory, node=GONE_NODE_NAME,
                 node_kind="TEST", good=False, verdict="directory-gone")
            emit("dir-done", directory=directory, good=False,
                 fail_db={GONE_NODE_NAME: "directory-gone"})
        good_f = not tree_plan.fault_tuple and not tree_plan.gone_tuple \
                 and all(done.good_f for done in done_list)
        fail_n = sum(done.fail_n for done in done_list) \
                 + len(tree_plan.gone_tuple)
        #  THE BUBBLES HANDED TO A PLATFORM run there, one after another,
        #  into the same stream; their verdicts count as local ones do.
        for decision, far_argv in tree_plan.handed_tuple:
            far_good_f, far_fail_n = await self._handed(
                                         decision, far_argv, tree_plan.root,
                                         emit, queue)
            good_f  = good_f and far_good_f
            fail_n += far_fail_n
        #  'meta_n' AND 'skip_n' ARE OPTIONAL AND ABSENT WHEN ZERO: a receiver that
        #  does not know the field never meets it unless the run had
        #  something to say.
        extra = {}
        if tree_plan.meta_hidden_n:  extra["meta_n"] = tree_plan.meta_hidden_n
        if tree_plan.wish_skipped_n: extra["skip_n"] = tree_plan.wish_skipped_n
        if tree_plan.not_run_n:      extra["not_run_n"] = tree_plan.not_run_n
        emit("tree-done", good=good_f, fail_n=fail_n, **extra)
        queue.put_nowait(None)

    async def _handed(self, decision, far_argv, root, emit, queue):
        """
        RETURN: (bool, int), whether the bubble of 'decision' stood on its
                platform -- every far verdict good, no fault, the far run
                ended 0 or EMPTY (a far wish that selected nothing is no
                failure) -- and how many far nodes failed.

        THE HAND-OVER (spec/42 sections 4, 5; rulings 14, 17, 20): the
        platform made ready ('start': an image built where it does not
        stand, said once); the bubble run there, its events into the
        stream as they come; 'stop' in a 'finally', a signal included
        (E-55). A start that fails is the bubble NOT RUN, 'reachable',
        counted nowhere (ruling 21).
        """
        name, spec = decision.platform, decision.spec
        ready_f, why = platforms.start(name, spec,
                                       lambda line: emit("warning",
                                                         text=line))
        if not ready_f:
            emit("not-run", directory=decision.name, platform=name,
                 reason="reachable",
                 text="%s/: platform '%s' not reachable: %s"
                      % (decision.name, name, why))
            return True, 0
        loop  = asyncio.get_running_loop()
        tally = {"good_f": True, "fail_n": 0}

        def sink(item):
            """RETURN: None. One far event, counted, into the queue --
            from the reading thread, the loop's own way."""
            kind = item.get("kind")
            if kind == "run-ended" and not item.get("good"):
                tally["fail_n"] += 1
                tally["good_f"]  = False
            elif kind == "fault" or (kind == "dir-done"
                                     and not item.get("good")):
                tally["good_f"] = False
            loop.call_soon_threadsafe(queue.put_nowait, item)

        try:
            status = await asyncio.to_thread(platforms.run, name, spec,
                                             decision.name, far_argv, sink,
                                             root=root)
        except Exception as error:                      # noqa: BLE001
            emit("fault", directory=decision.name, platform=name,
                 text="%s/: platform '%s' failed: %s"
                      % (decision.name, name, error))
            return False, tally["fail_n"]
        finally:
            platforms.stop(name, spec)
        await asyncio.sleep(0)          # the last far events into the queue
        #  A FAR WISH THAT SELECTED NOTHING IS NOT A FAILURE (2026-11-04,
        #  the author's run): EMPTY over there is what EMPTY is here --
        #  nothing ran, nothing failed ('platforms._status').
        return (tally["good_f"]
                and status in (0, platforms.FAR_EMPTY_STATUS),
                tally["fail_n"])

    def _ordered(self, unit_list, root):
        """
        RETURN: list[CDirectoryWork], the units in the order the
                selection order asks for -- THE SAME CRITERIA RECORD
                the node level uses, over a directory's WEIGHT: its
                LONGEST case this machine has measured
                ('duration_db_of'), or None where it has measured
                none (O-28).

        THE LONGEST CASE, NOT THE SUM (ruled 2026-09-26). The longest
        case cannot be split across workers: it is the directory's
        critical path, and started late it is the tail the whole run
        waits for. A sum measures how much work a directory holds, and
        many short cases outweighed one long one: the CSP solver's
        5.4 s case started fifth, behind directories of short cases.

        ONE VOCABULARY, BOTH LEVELS. 'longest first' says the same
        sentence about a directory as about a test, and a directory
        nobody has measured goes FIRST for the same reason a test
        does -- it is as likely to be heavy as light, and started late
        a heavy one becomes the tail everybody waits for.

        THE ORDER IS IDLE UNDER 'linear' AND SAYS SO. MEASURED: walk
        order and heaviest-first give the SAME total there, to the
        millisecond, because serial directories sum alike in any
        order. It is left applied all the same -- under linear it
        decides which directory a reader SEES first, which is not
        nothing, and it costs a sort of nineteen items.
        """
        if self.selection_order is None: return unit_list
        weight_db = {}
        for unit in unit_list:
            db = duration_db_of(os.path.normpath(
                     os.path.join(root, unit.directory)))
            weight_db[unit.directory] = max(db.values()) if db else None
        key_of = sort_key_of(self.selection_order, weight_db.get)
        return [unit for _, unit
                in sorted(enumerate(unit_list),
                          key=lambda pair: key_of((pair[0],
                                                   pair[1].directory)))]

    async def _guarded(self, unit, emit, budget):
        """
        RETURN: CDirDone, the unit's outcome -- 'good_f=False, fail_n=0'
                where the unit RAISED: the breakage is a 'fault' event,
                the directory is bad, the tree runs on and 'tree-done'
                still closes the queue (a held lock, a raising
                dispatcher).
        """
        try:
            return await unit.run(emit, budget)
        except Exception as error:
            emit("fault", directory=unit.directory,
                 text="%s: %s" % (type(error).__name__, error))
            emit("dir-done", directory=unit.directory,
                 good=False, fail_db={})
            return CDirDone(False, 0)


#  THE ONE CASE A GONE DIRECTORY FAILS AS (CR-2): no test stands to name.
GONE_NODE_NAME = "(directory)"


def broken_app_tuple(app_set, fault_tuple):
    """
    RETURN: tuple[str], every source file a fault of the directory names
            that exploration could NOT read as an application -- sorted,
            each once.

    A file that parsed stands in the APP SET; a file the fault names and
    the app set does not hold is one exploration could not read. The
    directory's own file ('hwut.conf') names no application and is left
    to the fault line alone. THE APP SET, NEVER THE PLAN: the wish
    narrows what runs, and narrows nothing about what is broken -- so
    'hwut.run' and 'hwut.report' name the same files (services E-128).
    """
    readable = {app.source_file for app in app_set}
    named = set()
    for fault in fault_tuple:
        file = getattr(fault, "file", None)
        if not file or file.endswith(".conf"):     continue
        if file in readable:                       continue
        named.add(file)
    return tuple(sorted(named))


def vanished_tuple(directory, app_set):
    """
    RETURN: tuple[(str, str)], one (node name, verdict) for every test
            the BOOK records that the directory no longer declares:
                'test-vanished'         the application is gone
                'test-choice-vanished'  the application stands, that
                                        choice of it does not
            Empty where book and tree agree, and where no book stands.

    THE DECLARATION IS THE APP SET, NEVER THE PLAN. 'app_set' is
    what EXISTS in the directory; a plan is what the WISH
    selected of it. Asking against the plan would read every
    unselected choice as vanished, so 'hwut.run test-x.py one' would
    accuse 'two' of not existing -- the wish narrows what runs, and
    narrows nothing about what is there.

    A BOOK THAT CANNOT BE READ SAYS NOTHING. The absence of a base, or
    a base that will not open, is not evidence that a test vanished.
    """
    if app_set is None: return ()
    declared_db = {app.source_file: list(app.choice_db)
                   for app in app_set}
    try:
        book = Bookkeeper(directory)
        divergence = book.divergence(declared_db)
    except (OSError, ValueError):
        return ()
    result = [(test, "test-vanished")
              for test in divergence.get("deleted", [])]
    for test, choice_list in sorted(divergence.get("non-responsive",
                                                   {}).items()):
        for choice in choice_list:
            name = test if choice is None else "%s %s" % (test, choice)
            result.append((name, "test-choice-vanished"))
    return tuple(result)


def no_good_file_tuple(refused_tuple):
    """
    RETURN: tuple[str], the case names the nominal gate refused because
            NO GOOD FILE stands (E-41's 'NOT_ACCEPTED_REASON') -- each is
            not run and FAILS, 'no GOOD file [FAIL]' (display D-32). The
            other refusals -- an aspirant, a backup-shaped name -- stay
            refusals.
    """
    return tuple(name for name, reason in refused_tuple
                 if reason == NOT_ACCEPTED_REASON)


def unaccepted_tuple_of(refused_tuple):
    """
    RETURN: tuple[str], the case names the nominal gate refused because
            their GOOD carries '##! unaccepted' (E-41's
            'UNACCEPTED_REASON', an ASPIRANT) -- each is not run and
            FAILS, 'unaccepted [FAIL]' (O-25).
    """
    return tuple(name for name, reason in refused_tuple
                 if reason == UNACCEPTED_REASON)


def unstood_tuple(directory, app_set, fault_tuple, conf_fault_tuple=()):
    """
    RETURN: tuple[(str, str)], one (case name, verdict) for every case a
            directory FAILS BEFORE ANYTHING RUNS -- where a configuration
            that governs it cannot be read ('conf_fault_tuple', ND7),
            every case it declares ('conf-broken'); the files exploration
            could not read ('spec-broken'); then, where the configuration
            reads, the book's tests and choices the directory no longer
            declares ('test-vanished', 'test-choice-vanished').

    ONE LAW, TWO READERS (services E-128): 'hwut.run' counts these as
    failing cases, and 'hwut.report' reports what the run counts. Neither
    is in the book as a verdict of its own -- the run never dispatches
    them -- so both ask this function, and the tree, directly.
    """
    #  ONE FAULT, ONE FAILURE (D-63, services E-181): a test whose
    #  header does not parse is no member of the app set, and the book,
    #  asked against the app set, would read it as deleted -- 'in book,
    #  no such test' beside 'spec [FAIL]' for one file that stands. Its
    #  declaration cannot be read, so the book cannot be judged against
    #  it: the header fault alone is said, and the book row stays.
    broken_tuple = broken_app_tuple(app_set, fault_tuple)
    broken_set   = set(broken_tuple)
    if conf_fault_tuple:
        #  A CONFIGURATION THAT CANNOT BE READ (ND7, services E-190): what
        #  it governs cannot be run as written -- every declared case
        #  fails by name. The book is not judged against a declaration
        #  read under a configuration that does not read.
        later = tuple((name if choice is None else "%s %s" % (name, choice),
                       "conf-broken")
                      for name, app in sorted(app_set.app_db.items())
                      for choice in app.choice_db)
    else:
        later = tuple(pair for pair in vanished_tuple(directory, app_set)
                      if pair[0].partition(" ")[0] not in broken_set)
    #  ONE ORDER ON EVERY PAGE (2026-10-19, "order must be the same"):
    #  by test, then choice -- the order the report and HINTS stand in.
    return tuple(sorted(
        tuple((name, "spec-broken") for name in broken_tuple) + later,
        key=lambda pair: tuple(pair[0].partition(" ")[::2])))


def _walked(root, wish):
    """
    RETURN: tuple, what the walk below 'root' decided for 'wish' --
              [0] the explored tree
              [1] dict, path -> the decision RUN here
              [2] dict, platform -> [decision handed, ...]
              [3] list, the decisions NOT RUN, each at its outermost
              [4] list, every directory's required tuple, for '-p' NOTEs
    """
    decide       = decider(root, wish)
    decision_db  = {}                  # path -> the decision RUN here
    handed_db    = {}                  # platform -> [decision, ...]
    not_run_list = []
    candidate_list = []                # every directory's C, for '-p' notes

    def gate(path):
        """RETURN: str, GATE_RUN: every level is decided by 'entry_gate'."""
        return GATE_RUN

    def _below_f(decision, decision_list):
        """RETURN: bool, 'decision' lies at or below one of 'decision_list'
        decided ALIKE -- the same state, platform and reason: said once,
        at the outermost."""
        return any((decision.path == d.path
                    or decision.path.startswith(d.path + os.sep))
                   and (d.state, d.platform, d.reason)
                       == (decision.state, decision.platform, decision.reason)
                   for d in decision_list)

    def entry_gate(directory, required):
        """RETURN: None where 'directory' runs here; '' where it is handed
        or, over there, another platform's; '' too where no platform takes
        it -- its decision kept for the 'not-run' event."""
        decision = decide(directory, required)
        candidate_list.append(decision.required_tuple)
        if decision.state == RUN:
            decision_db[directory] = decision
            return None
        if decision.state == HANDED:
            group = handed_db.setdefault(decision.platform, [])
            if not _below_f(decision, group): group.append(decision)
        elif decision.state == NOT_RUN:
            if not _below_f(decision, not_run_list):
                not_run_list.append(decision)
        return ""

    #  WHAT THE WISH NEVER ASKED ABOUT IS NOT WALKED (2026-11-04): the
    #  directory rules ('--dir', '--exclude-dir') reach the WALK, as they
    #  do in 'hwut.execute' -- a directory they rule out is not explored,
    #  no application of it interviewed, and it reports nothing. MEASURED
    #  before: 'hwut.run --dir <one>' explored all 129 directories and
    #  said 'the selection is empty' of the other 128.
    tree = explore_tree(root, boundary_f=wish.no_bubbles_f,
                        bubble_gate=gate,
                        wanted_f=dir_wanted_f(wish, root),
                        entry_gate=entry_gate)
    return tree, decision_db, handed_db, not_run_list, candidate_list


def _owned_function(root, wish, label_view, walked):
    """
    RETURN: callable, 'owned(decision, label_f=True)' -> tuple of str, the
            test directories, relative to 'root', that 'decision' holds
            (none below a deeper decision) and the wish's directory rules
            want -- and, with 'label_f' and a label the wish asks, of
            which the label may select a run ('label.selects_below_f').
    """
    _, decision_db, handed_db, not_run_list, _ = walked
    owner_list = sorted([d.path for d in not_run_list]
                        + [d.path for g in handed_db.values() for d in g]
                        + list(decision_db), key=len, reverse=True)
    wanted_f   = dir_wanted_f(wish, root)
    label_tree = None
    if wish.asks_label_f() and label_view is not None:
        label_tree = parse_expression(wish.label_spec)

    def owned(decision, label_f=True):
        """RETURN: tuple of str, as '_owned_function' says."""
        found_list = []
        for name in test_directory_name_tuple(decision.path):
            path = os.path.normpath(os.path.join(decision.path, name))
            owner = next((o for o in owner_list
                          if path == o or path.startswith(o + os.sep)),
                         None)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            if owner != decision.path: continue
            if wanted_f is not None and not wanted_f(relative): continue
            if label_f and label_tree is not None \
               and not selects_below_f(label_view, label_tree, path,
                                       _recorded_run_tuple(path)):
                continue
            found_list.append(relative)
        return tuple(found_list)

    return owned


def _recorded_run_tuple(directory):
    """
    RETURN: tuple of (str, str), '(absolute file, choice)' for every run
            the book of the test directory 'directory' records -- the
            runs known to stand there without asking an application.
            None, where no book stands: the runs are not known.
    """
    path = os.path.join(directory, "GOOD", "book.csv")
    try:
        with open(path, encoding="utf-8") as fh:
            row_list = [line.rstrip("\n").split(";") for line in fh
                        if line.strip() and not line.startswith("#")]
    except OSError:
        return None
    if not row_list or row_list[0][:2] != ["test", "choice"]: return None
    #  AN EMPTY TEST CELL is the row above's test (the register's own
    #  shorthand).
    run_list, test = [], ""
    for row in row_list[1:]:
        if len(row) < 2: continue
        test = row[0] or test
        run_list.append((os.path.join(directory, test), row[1] or None))
    return tuple(run_list)


def missing_platform_tuple(root, wish, label_view=None):
    """
    RETURN: tuple of (str, str, tuple of str), one per platform the next
            'hwut.run' below 'root' needs and that is not ready now
            ('platforms.is_ready'): its name, why -- missing, or its
            image still to be built --, and the test directories
            (relative to 'root') that need it, in the order the walk met
            them. Empty where every platform needed is ready. Builds
            nothing.

    Raises PlatformRefused as 'decision_tuple' does.
    """
    decision_tuple(root, wish)
    walked = _walked(root, wish)
    owned  = _owned_function(root, wish, label_view, walked)
    found_db = {}
    pair_list = [(d, d.why) for d in walked[3] if d.reason == "reachable"]
    for group in walked[2].values():
        ready_f, why = platforms.is_ready(group[0].platform, group[0].spec)
        if not ready_f: pair_list.extend((d, why) for d in group)
    for decision, why in pair_list:
        directory_tuple = owned(decision)
        if not directory_tuple: continue
        _, directory_list = found_db.setdefault(decision.platform,
                                                (why, []))
        directory_list.extend(directory_tuple)
    return tuple((name, why, tuple(directory_list))
                 for name, (why, directory_list) in found_db.items())


def orchestrate(root, wish, build_interview=None, label_view=None):
    """
    RETURN: CTreePlan, what 'wish' comes to on the tree below 'root':
            explored under the configuration tree, determined per
            directory (P-17).

    The Bookkeeper of each directory is made HERE and handed down,
    and only where the wish asks the base. THE LABEL VIEW IS NOT: the
    engine never opens 'HWUT_ROOT/labels.txt' -- a face builds it
    ('services/lib/labels.view_at') and hands it in, and 'None' means no
    label knowledge reaches the selection (disc-8).

    WHICH BUBBLE RUNS WHERE is decided first, from the confs alone
    ('plan/bubble.py', spec/42 section 3): confs refused raise
    PlatformRefused HERE; a bubble not run here is not walked for tests --
    nothing of it interviewed, nothing written -- and stands in the
    plan's 'not_run_tuple'. A directory below requiring a tool its
    bubble's platform does not announce is not entered (o-57), its NOTE
    among the plan's warnings.
    """
    #  THE REFUSALS FIRST (o-52, o-53): raised before anything is walked.
    decision_tuple(root, wish)
    #  EACH DIRECTORY DECIDED ON ITS OWN (intend/45 R-4): the walk asks the
    #  gate at every level; what runs here is entered, what is handed is
    #  gathered BY PLATFORM -- one far run each -- what no platform takes
    #  is not run, and said once, at its outermost directory.
    walked = _walked(root, wish)
    tree, decision_db, handed_db, not_run_list, candidate_list = walked
    owned = _owned_function(root, wish, label_view, walked)
    #  A PLATFORM MISSING STOPS THE RUN BEFORE IT BEGINS (ruled
    #  2026-11-26): every platform is taken to stand; one a wanted
    #  directory needs -- under the label the wish asks, where it asks
    #  one (ruled 2026-11-27, "(b)") -- and that is not there is said,
    #  with the words that take it out: nothing is interviewed, nothing
    #  run, and nothing said of the tests it holds.
    missing_list = [(d.platform, d.why)
                    for d in not_run_list
                    if d.reason == "reachable" and owned(d)]
    if missing_list: raise PlatformMissing(missing_text(missing_list))
    #  ONE FAR RUN PER PLATFORM (intend/45 R-4): the project's root, the
    #  wish as given, '--as-platform' and the near run's platform words --
    #  so the far run decides every directory as the near run did, and
    #  runs exactly those decided for it. Under a label, a directory the
    #  label selects nothing of is not handed (ruled 2026-11-27).
    handed_list = []
    for platform, group in handed_db.items():
        if wish.asks_label_f():
            group = [d for d in group if owned(d)]
            if not group: continue
        far_argv = wish.far_argv(".", platform)
        if far_argv is None: continue
        far_argv += wish.platform_word_list()
        directory_tuple = tuple(
            os.path.normpath(os.path.join(d.name, t)).replace(os.sep, "/")
            for d in group for t in test_directory_name_tuple(d.path))
        handed_list.append((replace(group[0], path=os.path.abspath(root),
                                    name=".",
                                    directory_tuple=directory_tuple),
                            far_argv))
    #  EVERY PLATFORM HANDED TO IS MADE READY BEFORE THE RUN BEGINS
    #  (ruled 2026-11-26): its image built where it does not stand. One
    #  that cannot be stops the run as a platform missing does, the
    #  build's lines beside the reason; what a ready one said goes
    #  before the first case.
    ready_db, made_list = {}, []
    for decision, _ in handed_list:
        if decision.platform in ready_db: continue
        line_list = []
        ready_db[decision.platform] = (platforms.start(decision.platform,
                                                       decision.spec,
                                                       line_list.append),
                                       line_list)
        made_list.extend(line_list)
    missing_list = [(name, why) for name, ((ready_f, why), _)
                    in ready_db.items() if not ready_f]
    if missing_list:
        raise PlatformMissing(missing_text(
                  missing_list, [line for name, (ready, line_list)
                                 in ready_db.items() if not ready[0]
                                 for line in line_list]))
    factory = None
    if wish.asks_base_f():
        def factory(directory):
            return Bookkeeper(os.path.normpath(os.path.join(root, directory)))
    def case_gate(directory, app_set):
        """RETURN: callable, 'admit(test, choice)' refusing a case whose
        header requires a tool its bubble's platform does not announce."""
        owner = owner_of(decision_db, directory)
        return lambda test, choice: case_refusal(owner, app_set, test,
                                                 choice)

    tree_plan = determine_tree(tree, wish,
                               bookkeeper_factory = factory,
                               build_interview    = build_interview,
                               label_view         = label_view,
                               case_gate          = case_gate)
    #  A '-p' NO DIRECTORY REQUIRES (spec/42 section 2): one NOTE each,
    #  asked of every directory decided.
    note_tuple = unrequired_platform_note_tuple(wish, candidate_list) \
                 + pending_move_note_tuple(tree_plan) + tuple(made_list)
    not_run_n, said_list = 0, []
    for decision in not_run_list:
        #  WHAT THE LABEL SELECTS NOTHING OF is not asked about: neither
        #  said nor counted (ruled 2026-11-27).
        mine_n = len(owned(decision))
        if mine_n:
            not_run_n += mine_n
            said_list.append(decision)
    return replace(tree_plan,
                   warning_tuple = tree_plan.warning_tuple + note_tuple,
                   not_run_tuple = tuple(said_list),
                   not_run_n     = not_run_n,
                   handed_tuple  = tuple(handed_list),
                   gone_tuple    = roster_gone_tuple(root, wish))


def pending_move_note_tuple(tree_plan):
    """
    RETURN: tuple of str, one note per test that stands in one directory
            with NO GOOD file while ANOTHER directory's book records it and
            it does not stand there (CR-7): 'hwut.rename' carried its
            records, and the 'git mv' of the source is still owed. Without
            the note the run says 'accept it' -- which would make fresh
            GOOD files at the old place.
    """
    root = tree_plan.root
    vanished_db = {}                         # test -> [directory]
    fresh_list  = []                         # (directory, test)
    for entry in tree_plan:
        whole = os.path.normpath(os.path.join(root, entry.directory))
        for name, verdict in vanished_tuple(whole, entry.app_set):
            if verdict == "test-vanished":
                vanished_db.setdefault(name, []).append(entry.directory)
        for name in no_good_file_tuple(entry.refused_tuple):
            test = name.partition(" ")[0]
            if (entry.directory, test) not in fresh_list:
                fresh_list.append((entry.directory, test))
    result = []
    for directory, test in fresh_list:
        if test in Bookkeeper(os.path.join(root, directory)).tests(): continue
        there = [d for d in vanished_db.get(test, ()) if d != directory]
        if len(there) != 1: continue
        source = "%s/%s" % (directory, test)
        target = "%s/%s" % (there[0], test)
        result.append("NOTE: pending move? '%s' stands, and its records "
                      "stand in '%s' => git mv %s %s"
                      % (source, there[0], source, target))
    return tuple(result)


def roster_gone_tuple(root, wish):
    """
    RETURN: tuple of str, the TEST directories 'HWUT_ROOT/directories.txt'
            records that do not stand, below 'root' and wanted by the
            wish's directory rules -- relative to 'root', '/'-separated,
            sorted (CR-2). Empty where no roster stands, and where the wish
            asks a question of cases (a glob, a label, '--fail', ...): a
            directory that does not stand offers no case to ask it of.
    """
    from hwut.engine.bookkeeper import roster
    if not wish.states_no_case_rule_f(): return ()
    tree_root = roster.root_of(root)
    if tree_root is None: return ()
    root = os.path.abspath(root)
    def relative_of(directory):
        return os.path.relpath(directory, root).replace(os.sep, "/")
    wanted = dir_wanted_f(wish, root)
    wanted_f = None if wanted is None \
               else (lambda tree_relative:
                         wanted(relative_of(os.path.join(tree_root,
                                                         tree_relative))))
    return tuple(relative_of(roster.directory_of(tree_root, entry))
                 for entry in roster.gone_tuple(tree_root, root, wanted_f))


def orchestrator(root, wish, dispatcher_factory, worker_max_n=None,
                 clock=None, strategy=None, label_view=None,
                 selection_order=None):
    """
    RETURN: asyncio.Queue, the report stream of the run -- the events
            of 'vocabulary.py', then one 'None'. The run stands as an
            asyncio task; the caller reads the queue.

    Requires a running event loop; determination happens before the
    first event is emitted, so a refused wish raises HERE, at the
    call, not inside the task.

    A finding of determination that decides nothing -- a glob that
    met only silenced runs -- is a 'warning' EVENT of the stream, on
    the same road as a fault, before the first run. There is no side
    road for it: a callback that a caller forgot to hand in once lost
    every warning 'hwut.run' had (O-26).
    """
    tree_plan = orchestrate(root, wish, label_view=label_view)
    queue     = asyncio.Queue()
    asyncio.ensure_future(
        CTreeScheduler(dispatcher_factory, worker_max_n,
                       clock, strategy,
                       selection_order).run(tree_plan, queue))
    return queue
