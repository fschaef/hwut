"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Bidirectional point-to-point conduit for Events.

An EventChannel is the wire between two EventTerminals. Each end is one
Terminal; one Channel connects exactly two Terminals. The Channel hides
the underlying transport (asyncio queue, thread queue, multiprocessing
queue, network socket) behind a uniform async interface.


ABC SHAPE

    async send(event)        -- ship an Event to the peer
    async receive()          -- await one Event from the peer
                               returns None if the Channel has closed
    async close()            -- close this end; peer detects via receive()

Channels are BIDIRECTIONAL. The same Channel object supports both
.send() and .receive(); the two directions are independent.

The interface is async even for synchronous transports. Concrete
subclasses for blocking transports (multiprocessing.Queue, sockets)
wrap blocking calls in loop.run_in_executor(). This lets every Channel
be used in an asyncio receive loop uniformly.


CONCRETE CHANNELS

    AsyncChannel       in-process; pair of asyncio.Queue
    ThreadChannel      in-process; pair of queue.Queue
    ProcessChannel     across-process; pair of multiprocessing.Queue;
                            uses Marshaller for serialisation
    RemoteChannel           across-machine; socket; uses Marshaller


SERIALISATION

Channels that cross a Python interpreter boundary (Process, Remote)
serialise via Marshaller. Local channels (AsyncQueue, ThreadQueue)
do not serialise; they ship Event instances directly.

This is invisible at the Channel interface. Callers send and receive
Event instances regardless of channel type.


ENCRYPTION

The serialising channels (Process, Remote) carry a Cipher (see
cipher.py). The Cipher transforms the serialised byte payload on send
(encrypt) and receive (decrypt). The default is IdentityCipher - a
pass-through, no encryption. A non-identity Cipher is configured via
the EventChannelParameter; the Channel runs cipher.handshake() during
its own connect, BEFORE it is handed up to the Terminal, so the
Cipher is fully established before any Event crosses the wire.

In-process channels (AsyncQueue, ThreadQueue) never serialise and
have no bytes to encrypt; they do not carry a Cipher.


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

from abc                import ABC, abstractmethod

from vut.engine.event.event              import Event
from vut.engine.event.channel.marshaller import Marshaller
from vut.engine.event.channel.cipher     import Cipher, IdentityCipher


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

class AsyncChannel(EventChannel):
    """In-process Channel over a pair of asyncio.Queues.

    Sends and receives in the same event loop. No serialisation;
    Event instances are passed by reference.

    Constructed with the queue used for SENDING (out_q) and the queue
    used for RECEIVING (in_q). The PEER's queues are flipped: peer's
    out_q is this side's in_q and vice versa.
    """

    _CLOSE_SENTINEL = object()                          # placed on in_q on close

    def __init__(self, in_q: asyncio.Queue, out_q: asyncio.Queue):
        """RETURN: a new AsyncChannel."""
        self._in_q   = in_q
        self._out_q  = out_q
        self._closed = False

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("AsyncChannel.send: channel is closed")
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

class ThreadChannel(EventChannel):
    """In-process Channel over a pair of thread-safe queue.Queue objects.

    Used when the peer is on a worker thread (not on the asyncio loop).
    Sends are non-blocking put_nowait; receives use run_in_executor()
    to wrap the blocking queue.Queue.get() so the asyncio loop is not
    blocked.
    """

    _CLOSE_SENTINEL = object()

    def __init__(self, in_q: _queue.Queue, out_q: _queue.Queue):
        """RETURN: a new ThreadChannel."""
        self._in_q   = in_q
        self._out_q  = out_q
        self._closed = False

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("ThreadChannel.send: channel is closed")
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

class ProcessChannel(EventChannel):
    """Across-process Channel over a pair of multiprocessing.Queue.

    Events are serialised via Marshaller before send and deserialised
    after receive. The wire form depends on whether a Cipher is
    active:

      -- IdentityCipher (default): the Marshaller wire dict is put on
         the queue directly (picklable dict, as before).
      -- a real Cipher: the wire dict is JSON-encoded to bytes,
         encrypted, and the resulting bytes are put on the queue.

    The Cipher, if any, is established via connect() before the
    channel is used.
    """

    _CLOSE_SENTINEL = {"_close": True}                  # picklable dict
    _POLL_TIMEOUT_S = 0.3                               # receive() wake period

    def __init__(self, in_q, out_q, cipher: "Cipher | None" = None):
        """RETURN: a new ProcessChannel.

        in_q and out_q must be multiprocessing.Queue (or compatible
        picklable queue objects). cipher defaults to IdentityCipher.
        """
        self._in_q   = in_q
        self._out_q  = out_q
        self._closed = False
        self._cipher = cipher if cipher is not None else IdentityCipher()

    async def connect(self) -> None:
        """RETURN: None,  once the Cipher handshake (if any) has completed.

        Runs cipher.handshake() over raw queue primitives. For
        IdentityCipher this is a no-op. Called by the ECP's
        make_channel() before the channel is handed to the Terminal.
        """
        await self._cipher.handshake(self._raw_send, self._raw_recv)

    async def _raw_send(self, b: bytes) -> None:
        """RETURN: None.  Put raw handshake bytes on the out queue."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._out_q.put, b)

    async def _raw_recv(self) -> bytes:
        """RETURN: bytes,  raw handshake bytes from the in queue.

        Used only during the pre-channel cipher handshake; a blocking
        get() is acceptable here because the handshake either completes
        or the spawn fails outright.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._in_q.get)

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("ProcessChannel.send: channel is closed")
        wire = Marshaller.serialize(event)
        loop = asyncio.get_running_loop()
        if isinstance(self._cipher, IdentityCipher):
            # Fast path: put the picklable dict directly.
            await loop.run_in_executor(None, self._out_q.put, wire)
        else:
            import json
            payload = self._cipher.encrypt(json.dumps(wire).encode("utf-8"))
            await loop.run_in_executor(None, self._out_q.put, payload)

    def _get_one(self):
        """RETURN: a queue item, or the _CLOSE_SENTINEL if none arrived.

        A SINGLE bounded get() on the in queue. Runs on an executor
        thread. The timeout is the key to clean shutdown: a blocking,
        unbounded get() would park the executor thread forever if the
        peer process died abnormally (closing a multiprocessing.Queue
        does NOT wake a thread blocked in get()), and that parked
        non-daemon thread would hang interpreter exit. A bounded get()
        instead returns control every _POLL_TIMEOUT_S so receive() can
        observe a closed channel and stop.

        On timeout it returns _CLOSE_SENTINEL-shaped emptiness: the
        caller re-checks _closed and either loops or stops.
        """
        try:
            return self._in_q.get(timeout=self._POLL_TIMEOUT_S)
        except _queue.Empty:
            return None                                 # nothing this tick
        except (OSError, ValueError, EOFError):
            # Queue closed / broken - peer is gone. Treat as channel end.
            return self._CLOSE_SENTINEL

    async def receive(self) -> "Event | None":
        """RETURN: Event,  the next event from the peer, or
                   None,   once the channel has closed (locally via
                           close(), by a peer _CLOSE_SENTINEL, or
                           because the peer's queue broke).

        Polls the in queue in bounded get() ticks (see _get_one) so the
        executor thread cannot be left parked on a dead peer. Between
        ticks it re-checks _closed, so a local close() ends the loop
        promptly without needing the sentinel to race the poll.
        """
        loop = asyncio.get_running_loop()
        while not self._closed:
            item = await loop.run_in_executor(None, self._get_one)
            if item is None:
                continue                                # empty tick; re-check
            if isinstance(item, dict) and item.get("_close"):
                self._closed = True
                return None
            if isinstance(item, dict):
                # Identity-cipher fast path: item IS the wire dict.
                return Marshaller.deserialize(item)
            # Encrypted path: item is bytes.
            try:
                import json
                wire = json.loads(
                    self._cipher.decrypt(item).decode("utf-8"))
            except Exception as e:
                print("ProcessChannel.receive: decrypt/decode failed: %s"
                      % e, file=sys.stderr)
                return None
            return Marshaller.deserialize(wire)
        return None                                     # channel closed

    async def close(self) -> None:
        """RETURN: None.

        Closes this end. Sets _closed (so an in-flight receive() poll
        loop exits at its next tick - at most _POLL_TIMEOUT_S away),
        puts a _CLOSE_SENTINEL on the in queue to wake the peer
        promptly, and cancel_join_thread()s both queues so their feeder
        threads cannot hold interpreter exit open.

        Idempotent: a second call returns at once.
        """
        if self._closed:
            return
        self._closed = True
        try:
            self._in_q.put_nowait(self._CLOSE_SENTINEL)
        except Exception as e:
            print("ProcessChannel.close: put_nowait failed: %s" % e,
                  file=sys.stderr)
        # Release the queues' feeder threads so they cannot block exit.
        for q in (self._in_q, self._out_q):
            cancel = getattr(q, "cancel_join_thread", None)
            if cancel is not None:
                try:
                    cancel()
                except Exception:
                    pass


# ============================================================================
# Across-machine: socket + Marshaller
# ============================================================================

class RemoteChannel(EventChannel):
    """Across-machine Channel over an asyncio stream socket.

    Wire format per message:

        4 bytes (network-order uint32) : payload length N
        N bytes                        : payload

    The payload is JSON of Marshaller.serialize(event), optionally
    encrypted by the Cipher. With IdentityCipher the payload is the
    JSON bytes directly; with a real Cipher it is the encrypted form.

    Two ends: one constructed in 'listen' mode (server accept), one in
    'connect' mode (client connect). The EventChannelParameter factory
    handles which end is which.

    Constructed pre-connected: pass the asyncio.StreamReader and
    StreamWriter once the connection is established.
    """

    _LEN_FMT = "!I"
    _CLOSE_HEADER = struct.pack("!I", 0)                # zero-length = close

    def __init__(self, reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter,
                       cipher: "Cipher | None" = None):
        """RETURN: a new RemoteChannel.

        cipher defaults to IdentityCipher (no encryption).
        """
        self._reader = reader
        self._writer = writer
        self._closed = False
        self._cipher = cipher if cipher is not None else IdentityCipher()

    async def connect(self) -> None:
        """RETURN: None,  once the Cipher handshake (if any) has completed.

        Runs cipher.handshake() over length-prefixed raw frames. For
        IdentityCipher this is a no-op. Called by the ECP's
        make_channel() before the channel is handed to the Terminal.
        """
        await self._cipher.handshake(self._raw_send, self._raw_recv)

    async def _raw_send(self, b: bytes) -> None:
        """RETURN: None.  Send one length-prefixed raw frame."""
        self._writer.write(struct.pack(self._LEN_FMT, len(b)) + b)
        await self._writer.drain()

    async def _raw_recv(self) -> bytes:
        """RETURN: bytes,  one length-prefixed raw frame."""
        header = await self._reader.readexactly(4)
        n      = struct.unpack(self._LEN_FMT, header)[0]
        if n == 0:
            return b""
        return await self._reader.readexactly(n)

    async def send(self, event: Event) -> None:
        if self._closed:
            raise RuntimeError("RemoteChannel.send: channel is closed")
        import json
        wire    = Marshaller.serialize(event)
        payload = self._cipher.encrypt(json.dumps(wire).encode("utf-8"))
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
            plaintext = self._cipher.decrypt(payload)
            wire      = json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            print("RemoteChannel.receive: decrypt/decode failed: %s" % e,
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
