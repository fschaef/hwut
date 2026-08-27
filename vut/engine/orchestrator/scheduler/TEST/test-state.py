#! /usr/bin/env python3
#
# hwut {
#     title      = "Plan state: admission, supports, exclusion, ordering"
#     choices    = ["admission", "exclusion", "ordering", "supports"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE STATE MACHINE -- who may start now, and what an ending
         drives terminal.

CHOICES: admission, supports, exclusion, ordering;

DESCRIPTION:

admission  the states at construction: [MISDEP] terminal before
           anything runs; who is ready and who is not.

supports   a BUILD node ending BAD leaves the TEST nodes it supports
           UNSUPPORTED, named at the ending; a BUILD node ending GOOD
           admits them.

exclusion  a member of an exclusion set standing RUNNING withholds
           admission from the others, and returns it at the ending.

ordering   a terminal state satisfies an ordering link, whatever it
           says -- the link is ordering, not success.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.plan.form  import (CExclusionSet, CPlanLink,
                                                CPlanNode, CTestPlan,
                                                E_LinkKind)
from vut.engine.orchestrator.scheduler.state import CPlanState


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def show(state):
    """RETURN: None. Every node's state, then who may start now."""
    for node in state.plan:
        print("    %-22s %s" % (node.name(),
                                state.state(node.name()).name))
    print("    ready: %s" % (", ".join(state.ready()) or "-"))


def test_admission():
    """RETURN: None. The states at construction."""
    plan = CTestPlan([CPlanNode.build("make"),
                      CPlanNode.test("a.py", "one"),
                      CPlanNode.test("a.py", "two"),
                      CPlanNode.test("z.py", None, misdep_f=True)],
                     [CPlanLink(E_LinkKind.SUPPORTS, "build[make]",
                                "a.py one")])
    state = CPlanState(plan)
    banner("at construction")
    show(state)
    print("    done_f=%s stuck_f=%s" % (state.done_f(), state.stuck_f()))

    banner("the build starts")
    state.started("build[make]")
    show(state)

    banner("starting what is not ready: refused")
    try:
        state.started("a.py one")
    except AssertionError as error:
        print("REFUSED: %s" % error)


def test_supports():
    """RETURN: None. A supporter ending, both ways."""
    def plan_of():
        return CTestPlan([CPlanNode.build("make"),
                          CPlanNode.test("a.py", "one"),
                          CPlanNode.test("a.py", "two")],
                         [CPlanLink(E_LinkKind.SUPPORTS, "build[make]",
                                    "a.py one"),
                          CPlanLink(E_LinkKind.SUPPORTS, "build[make]",
                                    "a.py two")])

    banner("the build stands")
    state = CPlanState(plan_of())
    state.started("build[make]")
    print("    ended() named: %s"
          % (", ".join(state.ended("build[make]", True)) or "-"))
    show(state)

    banner("the build breaks")
    state = CPlanState(plan_of())
    state.started("build[make]")
    print("    ended() named: %s"
          % (", ".join(state.ended("build[make]", False)) or "-"))
    show(state)
    print("    done_f=%s" % state.done_f())
    print("    failures: %s"
          % ", ".join("%s=%s" % (name, node_state.name)
                      for name, node_state
                      in sorted(state.failure_db().items())))


def test_exclusion():
    """RETURN: None. A running member withholds admission."""
    plan = CTestPlan([CPlanNode.test("net.py", None),
                      CPlanNode.test("port.py", "one"),
                      CPlanNode.test("port.py", "two"),
                      CPlanNode.test("free.py", None)],
                     (),
                     [CExclusionSet(("net.py", "port.py two"))])
    state = CPlanState(plan)
    banner("nothing runs")
    show(state)

    banner("'net.py' runs")
    state.started("net.py")
    show(state)

    banner("'net.py' ends")
    state.ended("net.py", True)
    show(state)


def test_ordering():
    """RETURN: None. A terminal state satisfies the link, whatever it
    says."""
    plan = CTestPlan([CPlanNode.test("a.py", None),
                      CPlanNode.test("b.py", None)],
                     [CPlanLink(E_LinkKind.ORDERING, "a.py", "b.py")])

    banner("'a.py' runs: 'b.py' waits")
    state = CPlanState(plan)
    state.started("a.py")
    show(state)

    banner("'a.py' ends BAD: 'b.py' is admitted all the same")
    state.ended("a.py", False)
    show(state)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Plan state: admission, supports, exclusion, ordering;", {
        "admission": test_admission,
        "supports":  test_supports,
        "exclusion": test_exclusion,
        "ordering":  test_ordering,
    }).run()
