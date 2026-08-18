"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Global transport for Events.

The Marshaller is the one place that knows how to move an Event across
a process or machine boundary. Class-as-singleton: all methods are
classmethods/staticmethods, no instances exist.

    Marshaller.serialize(event)    -> wire    (dict)
    Marshaller.deserialize(wire)   -> Event   (or None on failure)


WIRE FORMAT (Pattern A: external tag / envelope)

    {
        "id":   "EVENT_INFRA.EventTerminalUp",         # composite id
        "data": {"timestamp": 100.0},                  # all fields
    }

The "id" is the Event subclass's composite identity
("<category>.<class_name>"). Deserialise looks the class up via
event.CLASS_BY_ID.lookup() (one flat-dict access).


SPECIALISTS

Per-event-id overrides live in _SPECIALISTS, keyed by the full wire
id ("CATEGORY.ClassName"). Currently empty. Adding a specialist
requires editing this file.

Producer and consumer in a pair of communicating contexts share the
same Marshaller configuration AUTOMATICALLY because they share the
same build.


FUTURE DIRECTION: Construct

Specialists are a natural place to plug in `construct`
(https://construct.readthedocs.io) for compact binary wire formats.
Construct and Pydantic compose cleanly across a wire boundary:
Pydantic handles structured-data validation (per-field types,
constraints, JSON round-trip) while Construct handles binary layout
(bit-packing, endianness, alignment, length prefixes). For events
where every byte matters - high-frequency events on a fast network,
say - a Construct-based specialist can replace the default JSON
envelope without touching anything else in the package. Left as a
note for whoever profiles the wire and finds it worth doing.
________________________________________________________________________________
"""
import sys

from types   import MappingProxyType
from typing  import Callable

from vut.engine.event.event import Event, CLASS_BY_ID

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

    # Specialists override the default per composite event id. Empty
    # by default. Add an entry here when an event needs custom
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

        # Composite id "<category>.<class_name>"; look up the class.
        event_cls = CLASS_BY_ID.lookup(event_id)
        if event_cls is None:
            print("Marshaller.deserialize: unknown id %r" % event_id,
                  file=sys.stderr)
            return None

        specialist = cls._SPECIALISTS.get(event_id)
        if specialist is not None:
            return specialist[1](wire)
        return cls._deserialize_default(wire, event_cls)

    # ------------------------------------------------------------------
    # Default scheme
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_default(event: Event) -> dict:
        """RETURN: dict, the default envelope form of event.

        Two-key envelope: id (composite "<category>.<name>") + data.
        """
        return {
            "id":   event.id,
            "data": event.as_dict(),
        }

    @staticmethod
    def _deserialize_default(wire: dict, event_cls: type) -> "Event | None":
        """RETURN: Event,  if the data validates against the resolved class.
                   None,   on malformed envelope or validation failure.
        """
        try:
            data = wire["data"]
        except (KeyError, TypeError) as e:
            print("Marshaller.deserialize: malformed envelope (%s)" % e,
                  file=sys.stderr)
            return None

        # Delegate to the class's from_dict, which uses its TypeAdapter
        # and writes its own diagnostic on failure.
        return event_cls.from_dict(data)
