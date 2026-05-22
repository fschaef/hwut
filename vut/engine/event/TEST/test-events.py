#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the shipped EVENT_INFRA events and the registration lock.

CHOICES: shipped, frozen, collision, inheritance, lock;

DESCRIPTION:

The event package itself ships only two events: EventTerminalUp and
EventTerminalDown, both in the EVENT_INFRA category. Other events
are declared by users in their own modules.

    shipped     -- EventTerminalUp and EventTerminalDown construct,
                   have the expected .id and .category, and serialise
                   round-trip.

    frozen      -- instances are immutable.

    collision   -- two Event classes with the same name in the same
                   category raise EventIdCollision; the same name in
                   DIFFERENT categories is fine.

    inheritance -- a user-defined event can inherit fields from another
                   event in a different category and gets its own .id.

    lock        -- after Event.lock_registration(), opening a category
                   or defining an Event raises EventRegistrationLocked.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from dataclasses                                import FrozenInstanceError
from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import (Event,
                                                        category,
                                                        EventIdCollision,
                                                        EventRegistrationLocked,
                                                        EventTerminalUp,
                                                        EventTerminalDown)


def banner(label):
    """RETURN: None.  Prints a section heading."""
    print()
    print("--- %s ---" % label)


def run_shipped():
    """RETURN: None.

    Constructs each shipped event, prints metadata, and round-trips
    through the wire format.
    """
    banner("EventTerminalUp")
    up = EventTerminalUp(timestamp=10.0)
    print("type:      %s" % type(up).__name__)
    print("category:  %s" % up.category)
    print("id:        %s" % up.id)
    print("str:       %s" % str(up))
    wire = up.serialize()
    print("wire:      %s" % wire)
    back = Event.deserialize(wire)
    print("back type: %s" % type(back).__name__)

    banner("EventTerminalDown")
    down = EventTerminalDown(timestamp=20.0)
    print("type:      %s" % type(down).__name__)
    print("category:  %s" % down.category)
    print("id:        %s" % down.id)
    print("str:       %s" % str(down))


def run_frozen():
    """RETURN: None.

    Both shipped events are frozen dataclasses; assignment is refused.
    """
    up = EventTerminalUp(timestamp=10.0)
    banner("EventTerminalUp .timestamp = ...")
    try:
        up.timestamp = 99.0
        print("UNEXPECTED: assignment accepted")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")

    down = EventTerminalDown(timestamp=20.0)
    banner("EventTerminalDown .timestamp = ...")
    try:
        down.timestamp = 99.0
        print("UNEXPECTED: assignment accepted")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")


def run_collision():
    """RETURN: None.

    Same name in same category raises; same name in different categories
    is fine.
    """
    banner("define EventThing in TEST_EV_COL_A")
    with category("TEST_EV_COL_A"):
        class EventThing(Event):
            x: int
    print("EventThing.id: %s" % EventThing.id)

    banner("define EventThing again in TEST_EV_COL_A -- collision")
    try:
        with category("TEST_EV_COL_A"):
            class EventThing(Event):                # noqa: F811
                x: int
        print("UNEXPECTED: accepted")
    except EventIdCollision as e:
        head = str(e).split(";")[0]
        print("EventIdCollision raised: %s" % head)

    banner("define EventThing in TEST_EV_COL_B -- different category, OK")
    with category("TEST_EV_COL_B"):
        class EventThing(Event):                    # noqa: F811
            x: int
    print("new class registered: id=%s" % EventThing.id)


def run_inheritance():
    """RETURN: None.

    A user-defined event may inherit fields from another event in a
    DIFFERENT category. The child gets its own .category and .id.
    """
    banner("define EventBase in TEST_EV_INH_A")
    with category("TEST_EV_INH_A"):
        class EventBase(Event):
            task_id:    int
            duration_s: float

            def __str__(self) -> str:
                return "base id=%d t=%.1f" % (self.task_id, self.duration_s)

    banner("define EventDerived(EventBase) in TEST_EV_INH_B")
    with category("TEST_EV_INH_B"):
        class EventDerived(EventBase):
            source: str

            def __str__(self) -> str:
                return "derived %s id=%d" % (self.source, self.task_id)

    ev = EventDerived(task_id=42, duration_s=1.5, source="x.c")
    print("EventBase.id:        %s" % EventBase.id)
    print("EventDerived.id:     %s" % EventDerived.id)
    print("ids distinct:        %s" % (EventBase.id != EventDerived.id))
    print("isinstance EventBase: %s" % isinstance(ev, EventBase))
    print("derived inherits task_id: %d" % ev.task_id)
    print("derived adds source:      %s" % ev.source)
    print("str: %s" % str(ev))


def run_lock():
    """RETURN: None.

    After Event.lock_registration(), opening a category raises. Each
    HwutRunner choice runs in its own subprocess so module-level state
    does not leak between choices.
    """
    banner("pre-lock: registration works")
    with category("TEST_EV_LOCK_PRE"):
        class EventBefore(Event):
            x: int
    print("pre-lock id: %s" % EventBefore.id)

    banner("lock_registration()")
    Event.lock_registration()
    print("is_registration_locked: %s" % Event.is_registration_locked())

    banner("post-lock: opening a category raises")
    try:
        with category("TEST_EV_LOCK_POST"):
            pass
        print("UNEXPECTED: accepted")
    except EventRegistrationLocked as e:
        print("EventRegistrationLocked raised: %s" % str(e))

    banner("lock is idempotent")
    Event.lock_registration()
    print("still locked: %s" % Event.is_registration_locked())


HwutRunner(
    argv       = sys.argv,
    title      = "Shipped events and registration lock",
    choice_map = {
        "shipped":     run_shipped,
        "frozen":      run_frozen,
        "collision":   run_collision,
        "inheritance": run_inheritance,
        "lock":        run_lock,
    },
).run()
