#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Parse STORED monkey-fuzz fixtures and pin the resulting AST, plus two
         fixtures-free probes (a stackless depth bomb and the hand-written
         sprite examples). The random walk that GENERATES fixtures lives in
         monkey-file-creator.py; a normal run here touches no RNG, so the
         recording is reproducible.

CHOICES: deep, wide, luau, balanced, states, spread, depth_bomb, sprites.

DESCRIPTION:

Each profile choice (deep/wide/luau/balanced/states/spread) loads its stored
monkey_data/<name>.json token stream and parses it, printing the token count,
the top-level item count, any diagnostics, and the AST. The stored input is
fixed, so the AST is fixed -- only a grammar change (after re-running
monkey-file-creator.py) alters it.

'depth_bomb' parses 'open: a.b ... :close' nested to increasing depths, printing
one PASS/FAIL line per depth: a recursive engine overflows (RecursionError ->
FAIL), a stackless engine parses every depth (PASS). 'sprites' parses each
hand-written monkey_data/sprites_*.rule example and prints its AST.

If a fixture is missing, the choice fails with a directive to run
monkey-file-creator.py -- a fresh checkout or a new profile fails loudly rather
than with a confusing parse error.
______________________________________________________________________________
"""
import os
import sys
import json

from config import HwutRunner

import aux_renderer as R

from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar, parse
from vut.engine.temporal_logic.parser.core.ll1_engine import EngineParser
from vut.engine.temporal_logic.parser.core.lexer import Token
from vut.engine.temporal_logic.parser.core.terminals import terminal_by_name
from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter

from aux_walker import ListLexer

from fake_luau_oracle import FakeLuauOracle


_PROFILE_NAMES = ("deep", "wide", "luau", "balanced", "states", "spread")

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monkey_data")


def _fixture_path(profile_name):
    """RETURN: str, the monkey_data/ path of a profile's token fixture."""
    return os.path.join(_DATA_DIR, profile_name + ".json")


def _load_fixture(profile_name):
    """RETURN: (tokens, luau_texts), the stored token stream for a profile.

    Raises FileNotFoundError naming monkey-file-creator.py if the fixture is
    absent, so a fresh checkout or a new profile fails with a clear action
    rather than a confusing parse error.
    """
    path = _fixture_path(profile_name)
    if not os.path.exists(path):
        raise FileNotFoundError(
            "no fixture %s; run 'python3 monkey-file-creator.py' to generate "
            "monkey_data/ after a grammar change" % path)
    with open(path) as fh:
        payload = json.load(fh)
    tokens = [Token(terminal_by_name(name), text, 0, 0)
              for name, text in payload["tokens"]]
    return tokens, payload["luau"]


def _make_choice(profile_name):
    """RETURN: function, the HWUT run-function that parses one stored profile."""
    def run():
        g = compiled_grammar()
        tokens, luau_texts = _load_fixture(profile_name)

        parser = EngineParser.__new__(EngineParser)
        parser.reporter   = DiagnosticReporter()
        parser.grammar    = g
        parser.lexer      = ListLexer(tokens, luau_texts)
        parser.tok        = parser.lexer.next()
        parser._top_first = g.rules[g.start].first
        rule_file = parser.parse()

        print("=== monkey: %s ===" % profile_name)
        print("tokens parsed:      %d" % (len(tokens) - 1))
        print("top-level items:    %d" % len(rule_file.items))
        if parser.reporter.errors:
            print("UNEXPECTED DIAGNOSTICS:")
            for d in parser.reporter.errors:
                print("   %s off=%d %s"
                      % (d.phase.name, d.source_offset, d.message))
        else:
            print("diagnostics:        none")

        print("\n-- AST --")
        print(R.fmt(rule_file.items))
    return run


def run_depth_bomb():
    """RETURN: None. Nested-namespace liveness probe; the stackless acceptance test.

    Parses 'open: a.b ... :close' nested to increasing depths and prints one
    PASS/FAIL line per depth (not the AST), so the recording stays tiny. A
    recursive engine overflows past a few dozen levels (RecursionError -> FAIL);
    a stackless engine parses every depth (PASS). This is the objective
    criterion for the engine rewrite.
    """
    print("=== monkey: depth-bomb (namespace nesting) ===")
    for n in (10, 50, 100, 500, 20000):
        src = "open: a.b\n" * n + "on: T => Ping()\n" + ":close\n" * n
        rep = DiagnosticReporter()
        try:
            rf = parse(src, FakeLuauOracle(), rep)
            ok = (not rep.errors) and len(rf.items) == 1
            print("depth %5d : %s" % (n, "PASS" if ok else "FAIL (diagnostics)"))
        except RecursionError:
            print("depth %5d : FAIL (RecursionError: engine not stackless)" % n)


def run_sprites():
    """RETURN: None. Parses the massive sprites.rule and prints an AST census.

    sprites.rule exercises the full grammar surface in one file: include
    statements (recorded as AST nodes, NOT resolved -- resolution is a semantic
    concern), event/clock definitions, forward declarations, state machines
    (exclusive behaviour), mode groups (concurrent behaviour), and top-level
    causality rules. This is a pure parse; rather than dump the whole AST
    (thousands of nodes), it prints a recursive census -- how many of each node
    type the tree contains -- which pins the parse result compactly.
    """
    from dataclasses import is_dataclass, fields
    from collections import Counter

    rep = DiagnosticReporter()
    rule_file = parse(open(os.path.join(_DATA_DIR, "sprites.rule")).read(),
                      FakeLuauOracle(), rep)

    census = Counter()

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
        elif is_dataclass(n):
            census[type(n).__name__] += 1
            for fld in fields(n):
                walk(getattr(n, fld.name))

    walk(rule_file.items)

    print("=== monkey: sprites (massive example -- AST census) ===")
    status = "ok" if (rule_file.items and not rep.errors) else "DIAGNOSTICS"
    print("top-level items: %d (%s)" % (len(rule_file.items), status))
    print("total AST nodes: %d" % sum(census.values()))
    if rep.errors:
        for d in rep.errors:
            print("   %s off=%d %s"
                  % (d.phase.name, d.source_offset, d.message))
    print()
    # sorted by name for a stable, diffable census
    for name in sorted(census):
        print("  %-22s %5d" % (name, census[name]))


_CHOICES = {name: _make_choice(name) for name in _PROFILE_NAMES}
_CHOICES["depth_bomb"] = run_depth_bomb
_CHOICES["sprites"]    = run_sprites


HwutRunner(
    argv       = [a for a in sys.argv if a != "DEV"],
    title      = "Grammar Monkey Fuzz",
    choice_map = _CHOICES,
).run()
