"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Bidirectional point-to-point conduit for Events.

An EventChannel is the wire between two EventTerminals. Each end is one
Terminal; one Channel connects exactly two Terminals. The Channel hides
the underlying transport (asyncio queue, thread queue, multiprocessing
queue, network socket) behind a uniform async interface.


ABC SHAPE

    async send(event) -- ship an Event to the peer
    async receive()   -- await one Event from the peer
                         returns None if the Channel has closed
    async close()     -- close this end; peer detects via receive()

Channels are BIDIRECTIONAL. The same Channel object supports both
.send() and .receive(); the two directions are independent.

The interface is async even for synchronous transports. Concrete
subclasses for blocking transports (multiprocessing.Queue, sockets)
wrap blocking calls in loop.run_in_executor(). This lets every Channel
be used in an asyncio receive loop uniformly.


CONCRETE CHANNELS

    AsyncQueueChannel       in-process; pair of asyncio.Queue
    ThreadQueueChannel      in-process; pair of queue.Queue
    ProcessQueueChannel     across-process; pair of multiprocessing.Queue;
                            uses Marshaller for serialisation
    RemoteChannel           across-machine; socket; uses Marshaller


SERIALISATION

Channels that cross a Python interpreter boundary (Process, Remote)
serialise via Marshaller. Local channels (AsyncQueue, ThreadQueue)
do not serialise; they ship Event instances directly.

This is invisible at the Channel interface. Callers send and receive
Event instances regardless of channel type.


LIFECYCLE

A Channel exists for the duration of one Terminal-to-Terminal
connection. close() is end-to-end: the side that closes shuts down its
underlying transport (closes queues, closes sockets). The peer detects
closure as receive() returning None.

No transport-layer notion: when a Channel ends, the transport ends.
________________________________________________________________________________
"""
import asyncio
import queue as _queue                                  # threading queue
import struct
import sys

from abc      import ABC, abstractmethod

from vut.engine.event.event      import Event
from vut.engine.event.marshaller import Marshaller


# ============================================================================
# Abstract base
# ============================================================================

class EventChannel(ABC):
    """Bidirectional point-to-point Event conduit.

    See module header for the contract. Concrete subclasses
    implement the three async methods.
    """

    @abstractmethod
    async def send(self, event: Event) -> None:
        """RETURN: None.

        Ships event to the peer. May block (asynchronously) if the
        underlying transport is full / backpressured.
        """
        ...

    @abstractmethod
    async def receive(self) -> "Event | None":
        """RETURN: Event, the next event from the peer.
                   None,  if the Channel has closed.

        Blocks (asynchronously) until an event is available or the
        Channel closes.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """RETURN: None.

        Closes this end of the Channel. Idempotent. After close(),
        further send() calls may raise; receive() may return None.
        """
        ...


# ============================================================================
# In-process: asyncio.Queue
# ============================================================================

class AsyncQueueChannel(EventChannel):
    """In-process Channel over a pair of asyncio.Queues.

    Sends and receives in the same event loop. No serialisation;
    Event instances are passed by reference.

    Constructed with the queue used for SENDING (out_q) and the queue
    used for RECEIVING (in_q). The PEER's queues are flipped: peer's
    out_q is this side's in_q and vice versa.
    """

    _CLOSE_SENTINEL = object()                          # placed on in_q on close

    def __init__(self, in_q: asyncio.Queue, out_q: asyncio.Queue):
        """RETURN: a new AsyncQueueChannel."""
        self._in_q   = in_q
        self._out_q  = out_q
        self._closed = False

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("AsyncQueueChannel.send: channel is closed")
        await self._out_q.put(event)

    async def receive(self) -> "Event | None":
        if self._closed:
            return None
        item = await self._in_q.get()
        if item is self._CLOSE_SENTINEL:
            self._closed = True
            return None
        return item

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Wake any pending receive() on the LOCAL side, signalling closure.
        # We use a sentinel rather than asyncio.Queue.shutdown() (3.13+)
        # so the channel works on older Pythons.
        try:
            self._in_q.put_nowait(self._CLOSE_SENTINEL)
        except asyncio.QueueFull:
            # Receive side will see closed=True on next call regardless.
            pass


# ============================================================================
# Across-thread: queue.Queue with run_in_executor for the blocking get
# ============================================================================
class ThreadQueueChannel(EventChannel):
    """In-process Channel over a pair of thread-safe queue.Queue objects.

    Used when the peer is on a worker thread (not on the asyncio loop).
    Sends are non-blocking put_nowait; receives use run_in_executor()
    to wrap the blocking queue.Queue.get() so the asyncio loop is not
    blocked.
    """
    _CLOSE_SENTINEL = object()

    def __init__(self, in_q: _queue.Queue, out_q: _queue.Queue):
        """RETURN: a new ThreadQueueChannel."""
        self._in_q   = in_q
        self._out_q  = out_q
        self._closed = False

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("ThreadQueueChannel.send: channel is closed")
        # queue.Queue.put is blocking-by-default but typically very fast
        # for unbounded queues; we offload to the executor to keep the
        # asyncio loop responsive even with bounded queues.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._out_q.put, event)

    async def receive(self) -> "Event | None":
        if self._closed:
            return None
        loop = asyncio.get_running_loop()
        item = await loop.run_in_executor(None, self._in_q.get)
        if item is self._CLOSE_SENTINEL:
            self._closed = True
            return None
        return item

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Put the sentinel into THIS side's in_q so a blocked receive() wakes.
        try:
            self._in_q.put_nowait(self._CLOSE_SENTINEL)
        except _queue.Full:
            pass

# ============================================================================
# Across-process: multiprocessing.Queue + Marshaller
# ============================================================================
class ProcessQueueChannel(EventChannel):
    """Across-process Channel over a pair of multiprocessing.Queue.

    Events are serialised via Marshaller before send and deserialised
    after receive. The wire is a dict (Marshaller's wire form) rather
    than the raw Event - this is what crosses the pickle boundary.
    """

    _CLOSE_SENTINEL = {"_close": True}                  # picklable dict

    def __init__(self, in_q, out_q):
        """RETURN: a new ProcessQueueChannel.

        in_q and out_q must be multiprocessing.Queue (or compatible
        picklable queue objects).
        """
        self._in_q   = in_q
        self._out_q  = out_q
        self._closed = False

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("ProcessQueueChannel.send: channel is closed")
        wire = Marshaller.serialize(event)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._out_q.put, wire)

    async def receive(self) -> "Event | None":
        if self._closed:
            return None
        loop = asyncio.get_running_loop()
        wire = await loop.run_in_executor(None, self._in_q.get)
        if isinstance(wire, dict) and wire.get("_close"):
            self._closed = True
            return None
        return Marshaller.deserialize(wire)             # may return None on validation fail

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._in_q.put_nowait(self._CLOSE_SENTINEL)
        except Exception as e:
            print("ProcessQueueChannel.close: put_nowait failed: %s" % e,
                  file=sys.stderr)


# ============================================================================
# Across-machine: socket + Marshaller
# ============================================================================
class RemoteChannel(EventChannel):
    """Across-machine Channel over an asyncio stream socket.

    Wire format per message:

        4 bytes (network-order uint32) : payload length N
        N bytes                        : JSON of Marshaller.serialize(event)

    Two ends: one constructed in 'listen' mode (server accept), one in
    'connect' mode (client connect). The EventChannelParameter factory
    handles which end is which.

    Constructed pre-connected: pass the asyncio.StreamReader and
    StreamWriter once the connection is established.
    """

    _LEN_FMT = "!I"
    _CLOSE_HEADER = struct.pack("!I", 0)                # zero-length = close

    def __init__(self, reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter):
        """RETURN: a new RemoteChannel."""
        self._reader = reader
        self._writer = writer
        self._closed = False

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("RemoteChannel.send: channel is closed")
        import json
        wire    = Marshaller.serialize(event)
        payload = json.dumps(wire).encode("utf-8")
        header  = struct.pack(self._LEN_FMT, len(payload))
        self._writer.write(header + payload)
        await self._writer.drain()

    async def receive(self) -> "Event | None":
        if self._closed:
            return None
        import json
        try:
            header = await self._reader.readexactly(4)
        except asyncio.IncompleteReadError:
            self._closed = True
            return None
        n = struct.unpack(self._LEN_FMT, header)[0]
        if n == 0:                                      # peer close signal
            self._closed = True
            return None
        try:
            payload = await self._reader.readexactly(n)
        except asyncio.IncompleteReadError:
            self._closed = True
            return None
        try:
            wire = json.loads(payload.decode("utf-8"))
        except Exception as e:
            print("RemoteChannel.receive: decode failed: %s" % e,
                  file=sys.stderr)
            return None
        return Marshaller.deserialize(wire)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.write(self._CLOSE_HEADER)
            await self._writer.drain()
        except Exception:
            pass
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass
