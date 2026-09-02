"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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
from dataclasses import dataclass
from datetime    import datetime, timezone

from ...bookkeeper.api       import Bookkeeper
from ..exploration.tree_explorer   import explore_tree
from ..plan.form                   import E_NodeKind
from ..plan.tree                   import determine_tree
from ..scheduler.budget            import CBudget
from ..scheduler.scheduler         import Scheduler
from ..scheduler.state             import E_NodeState
from .strategy                     import CLinear
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
                    E_NodeKind.SESSION: "launch-failed"}[node_kind]


def _utc_now():
    """RETURN: str, the current UTC instant, seconds resolution,
    ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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

    def __init__(self, root, entry, dispatcher_factory):
        """
        RETURN: CDirectoryWork for 'entry' below the absolute 'root'.
        """
        self.root               = root
        self.entry              = entry
        self.dispatcher_factory = dispatcher_factory

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
        for report in entry.report_tuple:
            emit("report", directory=directory, text=str(report))
        broken_tuple  = _broken_app_tuple(entry)
        vanished_tuple = _vanished_tuple(self.root, entry)
        emit("dir-begun", directory=directory,
             node_n=len(entry.plan) + len(broken_tuple)
                    + len(vanished_tuple))
        for name in broken_tuple:
            emit("run-ended", directory=directory, node=name,
                 node_kind="TEST", good=False, verdict="spec-broken")
        #  THE BOOK DOCUMENTS WHAT TESTS EXIST, and a test it records
        #  that no longer stands is a FAILING TEST, not a silence: the
        #  documentation and the tree disagree, and only a person can
        #  say which of the two is wrong. Reported exactly as a broken
        #  specification is -- terminal before anything runs, counted,
        #  and named in HINTS.
        for name, verdict in vanished_tuple:
            emit("run-ended", directory=directory, node=name,
                 node_kind="TEST", good=False, verdict=verdict)

        #  [MISDEP] nodes are terminal before anything runs (P-6):
        #  their 'run-ended' comes first, verdict named.
        for node in entry.plan:
            if not node.misdep_f: continue
            emit("run-ended", directory=directory, node=node.name(),
                 node_kind=node.kind.name, good=False,
                 verdict="misdep")

        def notify(kind, **field_db):
            if kind == "frame":
                emit("frame", directory=directory,
                     role=field_db["role"],
                     good=bool(field_db["good_f"]))
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
                good_f  = state is E_NodeState.ENDED_GOOD
                verdict = _verdict(state, node.kind)
                if not good_f and report == "test-app-launch-failed":
                    verdict = "launch-failed"
                emit("run-ended", directory=directory,
                     node=node.name(), node_kind=node.kind.name,
                     good=good_f, verdict=verdict, **extra)

        dispatcher = self.dispatcher_factory(
                         os.path.normpath(os.path.join(self.root,
                                                       directory)),
                         entry)
        report_of  = getattr(dispatcher, "report_of",
                             lambda name: None)
        detail_of  = getattr(dispatcher, "detail_of",
                             lambda name: None)
        scheduler  = Scheduler(dispatcher,
                               on_entry     = entry.on_entry,
                               on_exit      = entry.on_exit,
                               worker_max_n = budget,
                               notify       = notify)
        report = await scheduler.run(entry.plan)
        close  = getattr(dispatcher, "close", None)
        if close is not None: await close()
        fail_db = {name: state.name for name, state
                   in sorted(report.failure_db().items())}
        good_f  = report.good_f() and not entry.fault_tuple \
                  and not vanished_tuple
        emit("dir-done", directory=directory, good=good_f,
             fail_db=fail_db)
        return CDirDone(good_f, len(fail_db))


class CTreeScheduler:
    """Executes a CTreePlan -- its directories in parallel under one
    budget, or one after another -- emitting the report stream into a
    queue."""

    def __init__(self, dispatcher_factory, worker_max_n=None,
                 clock=None, strategy=None):
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

    async def run(self, tree_plan, queue):
        """
        RETURN: None. Runs every entry of 'tree_plan' under the budget,
                each started when the strategy says; the report stream
                goes into 'queue'; one 'None' after 'tree-done' closes
                it.
        """
        def emit(kind, **field_db):
            queue.put_nowait(event(kind, self.clock(), **field_db))

        emit("tree-begun",
             directory_list=[entry.directory for entry in tree_plan])
        for fault in tree_plan.fault_tuple:
            emit("fault", directory=".", text=str(fault))

        budget    = CBudget(self.worker_max_n)
        unit_list = [CDirectoryWork(tree_plan.root, entry,
                                    self.dispatcher_factory)
                     for entry in tree_plan]
        done_list = await self.strategy.run(
                        [(lambda unit=unit:
                              self._guarded(unit, emit, budget))
                         for unit in unit_list])

        good_f = not tree_plan.fault_tuple \
                 and all(done.good_f for done in done_list)
        fail_n = sum(done.fail_n for done in done_list)
        emit("tree-done", good=good_f, fail_n=fail_n)
        queue.put_nowait(None)

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


def _broken_app_tuple(entry):
    """
    RETURN: tuple[str], every source file a fault of this directory
            names that DID NOT become a node -- sorted, each once.

    A file that parsed and ran stands in the plan; a file the fault
    names and the plan does not is one exploration could not read.
    The directory's own file ('hwut.conf') names no application and
    is left to the fault line alone.
    """
    planned = set()
    for node in entry.plan:
        name = node.name()
        planned.add(name)
        planned.add(name.split(" ", 1)[0])
        if "[" in name: planned.add(name.split("[", 1)[0].strip())
    named = set()
    for fault in entry.fault_tuple:
        file = getattr(fault, "file", None)
        if not file or file.endswith(".conf"):     continue
        if file in planned:                        continue
        named.add(file)
    return tuple(sorted(named))


def _vanished_tuple(root, entry):
    """
    RETURN: tuple[(str, str)], one (node name, verdict) for every test
            the BOOK records that the directory no longer declares:
                'test-vanished'         the application is gone
                'test-choice-vanished'  the application stands, that
                                        choice of it does not
            Empty where book and tree agree, and where no book stands.

    THE DECLARATION IS THE APP SET, NEVER THE PLAN. 'entry.app_set' is
    what EXISTS in the directory; 'entry.plan' is what the WISH
    selected of it. Asking against the plan would read every
    unselected choice as vanished, so 'hwut.run test-x.py one' would
    accuse 'two' of not existing -- the wish narrows what runs, and
    narrows nothing about what is there.

    A BOOK THAT CANNOT BE READ SAYS NOTHING. The absence of a base, or
    a base that will not open, is not evidence that a test vanished.
    """
    app_set = getattr(entry, "app_set", None)
    if app_set is None: return ()
    declared_db = {app.source_file: list(app.choice_db)
                   for app in app_set}
    try:
        book = Bookkeeper(os.path.normpath(os.path.join(root,
                                                        entry.directory)))
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


def orchestrate(root, wish, build_interview=None, label_view=None):
    """
    RETURN: CTreePlan, what 'wish' comes to on the tree below 'root':
            explored under the configuration tree, determined per
            directory (P-17).

    The Bookkeeper of each directory is made HERE and handed down,
    and only where the wish asks the base. THE LABEL VIEW IS NOT: the
    engine never opens 'hwut-root.labels' -- a face builds it
    ('services/lib/labels.view_at') and hands it in, and 'None' means no
    label knowledge reaches the selection (disc-8).
    """
    tree = explore_tree(root)
    factory = None
    if wish.asks_base_f():
        factory = lambda directory: \
            Bookkeeper(os.path.normpath(os.path.join(root, directory)))
    return determine_tree(tree, wish,
                          bookkeeper_factory = factory,
                          build_interview    = build_interview,
                          label_view         = label_view)


def orchestrator(root, wish, dispatcher_factory, worker_max_n=None,
                 clock=None, strategy=None, label_view=None,
                 warn=None):
    """
    RETURN: asyncio.Queue, the report stream of the run -- the events
            of 'vocabulary.py', then one 'None'. The run stands as an
            asyncio task; the caller reads the queue.

    Requires a running event loop; determination happens before the
    first event is emitted, so a refused wish raises HERE, at the
    call, not inside the task.

    'warn' takes one finding at a time and is called BEFORE the first
    event: a finding that decides nothing still belongs before the
    thing it is about.
    """
    tree_plan = orchestrate(root, wish, label_view=label_view)
    if warn is not None:
        for text in tree_plan.warning_tuple: warn(text)
    queue     = asyncio.Queue()
    asyncio.ensure_future(
        CTreeScheduler(dispatcher_factory, worker_max_n,
                       clock, strategy).run(tree_plan, queue))
    return queue
