#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the grammar-agnostic AST-MAP FAMILY (core/) in isolation --
         the routers (OrMap, OptMap) and the appliers (SeqMap, StarMap,
         PlusMap) -- driven by HAND-BUILT CST nodes, never the rule-file
         grammar. A router keys off what the CST node ITSELF carries (an OR's
         fired branch; an OPT's present flag); an applier applies ONE
         constructor uniformly. No parser, no grammar, no domain AST node is
         imported.

CHOICES: or_fired, or_role, or_shared, or_no_route, opt_present, opt_absent,
         opt_factory, seq_map, star_map, plus_map;

DESCRIPTION:

OrMap/OptMap route; SeqMap/StarMap/PlusMap apply (A-13 clarified: the
rejection of ARITY-ROUTING stands -- Star/PlusMap apply one item constructor
uniformly and produce the one product type NodeList regardless of arity).
Each choice pins one observable law.

    or_fired      OrMap routes by the fired branch's index: the leaf registered
                  for triggered_index N is applied to that branch's child, and a
                  different fired index selects a different leaf.
    or_role       OrMap routes by a branch's role string when the address is a
                  str: the role-keyed leaf fires, the index-keyed one does not.
    or_shared     A tuple address routes several branches through one leaf; each
                  member index resolves to that shared leaf.
    or_no_route   An OrMap with no route for the fired branch raises KeyError --
                  the hand-built-node guard (load gates totality in real use).
    opt_present   OptMap present=PASS forwards the fired body's child unchanged;
                  a factory present-leaf transforms it.
    opt_absent    The absent arm ALWAYS yields NodeAbsent, independent of the
                  present-leaf (A-13): PASS, a factory, or a constant present-leaf
                  all yield NodeAbsent when the optional did not fire.
    opt_factory   A FIRED optional over an all-silent body (present=True,
                  child=NodeAbsent) still routes through the present-leaf -- presence,
                  not child content, gates the transform.
    seq_map       SeqMap applies its one constructor to the finished sequence
                  node; PASS forwards the node unchanged (typed passthrough).
    star_map      StarMap applies one item leaf uniformly; the product is a
                  NodeList -- EMPTY (and falsey) for a star that matched
                  nothing, never a different product.
    plus_map      PlusMap is StarMap over a 1..n node: same one product type,
                  never empty.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.core.parser_generator.cst_nodes import (
        OR_Node, OPT_Node, SEQ_Node, STAR_Node, PLUS_Node, NodeAbsent)
from vut.engine.temporal_logic.core.parser_generator.ast_map_family import (
        OrMap, OptMap, SeqMap, StarMap, PlusMap, PASS)
from vut.engine.temporal_logic.core.symbol.ast import NodeList


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def show(label, value):
    """RETURN: None. Print 'label -> value' on one line."""
    print("%-28s -> %r" % (label, value))


def or_node(index, child, role=None):
    """RETURN: OR_Node, an alternation whose branch 'index' fired with 'child'.

    'role' is the optional advisory tag the str-keyed routing address matches.
    """
    return OR_Node(triggered_index=index, child=child, role=role)


def opt_node(present, child):
    """RETURN: OPT_Node, an optional that fired iff 'present', carrying 'child'."""
    return OPT_Node(present=present, child=child)


# A factory present/branch-leaf: tags its routed value so the route is visible.
def tag(value):
    """RETURN: tuple, ('got', value) -- a factory leaf that marks what it routed."""
    return ("got", value)


def run_or_fired():
    """RETURN: None. OrMap selects the leaf of the branch that actually fired."""
    banner("OrMap: fired branch index selects the leaf")
    router = OrMap({0: PASS, 1: tag})
    show("branch 0 (PASS) -> child", router(or_node(0, "A")))
    show("branch 1 (tag)  -> child", router(or_node(1, "B")))


def run_or_role():
    """RETURN: None. A str address routes by the fired branch's role, not index."""
    banner("OrMap: role-keyed address routes the tagged branch")
    router = OrMap({"named": tag, 0: PASS})
    show("fired role 'named'", router(or_node(7, "B", role="named")))
    show("fired index 0", router(or_node(0, "A", role=None)))


def run_or_shared():
    """RETURN: None. A tuple address shares one leaf across several branches."""
    banner("OrMap: tuple address shares one leaf")
    router = OrMap({(0, 2): tag, 1: PASS})
    show("branch 0 -> shared tag", router(or_node(0, "A")))
    show("branch 2 -> shared tag", router(or_node(2, "C")))
    show("branch 1 -> PASS", router(or_node(1, "B")))


def run_or_no_route():
    """RETURN: None. No route for the fired branch raises KeyError."""
    banner("OrMap: unrouted fired branch raises KeyError")
    router = OrMap({0: PASS})
    try:
        router(or_node(1, "B"))
        show("no error", "UNEXPECTED")
    except KeyError as e:
        show("KeyError", str(e))


def run_opt_present():
    """RETURN: None. Present routes the child through the present-leaf."""
    banner("OptMap: present routes child through present-leaf")
    show("PASS present", OptMap()(opt_node(True, "X")))
    show("PASS present (explicit)", OptMap(present=PASS)(opt_node(True, "Y")))
    show("factory present", OptMap(present=tag)(opt_node(True, "Z")))


def run_opt_absent():
    """RETURN: None, always. The absent arm yields NodeAbsent, whatever the present-leaf (A-13)."""
    banner("OptMap: absent arm ALWAYS yields NodeAbsent (A-13, non-negotiable)")
    show("absent, present=PASS", OptMap(present=PASS)(opt_node(False, NodeAbsent)))
    show("absent, present=factory", OptMap(present=tag)(opt_node(False, NodeAbsent)))
    show("absent, present=constant", OptMap(present=42)(opt_node(False, NodeAbsent)))


def run_opt_factory():
    """RETURN: None. A fired optional over an all-silent body still routes.

    present=True with child=NodeAbsent is a FIRED optional whose body produced no
    surviving value; presence gates the transform, so the present-leaf runs on
    NodeAbsent rather than the absent branch's own NodeAbsent.
    """
    banner("OptMap: fired-but-silent body routes on presence, not content")
    show("present, child=NodeAbsent, PASS", OptMap()(opt_node(True, NodeAbsent)))
    show("present, child=NodeAbsent, tag", OptMap(present=tag)(opt_node(True, NodeAbsent)))


def run_seq_map():
    """RETURN: None, always. SeqMap applies its one constructor to the node.

    The constructor reads the node it receives; PASS is the explicit typed
    passthrough (the coverage gate sees a mapped rule either way).
    """
    banner("SeqMap: one constructor over the finished sequence node")
    node = SEQ_Node(children=("A", "B"), roles=("left", "right"), name="pair")
    show("factory ctor", SeqMap(tag)(node))
    show("PASS ctor", SeqMap(PASS)(node) is node)
    show("ctor reads by role", SeqMap(lambda n: n["right"])(node))


def run_star_map():
    """RETURN: None, always. StarMap yields ONE product type: NodeList.

    Empty match -> EMPTY NodeList (falsey), n matches -> n items in match
    order; the item leaf is applied uniformly (A-13: no arity routing).
    """
    banner("StarMap: uniform item leaf, NodeList product, emptiness is a state")
    empty = STAR_Node(items=(), name="<xs>")
    full  = STAR_Node(items=("A", "B", "C"), name="<xs>")
    e = StarMap(tag)(empty)
    show("empty star -> NodeList", e)
    show("empty star -> falsey", not e)
    f = StarMap(tag)(full)
    show("3-item star -> NodeList", f)
    show("len", len(f))
    show("PASS items", StarMap()(full))


def run_plus_map():
    """RETURN: None, always. PlusMap is StarMap over a 1..n node: never empty."""
    banner("PlusMap: same product type, never empty (engine guarantees 1..n)")
    one  = PLUS_Node(items=("A",), name="<ys>")
    many = PLUS_Node(items=("A", "B"), name="<ys>")
    show("1-item plus", PlusMap(tag)(one))
    show("2-item plus", PlusMap(tag)(many))
    show("truthy", bool(PlusMap()(one)))


HwutRunner(
    argv       = sys.argv,
    title      = "AST-Map Family (routers + appliers)",
    choice_map = {
        "or_fired":    run_or_fired,
        "or_role":     run_or_role,
        "or_shared":   run_or_shared,
        "or_no_route": run_or_no_route,
        "opt_present": run_opt_present,
        "opt_absent":  run_opt_absent,
        "opt_factory": run_opt_factory,
        "seq_map":     run_seq_map,
        "star_map":    run_star_map,
        "plus_map":    run_plus_map,
    },
).run()
