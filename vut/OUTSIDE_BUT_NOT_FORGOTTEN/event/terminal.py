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

The one exception is EventTerminalDown observed by an EventRouter:
the Router registers a peer-down callback ("the peer told us they're
going") so it can remove the dead Terminal's entry. The hook is
add_peer_down_callback() (additive); set_peer_down_callback() is the
single-slot back-compat form.

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

from vut.engine.event.channel.channel   import EventChannel
from vut.engine.event.channel.parameter import EventChannelParameter
from vut.engine.event.dispatcher        import EventDispatcher
from vut.engine.event.event             import Event
from vut.engine.event.events            import (EventTerminalUp,
                                                EventTerminalDown,
                                                EventInfo)


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
        self._ecp   = ecp
        self._state = _STATE_NEW
        self._channel:   "EventChannel | None" = None
        self._recv_task: "asyncio.Task | None" = None

        # Handshake plumbing. _peer_up_event fires when the peer's Up
        # has been received. start() awaits it.
        self._peer_up_event = asyncio.Event()

        # Callbacks invoked when peer Down arrives - i.e. when "this
        # Terminal's peer told us they're going". A LIST: more than one
        # consumer may care (e.g. several Router entries sharing this
        # Terminal). Registered via add_peer_down_callback();
        # set_peer_down_callback() is the single-slot back-compat form.
        self._peer_down_callbacks: list = []

        # EventInfo handshake state (versioning, see send()/_receive_loop):
        #   _info_sent  -- event ids for which we have already sent an
        #                  EventInfo ahead of the first occurrence.
        #   _info_seen  -- event id -> version, learned from peer EventInfo.
        #                  An incoming non-infra event whose id is absent
        #                  here is REJECTED (loud diagnostic, dropped).
        self._info_sent: set            = set()
        self._info_seen: dict[str, int] = {}

        # User-facing receive dispatcher. 
        # EVENT_INFRA are NOT routed here.
        self.dispatcher = EventDispatcher(
            enforce_async_callbacks_f=True
        )

    # ------------------------------------------------------------------
    # Explicit lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> bool:
        """RETURN: True,  the Terminal is UP (handshake complete: our Up
                          sent and the peer's Up received), or was
                          already UP.
                   False, the Terminal is DOWN and cannot be started
                          (single-use); a diagnostic is written to
                          stderr. Nothing is built.

        Builds the Channel, spawns the receive loop, sends our
        EventTerminalUp on the wire, and BLOCKS until the peer's Up
        arrives. A Terminal is not functional without its counterpart
        so we do not return until the counterpart has confirmed.

        Idempotent: calling start() while already UP returns True
        immediately. A Terminal is single-use - once DOWN it cannot be
        restarted; that is reported by return value, not exception.
        """
        if self._state == _STATE_UP:
            return True
        elif self._state == _STATE_DOWN:
            print("EventTerminal.start: terminal is DOWN; cannot restart "
                  "(single-use) - not started.", file=sys.stderr)
            return False
        elif self._state != _STATE_NEW:
            # UP_PENDING - already starting; await the existing handshake.
            await self._peer_up_event.wait()
            return True

        # NEW -> UP_PENDING: build the channel, spawn the receive loop,
        # send our Up, then block until the peer's Up arrives.
        self._channel   = await self._ecp.make_channel()
        self._recv_task = asyncio.create_task(self._receive_loop())
        self._state     = _STATE_UP_PENDING

        await self._channel.send(EventTerminalUp())

        # Block until '_receive_loop()' receives the counter sides 'Up' message
        await self._peer_up_event.wait()
        # received 'Up' message => 'self._state == _STATE_UP'
        return True

    async def send(self, event: Event) -> bool:
        """RETURN: True,  the event was handed to the Channel.
                   False, the Terminal was not UP; nothing was sent
                          (a diagnostic is written to stderr).

        Sends event to the peer Terminal. A not-UP send() is a NORMAL,
        expected outcome - the peer may go DOWN between the caller's
        check and this call through no fault of the caller - so it is
        reported by return value, not by exception. The caller decides
        whether a failed send matters.

        On first send of a given event TYPE, an EventInfo descriptor for
        that type is sent ahead of the event (see _ensure_event_info);
        the peer rejects an event whose type it has no EventInfo for.
        """
        if self._state != _STATE_UP:
            print("EventTerminal.send: terminal state is %s; send() requires "
                  "UP - event not sent." % self._state, file=sys.stderr)
            return False
        await self._ensure_event_info(event)
        await self._channel.send(event)
        return True

    async def _ensure_event_info(self, event: Event) -> None:
        """RETURN: None.

        On the FIRST send of a given event type, send an EventInfo
        descriptor (carrying that type's WIRE_VERSION) ahead of it, so
        the peer learns the version before it sees the event itself.
        Subsequent sends of the same type send nothing extra.

        EVENT_INFRA events (Up, Down, EventInfo itself) are exempt -
        they are the bootstrap protocol and carry no EventInfo, else
        the handshake would recurse. The peer accepts EVENT_INFRA
        unconditionally (see _receive_loop).
        """
        if event.category == "EVENT_INFRA":
            return
        event_id = type(event).id
        if event_id in self._info_sent:
            return
        self._info_sent.add(event_id)
        await self._channel.send(
            EventInfo(event_id=event_id,
                      version=type(event).WIRE_VERSION)
        )

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
    def add_peer_down_callback(self, callback) -> None:
        """RETURN: None.

        Register a callback invoked when this Terminal receives an
        EventTerminalDown from its peer (the peer signalled deliberate
        termination). The callback receives no arguments and may be
        sync or async. Multiple callbacks may be registered; all fire,
        in registration order, on peer Down.

        EventRouter uses this to remove a dead Terminal's entry from
        its dispatch table - several entries may share one Terminal,
        so additive registration (not a single slot) is required.
        """
        self._peer_down_callbacks.append(callback)

    def set_peer_down_callback(self, callback) -> None:
        """RETURN: None.

        Back-compat single-slot form: REPLACES all registered peer-down
        callbacks with the one given. Prefer add_peer_down_callback()
        when more than one consumer may care.
        """
        self._peer_down_callbacks = [callback]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _receive_loop(self) -> None:
        """RETURN: None,  when the channel closes or the task is cancelled.

        Pulls events from the channel. EVENT_INFRA events (Up, Down,
        EventInfo) are consumed internally - handshake, peer-down, and
        version caching - and never reach the user dispatcher. Every
        other event is checked against the EventInfo cache: an event
        whose type has no prior EventInfo is REJECTED (loud diagnostic,
        dropped) rather than dispatched. Accepted events go to the
        user-facing dispatcher.

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

                # EVENT_INFRA events are the bootstrap protocol: handled
                # internally, accepted unconditionally, never dispatched.
                if isinstance(event, EventTerminalUp):
                    await self._on_EventTerminalUp(event)
                elif isinstance(event, EventTerminalDown):
                    await self._on_EventTerminalDown(event)
                    break
                elif isinstance(event, EventInfo):
                    self._on_EventInfo(event)
                else:
                    # Versioned admission: the type must have been
                    # announced by an EventInfo first, else reject.
                    if type(event).id not in self._info_seen:
                        print("EventTerminal._receive_loop: rejected event "
                              "of type %r - no EventInfo received for it "
                              "first (version handshake missing or out of "
                              "order); dropping."
                              % type(event).id, file=sys.stderr)
                        continue
                    try:
                        self.dispatcher.dispatch(event)
                    except Exception as e:
                        print("EventTerminal._receive_loop: dispatch raised: %s"
                              % e, file=sys.stderr)

        except asyncio.CancelledError:
            pass

    def _on_EventInfo(self, event) -> None:
        """RETURN: None.

        Cache the (event_id -> version) announced by the peer. A later
        event of that type is admitted; one with no cached EventInfo is
        rejected in _receive_loop. Re-announcement (same id again) just
        overwrites - last writer wins, harmless for a single peer.
        """
        self._info_seen[event.event_id] = event.version

    async def _on_EventTerminalUp(self, event):
        # Peer Up: complete the handshake if still pending. If
        # already UP, ignore (peer restarted / duplicate).
        if self._state == _STATE_UP_PENDING:
            self._state = _STATE_UP
            self._peer_up_event.set()

    async def _on_EventTerminalDown(self, event):
        # Mark DOWN immediately => no more send()
        self._state = _STATE_DOWN

        # Peer is going. Notify every registered consumer (Router
        # entries, user hooks). We do NOT send our own Down back; the
        # peer is gone. One callback raising must not stop the others,
        # so each is isolated. Iterate a snapshot in case a callback
        # mutates the list (e.g. Router.remove_entry).
        for callback in tuple(self._peer_down_callbacks):
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print("EventTerminal._on_EventTerminalDown: peer-down "
                      "callback raised: %s" % e, file=sys.stderr)

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

