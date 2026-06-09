#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the LEXER MACHINERY grammar-agnostically: comment/whitespace skip
         groups, the Luau oracle handoff ('{ ... }' -> one LUAU_BLOCK), error
         recovery (illegal char -> MISMATCH; unparseable fragment -> recovered
         block), and SourceMap offset resolution across an oracle-skipped span.

         These behaviours do not depend on WHICH keywords a grammar declares, so
         the test registers a small TOY grammar (just the symbols its inputs use)
         rather than the rule language. The lexer's behaviour on the rule
         language's specific keyword set and dotted-name semantics is a LANGUAGE
         concern, tested in parser/TEST/test-lexer.py.

CHOICES: comments_ws, oracle_handoff, mismatch, malformed_fragment, source_map;

DESCRIPTION:

    comments_ws         '##' line comments and whitespace are skipped silently;
                        spans of the surviving tokens are unaffected.
    oracle_handoff      A '{ ... }' span returns as one LUAU_BLOCK; a '}' inside
                        a Luau string is skipped, so the block ends at the true
                        closer, not the first '}'. Also reports how many
                        candidate closers the oracle was asked about.
    mismatch            An illegal control-plane character is reported non-fatal
                        and returned as MISMATCH so the parser can resync; the
                        sticky error_f flag is raised and lexing continues.
    malformed_fragment  A Luau fragment the oracle cannot parse is reported
                        non-fatal, error_f is raised, and a LUAU_BLOCK over the
                        recovered span is still returned so lexing continues.
    source_map          Offsets resolve to 1-based (line, column), including
                        offsets inside a Luau block the lexer skipped.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.parser.core.lexer import (Lexer, SourceMap,
                                                         register_grammar)
from vut.engine.temporal_logic.parser.core.terminals import (t_fr_span_open,
                                                            t_fr_span_block,
                                                            t_fr_eof)
from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.luau.luau_fragment import Role
from fake_luau_oracle import FakeLuauOracle


# A TOY grammar whose only purpose is to seed the lexer's token spec with the
# handful of symbols the machinery inputs use ('=>', '&', '(', ')'). The Luau
# open '{' and the skip/mismatch groups are framing and always present, so they
# need no grammar. Keyword identity is irrelevant here -- the tests assert skip,
# handoff, recovery and mapping, not which lexeme is which keyword.
_TOY = {"toy": ("=>", "&", "(", ")")}
register_grammar(_TOY)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def drive(text, role=Role.STATEMENT_BLOCK, record=False):
    """RETURN: (tokens, reporter, lexer), the full pull-driven lex of 'text'.

    Steps the Lexer to exhaustion. At each LUAU_OPEN it calls read_span
    with 'role' (a single role suffices for these focused tests). A None block
    return (oracle infrastructure failure) ends the drive. END_OF_FILE is the
    last token included.
    """
    reporter = DiagnosticReporter()
    lexer    = Lexer(text, FakeLuauOracle(record=record), reporter)
    tokens   = []
    while True:
        tok = lexer.next()
        if tok.kind is t_fr_span_open:
            block = lexer.read_span(tok, role)
            if block is None:
                break
            tokens.append(block)
            continue
        tokens.append(tok)
        if tok.kind is t_fr_eof:
            break
    return tokens, reporter, lexer


def show_tokens(tokens):
    """RETURN: None. Prints each token's kind, span, and lexeme, one per line."""
    for t in tokens:
        print("%-14s [%3d:%-3d] %r" % (t.kind._name(), t.begin, t.end, t.text))


def show_diagnostics(reporter):
    """RETURN: None. Prints each collected diagnostic deterministically."""
    if not reporter.errors:
        print("(no diagnostics)")
        return
    for d in reporter.errors:
        print("%-8s fatal=%-5s off=%-3d %s"
              % (d.phase.name, str(d.fatal), d.source_offset, d.message))


def run_comments_ws():
    """RETURN: None. '##' comments and whitespace vanish; spans stay correct."""
    banner("comment lines and blank lines are skipped")
    src = ("## a leading comment\n"
           "( foo )   ## trailing comment\n"
           "=> ( bar )\n")
    tokens, _, _ = drive(src)
    show_tokens(tokens)


def run_oracle_handoff():
    """RETURN: None. A Luau span is one LUAU_BLOCK; inner '}' is not the closer."""
    banner("plain mutation block")
    tokens, _, _ = drive("=> { sm.n = sm.n + 1 }")
    show_tokens(tokens)

    banner("closing brace inside a Luau string is skipped")
    tokens, reporter, lexer = drive('=> { s = "a}b}c" }')
    show_tokens(tokens)
    print("error_f:", lexer.error_f)
    show_diagnostics(reporter)

    banner("candidate count for the string case")
    rep = DiagnosticReporter()
    rec = FakeLuauOracle(record=True)
    lx  = Lexer('=> { s = "a}b}c" }', rec, rep)
    lx.next()                       # ARROW
    open_tok = lx.next()            # LUAU_OPEN
    lx.read_span(open_tok, Role.STATEMENT_BLOCK)
    print("oracle parse attempts:", len(rec.seen))


def run_mismatch():
    """RETURN: None. Illegal char is reported non-fatal and returned as MISMATCH."""
    banner("stray '?' between valid tokens")
    tokens, reporter, lexer = drive("=> ? &")
    show_tokens(tokens)
    print("error_f:", lexer.error_f)
    show_diagnostics(reporter)


def run_malformed_fragment():
    """RETURN: None. Unparseable Luau is recovered; error_f set; block returned."""
    banner("unbalanced parenthesis in a guard fragment")
    # '( foo' never balances for any candidate '}', so the oracle rejects all;
    # find_matching_brace raises FragmentSyntaxError and the lexer recovers.
    tokens, reporter, lexer = drive("& { ( foo } => end", role=Role.CONDITION)
    show_tokens(tokens)
    print("error_f:", lexer.error_f)
    show_diagnostics(reporter)


def run_source_map():
    """RETURN: None. Offsets resolve to 1-based line/column, across Luau spans."""
    banner("line/column of selected offsets")
    text = "=> foo\n  => { a =\n       1 }\nend\n"
    smap = SourceMap(text)
    points = [
        (0,  "'=' of =>, line 1 col 1"),
        (3,  "'f' of foo, line 1 col 4"),
        (7,  "first space of line 2"),
        (9,  "'=' of =>, line 2"),
        (23, "'1' inside the Luau block, line 3"),
    ]
    for off, what in points:
        line, col = smap.line_column(off)
        print("offset %2d -> line %d col %2d   (%s)" % (off, line, col, what))

    banner("the Luau block the lexer skipped still resolves")
    tokens, _, _ = drive(text)
    block = [t for t in tokens if t.kind is t_fr_span_block][0]
    bl, bc = smap.line_column(block.begin)
    el, ec = smap.line_column(block.end - 1)
    print("block opens at line %d col %d, closes at line %d col %d"
          % (bl, bc, el, ec))


HwutRunner(
    argv       = sys.argv,
    title      = "Core Lexer Machinery",
    choice_map = {
        "comments_ws":        run_comments_ws,
        "oracle_handoff":     run_oracle_handoff,
        "mismatch":           run_mismatch,
        "malformed_fragment": run_malformed_fragment,
        "source_map":         run_source_map,
    },
).run()
