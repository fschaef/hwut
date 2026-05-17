"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Event identity, data, dispatch, and transport for the VUT system.

This package provides:

    -- E_EventCategory       functional grouping by subsystem
    -- Event                 base class for all events (frozen dataclass)
    -- TaskStartedEvent      |
    -- TaskDoneEvent         |
    -- TaskFailedEvent       |  concrete events; instantiate directly
    -- TaskProgressEvent     |
    -- TaskCancelledEvent    |
    -- CompilerNoSourceEvent
    -- CompilerDoneEvent
    -- ArtifactAvailableEvent
    -- ArtifactImpossibleEvent
    -- WorkflowTaskCancelledEvent
    -- CLASS_BY_ID           module-level dispatch table (id -> class)
    -- EventIdCollision      exception raised on duplicate event class name
    -- Marshaller            transport: serialise / deserialise events
    -- Router                in-process publish-subscribe by id / category / predicate
    -- Subscription          opaque handle returned by Router.subscribe_*

ORGANISATION:

    enums.py        E_EventCategory
    event.py        Event base class, CLASS_BY_ID, EventIdCollision
    events.py       Concrete Event subclasses
    marshaller.py   Marshaller
    router.py       Router, Subscription

NOTE: Event identity is derived from the class name. There is no
E_EventId enum; .id on any concrete Event is its class __name__
(e.g. TaskDoneEvent.id == "TaskDoneEvent"). Uniqueness is enforced
at class-creation time via Event.__init_subclass__; a duplicate
class name raises EventIdCollision.

For design rationale see README.txt.
For discussion history see DISCUSSIONS.txt.

PYDANTIC V2 IS REQUIRED for TypeAdapter-based validation and
serialisation on the Event dataclasses.
________________________________________________________________________________
"""
from .enums       import E_EventCategory
from .event       import Event, CLASS_BY_ID, EventIdCollision, all_event_classes
from .events      import (TaskStartedEvent,
                          TaskDoneEvent,
                          TaskFailedEvent,
                          TaskProgressEvent,
                          TaskCancelledEvent,
                          CompilerNoSourceEvent,
                          CompilerDoneEvent,
                          ArtifactAvailableEvent,
                          ArtifactImpossibleEvent,
                          WorkflowTaskCancelledEvent)
from .marshaller  import Marshaller
from .router      import Router, Subscription

__all__ = [
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
    "Marshaller",
    "Router",
    "Subscription",
]
