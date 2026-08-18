"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Event dispatcher.

The EventDispatcher matches an Event against registered (predicate, sink)
pairs and calls the sinks whose predicate matches. It is concerned ONLY
with this matching. It does NOT own queues, transports, processes, or
threads.

This separation matters: the Dispatcher is the building block reused by
the Terminal (to fan out incoming events to local handlers) and by the
Router (to decide which Terminal(s) get each outgoing event). Both
inherit the same predicate API for free.


SUBSCRIPTION API

Same three filter dimensions as the previous Router:

    .subscribe_on_event(event_class | name, sink)    -> Subscription
    .subscribe_on_category(category, sink)           -> Subscription
    .subscribe_on_predicate(predicate, sink)         -> Subscription

Sinks are Python callables. They are called with the Event as the
single argument when the predicate matches.


SYNC vs ASYNC CALLBACK ENFORCEMENT

At construction time, a Dispatcher may be created with
enforce_async_callbacks_f=True. In that mode, any callback registered
that is NOT a coroutine function is rejected with TypeError at
subscribe time.

This mode is intended for Dispatchers serving a low-latency context
(e.g. a Terminal's receive loop). Sync callbacks would block the loop;
the flag enforces the discipline at the subscription boundary instead
of letting the problem surface later.


DISPATCH SEMANTICS

dispatch(event) iterates a snapshot of the current subscriptions and
calls each matching sink. The snapshot is taken at the top of
dispatch(); subscriptions added/removed during the call take effect
on the NEXT dispatch.

The Dispatcher itself does NOT decide HOW to call a sink (inline,
scheduled, in a thread). That decision is the SINK's concern. A
Terminal-as-sink puts the event on a queue; a function-as-sink is
called directly. The Dispatcher does the matching, the sink does
the delivery.

Sinks-as-objects: the Dispatcher accepts callables OR any object
with a .send(event) method. This is what lets a Terminal be a sink
for a Router's Dispatcher.

Sync callables, when allowed (enforce_async_callbacks_f=False), are
called inline on the dispatch thread. Caller responsibility is to
keep them fast.

Async callables, when present, are scheduled via asyncio.create_task
and NOT awaited. The dispatch() method does not block on them.

EXPECT: AWAITABLE 

expect_* methods are the awaitable counterpart to subscribe_*: each returns an
awaitable that a coroutine can 'await' to suspend until the next matching
event, then resume with that event as the value.

    expect_event(event_class_or_id)   next event of that id
    expect_category(category)         next event in that category
    expect_predicate(callable)        next event satisfying callable
    match expect_any([ClassA, ClassB, ...]): 
        ..

This lets an event sequence be written as straight-line coroutine
code instead of being scattered across handler callbacks.

EXPECT vs. SUBSCRIPTION:

Each expect_* is one-shot (satisfied by the first match, then done),
forward-looking (matches only events dispatched after it was created),
and non-consuming (it observes; ordinary subscribers and other
outstanding expect_* still receive the same event). Internally an
expect_* is just an ordinary subscription whose sink resolves a
future and unsubscribes itself - so the matching rule is exactly the
corresponding subscribe_on_*'s rule, never re-implemented.
________________________________________________________________________________
"""
import asyncio
import inspect
import sys

from dataclasses import dataclass
from typing      import Any, Callable

from vut.engine.event.event import Event


@dataclass(frozen=True)
class Subscription:
    """Opaque handle returned from each subscribe_on_*."""
    handle:    int
    predicate: Callable[[Event], bool]
    sink:      Any
    kind:      str                              # "send", "async", "sync"


class _ExpectSink:
    """One-shot .send-object sink behind the expect_* methods.

    Registered as the sink of an ordinary subscription. On the first
    matching event it unsubscribes EVERY subscription it was told to
    clear and resolves the future with that event. Being a .send-object
    (not a plain callable), it is accepted even by a Dispatcher built
    with enforce_async_callbacks_f=True - which is what lets expect_*
    work on a Terminal's receive dispatcher.

    The 'subs_func' indirection exists because a sink must be able to
    unsubscribe its own Subscription, yet that Subscription does not
    exist until subscribe_on_* has returned. subs_func is a zero-arg
    callable returning the list of Subscriptions to remove; it is
    called only when the event fires, by which time the list is filled.
    For expect_any, subs_func returns all the per-class subscriptions,
    so the losing alternatives are cleaned up too.
    """

    def __init__(self, dispatcher, future, subs_func):
        """RETURN: a new _ExpectSink.

        dispatcher -- the EventDispatcher to unsubscribe from on match.
        future     -- the asyncio.Future to resolve on first match.
        subs_func  -- zero-arg callable yielding the list of
                      Subscriptions to unsubscribe on first match.
        """
        self._dispatcher = dispatcher
        self._future     = future
        self._subs_func  = subs_func

    def send(self, event: Event) -> None:
        """RETURN: None.

        First call: unsubscribe all associated subscriptions (one-shot,
        no leak) and resolve the future with 'event'. Later calls are
        ignored - the future is already settled.
        """
        if self._future.done():
            return
        for sub in self._subs_func():
            self._dispatcher.unsubscribe(sub)
        self._future.set_result(event)


class EventDispatcher:
    """Matches events against (predicate, sink) pairs and calls sinks.

    See module header for design rationale. Public API:

        subscribe_on_event(event_class_or_name, sink)   -> Subscription
        subscribe_on_category(category, sink)           -> Subscription
        subscribe_on_predicate(predicate, sink)         -> Subscription
        unsubscribe(subscription)                       -> bool
        dispatch(event)                                 -> None
    """

    def __init__(self, enforce_async_callbacks_f: bool = False):
        """RETURN: a new EventDispatcher.

        If enforce_async_callbacks_f is True, sync callable sinks are
        REFUSED at subscribe time (TypeError). Object sinks (with
        .send()) and async callable sinks are still accepted.
        """
        self._enforce_async = enforce_async_callbacks_f
        self._subscriptions:   dict[int, Subscription] = {}
        self._next_handle:     int                     = 0

        # Strong references to scheduled async sink tasks. CPython holds
        # only a WEAK reference to a bare create_task() result, so a
        # fire-and-forget task can be garbage-collected mid-flight. We
        # keep each task here until it finishes (see _spawn), which also
        # gives us a place to surface exceptions that an unawaited task
        # would otherwise swallow.
        self._inflight: set = set()

    # ----------------------------------------------------------------
    # Subscription
    # ----------------------------------------------------------------

    def subscribe_on_event(self, event_id_or_class, sink) -> Subscription:
        """RETURN: Subscription, handle for the new subscription.

        Subscribes 'sink' to receive every Event whose .id equals
        event_id_or_class. Argument may be:

            - the class itself:   subscribe_on_event(EventTaskDone, sink)
            - the id string:      subscribe_on_event("WORKFLOW.EventTaskDone", sink)

        Class form is recommended (type-checked, refactor-friendly).
        """
        if isinstance(event_id_or_class, type) and issubclass(event_id_or_class, Event):
            id_str = event_id_or_class.id
        else:
            id_str = event_id_or_class
        return self._add(
            predicate = lambda ev, eid=id_str: ev.id == eid,
            sink      = sink,
        )

    def subscribe_on_category(self, category: str, sink) -> Subscription:
        """RETURN: Subscription, handle for the new subscription.

        Subscribes 'sink' to receive every Event whose .category equals
        the given category (e.g. "WORKFLOW", "COMPILATION").
        """
        return self._add(
            predicate = lambda ev, cat=category: ev.category == cat,
            sink      = sink,
        )

    def subscribe_on_predicate(self, predicate, sink) -> Subscription:
        """RETURN: Subscription, handle for the new subscription.

        Subscribes 'sink' to receive every Event for which
        predicate(event) returns True. General-purpose filter.
        """
        return self._add(predicate=predicate, sink=sink)

    def unsubscribe(self, subscription: Subscription) -> bool:
        """RETURN: True,  if subscription was removed.
                   False, if the handle was unknown.
        """
        if subscription.handle not in self._subscriptions:
            return False
        del self._subscriptions[subscription.handle]
        return True

    # ----------------------------------------------------------------
    # Expect: awaitable counterpart of subscribe_on_*
    # ----------------------------------------------------------------

    def expect_event(self, event_id_or_class):
        """RETURN: awaitable, yielding the next Event whose .id equals
                              event_id_or_class.

        The awaitable counterpart of subscribe_on_event: instead of
        registering a handler, it lets a coroutine 'await' the next
        matching event. Awaiting suspends the caller until that event
        is dispatched, then resumes with the event as the awaited
        value.

        One-shot and forward-looking: it matches the first event
        dispatched AFTER this call and then is done. Argument forms are
        the same as subscribe_on_event (class or id string).
        """
        return self._expect(self.subscribe_on_event, event_id_or_class)

    def expect_category(self, category: str):
        """RETURN: awaitable, yielding the next Event whose .category
                              equals the given category.

        The awaitable counterpart of subscribe_on_category. See
        expect_event for the suspend/resume and one-shot semantics.
        """
        return self._expect(self.subscribe_on_category, category)

    def expect_predicate(self, predicate):
        """RETURN: awaitable, yielding the next Event for which
                              predicate(event) is true.

        The awaitable counterpart of subscribe_on_predicate. See
        expect_event for the suspend/resume and one-shot semantics.
        """
        return self._expect(self.subscribe_on_predicate, predicate)

    def expect_any(self, event_class_list):
        """RETURN: awaitable, yielding the next Event that is an instance
                              of ANY class in event_class_list.

        Resolves on the FIRST matching event and yields that one event
        (it does not collect several). The caller branches on the
        result, e.g.:

            event = await dispatcher.expect_any([EventA, EventB])
            match event:
                case EventA(): ...
                case EventB(): ...

        Matching reuses subscribe_on_event's id rule, one subscription
        per class; whichever fires first wins. See expect_event for the
        one-shot and forward-looking semantics.
        """
        if not event_class_list:
            raise ValueError(
                "expect_any: event_class_list must not be empty."
            )

        loop   = asyncio.get_running_loop()
        future = loop.create_future()

        # One subscription per class. Each carries a one-shot sink that
        # resolves the SHARED future, so the first event of any listed
        # class wins. The sink's subs_func returns the whole list, so
        # the losing subscriptions are unsubscribed too - no leak.
        subscriptions = []
        for event_class in event_class_list:
            sub = self.subscribe_on_event(
                event_class,
                _ExpectSink(self, future, lambda: subscriptions),
            )
            subscriptions.append(sub)

        return future

    def _expect(self, subscribe_method, *subscribe_args):
        """RETURN: awaitable (asyncio.Future), resolved with the next event
                                               matching the subscription.

        Shared implementation of expect_event / expect_category /
        expect_predicate. Subscribes a one-shot _ExpectSink via the
        given subscribe_on_* method - so the matching rule is exactly
        that method's rule, never re-implemented - and returns the
        future the sink will resolve.

        The sink unsubscribes itself on first match, so the
        subscription does not leak once the awaitable completes.

        INVARIANT: relies on there being no 'await' between the
        subscribe_method() call and box.append(sub) below. In
        single-threaded asyncio nothing can preempt this stretch, so
        the sink's back-reference (box) is always filled before any
        event can reach it.
        """
        loop   = asyncio.get_running_loop()
        future = loop.create_future()

        # The sink needs its own Subscription handle to unsubscribe
        # itself, but that handle does not exist until subscribe_*
        # returns. A one-element list is the forward reference: the
        # sink reads box[0], which is filled in immediately below.
        box = []
        sub = subscribe_method(*subscribe_args,
                               _ExpectSink(self, future, lambda: box))
        box.append(sub)

        return future

    # ----------------------------------------------------------------
    # Dispatch
    # ----------------------------------------------------------------
    def dispatch(self, event: Event) -> None:
        """RETURN: None.

        Calls each matching sink. Sinks are dispatched per their kind:

            "send"   -- object with .send(event); called directly.
                        send() may itself be async or sync; the
                        Dispatcher does not await it.
            "async"  -- coroutine function; scheduled via
                        asyncio.create_task(); not awaited.
            "sync"   -- regular callable; called inline on the
                        dispatch thread.

        Snapshot iteration: mutation of the subscription set during
        dispatch does NOT affect the current call.

        Per-subscription exceptions in predicates or sync sink-calls are
        caught and logged to stderr; other subscriptions are still
        served. Async sinks are scheduled via _spawn, which retains the
        task (so it cannot be GC'd mid-flight) and logs any exception it
        raises through the same stderr channel.
        """
        for sub in tuple(self._subscriptions.values()):
            try:
                if not sub.predicate(event):
                    continue
            except Exception as e:
                print("EventDispatcher.dispatch: predicate raised on "
                      "subscription %d: %s" % (sub.handle, e),
                      file=sys.stderr)
                continue

            try:
                if sub.kind == "send":
                    result = sub.sink.send(event)
                    # If send() returned a coroutine (Terminal.send is async),
                    # schedule it so we do not block.
                    if inspect.iscoroutine(result):
                        self._spawn(result, sub.handle)
                elif sub.kind == "async":
                    self._spawn(sub.sink(event), sub.handle)
                else:                              # "sync"
                    sub.sink(event)
            except RuntimeError as e:
                # Most often: "no running event loop" when create_task is
                # called from a non-async context.
                print("EventDispatcher.dispatch: cannot deliver to "
                      "subscription %d: %s" % (sub.handle, e),
                      file=sys.stderr)
            except Exception as e:
                print("EventDispatcher.dispatch: sink call raised on "
                      "subscription %d: %s" % (sub.handle, e),
                      file=sys.stderr)

    # ----------------------------------------------------------------
    # Introspection
    # ----------------------------------------------------------------

    def __len__(self) -> int:
        """RETURN: int, number of active subscriptions."""
        return len(self._subscriptions)

    def __contains__(self, subscription: Subscription) -> bool:
        """RETURN: True if subscription is active in this Dispatcher."""
        return subscription.handle in self._subscriptions

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    def _spawn(self, coro, handle: int) -> None:
        """RETURN: None.

        Schedule 'coro' on the running loop and keep a STRONG reference
        to the resulting task until it completes - so the task cannot be
        garbage-collected mid-flight. When it finishes, drop the
        reference and, if it raised, log the exception to stderr in the
        same form as the synchronous path (an unawaited task would
        otherwise swallow the exception until GC).

        Raises nothing: a RuntimeError from create_task (no running
        loop) is caught and logged, matching the sync path's behaviour.
        """
        try:
            task = asyncio.create_task(coro)
        except RuntimeError as e:
            # No running loop: same diagnostic the inline path emits.
            print("EventDispatcher.dispatch: cannot deliver to "
                  "subscription %d: %s" % (handle, e),
                  file=sys.stderr)
            return

        self._inflight.add(task)

        def _done(t: "asyncio.Task", h=handle) -> None:
            self._inflight.discard(t)
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                print("EventDispatcher.dispatch: async sink raised on "
                      "subscription %d: %s" % (h, exc),
                      file=sys.stderr)

        task.add_done_callback(_done)

    def _add(self, predicate, sink) -> Subscription:
        """RETURN: Subscription, the handle for the new entry.

        Classifies the sink (send-object, async-callable, sync-callable)
        and assigns a unique handle. Raises TypeError if the sink does
        not match any allowed kind, or if it is a sync callable and
        the Dispatcher was constructed with
        enforce_async_callbacks_f=True.
        """
        # Object with .send(): always allowed.
        if callable(getattr(sink, "send", None)):
            kind = "send"
        elif callable(sink):
            if inspect.iscoroutinefunction(sink):
                kind = "async"
            else:
                if self._enforce_async:
                    raise TypeError(
                        "EventDispatcher: sync callable sink rejected "
                        "(enforce_async_callbacks_f=True is set). "
                        "Sink must be an async def or have a .send() method."
                    )
                kind = "sync"
        else:
            raise TypeError(
                "EventDispatcher: sink must be a callable or an object "
                "with a .send(event) method; got %s" % type(sink).__name__
            )

        handle = self._next_handle
        self._next_handle += 1

        sub = Subscription(handle=handle, predicate=predicate,
                           sink=sink, kind=kind)
        self._subscriptions[handle] = sub
        return sub

