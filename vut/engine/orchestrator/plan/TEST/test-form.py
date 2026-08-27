#! /usr/bin/env python3
#
# hwut {
#     title      = "Plan form: nodes, links, exclusions, laws at the door"
#     choices    = ["closure", "derived", "nodes", "refused", "stage"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FORM -- nodes, links, exclusion sets, and the construction
         laws of 'CTestPlan'.

CHOICES: nodes, derived, refused, closure;

DESCRIPTION:

nodes    the three node kinds, their names, and the annotations a TEST
         node carries: '[MISDEP]', provenance, 'implied_by'.

derived  the tables 'CTestPlan' derives at construction: before_db,
         supports_db, supporter_db; and 'exclusion_sets_of'.

refused  every construction law, violated one at a time: the plan never
         comes into being, the message names the offender.

closure  the R-35 closure asserted by the form: an ordering link may
         leave a [MISDEP] node for a [MISDEP] node alone; and a cycle
         in the ordering links is refused, naming its members.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.plan.form import (E_ProvisionStage,
                                                CExclusionSet, CPlanLink,
                                               CPlanNode, CTestPlan,
                                               E_LinkKind, E_NodeKind,
                                               E_Provenance)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def small_plan():
    """
    RETURN: CTestPlan, the standing example: two applications, one
            build, one interactive session, one implied case, one
            [MISDEP] pair, one exclusion set.
    """
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
        CPlanNode.test("test-d.py", None, misdep_f=True),
    ]
    link_list = [
        CPlanLink(E_LinkKind.ORDERING, "test-b.py",    "test-a.py one"),
        CPlanLink(E_LinkKind.ORDERING, "test-c.py",    "test-d.py"),
        CPlanLink(E_LinkKind.SUPPORTS, "build[make]",  "test-a.py one"),
        CPlanLink(E_LinkKind.SUPPORTS, "build[make]",  "test-a.py two"),
        CPlanLink(E_LinkKind.SUPPORTS, "session[test-i.py]",
                                       "test-i.py x"),
        CPlanLink(E_LinkKind.SUPPORTS, "session[test-i.py]",
                                       "test-i.py y"),
    ]
    exclusion_list = [
        CExclusionSet(("test-a.py", "test-i.py x")),
    ]
    return CTestPlan(node_list, link_list, exclusion_list)


def test_nodes():
    """RETURN: None. The three kinds, names and annotations."""
    banner("names, one per kind")
    for node in (CPlanNode.test("t.py", "one"),
                 CPlanNode.test("t.py", None),
                 CPlanNode.build("make all"),
                 CPlanNode.session("t.py")):
        print("    %-20s %s" % (node.name(), node.kind.name))

    banner("the TEST node's annotations")
    named   = CPlanNode.test("t.py", "one")
    implied = CPlanNode.test("u.py", None,
                             provenance = E_Provenance.IMPLIED,
                             implied_by = "t.py one")
    misdep  = CPlanNode.test("v.py", None, misdep_f=True)
    for node in (named, implied, misdep):
        print("    %-10s provenance=%-8s implied_by=%-10s misdep_f=%s"
              % (node.name(), node.provenance.name,
                 node.implied_by, node.misdep_f))

    banner("provenance and implied_by contradict: refused")
    try:
        CPlanNode.test("t.py", "one", implied_by="u.py")
    except AssertionError as error:
        print("REFUSED: %s" % error)
    try:
        CPlanNode.test("t.py", "one",
                       provenance=E_Provenance.IMPLIED)
    except AssertionError as error:
        print("REFUSED: %s" % error)


def test_derived():
    """RETURN: None. The derived tables of the standing example."""
    plan = small_plan()
    banner("the plan")
    print("%d node(s):" % len(plan))
    for node in plan:
        print("    %s" % node.name())

    banner("before_db")
    for name in sorted(plan.before_db):
        print("    %-16s <- %s"
              % (name, ", ".join(plan.before_db[name])))

    banner("supports_db")
    for name in sorted(plan.supports_db):
        print("    %-20s ==> %s"
              % (name, ", ".join(plan.supports_db[name])))

    banner("supporter_db")
    for name in sorted(plan.supporter_db):
        print("    %-16s <== %s"
              % (name, ", ".join(plan.supporter_db[name])))

    banner("exclusion_sets_of")
    for name in ("test-a.py one", "test-a.py two", "test-i.py x",
                 "test-i.py y", "build[make]", "no-such-node"):
        set_list = plan.exclusion_sets_of(name)
        text = "; ".join("{ %s }" % ", ".join(x.member_tuple)
                         for x in set_list) or "-"
        print("    %-16s %s" % (name, text))


def test_refused():
    """RETURN: None. Every construction law, violated one at a time."""
    a   = CPlanNode.test("a.py", "one")
    b   = CPlanNode.test("b.py", None)
    mk  = CPlanNode.build("make")
    ses = CPlanNode.session("a.py")

    def refused(label, node_list, link_list=(), exclusion_list=()):
        banner(label)
        try:
            CTestPlan(node_list, link_list, exclusion_list)
            print("NOT REFUSED -- a law is broken")
        except AssertionError as error:
            print("REFUSED: %s" % error)

    refused("two nodes of one name",
            [a, CPlanNode.test("a.py", "one")])
    refused("a link source naming no node",
            [a], [CPlanLink(E_LinkKind.ORDERING, "ghost.py", "a.py one")])
    refused("a link target naming no node",
            [a], [CPlanLink(E_LinkKind.ORDERING, "a.py one", "ghost.py")])
    refused("an ordering link whose end is a BUILD node",
            [a, mk],
            [CPlanLink(E_LinkKind.ORDERING, "build[make]", "a.py one")])
    refused("a supports link whose source is a TEST node",
            [a, b],
            [CPlanLink(E_LinkKind.SUPPORTS, "b.py", "a.py one")])
    refused("a supports link whose target is a BUILD node",
            [a, mk],
            [CPlanLink(E_LinkKind.SUPPORTS, "build[make]", "build[make]")])
    refused("a session supporting a choice of another file",
            [CPlanNode.test("b.py", "one"), ses],
            [CPlanLink(E_LinkKind.SUPPORTS, "session[a.py]", "b.py one")])
    refused("an exclusion member covering no TEST node",
            [a], (), [CExclusionSet(("a.py one", "ghost.py"))])
    refused("an exclusion member naming only a BUILD node",
            [a, mk], (), [CExclusionSet(("build[make]",))])


def test_closure():
    """RETURN: None. The R-35 closure and the cycle assertion."""
    banner("[MISDEP] -> non-[MISDEP]: refused")
    m = CPlanNode.test("m.py", None, misdep_f=True)
    a = CPlanNode.test("a.py", None)
    try:
        CTestPlan([m, a],
                  [CPlanLink(E_LinkKind.ORDERING, "m.py", "a.py")])
        print("NOT REFUSED -- a law is broken")
    except AssertionError as error:
        print("REFUSED: %s" % error)

    banner("[MISDEP] -> [MISDEP]: stands")
    n = CPlanNode.test("n.py", None, misdep_f=True)
    plan = CTestPlan([m, n],
                     [CPlanLink(E_LinkKind.ORDERING, "m.py", "n.py")])
    print("%d node(s); before_db: %s"
          % (len(plan),
             {k: list(v) for k, v in plan.before_db.items()}))

    banner("a cycle in the ordering links: refused, members named")
    a = CPlanNode.test("a.py", None)
    b = CPlanNode.test("b.py", None)
    c = CPlanNode.test("c.py", None)
    try:
        CTestPlan([a, b, c],
                  [CPlanLink(E_LinkKind.ORDERING, "a.py", "b.py"),
                   CPlanLink(E_LinkKind.ORDERING, "b.py", "c.py"),
                   CPlanLink(E_LinkKind.ORDERING, "c.py", "a.py")])
        print("NOT REFUSED -- a law is broken")
    except AssertionError as error:
        print("REFUSED: %s" % error)




def test_stage():
    """THE PROVISION LADDER (P-18): 'provision_stage()' is DERIVED from
    the kind, stored nowhere -- a SESSION is the shared facet of
    EXECUTE, a TEST is the case itself on the same rung."""
    build   = CPlanNode.build("make lib")
    session = CPlanNode.session("test-app.py")
    test    = CPlanNode.test("test-app.py", "one")
    for node in (build, session, test):
        print("    %-22s %-8s -> %s"
              % (node.name(), node.kind.name,
                 node.provision_stage().name))
    print("    the ladder's rungs: %s"
          % ", ".join(stage.name for stage in E_ProvisionStage))


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Plan form: nodes, links, exclusions, laws at the door;", {
        "nodes":   test_nodes,
        "derived": test_derived,
        "refused": test_refused,
        "stage":    test_stage,
        "closure": test_closure,
    }).run()
