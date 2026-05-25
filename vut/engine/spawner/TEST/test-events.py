#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test - E_ChildState enum and the SPAWNER-category events.

Covers the two pure-data leaf modules of the spawner component:

    enums.py    E_ChildState - the child-state machine's states
    events.py   the four SPAWNER events + E_TerminationReason

CHOICES
    child_state    E_ChildState members, is_terminal() / is_live().
    events         the four events: construction, fields, __str__.
    reason         E_TerminationReason members.

All output is deterministic - these modules carry no timestamps a test
prints, no PIDs, no scheduling. The events DO carry a base-class
'timestamp' field, but the tests print only the semantic fields (via
each event's __str__, which omits timestamp), so no HAPPY pattern is
needed.
________________________________________________________________________________
"""
import config  # noqa: F401  (path bootstrap; must precede vut.* imports)
import sys

from vut.language_support.python.hwut_runner import HwutRunner

from vut.engine.spawner.enums  import E_ChildState
from vut.engine.spawner.events import (EventChildTerminationReq,
                                       EventChildTermination,
                                       EventChildKilled,
                                       EventChildStateChanged,
                                       E_TerminationReason)


def run_child_state():
    """RETURN: None.

    Walks every E_ChildState member and reports its terminal/live
    classification, then asserts the two predicates are exact
    complements and that exactly the three TERM_* members are terminal.
    """
    print("--- E_ChildState members ---")
    for st in E_ChildState:
        print("  %-22s terminal=%-5s live=%-5s"
              % (st, st.is_terminal(), st.is_live()))

    print("--- invariants ---")
    terminal = [st for st in E_ChildState if st.is_terminal()]
    print("  terminal states: %s" % ", ".join(str(s) for s in terminal))
    # Safety net: predicates are exact complements; exactly three
    # terminal states; str() is the bare member name.
    for st in E_ChildState:
        assert st.is_terminal() != st.is_live(), st
    assert len(terminal) == 3, terminal
    assert str(E_ChildState.RUNNING) == "RUNNING"
    print("  is_terminal/is_live are exact complements: OK")
    print("  exactly 3 terminal states: OK")


def run_events():
    """RETURN: None.

    Constructs each of the four SPAWNER events, prints its __str__ and
    its semantic fields, and asserts the fields round-trip. The base
    'timestamp' field is deliberately NOT printed - __str__ omits it -
    so the output is deterministic.
    """
    print("--- EventChildTerminationReq ---")
    e1 = EventChildTerminationReq(wait_to_kill_ms=500)
    print("  str        : %s" % e1)
    print("  field      : wait_to_kill_ms=%s" % e1.wait_to_kill_ms)
    e1n = EventChildTerminationReq(wait_to_kill_ms=None)
    print("  str (None) : %s" % e1n)
    assert e1.wait_to_kill_ms == 500 and e1n.wait_to_kill_ms is None

    print("--- EventChildTermination ---")
    for reason in E_TerminationReason:
        e2 = EventChildTermination(reason=reason)
        print("  str        : %s" % e2)
        assert e2.reason is reason

    print("--- EventChildKilled ---")
    e3 = EventChildKilled(last_state = E_ChildState.TERMINATING,
                          killed_at  = 1000.0,
                          grace_ms   = 250)
    # killed_at is fixed here (not time.time()), so printing str() is
    # safe and deterministic.
    print("  str        : %s" % e3)
    print("  fields     : last_state=%s grace_ms=%s"
          % (e3.last_state, e3.grace_ms))
    assert e3.last_state is E_ChildState.TERMINATING and e3.grace_ms == 250

    print("--- EventChildStateChanged ---")
    e4 = EventChildStateChanged(old_state = E_ChildState.RUNNING,
                                new_state = E_ChildState.TERMINATING)
    print("  str        : %s" % e4)
    assert e4.old_state is E_ChildState.RUNNING
    assert e4.new_state is E_ChildState.TERMINATING

    print("--- event identity (category derives from class) ---")
    # Every SPAWNER event's id is the string 'SPAWNER.<ClassName>'.
    for ev in (e1, EventChildTermination(reason=E_TerminationReason.COMPLETED),
               e3, e4):
        print("  %-26s -> id=%s" % (type(ev).__name__, ev.id))
        assert ev.id == "SPAWNER.%s" % type(ev).__name__, ev.id
    print("  every id is 'SPAWNER.<ClassName>': OK")


def run_reason():
    """RETURN: None.

    Walks E_TerminationReason and reports each member. The reason
    enum records the child's FUNCTIONAL verdict on itself, distinct
    from the Spawner's E_ChildState verdict (DISCUSSION.txt D7).
    """
    print("--- E_TerminationReason members ---")
    for r in E_TerminationReason:
        print("  %s" % r)
    assert {str(r) for r in E_TerminationReason} \
           == {"COMPLETED", "TERMINATED", "FAILED"}
    print("  exactly COMPLETED / TERMINATED / FAILED: OK")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "E_ChildState enum and SPAWNER events",
        choice_map = {
            "child_state": run_child_state,
            "events":      run_events,
            "reason":      run_reason,
        },
    ).run()
