#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the EventChannel implementations.

CHOICES: async, thread, process, close;

DESCRIPTION:

EventChannel is bidirectional. For each concrete subclass, verify a
basic send/receive round-trip between two ends of a pair. Then verify
that close() properly signals end-of-stream to the peer (receive returns
None).

    async           AsyncChannel pair, both sides on the same loop.
    thread          ThreadChannel pair, blocking get wrapped via
                    run_in_executor.
    process         ProcessChannel pair WITHOUT spawning a process
                    (we exercise the channel from two coroutines that
                    share the same multiprocessing.Queue pair; this
                    tests the serialise/deserialise path).
    close           close() on one end causes receive() on the other
                    to return None.

We do NOT test RemoteChannel here - it requires a TCP socket pair and
real network I/O, which complicates the test for limited additional
coverage. The wire format is exercised indirectly via Marshaller tests.
______________________________________________________________________________
"""
import asyncio
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (Event,
                                                        category,
                                                        EventChannelParameter)


# Test-local event vocabulary.
with category("TEST_LOCAL_CHANNEL"):

    class EventTaskDone(Event):
        task_id:    int
        duration_s: float

    class EventCompilerDone(EventTaskDone):
        source: str
        output: str


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _async():
    """RETURN: None. AsyncChannel pair, basic round-trip."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a_ch = await a_ecp.make_channel()
    b_ch = await b_ecp.make_channel()

    banner("A sends, B receives")
    await a_ch.send(EventTaskDone(task_id=1, duration_s=1.0, timestamp=10.0))
    ev = await b_ch.receive()
    print("type:        %s" % type(ev).__name__)
    print("task_id:     %d" % ev.task_id)
    print("duration_s:  %s" % ev.duration_s)
    print("timestamp:   %s" % ev.timestamp)

    banner("B sends, A receives (bidirectional)")
    await b_ch.send(EventCompilerDone(task_id=2, source="a.c",
                                      output="a.o", duration_s=0.5,
                                      timestamp=20.0))
    ev = await a_ch.receive()
    print("type:        %s" % type(ev).__name__)
    print("source:      %s" % ev.source)

    await a_ch.close()
    await b_ch.close()


async def _thread():
    """RETURN: None. ThreadChannel pair, used between two coroutines
    on the same loop (since we don't actually spawn a thread here -
    that's what the Terminal test does)."""
    a_ecp, b_ecp = EventChannelParameter.for_thread()
    a_ch = await a_ecp.make_channel()
    b_ch = await b_ecp.make_channel()

    banner("A sends, B receives via thread queue")
    await a_ch.send(EventTaskDone(task_id=42, duration_s=2.0, timestamp=10.0))
    ev = await b_ch.receive()
    print("type:        %s" % type(ev).__name__)
    print("task_id:     %d" % ev.task_id)

    await a_ch.close()
    await b_ch.close()


async def _process():
    """RETURN: None. ProcessChannel pair WITHOUT spawning a child
    process. The serialise/deserialise path goes through Marshaller."""
    a_ecp, b_ecp = EventChannelParameter.for_process()
    a_ch = await a_ecp.make_channel()
    b_ch = await b_ecp.make_channel()

    banner("A sends, B receives via mp.Queue with Marshaller wire format")
    sent = EventTaskDone(task_id=99, duration_s=3.5, timestamp=10.0)
    await a_ch.send(sent)
    ev = await b_ch.receive()
    print("type:        %s" % type(ev).__name__)
    print("task_id:     %d" % ev.task_id)
    print("duration_s:  %s" % ev.duration_s)
    print("type matches: %s" % (type(ev) is EventTaskDone))

    await a_ch.close()
    await b_ch.close()


async def _close():
    """RETURN: None. close() on one end -> receive() returns None on
    the same end (close signals end of receive)."""
    banner("AsyncChannel: close() -> receive() returns None")
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a_ch = await a_ecp.make_channel()
    b_ch = await b_ecp.make_channel()

    # Initiate a receive then close.
    recv_task = asyncio.create_task(b_ch.receive())
    await asyncio.sleep(0.01)             # ensure receive is awaiting
    await b_ch.close()
    result = await recv_task
    print("result: %s" % result)

    banner("send on closed channel raises RuntimeError")
    try:
        await b_ch.send(EventTaskDone(task_id=1, duration_s=1.0))
        print("UNEXPECTED: send succeeded")
    except RuntimeError:
        print("RuntimeError raised (expected)")
    await a_ch.close()


def run_async():    asyncio.run(_async())
def run_thread():   asyncio.run(_thread())
def run_process():  asyncio.run(_process())
def run_close():    asyncio.run(_close())


HwutRunner(
    argv       = sys.argv,
    title      = "EventChannel implementations",
    choice_map = {
        "async":   run_async,
        "thread":  run_thread,
        "process": run_process,
        "close":   run_close,
    },
).run()
