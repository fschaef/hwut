#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the AST-map ROUTER FAMILY (D-19): OrMap / OptMap / StarMap as
         callable routers over CST nodes, the route-leaf forms (factory /
         constant / PASS), and the load-time SHAPE GATE that pins each router to
         its rule shape and validates an OrMap's branch addresses. The real
         grammar is the fixture for routing; crafted bad entries exercise the
         gate.

CHOICES: routing, leaves, shape_gate, address_gate.

DESCRIPTION:

    routing       Drive the three converted OR rules (algebr/atom, code-block,
                  type) through the live parser and show each fired branch
                  routes to the right product -- index routing, role routing
                  (type's named-id branch), and grouped-index routing
                  (algebr/atom's literal group).
    leaves        OptMap / StarMap over hand-built CST nodes: a present optional
                  routes its child through a factory; an absent one yields the
                  constant leaf; a non-empty STAR folds, an empty one yields the
                  constant. PASS forwards the routed value unchanged.
    shape_gate    A router on the wrong shape (OrMap on a SEQ rule, OptMap on an
                  OR rule) is a MapShapeError at load, naming the rule -- the
                  gate reads the rule's OWN shape, never the product.
    address_gate  An OrMap whose addresses miss a branch, index out of range, or
                  name a role no branch carries is a MapShapeError, each
                  violation naming the rule.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.parser.grammar import GRAMMAR as _AUTHORED
from vut.engine.temporal_logic.parser.core.subspace import flatten as _flatten
GRAMMAR, _SCOPE = _flatten(_AUTHORED)   # subspaces lowered to the flat qualified-named map
from vut.engine.temporal_logic.parser.core.lexer import register_grammar
from vut.engine.temporal_logic.parser.core.ll2_engine import Grammar, EngineParser
from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.parser.core.cst_nodes import (
        OR_Node, OPT_Node, STAR_Node, ABSENT)
from vut.engine.temporal_logic.parser import ast_map as M
from vut.engine.temporal_logic.parser.core.ast_map_family import (
        OrMap, OptMap, StarMap, PASS)
from fake_luau_oracle import FakeLuauOracle


def banner(label):
    print()
    print("--- %s ---" % label)


def _cst_grammar():
    """RETURN: Grammar, the real grammar compiled CST-only (raw OR_Nodes)."""
    register_grammar(_AUTHORED)
    return Grammar(_AUTHORED, cst=True, start="top-level")


def _ast_grammar():
    """RETURN: Grammar, the real grammar with the AST_MAP transformer overlay,
               so a matched rule's children arrive already as final products."""
    register_grammar(_AUTHORED)
    return Grammar(_AUTHORED, transformers=M.AST_MAP, start="top-level")


def _match(g, rule, src):
    """RETURN: CST node, the raw parse of 'src' from 'rule' (errors asserted 0)."""
    rep = DiagnosticReporter()
    node = EngineParser(src, FakeLuauOracle(), rep, g)._match(g.rules[rule])
    assert not rep.errors, (rule, src, rep.errors)
    return node


def run_routing():
    g = _ast_grammar()

    def product(rule, src):
        """RETURN: str, the type name of the rule's transformed product."""
        rep = DiagnosticReporter()
        v = EngineParser(src, FakeLuauOracle(), rep, g)._match(g.rules[rule])
        assert not rep.errors, (rule, src, rep.errors)
        return type(v).__name__ if not isinstance(v, (list, str)) else repr(v)

    banner("code-block: branch 0 -> OpaqueCode, branch 1 -> DoSweep (PASS)")
    print("{ x = 1 }              ->", product("code-block", "{ x = 1 }"))
    print("do: instant: X ( ) :end ->",
          product("code-block", "do: instant: X ( ) :end"))

    banner("type: built-in & named-id -> text; nested dict -> DictType (PASS)")
    print("int               ->", product("type", "int"))
    print("MyStruct          ->", product("type", "MyStruct"))
    print("dict < int , int> ->", product("type", "dict < int , int >"))

    banner("algebr/atom: literal group -> Literal; opaque -> OpaqueCode")
    print("42      ->", product("algebr/atom", "42"))
    print("\"hi\"    ->", product("algebr/atom", "\"hi\""))
    print("true    ->", product("algebr/atom", "true"))


def run_leaves():
    banner("OptMap: present routes child through factory; absent -> constant")
    om = OptMap({True: lambda c: ("got", c), False: []})
    present = OPT_Node(present=True, child="X", begin=0)
    absent  = OPT_Node(present=False, child=ABSENT, begin=0)
    print("present ->", om(present))
    print("absent  ->", om(absent))

    banner("OptMap default leaves: missing True -> PASS, missing False -> None")
    om2 = OptMap({})
    print("present (PASS) ->", om2(OPT_Node(present=True, child="Y", begin=0)))
    print("absent  (None) ->", om2(OPT_Node(present=False, child=ABSENT, begin=0)))

    banner("StarMap: non-empty folds the node; empty -> constant")
    sm = StarMap({True: lambda node: len(node.items), False: 0})
    print("three items ->", sm(STAR_Node(items=(1, 2, 3), begin=0)))
    print("empty       ->", sm(STAR_Node(items=(), begin=0)))

    banner("PASS leaf forwards the routed value unchanged")
    op = OptMap({True: PASS, False: None})
    print("present ->", op(OPT_Node(present=True, child="Z", begin=0)))


def _expect_shape_error(label, rule, entry):
    """RETURN: None. Swaps 'entry' onto 'rule', runs the gate, prints violations."""
    g = _cst_grammar()
    saved = dict(M.AST_MAP)
    try:
        M.AST_MAP[rule] = entry
        M.validate_ast_map_shapes(g)
        print("%s: NO ERROR (unexpected)" % label)
    except M.MapShapeError as exc:
        for v in exc.violations:
            print("  %s" % v)
    finally:
        M.AST_MAP.clear()
        M.AST_MAP.update(saved)


def run_shape_gate():
    banner("OrMap on a SEQ rule -> MapShapeError")
    _expect_shape_error("OrMap-on-SEQ", "step/spawn", OrMap({0: PASS}))

    banner("OptMap on an OR rule -> MapShapeError")
    _expect_shape_error("OptMap-on-OR", "code-block", OptMap({True: PASS}))


def run_address_gate():
    banner("OrMap index out of range + branch left unrouted")
    _expect_shape_error("bad-index", "code-block", OrMap({0: PASS, 9: PASS}))

    banner("OrMap role that tags no branch + branch left unrouted")
    _expect_shape_error("bad-role", "type", OrMap({(0, 1, 2): PASS, "nosuch": PASS}))


HwutRunner(
    argv       = sys.argv,
    title      = "AST-Map Router Family",
    choice_map = {
        "routing":      run_routing,
        "leaves":       run_leaves,
        "shape_gate":   run_shape_gate,
        "address_gate": run_address_gate,
    },
).run()
