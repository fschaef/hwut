"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Watchdog - liveness supervision of a launched child.

The Watchdog answers ONE question, repeatedly: "is the child still
there, and if not, what verdict does that imply?". It is the only place
where a child that dies WITHOUT a clean EventChildTermination becomes a
terminal E_ChildState.

WHY A SEPARATE MODULE

The Spawner has three jobs - launch, route, and supervise liveness. The
first two are event-driven and synchronous to the spawn call; the third
is a free-running background activity with its own lifetime, its own
poll period, and its own shutdown. Bundling it into the Spawner mixed a
background loop into an otherwise reactive object. Pulled out, the
Watchdog is a small unit with a clear contract and can be reasoned about
- and tested - on its own.

WHAT IT DEPENDS ON

A Watchdog is constructed with exactly the three collaborators it needs,
and holds nothing else:

    handle          - the ChildHandle; its liveness() is the liveness
                      source (returns an E_Liveness).
    state_machine   - the ChildStateMachine; its notify_channel_silent()
                      is the verdict sink, and its .state tells the
                      Watchdog when to stop.
    parent_terminal - the SpawnerParentEventTerminal; only its
                      set_peer_down_callback() is used, to register the
                      reactive trigger.

It does not know about the EventRouter, the config, or the spawn
functions. That keeps the Spawner <-> Watchdog seam narrow.

TWO TRIGGERS, ONE RESOLVER

    periodic poll   every poll_ms the loop consults handle.liveness().
                    Catches a child gone SILENT without the channel
                    ever signalling - a wedged process, or an
                    abnormally-killed one whose queue never closes.
    peer-down       the parent terminal's peer-down callback fires the
                    resolver at once, without waiting for the next tick,
                    when the channel DID signal.

Both funnel into resolve_silence(), which hands an E_Liveness to the
FSM. See the per-method docstrings for the DEAD / ALIVE / UNKNOWN
verdict logic (DISCUSSION.txt D7/D8).
________________________________________________________________________________
"""
import asyncio
import sys

from vut.engine.spawner.enums import E_Liveness


class Watchdog:
    """Liveness supervision of one launched child.

    Owned by a Spawner, one per spawned child. Created together with the
    child's ChildStateMachine and started once the startup handshake has
    proven the channel live. Runs until the FSM reaches a terminal state
    (it stops itself) or the Spawner cancels it.

    The Watchdog NEVER decides a verdict itself - it only reads liveness
    and forwards it; the ChildStateMachine owns the E_ChildState
    transition. This keeps the verdict logic in one place.
    """

    def __init__(self,
                 handle,
                 state_machine,
                 parent_terminal,
                 poll_ms: int = 250):
        """RETURN: a new, not-yet-started Watchdog.

        handle          -- the ChildHandle; handle.liveness() is polled.
        state_machine   -- the ChildStateMachine; receives the verdict
                           via notify_channel_silent() and is queried
                           for .state.
        parent_terminal -- the SpawnerParentEventTerminal; its
                           set_peer_down_callback() registers the
                           reactive trigger.
        poll_ms         -- the periodic poll period in milliseconds;
                           also the grace period granted for an
                           in-flight confirmation (see _loop).

        Construction wires nothing and starts nothing; call start().
        """
        self._handle        = handle
        self._state_machine = state_machine
        self._parent        = parent_terminal
        self._poll_ms       = poll_ms
        self._task          = None      # asyncio.Task, set by start()

    # ----------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------

    def start(self) -> None:
        """RETURN: None.

        Arms both triggers:

          -- the REACTIVE one: registers a peer-down callback on the
             parent terminal, so a channel that signals its peer is gone
             resolves immediately, without waiting for the next poll.
          -- the PROACTIVE one: launches the periodic poll loop as an
             asyncio.Task.

        Called by the Spawner only AFTER the startup handshake has
        completed - before that there is no proven-live child worth
        supervising.
        """
        # Reactive trigger: peer-down resolves at once.
        def _on_peer_down():
            return asyncio.create_task(self.resolve_silence())
        self._parent.set_peer_down_callback(_on_peer_down)

        # Proactive trigger: the periodic poll loop.
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        """RETURN: None.

        Cancels the periodic poll task, if running. Called when the FSM
        reaches a terminal state - a verdict exists, there is nothing
        left to watch. Wired as the FSM's on-terminal callback by the
        Spawner, so it fires automatically.

        Safe to call more than once, and safe to call before start().
        """
        if self._task is not None and not self._task.done():
            self._task.cancel()

    # ----------------------------------------------------------------
    # The poll loop
    # ----------------------------------------------------------------

    async def _loop(self) -> None:
        """RETURN: None, when the FSM has reached a terminal state.

        The periodic half of the Watchdog. Every poll_ms it consults the
        child handle's liveness directly - it does NOT gate on the
        terminal's is_up flag, because a peer killed abnormally leaves
        is_up True indefinitely (the channel queue never closes); gating
        on it would reproduce exactly that blind spot. The handle's
        liveness IS the signal.

        Per tick:

          handle ALIVE    healthy; nothing to do.
          handle DEAD     the child's OS context is gone. A clean
                          completion ALSO reads DEAD, and its
                          EventChildTermination may still be in flight
                          on the receive loop. So a DEAD reading is not
                          acted on immediately: the loop waits one more
                          tick as a grace period for the confirmation
                          to be processed. If the FSM has by then
                          reached a terminal state (TERM_OK), the clean
                          completion won the race and the loop simply
                          exits. If the FSM is STILL live after the
                          grace tick, no confirmation is coming ->
                          resolve_silence() turns the DEAD reading into
                          TERM_FAILURE.
          handle UNKNOWN  the handle could not be consulted -> resolve
                          immediately (TERM_LOST_CONNECTION); there is
                          no confirmation race to wait out.

        The loop exits as soon as the FSM is terminal - by then a
        verdict exists and there is nothing left to supervise.
        """
        try:
            while not self._state_machine.state.is_terminal():
                await asyncio.sleep(self._poll_ms / 1000.0)
                if self._state_machine.state.is_terminal():
                    break

                liveness = await self._handle.liveness()

                if liveness is E_Liveness.ALIVE:
                    continue                        # healthy; keep watching

                elif liveness is E_Liveness.UNKNOWN:
                    # No information, no race to wait out - resolve now.
                    await self.resolve_silence()
                    break

                # liveness is DEAD: grant one grace tick for an
                # in-flight EventChildTermination to be processed.
                await asyncio.sleep(self._poll_ms / 1000.0)
                if self._state_machine.state.is_terminal():
                    break                           # clean completion won
                # Still live after the grace tick - no confirmation is
                # coming. Resolve the DEAD reading into a verdict.
                await self.resolve_silence()
                break
        except asyncio.CancelledError:
            return
        except Exception as e:
            print("Watchdog._loop: watchdog raised: %s" % e,
                  file=sys.stderr)

    # ----------------------------------------------------------------
    # The resolver
    # ----------------------------------------------------------------

    async def resolve_silence(self) -> None:
        """RETURN: None.

        Consults the child handle's liveness and hands the result to the
        FSM's notify_channel_silent(), which turns it into a terminal
        verdict (TERM_FAILURE for a DEAD child, TERM_LOST_CONNECTION for
        ALIVE / UNKNOWN - see ChildStateMachine.notify_channel_silent).

        A no-op once the FSM is terminal: the verdict is already in.
        Idempotent, so it is safe for both triggers (the poll loop and
        the peer-down callback) to call it, possibly more than once.
        """
        if self._state_machine.state.is_terminal():
            return
        liveness = await self._handle.liveness()
        await self._state_machine.notify_channel_silent(liveness)
