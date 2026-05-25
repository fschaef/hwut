"""Acceptance tests for the expect_* methods on EventDispatcher."""
import asyncio
import sys

import config                                                       # noqa: F401

from vut.engine.event.event      import Event, category
from vut.engine.event.dispatcher import EventDispatcher



with category("WORKFLOW"):
    class EventTaskStarted(Event):
        task_id: int
    class EventTaskCancelled(Event):
        task_id: int
    class EventTaskDone(Event):
        task_id: int

with category("OTHER"):
    class EventNoise(Event):
        text: str


PASS, FAIL = [], []

def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "FAIL  ") + name)


# ===========================================================================
async def test_A1_expect_event():
    """A1: await expect_event(E) resumes with the next E."""
    d = EventDispatcher()
    got = []

    async def waiter():
        got.append(await d.expect_event(EventTaskDone))

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    d.dispatch(EventTaskDone(task_id=7))
    await asyncio.wait_for(t, 1.0)

    check("A1 expect_event resumes with the event",
          len(got) == 1 and got[0].task_id == 7)


# ===========================================================================
async def test_A2_category_and_predicate():
    """A2: expect_category / expect_predicate behave as A1 for their rule."""
    d = EventDispatcher()
    by_cat, by_pred = [], []

    async def w_cat():
        by_cat.append(await d.expect_category("WORKFLOW"))
    async def w_pred():
        by_pred.append(await d.expect_predicate(lambda ev: ev.task_id == 42))

    tc = asyncio.create_task(w_cat())
    tp = asyncio.create_task(w_pred())
    await asyncio.sleep(0)

    d.dispatch(EventNoise(text="ignored by both"))   # wrong cat, no task_id
    await asyncio.sleep(0)
    check("A2 expect_category ignores other-category event", by_cat == [])

    d.dispatch(EventTaskStarted(task_id=42))         # matches both
    await asyncio.wait_for(asyncio.gather(tc, tp), 1.0)

    check("A2 expect_category resumes on category match",
          len(by_cat) == 1 and by_cat[0].category == "WORKFLOW")
    check("A2 expect_predicate resumes on predicate match",
          len(by_pred) == 1 and by_pred[0].task_id == 42)


# ===========================================================================
async def test_A3_expect_any():
    """A3: expect_any resumes with whichever class is dispatched first."""
    d = EventDispatcher()
    branch = []

    async def waiter():
        event = await d.expect_any([EventTaskCancelled, EventTaskDone])
        match event:
            case EventTaskCancelled():
                branch.append("cancelled")
            case EventTaskDone():
                branch.append("done")

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    d.dispatch(EventTaskDone(task_id=1))             # second class wins
    await asyncio.wait_for(t, 1.0)

    check("A3 expect_any resumes and 'match' branches on the type",
          branch == ["done"])
    check("A3 expect_any leaves no subscription behind", len(d) == 0)


# ===========================================================================
async def test_A4_B2_one_shot():
    """A4/B2: an expect_* fires exactly once."""
    d = EventDispatcher()
    fires = []

    async def waiter():
        fires.append(await d.expect_event(EventTaskDone))

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    d.dispatch(EventTaskDone(task_id=1))
    await asyncio.wait_for(t, 1.0)
    d.dispatch(EventTaskDone(task_id=2))             # no waiter now
    await asyncio.sleep(0)

    check("B2 expect_* fires exactly once", len(fires) == 1 and fires[0].task_id == 1)
    check("B2 one-shot leaves no subscription", len(d) == 0)


# ===========================================================================
async def test_A4_B3_forward_looking():
    """B3: an expect_* does not match an event dispatched before it existed."""
    d = EventDispatcher()
    d.dispatch(EventTaskDone(task_id=99))            # BEFORE any expect

    got = []
    async def waiter():
        got.append(await d.expect_event(EventTaskDone))

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0.02)
    check("B3 earlier event not retro-matched", got == [])

    d.dispatch(EventTaskDone(task_id=100))
    await asyncio.wait_for(t, 1.0)
    check("B3 expect_* matches the next event after creation",
          len(got) == 1 and got[0].task_id == 100)


# ===========================================================================
async def test_A4_B4_non_consuming():
    """B4: an expect_* does not remove the event from normal delivery."""
    d = EventDispatcher()
    handler_saw, expect_saw = [], []

    async def handler(ev):
        handler_saw.append(ev)
    d.subscribe_on_event(EventTaskDone, handler)

    async def waiter():
        expect_saw.append(await d.expect_event(EventTaskDone))

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    d.dispatch(EventTaskDone(task_id=3))
    await asyncio.wait_for(t, 1.0)
    await asyncio.sleep(0)                           # let handler task run

    check("B4 ordinary handler still receives the event", len(handler_saw) == 1)
    check("B4 expect_* also receives the event", len(expect_saw) == 1)


# ===========================================================================
async def test_A4_B5_concurrent():
    """B5: one event satisfies every outstanding expect_* that matches."""
    d = EventDispatcher()
    a, b, c = [], [], []

    async def w_a():
        a.append(await d.expect_event(EventTaskDone))
    async def w_b():
        b.append(await d.expect_category("WORKFLOW"))
    async def w_c():
        c.append(await d.expect_predicate(lambda ev: True))

    tasks = [asyncio.create_task(w()) for w in (w_a, w_b, w_c)]
    await asyncio.sleep(0)
    d.dispatch(EventTaskDone(task_id=5))             # matches all three
    await asyncio.wait_for(asyncio.gather(*tasks), 1.0)

    check("B5 one event satisfies all matching expects",
          len(a) == 1 and len(b) == 1 and len(c) == 1)
    check("B5 all three resumed with the same event",
          a[0].task_id == 5 and b[0].task_id == 5 and c[0].task_id == 5)
    check("B5 no subscriptions leak after all resolve", len(d) == 0)


# ===========================================================================
async def test_B6_expect_any_first_only():
    """B6: expect_any resolves on the first match and yields one event."""
    d = EventDispatcher()
    got = []

    async def waiter():
        got.append(await d.expect_any([EventTaskCancelled, EventTaskDone]))

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    d.dispatch(EventTaskCancelled(task_id=1))        # first
    await asyncio.wait_for(t, 1.0)
    d.dispatch(EventTaskDone(task_id=2))             # after resolution
    await asyncio.sleep(0)

    check("B6 expect_any yields exactly the first match",
          len(got) == 1 and isinstance(got[0], EventTaskCancelled))


# ===========================================================================
async def test_enforce_async_dispatcher():
    """expect_* works on a dispatcher with enforce_async_callbacks_f=True."""
    d = EventDispatcher(enforce_async_callbacks_f=True)
    got = []

    async def waiter():
        got.append(await d.expect_event(EventTaskDone))

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    d.dispatch(EventTaskDone(task_id=1))
    await asyncio.wait_for(t, 1.0)

    check("expect_* works under enforce_async_callbacks_f "
          "(sink is a .send-object)", len(got) == 1)


# ===========================================================================
async def main():
    tests = [
        test_A1_expect_event,
        test_A2_category_and_predicate,
        test_A3_expect_any,
        test_A4_B2_one_shot,
        test_A4_B3_forward_looking,
        test_A4_B4_non_consuming,
        test_A4_B5_concurrent,
        test_B6_expect_any_first_only,
        test_enforce_async_dispatcher,
    ]
    for t in tests:
        print("\n[%s]" % t.__name__)
        await t()

    print("\n" + "=" * 60)
    print("PASSED %d   FAILED %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("FAILURES:", ", ".join(FAIL))
        sys.exit(1)
    print("all acceptance checks passed")


if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("Dispatcher: expect")
        sys.exit()
    asyncio.run(main())
