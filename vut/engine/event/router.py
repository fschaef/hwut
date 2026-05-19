"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: EventRouter - one-to-many outgoing dispatch over Terminals.

The Router holds a set of Terminals (each a one-to-one peer connection)
and uses an internal Dispatcher to decide which Terminal(s) receive
each published Event.

A Router is NOT a Terminal. A Terminal is a single peer connection; a
Router is a hub that knows about many. Both use an EventDispatcher
internally, for different ends of the same matching problem:

    Terminal's Dispatcher    -- incoming Events fan out to local handlers
    Router's Dispatcher      -- outgoing Events fan out to peer Terminals


PUBLIC SHAPE

    router = EventRouter()

    handle = router.add_entry(predicate, terminal)
    handle = router.add_entry(predicate, terminal,
                              source_terminal_list=[t1, t2])
    router.remove_entry(handle)    # -> bool

    router.publish(event)          # synchronous; non-blocking


SOURCE FILTERING

add_entry accepts an optional source_terminal_list. When set, the
target Terminal only receives Events that came from one of the named
source Terminals (or from local publish() calls if 'None' appears in
the list).

When source_terminal_list is None (the default), the target Terminal
receives matching Events regardless of source.

This supports asymmetric topologies: e.g. "forward Compiler events
from the network-incoming Terminal to the WFM-internal handlers, but
NOT to the network-outgoing Terminals" - which would otherwise loop.


PREDICATE-FIRST ORDERING

add_entry(predicate, terminal, ...) puts the predicate first so the
call site reads as "what to route" then "where to". This matches the
mental model of a router: a rule plus a destination.


CALL FROM TERMINAL'S RECEIVE SIDE

A Terminal that wants to forward incoming Events into the Router can
subscribe the Router's .publish_from() method on its receive
Dispatcher:

    terminal.dispatcher.subscribe_on_predicate(
        lambda ev: True,
        lambda ev: router.publish_from(terminal, ev),
    )

Or pass source-aware publish for use in such forwards.
________________________________________________________________________________
"""
import sys

from typing  import Callable, Optional

from vut.engine.event.dispatcher import EventDispatcher
from vut.engine.event.event      import Event
from vut.engine.event.terminal   import EventTerminal


class EventRouter:
    """Hub of Terminals; routes outgoing Events to those whose predicate matches.

    See module header for the contract. Internally a Dispatcher whose
    sinks are wrappers around Terminals (carrying source filter, etc).
    """

    def __init__(self):
        self._dispatcher = EventDispatcher(enforce_async_callbacks_f=False)
        self._entries:     dict[int, "EventRouterEntry"] = {}
        self._next_id:     int                       = 0

    # ----------------------------------------------------------------
    # Registration
    # ----------------------------------------------------------------
    def add_entry(self,
                  predicate:            Callable[[Event], bool],
                  terminal:             EventTerminal,
                  source_terminal_list: Optional[list] = None) -> int:
        """RETURN: int, entry handle for later remove_entry().

        Registers 'terminal' as a destination for Events matching
        'predicate'. If source_terminal_list is given, the Event is
        only routed to 'terminal' when it ORIGINATED from one of the
        listed source Terminals (or from a local publish() call when
        None appears in the list).

        The 'predicate' is a callable Event -> bool; same form as on
        the Dispatcher.
        """
        handle = self._next_id
        self._next_id += 1

        entry = EventRouterEntry(handle               = handle,
                                 terminal             = terminal,
                                 predicate            = predicate,
                                 source_terminal_list = source_terminal_list)
        entry._router_dispatcher = self._dispatcher
        self._entries[handle] = entry

        # Register the entry's __call__ as a SINK in the dispatcher.
        # The entry is callable (sync) and forwards to terminal.send.
        sub = self._dispatcher.subscribe_on_predicate(
            predicate = lambda ev, e=entry: e._matches(ev),
            sink      = entry,
        )
        entry.subscription = sub
        return handle

    def remove_entry(self, handle: int) -> bool:
        """RETURN: True,  if the entry was removed.
                   False, if the handle is unknown.
        """
        entry = self._entries.pop(handle, None)
        if entry is None:
            return False
        if entry.subscription is not None:
            self._dispatcher.unsubscribe(entry.subscription)
        return True

    # ----------------------------------------------------------------
    # Publish
    # ----------------------------------------------------------------
    def publish(self, event: Event) -> None:
        """RETURN: None.

        Dispatches event from a LOCAL source (no source Terminal).
        For source-aware routing (when an Event came from an incoming
        Terminal that should not loop back), use publish_from().
        """
        self.publish_from(None, event)

    def publish_from(self, source_terminal, event: Event) -> None:
        """RETURN: None.

        Dispatches 'event' as if it originated from 'source_terminal'.
        Terminals whose source_terminal_list excludes 'source_terminal'
        will NOT receive it. Use source_terminal=None for events
        produced locally (not received from any Terminal).
        """
        # Tag the event with a transient source marker. We attach via
        # a thread-unsafe attribute on the dispatcher itself, since the
        # dispatcher iterates synchronously - the marker is read by
        # _matches() while iterating.
        self._dispatcher._current_source = source_terminal      # type: ignore
        try:
            self._dispatcher.dispatch(event)
        finally:
            self._dispatcher._current_source = None             # type: ignore

    # ----------------------------------------------------------------
    # Introspection
    # ----------------------------------------------------------------

    def __len__(self) -> int:
        """RETURN: int, number of registered Terminals."""
        return len(self._entries)


class EventRouterEntry:
    """Internal: one (predicate, terminal, source_filter) row.

    Callable as a sync sink: when invoked with an Event, it schedules
    the terminal.send(event) coroutine.
    """

    def __init__(self, handle, terminal, predicate, source_terminal_list):
        """RETURN: a new EventRouterEntry."""
        self.handle               = handle
        self.terminal             = terminal
        self.predicate            = predicate
        self.source_terminal_list = source_terminal_list
        self.subscription         = None
        # Will be patched at registration time. The router sets
        # _current_source on its dispatcher before each dispatch.
        self._router_dispatcher   = None

    def _matches(self, event: Event) -> bool:
        """RETURN: True if this entry should fire on 'event'.

        Combines the user-supplied predicate with the source-Terminal
        filter (if any).
        """
        if not self.predicate(event):
            return False
        if self.source_terminal_list is None:
            return True
        # We need the source. It is stamped on the dispatcher by the
        # Router just before dispatch.
        source = getattr(self._router_dispatcher, "_current_source", None)
        return source in self.source_terminal_list

    def __call__(self, event: Event) -> None:
        """RETURN: None.

        Forwards 'event' to the bound Terminal asynchronously.
        Called by the Dispatcher when this entry matches.
        """
        # The Terminal's send is async; schedule it.
        import asyncio
        try:
            asyncio.create_task(self.terminal.send(event))
        except RuntimeError as e:
            print("EventRouterEntry.__call__: cannot forward to terminal "
                  "(no running loop): %s" % e, file=sys.stderr)
