#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

NOT A TEST. Generates the monkey-fuzz fixtures under monkey_data/ by walking the
compiled grammar with a seeded DeterministicStream. Run this after a grammar
change; monkey-fuzz.py then parses the STORED fixtures with no RNG dependency.

    python3 monkey-file-creator.py            regenerate every profile fixture
    python3 monkey-file-creator.py --debug    also re-lex each rendered source
                                              through the REAL lexer and report
                                              whether the AST matches the walk

Each profile writes monkey_data/<name>.json (the token stream) and
monkey_data/<name>.rule (the rendered source, for human reading). The random
walk's policy (OR spread, recursion coin, repetition counts, Luau nesting) is
the Walker class here; the shared primitives (tok, ListLexer, reachability) come
from aux_walker.

This file is excluded from HWUT test discovery via '--not' in hwut-info.dat.
______________________________________________________________________________
"""
import os
import sys
import json

import config  # noqa: F401  -- FIRST: puts the 'vut' repository on sys.path

from dataclasses import is_dataclass, fields

from vut.language_support.python.deterministic_random import (DeterministicStream,
                                                             SelectionMarker)
from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar, parse
from vut.engine.temporal_logic.parser.core.ll2_engine import EngineParser
from vut.engine.temporal_logic.parser.core.ll2_grammar_spec import (
        Terminal_Spec, Rule_Spec, Tagged_Spec,
        SEQ_Spec, OR_Spec, OPT_Spec, PLUS_Spec, STAR_Spec)
from vut.engine.temporal_logic.parser.core.lexer import Token
from vut.engine.temporal_logic.parser.core.ll2_grammar_spec import T, t_fr_span_open, t_fr_eof
from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter
from fake_luau_oracle import FakeLuauOracle

from aux_walker import (tok as _tok, ListLexer as _ListLexer,
                        reaches, branch_reenters, _children, min_terminal_distance)


# Reachability closure over the grammar graph, computed once. The Walker asks
# 'does this branch lead back into an active rule?' as a finite set test.
_REACHES = reaches(compiled_grammar())


def _branch_reenters(element, active):
    """RETURN: True if 'element' can reach a rule currently being expanded."""
    return branch_reenters(element, active, _REACHES)


def _count_nt(element):
    """RETURN: int, the number of NonTerminals reachable in 'element'."""
    if isinstance(element, Terminal_Spec):
        return 0
    if isinstance(element, Rule_Spec):
        return 1
    return sum(_count_nt(e) for e in _children(element))


def _shallowest(branches):
    """RETURN: list, the branch(es) with the shortest full derivation (fallback).

    Scored by min_terminal_distance (the fewest tokens to bottom out at
    terminals), not by a one-level NonTerminal count: at a deep cyclic OR where
    every branch re-enters (e.g. <cond-atom> via the bridge/paren cycle), the
    one-level count ties <cond-bracket> with <comparison> and could pick the
    re-entering bracket forever. The shortest-derivation branch always
    terminates.
    """
    g = compiled_grammar()
    scored = [(min_terminal_distance(b, g), b) for b in branches]
    lo = min(s for s, _ in scored)
    return [b for s, b in scored if s == lo]


class Walker:
    """Walks a compiled grammar with a DeterministicStream to emit valid tokens.

    A walk is fully determined by (stream seed, profile weights), so the token
    sequence -- and thus the parsed AST -- is reproducible.
    """
    def __init__(self, grammar, stream, profile):
        """RETURN: None. Binds the grammar, the random stream, and the profile."""
        self.g       = grammar
        self.s       = stream
        self.p       = profile
        self.id_n    = 0
        self.tokens  = []
        self.luau    = []
        self._active = []
        self.visited = set()      # rule names entered during the walk
        self._markers = {}        # id(OR element) -> SelectionMarker

    def walk_file(self, n_items):
        """RETURN: (tokens, luau_texts) for 'n_items' top-level constructs."""
        start = self.g.rules[self.g.start]
        for _ in range(n_items):
            self._emit(start, self.p["depth"])
        self.tokens.append(Token(t_fr_eof, "", 0, 0))
        return self.tokens, self.luau

    def _next_id(self):
        """RETURN: int, a fresh identifier suffix so names vary across the walk."""
        self.id_n += 1
        return self.id_n

    def _emit(self, element, budget):
        """RETURN: None. Appends tokens for 'element', bounded by 'budget'."""
        if isinstance(element, Terminal_Spec):
            if element.is_opaque:
                self._emit_luau(budget)
            else:
                self.tokens.append(_tok(element, self._next_id()))
            return
        if isinstance(element, Tagged_Spec):
            # An advisory role tag (D-10) is transparent: emit its body.
            self._emit(element.body, budget)
            return
        if isinstance(element, Rule_Spec):
            self.visited.add(element.name)
            self._active.append(element.name)
            try:
                self._emit(element.pattern, budget - 1)
            finally:
                self._active.pop()
            return
        if isinstance(element, SEQ_Spec):
            for sub in element.branches:
                self._emit(sub, budget)
        elif isinstance(element, OR_Spec):
            self._emit(self._pick_alt(element, budget), budget)
        elif isinstance(element, OPT_Spec):
            if budget > 0 and self.s.coin(self.p["opt"] * 0.01):
                self._emit(element.body, budget)
        elif isinstance(element, PLUS_Spec):
            for _ in range(self._rep_count(1, budget)):
                self._emit(element.body, budget)
        elif isinstance(element, STAR_Spec):
            for _ in range(self._rep_count(0, budget)):
                self._emit(element.body, budget)
        else:
            raise ValueError("unknown grammar node %r" % (element,))

    def _marker_for(self, element):
        """RETURN: SelectionMarker, the spread memory for one grammar OR node.

        Keyed by the OR element's identity, so one marker serves every entry
        into that alternation across the whole walk -- coverage-style spread.
        The element is a long-lived grammar node, so id() is a stable key
        (unlike id() of the transient safe/recursive sub-pools).
        """
        m = self._markers.get(id(element))
        if m is None:
            m = SelectionMarker()
            self._markers[id(element)] = m
        return m

    def _pick_alt(self, element, budget):
        """
        RETURN: element, a chosen OR branch.

        When the budget is spent, restricts the choice to branches that do NOT
        re-enter the rule being expanded so the walk terminates. While budget
        remains, with probability 'recurse'% prefers a branch that re-enters an
        active rule (deep nesting); otherwise spreads across branches, preferring
        ones not yet chosen at this OR so every alternative is exercised.

        Spread memory is one SelectionMarker per OR node (held by the walker),
        shared across this site's safe/recursive/full sub-pools by BRANCH
        identity. So the spread is reproducible regardless of container address
        reuse -- the marker, not id(container), is the memory.
        """
        branches = element.branches
        marker   = self._marker_for(element)
        active   = set(self._active)
        if budget <= 0:
            safe = [b for b in branches if not _branch_reenters(b, active)]
            pool = safe if safe else _shallowest(branches)
            return self.s.select_unchosen(pool, marker)
        recursive = [b for b in branches if _branch_reenters(b, active)]
        if recursive and self.s.coin(self.p["recurse"] * 0.01):
            return self.s.select_unchosen(recursive, marker)
        # Spread across ALL branches, preferring unchosen ones at this OR.
        return self.s.select_unchosen(branches, marker)

    def _rep_count(self, minimum, budget):
        """RETURN: int, a repetition count drawn from the profile and capped."""
        if budget <= 0:
            return max(minimum, 1) if minimum == 0 else minimum
        return self.s.next_int(max(minimum, 1), self.p["reps"])

    def _emit_luau(self, budget):
        """RETURN: None. Emits a LUAU_OPEN and queues a balanced block body.

        The body is opaque to the parser, so only balance matters. The 'luau'
        profile nests braces to exercise the oracle's matching; others stay flat.
        """
        depth = self.s.next_int(0, self.p["luau"])
        inner = "x" + "{ y }" * depth
        text  = "{ " + inner + " }"
        self.luau.append(text)
        self.tokens.append(Token(t_fr_span_open, "{", 0, 0))


# --------------------------------------------------------------------------
# Profiles: a seed and weight dict each.
#   depth : descent budget before OR is forced shallow / reps forced minimal
#   reps  : maximum PLUS/STAR repetition count
#   opt   : percent chance an OPT is taken
#   luau  : maximum nested-brace depth inside a Luau block
#   items : number of top-level constructs in the file
#   recurse : percent chance a recursive branch is preferred while budget remains
# --------------------------------------------------------------------------
_PROFILES = {
    "deep":     {"seed": 0x0DEE,  "depth": 30, "reps": 1, "opt": 20, "luau": 0, "items": 3, "recurse": 80},
    "wide":     {"seed": 0x031D,  "depth": 6,  "reps": 5, "opt": 60, "luau": 1, "items": 6, "recurse": 10},
    "luau":     {"seed": 0x1A41,  "depth": 6,  "reps": 2, "opt": 50, "luau": 6, "items": 6, "recurse": 15},
    "balanced": {"seed": 0xBA1,   "depth": 8,  "reps": 2, "opt": 45, "luau": 2, "items": 5, "recurse": 25},
    "states":   {"seed": 0x101,   "depth": 8,  "reps": 4, "opt": 40, "luau": 1, "items": 6, "recurse": 20},
    "spread":   {"seed": 0xC0FFEE, "depth": 10, "reps": 4, "opt": 100, "luau": 1, "items": 12, "recurse": 10},
    # 'members' biases toward present optionals and several arg repetitions so
    # the arg surface is exercised heavily: named args ('name = value'), shallow
    # member access ('event.x' / 'sm.x' / 'mg.x' / 'mode.x'), and the typed
    # member declarations ('name: type') that those accesses resolve against.
    "members":  {"seed": 0x3E3B,  "depth": 9,  "reps": 3, "opt": 90, "luau": 2, "items": 8, "recurse": 15},
    # 'clockwork' biases toward deep nesting and present optionals so the
    # clockwork body is exercised: the step variety (paced emission, instant:,
    # the bare commands), wait:/select: suspension, and the if/elif/else and
    # while control frames composing within one another.
    "clockwork": {"seed": 0xC107,  "depth": 12, "reps": 3, "opt": 80, "luau": 2, "items": 6, "recurse": 30},
    # 'math' biases toward long operator chains (high reps) and present optionals
    # (high opt) to exercise the arithmetic surface: the multiplicative ladder
    # including '/', and the expression-level 'undef:' fallback that a division
    # carries. Free-function and method calls fall out of the operand's optional
    # leading call and postfix chain.
    "math":     {"seed": 0x4A12,  "depth": 10, "reps": 6, "opt": 95, "luau": 0, "items": 5, "recurse": 12},
}


# Tokens before which a newline reads naturally; keeps rendered source legible
# and lets the REAL lexer re-parse it (newlines separate statement-ish forms).
_NEWLINE_BEFORE = {
    T.string(s) for s in (
        "=>", "until:", "on:", "mode:", "mode_group:", "state_machine:",
        "state:", "event:", "clock:", "open:", ":close", "has:", "default:",
        "init:", "deinit:", ":end",
        "clockwork:", "instant:", "wait:", "select:", "if:", "elif:", "else:",
        "while:", "spawn:", "unspawn:", "arm:",
    )
}


def _render_source(tokens, luau_texts):
    """RETURN: str, readable source text for the synthesized token stream.

    Splices each queued Luau block in at its LUAU_OPEN and inserts a newline
    before statement-ish tokens so the text is legible and re-lexable by the
    REAL lexer. Identifiers keep their per-walk suffix so names stay distinct.
    """
    luau_i = 0
    out    = []
    for t in tokens:
        if t.kind is t_fr_eof:
            continue
        if t.kind is t_fr_span_open:
            text = luau_texts[luau_i] if luau_i < len(luau_texts) else "{ }"
            luau_i += 1
            if out and not out[-1].endswith("\n"):
                out.append(" ")
            out.append(text)
            continue
        if out and t.kind in _NEWLINE_BEFORE:
            out.append("\n")
        elif out and not out[-1].endswith("\n"):
            out.append(" ")
        out.append(t.text)
    return "".join(out).strip() + "\n"


def _fmt(node, indent=0):
    """RETURN: str, a stable indented rendering of an AST node / sequence / leaf."""
    pad = "  " * indent
    if isinstance(node, (list, tuple)):
        if not node:
            return pad + "[]"
        return "\n".join(_fmt(x, indent) for x in node)
    if is_dataclass(node):
        lines = [pad + type(node).__name__]
        for f in fields(node):
            val = getattr(node, f.name)
            if is_dataclass(val) or isinstance(val, list):
                lines.append("%s  %s:" % (pad, f.name))
                lines.append(_fmt(val, indent + 2))
            else:
                lines.append("%s  %s = %r" % (pad, f.name, val))
        return "\n".join(lines)
    return pad + repr(node)


def _strip_begin(text):
    """RETURN: str, the formatted AST with 'begin = N' lines removed."""
    return "\n".join(l for l in text.splitlines()
                     if l.strip().split(" = ")[0] != "begin")


def _collect_node_types(node, seen):
    """RETURN: None. Adds the type name of every AST dataclass found in 'node'."""
    if isinstance(node, (list, tuple)):
        for x in node:
            _collect_node_types(x, seen)
    elif is_dataclass(node) and type(node).__module__.endswith("ast_nodes"):
        seen.add(type(node).__name__)
        for f in fields(node):
            _collect_node_types(getattr(node, f.name), seen)


def _all_node_types():
    """RETURN: set, names of AST node types that can appear in a finished tree."""
    import vut.engine.temporal_logic.parser.ast_nodes as ast_mod
    transient = {"RuleFile", "InitBlock", "DeinitBlock"}
    out = set()
    for name in dir(ast_mod):
        obj = getattr(ast_mod, name)
        if isinstance(obj, type) and is_dataclass(obj) and name not in transient:
            out.add(name)
    return out


_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monkey_data")


def _fixture_path(profile_name):
    """RETURN: str, the monkey_data/ path of a profile's token fixture."""
    return os.path.join(_DATA_DIR, profile_name + ".json")


def _save_fixture(profile_name, tokens, luau_texts):
    """RETURN: None. Writes a profile's token stream to monkey_data/ as JSON.

    A token is stored as (token-id name, lexeme); offsets are not stored (the
    fixture is offset-0, exactly as the walker emits). The rendered source is
    saved beside it as a '.rule' file for human reading, not for parsing.
    """
    os.makedirs(_DATA_DIR, exist_ok=True)
    payload = {
        "tokens": [(t.kind._name(), t.text) for t in tokens],
        "luau":   list(luau_texts),
    }
    with open(_fixture_path(profile_name), "w") as fh:
        json.dump(payload, fh, indent=1)
    with open(os.path.join(_DATA_DIR, profile_name + ".rule"), "w") as fh:
        fh.write(_render_source(tokens, luau_texts))


def _create_profile(g, name, profile, debug):
    """RETURN: None. Walks one profile, saves its fixture, prints a walk report.

    With 'debug', additionally re-lexes the rendered source through the real
    lexer and reports whether the resulting AST matches the walk's own parse --
    the cross-check that the rendered '.rule' file is itself re-parseable.
    """
    walker = Walker(g, DeterministicStream(profile["seed"]), profile)
    tokens, luau_texts = walker.walk_file(profile["items"])
    _save_fixture(name, tokens, luau_texts)

    parser = EngineParser(None, None, DiagnosticReporter(), g,
                          lexer=_ListLexer(tokens, luau_texts))
    rule_file = parser.parse()

    node_types = set()
    _collect_node_types(rule_file.items, node_types)
    print("=== created: %s ===" % name)
    print("tokens:             %d" % (len(tokens) - 1))
    print("top-level items:    %d" % len(rule_file.items))
    print("rules visited:      %d / %d" % (len(walker.visited), len(g.rules)))
    print("node types built:   %d / %d" % (len(node_types), len(_all_node_types())))
    if parser.reporter.errors:
        print("UNEXPECTED DIAGNOSTICS:")
        for d in parser.reporter.errors:
            print("   %s off=%d %s" % (d.phase.name, d.source_offset, d.message))

    if debug:
        source = _render_source(tokens, luau_texts)
        rep2   = DiagnosticReporter()
        rule_file2 = parse(source, FakeLuauOracle(), rep2)
        same = (_strip_begin(_fmt(rule_file.items))
                == _strip_begin(_fmt(rule_file2.items)))
        print("[debug] real-lexer reparse: %s, %d diagnostic(s)"
              % ("AST matches" if same else "AST DIFFERS", len(rep2.errors)))


def main():
    """RETURN: None. Regenerate every profile's monkey_data/ fixture."""
    g     = compiled_grammar()
    debug = "--debug" in sys.argv
    for name, profile in _PROFILES.items():
        _create_profile(g, name, profile, debug)


if __name__ == "__main__":
    main()
