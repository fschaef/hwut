"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: The two Spawner-side EventTerminal subclasses.

    SpawnerParentEventTerminal   what the user gets back from a spawn_*
                                 call: a real EventTerminal plus the
                                 supervision surface.
    SpawnerChildEventTerminal    what the trampoline builds on the child
                                 side and hands to the user callable.

WHY SUBCLASSES, NOT A NEW TYPE (DISCUSSION.txt D1/D2)

An early sketch grafted kill-machinery onto a Terminal. Rejected: a
Terminal is ONE peer of ONE channel; supervision is a hub concern that
belongs to the Spawner (a Router). So the parent terminal stays a plain
EventTerminal in every inherited respect - send / dispatcher / start /
stop are untouched - and the subclass adds only a thin SUPERVISION
SURFACE:

    .terminate(wait_to_kill_ms)  -> bool
    .suspend()                   -> bool
    .resume()                    -> bool
    .child_state()               -> E_ChildState

.terminate() IS A REQUEST, NOT AN ACTION (DISCUSSION.txt D3)

.terminate() does not kill anything itself. It emits
EventChildTerminationReq through the Spawner's router; the Spawner acts.
The terminal stays a terminal. Designing the hand-off as an event - even
though the Spawner is co-located today - is what lets a future Spawner
move off the parent's context without rewriting this contract.

THE REFUSAL CONVENTION (DISCUSSION.txt D9)

All three supervision methods report success or refusal by RETURN VALUE
(bool), never by exception. A refusal is a NORMAL outcome: .terminate()
returns False for a numeric deadline on a 'thread'; .suspend()/.resume()
return False on async or thread. An unsupported request is ordinary, not
exceptional - raising would force every call site into try/except for a
foreseeable case.

THE OS HANDLE IS NEVER SURFACED (DISCUSSION.txt D2)

The user never sees a PID, a Task, or a socket. The handle lives inside
the Spawner, behind the force-kill path. This subclass holds only a
reference to its Spawner and reads child state from the FSM the Spawner
runs.
________________________________________________________________________________
"""
import sys

from vut.engine.event.channel.parameter import EventChannelParameter
from vut.engine.event.terminal          import EventTerminal

from vut.engine.spawner.enums  import E_ChildState
from vut.engine.spawner.events import (EventChildTerminationReq,
                                       EventChildTermination,
                                       E_TerminationReason)


# ============================================================================
# Parent side
# ============================================================================

class SpawnerParentEventTerminal(EventTerminal):
    """A user-facing EventTerminal with a child-supervision surface.

    Returned by every successful spawn_* call. Inherits the full
    EventTerminal contract (send, dispatcher, start, stop, the async
    context-manager form) unchanged, and adds .terminate, .suspend,
    .resume, .child_state.

    The supervision methods are thin: .terminate() emits a request
    event; .suspend()/.resume() ask the Spawner to act on the OS
    handle; .child_state() reads the FSM. None of them owns process
    machinery - that is the Spawner's.

    A SpawnerParentEventTerminal is bound to its Spawner at construction
    via attach_supervision(). Until that call the supervision surface
    has nothing to talk to; the Spawner makes the call as the last step
    of a spawn, before handing the terminal to the user. A user never
    observes the unattached window.
    """

    def __init__(self, ecp: EventChannelParameter):
        """RETURN: a new (not yet started, not yet supervised) terminal.

        Channel setup is inherited from EventTerminal. The supervision
        surface is dormant until attach_supervision() binds a Spawner
        and its child-state machine.
        """
        super().__init__(ecp)
        self._spawner       = None      # set by attach_supervision()
        self._state_machine = None      # set by attach_supervision()

    # ----------------------------------------------------------------
    # Binding (called by the Spawner, not by the user)
    # ----------------------------------------------------------------

    def attach_supervision(self, spawner, state_machine) -> None:
        """RETURN: None.

        Binds this terminal to the Spawner that launched it and to the
        child-state machine that Spawner runs. Called once, by the
        Spawner, as the final step of a spawn - before the terminal is
        handed to the user.

        Not part of the user-facing API: the user receives an
        already-attached terminal and never calls this.
        """
        self._spawner       = spawner
        self._state_machine = state_machine

    # ----------------------------------------------------------------
    # Supervision surface
    # ----------------------------------------------------------------

    async def terminate(self, wait_to_kill_ms: "int | None") -> bool:
        """RETURN: True,  the termination request was accepted and emitted;
                          the child-state machine will drive shutdown.
                   False, the request was refused and nothing was emitted.

        Refused (False) when:
          -- wait_to_kill_ms is numeric but the child kind has no
             force-kill path (a 'thread'; see DISCUSSION.txt D9). For a
             thread, only wait_to_kill_ms=None is honourable.
          -- the terminal is not attached to a Spawner, or the child is
             already in a terminal state (nothing left to terminate).

        Does NOT raise on refusal: an unsupported request is a normal,
        expected outcome (D9), so the caller branches on the bool rather
        than guarding with try/except.

        wait_to_kill_ms is the grace period before a force-kill:
        a number of milliseconds, or None to wait forever. It is
        MANDATORY - infinite wait must be the deliberate value None,
        never a forgotten argument.

        On acceptance this method only EMITS EventChildTerminationReq
        toward the Spawner (DISCUSSION.txt D3); the Spawner performs the
        actual shutdown sequence. Returning True means "the request is
        on its way", not "the child has stopped".
        """
        if self._spawner is None or self._state_machine is None:
            print("SpawnerParentEventTerminal.terminate: terminal is not "
                  "attached to a Spawner; cannot terminate.", file=sys.stderr)
            return False

        if self._state_machine.state.is_terminal():
            print("SpawnerParentEventTerminal.terminate: child already in "
                  "terminal state %s; nothing to terminate."
                  % self._state_machine.state, file=sys.stderr)
            return False

        # The kill asymmetry (D9): a numeric deadline is meaningless for
        # a kind with no force-kill path. Refuse rather than silently
        # treating the number as None.
        if wait_to_kill_ms is not None \
           and not self._spawner.config.supports_force_kill:
            print("SpawnerParentEventTerminal.terminate: numeric "
                  "wait_to_kill_ms=%s rejected for kind %r - it cannot be "
                  "force-killed; pass None to wait forever."
                  % (wait_to_kill_ms, self._spawner.config.kind_name),
                  file=sys.stderr)
            return False

        # Thin request: emit the event, let the Spawner act.
        return await self.send(EventChildTerminationReq(
            wait_to_kill_ms=wait_to_kill_ms))

    async def suspend(self) -> bool:
        """RETURN: True,  the child was suspended via its OS handle.
                   False, suspend is unsupported for this child's kind,
                          or the child is not in a suspendable state.

        Supported only for 'process' and 'remote' children, which have
        an OS handle. For 'async' and 'thread' this returns False
        (DISCUSSION.txt D9) - by return value, never by exception.

        A child is suspendable only from RUNNING; calling suspend() in
        any other state returns False.
        """
        if self._spawner is None:
            print("SpawnerParentEventTerminal.suspend: terminal is not "
                  "attached to a Spawner.", file=sys.stderr)
            return False
        if not self._spawner.config.supports_suspend:
            print("SpawnerParentEventTerminal.suspend: unsupported for "
                  "kind %r." % self._spawner.config.kind_name,
                  file=sys.stderr)
            return False
        return await self._spawner.suspend_child()

    async def resume(self) -> bool:
        """RETURN: True,  the child was resumed via its OS handle.
                   False, resume is unsupported for this child's kind,
                          or the child is not currently SUSPENDED.

        The exact counterpart of suspend(): supported only for 'process'
        and 'remote', refusal reported by return value (DISCUSSION.txt
        D9). A child is resumable only from SUSPENDED.
        """
        if self._spawner is None:
            print("SpawnerParentEventTerminal.resume: terminal is not "
                  "attached to a Spawner.", file=sys.stderr)
            return False
        if not self._spawner.config.supports_suspend:
            print("SpawnerParentEventTerminal.resume: unsupported for "
                  "kind %r." % self._spawner.config.kind_name,
                  file=sys.stderr)
            return False
        return await self._spawner.resume_child()

    def child_state(self) -> E_ChildState:
        """RETURN: E_ChildState, the child-state machine's current state.

        A snapshot read, never blocking. To AWAIT a transition instead
        of polling, subscribe to EventChildStateChanged on .dispatcher
        or use dispatcher.expect_event(EventChildStateChanged).

        If the terminal is not attached to a Spawner this returns
        E_ChildState.LAUNCHED - the pre-supervision default - rather than
        raising; an unattached terminal is an internal transient the
        user never sees.
        """
        if self._state_machine is None:
            return E_ChildState.LAUNCHED
        return self._state_machine.state


# ============================================================================
# Child side
# ============================================================================

class SpawnerChildEventTerminal(EventTerminal):
    """The child-side EventTerminal, built by the trampoline.

    Lives on the 'other' side of the user's context - inside the
    asyncio Task, worker thread, child process, or remote process. The
    trampoline constructs it from the child ECP and hands it to the
    user callable as the callable's first argument (named
    'event_terminal' when args are a dict).

    It is a plain EventTerminal in every send/receive respect, with one
    addition: on start() it subscribes to EventChildTerminationReq, so
    that a parent-side .terminate() drives a cooperative wind-down here;
    and on stop() it emits EventChildTermination, the child's voluntary
    exit report.

    INTENDED USE - via the trampoline's context manager:

        async with SpawnerChildEventTerminal(ecp) as term:
            await callable_thing(term, *args)

    __aenter__ runs start() (Up handshake + subscribe); __aexit__ runs
    stop() (emit EventChildTermination + close). The reason carried by
    that exit event is set by report_reason() - the trampoline sets it
    from the callable's outcome before the context manager exits.
    """

    def __init__(self, ecp: EventChannelParameter):
        """RETURN: a new (not yet started) child terminal.

        The exit reason defaults to COMPLETED; the trampoline overrides
        it via report_reason() if the callable was terminated on
        request or raised.
        """
        super().__init__(ecp)
        self._exit_reason          = E_TerminationReason.COMPLETED
        self._termination_callback = None      # optional; set by user code

    # ----------------------------------------------------------------
    # Lifecycle additions over EventTerminal
    # ----------------------------------------------------------------

    async def start(self) -> None:
        """RETURN: None, after the Up handshake has completed.

        Extends EventTerminal.start(): once the handshake is done, the
        child terminal additionally subscribes to
        EventChildTerminationReq on its receive dispatcher, so a
        parent-side .terminate() reaches the cooperative-wind-down
        handler here.

        Idempotent in the same way EventTerminal.start() is.
        """
        await super().start()
        # Subscribe AFTER the handshake: before UP the dispatcher would
        # accept the subscription but no application events flow yet.
        self.dispatcher.subscribe_on_event(
            EventChildTerminationReq,
            self._on_termination_req,
        )

    async def stop(self) -> None:
        """RETURN: None.

        Extends EventTerminal.stop(): emits EventChildTermination
        (carrying the current exit reason) on the wire BEFORE the
        inherited stop() sends EventTerminalDown and closes the channel.

        The ordering matters: EventChildTermination is the child's
        CONFIRMATION; it must reach the parent before the channel goes
        away, or the Spawner's TERMINATING state will time out into
        TERM_FAILURE despite a clean exit (DISCUSSION.txt D7).

        Idempotent: a second call neither re-emits nor re-closes.
        """
        if self.state == "DOWN":
            return
        # Best-effort confirmation while the channel is still up.
        if self.is_up:
            sent = await self.send(EventChildTermination(
                reason=self._exit_reason))
            if not sent:
                print("SpawnerChildEventTerminal.stop: could not emit "
                      "EventChildTermination (terminal not UP).",
                      file=sys.stderr)
        await super().stop()

    # ----------------------------------------------------------------
    # Exit-reason plumbing (used by the trampoline)
    # ----------------------------------------------------------------

    def report_reason(self, reason: E_TerminationReason) -> None:
        """RETURN: None.

        Sets the reason that the EventChildTermination emitted by stop()
        will carry. The trampoline calls this from the callable's
        outcome:
            normal return            -> COMPLETED (the default)
            EventChildTerminationReq -> TERMINATED
            callable raised          -> FAILED

        Calling it after stop() has run has no effect; the event is
        already on the wire.
        """
        self._exit_reason = reason

    def set_termination_callback(self, callback) -> None:
        """RETURN: None.

        Register a callback the child terminal invokes when an
        EventChildTerminationReq arrives - i.e. when the parent asked
        for termination. The callback receives the
        EventChildTerminationReq and may be sync or async.

        This is how a long-running user callable learns it should wind
        down cooperatively. A callable that ignores it will simply run
        until the Spawner's force-kill path (if any) reaches it.
        """
        self._termination_callback = callback

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    async def _on_termination_req(self, event: EventChildTerminationReq) -> None:
        """RETURN: None.

        Receive-side handler for EventChildTerminationReq. Records that
        the eventual exit reason is TERMINATED (not COMPLETED) and, if
        the user registered a termination callback, invokes it so the
        callable can begin a cooperative wind-down.

        Per-callback exceptions are caught and logged; they do not
        propagate into the receive loop.
        """
        self._exit_reason = E_TerminationReason.TERMINATED
        if self._termination_callback is None:
            return
        try:
            import asyncio
            result = self._termination_callback(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            print("SpawnerChildEventTerminal._on_termination_req: "
                  "termination callback raised: %s" % e, file=sys.stderr)
