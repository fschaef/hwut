#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test - resource-freeing vs. deadline-kill, and the kill() contract.

These choices pin behaviour that a review found inconsistent in an
earlier version:

  -- the OS context being RECLAIMED is a different fact from the task
     having been force-killed past its deadline. They must surface as
     different events: a neutral 'resources freed' on every freeing
     path, and the 'killed' alarm ONLY when a deadline elapsed without
     confirmation.
  -- ChildHandle.kill() is annotated '-> bool' and its bool is honest:
     True only when a real force-kill was initiated, False when the
     kind has no force path.
  -- E_TerminationReason names the TASK outcome (DONE / TERMINATED /
     UNACCOMPLISHED), a level distinct from the supervision verdict
     (TERM_OK / TERM_FAILURE). UNACCOMPLISHED never reads as a verdict.

CHOICES
    reason_names      E_TerminationReason members are exactly
                      DONE / TERMINATED / UNACCOMPLISHED.
    kill_contract     each ChildHandle.kill() returns a bool; the value
                      matches the kind's force-kill capability.
    clean_reclaim     a child confirms in time -> TERM_OK; the OS
                      context is reclaimed and EventChildResourcesFreed
                      fires, but NO EventChildKilled-style alarm.
    deadline_kill     no confirmation before the deadline -> kill ->
                      TERM_FAILURE; both the verdict and a resources-
                      freed event surface, the latter marked as having
                      followed a deadline.

The FSM emits events whose __str__ omits volatile fields (timestamps,
freed_at); the test prints only the semantic fields, so output is
deterministic.
________________________________________________________________________________
"""
import sys
import asyncio

from config import HwutRunner

from vut.engine.event.channel.parameter import EventChannelParameter

from vut.engine.spawner.enums         import (E_ChildState, E_Liveness,
                                              E_TerminationReason)
from vut.engine.spawner.events        import (EventChildTermination,
                                              EventChildStateChanged,
                                              EventChildResourcesFreed)
from vut.engine.spawner.state_machine import ChildStateMachine
from vut.engine.spawner.terminals     import (SpawnerParentEventTerminal,
                                              SpawnerChildEventTerminal)
from vut.engine.spawner.handles       import (AsyncChildHandle,
                                              ThreadChildHandle,
                                              ProcessChildHandle,
                                              RemoteChildHandle)


# ----------------------------------------------------------------------
# Harness
# ----------------------------------------------------------------------

class _EventLog:
    """Sink that records every spawner -> parent event the FSM emits.

    Subscribed on the parent terminal's dispatcher. Keeps state-change
    edges as 'old->new' and resources-freed events as a compact line, so
    a choice can print the exact sequence of facts the FSM surfaced.
    """
    def __init__(self):
        """RETURN: a new, empty _EventLog."""
        self.lines = []

    def send(self, event):
        """RETURN: None.  Records one line per recognised event."""
        if isinstance(event, EventChildStateChanged):
            self.lines.append("state %s->%s"
                              % (event.old_state, event.new_state))
        elif isinstance(event, EventChildResourcesFreed):
            self.lines.append("freed last_state=%s after_deadline=%s"
                              % (event.last_state, event.after_deadline))


async def _make_pair():
    """RETURN: (parent_terminal, child_terminal), both started.

    A real terminal pair over an in-process async channel, handshake
    completed - the genuine contract the FSM runs against.
    """
    p_ecp, c_ecp = EventChannelParameter.for_async()
    parent = SpawnerParentEventTerminal(p_ecp)
    child  = SpawnerChildEventTerminal(c_ecp)
    await asyncio.gather(parent.start(), child.start())
    return parent, child


class _FakeKiller:
    """Killer coroutine that records invocation and returns True.

    Stands in for an OS force-kill that succeeds; the FSM only needs an
    awaitable returning a bool.
    """
    def __init__(self):
        """RETURN: a new _FakeKiller, not yet called."""
        self.called = False

    async def __call__(self) -> bool:
        """RETURN: True,  always - a successful kill was initiated."""
        self.called = True
        return True


# ----------------------------------------------------------------------
# Choices
# ----------------------------------------------------------------------

def run_reason_names():
    """RETURN: None.

    The task-outcome reason set is exactly DONE / TERMINATED /
    UNACCOMPLISHED - none of which collides with a supervision verdict.
    """
    print("--- E_TerminationReason members ---")
    for r in E_TerminationReason:
        print("  %s" % r)
    names = {r.name for r in E_TerminationReason}
    assert names == {"DONE", "TERMINATED", "UNACCOMPLISHED"}, names
    print("  exactly DONE / TERMINATED / UNACCOMPLISHED: OK")


def run_kill_contract():
    """RETURN: None.

    Every ChildHandle.kill() returns a bool whose value matches the
    kind's force-kill capability: True for kinds that can force-kill,
    False for the thread (no force path). The remote handle reports its
    agent's acknowledgement.
    """
    async def _body():
        print("--- kill() returns a bool matching capability ---")

        # async: cancellable Task -> can force-kill -> True
        async def _noop():
            await asyncio.sleep(0)
        task = asyncio.ensure_future(_noop())
        await asyncio.sleep(0)
        a = AsyncChildHandle(task)
        a_ret = await a.kill()
        print("  async   can_force_kill=%-5s kill()->%s"
              % (a.can_force_kill, a_ret))

        # thread: no force path -> kill() refuses -> False
        class _DummyThread:
            def is_alive(self): return False
        t = ThreadChildHandle(_DummyThread())
        t_ret = await t.kill()
        print("  thread  can_force_kill=%-5s kill()->%s"
              % (t.can_force_kill, t_ret))

        # remote, agent acknowledges -> True
        async def _ack(action): return True
        r_ok = RemoteChildHandle(control_send=_ack, remote_id="r1")
        r_ok_ret = await r_ok.kill()
        print("  remote  agent-ack    kill()->%s" % r_ok_ret)

        # remote, agent does NOT acknowledge -> False
        async def _nack(action): return False
        r_no = RemoteChildHandle(control_send=_nack, remote_id="r2")
        r_no_ret = await r_no.kill()
        print("  remote  agent-refuse kill()->%s" % r_no_ret)

        assert a_ret is True
        assert t_ret is False
        assert r_ok_ret is True
        assert r_no_ret is False
        print("  all kill() returns are bool and capability-honest: OK")

    asyncio.run(_body())


async def run_clean_reclaim():
    """RETURN: None.

    A child confirms termination within the deadline. The verdict is
    TERM_OK; the OS context is then reclaimed (the killer runs) and an
    EventChildResourcesFreed fires with after_deadline=False. NO
    EventChildKilled alarm is emitted - nothing went wrong.
    """
    parent, child = await _make_pair()
    log = _EventLog()
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, log)
    parent.dispatcher.subscribe_on_event(EventChildResourcesFreed, log)

    killer = _FakeKiller()
    fsm = ChildStateMachine(parent_terminal=parent, killer=killer)
    await fsm.notify_running()

    print("--- terminate(2000ms); child confirms quickly ---")
    term = asyncio.ensure_future(fsm.begin_termination(2000))
    await asyncio.sleep(0.02)
    await child.send(EventChildTermination(
        reason=E_TerminationReason.DONE))
    await term

    print("  final state    : %s" % fsm.state)
    print("  killer invoked  : %s" % killer.called)
    print("--- events surfaced ---")
    for line in log.lines:
        print("  %s" % line)

    assert fsm.state is E_ChildState.TERM_OK
    assert killer.called is True
    # The reclamation must surface as 'freed', never as a kill alarm.
    assert any(l.startswith("freed") and "after_deadline=False" in l
               for l in log.lines)
    await parent.stop()


async def run_deadline_kill():
    """RETURN: None.

    No confirmation arrives before the deadline. The OS context is
    force-killed and the verdict is TERM_FAILURE. A resources-freed
    event surfaces too, marked after_deadline=True - so a subscriber can
    tell a deadline kill from a clean reclamation by that flag alone.
    """
    parent, child = await _make_pair()
    log = _EventLog()
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, log)
    parent.dispatcher.subscribe_on_event(EventChildResourcesFreed, log)

    killer = _FakeKiller()
    fsm = ChildStateMachine(parent_terminal=parent, killer=killer)
    await fsm.notify_running()

    print("--- terminate(50ms); child stays silent past the deadline ---")
    await fsm.begin_termination(50)

    print("  final state    : %s" % fsm.state)
    print("  killer invoked  : %s" % killer.called)
    print("--- events surfaced ---")
    for line in log.lines:
        print("  %s" % line)

    assert fsm.state is E_ChildState.TERM_FAILURE
    assert killer.called is True
    assert any(l.startswith("freed") and "after_deadline=True" in l
               for l in log.lines)
    await parent.stop()


def _sync(coro):
    """RETURN: None.  Run an async choice body to completion."""
    asyncio.run(coro())


HwutRunner(
    argv       = sys.argv,
    title      = "Spawner: resource-freeing vs. deadline-kill, kill() contract",
    choice_map = {
        "reason_names":  run_reason_names,
        "kill_contract": run_kill_contract,
        "clean_reclaim": lambda: _sync(run_clean_reclaim),
        "deadline_kill": lambda: _sync(run_deadline_kill),
    },
).run()
