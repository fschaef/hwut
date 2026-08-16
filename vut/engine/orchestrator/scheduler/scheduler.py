"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE SCHEDULER -- the unit that EXECUTES a test plan. It reads
         the plan, obeys its constraints, and hands every piece of work
         to a dispatcher. It runs no process itself: running is
         test_run's (P-1).

    frame           on_entry before any dispatch; on_exit after all
                    work has ended, ALWAYS. Entry failure: the frame
                    did not stand -- nothing is dispatched (P-10).
    admission       CPlanState says who MAY start; the scheduler picks
                    out of that, at run time, free to use timings (P-3).
    supports law    a BUILD or SESSION node ending BAD leaves the TEST
                    nodes it supports UNSUPPORTED -- they FAIL, they do
                    not wait (P-5).
    [MISDEP]        never dispatched, reported as FAILURE (P-6).
    sessions        a SESSION node is opened by dispatch and CLOSED
                    once every TEST node it supports stands terminal.

THE DISPATCHER (I_Dispatcher) is the seam to the world: one coroutine
per kind of work. A test drives the scheduler through a dispatcher of
its own and needs no process; the orchestrator's dispatcher hands the
work to test_run.

    open_session(node)      -> bool     the session launched
    run_build(node)         -> bool     the build stood
    run_test(node)          -> bool     the verdict
    close_session(node)     -> None
    run_script(role, text)  -> bool     'on_entry' / 'on_exit'

THE WORKER COUNT bounds how many pieces of work stand at once. 'None'
is no bound: the plan's own exclusion sets are then the only limit.
______________________________________________________________________________
"""
import asyncio
from abc         import ABC, abstractmethod
from dataclasses import dataclass, field

from ..plan.form  import E_NodeKind
from .state       import CPlanState, E_NodeState, FAILURE_SET


class I_Dispatcher(ABC):
    """WHERE THE WORK GOES. Every member is a coroutine; a failure is a
    VALUE (False), never an exception."""

    @abstractmethod
    async def run_script(self, role, command):
        """
        RETURN: bool, True where the frame script stood.

        'role' is 'on_entry' or 'on_exit'; 'command' the directory's
        own string.
        """

    @abstractmethod
    async def run_build(self, node):
        """RETURN: bool, True where the build action stood."""

    @abstractmethod
    async def open_session(self, node):
        """RETURN: bool, True where the interactive session launched."""

    @abstractmethod
    async def close_session(self, node):
        """RETURN: None. The session is spent; its process may go."""

    @abstractmethod
    async def run_test(self, node):
        """RETURN: bool, the verdict of the test run -- True where the
        test stood."""


@dataclass(frozen=True, slots=True)
class CRunReport:
    """WHAT ONE EXECUTION OF ONE PLAN CAME TO.

    'entry_f' and 'exit_f' are 'None' where the directory states no
    such script -- absence is data, not a silent True. 'dispatched' is
    what the scheduler actually started, in start order; the state of
    every node stands in 'state_db'."""
    entry_f:    bool | None
    exit_f:     bool | None
    state_db:   dict
    dispatched: tuple = ()

    def failure_db(self):
        """
        RETURN: dict, name -> E_NodeState, every node that failed:
                ENDED_BAD, UNSUPPORTED or MISDEP.
        """
        return {name: state for name, state in self.state_db.items()
                if state in FAILURE_SET}

    def good_f(self):
        """
        RETURN: bool, True where the frame stood and no node failed.
        """
        return self.entry_f is not False and self.exit_f is not False \
               and not self.failure_db()


class Scheduler:
    """Executes a plan through a dispatcher. One scheduler serves one
    run; 'run()' is a coroutine and may be driven by 'asyncio.run'."""

    def __init__(self, dispatcher, on_entry=None, on_exit=None,
                 worker_max_n=None):
        """
        RETURN: Scheduler, ready to run a plan.

        'dispatcher'    the I_Dispatcher the work goes to.
        'on_entry'      the directory's entry command, or 'None'.
        'on_exit'       the directory's exit command, or 'None'.
        'worker_max_n'  how many pieces of work may stand at once;
                        'None' is no bound.

        Raises AssertionError where 'worker_max_n' is not a positive
        number -- a bound of zero schedules nothing and is refused at
        the door.
        """
        assert isinstance(dispatcher, I_Dispatcher), \
               "Scheduler requires an I_Dispatcher; received a %s" \
               % type(dispatcher).__name__
        assert worker_max_n is None or worker_max_n >= 1, \
               "worker_max_n is %r; a bound below one schedules nothing" \
               % worker_max_n
        self.dispatcher   = dispatcher
        self.on_entry     = on_entry
        self.on_exit      = on_exit
        self.worker_max_n = worker_max_n

    async def run(self, plan):
        """
        RETURN: CRunReport, the state of every node of 'plan' after the
                run, the frame's outcome, and what was dispatched in
                start order.

        The entry script failing stops the run before any dispatch; the
        exit script runs in either case. Nothing raises: a failure is a
        state.
        """
        state      = CPlanState(plan)
        dispatched = []

        entry_f = None
        if self.on_entry is not None:
            entry_f = bool(await self.dispatcher.run_script("on_entry",
                                                            self.on_entry))
        if entry_f is not False:
            await self._dispatch_all(plan, state, dispatched)

        exit_f = None
        if self.on_exit is not None:
            exit_f = bool(await self.dispatcher.run_script("on_exit",
                                                           self.on_exit))

        return CRunReport(entry_f    = entry_f,
                          exit_f     = exit_f,
                          state_db   = dict(state.state_db),
                          dispatched = tuple(dispatched))

    async def _dispatch_all(self, plan, state, dispatched):
        """
        RETURN: None. Starts what may start, awaits the first ending,
                and repeats until every node stands terminal.
        """
        task_db    = {}                 # asyncio.Task -> node name
        closed_set = set()              # SESSION nodes already closed
        while not state.done_f():
            #  READINESS IS ASKED ANEW BEFORE EVERY START: starting one
            #  member of an exclusion set withdraws admission from the
            #  others, and a snapshot taken before the start no longer
            #  states the truth.
            while self.worker_max_n is None \
                  or len(task_db) < self.worker_max_n:
                ready_tuple = state.ready()
                if not ready_tuple: break
                name = ready_tuple[0]
                state.started(name)
                dispatched.append(name)
                task_db[asyncio.ensure_future(
                            self._work(plan.node(name)))] = name

            if not task_db:
                #  Nothing runs and nothing may start: only a plan
                #  violating its own construction laws reaches here.
                assert not state.stuck_f(), \
                       "the plan is stuck: %s remain(s) pending" \
                       % ", ".join(sorted(
                             name for name, node_state
                             in state.state_db.items()
                             if node_state is E_NodeState.PENDING))
                break

            done_set, _ = await asyncio.wait(
                              task_db, return_when=asyncio.FIRST_COMPLETED)
            for task in sorted(done_set, key=lambda t: task_db[t]):
                name = task_db.pop(task)
                state.ended(name, bool(task.result()))
            await self._close_spent_sessions(plan, state, closed_set)

    async def _work(self, node):
        """
        RETURN: bool, the outcome of one node's work: the build stood,
                the session launched, or the test's verdict.
        """
        if   node.kind is E_NodeKind.BUILD:
            return bool(await self.dispatcher.run_build(node))
        elif node.kind is E_NodeKind.SESSION:
            return bool(await self.dispatcher.open_session(node))
        else:
            return bool(await self.dispatcher.run_test(node))

    async def _close_spent_sessions(self, plan, state, closed_set):
        """
        RETURN: None. Closes every SESSION node that LAUNCHED and whose
                supported TEST nodes all stand terminal -- once each,
                the closed ones held in 'closed_set'.

        A session that did not launch is never closed: there is no
        process to let go of.
        """
        for node in plan:
            if node.kind is not E_NodeKind.SESSION:            continue
            name = node.name()
            if name in closed_set:                             continue
            if state.state(name) is not E_NodeState.ENDED_GOOD: continue
            if not state.session_spent_f(name):                continue
            closed_set.add(name)
            await self.dispatcher.close_session(node)
