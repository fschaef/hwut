"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: EventTerminal - one end of a point-to-point Event connection.

A Terminal owns exactly one Channel (its peer connection) and one
receive-side Dispatcher (fans received Events out to local handlers).
The Terminal is protocol-agnostic: the user passes an
EventChannelParameter and never has to care which transport is
actually used.

PUBLIC SHAPE

    # Explicit lifecycle
    terminal = EventTerminal(ecp)
    sub = terminal.dispatcher.subscribe_on_event(SomeEvent, handler)
    await terminal.start()                  # blocks until peer Up received
    await terminal.send(some_event)
    await terminal.stop()                   # sends Down, closes channel

    # Async context manager
    async with EventTerminal(ecp) as terminal:
        terminal.dispatcher.subscribe_on_event(SomeEvent, handler)
        await terminal.send(some_event)
    # stop() runs on exit, whether normal or exception

Note that subscription via `.dispatcher` is done either between
construction and start(), or any time after start() returns.
In the `with` form, subscribe inside the block before the first
expected event arrives.


LIFECYCLE PROTOCOL (Up / Down handshake)

A Terminal participates in a symmetric wire-level handshake with its
peer using two EVENT_INFRA events:

    EventTerminalUp    sent on receive-loop entry; the peer replies
                       with its own EventTerminalUp.
    EventTerminalDown  sent on deliberate stop(); signals the peer
                       that no more application events will follow.

start() blocks until BOTH conditions hold:
    -- we have sent our own Up
    -- we have received the peer's Up

The protocol is symmetric. Both sides send Up on receive-loop entry.
A side that receives Up while still in UP_PENDING transitions to UP;
its own Up has already been sent so it does NOT send another. A side
that receives Up after it has already transitioned to UP also does
nothing (the peer may have restarted, or duplicated; we don't care).

A lost Up is harmless: if our Up was lost, the peer is still
UP_PENDING and waiting for ours; we'll send another Up if it arrives
late (we won't - we only send once on loop entry). The actual safety
property is that BOTH sides are sending Up at loop-entry time, so as
long as either Up arrives, the receiving side completes its handshake
and the sending side either has already received its peer's Up (and
is done) or will receive it when the other side reciprocates. In
practice, both Ups reach their peers because the channels we ship
do not drop messages; the "no harm if a signal gets lost" property
applies to imagined fault-tolerant transports without changing the
shipped semantics.

stop() sends EventTerminalDown on the wire (best-effort) and then
closes the channel. If the peer initiated the close (we received
their Down, then channel.receive() returned None), we do NOT send
our own Down in response - the peer is gone and any send would land
in a closed channel.


EVENT_INFRA EVENTS ARE NOT DISPATCHED LOCALLY

EventTerminalUp and EventTerminalDown received from the peer are
handled INTERNALLY by the Terminal (state transitions, handshake
release). They are NOT passed to the user's receive-side Dispatcher.

The one exception is EventTerminalDown forwarded by an EventRouter:
the Router subscribes (via a private hook) to "the peer told us
they're going" so it can remove the dead Terminal's entry. This
hook is exposed via the `_on_peer_down` mechanism; see set_peer_down_callback.

Locally-emitted Up / Down (the ones we send) are NEVER dispatched
to our own dispatcher. The Terminal's local lifecycle is the
caller's concern (the caller knows because they called start() /
stop()).


RECEIVE-SIDE DISPATCHER

The receive Dispatcher is constructed with
enforce_async_callbacks_f=True. Callbacks must be coroutine
functions because they run on the same asyncio loop that drives
the receive loop; a slow sync callback would block further Event
delivery.

If the consumer wants to do sync work (e.g. push onto a thread Queue
for processing elsewhere), the right pattern is to subscribe a
callable object with a .send() method - the Dispatcher treats it
as a "send" sink and calls it without create_task.
________________________________________________________________________________
"""
import asyncio
import sys

from vut.engine.event.channel           import EventChannel
from vut.engine.event.channel_parameter import EventChannelParameter
from vut.engine.event.dispatcher        import EventDispatcher
from vut.engine.event.event             import Event
from vut.engine.event.events            import EventTerminalUp, EventTerminalDown


# ============================================================================
# Internal handshake states
# ============================================================================

_STATE_NEW         = "NEW"            # constructed, not started
_STATE_UP_PENDING  = "UP_PENDING"     # we sent Up, awaiting peer Up
_STATE_UP          = "UP"             # peer Up received; fully connected
_STATE_DOWN        = "DOWN"           # stop()ped or peer Down received


class EventTerminal:
    """One end of a point-to-point Event connection.

    Owns one Channel and one receive-side Dispatcher. Supports both
    explicit start()/stop() and the async context-manager form.
    """

    def __init__(self, ecp: EventChannelParameter):
        """RETURN: a new (not yet started) EventTerminal.

        Channel construction is DEFERRED to start() because building
        some channels (Remote, in particular) is async work.
        """
        self._ecp                          = ecp
        self._channel: "EventChannel | None"    = None
        self._recv_task: "asyncio.Task | None"  = None
        self._state                        = _STATE_NEW

        # Handshake plumbing. _peer_up_event fires when the peer's Up
        # has been received. start() awaits it.
        self._peer_up_event                = asyncio.Event()

        # Optional callback (Router uses this) invoked when peer Down
        # arrives - i.e. when "this Terminal's peer told us they're
        # going". Set via set_peer_down_callback().
        self._peer_down_callback           = None

        # User-facing receive dispatcher. EVENT_INFRA events are NOT
        # routed here.
        self.dispatcher                    = EventDispatcher(
            enforce_async_callbacks_f=True
        )

    # ------------------------------------------------------------------
    # Explicit lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """RETURN: None,  after the handshake has completed (both our
                          Up sent and peer's Up received).

        Builds the Channel, spawns the receive loop, sends our
        EventTerminalUp on the wire, and BLOCKS until the peer's Up
        arrives. A Terminal is not functional without its counterpart
        so we do not return until the counterpart has confirmed.

        Idempotent: calling start() while already UP returns immediately.
        Calling start() after stop() raises RuntimeError - a Terminal
        is single-use.
        """
        if self._state == _STATE_UP:
            return
        if self._state == _STATE_DOWN:
            raise RuntimeError(
                "EventTerminal.start: terminal is DOWN; cannot restart."
            )
        if self._state != _STATE_NEW:
            # UP_PENDING - already starting; await the existing handshake.
            await self._peer_up_event.wait()
            return

        # NEW -> UP_PENDING: build the channel, spawn the receive loop,
        # send our Up, then block until the peer's Up arrives.
        self._channel   = await self._ecp.make_channel()
        self._recv_task = asyncio.create_task(self._receive_loop())
        self._state     = _STATE_UP_PENDING

        await self._channel.send(EventTerminalUp())

        # Block until peer's Up arrives. The receive loop sets
        # _peer_up_event when it sees an incoming EventTerminalUp.
        await self._peer_up_event.wait()
        # State has been advanced to UP by _handle_infra_event.

    async def send(self, event: Event) -> None:
        """RETURN: None,  after the event has been handed to the channel.

        Sends event to the peer Terminal. Requires the terminal to
        be UP (handshake complete). Raises RuntimeError if not UP.
        """
        if self._state != _STATE_UP:
            raise RuntimeError(
                "EventTerminal.send: terminal state is %s; "
                "send() requires UP. Did you forget start()?" % self._state
            )
        await self._channel.send(event)

    async def stop(self) -> None:
        """RETURN: None.

        Sends EventTerminalDown on the wire (best-effort), cancels
        the receive loop, and closes the Channel. Idempotent: a
        second call is a no-op.
        """
        if self._state == _STATE_DOWN:
            return

        prior_state = self._state
        self._state = _STATE_DOWN

        # Best-effort Down. Only attempt if the channel was ever built
        # and if we hadn't already received peer Down (in which case
        # the channel is on its way out anyway).
        if self._channel is not None and prior_state in (_STATE_UP, _STATE_UP_PENDING):
            try:
                await self._channel.send(EventTerminalDown())
            except Exception as e:
                # Channel may already be closed by peer. Not fatal.
                print("EventTerminal.stop: send Down failed (likely peer gone): %s"
                      % e, file=sys.stderr)

        # Cancel the receive loop. If it's already exited, this is a no-op.
        if self._recv_task is not None and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass

        # Close the channel.
        if self._channel is not None:
            try:
                await self._channel.close()
            except Exception as e:
                print("EventTerminal.stop: channel close raised: %s" % e,
                      file=sys.stderr)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "EventTerminal":
        """RETURN: self,  after start() has completed (handshake done).

        Enables:
            async with EventTerminal(ecp) as t:
                ...

        On exit, stop() is called whether the block completed normally
        or raised.
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """RETURN: None.  Calls stop() on block exit.

        Exceptions inside the block are NOT suppressed; they propagate
        normally after stop() has run.
        """
        await self.stop()
        # Returning falsy / None means: do not suppress the exception.
        return None

    # ------------------------------------------------------------------
    # Router hook for peer-Down notification
    # ------------------------------------------------------------------

    def set_peer_down_callback(self, callback) -> None:
        """RETURN: None.

        Register a callback invoked when this Terminal receives an
        EventTerminalDown from its peer (i.e. the peer has signalled
        deliberate termination). The callback receives no arguments
        and may be sync or async.

        Used by EventRouter to remove a dead Terminal's entry from
        its dispatch table.
        """
        self._peer_down_callback = callback

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """RETURN: None,  when the channel closes or the task is cancelled.

        Pulls events from the channel. EVENT_INFRA events are handled
        internally (handshake / peer-Down). All other events are
        dispatched through the user-facing dispatcher.

        Individual-event exceptions are logged and do NOT kill the
        loop. Cancellation propagates cleanly.
        """
        try:
            while True:
                try:
                    event = await self._channel.receive()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print("EventTerminal._receive_loop: receive raised: %s"
                          % e, file=sys.stderr)
                    break

                if event is None:                       # channel closed
                    break

                # Filter EVENT_INFRA events into the internal handler;
                # everything else goes to the user dispatcher.
                if isinstance(event, (EventTerminalUp, EventTerminalDown)):
                    handled = await self._handle_infra_event(event)
                    if handled is False:
                        # Peer Down -> exit loop cleanly.
                        break
                else:
                    try:
                        self.dispatcher.dispatch(event)
                    except Exception as e:
                        print("EventTerminal._receive_loop: dispatch raised: %s"
                              % e, file=sys.stderr)
        except asyncio.CancelledError:
            pass

    async def _handle_infra_event(self, event) -> bool:
        """RETURN: True,   to continue the receive loop.
                  False,   to exit the receive loop cleanly (peer Down).

        Handles EVENT_INFRA events. Up advances state; Down triggers
        loop exit and the peer-Down callback.
        """
        if isinstance(event, EventTerminalUp):
            # Peer Up: complete the handshake if still pending. If
            # already UP, ignore (peer restarted / duplicate).
            if self._state == _STATE_UP_PENDING:
                self._state = _STATE_UP
                self._peer_up_event.set()
            return True

        if isinstance(event, EventTerminalDown):
            # Peer is going. Notify the router (or whoever subscribed).
            # We do NOT send our own Down back; the peer is gone.
            if self._peer_down_callback is not None:
                try:
                    result = self._peer_down_callback()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    print("EventTerminal._handle_infra_event: peer_down callback raised: %s"
                          % e, file=sys.stderr)
            # Mark DOWN immediately so any concurrent send() raises
            # rather than going into a closing channel.
            self._state = _STATE_DOWN
            return False

        # Defensive: unknown EVENT_INFRA event. Log, ignore.
        print("EventTerminal._handle_infra_event: unexpected event %s"
              % type(event).__name__, file=sys.stderr)
        return True

    # ------------------------------------------------------------------
    # Object-as-sink protocol: a Terminal IS a sink.
    # ------------------------------------------------------------------

    def send_nowait(self, event: Event) -> None:
        """RETURN: None.

        Schedule send(event) without awaiting it. Used when this
        Terminal is registered as a sink in a Dispatcher whose
        dispatch() is synchronous - the Dispatcher calls
        terminal.send(event), gets a coroutine, and schedules it
        as a task.

        This shim is provided for completeness; the Dispatcher's
        own send-sink handling (see dispatcher.py) already detects
        a coroutine result from .send() and schedules it.
        """
        asyncio.create_task(self.send(event))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        """RETURN: str,  one of 'NEW', 'UP_PENDING', 'UP', 'DOWN'.

        For tests and diagnostics.
        """
        return self._state

    @property
    def is_up(self) -> bool:
        """RETURN: bool,  True if the terminal is fully connected (state == UP)."""
        return self._state == _STATE_UP
