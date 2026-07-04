#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the grammar-agnostic LL(2) ENGINE (core/) in isolation, on small
         TOY grammars defined here -- never the rule-file language. What is under
         test is the machinery: FIRST_2 computation, LL(2) conflict detection,
         the two-pass branch selection that distinguishes 'id' from 'id =', the
         stackless conflict scan, and an end-to-end parse driven by 2-token
         lookahead.

CHOICES: first2, ll2_ok, ll2_conflict, ll1_needs_ll2, choose_alt, deep_alt,
         parse_disambiguation;

DESCRIPTION:

The engine is parameterised by a grammar dict of combinator expressions; these
choices pin its observable behaviour without reference to any particular
language. Each builds its own toy grammar.

    first2              FIRST_2 of a sequence 'a b c' is {(a, b)}; of an optional
                        head 'a? b' both {(a, b)} and {(b, ...)}; a nullable tail
                        leaves a length-1 entry.
    ll2_ok              A grammar whose OR branches differ in their FIRST token
                        compiles with no conflict.
    ll2_conflict        OR branches sharing BOTH lookahead tokens are rejected
                        with a located conflict report.
    ll1_needs_ll2       The canonical case: two OR branches share their FIRST
                        token but differ on the SECOND ('x' vs 'x ='); LL(1)
                        would reject this, LL(2) accepts it.
    choose_alt          Two-pass selection: a full 2-token pair match beats a
                        length-1 (single-token) match, so 'x =' picks the named
                        branch even though the positional branch begins with 'x'.
    deep_alt            The conflict scan is iterative: a 20000-deep nested OR
                        does not overflow a lowered recursion limit.
    parse_disambiguation  An end-to-end parse over the LL(2) toy grammar yields
                        the correct branch for each input.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.core.parser_generator.combinators import OR, STAR
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import T
from vut.engine.temporal_logic.core.parser_generator import ll2_grammar_spec as N
from vut.engine.temporal_logic.core.parser_generator.ll2_engine import (
        Grammar, EngineParser, LL2ConflictError)
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import merge_first2
from vut.engine.temporal_logic.core.lexer.lexer import register_grammar
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter


# Toy VALUE terminals: captured (non-silent) so they reach reduce frames. Their
# patterns are '@'-led so NO other terminal in the process-global terminal DB can
# match the same lexeme -- token identity is the Terminal object, and the generic
# identifier regex r'[a-zA-Z_]\w*' (minted by the real grammar) would otherwise
# shadow a plain-word toy terminal at lex time, since tier-6 regexes match in
# declaration order. The '@' prefix sidesteps that overlap entirely.
t_ID  = T.regex(r'@id\b')
t_NUM = T.regex(r'@num\b')


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _fmt_set(s):
    """RETURN: str, a FIRST_2 set rendered stably (sorted by token debug names).

    Each tuple element is a Terminal; its _name() gives a stable label, so the
    rendering is deterministic regardless of set iteration order.
    """
    def key(tup):
        return tuple(t._name() for t in tup)
    def show(tup):
        return "(" + ", ".join(t._name() for t in tup) + ")"
    return "{" + ", ".join(show(t) for t in sorted(s, key=key)) + "}"


def run_first2():
    """RETURN: None. FIRST_2 of representative rule shapes, computed by the engine.

    Builds a tiny grammar, lets Grammar._analyse run the FIRST_2 fixpoint, then
    prints each rule's set. Covers a plain sequence (two-token pair), an
    optional-headed sequence (pair plus the skip alternative), and a
    nullable-tailed sequence (a length-1 entry survives).
    """
    g = Grammar({
        "seq":      (t_ID, t_NUM, t_ID),          # FIRST_2 = {(id, num)}
        "opt_head": ([t_ID], t_NUM),              # {(id, num), (num,)}
        "null_tail":(t_ID, STAR(t_NUM)),          # {(id, num), (id,)}
    }, {"seq": None, "opt_head": None, "null_tail": None}, start="seq")
    banner("FIRST_2 of rule shapes")
    for name in ("seq", "opt_head", "null_tail"):
        print("%-12s %s" % (name, _fmt_set(g.rules[name].first)))


def run_ll2_ok():
    """RETURN: None. OR branches with distinct FIRST tokens compile cleanly."""
    banner("disjoint OR branches -> no conflict")
    g = Grammar({
        "top": ("<a>", OR, "<b>"),
        "a":   (t_ID,  "then"),
        "b":   (t_NUM, "then"),
    }, {"top": None, "a": None, "b": None}, start="top")
    print("rules compiled:", len(g.rules))
    print("conflict:       none")


def run_ll2_conflict():
    """RETURN: None. OR branches sharing BOTH lookahead tokens are rejected.

    Both branches begin 'id then', so neither one nor two tokens separates them;
    the LL(2) analyser must report the conflict, located by rule name.
    """
    banner("OR branches identical in two-token lookahead -> conflict")
    bad = {
        "top": ("<a>", OR, "<b>"),
        "a":   (t_ID, "then", "left"),
        "b":   (t_ID, "then", "right"),
    }
    actions = {"top": None, "a": None, "b": None}
    try:
        Grammar(bad, actions, start="top")
        print("UNEXPECTED: no conflict detected")
    except LL2ConflictError as exc:
        print("rejected with %d conflict(s):" % len(exc.conflicts))
        for c in exc.conflicts:
            print("  ", c)


def run_ll1_needs_ll2():
    """RETURN: None. The construct LL(1) cannot do but LL(2) can.

    The two OR branches share their FIRST token (an identifier) but differ on
    the SECOND: the positional branch is a bare identifier, the named branch is
    'identifier ='. One token cannot tell them apart; two can. This grammar would
    raise under an LL(1) analyser; under LL(2) it compiles, and FIRST_2 shows the
    distinguishing second token.
    """
    banner("shared FIRST token, distinct SECOND -> needs LL(2)")
    g = Grammar({
        "arg": ("<rvalue>", OR, (t_ID, "=", "<rvalue>")),
        "rvalue": (t_NUM, OR, t_ID),
    }, {"arg": None, "rvalue": None}, start="arg")
    print("compiled under LL(2): yes")
    # Show the two branches' FIRST_2 explicitly.
    alt = g.rules["arg"].pattern          # the rule pattern is directly the Alt
    for i, branch in enumerate(alt.branches):
        print("branch %d FIRST_2: %s" % (i, _fmt_set(branch.first2_set(g))))


def run_choose_alt():
    """RETURN: None. Two-pass branch selection: a full pair beats a length-1 match.

    Drives EngineParser.choose_alt directly over a toy 'arg' grammar with a primed
    two-token window. On lookahead '(ID, EQ)' the positional branch's FIRST_2
    contains the length-1 '(ID,)', which a single greedy 'pair OR truncation' test
    would have matched first, mis-selecting positional. The two-pass rule must
    instead pick the NAMED branch on '(ID, EQ)' and the POSITIONAL branch on
    '(ID, THEN)'.

    The toy terminals are unique STRING keywords ('ID', 'EQ', 'THEN', 'NUM'), not
    shared regex classes: token identity is the Terminal object, and the global
    terminal DB may already hold a regex that matches the same lexeme, so a toy
    regex could be shadowed at lex time. Unique keywords keep identity exact.
    """
    grammar = {"arg":    (t_ID, OR, (t_ID, "EQ", "<rvalue>")),
               "rvalue": (t_NUM, OR, "THEN")}
    banner("choose_alt prefers the two-token match")
    register_grammar(grammar)
    g = Grammar(grammar, {"arg": None, "rvalue": None}, start="arg")
    alt = g.rules["arg"].pattern          # the rule pattern is directly the Alt

    for src, want in (("@id EQ @num", "named"), ("@id THEN", "positional")):
        rep = DiagnosticReporter()
        p = EngineParser(src, rep, g)
        chosen = p.choose_alt(alt)
        idx = list(alt.branches).index(chosen)
        got = "positional" if idx == 0 else "named"
        mark = "ok" if got == want else "MISMATCH"
        print("  %-10s -> %-10s (%s)" % (src, got, mark))


def run_deep_alt():
    """RETURN: None. The conflict scan survives a pathologically deep tree.

    collect_alt_conflicts and the FIRST_2 computation it drives are iterative (an
    explicit worklist, not Python recursion), so a tree nested far deeper than the
    interpreter limit must not overflow. Builds a 20000-level nested alternation,
    lowers the recursion limit well below that, and checks the scan returns a
    (here empty) conflict list rather than raising RecursionError.
    """
    banner("deeply nested OR does not overflow the conflict scan")
    saved = sys.getrecursionlimit()
    sys.setrecursionlimit(2000)
    try:
        node = T.string("leaf")
        for _ in range(20000):
            node = N.OR_Spec([node])

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


# A reduce action for the toy 'arg' rule, recording each argument's shape so
# run_parse_disambiguation can report it. Module-level (engine actions are
# 'fn(frame) -> value'); the list is cleared by the caller per input.
_LAST_ARGS = []


def _mk_arg(frame):
    """RETURN: str, a label for the argument frame ('named:ID' or 'pos').

    Two frame shapes: [value] positional, [id_tok, value] named. Records the
    label in _LAST_ARGS and returns it; the value is irrelevant to this test,
    which checks branch selection, not value capture.
    """
    if len(frame.values) == 2:
        label = "named"
    else:
        label = "pos"
    _LAST_ARGS.append(label)
    return label


def run_parse_disambiguation():
    """RETURN: None. End-to-end LL(2) parse picks the right branch per input.

    Parses each input against a toy comma-separated argument list and prints, per
    argument, whether it parsed positional or named. This integrates lexer +
    two-token window + choose_alt over a STAR-repeated OR -- the shape the rule
    language's argument list has, reduced to essentials. Terminals are unique
    string keywords (see run_choose_alt) so token identity is exact, including at
    end-of-input where a length-1 lookahead '(NUM, eof)' must still select the
    positional branch via the two-pass rule.
    """
    grammar = {
        "args":   ("<arg>", STAR(("COMMA", "<arg>"))),
        "arg":    ("<rvalue>", OR, (t_ID, "EQ", "<rvalue>")),
        "rvalue": (t_NUM, OR, t_ID),
    }
    register_grammar(grammar)
    g = Grammar(grammar, {"args": None, "arg": _mk_arg, "rvalue": None},
                start="args")
    from vut.engine.temporal_logic.core.parser_generator.ll2_engine import _ResyncError

    banner("end-to-end LL(2) parse of an argument list")
    for src in ("@id", "@id EQ @num", "@id COMMA @id EQ @num", "@id EQ @num COMMA @num"):
        rep = DiagnosticReporter()
        p = EngineParser(src, rep, g)
        try:
            p._match(g.rules["args"])
            shown = _LAST_ARGS[:]
        except _ResyncError:
            shown = ["<resync>"]
        _LAST_ARGS.clear()
        print("  %-22s -> %s  (err=%d)"
              % (src, ", ".join(shown), len(rep.errors)))


class _ListLexer:
    """A minimal lexer stand-in: serves a prebuilt token list, then EOF.

    The one method EngineParser uses on it is next(). This mirrors how the
    framework's aux_walker drives a rule over a synthetic token stream -- the
    path that a single-token priming regression breaks but the lexer-backed tests
    do not, because aux_walker injects its own lexer.
    """
    def __init__(self, tokens):
        """RETURN: None. Holds the token list and a read cursor."""
        self.tokens = tokens
        self.i      = 0

    def next(self):
        """RETURN: Token, the next token, or an EOF sentinel past the end."""
        if self.i < len(self.tokens):
            t = self.tokens[self.i]
            self.i += 1
            return t
        from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import t_fr_eof
        from vut.engine.temporal_logic.core.lexer.lexer import Token
        return Token(t_fr_eof, "", 0, 0)


def run_construct_primes_window():
    """RETURN: None. The constructor primes BOTH lookahead tokens; no by-hand path.

    Regression guard for the migration bug where a caller built the parser and
    primed a single 'tok' (the retired LL(1) field), leaving tok1/tok2 unset so
    _match's very first 'self.tok1.begin' raised AttributeError. Asserts that
    after construction tok1 and tok2 BOTH exist and hold the first two tokens of
    the stream, and that a one-token stream still leaves tok2 as EOF rather than
    unset. The point is that priming lives in exactly one place (the constructor)
    and the window is always live before any match begins.
    """
    from vut.engine.temporal_logic.core.lexer.lexer import Token, register_grammar
    from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import T, t_fr_eof
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter

    t_a = T.regex(r'@a\b')
    grammar = {"top": (t_a,)}
    register_grammar(grammar)
    g = Grammar(grammar, {"top": None}, start="top")

    banner("constructor primes tok1 and tok2")
    toks = [Token(t_a, "@a", 0, 2), Token(t_a, "@a", 3, 5)]
    p = EngineParser(None, DiagnosticReporter(), g, lexer=_ListLexer(toks))
    print("tok1 set:", hasattr(p, "tok1"), "->", p.tok1.text)
    print("tok2 set:", hasattr(p, "tok2"), "->", p.tok2.text)
    print("no retired single 'tok':", not hasattr(p, "tok"))

    banner("one-token stream still leaves a live window (tok2 = EOF)")
    p1 = EngineParser(None, DiagnosticReporter(), g,
                      lexer=_ListLexer([Token(t_a, "@a", 0, 2)]))
    print("tok1:", p1.tok1.text or "(empty)",
          "tok2 is EOF:", p1.tok2.kind is t_fr_eof)


def run_drive_token_list():
    """RETURN: None. Driving _match over an injected token list parses correctly.

    Exercises the same construction path the framework's cover tests use -- real
    constructor, injected list lexer, then _match(rule) -- which is what the
    lexer-backed tests never touch. A rule is driven over a well-formed token
    list (built) and a truncated one (abandoned via _ResyncError), confirming
    both the happy path and recovery work through the driver, not only through a
    real Lexer.
    """
    from vut.engine.temporal_logic.core.lexer.lexer import Token, register_grammar
    from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import T
    from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
    from vut.engine.temporal_logic.core.parser_generator.ll2_engine import _ResyncError

    t_a = T.regex(r'@a\b')
    t_b = T.regex(r'@b\b')
    grammar = {"pair": (t_a, t_b)}
    register_grammar(grammar)
    g = Grammar(grammar, {"pair": None}, start="pair")

    def drive(tokens):
        p = EngineParser(None, DiagnosticReporter(), g,
                         lexer=_ListLexer(tokens))
        try:
            p._match(g.rules["pair"])
            return "built", len(p.reporter.errors)
        except _ResyncError:
            return "abandoned", len(p.reporter.errors)

    banner("drive _match over an injected token list")
    well = [Token(t_a, "@a", 0, 2), Token(t_b, "@b", 3, 5)]
    trunc = [Token(t_a, "@a", 0, 2)]
    print("well-formed [@a @b]:", drive(well))
    print("truncated   [@a]   :", drive(trunc))


HwutRunner(
    argv       = sys.argv,
    title      = "Core LL(2) Engine",
    choice_map = {
        "first2":                 run_first2,
        "ll2_ok":                 run_ll2_ok,
        "ll2_conflict":           run_ll2_conflict,
        "ll1_needs_ll2":          run_ll1_needs_ll2,
        "choose_alt":             run_choose_alt,
        "deep_alt":               run_deep_alt,
        "parse_disambiguation":   run_parse_disambiguation,
        "construct_primes_window":run_construct_primes_window,
        "drive_token_list":       run_drive_token_list,
    },
).run()
