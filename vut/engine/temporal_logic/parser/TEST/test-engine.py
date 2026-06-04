#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the table-driven parse engine and the declarative grammar.

CHOICES: first_sets, ll1_ok, ll1_conflict, literal_table;

DESCRIPTION:

The engine compiles the declarative GRAMMAR (grammar.py) to symbols, computes
FIRST sets, validates LL(1), and interprets the result to build the same AST as
the hand-written parser.

    first_sets       Computed FIRST sets for representative rules match the
                     tokens that can actually begin each construct.
    ll1_ok           The real rule-file grammar compiles and passes LL(1)
                     validation without conflict.
    ll1_conflict     A deliberately ambiguous grammar (two ALT branches sharing
                     a FIRST token) is rejected with a located conflict report.
    literal_table    The literal->token map derived from the lexer covers every
                     fixed-spelling terminal the grammar refers to.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner 

from   dataclasses import is_dataclass, fields

from   vut.engine.temporal_logic.parser.grammar       import SEQ, ALT

from   vut.engine.temporal_logic.parser.parser_engine import (Grammar, 
                                                              LL1ConflictError, 
                                                              compiled_grammar,
                                                              _literal_table)
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


# Inputs used by parity choices: one per construct plus mixed cases.
_SPREAD = [
    'on: Tick & { event.n > 0 } => Beep()',
    'on: ANY => Log()',
    ('on: Tick => Beep(3) => ! Blink() '
     '=> "tick {event.n}" => { sm.n = sm.n + 1 }'),
    'mode: Blink\n on Tick => Toggle()\n init: { sm.x = 0 }\n until: ANY\n',
    ('state_machine: Traffic\n default: Traffic.RED\n'
     ' state: RED\n  on Tick => Switch()\n until: switched\n :end\n'),
    'state_machine: Idle\n default: Idle.VOID\n has: Other.VOID\n :end\n',
    ('mode_group: Lights\n init: { sm.x = 0 }\n'
     ' mode: Blink\n  on Tick => Toggle()\n until: ANY\n has: Glow\n :end\n'),
    'event: Move(dx: int ; dy: int)',
    'clock: Tick 100',
    'on: X => Honk({ event.hz * 2 }, 5)',
    'on: Boom => +! SmTraffic() in: north => ! Blink()',
    'on: Clear => -! north',
    'Ghosts is: container(fifo, 64) as: { db.ghosts }',
]


def run_first_sets():
    """RETURN: None. FIRST sets of representative rules."""
    g = compiled_grammar()
    banner("FIRST sets of key rules")
    for name in ("<top-level>", "<trigger>", "<effect>", "<rvalue>",
                 "<mode-elm>", "<state-machine-elm>", "<mode-group-elm>"):
        toks = sorted(t.name for t in g.rules[name].first)
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
    bad = {
        "<top-level>": (ALT, "<a>", "<b>"),
        "<a>":         (SEQ, "#ID", "end"),
        "<b>":         (SEQ, "#ID", "on"),
    }
    actions = {"<top-level>": None, "<a>": None, "<b>": None}
    try:
        Grammar(bad, actions, start="<top-level>")
        print("UNEXPECTED: no conflict detected")
    except LL1ConflictError as exc:
        print("rejected with %d conflict(s):" % len(exc.conflicts))
        for c in exc.conflicts:
            print("  ", c)


def run_literal_table():
    """RETURN: None. The lexer-derived literal table, and grammar coverage."""
    banner("literal -> token id (derived from the lexer)")
    table = _literal_table()
    for literal in sorted(table):
        print("%-16s -> %s" % (repr(literal), table[literal].name))

    banner("every fixed-spelling terminal in the grammar resolves")
    # A grammar literal is a bare string that is neither a <non-terminal>, a
    # '#CLASS', nor a '{luau:...}' marker.
    missing = []
    for pattern in G.GRAMMAR.values():
        for lit in _literals_in(pattern):
            if lit not in table and lit not in G.CAPTURED_LITERALS:
                missing.append(lit)
            elif lit not in table:
                missing.append(lit)
    print("unresolved:", missing if missing else "(none)")


def _literals_in(element):
    """RETURN: list, the bare literal strings appearing in a grammar pattern."""
    found = []
    if isinstance(element, tuple):
        for sub in element[1:]:
            found += _literals_in(sub)
    elif isinstance(element, str):
        if not (element.startswith("<") or element.startswith("#")
                or element.startswith("{luau:")):
            found.append(element)
    return found


HwutRunner(
    argv       = sys.argv,
    title      = "Table-driven Parse Engine",
    choice_map = {
        "first_sets":      run_first_sets,
        "ll1_ok":          run_ll1_ok,
        "ll1_conflict":    run_ll1_conflict,
        "literal_table":   run_literal_table,
    },
).run()
