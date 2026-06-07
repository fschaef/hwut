#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the rule-file Lexer: tokenizing, oracle handoff, error recovery.

CHOICES: tokens, dotted_names, comments_ws, oracle_handoff, mismatch,
         malformed_fragment, source_map;

DESCRIPTION:

The Lexer is pull-driven: the parser calls next() per control-plane token and
read_luau_block(role) at each '{'. These choices pin its observable behaviour.

    tokens              Every keyword, operator, literal, and identifier maps
                        to the expected E_TokenId, with correct source spans.
    dotted_names        '.' is its own DOT token; a dotted name lexes as
                        ID DOT ID, and a trailing 'VOID' surfaces as KW_VOID
                        rather than being swallowed into an identifier.
    comments_ws         '##' line comments and whitespace are skipped silently;
                        spans of the surviving tokens are unaffected.
    oracle_handoff      A '{ ... }' span is returned as one LUAU_BLOCK; a '}'
                        inside a Luau string is skipped, so the block ends at
                        the true closer, not the first '}'.
    mismatch            An illegal control-plane character is reported non-fatal
                        and returned as MISMATCH so the parser can resync; the
                        sticky error_f flag is raised and lexing continues.
    malformed_fragment  A Luau fragment the oracle cannot parse is reported
                        non-fatal, error_f is raised, and a LUAU_BLOCK over the
                        recovered span is still returned so lexing continues.
    source_map          SourceMap turns absolute offsets into 1-based
                        (line, column) pairs, including across a multi-line
                        Luau block the lexer skipped via the oracle.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner      import HwutRunner
from vut.engine.temporal_logic.parser.lexer       import Lexer, SourceMap
from vut.engine.temporal_logic.parser.terminals   import t_fr_luau_open, t_fr_luau_block, t_fr_eof
from vut.engine.temporal_logic.parser.diagnostic  import DiagnosticReporter
from vut.engine.temporal_logic.luau.luau_fragment import Role
from fake_luau_oracle import FakeLuauOracle


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def drive(text, role=Role.STATEMENT_BLOCK, record=False):
    """
    RETURN: (tokens, reporter, lexer), the full pull-driven lex of 'text'.

    Steps the Lexer to exhaustion. At each LUAU_OPEN it calls read_luau_block
    with 'role' (a single role suffices for these focused tests). A None block
    return (oracle infrastructure failure) ends the drive. END_OF_FILE is the
    last token included.
    """
    reporter = DiagnosticReporter()
    lexer    = Lexer(text, FakeLuauOracle(record=record), reporter)
    tokens   = []
    while True:
        tok = lexer.next()
        if tok.kind is t_fr_luau_open:
            block = lexer.read_luau_block(tok, role)
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
    src = ("on: mode: mode_group: state_machine: state: has: as: until: :end "
           "event: clock: into: in: open: :close container is: "
           "default: init: deinit: ANY BEGIN END VOID")
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


def run_comments_ws():
    """RETURN: None. '##' comments and whitespace vanish; spans stay correct."""
    banner("comment lines and blank lines are skipped")
    src = ("## a leading comment\n"
           "on Tick   ## trailing comment\n"
           "=> Beep()\n")
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
    # Drive once more with a recording oracle to show how many candidates
    # find_matching_brace tried before settling on the true closer.
    rep = DiagnosticReporter()
    rec = FakeLuauOracle(record=True)
    lx  = Lexer('=> { s = "a}b}c" }', rec, rep)
    lx.next()                       # ARROW
    open_tok = lx.next()            # LUAU_OPEN
    lx.read_luau_block(open_tok, Role.STATEMENT_BLOCK)
    print("oracle parse attempts:", len(rec.seen))


def run_mismatch():
    """RETURN: None. Illegal char is reported non-fatal and returned as MISMATCH."""
    banner("stray '?' between valid tokens")
    tokens, reporter, lexer = drive("on: ? :end")
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
    text = "on Tick\n  => { a =\n       1 }\nend\n"
    smap = SourceMap(text)
    #            offset : what is there
    points = [
        (0,  "'o' of on, line 1 col 1"),
        (3,  "'T' of Tick, line 1 col 4"),
        (8,  "first space of line 2"),
        (10, "'=' of =>, line 2"),
        (24, "'1' inside the Luau block, line 3"),
    ]
    for off, what in points:
        line, col = smap.line_column(off)
        print("offset %2d -> line %d col %2d   (%s)" % (off, line, col, what))

    banner("the Luau block the lexer skipped still resolves")
    tokens, _, _ = drive(text)
    block = [t for t in tokens if t.kind is t_fr_luau_block][0]
    bl, bc = smap.line_column(block.begin)
    el, ec = smap.line_column(block.end - 1)
    print("block opens at line %d col %d, closes at line %d col %d"
          % (bl, bc, el, ec))


HwutRunner(
    argv       = sys.argv,
    title      = "Rule-file Lexer",
    choice_map = {
        "tokens":             run_tokens,
        "dotted_names":       run_dotted_names,
        "comments_ws":        run_comments_ws,
        "oracle_handoff":     run_oracle_handoff,
        "mismatch":           run_mismatch,
        "malformed_fragment": run_malformed_fragment,
        "source_map":         run_source_map,
    },
).run()