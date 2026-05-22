#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the EventDispatcher.

CHOICES: matching, sink_kinds, enforce_async, snapshot;

DESCRIPTION:

The Dispatcher matches Events against (predicate, sink) pairs and
calls sinks. It is concerned ONLY with matching - not transport.

    matching        subscribe_on_event/category/predicate; verify
                    each fires the correct sink.

    sink_kinds      three sink shapes: object-with-.send, async
                    callable, sync callable. Each is detected and
                    dispatched per its kind.

    enforce_async   constructed with enforce_async_callbacks_f=True
                    rejects sync callables at subscribe time.

    snapshot        subscribing/unsubscribing during dispatch()
                    does not affect the current call; the snapshot
                    iteration handles re-entrancy.
______________________________________________________________________________
"""
import asyncio
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (Event,
                                                        category,
                                                        EventDispatcher)


# Test-local event vocabulary. Split into two categories so that
# subscribe_on_category("...COMPILE") discriminates from "...TASK".
with category("TEST_LOCAL_DISP_TASK"):

    class EventTaskStarted(Event):
        task_id: int

    class EventTaskDone(Event):
        task_id:    int
        duration_s: float

    class EventTaskFailed(Event):
        task_id: int
        reason:  str


with category("TEST_LOCAL_DISP_COMPILE"):

    class EventCompilerDone(EventTaskDone):
        source: str
        output: str


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _matching():
    """RETURN: None. Verify each subscribe_on_* fires correctly."""
    d = EventDispatcher()
    by_event    = []
    by_category = []
    by_pred     = []

    async def cb_event(ev):    by_event.append(ev.id)
    async def cb_category(ev): by_category.append(ev.id)
    async def cb_pred(ev):     by_pred.append(ev.id)

    d.subscribe_on_event(EventTaskDone,                   cb_event)
    d.subscribe_on_category("TEST_LOCAL_DISP_COMPILE",  cb_category)
    d.subscribe_on_predicate(lambda ev: ev.task_id == 7,  cb_pred)

    banner("len after three subscribes")
    print("len: %d" % len(d))

    banner("dispatch three events")
    d.dispatch(EventTaskDone(task_id=1, duration_s=1.0))   # event match
    d.dispatch(EventCompilerDone(task_id=7, source="x",
                                 output="y", duration_s=0.1))   # category AND pred
    d.dispatch(EventTaskStarted(task_id=99))                # no match anywhere
    await asyncio.sleep(0.01)

    print("by_event   : %s" % by_event)
    print("by_category: %s" % by_category)
    print("by_pred    : %s" % by_pred)


async def _sink_kinds():
    """RETURN: None. The three sink kinds."""
    d = EventDispatcher()

    banner("async callable sink (kind=async)")
    async_seen = []
    async def async_cb(ev):
        async_seen.append(ev.id)
    s_async = d.subscribe_on_event(EventTaskDone, async_cb)
    print("kind: %s" % s_async.kind)

    banner("sync callable sink (kind=sync)")
    sync_seen = []
    def sync_cb(ev):
        sync_seen.append(ev.id)
    s_sync = d.subscribe_on_event(EventTaskDone, sync_cb)
    print("kind: %s" % s_sync.kind)

    banner("object-with-.send sink (kind=send)")
    class Bucket:
        def __init__(self):
            self.items = []
        def send(self, ev):
            self.items.append(ev.id)
    bucket = Bucket()
    s_send = d.subscribe_on_event(EventTaskDone, bucket)
    print("kind: %s" % s_send.kind)

    banner("dispatch fires all three")
    d.dispatch(EventTaskDone(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.01)
    print("async_seen : %s" % async_seen)
    print("sync_seen  : %s" % sync_seen)
    print("bucket.items: %s" % bucket.items)

    banner("non-callable, non-send object is rejected")
    try:
        d.subscribe_on_event(EventTaskDone, 42)
        print("UNEXPECTED: accepted")
    except TypeError as e:
        print("TypeError: %s" % e)


async def _enforce_async():
    """RETURN: None. enforce_async_callbacks_f=True rejects sync callables."""
    d = EventDispatcher(enforce_async_callbacks_f=True)

    banner("async callable accepted")
    async def cb(ev): pass
    s = d.subscribe_on_event(EventTaskDone, cb)
    print("kind: %s" % s.kind)

    banner("object-with-.send accepted")
    class Bucket:
        def send(self, ev): pass
    s = d.subscribe_on_event(EventTaskDone, Bucket())
    print("kind: %s" % s.kind)

    banner("sync callable rejected")
    def sync_cb(ev): pass
    try:
        d.subscribe_on_event(EventTaskDone, sync_cb)
        print("UNEXPECTED: accepted")
    except TypeError:
        print("TypeError raised (expected)")

    banner("lambda (sync) rejected")
    try:
        d.subscribe_on_event(EventTaskDone, lambda ev: None)
        print("UNEXPECTED: accepted")
    except TypeError:
        print("TypeError raised (expected)")


async def _snapshot():
    """RETURN: None. Subscribing during dispatch does not affect the
    current call; the snapshot iteration handles re-entrancy."""
    d = EventDispatcher()
    fired = []

    async def late_cb(ev):
        fired.append("late")

    async def mutator(ev):
        # Subscribe a new callback during dispatch. It must NOT fire on
        # the current event.
        d.subscribe_on_event(EventTaskDone, late_cb)
        fired.append("first")

    d.subscribe_on_event(EventTaskDone, mutator)

    banner("first dispatch: only 'first' fires; 'late_cb' added but not yet active")
    d.dispatch(EventTaskDone(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.01)
    print("fired: %s" % fired)
    print("len(d): %d" % len(d))

    banner("second dispatch: now both fire (and mutator adds yet another)")
    d.dispatch(EventTaskDone(task_id=2, duration_s=2.0))
    await asyncio.sleep(0.01)
    print("fired: %s" % fired)

    banner("predicate that raises does not break iteration")
    d2 = EventDispatcher()
    fired2 = []
    def bad_pred(ev):
        raise RuntimeError("predicate boom")
    async def good_cb(ev):
        fired2.append("good")
    d2.subscribe_on_predicate(bad_pred, good_cb)
    d2.subscribe_on_event(EventTaskDone, good_cb)
    d2.dispatch(EventTaskDone(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.01)
    print("fired2: %s" % fired2)


def run_matching():     asyncio.run(_matching())
def run_sink_kinds():   asyncio.run(_sink_kinds())
def run_enforce_async():asyncio.run(_enforce_async())
def run_snapshot():     asyncio.run(_snapshot())


HwutRunner(
    argv       = sys.argv,
    title      = "EventDispatcher",
    choice_map = {
        "matching":      run_matching,
        "sink_kinds":    run_sink_kinds,
        "enforce_async": run_enforce_async,
        "snapshot":      run_snapshot,
    },
).run()
