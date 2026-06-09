#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the table-driven parse engine and the declarative grammar.

CHOICES: first_sets, ll1_ok, ll1_conflict, token_inventory, deep_alt, shallow_member_access;

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

    Walks the compiled object tree. A BranchNode (Sequence/Alternative) exposes
    its sub-nodes through .branches; an OperatorNode (Opt/Star/Plus) through
    .body; a PassThroughNode is followed once via .pattern (cycle guard) so a
    recursive rule terminates. An opaque TerminalNode carries no silent keyword,
    so it contributes nothing.
    """
    if seen is None:
        seen = set()
    out = set()
    if isinstance(node, N.TerminalNode):
        if node.silent and not node.is_opaque:
            out.add(node.token_id)
    elif isinstance(node, N.PassThroughNode):
        if node.name not in seen:
            seen.add(node.name)
            out |= _silent_terminals(node.pattern, seen)
    elif isinstance(node, N.BranchNode):
        for sub in node.branches:
            out |= _silent_terminals(sub, seen)
    elif isinstance(node, N.OperatorNode):
        out |= _silent_terminals(node.body, seen)
    return out


def run_deep_alt():
    """RETURN: None. The LL(1) conflict scan survives a pathologically deep tree.

    collect_alt_conflicts and the FIRST-set computation it drives are iterative
    (an explicit worklist, not Python recursion), so a grammar nested far deeper
    than the interpreter's recursion limit must not overflow. This builds a
    20000-level nested alternation by hand, lowers the recursion limit well below
    that, and checks the scan returns a (here empty) conflict list rather than
    raising RecursionError.
    """
    banner("deeply nested ALT does not overflow the conflict scan")
    saved = sys.getrecursionlimit()
    sys.setrecursionlimit(2000)
    try:
        node = N.TerminalNode(T.string("leaf"), silent=True)
        for _ in range(20000):
            node = N.AlternativeNode([node])

        class _Ctx:
            rules = {}
        try:
            conflicts = N.collect_alt_conflicts(node, "deep", _Ctx())
            print("depth 20000, recursion limit 2000")
            print("overflow:   no")
            print("conflicts:  %d" % len(conflicts))
        except RecursionError:
            print("overflow:   YES -- the scan is still recursive")
    finally:
        sys.setrecursionlimit(saved)


def run_shallow_member_access():
    """RETURN: None. Argument forms: positional, named, and shallow member access.

    Parses one effect per line and prints each argument's name (or '-'), kind,
    and value. Exercises: a bare-identifier LITERAL, a named LITERAL, a shallow
    'binding.member' MEMBER for each of the four bindings, a named MEMBER, and an
    opaque LUAU expression. Then a block of forms that MUST be rejected: a deep
    'event.a.b' (shallow is one '.' only), a binding with no member, a missing
    member after the dot, and a non-binding head 'foo.bar'.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    def _args(tree):
        out = []
        stack = list(tree.items)
        while stack:
            n = stack.pop(0)
            if isinstance(n, (ast.EventSpec, ast.ModeArming, ast.Spawn)):
                out.extend(n.args)
            for fld in getattr(n, "__dataclass_fields__", {}):
                v = getattr(n, fld)
                if isinstance(v, list):
                    stack.extend(x for x in v if hasattr(x, "__dataclass_fields__"))
                elif hasattr(v, "__dataclass_fields__"):
                    stack.append(v)
        return out

    def _val(a):
        if a.kind is ast.E_ArgKind.MEMBER:
            return "%s.%s" % (a.value.binding, a.value.member)
        if a.kind is ast.E_ArgKind.LUAU:
            return a.value.text
        return a.value

    banner("accepted argument forms (name | kind | value)")
    accepted = [
        "on: A => Chase(target)",
        "on: A => Chase(lane = 2)",
        "on: A => Chase(event.target)",
        "on: A => Chase(sm.count)",
        "on: A => Chase(mg.index)",
        "on: A => Chase(mode.req)",
        "on: A => LOG(time = event.time)",
        "on: A => Chase({ event.x + 1 })",
    ]
    for src in accepted:
        rep = DiagnosticReporter()
        tree = parse(src, FakeLuauOracle(), rep)
        if rep.errors:
            print("UNEXPECTED ERROR: %s" % src)
            continue
        for a in _args(tree):
            print("  %-8s %-8s %s" % (a.name or "-", a.kind.name, _val(a)))

    banner("rejected forms (shallow is one '.', head must be a binding)")
    rejected = [
        "on: A => Chase(event.a.b)",
        "on: A => Chase(event)",
        "on: A => Chase(event.)",
        "on: A => Chase(foo.bar)",
    ]
    for src in rejected:
        rep = DiagnosticReporter()
        parse(src, FakeLuauOracle(), rep)
        verdict = "rejected" if rep.errors else "ACCEPTED (unexpected)"
        print("  %-28s %s" % (src.split("=>")[1].strip(), verdict))


HwutRunner(
    argv       = sys.argv,
    title      = "Table-driven Parse Engine",
    choice_map = {
        "first_sets":            run_first_sets,
        "ll1_ok":                run_ll1_ok,
        "ll1_conflict":          run_ll1_conflict,
        "token_inventory":       run_token_inventory,
        "deep_alt":              run_deep_alt,
        "shallow_member_access": run_shallow_member_access,
    },
).run()

