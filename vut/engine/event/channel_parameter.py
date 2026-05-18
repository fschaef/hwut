"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: EventChannelParameter - everything needed to construct a Channel.

ONE class, with classmethod factories per transport flavour. The flat
design is deliberate (vs. an ABC with per-transport subclasses): keeping
the API surface minimal at the cost of less type-checking inside.

USAGE

The factory creates an ECP PAIR - one for each side of the connection.
The 'A' side and 'B' side ECPs are mirror images: A's send-queue is
B's receive-queue and vice versa.

    a_ecp, b_ecp = EventChannelParameter.for_async()
    a_ecp, b_ecp = EventChannelParameter.for_thread()
    a_ecp, b_ecp = EventChannelParameter.for_process()
    a_ecp, b_ecp = EventChannelParameter.for_remote(host=..., port=...)

For PROCESS and REMOTE, the ECPs are designed to survive being passed
through the spawning mechanism (pickling for multiprocessing; manual
hand-off for remote). For ASYNC and THREAD, the ECPs are NOT passable
across a process boundary - but they do not need to be, since async
and thread spawning share memory.


TYPICAL SPAWN

    a_ecp, b_ecp = EventChannelParameter.for_process()
    proc = multiprocessing.Process(target=child_main, args=(b_ecp,))
    proc.start()
    parent_terminal = EventTerminal(a_ecp)
    # ... use parent_terminal ...

    def child_main(ecp):
        child_terminal = EventTerminal(ecp)
        child_terminal.start()
        # ... use child_terminal ...


make_channel()

EventTerminal.__init__ calls ecp.make_channel() to build the actual
EventChannel instance. The Terminal does not know which Channel type
it got - it just uses the abstract interface.
________________________________________________________________________________
"""
import asyncio
import queue as _queue
import multiprocessing

from enum        import Enum, auto

from vut.engine.event.channel import (AsyncQueueChannel,
                                      ThreadQueueChannel,
                                      ProcessQueueChannel,
                                      RemoteChannel,
                                      EventChannel)


class E_TransportKind(Enum):
    """Discriminator for EventChannelParameter."""
    ASYNC   = auto()
    THREAD  = auto()
    PROCESS = auto()
    REMOTE  = auto()


class EventChannelParameter:
    """Everything needed to construct an EventChannel.

    Single class, switched internally on .kind. The kind discriminates
    the .params dict, whose keys depend on the kind:

        ASYNC    -> { in_q:  asyncio.Queue, out_q:  asyncio.Queue }
        THREAD   -> { in_q:  queue.Queue,   out_q:  queue.Queue   }
        PROCESS  -> { in_q:  mp.Queue,      out_q:  mp.Queue      }
        REMOTE   -> { host:  str, port: int, mode:  "listen" | "connect" }

    Validation of params is done inside make_channel(), not at
    construction. The class is intentionally permissive at construction
    so that for_* factories can build it in one expression.
    """

    def __init__(self, kind: E_TransportKind, params: dict):
        """RETURN: a new EventChannelParameter.

        Direct construction is allowed but discouraged. Use the
        for_* classmethods instead.
        """
        self.kind   = kind
        self.params = params

    # ----------------------------------------------------------------
    # Factories - each returns (a_ecp, b_ecp) as mirror images.
    # ----------------------------------------------------------------

    @classmethod
    def for_async(cls) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair connected by asyncio.Queues.

        Both sides must be used on the SAME asyncio event loop.
        """
        q_ab = asyncio.Queue()                          # A sends, B receives
        q_ba = asyncio.Queue()                          # B sends, A receives
        a = cls(E_TransportKind.ASYNC, {"in_q": q_ba, "out_q": q_ab})
        b = cls(E_TransportKind.ASYNC, {"in_q": q_ab, "out_q": q_ba})
        return a, b

    @classmethod
    def for_thread(cls) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair connected by thread queues.

        One side typically lives on the asyncio loop; the other side
        on a worker thread. Both share the same Python interpreter
        memory.
        """
        q_ab = _queue.Queue()
        q_ba = _queue.Queue()
        a = cls(E_TransportKind.THREAD, {"in_q": q_ba, "out_q": q_ab})
        b = cls(E_TransportKind.THREAD, {"in_q": q_ab, "out_q": q_ba})
        return a, b

    @classmethod
    def for_process(cls) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair connected by multiprocessing.Queue.

        Either ECP may be passed (via multiprocessing args) to the
        spawned process. The ECP is picklable; the queues are picklable
        by design.
        """
        q_ab = multiprocessing.Queue()
        q_ba = multiprocessing.Queue()
        a = cls(E_TransportKind.PROCESS, {"in_q": q_ba, "out_q": q_ab})
        b = cls(E_TransportKind.PROCESS, {"in_q": q_ab, "out_q": q_ba})
        return a, b

    @classmethod
    def for_remote(cls, host: str, port: int) \
            -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair for cross-machine connection.

        a_ecp is the LISTEN end (accepts a connection on host:port);
        b_ecp is the CONNECT end (connects to host:port).

        Note: both ECPs reference the same host/port. In a real
        deployment, only the b_ecp travels to the remote machine; the
        a_ecp stays on the listening machine.

        Establishing the connection (server accept / client connect)
        happens at make_channel() time, NOT here.
        """
        a = cls(E_TransportKind.REMOTE,
                {"host": host, "port": port, "mode": "listen"})
        b = cls(E_TransportKind.REMOTE,
                {"host": host, "port": port, "mode": "connect"})
        return a, b

    # ----------------------------------------------------------------
    # Channel construction
    # ----------------------------------------------------------------

    async def make_channel(self) -> EventChannel:
        """RETURN: EventChannel, constructed from this ECP.

        Called by EventTerminal at start-up. For ASYNC, THREAD, PROCESS,
        this is synchronous in nature but presented as async for
        uniformity. For REMOTE, it performs the actual TCP accept or
        connect, which is genuinely async.
        """
        k = self.kind
        p = self.params

        if k is E_TransportKind.ASYNC:
            return AsyncQueueChannel(in_q=p["in_q"], out_q=p["out_q"])

        if k is E_TransportKind.THREAD:
            return ThreadQueueChannel(in_q=p["in_q"], out_q=p["out_q"])

        if k is E_TransportKind.PROCESS:
            return ProcessQueueChannel(in_q=p["in_q"], out_q=p["out_q"])

        if k is E_TransportKind.REMOTE:
            host = p["host"]
            port = p["port"]
            mode = p["mode"]
            if mode == "listen":
                # Wait for a single incoming connection.
                ready_q: asyncio.Queue = asyncio.Queue(maxsize=1)
                async def _on_conn(reader, writer):
                    await ready_q.put((reader, writer))
                server = await asyncio.start_server(_on_conn, host, port)
                reader, writer = await ready_q.get()
                server.close()
                await server.wait_closed()
                return RemoteChannel(reader=reader, writer=writer)
            elif mode == "connect":
                reader, writer = await asyncio.open_connection(host, port)
                return RemoteChannel(reader=reader, writer=writer)
            raise ValueError("EventChannelParameter: unknown remote mode %r" % mode)

        raise ValueError("EventChannelParameter: unknown kind %r" % k)
