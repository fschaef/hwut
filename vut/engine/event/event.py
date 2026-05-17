"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Event base class.

An Event is a frozen dataclass holding the data for one occurrence of
one event kind. Every concrete event in the system is a subclass of
Event with:

    -- a category class attribute (E_EventCategory)
    -- instance-level fields (the data)
    -- a __str__ override that renders the event human-readably

IDENTITY IS DERIVED FROM THE CLASS NAME.

Each concrete subclass automatically gets an .id class attribute
equal to its own __name__ (e.g. TaskDoneEvent.id == "TaskDoneEvent").
There is NO separate E_EventId enum to maintain in parallel.

Adding a new event is ONE step: define the subclass. The id, the
TypeAdapter, and the CLASS_BY_ID registration all happen
automatically in __init_subclass__.

UNIQUENESS IS ENFORCED AT CLASS CREATION.

All concrete Event subclasses share a single namespace via the
module-level CLASS_BY_ID dict. Two subclasses with the same name
collide; this is a programmer error (it would silently misroute
events) so it raises EventIdCollision at class-definition time.
The collision cannot be handled at runtime - the module would not
finish importing.

Note: SUBCLASSES sharing a name with their PARENT do not collide
because the parent is already registered under that name. Inheriting
without renaming is unusual; if it happens, the subclass will collide
with itself and raise. Concrete subclasses should always have unique
class names.


WIRE INTERFACE

Two methods are the bridge to/from the wire:

    event.as_dict()                 -> dict   (just the data fields)
    SomeEventClass.from_dict(d)     -> Event  (or None on validation error)

The Marshaller wraps these with an envelope carrying the id; see
marshaller.py.


VERSIONING (deferred design)

Event identity is now the class name itself; renaming a class
breaks every consumer producing or consuming that class on the
wire. This makes "do not rename event types lightly" a hard
discipline rather than a soft convention.

Cross-build replay is UNDEFINED. See DISCUSSIONS.txt for the full
versioning conversation.
________________________________________________________________________________
"""
import sys
import time

from dataclasses import dataclass, field
from typing      import ClassVar

from pydantic    import TypeAdapter, ValidationError

from vut.engine.event.enums import E_EventCategory


# ============================================================================
# Module-level registry of all concrete Event subclasses, keyed by class name.
# Populated by Event.__init_subclass__ as each subclass is defined.
# ============================================================================
CLASS_BY_ID: dict[str, type] = {}


class EventIdCollision(Exception):
    """Raised when two Event subclasses share a class name.

    A programmer error caught at class-definition time. It cannot be
    handled at runtime - the module that defined the offending second
    class will not finish importing.
    """
    pass


@dataclass(frozen=True, kw_only=True)
class Event:
    """Base class for all events.

    Subclasses declare:
        -- a category class attribute (E_EventCategory)
        -- instance fields (the data)
        -- a __str__ override

    The .id class attribute is auto-derived from the class name in
    __init_subclass__. See module header for design rationale.
    """

    # Class-level metadata. .id is set automatically in __init_subclass__
    # to the subclass's __name__. .category MUST be overridden by each
    # concrete subclass.
    id:       ClassVar[str]             = None     # auto-set
    category: ClassVar[E_EventCategory] = None     # set by subclasses

    # Pydantic adapter cache. Created lazily on first use; see
    # _get_adapter().
    _adapter: ClassVar = None

    # The one instance field on the base.
    timestamp: float = field(default_factory=time.monotonic)

    @classmethod
    def _get_adapter(cls):
        """RETURN: TypeAdapter, the Pydantic adapter for this concrete class.

        Created on first use and cached on the class itself. Per-class
        flyweight: every instance of one Event subclass shares the
        same adapter object.

        Created lazily (NOT in __init_subclass__) because
        __init_subclass__ runs before @dataclass has finished
        processing the subclass's fields; an eager adapter would miss
        those fields.
        """
        # Use __dict__ lookup (not attribute lookup) so that we do NOT
        # inherit a parent class's adapter - each subclass gets its own.
        if '_adapter' not in cls.__dict__ or cls.__dict__['_adapter'] is None:
            cls._adapter = TypeAdapter(cls)
        return cls._adapter

    def __init_subclass__(cls, **kwargs):
        """Auto-derive .id from class name, enforce uniqueness, register.

        Sets cls.id = cls.__name__ and registers cls in CLASS_BY_ID.
        Raises EventIdCollision if the name is already taken.
        """
        super().__init_subclass__(**kwargs)

        name = cls.__name__
        if name in CLASS_BY_ID:
            existing = CLASS_BY_ID[name]
            raise EventIdCollision(
                "Event subclass name %r is already registered to %s.%s; "
                "cannot also register %s.%s. All Event subclasses must "
                "have unique class names across the whole system." % (
                    name,
                    existing.__module__, existing.__qualname__,
                    cls.__module__,      cls.__qualname__,
                )
            )

        cls.id = name
        CLASS_BY_ID[name] = cls

    def __str__(self) -> str:
        """RETURN: str, human-readable rendering.

        The base implementation is a generic fallback. Subclasses
        SHOULD override this with a kind-specific message.
        """
        return "%s%s" % (type(self).__name__, vars(self))

    def __repr__(self) -> str:
        """RETURN: str, technical representation for debugging."""
        return "%s(%s)" % (
            type(self).__name__,
            ", ".join("%s=%r" % (k, v) for k, v in vars(self).items())
        )

    def as_dict(self) -> dict:
        """RETURN: dict, the data fields of this event as a plain dict.

        Uses the class's Pydantic adapter to serialise. The result is
        a plain Python dict, JSON-safe (enums -> their values, etc).
        """
        return type(self)._get_adapter().dump_python(self, mode="json")

    @classmethod
    def from_dict(cls, d: dict) -> "Event | None":
        """RETURN: cls instance, if d validates against cls's schema.
                   None,         on validation failure (stderr diagnostic).

        This is called on a CONCRETE subclass, e.g.
        TaskDoneEvent.from_dict({...}). The Marshaller dispatches to
        the right subclass via CLASS_BY_ID before calling this.
        """
        try:
            return cls._get_adapter().validate_python(d)
        except ValidationError as e:
            err = e.errors()[0]
            print("Event.from_dict failed for %s: field %s, type %s"
                  % (cls.__name__, err["loc"], err["type"]),
                  file=sys.stderr)
            return None

    def serialize(self) -> dict:
        """RETURN: dict, the wire form of this event.

        Thin delegation to Marshaller.serialize(self). The Marshaller
        is a global class-as-singleton; no configuration is needed
        at the call site.
        """
        # Local import to break the event <-> marshaller cycle at module
        # load. The Marshaller imports Event, CLASS_BY_ID, etc.
        from vut.engine.event.marshaller import Marshaller
        return Marshaller.serialize(self)

    @classmethod
    def deserialize(cls, wire: dict) -> "Event | None":
        """RETURN: Event, if wire decodes to a valid event of a known kind.
                   None,  on any failure (stderr diagnostic).

        Classmethod because there is no Event instance before decoding.
        Delegates to Marshaller.deserialize(wire), which dispatches on
        the wire's id to the right Event subclass.
        """
        from vut.engine.event.marshaller import Marshaller
        return Marshaller.deserialize(wire)


def all_event_classes() -> list:
    """RETURN: list[type[Event]], every concrete Event subclass.

    Convenience for tests and introspection. Order is registration
    order (insertion order in CLASS_BY_ID).
    """
    return list(CLASS_BY_ID.values())
