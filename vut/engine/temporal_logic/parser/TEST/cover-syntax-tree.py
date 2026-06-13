#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Positive grammar coverage. Walk every grammar rule in sorted order,
         synthesize the canonical paths through it, parse each in isolation, and
         print the resulting AST -- so the accepted language is pinned by one
         HWUT recording.

CHOICES: positive.

DESCRIPTION:

A single 'positive' choice iterates 'sorted(grammar.rules)'. For each rule the
canonical paths come from aux_walker.rule_paths: an OR rule yields one path per
branch; a rule with a variadic point yields one path per case (PLUS 1x/2x, STAR
0x/1x/2x, OPT absent/present); otherwise a single default path. Each path is
driven against its rule in isolation and the built AST is printed beneath the
input fragment.

Because the iteration is sorted, a grammar change shows up as a localised diff
in the affected rule's section. The choice set is fixed (one mega-choice), so
adding a grammar rule needs no edit here -- it simply appears in the walk.
______________________________________________________________________________
"""
import sys
from config import HwutRunner

import aux_walker   as W
import aux_renderer as R

from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar


def _print_diags(reporter):
    """RETURN: None. Prints any diagnostics raised during a drive."""
    for d in reporter.errors:
        print("   DIAG %s off=%d %s"
              % (d.phase.name, d.source_offset, d.message))


def run_positive():
    """RETURN: None. Canonical paths of every rule, sorted, parsed and dumped."""
    g = compiled_grammar()
    for name in sorted(g.rules):
        rule = g.rules[name]
        print("=== %s ===" % name)
        for path in W.rule_paths(g, rule):
            toks = path.tokens()
            res  = W.drive(g, rule, toks)
            print("\n-- %s --" % path.label)
            print("   input: %s" % R.fragment(toks))
            print(R.fmt(res.node))
            _print_diags(res.reporter)
        print()


HwutRunner(
    argv       = [a for a in sys.argv if a != "DEV"],
    title      = "Grammar Rule Positive Coverage",
    choice_map = {"positive": run_positive},
).run()