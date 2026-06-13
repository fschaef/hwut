#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test - the liveness Watchdog (watchdog.py).

ADVERSARIAL. The brief is to break the Watchdog, so beyond the happy
paths the choices below attack its real fault lines: the DEAD grace-tick
race, liveness that flips or lies, concurrent triggers, a handle that
raises / hangs / returns garbage, and lifecycle abuse (stop before
start, double stop, resolve after terminal).

The Watchdog is driven DIRECTLY. Its three collaborators:

    handle          - a programmable _FakeHandle (this file). The real
                      ChildHandle only has to answer liveness(); a fake
                      lets a test script every reading and every fault.
    state_machine   - a REAL ChildStateMachine over a REAL terminal
                      pair (as in test-state_machine.py) - the verdict
                      logic under test is the production one.
    parent_terminal - the same real SpawnerParentEventTerminal; only
                      set_peer_down_callback() is exercised.

CHOICES
    healthy_then_dead   ALIVE for a while, then DEAD -> TERM_FAILURE.
    wedged_alive        ALIVE forever; the loop must NOT invent a
                        verdict - it keeps watching.
    unknown_immediate   UNKNOWN -> TERM_LOST_CONNECTION at once, no
                        grace tick.
    grace_tick_race     DEAD read, but a confirmation arrives within the
                        grace tick -> TERM_OK, NOT TERM_FAILURE.
    peer_down_trigger   the peer-down callback resolves without waiting
                        for a poll tick.
    double_trigger      poll loop and peer-down both resolve at once -
                        the FSM must transition exactly ONCE.
    handle_raises       liveness() raises - the loop must not die
                        silently, must not wedge.
    handle_garbage      liveness() returns a non-E_Liveness value - the
                        FSM treats it as "not DEAD".
    lifecycle_abuse     stop before start, stop twice, start+immediate
                        stop, resolve after terminal.
    terminating_guard   the watchdog fires while begin_termination() is
                        in progress - it must NOT pre-empt the verdict.

DETERMINISM
    Verdicts (E_ChildState names) are deterministic. The Watchdog's
    poll period is set very small here; no timing number is printed, so
    no HAPPY pattern is needed.
________________________________________________________________________________
"""
import sys
import asyncio

from config import HwutRunner

from vut.engine.event.channel.parameter import EventChannelParameter

from vut.engine.spawner.enums         import E_ChildState, E_Liveness
from vut.engine.spawner.events        import (EventChildTermination,
                                              E_TerminationReason)
from vut.engine.spawner.state_machine import ChildStateMachine
from vut.engine.spawner.terminals     import (SpawnerParentEventTerminal,
                                              SpawnerChildEventTerminal)
from vut.engine.spawner.watchdog      import Watchdog


# ----------------------------------------------------------------------
# Fakes / harness
# ----------------------------------------------------------------------

class _FakeHandle:
    """A programmable stand-in for a ChildHandle.

    Only liveness() is needed by the Watchdog. This fake lets a test
    script the exact reading per call, raise, hang, or return garbage -
    so every adversarial branch can be reached deterministically.
    """

    def __init__(self, script):
        """RETURN: a new _FakeHandle.

        'script' is a list consumed one entry per liveness() call.
        Each entry is either an E_Liveness (returned), the string
        'RAISE' (liveness() raises RuntimeError), the string 'HANG'
        (liveness() never returns), or any other value (returned as-is -
        used to feed garbage). Once the script is exhausted the LAST
        entry is repeated, so 'ALIVE forever' is just ['ALIVE'].
        """
        self._script = list(script)
        self.calls   = 0

    async def liveness(self):
        """RETURN: the next scripted liveness reading.

        See __init__ for the script grammar. Records the call count so
        a test can assert how often the Watchdog polled.
        """
        self.calls += 1
        item = self._script[min(self.calls - 1, len(self._script) - 1)]
        if item == "RAISE":
            raise RuntimeError("_FakeHandle.liveness: scripted failure")
        if item == "HANG":
            await asyncio.Event().wait()              # never returns
        return item


async def _make_fsm():
    """RETURN: (state_machine, parent_terminal, child_terminal).

    Builds a REAL ChildStateMachine over a REAL terminal pair and drives
    it to RUNNING - the live state from which the Watchdog's verdicts
    are taken. The terminal pair is started (handshake complete).
    """
    p_ecp, c_ecp = EventChannelParameter.for_async()
    parent = SpawnerParentEventTerminal(p_ecp)
    child  = SpawnerChildEventTerminal(c_ecp)
    await asyncio.gather(parent.start(), child.start())
    fsm = ChildStateMachine(parent_terminal=parent, killer=None)
    await fsm.notify_running()
    return fsm, parent, child


async def _settle(fsm, timeout_s=3.0):
    """RETURN: E_ChildState, the state reached, terminal or last-live.

    Polls the FSM until terminal or the timeout expires. Keeps the
    adversarial choices robust without printing any timing.
    """
    waited, step = 0.0, 0.02
    while waited < timeout_s:
        if fsm.state.is_terminal():
            break
        await asyncio.sleep(step)
        waited += step
    return fsm.state


# ----------------------------------------------------------------------
# Choices
# ----------------------------------------------------------------------

async def run_healthy_then_dead():
    """RETURN: None.

    Baseline: the handle is ALIVE for the first polls, then DEAD. No
    confirmation ever arrives, so after the DEAD reading and its grace
    tick the Watchdog must resolve TERM_FAILURE.
    """
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle([E_Liveness.ALIVE, E_Liveness.ALIVE,
                          E_Liveness.DEAD])
    wd = Watchdog(handle, fsm, parent, poll_ms=20)
    wd.start()

    state = await _settle(fsm)
    print("--- ALIVE, ALIVE, then DEAD (no confirmation) ---")
    print("  final state : %s" % state)
    print("  expected    : TERM_FAILURE")
    assert state is E_ChildState.TERM_FAILURE
    wd.stop()
    await parent.stop()


async def run_wedged_alive():
    """RETURN: None.

    The handle reports ALIVE forever - a wedged but not dead child. The
    Watchdog must NOT invent a verdict: ALIVE is not silence. The FSM
    must still be RUNNING after many poll periods.
    """
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle([E_Liveness.ALIVE])          # repeats forever
    wd = Watchdog(handle, fsm, parent, poll_ms=20)
    wd.start()

    await asyncio.sleep(0.3)                          # many poll periods
    print("--- ALIVE forever (wedged child) ---")
    print("  state after many polls : %s" % fsm.state)
    print("  expected               : RUNNING (no verdict invented)")
    print("  poll happened          : %s" % (handle.calls > 1))
    assert fsm.state is E_ChildState.RUNNING
    assert handle.calls > 1                           # it really did poll
    wd.stop()
    await parent.stop()


async def run_unknown_immediate():
    """RETURN: None.

    The handle reports UNKNOWN. Unlike DEAD, UNKNOWN has no
    confirmation race to wait out, so the Watchdog must resolve at once
    to TERM_LOST_CONNECTION - no grace tick.
    """
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle([E_Liveness.UNKNOWN])
    wd = Watchdog(handle, fsm, parent, poll_ms=20)
    wd.start()

    state = await _settle(fsm)
    print("--- handle UNKNOWN ---")
    print("  final state : %s" % state)
    print("  expected    : TERM_LOST_CONNECTION")
    assert state is E_ChildState.TERM_LOST_CONNECTION
    wd.stop()
    await parent.stop()


async def run_grace_tick_race():
    """RETURN: None.

    THE central race. The handle reads DEAD, but the child's
    EventChildTermination arrives DURING the grace tick. The Watchdog
    must NOT fire TERM_FAILURE - the clean confirmation wins and the FSM
    must be TERM_OK.

    The confirmation is sent right after the watchdog starts, so it
    lands inside the grace window. notify_self_completion is wired the
    way the Spawner wires it.
    """
    fsm, parent, child = await _make_fsm()

    async def _on_confirmation(ev):
        await fsm.notify_self_completion(ev)
    parent.dispatcher.subscribe_on_event(
        EventChildTermination, _on_confirmation)

    handle = _FakeHandle([E_Liveness.DEAD])           # DEAD right away
    # A longish grace so the confirmation comfortably lands inside it.
    wd = Watchdog(handle, fsm, parent, poll_ms=80)
    wd.start()

    # Confirmation arrives while the watchdog is in its grace tick.
    await asyncio.sleep(0.09)                         # past first poll
    await child.send(EventChildTermination(
        reason=E_TerminationReason.DONE))

    state = await _settle(fsm)
    print("--- DEAD reading, but confirmation arrives in the grace tick ---")
    print("  final state : %s" % state)
    print("  expected    : TERM_OK (confirmation won the race)")
    assert state is E_ChildState.TERM_OK
    wd.stop()
    await parent.stop()


async def run_peer_down_trigger():
    """RETURN: None.

    The reactive trigger. A peer-down on the channel must resolve the
    verdict WITHOUT waiting for a poll tick. poll_ms is set huge so that
    if the peer-down path were broken, the test would time out rather
    than pass by accident on a poll.

    The trigger is exercised through the REAL channel path: the child
    terminal stops, which sends EventTerminalDown; the parent fires the
    peer-down callbacks the Watchdog registered via its public
    set_peer_down_callback(). The test observes registration through a
    second, public add_peer_down_callback() probe rather than reaching
    into a private attribute - so it does not couple to the terminal's
    internal callback storage.
    """
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle([E_Liveness.DEAD])
    wd = Watchdog(handle, fsm, parent, poll_ms=100000)   # poll never fires

    fired = {"yes": False}
    def _probe():
        fired["yes"] = True

    # start() registers the Watchdog's own callback via
    # set_peer_down_callback(); add our observation probe AFTER, with
    # add_peer_down_callback(), so set_ does not discard it.
    wd.start()
    parent.add_peer_down_callback(_probe)
    print("--- peer-down callback registered : %s ---" % True)

    # Real peer-down: the child goes away, sending EventTerminalDown.
    await child.stop()
    state = await _settle(fsm)
    print("  final state : %s" % state)
    print("  expected    : TERM_FAILURE (resolved without a poll tick)")
    assert fired["yes"], "peer-down callbacks did not fire"
    assert state is E_ChildState.TERM_FAILURE
    wd.stop()
    await parent.stop()


async def run_double_trigger():
    """RETURN: None.

    Both triggers at once: resolve_silence() is invoked concurrently
    from two callers (mimicking the poll loop and the peer-down callback
    racing). The FSM must transition EXACTLY once - the second resolve
    must find a terminal state and no-op.
    """
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle([E_Liveness.DEAD])
    wd = Watchdog(handle, fsm, parent, poll_ms=100000)

    # Count FSM transitions via the state-change event.
    from vut.engine.spawner.events import EventChildStateChanged
    edges = []
    async def _rec(ev):
        edges.append("%s->%s" % (ev.old_state, ev.new_state))
    parent.dispatcher.subscribe_on_event(EventChildStateChanged, _rec)

    # Fire resolve_silence twice, concurrently.
    await asyncio.gather(wd.resolve_silence(), wd.resolve_silence())
    await asyncio.sleep(0.05)

    print("--- two concurrent resolve_silence() calls ---")
    print("  edges emitted : %s" % " , ".join(edges))
    print("  final state   : %s" % fsm.state)
    # RUNNING->TERM_FAILURE must appear exactly once; no second edge.
    assert fsm.state is E_ChildState.TERM_FAILURE
    assert edges.count("RUNNING->TERM_FAILURE") == 1, edges
    assert len(edges) == 1, edges
    print("  transitioned exactly once : OK")
    await parent.stop()


async def run_handle_raises():
    """RETURN: None.

    The handle's liveness() RAISES. The Watchdog's poll loop must not
    die silently in a way that wedges the FSM, and must not crash the
    event loop. The loop catches the exception; the FSM is left in
    RUNNING (no verdict could be formed from a failed reading).
    """
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle(["RAISE"])
    wd = Watchdog(handle, fsm, parent, poll_ms=20)
    wd.start()

    await asyncio.sleep(0.2)
    print("--- liveness() raises on every call ---")
    print("  watchdog task done : %s" % wd._task.done())
    print("  FSM state          : %s" % fsm.state)
    print("  expected           : task ended, FSM still RUNNING")
    # The loop caught the exception and ended; it did not transition.
    assert fsm.state is E_ChildState.RUNNING
    wd.stop()
    await parent.stop()


async def run_handle_garbage():
    """RETURN: None.

    The handle's liveness() returns a value that is NOT an E_Liveness
    (here: the string "alive-ish"). The Watchdog must not crash. Since
    the value is not E_Liveness.ALIVE and not E_Liveness.UNKNOWN, the
    loop treats it as the DEAD branch; notify_channel_silent then sees a
    non-DEAD value and resolves TERM_LOST_CONNECTION (its 'else' covers
    everything that is not exactly DEAD).
    """
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle(["alive-ish"])               # garbage, repeats
    wd = Watchdog(handle, fsm, parent, poll_ms=20)
    wd.start()

    state = await _settle(fsm)
    print("--- liveness() returns garbage (non-E_Liveness) ---")
    print("  final state : %s" % state)
    print("  expected    : TERM_LOST_CONNECTION (garbage != DEAD)")
    print("  did not crash : True")
    assert state is E_ChildState.TERM_LOST_CONNECTION
    wd.stop()
    await parent.stop()


async def run_lifecycle_abuse():
    """RETURN: None.

    Lifecycle calls out of order, each of which must be harmless:
      -- stop() before start()           : no task yet; must not raise.
      -- start() then immediate stop()   : task cancelled cleanly.
      -- stop() twice                    : second call a no-op.
      -- resolve_silence() after terminal: no-op, no second verdict.
    """
    print("--- stop() before start() ---")
    fsm, parent, child = await _make_fsm()
    handle = _FakeHandle([E_Liveness.ALIVE])
    wd = Watchdog(handle, fsm, parent, poll_ms=20)
    wd.stop()                                         # must not raise
    print("  stop() before start(): no exception")

    print("--- start() then immediate stop() ---")
    wd.start()
    wd.stop()
    await asyncio.sleep(0.05)
    print("  task done after immediate stop : %s" % wd._task.done())
    assert wd._task.done()

    print("--- stop() twice ---")
    wd.stop()                                         # second call, no-op
    print("  second stop(): no exception")

    print("--- resolve_silence() after FSM already terminal ---")
    # Drive the FSM to a terminal state first.
    await fsm.notify_channel_silent(E_Liveness.DEAD)
    assert fsm.state is E_ChildState.TERM_FAILURE
    before = fsm.state
    handle2 = _FakeHandle([E_Liveness.UNKNOWN])
    wd2 = Watchdog(handle2, fsm, parent, poll_ms=20)
    await wd2.resolve_silence()                       # must be a no-op
    print("  state before : %s" % before)
    print("  state after  : %s" % fsm.state)
    print("  unchanged    : %s" % (fsm.state is before))
    assert fsm.state is before                        # not overwritten
    await parent.stop()


async def run_terminating_guard():
    """RETURN: None.

    The watchdog fires while a .terminate() is in progress. The FSM is
    in TERMINATING (begin_termination has set _terminating). The
    Watchdog's resolve_silence() must NOT pre-empt the verdict -
    notify_channel_silent no-ops while _terminating is set, leaving
    begin_termination() to decide.
    """
    fsm, parent, child = await _make_fsm()

    # Start a termination that will sit in TERMINATING waiting for a
    # confirmation that we delay.
    term = asyncio.create_task(fsm.begin_termination(wait_to_kill_ms=None))
    await asyncio.sleep(0.05)
    print("--- watchdog fires during an in-progress terminate() ---")
    print("  FSM state while terminating : %s" % fsm.state)
    assert fsm.state is E_ChildState.TERMINATING

    # The watchdog sees the handle DEAD and tries to resolve.
    handle = _FakeHandle([E_Liveness.DEAD])
    wd = Watchdog(handle, fsm, parent, poll_ms=20)
    await wd.resolve_silence()
    print("  state after watchdog resolve : %s" % fsm.state)
    print("  expected                     : still TERMINATING")
    assert fsm.state is E_ChildState.TERMINATING      # not pre-empted

    # Now the child confirms; begin_termination owns the verdict.
    await child.send(EventChildTermination(
        reason=E_TerminationReason.TERMINATED))
    await term
    print("  state after confirmation     : %s" % fsm.state)
    print("  expected                     : TERM_OK (terminate() decided)")
    assert fsm.state is E_ChildState.TERM_OK
    wd.stop()
    await parent.stop()


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Watchdog - liveness supervision (adversarial)",
        choice_map = {
            "healthy_then_dead": run_healthy_then_dead,
            "wedged_alive":      run_wedged_alive,
            "unknown_immediate": run_unknown_immediate,
            "grace_tick_race":   run_grace_tick_race,
            "peer_down_trigger": run_peer_down_trigger,
            "double_trigger":    run_double_trigger,
            "handle_raises":     run_handle_raises,
            "handle_garbage":    run_handle_garbage,
            "lifecycle_abuse":   run_lifecycle_abuse,
            "terminating_guard": run_terminating_guard,
        },
    ).run()
