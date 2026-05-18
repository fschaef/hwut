#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the EventTerminal.

CHOICES: pair, dispatch_to_local, stop;

DESCRIPTION:

A Terminal owns one Channel and one receive-side Dispatcher. The
public surface is: constructor takes an ECP, start() builds the
Channel and starts the receive loop, send() ships an Event to the
peer, stop() shuts down.

    pair                two Terminals connected by an async ECP pair;
                        events sent on one are received-and-dispatched
                        on the other.

    dispatch_to_local   the receive-side Dispatcher fires local
                        callbacks for each incoming event, filtered by
                        the subscription predicate.

    stop                stop() ends the receive loop and closes the
                        Channel; further sends fail.
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
                                                        EventTerminal)


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

    await a.start()
    await b.start()

    banner("send a few events both directions")
    await a.send(TaskDoneEvent(task_id=1, duration_s=1.0, timestamp=10.0))
    await b.send(TaskStartedEvent(task_id=2, timestamp=20.0))
    await a.send(CompilerDoneEvent(task_id=3, source="x.c",
                                   output="x.o", duration_s=0.5,
                                   timestamp=30.0))

    await asyncio.sleep(0.05)
    print("a_seen: %s" % a_seen)
    print("b_seen: %s" % b_seen)

    await a.stop()
    await b.stop()


async def _dispatch_to_local():
    """RETURN: None. Receive-side dispatcher fires callbacks by category."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    workflow_seen   = []
    compilation_seen = []

    async def on_workflow(ev):
        workflow_seen.append(type(ev).__name__)
    async def on_compilation(ev):
        compilation_seen.append(type(ev).__name__)

    b.dispatcher.subscribe_on_category(E_EventCategory.WORKFLOW,    on_workflow)
    b.dispatcher.subscribe_on_category(E_EventCategory.COMPILATION, on_compilation)

    await a.start()
    await b.start()

    banner("send WORKFLOW and COMPILATION events; each fires the right handler")
    await a.send(TaskDoneEvent(task_id=1, duration_s=1.0, timestamp=10.0))
    await a.send(CompilerDoneEvent(task_id=2, source="x.c",
                                   output="x.o", duration_s=0.5,
                                   timestamp=20.0))
    await a.send(TaskStartedEvent(task_id=3, timestamp=30.0))

    await asyncio.sleep(0.05)
    print("workflow_seen:    %s" % workflow_seen)
    print("compilation_seen: %s" % compilation_seen)

    await a.stop()
    await b.stop()


async def _stop():
    """RETURN: None. stop() ends the loop; send after stop fails."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    await a.start()
    await b.start()

    banner("send before stop works")
    await a.send(TaskDoneEvent(task_id=1, duration_s=1.0, timestamp=10.0))
    await asyncio.sleep(0.01)

    banner("stop both terminals")
    await a.stop()
    await b.stop()
    print("a stopped: %s" % a._stopped)
    print("b stopped: %s" % b._stopped)

    banner("send after stop raises")
    try:
        await a.send(TaskDoneEvent(task_id=2, duration_s=2.0))
        print("UNEXPECTED: send succeeded")
    except RuntimeError as e:
        print("RuntimeError raised (expected)")

    banner("stop is idempotent")
    await a.stop()
    print("second stop returned cleanly")


def run_pair():               asyncio.run(_pair())
def run_dispatch_to_local():  asyncio.run(_dispatch_to_local())
def run_stop():               asyncio.run(_stop())


HwutRunner(
    argv       = sys.argv,
    title      = "EventTerminal",
    choice_map = {
        "pair":              run_pair,
        "dispatch_to_local": run_dispatch_to_local,
        "stop":              run_stop,
    },
).run()
