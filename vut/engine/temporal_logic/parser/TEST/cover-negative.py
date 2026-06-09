#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Negative grammar coverage. For every grammar rule in sorted order, take
         the canonical minimal valid case and feed deliberately malformed
         variants of it to that rule in isolation, recording the parser's
         diagnostic and recovery response -- so error detection is pinned by one
         HWUT recording, just as the accepted language is by cover-syntax-tree.

CHOICES: negative.

DESCRIPTION:

A single 'negative' choice iterates 'sorted(grammar.rules)'. For each rule the
pure-minimum canonical path (aux_walker.minimal_path) is perturbed by
aux_walker.deviations into:

    junk-head            first token replaced with an unexpected one
    truncate             final token dropped               (when len >= 2)
    omit-required-k      each REQUIRED terminal dropped in turn

Only required terminals are omitted: dropping an optional one would still be
valid. Each malformed case is driven in isolation and the recording shows the
input, whether a node was still built (recovery), how many tokens were consumed,
and every diagnostic raised. A sub-rule that stops early -- consuming a valid
prefix and leaving the rest -- shows 'diag: (none; stopped early)', itself
meaningful.
______________________________________________________________________________
"""
import sys
from config import HwutRunner

import aux_walker   as W
import aux_renderer as R

from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar


def _print_outcome(res):
    """RETURN: None. Prints the recovery outcome and any diagnostics."""
    if res.node is None:
        print("   built:   no (rule abandoned)")
    else:
        print("   built:   %s" % type(res.node).__name__)
    print("   consumed: %d token(s); leftover: %d" % (res.consumed, res.leftover))
    if res.reporter.errors:
        for d in res.reporter.errors:
            print("   diag: %s off=%d %s"
                  % (d.phase.name, d.source_offset, d.message))
    else:
        print("   diag: (none; stopped early)")


def run_negative():
    """RETURN: None. Malformed deviations of every rule's minimal case, sorted."""
    g = compiled_grammar()
    for name in sorted(g.rules):
        rule = g.rules[name]
        print("=== negative: %s ===" % name)
        path = W.minimal_path(g, rule)
        for label, tokens in W.deviations(path):
            res = W.drive(g, rule, tokens)
            print("\n-- %s --" % label)
            print("   input: %s" % R.fragment(tokens))
            _print_outcome(res)
        print()


HwutRunner(
    argv       = [a for a in sys.argv if a != "DEV"],
    title      = "Grammar Rule Negative Coverage",
    choice_map = {"negative": run_negative},
).run()

