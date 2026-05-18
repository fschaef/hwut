"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Event identity, data, dispatch, transport, and routing.

This package provides:

    Events:
      -- E_EventCategory             subsystem categorisation
      -- Event                       base class
      -- TaskStartedEvent, ...       concrete events
      -- CLASS_BY_ID                 module-level id -> class table
      -- EventIdCollision            raised on duplicate event class name

    Transport (single peer):
      -- E_TransportKind             enum of transport flavours
      -- EventChannelParameter       single-class ECP with for_* factories
      -- EventChannel                ABC + concrete subclasses:
                                       AsyncQueueChannel, ThreadQueueChannel,
                                       ProcessQueueChannel, RemoteChannel
      -- EventTerminal               one Channel + receive Dispatcher

    Dispatch and routing:
      -- EventDispatcher             predicate-to-sink matching
      -- Subscription                opaque handle from EventDispatcher
      -- EventRouter                 hub of Terminals; predicate-driven
                                     outgoing routing

    Wire transport (used internally by ProcessQueueChannel, RemoteChannel):
      -- Marshaller                  serialise/deserialise

ORGANISATION:

    enums.py                E_EventCategory
    event.py                Event base class, CLASS_BY_ID, EventIdCollision
    events.py               Concrete Event subclasses
    marshaller.py           Marshaller
    dispatcher.py           EventDispatcher, Subscription
    channel.py              EventChannel ABC + concrete subclasses
    channel_parameter.py    EventChannelParameter, E_TransportKind
    terminal.py             EventTerminal
    router.py               EventRouter

For design rationale see README.txt.
For discussion history see DISCUSSIONS.txt.

PYDANTIC V2 IS REQUIRED for TypeAdapter-based validation on Events.
________________________________________________________________________________
"""
from .enums              import E_EventCategory
from .event              import Event, CLASS_BY_ID, EventIdCollision, all_event_classes
from .events             import (TaskStartedEvent,
                                 TaskDoneEvent,
                                 TaskFailedEvent,
                                 TaskProgressEvent,
                                 TaskCancelledEvent,
                                 CompilerNoSourceEvent,
                                 CompilerDoneEvent,
                                 ArtifactAvailableEvent,
                                 ArtifactImpossibleEvent,
                                 WorkflowTaskCancelledEvent)
from .marshaller         import Marshaller
from .dispatcher         import EventDispatcher, Subscription
from .channel            import (EventChannel,
                                 AsyncQueueChannel,
                                 ThreadQueueChannel,
                                 ProcessQueueChannel,
                                 RemoteChannel)
from .channel_parameter  import EventChannelParameter, E_TransportKind
from .terminal           import EventTerminal
from .router             import EventRouter

__all__ = [
    # Events
    "E_EventCategory",
    "Event",
    "EventIdCollision",
    "TaskStartedEvent",
    "TaskDoneEvent",
    "TaskFailedEvent",
    "TaskProgressEvent",
    "TaskCancelledEvent",
    "CompilerNoSourceEvent",
    "CompilerDoneEvent",
    "ArtifactAvailableEvent",
    "ArtifactImpossibleEvent",
    "WorkflowTaskCancelledEvent",
    "CLASS_BY_ID",
    "all_event_classes",
    # Transport
    "E_TransportKind",
    "EventChannelParameter",
    "EventChannel",
    "AsyncQueueChannel",
    "ThreadQueueChannel",
    "ProcessQueueChannel",
    "RemoteChannel",
    "EventTerminal",
    # Dispatch / routing
    "EventDispatcher",
    "Subscription",
    "EventRouter",
    # Marshaller
    "Marshaller",
]
