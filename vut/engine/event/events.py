"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Concrete Event subclasses.

Each concrete event in the system is one class here:

    class TaskDoneEvent(Event):
        category = E_EventCategory.WORKFLOW
        task_id:    int
        duration_s: float
        def __str__(self): ...

The .id class attribute is auto-derived from the class name in
Event.__init_subclass__; the class is auto-registered in CLASS_BY_ID
(see event.py). Defining a new event is ONE step: define the class.

Inheritance carries specialisation: CompilerDoneEvent inherits from
TaskDoneEvent and overrides .category. Each concrete subclass gets
its own .id (its own __name__), so CompilerDoneEvent.id is
"CompilerDoneEvent" - distinct from "TaskDoneEvent".

Adding a new event is a one-step operation:

    1. Declare an Event subclass here (or in the owning subsystem's
       module - subsystems may host their own event classes; they
       just need to be IMPORTED somewhere to trigger registration).
________________________________________________________________________________
"""
from dataclasses import dataclass
from typing      import ClassVar

from vut.engine.event.enums import E_EventCategory
from vut.engine.event.event import Event


# ============================================================================
# Generic Task lifecycle events
# ============================================================================

@dataclass(frozen=True, kw_only=True)
class TaskStartedEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id: int

    def __str__(self) -> str:
        return "task %d started" % self.task_id


@dataclass(frozen=True, kw_only=True)
class TaskDoneEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id:    int
    duration_s: float

    def __str__(self) -> str:
        return "task %d done in %.3fs" % (self.task_id, self.duration_s)


@dataclass(frozen=True, kw_only=True)
class TaskFailedEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id: int
    reason:  str

    def __str__(self) -> str:
        return "task %d failed: %s" % (self.task_id, self.reason)


@dataclass(frozen=True, kw_only=True)
class TaskProgressEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id:  int
    fraction: float                     # 0.0 to 1.0
    note:     str = ""

    def __str__(self) -> str:
        if self.note:
            return "task %d progress: %.0f%%  (%s)" % (
                self.task_id, self.fraction * 100.0, self.note
            )
        return "task %d progress: %.0f%%" % (
            self.task_id, self.fraction * 100.0
        )


@dataclass(frozen=True, kw_only=True)
class TaskCancelledEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id: int

    def __str__(self) -> str:
        return "task %d cancelled" % self.task_id


# ============================================================================
# Compilation subsystem events
# ============================================================================

@dataclass(frozen=True, kw_only=True)
class CompilerNoSourceEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.COMPILATION

    task_id:  int
    expected: str                       # path the compiler was looking for

    def __str__(self) -> str:
        return "task %d: no source: %s" % (self.task_id, self.expected)


@dataclass(frozen=True, kw_only=True)
class CompilerDoneEvent(TaskDoneEvent):
    """Specialises TaskDoneEvent with compiler-specific outputs.

    Inherits task_id and duration_s from TaskDoneEvent; adds source
    and output. The compiler emits THIS class instead of the generic
    TaskDoneEvent - .id and .category differ.
    """
    category: ClassVar[E_EventCategory] = E_EventCategory.COMPILATION

    source:  str
    output:  str

    def __str__(self) -> str:
        return "task %d compiled %s -> %s in %.3fs" % (
            self.task_id, self.source, self.output, self.duration_s
        )


# ============================================================================
# Workflow subsystem events (emitted by the WFM itself, not Tasks)
# ============================================================================

@dataclass(frozen=True, kw_only=True)
class ArtifactAvailableEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id:     int                    # task that produced the artifact
    artifact_id: int

    def __str__(self) -> str:
        return "artifact %d available (by task %d)" % (
            self.artifact_id, self.task_id
        )


@dataclass(frozen=True, kw_only=True)
class ArtifactImpossibleEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id:     int                    # task that determined impossibility
    artifact_id: int
    reason:      str = ""

    def __str__(self) -> str:
        if self.reason:
            return "artifact %d impossible (by task %d): %s" % (
                self.artifact_id, self.task_id, self.reason
            )
        return "artifact %d impossible (by task %d)" % (
            self.artifact_id, self.task_id
        )


@dataclass(frozen=True, kw_only=True)
class WorkflowTaskCancelledEvent(Event):
    category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

    task_id: int                        # task that is being cancelled

    def __str__(self) -> str:
        return "task %d cancelled by workflow" % self.task_id
