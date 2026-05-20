#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the EventRouter.

CHOICES: predicate_routing, source_filter, remove, peer_down_removes;

DESCRIPTION:

The Router holds N Terminals and uses an internal Dispatcher to route
each published Event to those Terminals whose predicate matches. The
optional source_terminal_list restricts routing based on the
originating Terminal. When a Terminal's peer sends Down, the Router
auto-removes that entry.

    predicate_routing    multiple Terminals each with a different
                         predicate; publish() sends each event to
                         only the matching destinations.

    source_filter        Events tagged with a source Terminal are
                         only delivered to destinations whose
                         source_terminal_list permits that source.

    remove               remove_entry() detaches a Terminal; subsequent
                         publish() does not deliver to it. remove_entry
                         of a stale handle returns False.

    peer_down_removes    when a Terminal's peer sends EventTerminalDown,
                         the router auto-removes the entry.
______________________________________________________________________________
"""
import asyncio
import sys
import config                                                       # noqa: F401

from dataclasses                                import dataclass
from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (Event,
                                                        category,
                                                        EventChannelParameter,
                                                        EventTerminal,
                                                        EventRouter)


# Test-local events in two categories so the predicate-routing test
# can discriminate by category.
with category("TEST_LOCAL_ROUTER_TASK"):

    @dataclass(frozen=True, kw_only=True)
    class EventTaskStarted(Event):
        task_id: int

    @dataclass(frozen=True, kw_only=True)
    class EventTaskDone(Event):
        task_id:    int
        duration_s: float


with category("TEST_LOCAL_ROUTER_COMPILE"):

    @dataclass(frozen=True, kw_only=True)
    class EventCompilerDone(EventTaskDone):
        source: str
        output: str


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _setup_destination_terminal():
    """RETURN: (router_side_terminal, peer_terminal, seen_list).

    Builds an async-pair, starts both sides concurrently (handshake
    blocks each start), returns the router-facing terminal, the peer,
    and the seen list.
    """
    a_ecp, b_ecp = EventChannelParameter.for_async()
    router_side = EventTerminal(a_ecp)
    peer        = EventTerminal(b_ecp)

    seen = []
    async def handler(ev):
        seen.append((type(ev).__name__, ev.task_id))
    peer.dispatcher.subscribe_on_predicate(lambda ev: True, handler)

    await asyncio.gather(router_side.start(), peer.start())
    return router_side, peer, seen


async def _predicate_routing():
    """RETURN: None. Multiple Terminals, each with a different predicate."""
    router = EventRouter()

    t1, p1, seen1 = await _setup_destination_terminal()
    t2, p2, seen2 = await _setup_destination_terminal()
    t3, p3, seen3 = await _setup_destination_terminal()

    router.add_entry(lambda ev: ev.category == "TEST_LOCAL_ROUTER_TASK",     t1)
    router.add_entry(lambda ev: ev.category == "TEST_LOCAL_ROUTER_COMPILE",  t2)
    router.add_entry(lambda ev: ev.task_id == 42,                            t3)

    banner("router has 3 entries")
    print("len(router): %d" % len(router))

    banner("publish three events; each lands on the matching Terminals")
    router.publish(EventTaskDone(task_id=1, duration_s=1.0))          # TASK only -> t1
    router.publish(EventCompilerDone(task_id=42, source="x",          # COMPILE + 42 -> t2, t3
                                     output="y", duration_s=1.0))
    router.publish(EventTaskStarted(task_id=42))                      # TASK + 42 -> t1, t3

    await asyncio.sleep(0.1)
    print("seen1 (TASK)   : %s" % seen1)
    print("seen2 (COMPILE): %s" % seen2)
    print("seen3 (id=42)  : %s" % seen3)

    await asyncio.gather(*(t.stop() for t in (t1, p1, t2, p2, t3, p3)))


async def _source_filter():
    """RETURN: None. source_terminal_list restricts deliveries by origin."""
    router = EventRouter()

    t_out_x, p_x, seen_x = await _setup_destination_terminal()
    t_out_y, p_y, seen_y = await _setup_destination_terminal()

    # Sentinel "source terminal" references for publish_from().
    class FakeSource: pass
    source_alpha = FakeSource()
    source_beta  = FakeSource()

    router.add_entry(
        predicate            = lambda ev: True,
        terminal             = t_out_x,
        source_terminal_list = [source_alpha, None],
    )
    router.add_entry(
        predicate            = lambda ev: True,
        terminal             = t_out_y,
        source_terminal_list = [source_beta],
    )

    banner("publish from source_alpha: lands on t_out_x only")
    router.publish_from(source_alpha, EventTaskDone(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.05)
    print("seen_x: %s" % seen_x)
    print("seen_y: %s" % seen_y)

    banner("publish from source_beta: lands on t_out_y only")
    router.publish_from(source_beta, EventTaskStarted(task_id=2))
    await asyncio.sleep(0.05)
    print("seen_x: %s" % seen_x)
    print("seen_y: %s" % seen_y)

    banner("local publish (source=None): lands on t_out_x only (None in its list)")
    router.publish(EventTaskDone(task_id=3, duration_s=3.0))
    await asyncio.sleep(0.05)
    print("seen_x: %s" % seen_x)
    print("seen_y: %s" % seen_y)

    await asyncio.gather(*(t.stop() for t in (t_out_x, p_x, t_out_y, p_y)))


async def _remove():
    """RETURN: None. remove_entry() detaches; stale handle returns False."""
    router = EventRouter()

    t1, p1, seen1 = await _setup_destination_terminal()

    handle = router.add_entry(lambda ev: True, t1)
    print("len after add: %d" % len(router))

    banner("publish before remove")
    router.publish(EventTaskDone(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.05)
    print("seen1: %s" % seen1)

    banner("remove_entry returns True")
    print("removed: %s" % router.remove_entry(handle))
    print("len after remove: %d" % len(router))

    banner("publish after remove: nothing delivered")
    router.publish(EventTaskDone(task_id=2, duration_s=2.0))
    await asyncio.sleep(0.05)
    print("seen1: %s" % seen1)

    banner("remove of stale handle returns False")
    print("removed again: %s" % router.remove_entry(handle))

    await asyncio.gather(t1.stop(), p1.stop())


async def _peer_down_removes():
    """RETURN: None.

    When a Terminal's peer sends EventTerminalDown (its peer terminal
    calls stop()), the router auto-removes that entry.
    """
    router = EventRouter()

    t1, p1, seen1 = await _setup_destination_terminal()
    t2, p2, seen2 = await _setup_destination_terminal()

    router.add_entry(lambda ev: True, t1)
    router.add_entry(lambda ev: True, t2)

    banner("router has 2 entries; publish reaches both peers")
    router.publish(EventTaskDone(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.05)
    print("seen1: %s" % seen1)
    print("seen2: %s" % seen2)
    print("len(router): %d" % len(router))

    banner("peer p1 stops; t1's entry is auto-removed by the router")
    await p1.stop()
    await asyncio.sleep(0.05)
    print("len(router): %d  (1 expected)" % len(router))

    banner("further publish reaches only the surviving peer")
    router.publish(EventTaskDone(task_id=2, duration_s=2.0))
    await asyncio.sleep(0.05)
    print("seen1: %s  (unchanged)" % seen1)
    print("seen2: %s" % seen2)

    await asyncio.gather(t1.stop(), t2.stop(), p2.stop())


def run_predicate_routing():  asyncio.run(_predicate_routing())
def run_source_filter():      asyncio.run(_source_filter())
def run_remove():             asyncio.run(_remove())
def run_peer_down_removes():  asyncio.run(_peer_down_removes())


HwutRunner(
    argv       = sys.argv,
    title      = "EventRouter",
    choice_map = {
        "predicate_routing":  run_predicate_routing,
        "source_filter":      run_source_filter,
        "remove":             run_remove,
        "peer_down_removes":  run_peer_down_removes,
    },
).run()
