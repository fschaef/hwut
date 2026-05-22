"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Event base class, registration, category context, lock.

An Event is a frozen dataclass holding the data for one occurrence of
one event kind. Concrete event classes are registered into a category
via a context manager:

    with category("WORKFLOW"):
        class EventTaskStarted(Event):
            test_name: str
            ...
        class EventTaskDone(Event):
            ...

Note: concrete subclasses are written WITHOUT a @dataclass decorator.
See "DATACLASS TRANSFORM" below.

IDENTITY:

Each concrete subclass gets:
    .category       set from the open category context
    .id             composite string "<category>.<__name__>"

CLASS_BY_ID is a Registry (a dict subclass) mapping the composite wire
id "<category>.<class_name>" -> Event subclass:
    CLASS_BY_ID["WORKFLOW.EventTaskDone"]   ==   EventTaskDone

The Registry carries the lookup/enumeration behaviour as member
functions (lookup, all_classes, categories, in_category) rather than
as free functions operating on a bare dict.

WIRE ID:

The .id attribute is the wire identifier. E.g.:
    EventTaskDone.id         == "WORKFLOW.EventTaskDone"
    event.id                 == "WORKFLOW.EventTaskDone"

The "." separator is reserved; category strings cannot contain it.


CATEGORY CONTEXT

Categories are user-defined strings. A category is opened with the
`category(name)` context manager; every Event subclass created
inside the `with` block joins that category. Outside any open
category, defining an Event subclass raises
EventDefinitionOutsideCategoryContext.

Multiple files may contribute to the same category (re-opening is
permitted). Nesting is disallowed - one category open at a time.


REGISTRATION LOCK

Once `Event.lock_registration()` has been called, opening a category
or defining an Event subclass raises EventRegistrationLocked. This is
a one-way switch: there is no unlock. The intended usage is for a
system's startup sequence to lock after all required modules have
been imported.


DATACLASS TRANSFORM

Concrete Event subclasses are NOT decorated with @dataclass by their
authors. The metaclass EventMeta applies

    dataclass(frozen=True, kw_only=True)

to every subclass automatically, at class-creation time. This is a
deliberate choice with a specific rationale:

  -- A validator (here: Pydantic, see below) can only see fields that
     dataclass processing has turned into real dataclass fields, i.e.
     entries in cls.__dataclass_fields__. A subclass whose author
     forgot the decorator would have its annotations sit unprocessed
     in __annotations__; the generated __init__ would be the BASE
     class's, and validation/serialisation would SILENTLY drop the
     subclass's own fields at the wire boundary.

  -- Auto-applying the transform in the metaclass removes that
     footgun without forcing the hierarchy onto a heavier base such
     as Pydantic's BaseModel. The decorator still runs - it must, the
     fields depend on it - but the author never writes it and cannot
     forget it.

  -- The transform is applied in EventMeta.__new__ AFTER the class
     body is built, so by the time __dataclass_fields__ is read
     (lazily, by the Pydantic adapter) it is complete.

Consequence for subclass authors: declare fields as plain annotations;
do not add @dataclass; do not pass frozen=/kw_only= yourself.


PYDANTIC

Each concrete class has a per-class TypeAdapter, created lazily on
first use of .as_dict() / .from_dict(). The adapter validates and
serialises the dataclass. It is built lazily (not eagerly) so that
the EventMeta dataclass transform has certainly completed first.
________________________________________________________________________________
"""
import sys
import time

from contextlib  import contextmanager
from dataclasses import dataclass, field
from typing      import ClassVar

from pydantic    import TypeAdapter, ValidationError


# ============================================================================
# Registry
# ============================================================================
class Registry(dict):
    """Registry of all concrete Event subclasses, keyed by composite wire id.

    A dict subclass: keys are the composite wire id strings
    "<category>.<class_name>", values are the Event subclasses. Being a
    dict, it supports the plain mapping operations the registration path
    relies on:

        composite in registry            membership test
        registry[composite] = cls        insertion
        for wire_id in registry: ...      iteration in registration order

    Flat by design: this is exactly what the Marshaller has in hand when
    it parses an incoming wire envelope ("WORKFLOW.EventTaskDone" arrives
    as one string), so .lookup() is a single dict access. Per-category
    enumeration is a derived helper (.in_category()), not the primary
    shape.

    The lookup/enumeration behaviour lives here as member functions
    rather than as free functions operating on a bare dict.
    """

    def register(self, cls) -> None:
        """RETURN: None.

        Insert a concrete Event subclass under its .id. Raises
        EventIdCollision if .id is already taken; the colliding class
        is named in the message.

        Called by Event.__init_subclass__ once .category and .id have
        been stamped on the class.
        """
        composite = cls.id
        if composite in self:
            existing = self[composite]
            raise EventIdCollision(
                "Event subclass name %r is already registered in category %r "
                "to %s.%s; cannot also register %s.%s. Event names must be "
                "unique within a category." % (
                    cls.__name__, cls.category,
                    existing.__module__, existing.__qualname__,
                    cls.__module__,      cls.__qualname__,
                )
            )
        self[composite] = cls

    def lookup(self, wire_id: str) -> "type | None":
        """RETURN: type[Event],  the Event subclass whose .id equals wire_id.
                   None,          if no such class is registered, or if
                                  wire_id is not a string.

        One dict access; wire_id is the composite "<category>.<class_name>"
        exactly as it appears on the wire.
        """
        if not isinstance(wire_id, str):
            return None
        return self.get(wire_id)

    def all_classes(self) -> list:
        """RETURN: list[type[Event]],  every concrete Event subclass in
                                       registration order.

        Convenience for tests and introspection.
        """
        return list(self.values())

    def categories(self) -> list:
        """RETURN: list[str],  every category that has at least one event
                               registered, in first-registration order.

        Walks the registry once and collects unique category prefixes.
        """
        seen     = []
        seen_set = set()
        for wire_id in self:
            cat = wire_id.split(".", 1)[0]
            if cat not in seen_set:
                seen_set.add(cat)
                seen.append(cat)
        return seen

    def in_category(self, category_name: str) -> list:
        """RETURN: list[type[Event]],  every Event subclass registered in the
                                       given category, in registration order.

        Convenience for tests and introspection. Walks the registry once
        and filters on prefix.
        """
        prefix = category_name + "."
        return [cls for wire_id, cls in self.items()
                if wire_id.startswith(prefix)]


# ============================================================================
# Module-level registry instance.
#
# A single Registry shared by the whole process. Event.__init_subclass__
# registers into it; the Marshaller looks classes up out of it.
# ============================================================================
CLASS_BY_ID: Registry = Registry()


# ----------------------------------------------------------------------------
# Internal state:
#   _current_category    name of the currently-open category, or None.
#   _registration_locked True once lock_registration() has been called.
# ----------------------------------------------------------------------------
_current_category:    "str | None" = None
_registration_locked: bool         = False

class EventIdCollision(Exception):
    pass

class EventDefinitionOutsideCategoryContext(Exception):
    pass

class EventRegistrationLocked(Exception):
    pass


# ============================================================================
# Category context
# ============================================================================
@contextmanager
def category(name: str):
    """Open a category for the duration of the `with` block.

    Every Event subclass defined inside the block joins this category.

    Constraints:
        -- the name must not contain '.' (reserved as wire-id separator)
        -- nesting is not allowed; opening while a category is open raises
        -- once Event.lock_registration() has been called, opening raises

    Re-opening a category (same name, separate `with` block, possibly
    in a different module) is permitted: the new block adds events to
    the existing category. Same-name collisions inside the category
    still raise EventIdCollision.
    """
    global _current_category

    if _registration_locked:
        raise EventRegistrationLocked(
            "Cannot open category %r: registration is locked." % name
        )

    if not isinstance(name, str) or not name:
        raise ValueError(
            "Category name must be a non-empty string; got %r" % (name,)
        )

    if "." in name:
        raise ValueError(
            "Category name %r must not contain '.' "
            "(the '.' is reserved as the wire-id separator)." % name
        )

    if _current_category is not None:
        raise RuntimeError(
            "Cannot open category %r: category %r is already open. "
            "Nesting of category() blocks is not allowed." % (
                name, _current_category,
            )
        )

    _current_category = name

    try:
        yield name
    finally:
        # Always clear, even if the with-block raised. This is the whole
        # point of using a context manager instead of paired open/close
        # function calls.
        _current_category = None


# ============================================================================
# Metaclass: applies the dataclass transform to every Event subclass.
# ============================================================================
class EventMeta(type):
    """Metaclass that auto-applies dataclass(frozen=True, kw_only=True).

    Subclass authors write plain classes with field annotations and no
    @dataclass decorator; EventMeta.__new__ runs the transform for them.
    See the module header section "DATACLASS TRANSFORM" for the
    rationale.

    The transform is applied to every class in the hierarchy, the Event
    base included, so the base's own fields (timestamp) are processed
    too.
    """

    def __new__(mcs, name, bases, namespace, **kwargs):
        """RETURN: type, the freshly created class with dataclass processing
                         applied.

        Builds the class normally, then runs
        dataclass(frozen=True, kw_only=True) on it before returning, so
        that __dataclass_fields__ is complete by the time any caller
        (including the lazy Pydantic adapter) reads it.
        """
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        return dataclass(frozen=True, kw_only=True)(cls)


# ============================================================================
# Event base class
# ============================================================================
class Event(metaclass=EventMeta):
    """Base class for all events.

    Subclasses are defined inside `with category("X"):` blocks, with NO
    @dataclass decorator (EventMeta applies it):

        with category("WORKFLOW"):
            class EventTaskDone(Event):
                task_id:    int
                duration_s: float
                def __str__(self): ...

    On class creation, Event.__init_subclass__:
        -- reads the currently-open category (raises if none)
        -- sets cls.category and cls.id
        -- registers cls in CLASS_BY_ID
        -- raises EventIdCollision on duplicate name within the category

    .id is the composite wire id, e.g. "WORKFLOW.EventTaskDone".
    """

    # Class-level metadata. Set by __init_subclass__; never declared
    # explicitly on subclasses.
    category: ClassVar[str] = None     # set by __init_subclass__
    id:       ClassVar[str] = None     # set by __init_subclass__, e.g. "WORKFLOW.EventTaskDone"

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

        Created lazily (NOT in __init_subclass__) because the EventMeta
        dataclass transform runs in the metaclass's __new__; building
        the adapter on first .as_dict()/.from_dict() use guarantees the
        transform has completed and __dataclass_fields__ is complete.
        """
        # Use __dict__ lookup (not attribute lookup) so each subclass
        # gets its own adapter rather than inheriting the parent's.
        if "_adapter" not in cls.__dict__ or cls.__dict__["_adapter"] is None:
            cls._adapter = TypeAdapter(cls)
        return cls._adapter

    def __init_subclass__(cls, **kwargs):
        """RETURN: None.

        Stamps cls.category and cls.id, then registers cls in
        CLASS_BY_ID. Raises EventRegistrationLocked if locked,
        EventDefinitionOutsideCategoryContext if no category is open,
        EventIdCollision if the name is already taken in this category.
        """
        super().__init_subclass__(**kwargs)

        if _registration_locked:
            raise EventRegistrationLocked(
                "Cannot define Event subclass %s.%s: registration is locked." % (
                    cls.__module__, cls.__qualname__,
                )
            )

        if _current_category is None:
            raise EventDefinitionOutsideCategoryContext(
                "Event subclass %s.%s defined outside any category context. "
                "Wrap the class definition in `with category(\"NAME\"):`." % (
                    cls.__module__, cls.__qualname__,
                )
            )

        cls.category = _current_category
        cls.id       = "%s.%s" % (_current_category, cls.__name__)

        # Registry.register() owns the collision check and the insertion.
        CLASS_BY_ID.register(cls)

    @classmethod
    def lock_registration(cls):
        """RETURN: None.

        Permanently disable further category openings and Event-subclass
        creations. One-way switch; there is no unlock. Calling more than
        once is a no-op.

        Intended use: after a system's startup sequence has imported
        every module whose events should exist in this run, the system
        calls Event.lock_registration() to seal the registry.
        """
        global _registration_locked
        _registration_locked = True

    @classmethod
    def is_registration_locked(cls) -> bool:
        """RETURN: bool, True if lock_registration() has been called."""
        return _registration_locked

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
        """RETURN: cls instance,   if d validates against cls's schema.
                   None,            on validation failure (stderr diagnostic).

        This is called on a CONCRETE subclass, e.g.
        EventTaskDone.from_dict({...}). The Marshaller dispatches to
        the right subclass via CLASS_BY_ID.lookup before calling this.
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
        # Local import to break the event <-> marshaller cycle at
        # module load.
        from vut.engine.event.channel.marshaller import Marshaller
        return Marshaller.serialize(self)

    @classmethod
    def deserialize(cls, wire: dict) -> "Event | None":
        """RETURN: Event,   if wire decodes to a valid event of a known kind.
                   None,    on any failure (stderr diagnostic).

        Classmethod because there is no Event instance before decoding.
        Delegates to Marshaller.deserialize(wire), which dispatches on
        the wire's id to the right Event subclass.
        """
        from vut.engine.event.channel.marshaller import Marshaller
        return Marshaller.deserialize(wire)

