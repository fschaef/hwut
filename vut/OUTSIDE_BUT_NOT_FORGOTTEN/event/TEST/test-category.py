#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the category() context manager.

CHOICES: basic, outside, nesting, validation, reopen;

DESCRIPTION:

A category is opened with the `category(name)` context manager.
Inside the `with` block, every Event subclass joins that category.

    basic       -- a category opens, classes register, .category and
                   .id are stamped, the bucket appears in CLASS_BY_ID.
    outside     -- defining an Event outside any open category raises
                   EventDefinitionOutsideCategoryContext.
    nesting     -- opening a category while one is already open raises.
    validation  -- category names must be non-empty strings without
                   any '.' character.
    reopen      -- the same category may be opened in separate `with`
                   blocks; classes accumulate; same-name collisions
                   still raise EventIdCollision.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner                                                  # noqa: F401

from vut.engine.event import (Event,
                              category,
                              CLASS_BY_ID,
                              EventIdCollision,
                                                        EventDefinitionOutsideCategoryContext)


def banner(label):
    """RETURN: None.  Prints a section heading."""
    print()
    print("--- %s ---" % label)


def run_basic():
    """RETURN: None.

    Opens an isolated category, defines two events, checks that
    .category and .id are stamped and CLASS_BY_ID is populated.
    """
    banner("open category 'BASIC_TEST'")
    with category("BASIC_TEST"):
        class EventOne(Event):
            x: int
        class EventTwo(Event):
            y: str

    print("EventOne.category:  %s" % EventOne.category)
    print("EventOne.id:        %s" % EventOne.id)
    print("EventTwo.category:  %s" % EventTwo.category)
    print("EventTwo.id:        %s" % EventTwo.id)

    banner("events_in_category('BASIC_TEST')")
    print([c.__name__ for c in CLASS_BY_ID.in_category("BASIC_TEST")])


def run_outside():
    """RETURN: None.

    Defining an Event subclass outside any open category raises.
    """
    banner("Event defined outside any open category")
    try:
        class EventStray(Event):
            x: int
        print("UNEXPECTED: accepted")
    except EventDefinitionOutsideCategoryContext as e:
        # Trim path-dependent prefix.
        msg = str(e)
        head = msg.split(".")[-2:]
        print("EventDefinitionOutsideCategoryContext raised (expected)")
        print("message contains class name: %s" % ("EventStray" in msg))


def run_nesting():
    """RETURN: None.

    Opening a category while one is already open raises RuntimeError.
    """
    banner("attempt to nest category() blocks")
    try:
        with category("OUTER_NEST"):
            with category("INNER_NEST"):
                pass
        print("UNEXPECTED: accepted")
    except RuntimeError as e:
        print("RuntimeError raised (expected)")
        print("mentions both names: %s" % (
            "OUTER_NEST" in str(e) and "INNER_NEST" in str(e)
        ))

    banner("after the exception, the outer category is cleanly closed")
    # If state cleanup worked, opening another category at top level
    # should succeed.
    with category("AFTER_NEST"):
        pass
    print("subsequent category() at top level: ok")


def run_validation():
    """RETURN: None.

    Category names must be non-empty strings without '.' characters.
    """
    banner("empty string")
    try:
        with category(""):
            pass
        print("UNEXPECTED: accepted")
    except ValueError:
        print("ValueError raised (expected)")

    banner("non-string")
    try:
        with category(123):
            pass
        print("UNEXPECTED: accepted")
    except ValueError:
        print("ValueError raised (expected)")

    banner("contains '.'")
    try:
        with category("BAD.NAME"):
            pass
        print("UNEXPECTED: accepted")
    except ValueError:
        print("ValueError raised (expected)")


def run_reopen():
    """RETURN: None.

    A category opened twice (in separate blocks) accumulates events.
    Same-name collisions within the category still raise.
    """
    banner("open 'REOPEN_TEST' first time")
    with category("REOPEN_TEST"):
        class EventFirst(Event):
            a: int

    banner("open 'REOPEN_TEST' again, add another class")
    with category("REOPEN_TEST"):
        class EventSecond(Event):
            b: int

    print("classes accumulated: %s" % [c.__name__ for c in CLASS_BY_ID.in_category("REOPEN_TEST")])

    banner("re-open and re-register same name: collision")
    try:
        with category("REOPEN_TEST"):
            class EventFirst(Event):       # noqa: F811
                a: int
        print("UNEXPECTED: accepted")
    except EventIdCollision:
        print("EventIdCollision raised (expected)")


HwutRunner(
    argv       = sys.argv,
    title      = "category() context manager",
    choice_map = {
        "basic":      run_basic,
        "outside":    run_outside,
        "nesting":    run_nesting,
        "validation": run_validation,
        "reopen":     run_reopen,
    },
).run()
