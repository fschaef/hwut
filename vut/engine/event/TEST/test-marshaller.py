#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the Marshaller and Event's serialise/deserialise methods.

CHOICES: roundtrip, frozen, errors;

DESCRIPTION:

The Marshaller is a global class-as-singleton: classmethods only, a
frozen _SPECIALISTS class attribute, no constructor. Event has thin
.serialize() and .deserialize() methods that delegate here.

The wire envelope is:

    {"id": "TEST_LOCAL_MARSHALLER.EventTaskDone", "data": {<all fields>}}

The id is the Event subclass's __name__ verbatim.

    roundtrip   -- the default scheme round-trips events; the
                   reconstructed event is the correct subclass.

    frozen      -- _SPECIALISTS is a MappingProxyType: mutation
                   attempts raise.

    errors      -- unknown id, missing envelope fields, bad data
                   all produce None (stderr diagnostics not captured).
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from dataclasses                                import dataclass
from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (Event,
                                                        category,
                                                        Marshaller)


# Test-local event vocabulary. Declared here so this test file is
# self-contained: the event package no longer ships application
# events.
with category("TEST_LOCAL_MARSHALLER"):

    @dataclass(frozen=True, kw_only=True)
    class EventTaskDone(Event):
        task_id:    int
        duration_s: float

    @dataclass(frozen=True, kw_only=True)
    class EventCompilerDone(EventTaskDone):
        source: str
        output: str

    @dataclass(frozen=True, kw_only=True)
    class EventTaskProgress(Event):
        task_id:  int
        fraction: float
        note:     str = ""


def banner(label):
    """RETURN: None.  Prints a section heading."""
    print()
    print("--- %s ---" % label)


def run_roundtrip():
    """RETURN: None.

    Round-trips two events (one direct, one inheriting via Compiler)
    via both entry points. Confirms class identity is preserved.
    """
    banner("EventCompilerDone via event.serialize()")
    ev = EventCompilerDone(task_id=42, source="x.c", output="x.o",
                           duration_s=1.5, timestamp=100.0)
    wire_a = ev.serialize()
    print("id   = %s" % wire_a["id"])
    print("data = %s" % wire_a["data"])

    banner("identical via Marshaller.serialize(event)")
    wire_b = Marshaller.serialize(ev)
    print("identical: %s" % (wire_a == wire_b))

    banner("deserialise via Event.deserialize(wire)")
    back = Event.deserialize(wire_a)
    print("type:           %s" % type(back).__name__)
    print("is Compiler:    %s" % isinstance(back, EventCompilerDone))
    print("is TaskDone:    %s" % isinstance(back, EventTaskDone))
    print("fields equal:   %s" % (back.task_id == 42
                                  and back.source == "x.c"
                                  and back.output == "x.o"
                                  and back.duration_s == 1.5))
    print("timestamp:      %s" % back.timestamp)
    print("str(back):      %s" % str(back))

    banner("deserialise via Marshaller.deserialize(wire)")
    back2 = Marshaller.deserialize(wire_a)
    print("identical type: %s" % (type(back2) is type(back)))

    banner("event with optional field (EventTaskProgress)")
    ev2 = EventTaskProgress(task_id=7, fraction=0.33, note="hi",
                            timestamp=200.0)
    wire2 = ev2.serialize()
    print("wire = %s" % wire2)
    back3 = Event.deserialize(wire2)
    print("note preserved: %s" % (back3.note == "hi"))


def run_frozen():
    """RETURN: None.

    Demonstrates _SPECIALISTS is immutable. There is no constructor.
    """
    banner("_SPECIALISTS is empty by default")
    print("len(_SPECIALISTS): %d" % len(Marshaller._SPECIALISTS))

    banner("item assignment is refused")
    try:
        Marshaller._SPECIALISTS["TEST_LOCAL_MARSHALLER.EventTaskDone"] = ("a", "b")
        print("UNEXPECTED: assignment succeeded")
    except TypeError as e:
        print("TypeError (expected): %s" % e)

    banner("deletion is refused")
    try:
        del Marshaller._SPECIALISTS["TEST_LOCAL_MARSHALLER.EventTaskDone"]
        print("UNEXPECTED: deletion succeeded")
    except TypeError as e:
        print("TypeError (expected): %s" % e)


def run_errors():
    """RETURN: None.

    Failure paths through deserialize(): unknown id, missing id,
    non-dict envelope, wrong-typed data, missing required field.
    """
    banner("unknown id")
    print("result: %s" % Event.deserialize(
        {"id": "NotARealEvent", "data": {}}))

    banner("missing id in envelope")
    print("result: %s" % Event.deserialize({"data": {}}))

    banner("envelope is not a dict")
    print("result: %s" % Event.deserialize("not a dict"))

    banner("payload validation failure (wrong type)")
    print("result: %s" % Event.deserialize({
        "id":   "TEST_LOCAL_MARSHALLER.EventTaskDone",
        "data": {"task_id": 1, "duration_s": "two seconds", "timestamp": 0.0},
    }))

    banner("payload validation failure (missing required field)")
    print("result: %s" % Event.deserialize({
        "id":   "TEST_LOCAL_MARSHALLER.EventTaskDone",
        "data": {"task_id": 1, "timestamp": 0.0},   # missing duration_s
    }))


HwutRunner(
    argv       = sys.argv,
    title      = "Marshaller and Event.serialize/deserialize",
    choice_map = {
        "roundtrip": run_roundtrip,
        "frozen":    run_frozen,
        "errors":    run_errors,
    },
).run()
