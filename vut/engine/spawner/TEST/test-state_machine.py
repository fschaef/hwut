#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test - the child-state machine (state_machine.py).

Drives ChildStateMachine directly, over a REAL SpawnerParentEventTerminal
/ SpawnerChildEventTerminal pair connected by an in-process async
channel. No process is spawned: the FSM is exercised in isolation, but
against the real terminal contract (not a fake), so the expect_* and
dispatch paths are the production ones.

CHOICES
    running          LAUNCHED -> RUNNING via notify_running().
    self_completion  RUNNING -> TERM_OK when the child confirms on its
                     own (no terminate requested) - DISCUSSION.txt D7.
    term_ok          begin_termination(): child confirms in time
                     -> TERM_OK.
    term_failure     begin_termination(): no confirmation before the
                     deadline -> kill -> TERM_FAILURE.
    lost_connection  notify_channel_silent(): handle ALIVE / UNKNOWN
                     -> TERM_LOST_CONNECTION; handle DEAD -> TERM_FAILURE
                     (DISCUSSION.txt D8 as clarified).
    suspend_resume   suspend_child()/resume_child() with and without an
                     OS handle - the D9 refusal convention.

Every choice prints the transition sequence it drove. Output is
deterministic: the FSM emits EventChildStateChanged whose __str__ is
old->new only (no timestamp); the test never prints killed_at.
________________________________________________________________________________
"""
import config  # noqa: F401  (path bootstrap; must precede vut.* imports)
import sys
import asyncio

from vut.language_support.python.hwut_runner import HwutRunner

from vut.engine.event.channel.parameter import EventChannelParameter

from vut.engine.spawner.enums         import E_ChildState
from vut.engine.spawner.events        import (EventChildTermination,
                                              EventChildStateChanged,
                                              E_TerminationReason)
from vut.engine.spawner.state_machine import ChildStateMachine
from vut.engine.spawner.terminals     import (SpawnerParentEventTerminal,
                                              SpawnerChildEventTerminal)
from vut.engine.spawner.handles       import E_Liveness


# ----------------------------------------------------------------------
# Harness
# ----------------------------------------------------------------------

class _Recorder:
    """Sink that records the FSM's EventChildStateChanged edges.

    Subscribed on the parent terminal's dispatcher; each edge is kept as
    an 'old->new' string so a test can print the exact sequence it
    drove.
    """
    def __init__(self):
        """RETURN: a new, empty _Recorder."""
        self.edges = []

    def send(self, event):
        """RETURN: None.  Records one edge if 'event' is a state change."""
        if isinstance(event, EventChildStateChanged):
            self.edges.append("%s->%s" % (event.old_state, event.new_state))


async def _make_pair():
    """RETURN: (parent_terminal, child_terminal), both started.

    Builds a real SpawnerParentEventTerminal / SpawnerChildEventTerminal
    over an in-process async channel and completes their Up handshake by
    starting both concurrently. The pair is the genuine terminal
    contract the FSM runs against.
    """
    p_ecp, c_ecp = EventChannelParameter.for_async()
    parent = SpawnerParentEventTerminal(p_ecp)
    child  = SpawnerChildEventTerminal(c_ecp)
    # Start concurrently: each start() blocks on the other's Up.
    await asyncio.gather(parent.start(), child.start())
    return parent, child


class _FakeKiller:
    """A killer coroutine that records it was called.

    Stands in for the OS force-kill the Spawner would inject. The FSM
    only needs an awaitable; this one also lets a test confirm the kill
    path ran.
    """
    def __init__(self):
        """RETURN: a new _FakeKiller, not yet called."""
        self.called = False

    async def __call__(self):
        """RETURN: None.  Marks the killer as having been invoked."""
        self.called = True


# ----------------------------------------------------------------------
# Choices
# ----------------------------------------------------------------------

async def run_running():
    """RETURN: None.

    Drives the LAUNCHED -> RUNNING edge via notify_running() and checks
    that a second call is a no-op (idempotent).
    """
    parent, child = await _make_pair()
    rec = _Recorder()
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, rec)
    fsm = ChildStateMachine(parent_terminal=parent, killer=None)

    print("--- initial state ---")
    print("  state: %s" % fsm.state)
    assert fsm.state is E_ChildState.LAUNCHED

    print("--- notify_running() ---")
    await fsm.notify_running()
    print("  state: %s" % fsm.state)
    assert fsm.state is E_ChildState.RUNNING

    print("--- notify_running() again (idempotent) ---")
    await fsm.notify_running()
    print("  state: %s" % fsm.state)

    print("--- edges emitted ---")
    print("  %s" % " , ".join(rec.edges))
    assert rec.edges == ["LAUNCHED->RUNNING"]
    await parent.stop()


async def run_self_completion():
    """RETURN: None.

    Drives a child that ends on its OWN initiative. The child terminal
    emits EventChildTermination over the channel; the FSM's
    notify_self_completion observes it and drives RUNNING -> TERM_OK
    (DISCUSSION.txt D7).
    """
    parent, child = await _make_pair()
    rec = _Recorder()
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, rec)
    fsm = ChildStateMachine(parent_terminal=parent, killer=None)
    await fsm.notify_running()

    print("--- child confirms completion on its own ---")
    # The child emits the confirmation; the parent receives it. Route it
    # into the FSM exactly as the Spawner's _on_child_termination would.
    # The parent dispatcher enforces async callbacks, so the handler is
    # an async def (not a lambda).
    async def _on_confirmation(ev):
        await fsm.notify_self_completion(ev)
    parent.dispatcher.subscribe_on_event(
        EventChildTermination, _on_confirmation)
    await child.send(EventChildTermination(
        reason=E_TerminationReason.COMPLETED))
    await asyncio.sleep(0.05)               # let the event be delivered
    print("  state: %s" % fsm.state)
    assert fsm.state is E_ChildState.TERM_OK

    print("--- edges emitted ---")
    print("  %s" % " , ".join(rec.edges))
    assert rec.edges == ["LAUNCHED->RUNNING", "RUNNING->TERM_OK"]
    await parent.stop()


async def run_term_ok():
    """RETURN: None.

    begin_termination() with a child that confirms within the deadline:
    the FSM goes RUNNING -> TERMINATING -> TERM_OK and the killer is
    NOT needed (a confirmation preceded any kill).
    """
    parent, child = await _make_pair()
    rec = _Recorder()
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, rec)
    killer = _FakeKiller()
    fsm = ChildStateMachine(parent_terminal=parent, killer=killer)
    await fsm.notify_running()

    print("--- begin_termination(2000ms); child will confirm ---")
    term = asyncio.create_task(fsm.begin_termination(wait_to_kill_ms=2000))
    await asyncio.sleep(0.05)
    print("  state while terminating: %s" % fsm.state)
    assert fsm.state is E_ChildState.TERMINATING

    # Child confirms well within the deadline.
    await child.send(EventChildTermination(
        reason=E_TerminationReason.TERMINATED))
    await term
    print("  state after confirmation: %s" % fsm.state)
    assert fsm.state is E_ChildState.TERM_OK

    print("--- edges emitted ---")
    print("  %s" % " , ".join(rec.edges))
    assert rec.edges == ["LAUNCHED->RUNNING",
                         "RUNNING->TERMINATING",
                         "TERMINATING->TERM_OK"]
    await parent.stop()


async def run_term_failure():
    """RETURN: None.

    begin_termination() with a child that never confirms: the deadline
    elapses, the killer runs, and the FSM lands in TERM_FAILURE -
    resources freed without confirmation (DISCUSSION.txt D7).
    """
    parent, child = await _make_pair()
    rec = _Recorder()
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, rec)
    killer = _FakeKiller()
    fsm = ChildStateMachine(parent_terminal=parent, killer=killer)
    await fsm.notify_running()

    print("--- begin_termination(100ms); child stays silent ---")
    # No EventChildTermination is ever sent: the deadline must fire.
    await fsm.begin_termination(wait_to_kill_ms=100)
    print("  state after deadline: %s" % fsm.state)
    print("  killer was invoked  : %s" % killer.called)
    assert fsm.state is E_ChildState.TERM_FAILURE
    assert killer.called is True

    print("--- edges emitted ---")
    print("  %s" % " , ".join(rec.edges))
    assert rec.edges == ["LAUNCHED->RUNNING",
                         "RUNNING->TERMINATING",
                         "TERMINATING->TERM_FAILURE"]
    await parent.stop()


async def run_lost_connection():
    """RETURN: None.

    notify_channel_silent(): the verdict depends on the handle's
    liveness reading (DISCUSSION.txt D8 as clarified).

        handle DEAD     -> TERM_FAILURE  (child gone, unconfirmed)
        handle ALIVE    -> TERM_LOST_CONNECTION
        handle UNKNOWN  -> TERM_LOST_CONNECTION

    Each sub-case uses a fresh FSM in RUNNING.
    """
    async def verdict_for(liveness):
        parent, child = await _make_pair()
        fsm = ChildStateMachine(parent_terminal=parent, killer=None)
        await fsm.notify_running()
        await fsm.notify_channel_silent(liveness)
        await parent.stop()
        return fsm.state

    print("--- handle DEAD -> TERM_FAILURE ---")
    s = await verdict_for(E_Liveness.DEAD)
    print("  state: %s" % s)
    assert s is E_ChildState.TERM_FAILURE

    print("--- handle ALIVE -> TERM_LOST_CONNECTION ---")
    s = await verdict_for(E_Liveness.ALIVE)
    print("  state: %s" % s)
    assert s is E_ChildState.TERM_LOST_CONNECTION

    print("--- handle UNKNOWN -> TERM_LOST_CONNECTION ---")
    s = await verdict_for(E_Liveness.UNKNOWN)
    print("  state: %s" % s)
    assert s is E_ChildState.TERM_LOST_CONNECTION


async def run_suspend_resume():
    """RETURN: None.

    suspend_child() / resume_child() under the D9 refusal convention.
    With no OS handle injected the FSM cannot suspend and the calls
    return False; with a handle they return True and move the state
    RUNNING <-> SUSPENDED.
    """
    print("--- no OS handle: suspend/resume refuse (return False) ---")
    parent, child = await _make_pair()
    fsm = ChildStateMachine(parent_terminal=parent, killer=None)
    await fsm.notify_running()
    s_ok = await fsm.suspend_child()
    r_ok = await fsm.resume_child()
    print("  suspend_child(): %s   resume_child(): %s" % (s_ok, r_ok))
    print("  state unchanged: %s" % fsm.state)
    assert s_ok is False and r_ok is False
    assert fsm.state is E_ChildState.RUNNING
    await parent.stop()

    print("--- with OS handle: suspend/resume move RUNNING<->SUSPENDED ---")
    async def do_suspend(): return True
    async def do_resume():  return True
    parent, child = await _make_pair()
    rec = _Recorder()
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, rec)
    fsm = ChildStateMachine(parent_terminal=parent, killer=None,
                            suspend_resume=(do_suspend, do_resume))
    await fsm.notify_running()
    print("  suspend_child(): %s" % await fsm.suspend_child())
    print("  state: %s" % fsm.state)
    assert fsm.state is E_ChildState.SUSPENDED
    print("  resume_child():  %s" % await fsm.resume_child())
    print("  state: %s" % fsm.state)
    assert fsm.state is E_ChildState.RUNNING
    print("--- edges emitted ---")
    print("  %s" % " , ".join(rec.edges))
    assert rec.edges == ["LAUNCHED->RUNNING",
                         "RUNNING->SUSPENDED",
                         "SUSPENDED->RUNNING"]
    await parent.stop()


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Child-state machine",
        choice_map = {
            "running":         run_running,
            "self_completion": run_self_completion,
            "term_ok":         run_term_ok,
            "term_failure":    run_term_failure,
            "lost_connection": run_lost_connection,
            "suspend_resume":  run_suspend_resume,
        },
    ).run()
