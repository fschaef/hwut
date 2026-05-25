"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: ChildStateMachine - the Spawner's model of one child's lifecycle.

The state set and transitions are in README.txt ("CHILD STATE MACHINE")
and DISCUSSION.txt D6/D7/D8. This module IMPLEMENTS them.

IMPLEMENTATION SHAPE (DISCUSSION.txt D6)

The machine is NOT a hand-rolled step variable plus timer. It is an
asyncio coroutine whose straight-line structure IS the state sequence:
each `await` is a suspension point, and the program counter sitting on
that await IS the current state. The awaits are the dispatcher's
expect_* helpers - one-shot awaitables that resume when a matching event
is dispatched.

So the shutdown sequence reads top-to-bottom as ordinary code:

    emit request
    await (confirmation  OR  deadline)        <- TERMINATING lives here
    if confirmation: -> TERM_OK
    else:            kill; -> TERM_FAILURE

THE DECISIVE DISTINCTION (DISCUSSION.txt D7)

TERM_OK vs TERM_FAILURE is about ORDERING, not "clean vs killed":

    TERM_OK       EventChildTermination arrived BEFORE resources were
                  freed - the child confirmed, then we reclaimed.
    TERM_FAILURE  resources were freed BEFORE or WITHOUT confirmation -
                  the functional outcome is unknown.

A kill after a TERM_OK confirmation is fine: the confirmation already
happened; the kill is pure OS reclamation.

TERM_LOST_CONNECTION (DISCUSSION.txt D8) is reachable from ANY live
state: if the channel breaks, the Spawner has NO information and cannot
even account for resources. It is distinct from TERM_FAILURE, which
still had a working channel and a definite verdict.

EVERY EDGE EMITS EventChildStateChanged(old, new) (D6), so a parent may
poll .state or await the transition.

WHO DRIVES WHAT

  -- The Up handshake completing drives LAUNCHED -> RUNNING. The Spawner
     calls notify_running() once the parent terminal's start() returns.
  -- A parent .terminate() emits EventChildTerminationReq; the Spawner
     hands it to begin_termination(), which runs the kind-specific
     shutdown coroutine.
  -- A broken channel (peer-down with no deliberate Down, or a receive
     error) drives -> TERM_LOST_CONNECTION via notify_connection_lost().

The kind-specific shutdown differences (process/remote hard kill,
thread no-kill, async cooperative cancel) are in README.txt
"TERMINATION"; this module branches on the injected 'killer'.
________________________________________________________________________________
"""
import asyncio
import sys
import time

from vut.engine.spawner.enums  import ChildState
from vut.engine.spawner.events import (EventChildTermination,
                                       EventChildKilled,
                                       EventChildStateChanged,
                                       E_TerminationReason)


class ChildStateMachine:
    """Runs the child-state machine for ONE Spawner-launched child.

    Owns the current ChildState and the transition logic. It does NOT
    own the OS handle or the channel - the handle lives in the Spawner
    behind an injected 'killer' coroutine; the channel is the parent
    terminal's. The machine only OBSERVES (via events) and DECIDES (the
    next state), then asks the Spawner to act.

    Construction wires the machine to:
      -- parent_terminal -- the SpawnerParentEventTerminal; source of
                            expect_* awaitables and the terminal whose
                            receive dispatcher the FSM dispatches
                            EventChildKilled / EventChildStateChanged
                            onto (locally - they are spawner -> parent
                            events for the user, not channel traffic).
      -- killer           -- async callable; performs the OS-level
                            force-kill for this child's kind. For a
                            'thread' kind it is None (no force path).
      -- suspend_resume   -- (suspend, resume) async callables, or
                            (None, None) for kinds without an OS handle.

    The machine starts in LAUNCHED. Its terminal states are the three
    ChildState.TERM_* members; once reached, no further transition
    occurs.
    """

    def __init__(self, parent_terminal, killer, suspend_resume=(None, None)):
        """RETURN: a new ChildStateMachine in state LAUNCHED.

        parent_terminal -- the SpawnerParentEventTerminal; source of
                            expect_* awaitables and sink for emitted
                            FSM events.
        killer          -- async callable performing the OS force-kill,
                            or None for a kind with no force path.
        suspend_resume  -- (suspend, resume) async callables, or
                            (None, None) when the kind has no OS handle.
        """
        self._parent      = parent_terminal
        self._killer      = killer
        self._suspend     = suspend_resume[0]
        self._resume      = suspend_resume[1]
        self._state       = ChildState.LAUNCHED
        self._terminating = False     # guards against re-entrant shutdown
        self._on_terminal = None      # optional callback, set by set_on_terminal()

    def set_on_terminal(self, callback) -> None:
        """RETURN: None.

        Registers a callback invoked once, when the FSM first enters a
        terminal state. The Spawner uses it to stop the watchdog - there
        is nothing left to supervise once a verdict exists. The callback
        takes no arguments and may be sync or async.
        """
        self._on_terminal = callback

    # ----------------------------------------------------------------
    # State access
    # ----------------------------------------------------------------

    @property
    def state(self) -> ChildState:
        """RETURN: ChildState, the current state. Snapshot read, non-blocking."""
        return self._state

    async def _transition(self, new_state: ChildState) -> None:
        """RETURN: None.

        Performs one FSM edge: records new_state and dispatches
        EventChildStateChanged(old, new) on the parent terminal's own
        receive dispatcher, so the parent may poll .child_state() or
        await the change via expect_event. The event is dispatched
        LOCALLY, never sent over the channel - it is a spawner -> parent
        notification, and the channel may already be closed at the
        final edge.

        A transition INTO an already-current state, or any transition
        out of an already-terminal state, is dropped (logged) - the
        terminal states are final, and a no-op edge should not emit a
        spurious event.
        """
        old = self._state
        if old.is_terminal():
            print("ChildStateMachine._transition: ignoring %s -> %s; "
                  "%s is terminal." % (old, new_state, old), file=sys.stderr)
            return
        if old is new_state:
            return
        self._state = new_state
        # EventChildStateChanged is a spawner -> parent event the USER
        # reads. It is dispatched LOCALLY on the parent terminal's own
        # receive dispatcher (where expect_* / subscribe_on_event look),
        # NOT sent over the channel: the child is not its audience, and
        # the channel may already be closed at the final edge.
        self._parent.dispatcher.dispatch(EventChildStateChanged(
            old_state=old, new_state=new_state))

        # On entering a terminal state, fire the one-shot terminal
        # callback (the Spawner stops the watchdog here). Errors in the
        # callback are logged, never propagated into the FSM.
        if new_state.is_terminal() and self._on_terminal is not None:
            cb, self._on_terminal = self._on_terminal, None
            try:
                result = cb()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print("ChildStateMachine._transition: on_terminal callback "
                      "raised: %s" % e, file=sys.stderr)

    # ----------------------------------------------------------------
    # Externally-driven transitions
    # ----------------------------------------------------------------

    async def notify_running(self) -> None:
        """RETURN: None.

        Drives LAUNCHED -> RUNNING. Called by the Spawner once the Up
        handshake has completed (the parent terminal's start() has
        returned), which - thanks to the trampoline - proves the
        channel is live, not merely that a process exists
        (DISCUSSION.txt D5).

        A no-op if the machine has already left LAUNCHED.
        """
        if self._state is ChildState.LAUNCHED:
            await self._transition(ChildState.RUNNING)

    async def notify_self_completion(self,
                                     event: EventChildTermination) -> None:
        """RETURN: None.

        Drives RUNNING (or SUSPENDED) -> TERM_OK when the child reports
        its own termination WITHOUT a prior .terminate() request - the
        child finished its own work and confirmed (E_TerminationReason
        COMPLETED, or FAILED reported out cleanly). The child confirmed
        before its resources were freed, so TERM_OK is the correct
        verdict (DISCUSSION.txt D7).

        This is the always-on counterpart to begin_termination()'s
        one-shot expect_event: the Spawner subscribes it to
        EventChildTermination for the child's whole life, so a child
        that ends on its own is not stranded in RUNNING.

        It acts in LAUNCHED, RUNNING and SUSPENDED:

          -- RUNNING / SUSPENDED -- the normal case; -> TERM_OK.
          -- LAUNCHED -- an instant-completing child can confirm before
             the Spawner's own bookkeeping has driven LAUNCHED ->
             RUNNING. That is a race, not an anomaly: the child DID
             confirm. The edge LAUNCHED -> TERM_OK is taken directly;
             the skipped RUNNING is bookkeeping the child outran.

        It is INERT otherwise:

          -- TERMINATING -- a .terminate() is in progress; the one-shot
             expect_event inside begin_termination() owns the
             confirmation and the resulting verdict. This handler
             standing down here is what prevents the two watchers from
             racing for the same transition.
          -- terminal    -- nothing left to transition.
        """
        if self._state in (ChildState.LAUNCHED,
                            ChildState.RUNNING,
                            ChildState.SUSPENDED):
            await self._transition(ChildState.TERM_OK)
        elif self._state is ChildState.TERMINATING:
            # begin_termination()'s expect_event handles this one.
            return
        else:
            print("ChildStateMachine.notify_self_completion: child "
                  "confirmation arrived in terminal state %s; ignored."
                  % self._state, file=sys.stderr)

    async def notify_channel_silent(self, liveness) -> None:
        """RETURN: None.

        Resolves a SILENT channel into a terminal verdict, using the
        child handle's liveness reading. Called by the Spawner's
        watchdog when the channel has gone quiet (a peer-down, or a
        watchdog poll that found no traffic), with 'liveness' the result
        of handle.is_alive() (an E_Liveness).

        The channel going quiet is NOT itself a verdict (DISCUSSION.txt
        D8 as clarified): the spawner must first ask whether it still
        has information about the child.

          liveness DEAD     the child's OS context is gone. If the FSM
                            is still live here, no EventChildTermination
                            was processed before the death (a
                            confirmation would have driven the FSM to
                            TERM_OK already, and this method no-ops on a
                            terminal state). Resources were freed
                            without confirmation -> TERM_FAILURE
                            (DISCUSSION.txt D7).

          liveness ALIVE    the process is there but unreachable - the
                            spawner cannot account for what it is doing.
          liveness UNKNOWN  the handle could not be consulted at all.

          ALIVE and UNKNOWN alike mean "no usable information about the
          child" -> TERM_LOST_CONNECTION (DISCUSSION.txt D8).

        A no-op once the FSM is already terminal: a clean TERM_OK is not
        disturbed by the channel close that normally follows it, and a
        verdict already reached is not overwritten. Also a no-op while a
        .terminate() is in progress (_terminating set): there, the
        channel going quiet is expected fallout of the deliberate
        shutdown and begin_termination() owns the verdict.
        """
        from vut.engine.spawner.handles import E_Liveness

        if self._state.is_terminal():
            return
        if self._terminating:
            # Deliberate shutdown underway; begin_termination() decides.
            return

        if liveness is E_Liveness.DEAD:
            # Child gone, no confirmation seen -> freed without
            # confirmation -> TERM_FAILURE.
            await self._transition(ChildState.TERM_FAILURE)
        else:
            # ALIVE or UNKNOWN: no information about the child.
            await self._transition(ChildState.TERM_LOST_CONNECTION)

    async def suspend_child(self) -> bool:
        """RETURN: True,  the child was suspended; state is now SUSPENDED.
                   False, the child could not be suspended.

        Refused (False) when the kind has no OS handle (no suspend
        callable was injected) or when the child is not in RUNNING -
        only a RUNNING child is suspendable. Refusal is by return value,
        never exception (DISCUSSION.txt D9).
        """
        if self._suspend is None:
            return False
        if self._state is not ChildState.RUNNING:
            print("ChildStateMachine.suspend_child: child is %s, not "
                  "RUNNING; cannot suspend." % self._state, file=sys.stderr)
            return False
        ok = await self._suspend()
        if ok:
            await self._transition(ChildState.SUSPENDED)
        return ok

    async def resume_child(self) -> bool:
        """RETURN: True,  the child was resumed; state is now RUNNING.
                   False, the child could not be resumed.

        Refused (False) when the kind has no OS handle or when the child
        is not in SUSPENDED - only a SUSPENDED child is resumable.
        Refusal is by return value, never exception (DISCUSSION.txt D9).
        """
        if self._resume is None:
            return False
        if self._state is not ChildState.SUSPENDED:
            print("ChildStateMachine.resume_child: child is %s, not "
                  "SUSPENDED; cannot resume." % self._state, file=sys.stderr)
            return False
        ok = await self._resume()
        if ok:
            await self._transition(ChildState.RUNNING)
        return ok

    # ----------------------------------------------------------------
    # The shutdown sequence
    # ----------------------------------------------------------------

    async def begin_termination(self, wait_to_kill_ms: "int | None") -> None:
        """RETURN: None, when the machine has reached a terminal state.

        Entry point for the shutdown sequence. Called by the Spawner
        when an EventChildTerminationReq arrives from the parent.

        Drives the live state -> TERMINATING and then awaits the
        outcome. The await is the TERMINATING state itself
        (DISCUSSION.txt D6): a single expect_* race between

            EventChildTermination   -- the child confirmed  -> TERM_OK
            the wait_to_kill_ms deadline elapsing            -> kill path

        wait_to_kill_ms:
            int   milliseconds to wait for confirmation before killing.
            None  wait forever - no deadline branch is armed.

        On a deadline kill the machine emits EventChildKilled and lands
        in TERM_FAILURE - resources freed without (or before)
        confirmation (DISCUSSION.txt D7). If confirmation arrives after
        the kill was issued the kill still stands; the OS context is
        gone either way, and the verdict is fixed by what came first.

        Re-entrant calls (a second EventChildTerminationReq while
        already TERMINATING) are dropped: the sequence is already
        running.
        """
        if self._terminating or self._state.is_terminal():
            print("ChildStateMachine.begin_termination: already "
                  "terminating or terminal (%s); request ignored."
                  % self._state, file=sys.stderr)
            return
        self._terminating = True

        await self._transition(ChildState.TERMINATING)

        # The await below IS the TERMINATING state. expect_event gives a
        # one-shot awaitable resolved by the next EventChildTermination.
        confirmation = self._parent.dispatcher.expect_event(
            EventChildTermination)

        if wait_to_kill_ms is None:
            # No deadline: wait for confirmation for as long as it takes.
            event = await confirmation
            await self._confirmed(event)
            return

        # Numeric deadline: race confirmation against the timeout.
        try:
            event = await asyncio.wait_for(
                confirmation, timeout=wait_to_kill_ms / 1000.0)
        except asyncio.TimeoutError:
            # Deadline reached with no confirmation -> kill -> TERM_FAILURE.
            await self._kill_and_fail(wait_to_kill_ms)
            return

        await self._confirmed(event)

    async def _confirmed(self, event: EventChildTermination) -> None:
        """RETURN: None.

        Confirmation path of begin_termination(): the child sent
        EventChildTermination before its resources were forcibly freed,
        so the machine lands in TERM_OK (DISCUSSION.txt D7).

        If the child kind has an OS handle (killer is not None) the OS
        context is then reclaimed - a kill AFTER a confirmation is pure
        reclamation and emits EventChildKilled for the record; it does
        NOT change the TERM_OK verdict, because confirmation came first.
        """
        await self._transition(ChildState.TERM_OK)
        # Reclaim the OS context if there is one. The child confirmed;
        # this kill is bookkeeping, not the verdict.
        if self._killer is not None:
            try:
                await self._killer()
                self._parent.dispatcher.dispatch(EventChildKilled(
                    last_state = ChildState.TERM_OK,
                    killed_at  = time.time(),
                    grace_ms   = 0,
                ))
            except Exception as e:
                print("ChildStateMachine._confirmed: post-confirmation "
                      "reclamation raised: %s" % e, file=sys.stderr)

    async def _kill_and_fail(self, grace_ms: int) -> None:
        """RETURN: None.

        Deadline path of begin_termination(): no confirmation arrived
        within grace_ms. The OS context is force-killed (if the kind has
        a killer) and the machine lands in TERM_FAILURE - resources
        freed without confirmation, functional outcome unknown
        (DISCUSSION.txt D7).

        Emits EventChildKilled recording last_state, the kill time, and
        the grace period that elapsed. A kind with no killer (a thread)
        never reaches this path, because .terminate() refuses a numeric
        deadline for it up front (DISCUSSION.txt D9).
        """
        last_state = self._state
        if self._killer is not None:
            try:
                await self._killer()
            except Exception as e:
                print("ChildStateMachine._kill_and_fail: killer raised: %s"
                      % e, file=sys.stderr)
        else:
            # Defensive: a kind with no force path should never have a
            # numeric deadline (terminate() refuses it). If we are here,
            # the refusal convention was bypassed somewhere upstream.
            print("ChildStateMachine._kill_and_fail: no killer for this "
                  "kind, yet a numeric deadline elapsed; the .terminate() "
                  "refusal was bypassed.", file=sys.stderr)

        self._parent.dispatcher.dispatch(EventChildKilled(
            last_state = last_state,
            killed_at  = time.time(),
            grace_ms   = grace_ms,
        ))
        await self._transition(ChildState.TERM_FAILURE)
