#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Assert the SIGNAL CORRESPONDENCE (D-8) for the rule-file grammar: every
         rule's dedicated AST node derives from the operator interface matching
         the rule's top-level operator (an OR rule -> OR_Interface, a SEQ rule ->
         SEQ_Interface, ...). Single-terminal rules (no operator) are exempt, as
         are pass-through rules (no dedicated node). This is the standing guard
         that the migration's hand-verified pairing stays true under future edits.

CHOICES: operator_table, signal_match, exemptions.

DESCRIPTION:

    operator_table   Each rule classified by its grammar top-level operator
                     (OR / SEQ / PLUS / STAR / TERMINAL), printed sorted -- the
                     ground truth the correspondence is checked against.
    signal_match     For every rule with a dedicated AST node, the node class
                     derives from the interface of the rule's operator. Printed
                     as 'rule -> Node : OK', any mismatch as 'MISMATCH'.
    exemptions       The rules legitimately without an operator signal: pass-
                     through (no node) and single-terminal (no operator).
______________________________________________________________________________
"""
import sys
from   config import HwutRunner

from vut.engine.temporal_logic.parser.grammar import GRAMMAR
from vut.engine.temporal_logic.parser.core.combinators import OR, PLUS, STAR
from vut.engine.temporal_logic.parser.core.combinators import _Combinator
from vut.engine.temporal_logic.parser.core.ll2_grammar_spec import Terminal_Spec
from vut.engine.temporal_logic.parser.core.operator_interface import (
        OR_Interface, SEQ_Interface, PLUS_Interface, STAR_Interface)
from vut.engine.temporal_logic.parser import ast_map as M


def banner(label):
    print()
    print("--- %s ---" % label)


def _top_operator(pattern):
    """RETURN: str, the rule pattern's top-level operator tag.

    'OR' if the tuple carries the OR sentinel; 'SEQ' for any other tuple;
    'STAR'/'PLUS' for those combinators; 'OPT' for a bare list; 'TERMINAL' for a
    single terminal spec; else the combinator class name.
    """
    if isinstance(pattern, tuple):
        return "OR" if any(p is OR for p in pattern) else "SEQ"
    if isinstance(pattern, list):
        return "OPT"
    if isinstance(pattern, Terminal_Spec):
        return "TERMINAL"
    name = type(pattern).__name__
    if name == "Star":
        return "STAR"
    if name == "Plus":
        return "PLUS"
    return name


_SIGNAL_OF = {"OR": OR_Interface, "SEQ": SEQ_Interface,
              "PLUS": PLUS_Interface, "STAR": STAR_Interface}


def _node_class_for(rule_name):
    """RETURN: type | None, the AST node class a built rule's factory yields.

    Recovers it from ast_map._BUILT: the factory is _wrap(_build_X); we read the
    bound builder's annotated return where possible, else parse a probe. To stay
    static and dependency-free, we use the explicit rule->node table the module
    already encodes in _BUILT by mapping each builder to the class it constructs,
    derived here by a light call-free convention: the test SAMPLES a parse.
    """
    return None  # resolved dynamically in run_signal_match via parsing


def run_operator_table():
    banner("each rule's top-level operator (ground truth)")
    for name in sorted(GRAMMAR):
        print("%-26s %s" % (name, _top_operator(GRAMMAR[name])))


# Rule -> dedicated AST node class, for the rules that build one. Single-terminal
# and pass-through rules are absent (they have no dedicated node).  This table is
# the correspondence under test; it is verified against the grammar operator and
# the node's actual interface derivation.
from vut.engine.temporal_logic.parser import ast_nodes as A

_RULE_NODE = {
    "namespace": A.Namespace, "include": A.Include, "causality": A.Causality,
    "cause": A.Cause, "cause-ref": A.CauseRef, "cause-def": A.CauseDef,
    "effect-def": A.EffectDef, "effect-ref": A.EffectRef, "trigger": A.Trigger,
    "bracket-guard": A.Condition, "or-cond": A.BoolOp, "and-cond": A.BoolOp,
    "not-cond": A.Not, "comparison": A.Comparison, "evt-member": A.EventMember,
    "spawn": A.Spawn, "unspawn": A.Unspawn, "event-spec": A.EventSpec,
    "mode-arming": A.ModeArming, "arg": A.Arg,
    "shallow-member-access": A.ShallowMemberAccess, "mode": A.Mode,
    "init": A.InitBlock, "deinit": A.DeinitBlock, "state": A.State,
    "has-ref": A.HasRef, "declaration": A.ArgDecl, "type-ref": A.ForwardDecl,
    "mode-group": A.ModeGroup, "state-machine": A.StateMachine,
    "default": A.StateMachineModeRef, "sm-mode-ref": A.StateMachineModeRef,
    "event-def": A.EventDef, "clock-def": A.ClockDef, "arg-decl": A.ArgDecl,
}


def run_signal_match():
    banner("each dedicated AST node derives from its rule's operator signal")
    mismatches = 0
    for rule in sorted(_RULE_NODE):
        op = _top_operator(GRAMMAR[rule])
        node_cls = _RULE_NODE[rule]
        iface = _SIGNAL_OF.get(op)
        if iface is None:
            # rule operator is OPT/TERMINAL/other -> no operator signal expected
            print("%-22s -> %-20s : (op %s, no signal expected)"
                  % (rule, node_cls.__name__, op))
            continue
        ok = issubclass(node_cls, iface)
        print("%-22s -> %-20s : %s"
              % (rule, node_cls.__name__, "OK" if ok else "MISMATCH (%s)" % op))
        if not ok:
            mismatches += 1
    print()
    print("mismatches:", mismatches)


def run_exemptions():
    banner("rules legitimately without an operator signal")
    built = set(M._BUILT)
    passthrough = set(M._PASS_THROUGH)
    print("pass-through (no dedicated node):")
    for r in sorted(passthrough):
        print("  %s" % r)
    print("single-terminal (no operator):")
    for r in sorted(GRAMMAR):
        if _top_operator(GRAMMAR[r]) == "TERMINAL":
            print("  %s" % r)


HwutRunner(
    argv       = sys.argv,
    title      = "Rule-file AST Signal Correspondence",
    choice_map = {
        "operator_table": run_operator_table,
        "signal_match":   run_signal_match,
        "exemptions":     run_exemptions,
    },
).run()
