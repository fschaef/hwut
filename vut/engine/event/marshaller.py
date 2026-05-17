"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Global transport for Events.

The Marshaller is the one place that knows how to move an Event across
a process or machine boundary. Class-as-singleton: all methods are
classmethods/staticmethods, no instances exist.

    Marshaller.serialize(event)    -> wire    (dict)
    Marshaller.deserialize(wire)   -> Event   (or None on failure)

DESIGN: GLOBAL CLASS-AS-SINGLETON

There is no Marshaller() constructor. Specialists are declared at
module load time in the _SPECIALISTS class attribute (currently
empty). Producer and consumer in any pair of communicating contexts
share the same Marshaller configuration AUTOMATICALLY, because they
share the same build (same VUT version). No registration handshake,
no synchronisation plumbing.

Adding a specialist for a new event requires editing this file.
The benefit is that nothing else requires editing - and
synchronisation comes for free.


DEFAULT WIRE FORMAT (Pattern A: external tag / envelope)

    {
        "id":   "TaskDoneEvent",                       # class name verbatim
        "data": {"task_id": 42, "duration_s": 1.5,     # all fields
                 "timestamp": 100.0},                  # from the class
    }

The "id" carries the Event subclass's __name__ verbatim. The Event
base class (see event.py) sets each subclass's .id to its __name__
in __init_subclass__ and registers it in CLASS_BY_ID.

The "data" is the result of the Event class's TypeAdapter.dump_python();
deserialisation looks up the class via CLASS_BY_ID[id] and calls its
TypeAdapter.validate_python() through Event.from_dict().
________________________________________________________________________________
"""
import sys

from types   import MappingProxyType
from typing  import Callable

from vut.engine.event.event   import Event, CLASS_BY_ID


SerializeFn   = Callable[[Event], dict]
DeserializeFn = Callable[[dict],  "Event | None"]


class Marshaller:
    """Global transport for Events.

    Call sites:
        wire  = Marshaller.serialize(event)
        event = Marshaller.deserialize(wire)

    Or via Event's own methods, which delegate here:
        wire  = event.serialize()
        event = Event.deserialize(wire)
    """

    # Specialists override the default per event id (the class name).
    # Currently empty. Add an entry here when an event needs custom
    # transport (compression, schema bridging, etc.).
    _SPECIALISTS: MappingProxyType = MappingProxyType({})

    @classmethod
    def serialize(cls, event: Event) -> dict:
        """RETURN: dict, the wire form of event.

        Routes to a specialist for event.id if declared in
        _SPECIALISTS; otherwise uses the default envelope scheme.
        """
        specialist = cls._SPECIALISTS.get(event.id)
        if specialist is not None:
            return specialist[0](event)
        return cls._serialize_default(event)

    @classmethod
    def deserialize(cls, wire: dict) -> "Event | None":
        """RETURN: Event,  if wire decodes to a valid event of a known kind.
                   None,   if the id is unknown, the data fails
                          validation, or the envelope is malformed.
        """
        try:
            event_id = wire["id"]
        except (KeyError, TypeError) as e:
            print("Marshaller.deserialize: malformed envelope (%s)" % e,
                  file=sys.stderr)
            return None

        if event_id not in CLASS_BY_ID:
            print("Marshaller.deserialize: unknown id %r" % event_id,
                  file=sys.stderr)
            return None

        specialist = cls._SPECIALISTS.get(event_id)
        if specialist is not None:
            return specialist[1](wire)
        return cls._deserialize_default(wire, event_id)

    # ------------------------------------------------------------------
    # Default scheme
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_default(event: Event) -> dict:
        """RETURN: dict, the default envelope form of event.

        Two-key envelope: id (class name verbatim) + data (all fields).
        """
        return {
            "id":   event.id,
            "data": event.as_dict(),
        }

    @staticmethod
    def _deserialize_default(wire: dict, event_id: str) -> "Event | None":
        """RETURN: Event,  if the data validates against the right Event subclass.
                   None,   on validation failure, missing data, or unknown class.
        """
        event_cls = CLASS_BY_ID.get(event_id)
        if event_cls is None:
            print("Marshaller.deserialize: no Event class for %r" % event_id,
                  file=sys.stderr)
            return None

        try:
            data = wire["data"]
        except (KeyError, TypeError) as e:
            print("Marshaller.deserialize: malformed envelope for %r (%s)"
                  % (event_id, e), file=sys.stderr)
            return None

        # Delegate to the class's from_dict, which uses its TypeAdapter
        # and writes its own diagnostic on failure.
        return event_cls.from_dict(data)
