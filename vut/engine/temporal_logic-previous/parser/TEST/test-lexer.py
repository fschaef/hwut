#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the Lexer against the RULE LANGUAGE's lexical surface -- that the
         language's keyword set, operators, literals, and dotted-name semantics
         tokenize as expected. The lexer MACHINERY (skip groups, oracle handoff,
         error recovery, source maps) is grammar-agnostic and tested in
         core/TEST/test-lexer.py; this module is about the language's tokens.

CHOICES: tokens, dotted_names;

DESCRIPTION:

The Lexer is pull-driven: the parser calls next() per control-plane token and
read_span(role) at each '{'. These choices pin the language's tokens.

    tokens              Every keyword, operator, literal, and identifier of the
                        rule language maps to the expected terminal, with correct
                        source spans.
    dotted_names        '.' is its own DOT token; a dotted name lexes as
                        ID DOT ID, and a trailing 'VOID' surfaces as KW_VOID
                        rather than being swallowed into an identifier.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner      import HwutRunner
from vut.engine.temporal_logic.lexer.lexer import Lexer, SourceMap
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import t_fr_span_open, t_fr_span_block, t_fr_eof
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.world.luau.luau_span_oracle import Role
from fake_luau_oracle import FakeLuauOracle

# The lexer's token spec is seeded from the registered grammar. Package import no
# longer registers it (that side effect created an import cycle), so trigger the
# one-time registration explicitly via the facade before any lexing here.
from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar
compiled_grammar()


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def drive(text, role=Role.STATEMENT_BLOCK, record=False):
    """
    RETURN: (tokens, reporter, lexer), the full pull-driven lex of 'text'.

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
        print("%-12s [%3d:%-3d] %r" % (t.kind._name(), t.begin, t.end, t.text))


def show_diagnostics(reporter):
    """RETURN: None. Prints each collected diagnostic deterministically."""
    if not reporter.errors:
        print("(no diagnostics)")
        return
    for d in reporter.errors:
        print("%-8s fatal=%-5s off=%-3d %s"
              % (d.phase.name, str(d.fatal), d.source_offset, d.message))


def run_tokens():
    """RETURN: None. Each token kind maps as expected, with correct spans."""
    banner("keywords and structure")
    src = ("on: mode: mode_group: state_machine: state: has: until: :end "
           "event: clock: cause: effect: for: by: via: import: into: in: "
           "open: :close is: default: init: deinit: "
           "ANY BEGIN END CHANGE VOID "
           "mode state mode_group state_machine struct dict list "
           "int float string bool true false")
    tokens, _, _ = drive(src)
    show_tokens(tokens)

    banner("operators and symbols")
    tokens, _, _ = drive("=> & , +! -! ! ; . ( ) < > n:")
    show_tokens(tokens)

    banner("literals and identifiers")
    tokens, _, _ = drive('Tick_3 42 -7 3.5 "hello world"')
    show_tokens(tokens)


def run_dotted_names():
    """RETURN: None. DOT is separate; dotted names and trailing VOID split out."""
    banner("state-machine mode reference")
    tokens, _, _ = drive("SM_TASK.RUN")
    show_tokens(tokens)

    banner("reference ending in VOID keyword")
    tokens, _, _ = drive("SM_TASK.VOID")
    show_tokens(tokens)

    banner("three-part dotted name")
    tokens, _, _ = drive("default: SM.MEMBER")
    show_tokens(tokens)







HwutRunner(
    argv       = sys.argv,
    title      = "Rule-file Lexer",
    choice_map = {
        "tokens":       run_tokens,
        "dotted_names": run_dotted_names,
    },
).run()
