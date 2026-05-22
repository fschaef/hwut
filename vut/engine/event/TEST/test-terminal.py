#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the EventTerminal.

CHOICES: pair, dispatch_to_local, handshake, stop, context_manager;

DESCRIPTION:

A Terminal owns one Channel and one receive-side Dispatcher.
start() now blocks until the symmetric Up handshake completes -
each side sends EventTerminalUp on receive-loop entry and waits
for the peer's Up. start() returns only when state == UP.

    pair                two Terminals connected by an async ECP pair;
                        events sent on one are received-and-dispatched
                        on the other. Both starts run concurrently
                        (gather) because each blocks on peer Up.

    dispatch_to_local   the receive-side Dispatcher fires local
                        callbacks for each incoming event, filtered by
                        category subscription.

    handshake           start() blocks; state transitions NEW ->
                        UP_PENDING -> UP; EVENT_INFRA events are NOT
                        seen by the local dispatcher.

    stop                stop() sends EventTerminalDown to the peer,
                        ends the receive loop, closes the channel.
                        Further sends raise RuntimeError. The peer
                        sees Down via its peer-down callback.

    context_manager     async with EventTerminal(ecp) as t:
                        runs start() on enter and stop() on exit,
                        also on exception.
______________________________________________________________________________
"""
import asyncio
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (Event,
                                                        category,
                                                        EventChannelParameter,
                                                        EventTerminal,
                                                        EventTerminalUp,
                                                        EventTerminalDown)


# Test-local event vocabulary in two categories so subscribe_on_category
# discriminates between them.
with category("TEST_LOCAL_TERM_TASK"):

    class EventTaskStarted(Event):
        task_id: int

    class EventTaskDone(Event):
        task_id:    int
        duration_s: float


with category("TEST_LOCAL_TERM_COMPILE"):

    class EventCompilerDone(EventTaskDone):
        source: str
        output: str


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _pair():
    """RETURN: None. Two Terminals connected via async ECP pair."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    a_seen = []
    b_seen = []
    async def a_handler(ev):
        a_seen.append(("a", type(ev).__name__, ev.task_id))
    async def b_handler(ev):
        b_seen.append(("b", type(ev).__name__, ev.task_id))

    a.dispatcher.subscribe_on_predicate(lambda ev: True, a_handler)
    b.dispatcher.subscribe_on_predicate(lambda ev: True, b_handler)

    # Concurrent start: each blocks on the peer's Up.
    await asyncio.gather(a.start(), b.start())

    banner("send a few events both directions")
    await a.send(EventTaskDone(task_id=1, duration_s=1.0, timestamp=10.0))
    await b.send(EventTaskStarted(task_id=2, timestamp=20.0))
    await a.send(EventCompilerDone(task_id=3, source="x.c",
                                   output="x.o", duration_s=0.5,
                                   timestamp=30.0))

    await asyncio.sleep(0.05)
    print("a_seen: %s" % a_seen)
    print("b_seen: %s" % b_seen)

    await asyncio.gather(a.stop(), b.stop())


async def _dispatch_to_local():
    """RETURN: None. Receive-side dispatcher fires callbacks by category."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    task_seen    = []
    compile_seen = []

    async def on_task(ev):
        task_seen.append(type(ev).__name__)
    async def on_compile(ev):
        compile_seen.append(type(ev).__name__)

    b.dispatcher.subscribe_on_category("TEST_LOCAL_TERM_TASK",    on_task)
    b.dispatcher.subscribe_on_category("TEST_LOCAL_TERM_COMPILE", on_compile)

    await asyncio.gather(a.start(), b.start())

    banner("send TASK and COMPILE events; each fires the right handler")
    await a.send(EventTaskDone(task_id=1, duration_s=1.0, timestamp=10.0))
    await a.send(EventCompilerDone(task_id=2, source="x.c",
                                   output="x.o", duration_s=0.5,
                                   timestamp=20.0))
    await a.send(EventTaskStarted(task_id=3, timestamp=30.0))

    await asyncio.sleep(0.05)
    print("task_seen:    %s" % task_seen)
    print("compile_seen: %s" % compile_seen)

    await asyncio.gather(a.stop(), b.stop())


async def _handshake():
    """RETURN: None. The handshake protocol step by step."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    banner("initial state")
    print("a.state: %s   b.state: %s" % (a.state, b.state))
    print("a.is_up: %s   b.is_up: %s" % (a.is_up, b.is_up))

    banner("subscribe to EVENT_INFRA events on local dispatcher")
    # These should NOT fire - infra events are handled internally.
    infra_seen = []
    async def cb(ev):
        infra_seen.append(type(ev).__name__)
    a.dispatcher.subscribe_on_event(EventTerminalUp,   cb)
    a.dispatcher.subscribe_on_event(EventTerminalDown, cb)

    banner("start both terminals concurrently; both block until peer Up")
    await asyncio.gather(a.start(), b.start())
    print("a.state: %s   b.state: %s" % (a.state, b.state))

    banner("local dispatcher saw infra events?")
    print("infra_seen: %s   (expected empty)" % infra_seen)

    await asyncio.gather(a.stop(), b.stop())


async def _stop():
    """RETURN: None. stop() sends Down; peer sees it via callback."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    peer_down_seen = []
    b.set_peer_down_callback(lambda: peer_down_seen.append("b saw peer Down"))

    await asyncio.gather(a.start(), b.start())

    banner("send before stop works")
    await a.send(EventTaskDone(task_id=1, duration_s=1.0, timestamp=10.0))
    await asyncio.sleep(0.01)

    banner("stop A; B's peer-down callback fires")
    await a.stop()
    await asyncio.sleep(0.05)
    print("a.state: %s" % a.state)
    print("b.state after peer Down: %s" % b.state)
    print("peer_down_seen: %s" % peer_down_seen)

    banner("send after stop raises")
    verdict = await a.send(EventTaskDone(task_id=2, duration_s=2.0))
    if verdict:
        print("UNEXPECTED: send succeeded")
    else:
        print("Send failed (expected)")

    banner("stop is idempotent")
    await a.stop()
    print("second stop returned cleanly")

    await b.stop()


async def _context_manager():
    """RETURN: None. async-with form drives start() / stop()."""
    a_ecp, b_ecp = EventChannelParameter.for_async()

    a_seen = []

    async def side_a():
        async with EventTerminal(a_ecp) as t:
            async def cb(ev):
                a_seen.append(type(ev).__name__)
            t.dispatcher.subscribe_on_event(EventTaskDone, cb)
            # Capture state while definitely inside the with block,
            # before either side has shut down.
            state_now = t.state
            # Wait briefly for b to send its event.
            await asyncio.sleep(0.05)
            return state_now

    async def side_b():
        async with EventTerminal(b_ecp) as t:
            state_now = t.state
            await t.send(EventTaskDone(task_id=1, duration_s=1.0))
            await asyncio.sleep(0.05)
            return state_now

    banner("normal context-manager use")
    a_state_inside, b_state_inside = await asyncio.gather(side_a(), side_b())
    print("a got: %s" % a_seen)
    print("a.state inside with: %s" % a_state_inside)
    print("b.state inside with: %s" % b_state_inside)

    banner("exit on exception still calls stop()")
    a_ecp2, b_ecp2 = EventChannelParameter.for_async()

    async def side_a_raises():
        async with EventTerminal(a_ecp2) as t:
            # Establish, then raise inside the block.
            raise ValueError("test-induced failure")

    async def side_b_simple():
        async with EventTerminal(b_ecp2) as t:
            await asyncio.sleep(0.1)
            return t.state

    try:
        await asyncio.gather(side_a_raises(), side_b_simple())
    except ValueError as e:
        print("ValueError propagated out of async-with (expected): %s" % e)


def run_pair():               asyncio.run(_pair())
def run_dispatch_to_local():  asyncio.run(_dispatch_to_local())
def run_handshake():          asyncio.run(_handshake())
def run_stop():               asyncio.run(_stop())
def run_context_manager():    asyncio.run(_context_manager())


HwutRunner(
    argv       = sys.argv,
    title      = "EventTerminal",
    choice_map = {
        "pair":              run_pair,
        "dispatch_to_local": run_dispatch_to_local,
        "handshake":         run_handshake,
        "stop":              run_stop,
        "context_manager":   run_context_manager,
    },
).run()
