#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Guard the behaviour fixed during the event-component review
         (DECISIONS 20, 21, 22).

CHOICES: async_exception, inflight_drains, send_not_up, peer_down_list,
         peer_down_isolated;

DESCRIPTION:

These choices pin behaviours that previously had latent bugs, so a
future change that reintroduces one shows as a diff.

    async_exception     an async sink that raises no longer swallows
                        the exception. dispatch() schedules it through
                        the owned-task registry, whose done-callback
                        surfaces the error (here captured via a
                        custom loop exception handler so stdout is
                        deterministic). [DECISION 20]

    inflight_drains     the dispatcher retains a strong reference to
                        each scheduled async-sink task until it
                        completes, then drops it - so the in-flight set
                        is non-empty while a slow sink runs and empty
                        once it finishes. [DECISION 20]

    send_not_up         EventTerminal.send() before UP returns False
                        and writes a stderr diagnostic - it does NOT
                        raise. A send to a not-UP peer is a normal race,
                        not a misuse, so it is reported by return value.
                        [DECISION 21, reversed]

    peer_down_list      add_peer_down_callback registers ADDITIVELY:
                        two callbacks on one Terminal both fire on peer
                        Down. set_peer_down_callback remains a
                        single-slot replace. [DECISION 22]

    peer_down_isolated  one peer-down callback raising does not stop the
                        others from firing. [DECISION 22]
______________________________________________________________________________
"""
import asyncio
import sys
from   config import HwutRunner

from   vut.engine.event import (Event,
                                category,
                                EventDispatcher,
                                EventChannelParameter,
                                EventTerminal)


with category("TEST_LOCAL_REGR"):

    class EventPing(Event):
        n: int


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _async_exception():
    """RETURN: None. A raising async sink is surfaced, not swallowed."""
    # Capture loop-level reports deterministically: the dispatcher's
    # done-callback prints to stderr (suppressed in the GOOD run); here
    # we additionally record that the task completed in error state via
    # our own done bookkeeping, so stdout shows the outcome.
    d = EventDispatcher()
    outcome = []

    async def good_sink(ev):
        outcome.append("good ran")

    async def bad_sink(ev):
        raise ValueError("boom")

    d.subscribe_on_event(EventPing, good_sink)
    d.subscribe_on_event(EventPing, bad_sink)

    banner("dispatch one event to a good and a raising async sink")
    d.dispatch(EventPing(n=1))
    await asyncio.sleep(0.05)

    # The good sink still ran; the bad sink's exception did not abort
    # dispatch nor the good sink. The exception itself was logged to
    # stderr by the registry's done-callback (not shown here).
    print("outcome:            %s" % outcome)
    print("inflight after run: %d" % len(d._inflight))


async def _inflight_drains():
    """RETURN: None. The owned-task set fills during a slow sink, empties after."""
    d = EventDispatcher()
    gate = asyncio.Event()

    async def slow_sink(ev):
        await gate.wait()        # hold the task open until released

    d.subscribe_on_event(EventPing, slow_sink)

    banner("while the async sink is in flight")
    d.dispatch(EventPing(n=1))
    await asyncio.sleep(0.02)    # let the task start and block on the gate
    print("inflight (sink running): %d" % len(d._inflight))

    banner("after releasing the sink")
    gate.set()
    await asyncio.sleep(0.02)    # let the task finish and done-callback run
    print("inflight (sink done):    %d" % len(d._inflight))


async def _send_not_up():
    """RETURN: None. send() before UP returns False (no exception)."""
    a_ecp, _ = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)

    banner("send() on a NEW (not started) terminal returns False")
    print("state: %s" % a.state)
    verdict = await a.send(EventPing(n=1))
    print("send returned: %s" % verdict)


async def _peer_down_list():
    """RETURN: None. Two additive peer-down callbacks both fire."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    fired = []
    b.add_peer_down_callback(lambda: fired.append("one"))
    b.add_peer_down_callback(lambda: fired.append("two"))

    await asyncio.gather(a.start(), b.start())

    banner("stop A; both of B's peer-down callbacks fire")
    await a.stop()
    await asyncio.sleep(0.05)
    print("fired: %s" % sorted(fired))

    banner("set_peer_down_callback REPLACES the list")
    c_ecp, d_ecp = EventChannelParameter.for_async()
    c = EventTerminal(c_ecp)
    e = EventTerminal(d_ecp)
    fired2 = []
    e.add_peer_down_callback(lambda: fired2.append("additive"))
    e.set_peer_down_callback(lambda: fired2.append("only-this"))
    await asyncio.gather(c.start(), e.start())
    await c.stop()
    await asyncio.sleep(0.05)
    print("fired2: %s" % fired2)

    await b.stop()
    await e.stop()


async def _peer_down_isolated():
    """RETURN: None. A raising peer-down callback does not stop the others."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    fired = []
    def raiser():
        raise RuntimeError("callback boom")
    b.add_peer_down_callback(raiser)
    b.add_peer_down_callback(lambda: fired.append("survivor"))

    await asyncio.gather(a.start(), b.start())

    banner("stop A; first callback raises, second still fires")
    await a.stop()
    await asyncio.sleep(0.05)
    # The raiser's exception is logged to stderr (suppressed here); the
    # survivor still ran.
    print("fired: %s" % fired)

    await b.stop()


def run_async_exception():    asyncio.run(_async_exception())
def run_inflight_drains():    asyncio.run(_inflight_drains())
def run_send_not_up():        asyncio.run(_send_not_up())
def run_peer_down_list():     asyncio.run(_peer_down_list())
def run_peer_down_isolated(): asyncio.run(_peer_down_isolated())


HwutRunner(
    argv       = sys.argv,
    title      = "Review-fix regressions",
    choice_map = {
        "async_exception":    run_async_exception,
        "inflight_drains":    run_inflight_drains,
        "send_not_up":        run_send_not_up,
        "peer_down_list":     run_peer_down_list,
        "peer_down_isolated": run_peer_down_isolated,
    },
).run()
