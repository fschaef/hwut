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

CTreeScheduler runs the directories SERIALLY, in walk order, each
under its own frame and its own dispatcher (P-17). Everything that
leads to the executability of a test is the test: a [MISDEP] node and
an UNSUPPORTED node each get their 'run-ended', verdict and cause
named (O-3).
______________________________________________________________________________
"""
import asyncio
import os
from datetime import datetime, timezone

from ..bookkeeper.bookkeeper       import Bookkeeper
from ..exploration.tree_explorer   import explore_tree
from ..plan.form                   import E_NodeKind
from ..plan.tree                   import determine_tree
from ..scheduler.scheduler         import Scheduler
from ..scheduler.state             import E_NodeState, FAILURE_SET
from .vocabulary                   import event


#  E_NodeState x kind -> the verdict word (O-3). ENDED_BAD names the
#  kind's own breaking; the rest name themselves.
def _verdict(state, node_kind):
    """
    RETURN: str, the verdict word of the vocabulary for a node of that
            kind ending in that state.
    """
    if state is E_NodeState.ENDED_GOOD:  return "ok"
    if state is E_NodeState.UNSUPPORTED: return "unsupported"
    if state is E_NodeState.MISDEP:      return "misdep"
    return {E_NodeKind.TEST:    "test-failed",
            E_NodeKind.BUILD:   "build-failed",
            E_NodeKind.SESSION: "launch-failed"}[node_kind]


def _utc_now():
    """RETURN: str, the current UTC instant, seconds resolution,
    ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CTreeScheduler:
    """Executes a CTreePlan, one directory after another, emitting the
    report stream into a queue."""

    def __init__(self, dispatcher_factory, worker_max_n=None,
                 clock=None):
        """
        RETURN: CTreeScheduler, ready to run a tree plan.

        'dispatcher_factory'  takes the ABSOLUTE directory path and
                              the directory's CTreePlanEntry, and
                              answers the I_Dispatcher for its work --
                              made above, handed down. A double may
                              ignore the entry.
        'worker_max_n'        the per-directory bound on work standing
                              at once; 'None' is no bound.
        'clock'               answers the 'when' string of an event;
                              the UTC instant where none is given. A
                              parameter so that a test may state the
                              clock.
        """
        self.dispatcher_factory = dispatcher_factory
        self.worker_max_n       = worker_max_n
        self.clock              = clock or _utc_now

    async def run(self, tree_plan, queue):
        """
        RETURN: None. Runs every entry of 'tree_plan' serially, in
                order; the report stream goes into 'queue'; one 'None'
                after 'tree-done' closes it.
        """
        def emit(kind, **field_db):
            queue.put_nowait(event(kind, self.clock(), **field_db))

        emit("tree-begun",
             directory_list=[entry.directory for entry in tree_plan])
        for fault in tree_plan.fault_tuple:
            emit("fault", directory=".", text=str(fault))

        good_f = not tree_plan.fault_tuple
        fail_n = 0
        for entry in tree_plan:
            try:
                entry_good_f, entry_fail_n = \
                    await self._run_directory(tree_plan.root, entry,
                                              emit)
            except Exception as error:
                #  A broken directory NEVER silences the stream: the
                #  breakage is an event (a held lock, a raising
                #  dispatcher), the directory is bad, the tree walks
                #  on and 'tree-done' still closes the queue.
                emit("fault", directory=entry.directory,
                     text="%s: %s" % (type(error).__name__, error))
                emit("dir-done", directory=entry.directory,
                     good=False, fail_db={})
                entry_good_f, entry_fail_n = False, 0
            good_f  = good_f and entry_good_f
            fail_n += entry_fail_n

        emit("tree-done", good=good_f, fail_n=fail_n)
        queue.put_nowait(None)

    async def _run_directory(self, root, entry, emit):
        """
        RETURN: [0] bool, True where the directory stood: frame good,
                    no fault, no failed node.
                [1] int, how many of its nodes failed.
        """
        directory = entry.directory
        for fault in entry.fault_tuple:
            emit("fault", directory=directory, text=str(fault))
        for report in entry.report_tuple:
            emit("report", directory=directory, text=str(report))
        emit("dir-begun", directory=directory,
             node_n=len(entry.plan))

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
                good_f  = state is E_NodeState.ENDED_GOOD
                verdict = _verdict(state, node.kind)
                if not good_f and report == "test-app-launch-failed":
                    verdict = "launch-failed"
                emit("run-ended", directory=directory,
                     node=node.name(), node_kind=node.kind.name,
                     good=good_f, verdict=verdict, **extra)

        dispatcher = self.dispatcher_factory(
                         os.path.normpath(os.path.join(root, directory)),
                         entry)
        report_of  = getattr(dispatcher, "report_of",
                             lambda name: None)
        scheduler  = Scheduler(dispatcher,
                               on_entry     = entry.on_entry,
                               on_exit      = entry.on_exit,
                               worker_max_n = self.worker_max_n,
                               notify       = notify)
        report = await scheduler.run(entry.plan)
        close  = getattr(dispatcher, "close", None)
        if close is not None: await close()
        fail_db = {name: state.name for name, state
                   in sorted(report.failure_db().items())}
        good_f  = report.good_f() and not entry.fault_tuple
        emit("dir-done", directory=directory, good=good_f,
             fail_db=fail_db)
        return good_f, len(fail_db)


def orchestrate(root, wish, build_interview=None):
    """
    RETURN: CTreePlan, what 'wish' comes to on the tree below 'root':
            explored under the configuration tree, determined per
            directory (P-17).

    The Bookkeeper of each directory is made HERE and handed down,
    and only where the wish asks the base.
    """
    tree = explore_tree(root)
    factory = None
    if wish.asks_base_f():
        factory = lambda directory: \
            Bookkeeper(os.path.normpath(os.path.join(root, directory)))
    return determine_tree(tree, wish,
                          bookkeeper_factory = factory,
                          build_interview    = build_interview)


def orchestrator(root, wish, dispatcher_factory, worker_max_n=None,
                 clock=None):
    """
    RETURN: asyncio.Queue, the report stream of the run -- the events
            of 'vocabulary.py', then one 'None'. The run stands as an
            asyncio task; the caller reads the queue.

    Requires a running event loop; determination happens before the
    first event is emitted, so a refused wish raises HERE, at the
    call, not inside the task.
    """
    tree_plan = orchestrate(root, wish)
    queue     = asyncio.Queue()
    asyncio.ensure_future(
        CTreeScheduler(dispatcher_factory, worker_max_n,
                       clock).run(tree_plan, queue))
    return queue
