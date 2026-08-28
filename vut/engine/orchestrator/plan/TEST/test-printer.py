#! /usr/bin/env python3
#
# @hwut {
#     title      = "Plan printer: the canonical text, one-way"
#     choices    = ["bare", "empty", "full"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CANONICAL PRINT -- what the service 'hwut.plan' emits.

CHOICES: full, empty, bare;

DESCRIPTION:

full     the standing example: every node kind, every annotation, both
         link kinds, an exclusion set -- one print carrying it all.

empty    the empty plan: every section prints '(none)'; nothing else.

bare     nodes without links or exclusions; the choice-less TEST node
         printing as the file name alone.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.plan.form    import (CExclusionSet, CPlanLink,
                                                  CPlanNode, CTestPlan,
                                                  E_LinkKind, E_Provenance)
from vut.engine.orchestrator.plan.printer import print_plan


def test_full():
    """RETURN: None. Every node kind, annotation and link kind."""
    node_list = [
        CPlanNode.build("make"),
        CPlanNode.session("test-i.py"),
        CPlanNode.test("test-a.py", "one"),
        CPlanNode.test("test-a.py", "two"),
        CPlanNode.test("test-i.py", "x"),
        CPlanNode.test("test-i.py", "y"),
        CPlanNode.test("test-b.py", None,
                       provenance = E_Provenance.IMPLIED,
                       implied_by = "test-a.py one"),
        CPlanNode.test("test-c.py", None, misdep_f=True),
        CPlanNode.test("test-d.py", None, misdep_f=True,
                       provenance = E_Provenance.IMPLIED,
                       implied_by = "test-c.py"),
    ]
    link_list = [
        CPlanLink(E_LinkKind.ORDERING, "test-b.py",   "test-a.py one"),
        CPlanLink(E_LinkKind.ORDERING, "test-c.py",   "test-d.py"),
        CPlanLink(E_LinkKind.SUPPORTS, "build[make]", "test-a.py one"),
        CPlanLink(E_LinkKind.SUPPORTS, "build[make]", "test-a.py two"),
        CPlanLink(E_LinkKind.SUPPORTS, "session[test-i.py]",
                                       "test-i.py x"),
        CPlanLink(E_LinkKind.SUPPORTS, "session[test-i.py]",
                                       "test-i.py y"),
    ]
    exclusion_list = [
        CExclusionSet(("test-a.py", "test-i.py x")),
        CExclusionSet(("test-b.py", "test-c.py")),
    ]
    print_plan(CTestPlan(node_list, link_list, exclusion_list))


def test_empty():
    """RETURN: None. The empty plan: '(none)' per section."""
    print_plan(CTestPlan([]))


def test_bare():
    """RETURN: None. Nodes alone; the choice-less TEST node's name."""
    print_plan(CTestPlan([CPlanNode.test("solo.py", None),
                          CPlanNode.test("duo.py", "one"),
                          CPlanNode.test("duo.py", "two")]))


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Plan printer: the canonical text, one-way;", {
        "full":  test_full,
        "empty": test_empty,
        "bare":  test_bare,
    }).run()
