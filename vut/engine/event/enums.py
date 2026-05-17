"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Event categorisation enum.

ONE enum lives here: E_EventCategory. The previous E_EventId was
dropped because event identity is now derived directly from the
Event subclass name. See DISCUSSIONS.txt (decision 10).

CATEGORIES ARE SUBSYSTEMS, NOT EVENT SHAPES.

A category answers "which subsystem of VUT does this event belong
to?", not "what shape of state-change does this represent?". A
consumer that says "give me all WORKFLOW events" or "all NETWORK
events" expresses a real, natural cut of interest. A consumer
that wants "all task-lifecycle events regardless of subsystem"
uses a predicate (e.g. event.id.endswith('DoneEvent')) instead
of demanding a privileged category.

This shape is deliberate. The category enum is the most common
filter dimension; it should match how consumers naturally group
their interests, which is by subsystem - not by abstract event
shape.
________________________________________________________________________________
"""
from enum import Enum, auto


class E_EventCategory(Enum):
    """Functional categorisation by VUT subsystem.

    Categories name SUBSYSTEMS. A consumer filtering by category
    expresses "I care about events from this subsystem". Other
    filters (by id, by source identity, by workload membership)
    are expressed as predicates over event attributes.

    The list is flat. No hierarchy in the category names; finer
    grouping is a predicate matter.
    """

    TEST_RESULT   = auto()    # outcomes of test execution
    WORKFLOW      = auto()    # WFM control, artifact lifecycle, task generics
    NETWORK       = auto()    # connection state, transport-level events
    COMPILATION   = auto()    # compiler / codegen events
    DIAGNOSTIC    = auto()    # logging, observability
