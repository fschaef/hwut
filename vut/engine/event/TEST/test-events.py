#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the concrete Event subclasses.

CHOICES: construction, str, inheritance, frozen, metadata, collision;

DESCRIPTION:

In the class-name-as-id design, each concrete Event subclass IS the
event kind. The class auto-registers in CLASS_BY_ID under its
__name__ at class-definition time; the .id class attribute is set
to that name.

    construction    -- subclasses construct via keyword arguments;
                       fields are accessible.

    str             -- __str__ produces the human-readable form;
                       optional fields are handled.

    inheritance     -- CompilerDoneEvent IS-A TaskDoneEvent;
                       inherits parent fields; each gets its own .id
                       (not inherited).

    frozen          -- instances cannot be mutated.

    metadata        -- class-level .id (== __name__) and .category
                       are correct for each concrete subclass.

    collision       -- defining two Event subclasses with the same
                       class name raises EventIdCollision.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from dataclasses                                import FrozenInstanceError, dataclass
from typing                                     import ClassVar
from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (E_EventCategory,
                                                        Event,
                                                        EventIdCollision,
                                                        TaskStartedEvent,
                                                        TaskDoneEvent,
                                                        TaskFailedEvent,
                                                        TaskProgressEvent,
                                                        TaskCancelledEvent,
                                                        CompilerNoSourceEvent,
                                                        CompilerDoneEvent,
                                                        ArtifactAvailableEvent,
                                                        ArtifactImpossibleEvent,
                                                        WorkflowTaskCancelledEvent,
                                                        all_event_classes)


def banner(label):
    """RETURN: None.  Prints a section heading."""
    print()
    print("--- %s ---" % label)


def run_construction():
    """RETURN: None.

    Builds one instance of each concrete event subclass and prints
    type and id. Uses explicit timestamp for stable output.
    """
    cases = [
        TaskStartedEvent  (task_id=1, timestamp=10.0),
        TaskDoneEvent     (task_id=1, duration_s=1.5, timestamp=10.0),
        TaskFailedEvent   (task_id=1, reason="boom", timestamp=10.0),
        TaskProgressEvent (task_id=1, fraction=0.5,  timestamp=10.0),
        TaskCancelledEvent(task_id=1, timestamp=10.0),

        CompilerNoSourceEvent(task_id=2, expected="main.c", timestamp=10.0),
        CompilerDoneEvent    (task_id=2, source="main.c", output="main.o",
                              duration_s=0.3, timestamp=10.0),

        ArtifactAvailableEvent (task_id=3, artifact_id=7,
                                timestamp=10.0),
        ArtifactImpossibleEvent(task_id=3, artifact_id=8,
                                reason="cycle", timestamp=10.0),
        WorkflowTaskCancelledEvent(task_id=4, timestamp=10.0),
    ]
    banner("construction of every concrete event class")
    for ev in cases:
        print("%-30s id=%-30s" % (type(ev).__name__, ev.id))


def run_str():
    """RETURN: None.

    Demonstrates __str__ for each class.
    """
    banner("TaskStartedEvent")
    print(str(TaskStartedEvent(task_id=1, timestamp=0)))

    banner("TaskDoneEvent")
    print(str(TaskDoneEvent(task_id=1, duration_s=2.0, timestamp=0)))

    banner("TaskFailedEvent")
    print(str(TaskFailedEvent(task_id=1, reason="exit code 1", timestamp=0)))

    banner("TaskProgressEvent without note")
    print(str(TaskProgressEvent(task_id=1, fraction=0.25, timestamp=0)))

    banner("TaskProgressEvent with note")
    print(str(TaskProgressEvent(task_id=1, fraction=0.50,
                                note="linking", timestamp=0)))

    banner("TaskCancelledEvent")
    print(str(TaskCancelledEvent(task_id=1, timestamp=0)))

    banner("CompilerNoSourceEvent")
    print(str(CompilerNoSourceEvent(task_id=2, expected="x.c", timestamp=0)))

    banner("CompilerDoneEvent")
    print(str(CompilerDoneEvent(task_id=2, source="x.c", output="x.o",
                                duration_s=0.5, timestamp=0)))

    banner("ArtifactAvailableEvent")
    print(str(ArtifactAvailableEvent(task_id=3, artifact_id=7, timestamp=0)))

    banner("ArtifactImpossibleEvent without reason")
    print(str(ArtifactImpossibleEvent(task_id=3, artifact_id=8, timestamp=0)))

    banner("ArtifactImpossibleEvent with reason")
    print(str(ArtifactImpossibleEvent(task_id=3, artifact_id=8,
                                      reason="cycle", timestamp=0)))

    banner("WorkflowTaskCancelledEvent")
    print(str(WorkflowTaskCancelledEvent(task_id=4, timestamp=0)))


def run_inheritance():
    """RETURN: None.

    CompilerDoneEvent inherits from TaskDoneEvent. The relationship
    is checked via isinstance and via field inheritance. Each concrete
    class gets its own .id (its own __name__), NOT the parent's.
    """
    banner("CompilerDoneEvent IS-A TaskDoneEvent")
    ev = CompilerDoneEvent(task_id=42, source="a.c", output="a.o",
                           duration_s=1.5, timestamp=0)
    print("isinstance Event:             %s" % isinstance(ev, Event))
    print("isinstance TaskDoneEvent:     %s" % isinstance(ev, TaskDoneEvent))
    print("isinstance CompilerDoneEvent: %s" % isinstance(ev, CompilerDoneEvent))

    banner("inherits parent's fields")
    print("ev.task_id:    %d" % ev.task_id)         # from TaskDoneEvent
    print("ev.duration_s: %s" % ev.duration_s)      # from TaskDoneEvent
    print("ev.source:     %s" % ev.source)          # own
    print("ev.output:     %s" % ev.output)          # own

    banner("each gets its own id (NOT inherited)")
    print("TaskDoneEvent.id:     %s" % TaskDoneEvent.id)
    print("CompilerDoneEvent.id: %s" % CompilerDoneEvent.id)
    print("distinct:             %s" % (TaskDoneEvent.id != CompilerDoneEvent.id))

    banner("Compiler overrides .category")
    print("TaskDoneEvent.category:     %s" % TaskDoneEvent.category.name)
    print("CompilerDoneEvent.category: %s" % CompilerDoneEvent.category.name)


def run_frozen():
    """RETURN: None.

    Demonstrates that instances are immutable (frozen=True).
    """
    ev = TaskDoneEvent(task_id=1, duration_s=1.0, timestamp=0)

    banner("attempt to assign .task_id")
    try:
        ev.task_id = 99
        print("UNEXPECTED: assignment succeeded")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")

    banner("attempt to assign .duration_s")
    try:
        ev.duration_s = 99.0
        print("UNEXPECTED: assignment succeeded")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")

    banner("attempt to assign .timestamp")
    try:
        ev.timestamp = 99.0
        print("UNEXPECTED: assignment succeeded")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")


def run_metadata():
    """RETURN: None.

    For every concrete Event subclass, checks that .id equals
    __name__ and .category is the right enum value.
    """
    expected = [
        (TaskStartedEvent,           "TaskStartedEvent",           E_EventCategory.WORKFLOW),
        (TaskDoneEvent,              "TaskDoneEvent",              E_EventCategory.WORKFLOW),
        (TaskFailedEvent,            "TaskFailedEvent",            E_EventCategory.WORKFLOW),
        (TaskProgressEvent,          "TaskProgressEvent",          E_EventCategory.WORKFLOW),
        (TaskCancelledEvent,         "TaskCancelledEvent",         E_EventCategory.WORKFLOW),
        (CompilerNoSourceEvent,      "CompilerNoSourceEvent",      E_EventCategory.COMPILATION),
        (CompilerDoneEvent,          "CompilerDoneEvent",          E_EventCategory.COMPILATION),
        (ArtifactAvailableEvent,     "ArtifactAvailableEvent",     E_EventCategory.WORKFLOW),
        (ArtifactImpossibleEvent,    "ArtifactImpossibleEvent",    E_EventCategory.WORKFLOW),
        (WorkflowTaskCancelledEvent, "WorkflowTaskCancelledEvent", E_EventCategory.WORKFLOW),
    ]
    banner("class metadata: .id equals __name__, .category as declared")
    for cls, exp_id, exp_cat in expected:
        print("%-30s id=%-28s cat=%-12s ok=%s" % (
            cls.__name__, cls.id, cls.category.name,
            cls.id == exp_id and cls.category is exp_cat
        ))

    banner("all_event_classes() count")
    print("count: %d" % len(all_event_classes()))


def run_collision():
    """RETURN: None.

    Defining a new Event subclass with a name that already exists
    raises EventIdCollision at class-creation time. We attempt three
    collisions and confirm each raises.
    """
    banner("collision with TaskDoneEvent (already registered in events.py)")
    try:
        @dataclass(frozen=True, kw_only=True)
        class TaskDoneEvent(Event):     # noqa: F811  intentional collision
            category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW
            task_id: int
        print("UNEXPECTED: collision accepted")
    except EventIdCollision as e:
        msg = str(e)
        # Print only the leading identifying portion to keep output
        # stable across modules with varying __module__ strings.
        head = msg.split(";")[0]
        print("EventIdCollision raised: %s" % head)

    banner("collision with CompilerDoneEvent")
    try:
        @dataclass(frozen=True, kw_only=True)
        class CompilerDoneEvent(Event):    # noqa: F811
            category: ClassVar[E_EventCategory] = E_EventCategory.COMPILATION
            task_id: int
        print("UNEXPECTED: collision accepted")
    except EventIdCollision as e:
        head = str(e).split(";")[0]
        print("EventIdCollision raised: %s" % head)

    banner("non-colliding definition works")
    @dataclass(frozen=True, kw_only=True)
    class _OneShotTestEvent(Event):
        category: ClassVar[E_EventCategory] = E_EventCategory.DIAGNOSTIC
        token: str
    print("class defined OK: %s" % _OneShotTestEvent.id)

    banner("redefining the same novel name DOES collide")
    try:
        @dataclass(frozen=True, kw_only=True)
        class _OneShotTestEvent(Event):    # noqa: F811
            category: ClassVar[E_EventCategory] = E_EventCategory.DIAGNOSTIC
            token: str
        print("UNEXPECTED: re-registration accepted")
    except EventIdCollision as e:
        head = str(e).split(";")[0]
        print("EventIdCollision raised: %s" % head)


HwutRunner(
    argv       = sys.argv,
    title      = "Concrete Event subclasses",
    choice_map = {
        "construction": run_construction,
        "str":          run_str,
        "inheritance":  run_inheritance,
        "frozen":       run_frozen,
        "metadata":     run_metadata,
        "collision":    run_collision,
    },
).run()
