"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Event identity, data, dispatch, and transport for VUT.

This package is a TOOLKIT, not a registry of application events.
Subsystems (workflow, compile, network, tests) define their own
events in their own modules using the `with category("..."):`
context manager.

The only events shipped here are LIFECYCLE events that an
EventTerminal emits on the wire about itself:

    EventTerminalUp     emitted on receive-loop entry; the symmetric
                        Up/Up handshake at start() uses this.
    EventTerminalDown   emitted on deliberate shutdown.

Both live in the EVENT_INFRA category.

This package provides:

    -- Event                 base class for all events (frozen dataclass)
    -- category              context manager for declaring a category

    -- EventTerminalUp       transport lifecycle event
    -- EventTerminalDown     transport lifecycle event

    -- CLASS_BY_ID           flat registry (composite wire id -> class)
    -- lookup_event_class    resolve composite wire id to class
    -- all_event_classes     list every registered subclass
    -- all_categories        list every category with registrations
    -- events_in_category    list events in one category

    -- EventIdCollision                       raised on duplicate name within a category
    -- EventDefinitionOutsideCategoryContext  raised on Event defined outside any category
    -- EventRegistrationLocked                raised on registration after lock

    -- Marshaller            transport: serialise / deserialise events
    -- EventDispatcher       predicate-to-sink matching
    -- EventChannel          ABC for bidirectional transport
    -- EventChannelParameter handle to construct Channels from spawning context
    -- EventTerminal         one end of a Channel + receive-side Dispatcher
                            (supports `with EventTerminal(ecp) as t:`)
    -- EventRouter           Dispatcher of Terminals (predicate routing)

CATEGORIES ARE USER-DEFINED STRINGS:

    with category("MY_SUBSYSTEM"):
        class EventSomething(Event):
            ...

Categories are not an enum. Multiple files may contribute to the
same category. Two events with the same class name in the same
category raise EventIdCollision. Two events with the same class
name in different categories are fine (their wire ids differ).

The wire id is "<category>.<class_name>", e.g. "EVENT_INFRA.EventTerminalUp".

REGISTRATION LOCK:

After a system's startup sequence has imported every module whose
events should exist in this run, call Event.lock_registration() to
seal the registry. After lock, opening a category or defining an
Event raises EventRegistrationLocked.

For design rationale see README.txt.
For discussion history see DISCUSSIONS.txt.

PYDANTIC V2 IS REQUIRED for TypeAdapter-based validation and
serialisation on the Event dataclasses.
________________________________________________________________________________
"""
from .event              import (Event,
                                 category,
                                 CLASS_BY_ID,
                                 EventIdCollision,
                                 EventDefinitionOutsideCategoryContext,
                                 EventRegistrationLocked)
from .events             import (EventTerminalUp,
                                 EventTerminalDown,
                                 EventInfo)
from .dispatcher         import EventDispatcher, Subscription
from .terminal           import EventTerminal
from .router             import EventRouter
from .channel.marshaller import Marshaller
from .channel.channel    import (EventChannel,
                                 AsyncChannel,
                                 ThreadChannel,
                                 ProcessChannel,
                                 RemoteChannel)
from .channel.parameter  import EventChannelParameter

__all__ = [
    # Core
    "Event",
    "category",
    "CLASS_BY_ID",
    "EventIdCollision",
    "EventDefinitionOutsideCategoryContext",
    "EventRegistrationLocked",
    # Lifecycle events
    "EventTerminalUp",
    "EventTerminalDown",
    "EventInfo",
    # Transport
    "Marshaller",
    "EventDispatcher",
    "Subscription",
    "EventChannel",
    "AsyncChannel",
    "ThreadChannel",
    "ProcessChannel",
    "RemoteChannel",
    "EventChannelParameter",
    "EventTerminal",
    "EventRouter",
]

