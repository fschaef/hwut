#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the LEXER MACHINERY grammar-agnostically: comment/whitespace skip
         groups, error recovery (illegal char -> MISMATCH), and SourceMap offset
         resolution. '{' and '}' are ordinary tokens like any other symbol.

         These behaviours do not depend on WHICH keywords a grammar declares, so
         the test registers a small TOY grammar (just the symbols its inputs use)
         rather than the rule language. The lexer's behaviour on the rule
         language's specific keyword set and dotted-name semantics is a LANGUAGE
         concern, tested in parser/TEST/test-lexer.py.

CHOICES: comments_ws, mismatch, source_map.

DESCRIPTION:

    comments_ws  '##' line comments and whitespace are skipped silently; spans
                 of the surviving tokens are unaffected.
    mismatch     An illegal character is reported non-fatal and returned as
                 MISMATCH so the parser can resync; the sticky error_f flag is
                 raised and lexing continues.
    source_map   Offsets resolve to 1-based (line, column), independent of how
                 the text was tokenized.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.core.lexer.lexer import (Lexer, SourceMap,
                                                         register_grammar)
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import t_fr_eof
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter


# A TOY grammar whose only purpose is to seed the lexer's token spec with the
# handful of symbols the machinery inputs use. '{' and '}' are ordinary symbols
# now, declared here like the rest; the skip/mismatch/eof groups are framing and
# always present. Keyword identity is irrelevant here -- the tests assert skip,
# recovery and mapping, not which lexeme is which keyword.
_TOY = {"toy": ("=>", "&", "(", ")", "{", "}")}
register_grammar(_TOY)


def banner(label):
    """RETURN: None, always. Prints a section heading for the label."""
    print()
    print("--- %s ---" % label)


def drive(text):
    """RETURN: (tokens, reporter, lexer), the full pull-driven lex of 'text'.

    Steps the Lexer to exhaustion; END_OF_FILE is the last token included.
    """
    reporter = DiagnosticReporter()
    lexer    = Lexer(text, reporter)
    tokens   = []
    while True:
        tok = lexer.next()
        tokens.append(tok)
        if tok.kind is t_fr_eof:
            break
    return tokens, reporter, lexer


def show_tokens(tokens):
    """RETURN: None, always. Prints each token's kind, span and lexeme, one per line."""
    for t in tokens:
        print("%-14s [%3d:%-3d] %r" % (t.kind._name(), t.begin, t.end, t.text))


def show_diagnostics(reporter):
    """RETURN: None, always. Prints each collected diagnostic deterministically."""
    if not reporter.errors:
        print("(no diagnostics)")
        return
    for d in reporter.errors:
        print("%-8s fatal=%-5s off=%-3d %s"
              % (d.phase.name, str(d.fatal), d.source_offset, d.message))


def run_comments_ws():
    """RETURN: None, always. Shows '##' comments and whitespace vanish; spans stay correct."""
    banner("comment lines and blank lines are skipped")
    src = ("## a leading comment\n"
           "( foo )   ## trailing comment\n"
           "=> ( bar )\n")
    tokens, _, _ = drive(src)
    show_tokens(tokens)


def run_mismatch():
    """RETURN: None, always. Shows an illegal char reported non-fatal and returned as MISMATCH."""
    banner("stray '?' between valid tokens")
    tokens, reporter, lexer = drive("=> ? &")
    show_tokens(tokens)
    print("error_f:", lexer.error_f)
    show_diagnostics(reporter)


def run_source_map():
    """RETURN: None, always. Shows offsets resolve to 1-based line/column."""
    banner("line/column of selected offsets")
    text = "=> foo\n  => { a =\n       1 }\nend\n"
    smap = SourceMap(text)
    points = [
        (0,  "'=' of =>, line 1 col 1"),
        (3,  "'f' of foo, line 1 col 4"),
        (7,  "first space of line 2"),
        (9,  "'=' of =>, line 2"),
        (23, "'1' on line 3"),
    ]
    for off, what in points:
        line, col = smap.line_column(off)
        print("offset %2d -> line %d col %2d   (%s)" % (off, line, col, what))

    banner("braces are ordinary tokens in the stream")
    tokens, _, _ = drive(text)
    show_tokens(tokens)


HwutRunner(
    argv       = sys.argv,
    title      = "Core Lexer Machinery",
    choice_map = {
        "comments_ws": run_comments_ws,
        "mismatch":    run_mismatch,
        "source_map":  run_source_map,
    },
).run()
