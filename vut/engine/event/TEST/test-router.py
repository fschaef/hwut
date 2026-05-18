#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the EventRouter.

CHOICES: predicate_routing, source_filter, remove;

DESCRIPTION:

The Router holds N Terminals and uses an internal Dispatcher to route
each published Event to those Terminals whose predicate matches. The
optional source_terminal_list restricts routing based on the
originating Terminal.

    predicate_routing    multiple Terminals each with a different
                         predicate; publish() sends each event to
                         only the matching destinations.

    source_filter        Events tagged with a source Terminal are
                         only delivered to destinations whose
                         source_terminal_list permits that source.
                         This prevents loops when forwarding.

    remove               remove_terminal() detaches a Terminal;
                         subsequent publish() does not deliver to it.
                         remove_terminal of a stale handle returns False.
______________________________________________________________________________
"""
import asyncio
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (E_EventCategory,
                                                        TaskStartedEvent,
                                                        TaskDoneEvent,
                                                        CompilerDoneEvent,
                                                        EventChannelParameter,
                                                        EventTerminal,
                                                        EventRouter)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _setup_destination_terminal():
    """RETURN: (router_side_terminal, peer_terminal, seen_list).

    Builds an async-pair, starts both sides, returns the
    router-facing terminal (the one we add to the router) and the
    peer terminal (the one we observe receives at). seen_list
    collects (event_type, task_id) tuples as events arrive at peer.
    """
    a_ecp, b_ecp = EventChannelParameter.for_async()
    router_side = EventTerminal(a_ecp)
    peer        = EventTerminal(b_ecp)

    seen = []
    async def handler(ev):
        seen.append((type(ev).__name__, ev.task_id))
    peer.dispatcher.subscribe_on_predicate(lambda ev: True, handler)

    await router_side.start()
    await peer.start()
    return router_side, peer, seen


async def _predicate_routing():
    """RETURN: None. Multiple Terminals, each with a different predicate."""
    router = EventRouter()

    t1, p1, seen1 = await _setup_destination_terminal()
    t2, p2, seen2 = await _setup_destination_terminal()
    t3, p3, seen3 = await _setup_destination_terminal()

    router.add_terminal(lambda ev: ev.category == E_EventCategory.WORKFLOW,    t1)
    router.add_terminal(lambda ev: ev.category == E_EventCategory.COMPILATION, t2)
    router.add_terminal(lambda ev: ev.task_id == 42,                            t3)

    banner("router has 3 entries")
    print("len(router): %d" % len(router))

    banner("publish three events; each lands on the matching Terminals")
    router.publish(TaskDoneEvent(task_id=1, duration_s=1.0))   # WORKFLOW only -> t1
    router.publish(CompilerDoneEvent(task_id=42, source="x",   # COMPILATION + task_id=42 -> t2, t3
                                     output="y", duration_s=1.0))
    router.publish(TaskStartedEvent(task_id=42))               # WORKFLOW + task_id=42 -> t1, t3

    await asyncio.sleep(0.1)
    print("seen1 (WORKFLOW)   : %s" % seen1)
    print("seen2 (COMPILATION): %s" % seen2)
    print("seen3 (task_id=42) : %s" % seen3)

    for t in (t1, p1, t2, p2, t3, p3):
        await t.stop()


async def _source_filter():
    """RETURN: None. source_terminal_list restricts deliveries by origin."""
    router = EventRouter()

    t_out_x, p_x, seen_x = await _setup_destination_terminal()
    t_out_y, p_y, seen_y = await _setup_destination_terminal()

    # A "fake" source terminal: just a sentinel reference. The router
    # doesn't actually receive from it here; we use publish_from() to
    # simulate originating from it.
    class FakeSource: pass
    source_alpha = FakeSource()
    source_beta  = FakeSource()

    # t_out_x receives events from source_alpha OR locally; never from beta.
    router.add_terminal(
        predicate            = lambda ev: True,
        terminal             = t_out_x,
        source_terminal_list = [source_alpha, None],
    )
    # t_out_y receives only events from source_beta.
    router.add_terminal(
        predicate            = lambda ev: True,
        terminal             = t_out_y,
        source_terminal_list = [source_beta],
    )

    banner("publish from source_alpha: lands on t_out_x only")
    router.publish_from(source_alpha, TaskDoneEvent(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.05)
    print("seen_x: %s" % seen_x)
    print("seen_y: %s" % seen_y)

    banner("publish from source_beta: lands on t_out_y only")
    router.publish_from(source_beta, TaskStartedEvent(task_id=2))
    await asyncio.sleep(0.05)
    print("seen_x: %s" % seen_x)
    print("seen_y: %s" % seen_y)

    banner("local publish (source=None): lands on t_out_x only (None in its list)")
    router.publish(TaskDoneEvent(task_id=3, duration_s=3.0))
    await asyncio.sleep(0.05)
    print("seen_x: %s" % seen_x)
    print("seen_y: %s" % seen_y)

    for t in (t_out_x, p_x, t_out_y, p_y):
        await t.stop()


async def _remove():
    """RETURN: None. remove_terminal() detaches; stale handle returns False."""
    router = EventRouter()

    t1, p1, seen1 = await _setup_destination_terminal()

    handle = router.add_terminal(lambda ev: True, t1)
    print("len after add: %d" % len(router))

    banner("publish before remove")
    router.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.05)
    print("seen1: %s" % seen1)

    banner("remove_terminal returns True")
    print("removed: %s" % router.remove_terminal(handle))
    print("len after remove: %d" % len(router))

    banner("publish after remove: nothing delivered")
    router.publish(TaskDoneEvent(task_id=2, duration_s=2.0))
    await asyncio.sleep(0.05)
    print("seen1: %s" % seen1)

    banner("remove of stale handle returns False")
    print("removed again: %s" % router.remove_terminal(handle))

    await t1.stop()
    await p1.stop()


def run_predicate_routing():  asyncio.run(_predicate_routing())
def run_source_filter():      asyncio.run(_source_filter())
def run_remove():             asyncio.run(_remove())


HwutRunner(
    argv       = sys.argv,
    title      = "EventRouter",
    choice_map = {
        "predicate_routing": run_predicate_routing,
        "source_filter":     run_source_filter,
        "remove":             run_remove,
    },
).run()
