#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Sanity-test the E_EventCategory enum.

CHOICES: members;

DESCRIPTION:

E_EventCategory is the only enum in the package (E_EventId was dropped
in favour of class-name-as-id). This file confirms the categories are
present as expected.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import E_EventCategory


def banner(label):
    """RETURN: None.  Prints a section heading."""
    print()
    print("--- %s ---" % label)


def run_members():
    """RETURN: None.

    Lists every E_EventCategory member and confirms value uniqueness.
    """
    banner("E_EventCategory members")
    for m in E_EventCategory:
        print("%-12s = %d" % (m.name, m.value))

    banner("value uniqueness")
    values = [m.value for m in E_EventCategory]
    print("count:        %d" % len(values))
    print("all distinct: %s" % (len(values) == len(set(values))))


HwutRunner(
    argv       = sys.argv,
    title      = "E_EventCategory inventory",
    choice_map = {
        "members": run_members,
    },
).run()
