"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: In-process event router.

The Router holds (filter, sink) subscriptions and pushes events to
matching subscribers. It is a small, general-purpose component that
many subsystems will share: the WFM's report loop, diagnostic
aggregators, test fixtures, etc.

DESIGN: SUBSCRIBE BY FILTER DIMENSION

The natural shape of a subscription is "I am interested in events
matching X". X is almost always one of three things:

    - a specific event id        (subscribe_on_event)
    - an entire category         (subscribe_on_category)
    - an arbitrary predicate     (subscribe_on_predicate)

The first two are by far the most common; the third covers the
general case. The API encodes this directly, with one method per
dimension. This avoids forcing every subscription through a lambda
("subscribe_on_event(E_EventId.X, sink)" reads better than
"subscribe(lambda ev: ev.id == E_EventId.X, sink)") AND leaves
room for future O(1) dispatch optimisation (id-keyed subscriptions
can be indexed; category-keyed likewise).


SINK KINDS

Each subscribe_on_* method takes a 'sink' that is one of three things:

    - QUEUE-LIKE OBJECT         any object with a .put_nowait method
                                Delivered immediately via put_nowait.

    - ASYNC CALLABLE            async def handler(event): ...
                                Scheduled via asyncio.create_task();
                                runs on the event loop, non-blocking.

    - SYNC CALLABLE             def handler(event): ...   (or lambda)
                                Dispatched via loop.run_in_executor()
                                to the default thread pool. Runs in a
                                worker thread, in the same Python
                                namespace as the publisher, but OFF
                                the event loop - so it does not block
                                other dispatches.

Anything else (an int, a dict, a non-callable non-queue) raises
TypeError at the SUBSCRIBE call, not later at publish time, so
mistakes surface immediately.

Sync callables share the Python namespace with the publisher and
the event loop, but they run in worker threads. Thread-safety of
any state touched by a sync callback is the callback's responsibility.


PUBLISH IS NON-BLOCKING

publish(event) dispatches to every matching subscription:

    queue sink           sink.put_nowait(event)
    async callable       asyncio.create_task(sink(event))
    sync callable        loop.run_in_executor(None, sink, event)

In all three cases, publish returns as fast as possible. Async
callables run on the event loop; sync callables run in worker
threads; queue puts are immediate.

A consequence: any exception raised inside a callback (async or
sync) is NOT visible to the publisher. Async callback exceptions
surface via asyncio's default task-exception handling. Sync
callback exceptions are captured by the future returned from
run_in_executor; if no one awaits that future, the exception is
swallowed silently. Callers who need stronger guarantees should
use queue sinks and process them in their own task.


UNSUBSCRIBE BY HANDLE

Each subscribe_on_* call returns a Subscription handle. Pass it
to unsubscribe(handle) to remove the subscription. Unsubscribing
a handle that no longer exists returns False rather than raising;
this is consistent with the rest of the VUT design (status returns,
not exceptions, for "not found" cases).
________________________________________________________________________________
"""
import asyncio
import inspect
import sys

from dataclasses import dataclass, field
from typing      import Any, Callable

from vut.engine.event.enums import E_EventCategory
from vut.engine.event.event import Event


# A Subscription handle. Returned from each subscribe_on_*, accepted
# by unsubscribe. Opaque to the caller; internally it carries the
# filter, the sink, and dispatch hints.
@dataclass(frozen=True)
class Subscription:
    handle:    int
    predicate: Callable[[Event], bool]      # always normalised to a predicate
    sink:      Any                          # async callable, sync callable, or queue-like
    is_queue:  bool                         # True if sink has put_nowait
    is_async:  bool                         # True if sink is a coroutine function
                                            # (mutually exclusive with is_queue)


class Router:
    """In-process publish-subscribe for Events.

    See module header for design rationale. Public API:

        subscribe_on_event(event_id, sink)    -> Subscription
        subscribe_on_category(category, sink) -> Subscription
        subscribe_on_predicate(pred, sink)    -> Subscription
        unsubscribe(subscription)             -> bool
        publish(event)                        -> None  (non-blocking)
    """

    def __init__(self):
        self._subscriptions: dict[int, Subscription] = {}
        self._next_handle:   int                     = 0

    # ----------------------------------------------------------------
    # Subscription
    # ----------------------------------------------------------------

    def subscribe_on_event(self,
                           event_id,
                           sink:     Any) -> Subscription:
        """RETURN: Subscription, the handle for this subscription.

        Subscribes 'sink' to receive every Event whose .id equals
        event_id. The event_id may be given as:

            - the class itself:   subscribe_on_event(TaskDoneEvent, sink)
            - the id string:      subscribe_on_event("TaskDoneEvent", sink)

        The class form is recommended at the call site - it is type-
        checked at import (typos surface immediately) and refactor-
        friendly (renaming a class is one IDE operation). The string
        form is available for dynamic dispatch from configuration or
        from wire data.

        'sink' may be an async callable, a sync callable, or a queue-
        like object (anything with put_nowait); TypeError is raised
        here if it is none of those.
        """
        # Normalise: a class -> its .id string. Anything else, accept
        # as-is (and let the predicate fail to match if it's garbage).
        if isinstance(event_id, type) and issubclass(event_id, Event):
            id_str = event_id.id
        else:
            id_str = event_id

        return self._add(
            predicate = lambda ev, eid=id_str: ev.id == eid,
            sink      = sink,
        )

    def subscribe_on_category(self,
                              category: E_EventCategory,
                              sink:     Any) -> Subscription:
        """RETURN: Subscription, the handle for this subscription.

        Subscribes 'sink' to receive every Event whose .category
        equals 'category'. See subscribe_on_event for sink rules.
        """
        return self._add(
            predicate = lambda ev, cat=category: ev.category is cat,
            sink      = sink,
        )

    def subscribe_on_predicate(self,
                               predicate: Callable[[Event], bool],
                               sink:      Any) -> Subscription:
        """RETURN: Subscription, the handle for this subscription.

        Subscribes 'sink' to receive every Event for which
        predicate(event) returns True. Use this for filters that
        don't fit subscribe_on_event or subscribe_on_category
        (multi-field filters, source-id filters, workload-membership
        filters, etc.).
        """
        return self._add(predicate=predicate, sink=sink)

    def unsubscribe(self, subscription: Subscription) -> bool:
        """RETURN: True,  if the subscription was removed.
                   False, if the handle was unknown (already removed,
                          or never registered with this Router).
        """
        if subscription.handle not in self._subscriptions:
            return False
        del self._subscriptions[subscription.handle]
        return True

    # ----------------------------------------------------------------
    # Publish
    # ----------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """RETURN: None.

        Dispatches event to every matching subscriber. NON-BLOCKING:

            - Queue sinks receive the event via put_nowait().
            - Callback sinks are scheduled via asyncio.create_task();
              publish does NOT await them.

        Exceptions from a predicate are caught and logged to stderr;
        the offending subscription is skipped for this event but
        remains in the table. Exceptions from a queue's put_nowait
        (e.g. QueueFull) are caught and logged; the event is dropped
        for that subscriber.

        Exceptions inside scheduled callbacks are NOT visible here;
        they surface via asyncio's default task-exception handling.
        """
        # Snapshot the subscriptions so that handlers that
        # subscribe/unsubscribe during dispatch do not mutate the
        # collection we are iterating.
        for sub in tuple(self._subscriptions.values()):
            try:
                matched = sub.predicate(event)
            except Exception as e:
                print("Router.publish: predicate raised on subscription %d: %s"
                      % (sub.handle, e), file=sys.stderr)
                continue

            if not matched:
                continue

            if sub.is_queue:
                try:
                    sub.sink.put_nowait(event)
                except Exception as e:
                    print("Router.publish: queue put_nowait failed on "
                          "subscription %d: %s" % (sub.handle, e),
                          file=sys.stderr)
            elif sub.is_async:
                try:
                    asyncio.create_task(sub.sink(event))
                except RuntimeError as e:
                    # No running event loop. Programming error at the
                    # caller's side (publish called outside an async
                    # context).
                    print("Router.publish: cannot schedule async callback "
                          "for subscription %d (no running loop): %s"
                          % (sub.handle, e), file=sys.stderr)
            else:
                # Sync callable: run in the default thread pool executor.
                # Same Python namespace (no IPC), but runs off the event
                # loop thread so it does NOT block other dispatches or
                # the rest of the event loop. Thread-safety of any state
                # touched by the callback is the callback's own concern.
                try:
                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(None, sub.sink, event)
                except RuntimeError as e:
                    print("Router.publish: cannot dispatch sync callback "
                          "for subscription %d (no running loop): %s"
                          % (sub.handle, e), file=sys.stderr)

    # ----------------------------------------------------------------
    # Introspection (mainly for tests and diagnostics)
    # ----------------------------------------------------------------

    def __len__(self) -> int:
        """RETURN: int, number of active subscriptions."""
        return len(self._subscriptions)

    def __contains__(self, subscription: Subscription) -> bool:
        """RETURN: True,  if subscription is active in this Router.
                   False, otherwise.
        """
        return subscription.handle in self._subscriptions

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    def _add(self, predicate, sink) -> Subscription:
        """RETURN: Subscription, the handle for the new entry.

        Validates the sink kind (queue-like / async-callable / sync-
        callable / none-of-the-above) and assigns a unique handle.
        TypeError on an unrecognised sink so mistakes are caught at
        subscribe time, not at first publish.
        """
        is_queue = self._is_queue_like(sink)
        is_async = False

        if not is_queue:
            if not callable(sink):
                raise TypeError(
                    "Router subscription sink must be a callable or an "
                    "object with put_nowait(); got %s" % type(sink).__name__
                )
            is_async = inspect.iscoroutinefunction(sink)
            # Sync callables ARE accepted: they will be dispatched via
            # run_in_executor at publish time, so they run in a worker
            # thread and do not block the event loop.

        handle = self._next_handle
        self._next_handle += 1

        sub = Subscription(handle=handle, predicate=predicate,
                           sink=sink, is_queue=is_queue,
                           is_async=is_async)
        self._subscriptions[handle] = sub
        return sub

    @staticmethod
    def _is_queue_like(obj) -> bool:
        """RETURN: True, if obj has a put_nowait method (asyncio.Queue,
                        multiprocessing.Queue, queue.Queue, etc.).
                  False, otherwise.

        Duck-typed; we do NOT check for a specific class.
        """
        return callable(getattr(obj, "put_nowait", None))
