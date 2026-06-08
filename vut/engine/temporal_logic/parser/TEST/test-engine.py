#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the table-driven parse engine and the declarative grammar.

CHOICES: first_sets, ll1_ok, ll1_conflict, token_inventory;

DESCRIPTION:

The engine compiles the declarative GRAMMAR (syntax.py) to a node tree, computes
FIRST sets, validates LL(1), and interprets the result to build the AST.

    first_sets       Computed FIRST sets for representative rules match the
                     tokens that can actually begin each construct.
    ll1_ok           The real rule-file grammar compiles and passes LL(1)
                     validation without conflict.
    ll1_conflict     A deliberately ambiguous grammar (two ALT branches sharing
                     a FIRST token) is rejected with a located conflict report.
    token_inventory  The generated token inventory, derived from the terminal
                     database (no literal table -- a token's identity is its
                     Terminal object), covers every fixed-spelling terminal the
                     grammar refers to.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner 

from   dataclasses import is_dataclass, fields

from vut.engine.temporal_logic.parser.core.combinators import ALT
from vut.engine.temporal_logic.parser.core.terminals import T

from vut.engine.temporal_logic.parser.core.ll1_engine import (Grammar,
                                                              LL1ConflictError)
from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar
from vut.engine.temporal_logic.parser.core.lexer import token_spec, token_debug_names
from   vut.engine.temporal_logic.parser.core import grammar_ast as N
import vut.engine.temporal_logic.parser.grammar as G


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def norm(node):
    """
    RETURN: a hashable nested structure mirroring 'node' for comparison.

    Dataclass nodes become (type-name, field-dict); lists recurse; leaves pass
    through. Two ASTs are equal iff their norms are equal.
    """
    if isinstance(node, list):
        return [norm(x) for x in node]
    if is_dataclass(node):
        return (type(node).__name__,
                tuple((f.name, norm(getattr(node, f.name)))
                      for f in fields(node)))
    return node


# Inputs exercising one per construct plus mixed cases (kept for ad-hoc use).
_SPREAD = [
    'on: Tick & { event.n > 0 } => Beep()',
    'on: ANY => Log()',
    ('on: Tick => Beep(3) => ! Blink() '
     '=> "tick {event.n}" => { sm.n = sm.n + 1 }'),
    'mode: Blink\n on Tick => Toggle()\n init: { sm.x = 0 }\n until: ANY\n',
    ('state_machine: Traffic\n default: Traffic.RED\n'
     ' state: RED\n  on Tick => Switch()\n until: ANY\n :end\n'),
    'state_machine: Idle\n default: Idle.VOID\n has: Other.VOID\n :end\n',
    ('mode_group: Lights\n init: { sm.x = 0 }\n'
     ' mode: Blink\n  on Tick => Toggle()\n until: ANY\n has: Glow\n :end\n'),
    'event: Move(dx: int ; dy: int)',
    'clock: Tick 100',
    'on: X => Honk({ event.hz * 2 }, 5)',
    'on: Boom => +! SmTraffic() in: north => ! Blink()',
    'on: Clear => -! north',
    'Ghosts is: container<fifo, 64> as: { db.ghosts }',
]


def run_first_sets():
    """RETURN: None. FIRST sets of representative rules."""
    g = compiled_grammar()
    banner("FIRST sets of key rules")
    for name in ("top-level", "trigger", "effect", "rvalue",
                 "mode-elm", "state-machine-elm", "mode-group-elm"):
        toks = sorted(t._name() for t in g.rules[name].first)
        print("%-22s %s" % (name, ", ".join(toks)))


def run_ll1_ok():
    """RETURN: None. The real grammar compiles and is LL(1)."""
    banner("compile and validate the rule-file grammar")
    g = compiled_grammar()
    print("rules compiled:", len(g.rules))
    print("start symbol:  ", g.start)
    print("LL(1):          yes (no conflict raised)")


def run_ll1_conflict():
    """RETURN: None. An ambiguous grammar is rejected with a located report."""
    banner("two ALT branches sharing a FIRST token")
    t_re_id = T.regex(r'[a-zA-Z_]\w*')
    bad = {
        "top-level": ("<a>", ALT, "<b>"),
        "a":         (t_re_id, ":end"),
        "b":         (t_re_id, "on:"),
    }
    actions = {"top-level": None, "a": None, "b": None}
    try:
        Grammar(bad, actions, start="top-level")
        print("UNEXPECTED: no conflict detected")
    except LL1ConflictError as exc:
        print("rejected with %d conflict(s):" % len(exc.conflicts))
        for c in exc.conflicts:
            print("  ", c)


def run_token_inventory():
    """RETURN: None. The generated token inventory, and grammar coverage.

    Token identity is the Terminal object; there is no literal table. This lists
    every generated token by its debug name and pattern, then checks that every
    silent keyword the grammar uses is a registered token.
    """
    banner("generated tokens (debug name -> pattern)")
    names = token_debug_names()
    for term, pattern in sorted(token_spec(), key=lambda kp: names[kp[0]]):
        print("%-22s %r" % (names[term], pattern))

    banner("every silent keyword in the grammar is a registered token")
    g = compiled_grammar()
    known = {term for term, _ in token_spec()}
    missing = []
    for name, nt in g.rules.items():
        for term in _silent_terminals(nt.pattern):
            if term not in known:
                missing.append((name, names.get(term, term._name())))
    print("unresolved:", sorted(missing) if missing else "(none)")


def _silent_terminals(node, seen=None):
    """RETURN: set, the Terminal of every silent TerminalNode reachable in 'node'.

    Walks the compiled object tree (SeqNode.parts / AltNode.branches /
    {Opt,Plus,Star}Node.body / NonTerminalNode.pattern). NonTerminals are visited
    once (cycle guard) so a recursive rule terminates.
    """
    if seen is None:
        seen = set()
    out = set()
    if isinstance(node, N.TerminalNode):
        if node.silent:
            out.add(node.token_id)
    elif isinstance(node, N.LuauNode):
        pass
    elif isinstance(node, N.NonTerminalNode):
        if node.name not in seen:
            seen.add(node.name)
            out |= _silent_terminals(node.pattern, seen)
    elif isinstance(node, N.SeqNode):
        for sub in node.parts:
            out |= _silent_terminals(sub, seen)
    elif isinstance(node, N.AltNode):
        for sub in node.branches:
            out |= _silent_terminals(sub, seen)
    elif isinstance(node, (N.OptNode, N.PlusNode, N.StarNode)):
        out |= _silent_terminals(node.body, seen)
    return out


HwutRunner(
    argv       = sys.argv,
    title      = "Table-driven Parse Engine",
    choice_map = {
        "first_sets":       run_first_sets,
        "ll1_ok":           run_ll1_ok,
        "ll1_conflict":     run_ll1_conflict,
        "token_inventory":  run_token_inventory,
    },
).run()
