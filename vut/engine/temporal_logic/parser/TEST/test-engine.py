#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the RULE-FILE LANGUAGE against the engine -- that the real GRAMMAR
         (grammar.py) compiles, is LL(2), generates the expected token inventory,
         and parses its distinctive argument forms correctly. The engine
         MACHINERY itself (FIRST_2, conflict detection, two-pass branch
         selection, the stackless scan) is tested grammar-agnostically in
         core/TEST/test-engine.py; this module is about the language.

CHOICES: first_sets, ll2_ok, token_inventory, shallow_member_access;

DESCRIPTION:

    first_sets       FIRST_2 sets of representative real rules -- the tokens (or
                     token pairs) that can begin each construct.
    ll2_ok           The real rule-file grammar compiles and passes LL(2)
                     validation; exactly one rule (<arg>) needs the second token.
    token_inventory  The generated token inventory, derived from the terminal
                     database (a token's identity is its Terminal object), covers
                     every fixed-spelling terminal the grammar refers to.
    shallow_member_access  Argument forms: a bare-rvalue positional, a named
                     'id = rvalue', and a shallow 'binding.member' for each of the
                     four bindings; plus forms that MUST be rejected.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner

from vut.engine.temporal_logic.parser.core.ll2_engine import LL2ConflictError
from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar
from vut.engine.temporal_logic.parser.core.lexer import (token_spec,
                                                         token_debug_names)
from vut.engine.temporal_logic.parser.core import ll2_grammar_ast as N


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _fmt_set(s):
    """RETURN: str, a FIRST_2 set rendered stably (sorted by token debug names)."""
    def key(tup):
        return tuple(t._name() for t in tup)
    def show(tup):
        return "(" + ", ".join(t._name() for t in tup) + ")"
    return "{" + ", ".join(show(t) for t in sorted(s, key=key)) + "}"


def run_first_sets():
    """RETURN: None. FIRST_2 sets of representative real rules."""
    g = compiled_grammar()
    banner("FIRST_2 sets of key rules")
    for name in ("top-level", "trigger", "effect", "rvalue", "arg",
                 "mode-elm", "state-machine-elm", "mode-group-elm"):
        if name in g.rules:
            print("%-20s %s" % (name, _fmt_set(g.rules[name].first)))


def run_ll2_ok():
    """RETURN: None. The real grammar compiles and is LL(2)."""
    banner("compile and validate the rule-file grammar")
    g = compiled_grammar()
    print("rules compiled:", len(g.rules))
    print("start symbol:  ", g.start)
    print("LL(2):          yes (no conflict raised)")


def run_token_inventory():
    """RETURN: None. The generated token inventory, and grammar coverage.

    Token identity is the Terminal object; there is no literal table. This lists
    every generated token by its debug name and pattern, then checks that every
    silent keyword the grammar uses is a registered token.
    """
    banner("generated tokens (debug name -> pattern)")
    g = compiled_grammar()          # ensure the grammar is registered/compiled
    names = token_debug_names()
    for term, pattern in sorted(token_spec(), key=lambda kp: names[kp[0]]):
        print("%-22s %r" % (names[term], pattern))

    banner("every silent keyword in the grammar is a registered token")
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
    recursive rule terminates. An opaque TerminalNode carries no silent keyword.
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


def run_shallow_member_access():
    """RETURN: None. Argument forms: positional, named, and shallow member access.

    Parses one effect per line and prints each argument's name (or '-'), kind,
    and value. Exercises a bare-identifier LITERAL positional, a named LITERAL, a
    shallow 'binding.member' MEMBER for each of the four bindings, a named MEMBER,
    and an opaque LUAU expression. Then forms that MUST be rejected: a deep
    'event.a.b' (shallow is one '.'), a binding with no member, a missing member
    after the dot, and a non-binding head 'foo.bar'.
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


def run_cause_effect():
    """RETURN: None. Named cause/effect definitions and references parse and bind.

    Exercises the reuse feature: a 'cause:' definition with a signature and an
    'on:'-signalled body; an 'effect:' definition with a '=>'-signalled bundle; a
    causality rule that fires a cause BY REFERENCE ('NAME(args)') and names an
    effect bundle BY REFERENCE (bare 'NAME'); and a mixed effect list where a
    bare name (effect-ref) and a name-with-parens (event-spec) sit side by side,
    told apart by the two-token lookahead. Prints the AST node kind per item.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    cases = [
        ("cause definition",
         "cause: NETWORK_UP(time: int)\n        on: NETWORK & { NETWORK.time > time }"),
        ("effect definition",
         "effect: SUPER_POWER => PACMAN_RUN(speed=12)\n"
         "                    => PELLET_BLINK\n"
         "                    => GHOSTS_FLEE"),
        ("cause-ref and effect-ref", "on: NETWORK(20) => SUPER_POWER"),
        ("mixed effect list", "on: NETWORK(20) => SUPER_POWER => Beep(3)"),
        ("inline still works", "on: Tick & { sm.n > 0 } => Beep()"),
    ]
    for label, src in cases:
        banner(label)
        rep = DiagnosticReporter()
        rf = parse(src, FakeLuauOracle(), rep)
        if rep.errors:
            for d in rep.errors:
                print("  ERROR off=%d %s" % (d.source_offset, d.message))
            continue
        for it in rf.items:
            kind = type(it).__name__
            if isinstance(it, ast.CauseDef):
                print("  CauseDef name=%s params=%d body=%s"
                      % (it.name, len(it.params), type(it.body).__name__))
            elif isinstance(it, ast.EffectDef):
                print("  EffectDef name=%s effects=[%s]"
                      % (it.name, ", ".join(type(e).__name__ for e in it.effects)))
            elif isinstance(it, ast.Causality):
                print("  Causality cause=%s effects=[%s]"
                      % (type(it.cause).__name__,
                         ", ".join(type(e).__name__ for e in it.effects)))
            else:
                print("  %s" % kind)


def _render_cond(node):
    """RETURN: str, a flat readable rendering of a bracket-condition tree."""
    n = type(node).__name__
    if n == "Condition":
        return _render_cond(node.expr)
    if n == "BoolOp":
        return "(%s)" % ((" %s " % node.op).join(_render_cond(o) for o in node.operands))
    if n == "Not":
        return "not %s" % _render_cond(node.operand)
    if n == "Comparison":
        return "%s %s %s" % (_render_cond(node.left), node.op, _render_cond(node.right))
    if n == "EventMember":
        return ".%s" % node.name
    if n == "Literal":
        return node.text
    return n


def run_guards_and_inheritance():
    """RETURN: None. Bracket-condition guards, effect-def signatures, is: bases.

    Exercises the constructs added alongside cause/effect reuse: a guard given as
    a bracket condition '[ ... ]' (an and/or/not algebra over leading-dot event
    members) as an alternative to a Luau guard; an effect definition carrying a
    parameter signature; and state-machine / mode-group inheritance via repeated
    'is:' base statements. Prints the guard kind and rendered condition, the
    effect-def signature, and the aggregate bases.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    cases = [
        ("bracket guard: comparison",
         'on: NetUp & [ .ip_adr == "10.0.0.1" ] => Beep()'),
        ("bracket guard: and / not",
         "on: NetUp & [ .port > 1024 and not .secure == 1 ] => Beep()"),
        ("bracket guard: parenthesised or",
         "on: T & [ (.x > 0 or .y < 10) and .ready == 1 ] => B()"),
        ("luau guard still admitted",
         "on: T & { sm.n > 0 } => B()"),
        ("effect definition with signature",
         "effect: Boost(level: int) => Beep() => Flash()"),
        ("state-machine inheritance",
         "state_machine: Derived(r: int) is: Base1 is: Base2 state: X :end"),
        ("mode-group inheritance",
         "mode_group: D is: Base mode: M on: E => B() until: T :end"),
        ("aggregate without bases",
         "state_machine: Plain state: X :end"),
    ]
    for label, src in cases:
        banner(label)
        rep = DiagnosticReporter()
        rf = parse(src, FakeLuauOracle(), rep)
        if rep.errors:
            for d in rep.errors:
                print("  ERROR off=%d %s" % (d.source_offset, d.message))
            continue
        it = rf.items[0]
        if isinstance(it, ast.Causality):
            g = it.cause.guard
            if g is None:
                print("  Causality, no guard")
            elif isinstance(g, ast.Condition):
                print("  Causality, bracket guard: %s" % _render_cond(g))
            elif isinstance(g, ast.Luau):
                print("  Causality, luau guard: %s" % g.text)
        elif isinstance(it, ast.EffectDef):
            print("  EffectDef name=%s params=%d effects=[%s]"
                  % (it.name, len(it.params),
                     ", ".join(type(e).__name__ for e in it.effects)))
        elif isinstance(it, ast.StateMachine):
            print("  StateMachine name=%s bases=%s states=%d"
                  % (it.name, it.bases, len(it.states)))
        elif isinstance(it, ast.ModeGroup):
            print("  ModeGroup name=%s bases=%s modes=%d"
                  % (it.name, it.bases, len(it.modes)))


HwutRunner(
    argv       = sys.argv,
    title      = "Rule-File Language",
    choice_map = {
        "first_sets":               run_first_sets,
        "ll2_ok":                   run_ll2_ok,
        "token_inventory":          run_token_inventory,
        "shallow_member_access":    run_shallow_member_access,
        "cause_effect":             run_cause_effect,
        "guards_and_inheritance":   run_guards_and_inheritance,
    },
).run()
