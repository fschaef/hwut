#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the RULE-FILE LANGUAGE against the engine -- that the real GRAMMAR
         (grammar.py) compiles, is LL(2), generates the expected token inventory,
         and parses its distinctive argument forms correctly. The engine
         MACHINERY itself (FIRST_2, conflict detection, two-pass branch
         selection, the stackless scan) is tested grammar-agnostically in
         core/TEST/test-engine.py; this module is about the language.

CHOICES: first_sets, ll2_ok, token_inventory, name_dotted_args;

DESCRIPTION:

    first_sets       FIRST_2 sets of representative real rules -- the tokens (or
                     token pairs) that can begin each construct.
    ll2_ok           The real rule-file grammar compiles and passes LL(2)
                     validation; the named tails and <arg> need the second token.
    token_inventory  The generated token inventory, derived from the terminal
                     database (a token's identity is its Terminal object), covers
                     every fixed-spelling terminal the grammar refers to.
    name_dotted_args Argument forms: a bare-name positional, a named
                     'id = rvalue', <name-dotted> references of any depth
                     ('e.target', 'tracker.pos.x'), literals incl. true/false,
                     opaque Luau; plus forms that MUST be rejected.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner

from vut.engine.temporal_logic.core.parser_generator.ll2_engine import LL2ConflictError
from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar
from vut.engine.temporal_logic.lexer.lexer import (token_spec,
                                                         token_debug_names)
from vut.engine.temporal_logic.core.parser_generator import ll2_grammar_spec as N


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
    for name in ("top-level", "cause", "cause-named", "effect", "effect-named",
                 "rvalue", "arg", "cond-term", "kind-decl",
                 "elm-mode", "elm-state-machine", "elm-mode-group"):
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
    """RETURN: set, the Terminal of every silent Terminal_Spec reachable in 'node'.

    Walks the compiled object tree. A Branch_Spec (Sequence/Alternative) exposes
    its sub-nodes through .branches; an Operator_Spec (Opt/Star/Plus) through
    .body; a Rule_Spec is followed once via .pattern (cycle guard) so a
    recursive rule terminates. An opaque Terminal_Spec carries no silent keyword.
    """
    if seen is None:
        seen = set()
    out = set()
    if isinstance(node, N.Terminal_Spec):
        if node.silent and not node.is_opaque:
            out.add(node)
    elif isinstance(node, N.Rule_Spec):
        if node.name not in seen:
            seen.add(node.name)
            out |= _silent_terminals(node.pattern, seen)
    elif isinstance(node, N.Branch_Spec):
        for sub in node.branches:
            out |= _silent_terminals(sub, seen)
    elif isinstance(node, N.Operator_Spec):
        out |= _silent_terminals(node.body, seen)
    return out


def run_name_dotted_args():
    """RETURN: None. Argument forms: positional, named, name-dotted, literal.

    Parses one effect per line and prints each argument's name (or '-'), kind,
    and value. Exercises a bare-name positional (a NAME of one segment), a
    named LITERAL, <name-dotted> references through the pseudo-symbol bindings
    ('e.target', 'sm.count', 'mg.index', 'm.req') and through plain symbols of
    any depth ('tracker.pos.x'), the true/false literals, and an opaque LUAU
    expression. Then forms that MUST be rejected: a trailing dot, a lone '=',
    a leading-dot member (the retired spelling).
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
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
        if a.kind is ast.E_ArgKind.NAME:
            return ".".join(a.value)
        if a.kind is ast.E_ArgKind.LUAU:
            return a.value.text
        return a.value

    banner("accepted argument forms (name | kind | value)")
    accepted = [
        "on: A => Chase(target)",
        "on: A => Chase(lane = 2)",
        "on: A => Chase(e.target)",
        "on: A => Chase(sm.count)",
        "on: A => Chase(mg.index)",
        "on: A => Chase(m.req)",
        "on: A => LOG(time = e.time)",
        "on: A => Chase(tracker.pos.x)",
        "on: A => Chase(armed = true)",
        "on: A => Chase({ e.x + 1 })",
    ]
    for src in accepted:
        rep = DiagnosticReporter()
        tree = parse(src, FakeLuauOracle(), rep)
        if rep.errors:
            print("UNEXPECTED ERROR: %s" % src)
            continue
        for a in _args(tree):
            print("  %-8s %-8s %s" % (a.name or "-", a.kind.name, _val(a)))

    banner("rejected forms (no trailing dot, no lone '=', no leading dot)")
    rejected = [
        "on: A => Chase(e.)",
        "on: A => Chase(= 3)",
        "on: A => Chase(.target)",
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
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    cases = [
        ("cause definition ('for:' binding, mandatory guard)",
         "cause: TOO_HOT(limit: int) for: NETWORK & [ e.time > limit ]"),
        ("effect definition",
         "effect: SUPER_POWER => PACMAN_RUN(speed=12)\n"
         "                    => PELLET_BLINK\n"
         "                    => GHOSTS_FLEE"),
        ("cause reference and effect reference", "on: TOO_HOT(20) => SUPER_POWER"),
        ("mixed effect list", "on: TOO_HOT(20) => SUPER_POWER => Beep(3)"),
        ("dotted references", "on: NS.TOO_HOT(20) => Fx.cleanup => NS.Beep(3)"),
        ("reference + extra guard (parses; pass-2 F-7)",
         "on: TOO_HOT(20) & [ e.x > 1 ] => Beep(3)"),
        ("inline guard with a method call",
         'on: Tick & [ e.tags.has("boss") ] => Beep()'),
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
            if isinstance(it, ast.Causality) and isinstance(it.cause, ast.CauseRef):
                print("  Causality cause=CauseRef name=%s guard=%s effects=[%s]"
                      % (".".join(it.cause.name),
                         type(it.cause.guard).__name__,
                         ", ".join(type(e).__name__ for e in it.effects)))
                continue
            if isinstance(it, ast.CauseDef):
                print("  CauseDef name=%s params=%d for=%s guard=%s"
                      % (it.name, len(it.params), ".".join(it.for_event),
                         type(it.guard).__name__))
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
    """RETURN: str, a flat readable rendering of a bracket-condition / algebr tree."""
    n = type(node).__name__
    if n == "Condition":
        return _render_cond(node.expr)
    if n == "BinOp":
        return "(%s %s %s)" % (_render_cond(node.left), node.op, _render_cond(node.right))
    if n == "UnOp":
        return "%s %s" % (node.op, _render_cond(node.operand))
    if n == "Bridge":
        return "(? %s then: %s else: %s)" % (_render_cond(node.cond),
                _render_cond(node.then_), _render_cond(node.else_))
    if n == "Comparison":
        return "%s %s %s" % (_render_cond(node.left), node.op, _render_cond(node.right))
    if n == "BoolRef":
        return ".".join(node.name)
    if n == "Literal":
        return node.text
    if n == "MethodCall":
        if node.receiver is None:
            # A free-function call ('sqrt(x)', 'min(a,b)') -- no receiver.
            return "%s(%d)" % (node.method, len(node.args))
        recv = _render_cond(node.receiver)
        if node.args is None:
            return "%s.%s" % (recv, node.method)
        return "%s.%s(%d)" % (recv, node.method, len(node.args))
    if n == "OpaqueCode":
        return node.text
    if isinstance(node, list):
        return ".".join(node)
    return n


def run_guards_and_inheritance():
    """RETURN: None. Bracket-condition guards, effect-def signatures, is: bases.

    Exercises the bracket-condition ladder and the aggregate features: a guard
    given as a bracket condition '[ ... ]' (an and/or/not algebra over
    comparisons, bare boolean references, and standard member-function calls;
    members spelled through the 'e' pseudo-symbol, both sides symmetric) -- the
    sole guard form; an effect definition carrying a parameter signature; and
    state-machine / mode-group inheritance via repeated 'is:' base statements.
    Prints the guard kind and rendered condition, the effect-def signature, and
    the aggregate bases.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    cases = [
        ("bracket guard: comparison",
         'on: NetUp & [ e.ip_adr == "10.0.0.1" ] => Beep()'),
        ("bracket guard: and / not",
         "on: NetUp & [ e.port > 1024 and not e.secure == 1 ] => Beep()"),
        ("bracket guard: parenthesised or",
         "on: T & [ (e.x > 0 or e.y < 10) and e.ready == 1 ] => B()"),
        ("bracket guard: bare boolean stands",
         "on: T & [ GHOSTS_AT_HOME and not e.armed ] => B()"),
        ("bracket guard: symmetric sides, literal right only",
         "on: T & [ TIMEOUT < e.elapsed and e.flag == true ] => B()"),
        ("bracket guard: standard member-function call",
         'on: T & [ e.tags.has("admin") and e.name.glob("svc_*") ] => B()'),
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


def run_clockwork_shapes():
    """RETURN: None. The clockwork construct parses; steps build their nodes (D-11).

    Exercises the tick-scripted stimulus actor: the signature and guarded 'on:'
    clock binding; the step variety told apart by leader -- a bare EventSpec
    (paced emission), 'instant:' (immediate injection), the bare commands
    ('spawn:'/'unspawn:'/opaque block; arm collapsed to bare name), 'wait:' with and without a
    co-temporal effect tail, 'select:' (first-of-many), and the 'if:'/'elif:'/
    'else:' and 'while:' control frames composing within the body. Also pins the
    FENCE: an imperative clockwork construct used as a causality effect is
    rejected. Prints the clockwork shape and the ordered step kinds.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    cases = [
        ("minimal clockwork (one paced emission)",
         "clockwork: a on: clk\n GO()\n:end"),
        ("signature + guarded clock + init/deinit",
         "clockwork: heinz(deadline: float) on: clk & [ ready ]\n"
         " init: { x }\n PING(seq = 1)\n deinit: { y }\n:end"),
        ("tick law: paced vs instant vs commands",
         "clockwork: a on: clk\n EVENT(p = 1)\n instant: OTHER(p = 2)\n"
         " spawn: SM(lane = 0)\n W(ip = \"x\")\n { setup() }\n unspawn: SM\n:end"),
        ("wait with co-temporal tail, then tail-less gate",
         "clockwork: a on: clk\n wait: RESP & [ e.ok ]\n => { x }\n => DONE(ok = true)\n"
         " wait: GO\n:end"),
        ("select: first-of-many",
         "clockwork: a on: clk\n select:\n  wait: ACK & [ e.p == 1 ]\n  => DONE()\n"
         "  wait: SHUTDOWN\n :end\n:end"),
        ("if / elif / else, one :end",
         "clockwork: a on: clk\n if: [ x ]\n  A()\n elif: [ y ]\n  instant: B()\n"
         " else:\n  { z }\n :end\n:end"),
        ("while: own :end, nested wait",
         "clockwork: a on: clk\n while: [ x ]\n  P(s = 1)\n  wait: PONG\n :end\n:end"),
        ("FENCE: imperative construct rejected as a causality effect",
         "on: T => wait: GO"),
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
        if isinstance(it, ast.Clockwork):
            print("  Clockwork name=%s params=%d clock=%s guard=%s init=%s deinit=%s"
                  % (".".join(it.name), len(it.params),
                     ".".join(it.clock.trigger.name),
                     it.clock.guard is not None,
                     it.init is not None, it.deinit is not None))
            print("  steps=[%s]" % ", ".join(type(s).__name__ for s in it.steps))
            for s in it.steps:
                if isinstance(s, ast.WaitLine):
                    print("    WaitLine cause=%s tail=%d"
                          % (".".join(s.cause.trigger.name), len(s.effects)))
                elif isinstance(s, ast.SelectFrame):
                    print("    SelectFrame branches=%d (tails=%s)"
                          % (len(s.branches),
                             ",".join(str(len(b.effects)) for b in s.branches)))
                elif isinstance(s, ast.IfFrame):
                    print("    IfFrame arms=%d else=%s"
                          % (len(s.arms), s.else_body is not None))
                elif isinstance(s, ast.WhileFrame):
                    print("    WhileFrame body=[%s]"
                          % ", ".join(type(x).__name__ for x in s.body))
        else:
            print("  %s" % type(it).__name__)


def run_expressions():
    """RETURN: None. The expression band and the clockwork mutations (D-13).

    Exercises the two ladders and their explicit crossings: arithmetic
    precedence ('+'/'-'/'*') and the unary minus; the shifts 'shl:'/'shr:'; the
    full boolean set 'and'/'nand'/'or'/'nor'/'xor'/'nxor'/'not'; the comparison
    (num->bool) and the '?'-bridge (bool->num); '[ ]' nesting and '( )' grouping;
    and -- in a clockwork body -- the four mutations 'gets:'/'incr:'/'decr:'/
    'recip:'. Prints the rendered guard tree, then the mutation step kinds.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    guards = [
        ("arithmetic precedence + comparison",
         "on: T & [ e.a + e.b * 2 - 1 == sm.total ] => X()"),
        ("unary minus, parens override",
         "on: T & [ -(e.a + 1) * 3 < e.b ] => X()"),
        ("shift below add",
         "on: T & [ e.a + 1 shl: 2 >= e.mask ] => X()"),
        ("every boolean operator",
         "on: T & [ e.p and e.q nand e.r or e.s nor e.t xor e.u nxor e.v ] => X()"),
        ("not + nested condition bracket",
         "on: T & [ not [ e.a > 0 and e.b > 0 ] ] => X()"),
        ("the bridge: bool -> num inside a comparison",
         "on: T & [ ? [ e.ok ] then: e.hi else: e.lo  >  sm.limit ] => X()"),
    ]
    for label, src in guards:
        banner(label)
        rep = DiagnosticReporter()
        rf = parse(src, FakeLuauOracle(), rep)
        if rep.errors:
            print("  ERROR %s" % rep.errors[0].message)
            continue
        print("  %s" % _render_cond(rf.items[0].cause.guard))

    banner("clockwork mutations: gets / incr / decr / recip")
    src = ("clockwork: m on: clk\n"
           " cw.acc gets: cw.acc + e.delta * 2\n"
           " incr: cw.hits\n"
           " incr: cw.score by: 10 to: 100\n"
           " decr: cw.lives by: 1\n"
           " cw.rate recip: cw.divisor\n"
           " else:\n"
           "   instant: DIV0()\n"
           "   { log() }\n"
           " :end\n"
           ":end")
    rep = DiagnosticReporter()
    rf = parse(src, FakeLuauOracle(), rep)
    if rep.errors:
        print("  ERROR %s" % rep.errors[0].message)
    else:
        for s in rf.items[0].steps:
            n = type(s).__name__
            if n == "Assign":
                print("  Assign %s = %s" % (".".join(s.lvalue), _render_cond(s.rhs)))
            elif n == "Incr":
                print("  Incr %s by=%s to=%s" % (".".join(s.lvalue),
                      _render_cond(s.amount) if s.amount else "default",
                      _render_cond(s.limit) if s.limit else "none"))
            elif n == "Decr":
                print("  Decr %s by=%s to=%s" % (".".join(s.lvalue),
                      _render_cond(s.amount) if s.amount else "default",
                      _render_cond(s.limit) if s.limit else "none"))
            elif n == "Recip":
                print("  Recip %s = 1/(%s) else_body=[%s]" % (".".join(s.lvalue),
                      _render_cond(s.operand),
                      ", ".join(type(x).__name__ for x in s.else_body)))


def run_division():
    """RETURN: None. The '/' operator and the expression-level 'undef:' fallback (D-23).

    '/' joins the multiplicative ladder beside '*'. An expression may carry one
    trailing 'undef:' fallback, supplying the value when a math operation is
    undefined (divide by zero); 'undef:' is distinct from the conditional 'else:';
    the PARSER accepts it on any expression (the SEMANTIC layer makes it
    mandatory iff a '/' appears, and dead otherwise -- not checked here). Math
    functions need no new grammar: they enter through the existing call form
    'name(args)'. Prints the rendered expression and the node kind, so a bare
    'undef:' shows the Expr wrapper while a fallback-free expression stays bare.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
    from fake_luau_oracle import FakeLuauOracle

    cases = [
        ("division in the multiplicative ladder",
         "on: T & [ e.a / e.b == sm.q ] => X()"),
        ("mixed * and / left-fold",
         "on: T & [ e.a * e.b / e.c > 0 ] => X()"),
        ("a math function call as an operand",
         "on: T & [ sqrt(e.x) + min(e.a, e.b) > sm.limit ] => X()"),
        ("'undef:' in a bridge arm coexists with the bridge's 'else:'",
         "on: T & [ ? [ e.ok ] then: e.a / e.b undef: 0 else: 9 > sm.t ] => X()"),
    ]
    for label, src in cases:
        banner(label)
        rep = DiagnosticReporter()
        rf = parse(src, FakeLuauOracle(), rep)
        if rep.errors:
            print("  ERROR %s" % rep.errors[0].message)
            continue
        print("  %s" % _render_cond(rf.items[0].cause.guard))

    banner("the expression-level 'undef:' fallback wraps the expression in Expr")
    src = ("clockwork: m on: clk\n"
           " cw.r gets: e.a / e.b undef: 0\n"
           ":end")
    rep = DiagnosticReporter()
    rf = parse(src, FakeLuauOracle(), rep)
    if rep.errors:
        print("  ERROR %s" % rep.errors[0].message)
    else:
        rhs = rf.items[0].steps[0].rhs
        print("  rhs node: %s" % type(rhs).__name__)
        if type(rhs).__name__ == "Expr":
            print("  body: %s" % _render_cond(rhs.body))
            print("  fallback: %s" % _render_cond(rhs.fallback))

    banner("a fallback-free expression stays bare (no Expr wrapper)")
    src = ("clockwork: m on: clk\n"
           " cw.r gets: e.a + e.b\n"
           ":end")
    rep = DiagnosticReporter()
    rf = parse(src, FakeLuauOracle(), rep)
    if rep.errors:
        print("  ERROR %s" % rep.errors[0].message)
    else:
        print("  rhs node: %s" % type(rf.items[0].steps[0].rhs).__name__)


def run_spawn_targets():
    """RETURN: None. Spawn 'into:' targets inside an anonymous clockwork.

    Spawn and container writes are clockwork-only (D-16): they run from a
    causality rule through an ANONYMOUS clockwork ('=> clockwork: ... :end'),
    never as bare effects. Pins the spawn target clause inside that body: a bare
    'into: <list>' (append, no key); an 'into: <dict>[ <key> ]' subscript; the
    keyless default. Also shows container entry access as standard member
    functions ('D.set', 'L.append') sitting as clockwork statements, mixed with
    a '{ luau }' segment. Prints the anonymous body's steps with spawn target
    and key.
    """
    from vut.engine.temporal_logic.parser.rule_parser import parse
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.parser import ast_nodes as ast
    from fake_luau_oracle import FakeLuauOracle

    cases = [
        ("default target (per-kind default container)",
         "on: T => do: spawn: SM(lane = 0) :end"),
        ("into a list (append, no key)",
         "on: T => do: spawn: SM(lane = 0) into: queue :end"),
        ("into a dict at a key",
         "on: T => do: spawn: SM(lane = 0) into: roster[e.id] :end"),
        ("into a dotted dict at a dotted key",
         "on: T => do: spawn: SM() into: NS.roster[e.lead.id] :end"),
        ("container writes + luau side by side",
         'on: T => do: scores gets: 5\n { db.flush() }\n'
         " instant: Ping() :end"),
        ("spawn as a BARE effect is rejected (clockwork-only)",
         "on: T => spawn: SM(lane = 0)"),
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
        sweeps = [e.body for e in it.effects
                  if isinstance(e, ast.Mutation) and isinstance(e.body, ast.DoSweep)]
        if sweeps:
            print("  DoSweep steps:")
            for s in sweeps[0].steps:
                if isinstance(s, ast.Spawn):
                    tgt = ".".join(s.into_container) if s.into_container else "default"
                    key = ".".join(s.key) if s.key else "(append/none)"
                    print("    Spawn into=%s key=%s" % (tgt, key))
                else:
                    print("    %s" % type(s).__name__)
        else:
            print("  effects:", [type(e).__name__ for e in it.effects])


HwutRunner(
    argv       = sys.argv,
    title      = "Rule-File Language",
    choice_map = {
        "first_sets":               run_first_sets,
        "ll2_ok":                   run_ll2_ok,
        "token_inventory":          run_token_inventory,
        "name_dotted_args":         run_name_dotted_args,
        "cause_effect":             run_cause_effect,
        "guards_and_inheritance":   run_guards_and_inheritance,
        "clockwork_shapes":         run_clockwork_shapes,
        "spawn_targets":            run_spawn_targets,
        "expressions":              run_expressions,
        "division":                 run_division,
    },
).run()
