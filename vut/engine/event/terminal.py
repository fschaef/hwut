"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: EventTerminal - one end of a point-to-point Event connection.

A Terminal owns exactly one Channel (its peer connection) and one
receive-side Dispatcher (fans received Events out to local handlers).
The Terminal is protocol-agnostic: the user passes an
EventChannelParameter and never has to care which transport is actually
used.

PUBLIC SHAPE

    terminal = EventTerminal(ecp)
    sub = terminal.dispatcher.subscribe_on_event(SomeEvent, handler)
    await terminal.start()                  # begins receive loop
    await terminal.send(some_event)         # sends to peer
    await terminal.stop()                   # ends, closes Channel


LIFECYCLE

    constructor       -- builds nothing yet; just stores ecp
    .start()          -- builds the Channel (async, may do socket I/O);
                         spawns the receive loop as an asyncio Task
    .send(event)      -- delegates to Channel.send()
    .stop()           -- cancels the receive loop; closes the Channel

When the underlying Channel closes (peer disconnects, etc.), the
receive loop ends. The Terminal does NOT auto-reconnect. This matches
the design: when a Terminal ends, the transport ends.


RECEIVE-SIDE DISPATCHER

The receive Dispatcher is constructed with
enforce_async_callbacks_f=True. Callbacks must be coroutine functions,
because they run on the same asyncio loop that drives the receive
loop; a slow sync callback would block further Event delivery.

If the consumer wants to do sync work (e.g. push onto a thread-Queue
for processing elsewhere), the right pattern is to subscribe a callable
object with a .send() method - the Dispatcher treats it as a "send"
sink and calls it without create_task. Slow .send() implementations
are still the consumer's responsibility.
________________________________________________________________________________
"""
import asyncio
import sys

from vut.engine.event.channel           import EventChannel
from vut.engine.event.channel_parameter import EventChannelParameter
from vut.engine.event.dispatcher        import EventDispatcher
from vut.engine.event.event             import Event


class EventTerminal:
    """One end of a point-to-point Event connection.

    Owns one Channel and one receive-side Dispatcher. Public API:

        terminal = EventTerminal(ecp)
        terminal.dispatcher.subscribe_on_*(...)         # arrange handlers
        await terminal.start()                          # build channel + recv loop
        await terminal.send(event)                      # send to peer
        await terminal.stop()                           # tear down
    """

    def __init__(self, ecp: EventChannelParameter):
        """RETURN: a new (not yet started) EventTerminal.

        Channel construction is DEFERRED to start() because building
        some channels (Remote, in particular) is async work.
        """
        self._ecp        = ecp
        self._channel:    "EventChannel | None"      = None
        self._recv_task:  "asyncio.Task | None"      = None
        self._started    = False
        self._stopped    = False
        self.dispatcher  = EventDispatcher(enforce_async_callbacks_f=True)

    async def start(self) -> None:
        """RETURN: None.

        Builds the Channel from the ECP and spawns the receive loop.
        Idempotent: calling start() twice is a no-op after the first.
        """
        if self._started:
            return
        self._started = True
        self._channel = await self._ecp.make_channel()
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def send(self, event: Event) -> None:
        """RETURN: None.

        Sends event to the peer Terminal. Awaits the underlying
        Channel.send(); if the transport is backpressured, this awaits
        until space is available.
        """
        if not self._started:
            raise RuntimeError("EventTerminal.send: terminal not started")
        if self._stopped:
            raise RuntimeError("EventTerminal.send: terminal is stopped")
        await self._channel.send(event)

    async def stop(self) -> None:
        """RETURN: None.

        Cancels the receive loop and closes the Channel. Idempotent.
        """
        if self._stopped:
            return
        self._stopped = True

        if self._recv_task is not None:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass

        if self._channel is not None:
            try:
                await self._channel.close()
            except Exception as e:
                print("EventTerminal.stop: channel close raised: %s" % e,
                      file=sys.stderr)

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """RETURN: None.

        Pulls events from the Channel until it returns None (closed)
        or the task is cancelled. Each received Event is dispatched
        through self.dispatcher.

        Exceptions from individual Events do NOT kill the loop; they
        are logged. Cancellation propagates cleanly via asyncio.
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

                try:
                    self.dispatcher.dispatch(event)
                except Exception as e:
                    print("EventTerminal._receive_loop: dispatch raised: %s"
                          % e, file=sys.stderr)
        except asyncio.CancelledError:
            pass

    # ----------------------------------------------------------------
    # Object-as-sink protocol: a Terminal IS a sink.
    # ----------------------------------------------------------------

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
