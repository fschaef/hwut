#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the grammar-agnostic CST machinery (core/) in isolation, on small
         TOY grammars defined here -- never the rule-file language. What is under
         test: the canonical CST the engine builds by default (cst_nodes), the
         operator SIGNAL interfaces (operator_interface), the transformer overlay
         (a partial rule-name -> factory map), children-transformed-first
         (bottom-up), and absent-optional carried as an OPT_Node state.

CHOICES: cst_shapes, absent_optional, silent_optional, signals, overlay,
         overlay_partial, children_first.

DESCRIPTION:

    cst_shapes        A grammar exercising SEQ / OR / STAR / PLUS yields the four
                      canonical CST node kinds, with rule names stamped on rule
                      nodes and None on inline operators.
    absent_optional   An inline optional is an OPT_Node: 'present' marks
                      whether it fired, 'child' is the body's value or ABSENT;
                      the parent SEQ keeps a STABLE slot either way -- presence
                      is read off the node, never inferred from child count.
    silent_optional   An optional over an ALL-SILENT body keeps fired-ness:
                      present=True with child=ABSENT (fired) is distinguishable
                      from present=False (absent).
    signals           Every CST node derives from the operator interface matching
                      its shape (OR_Node IS OR_Interface, etc.); the interfaces
                      are signals -- isinstance against them reports shape.
    overlay           A partial transformer map refines selected rules into typed
                      values; rules without a transformer pass their CST node
                      through untouched.
    overlay_partial   With NO transformer map the engine yields pure CST; the
                      same grammar with a partial map yields a mixed CST/typed
                      tree -- the overlay is opt-in per rule.
    children_first    A parent transformer sees its children ALREADY transformed
                      (bottom-up): the inner rule's factory ran before the outer's.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.parser.core.combinators import OR, STAR, PLUS
from vut.engine.temporal_logic.parser.core.ll2_grammar_spec import T
from vut.engine.temporal_logic.parser.core.ll2_engine import Grammar, EngineParser
from vut.engine.temporal_logic.parser.core.lexer import register_grammar
from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.parser.core.cst_nodes import (
        OR_Node, OPT_Node, SEQ_Node, PLUS_Node, STAR_Node, ABSENT)
from vut.engine.temporal_logic.parser.core.operator_interface import (
        OR_Interface, OPT_Interface, SEQ_Interface, PLUS_Interface,
        STAR_Interface)


# '@'-led toy terminals: no other terminal in the process-global DB can match the
# same lexeme, so token identity stays unambiguous (see test-engine.py rationale).
t_a = T.regex(r'@a\b')
t_b = T.regex(r'@b\b')
t_c = T.regex(r'@c\b')


class _ToyOracle:
    """A no-op span oracle; the toy grammars contain no opaque spans."""
    def measure(self, *a, **k):
        return None


def banner(title):
    print("--- %s ---" % title)


def _show(node, indent=0):
    """RETURN: None. Print a deterministic indented rendering of a CST/value tree."""
    pad = "  " * indent
    if isinstance(node, OR_Node):
        print("%sOR name=%r index=%d" % (pad, node.name, node.triggered_index))
        if node.child is ABSENT:
            print("%s  <absent>" % pad)
        else:
            _show(node.child, indent + 1)
    elif isinstance(node, OPT_Node):
        print("%sOPT name=%r" % (pad, node.name))
        if node.child is not ABSENT:
            _show(node.child, indent + 1)
        elif node.present:
            print("%s  <fired, all-silent body>" % pad)
        else:
            print("%s  <absent>" % pad)
    elif isinstance(node, SEQ_Node):
        print("%sSEQ name=%r (%d)" % (pad, node.name, len(node.children)))
        for c in node.children:
            _show(c, indent + 1)
    elif isinstance(node, (PLUS_Node, STAR_Node)):
        print("%s%s name=%r (%d)" % (pad, type(node).__name__, node.name,
                                     len(node.items)))
        for c in node.items:
            _show(c, indent + 1)
    else:
        text = getattr(node, "text", node)
        print("%sLEAF %r" % (pad, text))


def _parse(grammar, start, src, transformers=None):
    """RETURN: object, the parse of 'src' (pure CST, or overlaid if transformers)."""
    register_grammar(grammar)
    if transformers is None:
        g = Grammar(grammar, cst=True, start=start)
    else:
        g = Grammar(grammar, transformers=transformers, start=start)
    rep = DiagnosticReporter()
    return EngineParser(src, _ToyOracle(), rep, g)._match(g.rules[start]), rep


# --- choices ---------------------------------------------------------------

_SHAPES_GRAMMAR = {
    "seqr":  (t_a, "<orr>", "<starr>"),
    "orr":   (t_b, OR, t_c),
    "starr": STAR(t_a),
    "plusr": PLUS(t_b),
}


def run_cst_shapes():
    banner("SEQ/OR/STAR yield the four canonical CST kinds, names stamped")
    node, _ = _parse(_SHAPES_GRAMMAR, "seqr", "@a @b @a @a")
    _show(node)
    banner("PLUS rule")
    node2, _ = _parse(_SHAPES_GRAMMAR, "plusr", "@b @b")
    _show(node2)


_OPT_GRAMMAR = {
    "decl": (t_a, [t_b], t_c),     # inline optional [t_b] in the middle slot
}


def run_absent_optional():
    banner("optional PRESENT: OPT_Node child = value; SEQ slot stable")
    node, _ = _parse(_OPT_GRAMMAR, "decl", "@a @b @c")
    _show(node)
    banner("optional ABSENT: OPT_Node child = ABSENT; SEQ slot STILL there")
    node2, _ = _parse(_OPT_GRAMMAR, "decl", "@a @c")
    _show(node2)


_SILENT_OPT_GRAMMAR = {
    "tail": (t_a, ["sep"]),       # the optional's whole body is a silent keyword
}


def run_silent_optional():
    banner("fired over all-silent body: present=True, child=ABSENT")
    node, _ = _parse(_SILENT_OPT_GRAMMAR, "tail", "@a sep")
    _show(node)
    opt = node.children[1]
    print("present:", opt.present, " child is ABSENT:", opt.child is ABSENT)
    banner("absent: present=False, child=ABSENT")
    node2, _ = _parse(_SILENT_OPT_GRAMMAR, "tail", "@a")
    _show(node2)
    opt2 = node2.children[1]
    print("present:", opt2.present, " child is ABSENT:", opt2.child is ABSENT)


def run_signals():
    banner("every CST node IS its operator-interface signal")
    node, _ = _parse(_SHAPES_GRAMMAR, "seqr", "@a @b")
    print("seqr root is SEQ_Interface:", isinstance(node, SEQ_Interface))
    orn = node.children[1]
    print("orr     is OR_Interface :", isinstance(orn, OR_Interface))
    starn = node.children[2]
    print("starr   is STAR_Interface:", isinstance(starn, STAR_Interface))
    node2, _ = _parse(_SHAPES_GRAMMAR, "plusr", "@b")
    print("plusr   is PLUS_Interface:", isinstance(node2, PLUS_Interface))
    print("OR is not SEQ           :", not isinstance(orn, SEQ_Interface))
    node3, _ = _parse(_OPT_GRAMMAR, "decl", "@a @c")
    optn = node3.children[1]
    print("optional is OPT_Interface:", isinstance(optn, OPT_Interface))
    print("OPT is not OR           :", not isinstance(optn, OR_Interface))


def run_overlay():
    banner("partial overlay: 'orr' transformed, 'seqr'/'starr' left as CST")
    transformers = {
        "orr": lambda n: ("CHOSE", n.triggered_index),
    }
    node, _ = _parse(_SHAPES_GRAMMAR, "seqr", "@a @c @a", transformers)
    # seqr has no transformer -> still a SEQ_Node; its orr child is transformed.
    print("root type:", type(node).__name__)
    print("orr slot :", node.children[1])
    print("star slot type:", type(node.children[2]).__name__)


def run_overlay_partial():
    banner("no transformers => pure CST")
    node, _ = _parse(_SHAPES_GRAMMAR, "orr", "@b")
    print("pure:", type(node).__name__, "index", node.triggered_index)
    banner("partial map => mixed tree (same grammar, opt-in per rule)")
    node2, _ = _parse(_SHAPES_GRAMMAR, "orr", "@b", {"orr": lambda n: "TYPED"})
    print("typed:", node2)


_NEST_GRAMMAR = {
    "outer": (t_a, "<inner>"),
    "inner": (t_b, OR, t_c),
}


def run_children_first():
    banner("bottom-up: the inner transformer runs before the outer sees it")
    order = []
    def x_inner(n):
        order.append("inner")
        return ("inner-done", n.triggered_index)
    def x_outer(n):
        order.append("outer")
        # by now children[1] is the FINISHED inner value, not a raw OR_Node
        return ("outer-sees", n.children[1])
    node, _ = _parse(_NEST_GRAMMAR, "outer", "@a @b",
                     {"inner": x_inner, "outer": x_outer})
    print("call order:", order)
    print("outer received:", node)


HwutRunner(
    argv       = sys.argv,
    title      = "Core CST + Overlay Machinery",
    choice_map = {
        "cst_shapes":      run_cst_shapes,
        "absent_optional": run_absent_optional,
        "silent_optional": run_silent_optional,
        "signals":         run_signals,
        "overlay":         run_overlay,
        "overlay_partial": run_overlay_partial,
        "children_first":  run_children_first,
    },
).run()
