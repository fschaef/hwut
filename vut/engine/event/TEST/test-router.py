#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the Router.

CHOICES: by_event, by_category, by_predicate, unsubscribe, sinks;

DESCRIPTION:

The Router holds (predicate, sink) subscriptions and publishes events
to matching subscribers. Each test choice exercises one axis:

    by_event       subscribe_on_event delivers ONLY events whose .id
                   matches; multiple subscriptions for the same id
                   all fire (exact-match-all-subscribers).

    by_category    subscribe_on_category delivers ONLY events whose
                   .category matches.

    by_predicate   subscribe_on_predicate accepts arbitrary filters;
                   the same event may match several predicate
                   subscriptions.

    unsubscribe    handle removal stops further delivery; removing
                   a stale handle returns False (no exception);
                   removing during dispatch is safe (snapshot
                   iteration).

    sinks          three sink kinds (queue, async callable, sync
                   callable); validation of bad sinks (TypeError at
                   subscribe time); sync sinks run in worker threads.

The test scripts use asyncio.run() because publish() requires a
running event loop to schedule callback tasks. Queue sinks (using
asyncio.Queue.put_nowait) also require a running loop for the queue
to be useful.
______________________________________________________________________________
"""
import asyncio
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (E_EventCategory,
                                                        TaskStartedEvent,
                                                        TaskDoneEvent,
                                                        TaskFailedEvent,
                                                        CompilerDoneEvent,
                                                        CompilerNoSourceEvent,
                                                        ArtifactAvailableEvent,
                                                        Router)


def banner(label):
    """RETURN: None.  Prints a section heading."""
    print()
    print("--- %s ---" % label)


# ----------------------------------------------------------------------------
# Each choice's async body. The HwutRunner driver call is sync; we wrap.
# ----------------------------------------------------------------------------

async def _by_event():
    router = Router()
    seen_a = []
    seen_b = []

    async def cb_a(ev):
        seen_a.append(ev.id)

    async def cb_b(ev):
        seen_b.append(ev.id)

    banner("two subscriptions on the same id, both fire")
    router.subscribe_on_event(TaskDoneEvent, cb_a)
    router.subscribe_on_event(TaskDoneEvent, cb_b)
    router.subscribe_on_event(TaskFailedEvent, cb_a)

    router.publish(TaskDoneEvent  (task_id=1, duration_s=1.0))
    router.publish(TaskFailedEvent(task_id=2, reason="boom"))
    router.publish(TaskStartedEvent(task_id=3))  # not subscribed to
    await asyncio.sleep(0.01)

    print("seen_a: %s" % seen_a)
    print("seen_b: %s" % seen_b)

    banner("subscribing on CompilerDoneEvent delivers only Compiler events, not generic TaskDoneEvent")
    seen_c = []

    async def cb_c(ev):
        seen_c.append(type(ev).__name__)

    router2 = Router()
    router2.subscribe_on_event(CompilerDoneEvent, cb_c)
    router2.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    router2.publish(CompilerDoneEvent(task_id=2, source="a.c",
                                      output="a.o", duration_s=0.5))
    await asyncio.sleep(0.01)
    print("seen_c: %s" % seen_c)

    banner("subscribing by string id (\"TaskDoneEvent\") works the same as by class")
    seen_s = []
    async def cb_s(ev):
        seen_s.append(ev.id)

    router3 = Router()
    router3.subscribe_on_event("TaskDoneEvent", cb_s)
    router3.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    router3.publish(TaskFailedEvent(task_id=2, reason="boom"))
    await asyncio.sleep(0.01)
    print("seen_s: %s" % seen_s)


async def _by_category():
    router = Router()
    workflow_q   = asyncio.Queue()
    compilation_q = asyncio.Queue()

    banner("category=WORKFLOW gets task lifecycle events; category=COMPILATION gets compiler events")
    router.subscribe_on_category(E_EventCategory.WORKFLOW,    workflow_q)
    router.subscribe_on_category(E_EventCategory.COMPILATION, compilation_q)

    router.publish(TaskDoneEvent(task_id=1, duration_s=1.0))                  # WORKFLOW
    router.publish(CompilerDoneEvent(task_id=2, source="x.c",                 # COMPILATION
                                     output="x.o", duration_s=0.5))
    router.publish(CompilerNoSourceEvent(task_id=3, expected="y.c"))          # COMPILATION
    router.publish(ArtifactAvailableEvent(task_id=4, artifact_id=42))         # WORKFLOW

    # Queues are filled synchronously by put_nowait; no sleep needed.
    print("WORKFLOW queue contents:")
    while not workflow_q.empty():
        print("  %s" % type(workflow_q.get_nowait()).__name__)
    print("COMPILATION queue contents:")
    while not compilation_q.empty():
        print("  %s" % type(compilation_q.get_nowait()).__name__)


async def _by_predicate():
    router = Router()
    seen = []

    async def cb(ev):
        seen.append("%s/%s" % (type(ev).__name__, getattr(ev, "task_id", "?")))

    banner("predicate: task_id is in {1, 3}")
    router.subscribe_on_predicate(
        predicate = lambda ev: getattr(ev, "task_id", None) in {1, 3},
        sink      = cb,
    )

    router.publish(TaskDoneEvent(task_id=1, duration_s=1.0))    # match
    router.publish(TaskDoneEvent(task_id=2, duration_s=2.0))    # no
    router.publish(TaskDoneEvent(task_id=3, duration_s=3.0))    # match
    router.publish(TaskDoneEvent(task_id=4, duration_s=4.0))    # no
    await asyncio.sleep(0.01)
    print("seen: %s" % seen)

    banner("predicate over derived attribute: only events with .reason")
    router2 = Router()
    seen2 = []

    async def cb2(ev):
        seen2.append(type(ev).__name__)

    router2.subscribe_on_predicate(
        predicate = lambda ev: hasattr(ev, "reason"),
        sink      = cb2,
    )
    router2.publish(TaskDoneEvent(task_id=1, duration_s=1.0))           # no
    router2.publish(TaskFailedEvent(task_id=2, reason="boom"))          # match
    router2.publish(TaskStartedEvent(task_id=3))                        # no
    await asyncio.sleep(0.01)
    print("seen2: %s" % seen2)

    banner("predicate that raises is skipped, not propagated")
    router3 = Router()
    seen3 = []
    async def cb3(ev):
        seen3.append("hit")

    def bad_pred(ev):
        raise RuntimeError("predicate boom")

    router3.subscribe_on_predicate(bad_pred, cb3)
    # Add another subscription that DOES match, to verify it still fires.
    router3.subscribe_on_event(TaskDoneEvent, cb3)
    router3.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.01)
    print("seen3: %s" % seen3)


async def _unsubscribe():
    router = Router()
    seen = []

    async def cb(ev):
        seen.append(ev.id)

    banner("unsubscribe stops further delivery")
    sub = router.subscribe_on_event(TaskDoneEvent, cb)
    print("subs after subscribe: %d" % len(router))
    print("handle in router:     %s" % (sub in router))

    router.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.01)
    print("seen before unsub:    %s" % seen)

    print("unsubscribe returns:  %s" % router.unsubscribe(sub))
    print("subs after unsub:     %d" % len(router))
    print("handle in router:     %s" % (sub in router))

    router.publish(TaskDoneEvent(task_id=2, duration_s=2.0))
    await asyncio.sleep(0.01)
    print("seen after unsub:     %s" % seen)

    banner("unsubscribing a stale handle returns False")
    print("repeat unsubscribe:   %s" % router.unsubscribe(sub))

    banner("safe to subscribe during dispatch (snapshot iteration)")
    router2 = Router()
    fired = []

    async def late_cb(ev):
        fired.append("late")

    async def cb_mutator(ev):
        # Subscribe a NEW callback during dispatch. The new one should
        # NOT fire on the current event (snapshot was taken before).
        router2.subscribe_on_event(TaskDoneEvent, late_cb)
        fired.append("first")

    router2.subscribe_on_event(TaskDoneEvent, cb_mutator)
    router2.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.01)
    print("first publish fired:  %s" % fired)
    print("subs after first:     %d" % len(router2))

    # Second publish: the late_cb (added during the first dispatch) now fires.
    router2.publish(TaskDoneEvent(task_id=2, duration_s=2.0))
    await asyncio.sleep(0.01)
    print("second publish fired: %s" % fired)


async def _sinks():
    router = Router()

    banner("async callable is accepted as a sink (is_async=True)")
    async def async_cb(ev): pass
    sub_async = router.subscribe_on_event(TaskDoneEvent, async_cb)
    print("handle:   %d" % sub_async.handle)
    print("is_queue: %s" % sub_async.is_queue)
    print("is_async: %s" % sub_async.is_async)

    banner("sync callable is accepted as a sink (is_async=False, is_queue=False)")
    def sync_cb(ev): pass
    sub_sync = router.subscribe_on_event(TaskDoneEvent, sync_cb)
    print("handle:   %d" % sub_sync.handle)
    print("is_queue: %s" % sub_sync.is_queue)
    print("is_async: %s" % sub_sync.is_async)

    banner("lambda (sync) is accepted")
    sub_lam = router.subscribe_on_event(TaskDoneEvent, lambda ev: None)
    print("handle:   %d" % sub_lam.handle)
    print("is_async: %s" % sub_lam.is_async)

    banner("asyncio.Queue is accepted (has put_nowait)")
    q = asyncio.Queue()
    sub_q = router.subscribe_on_event(TaskDoneEvent, q)
    print("handle:   %d" % sub_q.handle)
    print("is_queue: %s" % sub_q.is_queue)
    print("is_async: %s" % sub_q.is_async)

    banner("plain int is rejected")
    try:
        router.subscribe_on_event(TaskDoneEvent, 42)
        print("UNEXPECTED: accepted")
    except TypeError as e:
        print("TypeError: %s" % e)

    banner("plain dict is rejected (no put_nowait, not callable)")
    try:
        router.subscribe_on_event(TaskDoneEvent, {})
        print("UNEXPECTED: accepted")
    except TypeError as e:
        print("TypeError: %s" % e)

    banner("queue with bounded size + full -> diagnostic to stderr, event dropped")
    bounded = asyncio.Queue(maxsize=1)
    bounded.put_nowait("filler")              # now full
    router2 = Router()
    router2.subscribe_on_event(TaskDoneEvent, bounded)
    # publish should NOT raise; the failure is logged to stderr (not captured).
    router2.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    print("publish on full queue returned cleanly")

    banner("sync callable runs in a worker thread, not the main thread")
    import threading
    router3 = Router()
    seen_threads = []
    def sync_observer(ev):
        seen_threads.append(threading.current_thread().name != main_thread)

    main_thread = threading.current_thread().name
    router3.subscribe_on_event(TaskDoneEvent, sync_observer)
    router3.publish(TaskDoneEvent(task_id=1, duration_s=1.0))
    await asyncio.sleep(0.05)
    print("ran off main thread: %s" % seen_threads)


# ----------------------------------------------------------------------------
# Sync wrappers (HwutRunner calls these)
# ----------------------------------------------------------------------------

def run_by_event():     asyncio.run(_by_event())
def run_by_category():  asyncio.run(_by_category())
def run_by_predicate(): asyncio.run(_by_predicate())
def run_unsubscribe():  asyncio.run(_unsubscribe())
def run_sinks():        asyncio.run(_sinks())


HwutRunner(
    argv       = sys.argv,
    title      = "Router: subscribe by event / category / predicate, unsubscribe, sinks",
    choice_map = {
        "by_event":     run_by_event,
        "by_category":  run_by_category,
        "by_predicate": run_by_predicate,
        "unsubscribe":  run_unsubscribe,
        "sinks":        run_sinks,
    },
).run()
