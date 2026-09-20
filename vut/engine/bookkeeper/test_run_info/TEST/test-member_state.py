#! /usr/bin/env python3
#
# @hwut {
#     title      = "Member state: the states, the events, the guards"
#     choices    = ["transitions", "sealed", "evidence", "consistency"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE UNIT UNDER TEST is the member state of 'bookkeeper/test_run_info': the state a case stands in
and the events that move it. Every line this file prints is an answer
of that module -- a state's name, a guard's refusal, a consistency
line. Nothing else is printed: no path, no clock, no registry.
______________________________________________________________________________
"""
import sys

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.bookkeeper.test_run_info              import (CMemberState,
                                                   E_MemberState,
                                                   MemberStateFault,
                                                   of_evidence)
from   vut.engine.bookkeeper.test_run_info import consistency_fault_tuple


def show(label, member_state):
    """RETURN: None. One line: what was done, and the state it left."""
    print("  %-34s %-9s runnable=%-5s playable=%s"
          % (label, member_state.state, member_state.is_runnable(),
             member_state.is_playable()))


def test_transitions():
    """Every event, from every state it can reach."""
    print("FROM UNKNOWN")
    show("start", CMemberState("test-a.sh"))
    show("on_accept_left_unaccepted",
         CMemberState("test-a.sh").on_accept_left_unaccepted())
    show("on_accept_clean_good",
         CMemberState("test-a.sh").on_accept_clean_good())
    show("on_no_output", CMemberState("test-a.sh").on_no_output())
    show("on_no_terminal", CMemberState("test-a.sh").on_no_terminal())

    print("FROM ASPIRANT")
    def aspirant(): return CMemberState("t").on_accept_left_unaccepted()
    show("on_accept_clean_good", aspirant().on_accept_clean_good())
    show("on_accept_left_unaccepted", aspirant().on_accept_left_unaccepted())
    show("on_no_output", aspirant().on_no_output())
    show("on_no_terminal", aspirant().on_no_terminal())
    show("on_nominal_removed", aspirant().on_nominal_removed())

    print("FROM MEMBER")
    def member(): return CMemberState("t").on_accept_clean_good()
    show("on_detected_unaccepted_in_good",
         member().on_detected_unaccepted_in_good())
    show("on_accept_clean_good", member().on_accept_clean_good())
    show("on_no_output", member().on_no_output())
    show("on_nominal_removed", member().on_nominal_removed())


def test_sealed():
    """Nothing moves by assignment, and no gate may be walked past."""
    member_state = CMemberState("test-a.sh")
    for attribute in ("state", "_state", "whatever"):
        try:
            setattr(member_state, attribute, E_MemberState.MEMBER)
            print("  FAIL: '%s' was assignable" % attribute)
        except MemberStateFault:
            print("  assignment refused: %s" % attribute)
    try:
        del member_state._state
        print("  FAIL: deletion was allowed")
    except MemberStateFault:
        print("  deletion refused")
    print("  state after all of it: %s" % member_state.state)

    print("A RUN MAY JUDGE A MEMBER AND NOTHING ELSE")
    for label, m in (("unknown",  CMemberState("t")),
                     ("aspirant", CMemberState("t").on_accept_left_unaccepted()),
                     ("member",   CMemberState("t").on_accept_clean_good())):
        try:
            m.on_run_verdict(True)
            print("  %-9s judged, state stays %s" % (label, m.state))
        except MemberStateFault as error:
            print("  %-9s refused: %s" % (label, error))


def test_evidence():
    """The files testify; the state follows them."""
    for stands_f in (False, True):
        for mark_f in (False, True):
            member_state = of_evidence("t", None, stands_f, mark_f)
            print("  nominal=%-5s mark=%-5s -> %s"
                  % (stands_f, mark_f, member_state.state))


def test_consistency():
    """What the book claims, against what the files show."""
    case_list = [
        ("no nominal, no row",      False, False, None),
        ("no nominal, row says member", False, False, E_MemberState.MEMBER),
        ("marked nominal, no row",  True,  True,  None),
        ("marked nominal, row says member", True, True, E_MemberState.MEMBER),
        ("marked nominal, row says aspirant", True, True,
                                            E_MemberState.ASPIRANT),
        ("clean nominal, no row",   True,  False, None),
        ("clean nominal, row says aspirant", True, False,
                                            E_MemberState.ASPIRANT),
        ("clean nominal, row says member", True, False,
                                            E_MemberState.MEMBER),
    ]
    for label, stands_f, mark_f, booked in case_list:
        member_state = of_evidence("t", None, stands_f, mark_f)
        fault_tuple = consistency_fault_tuple(member_state, booked)
        print("  %-36s %s" % (label, fault_tuple[0] if fault_tuple
                              else "(agree)"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    {"transitions": test_transitions, "sealed":      test_sealed,
     "evidence":    test_evidence,    "consistency": test_consistency,
     }.get(choice, lambda: print("choices: transitions sealed evidence "
                                 "consistency"))()
    print("<hwut-end>")
