#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify the transpiler bottom layer: brace finding and source-to-
         target location mapping.

CHOICES: brace_find, brace_skip, brace_malformed, mapper, mapper_gaps;

DESCRIPTION:

  brace_find       'find_matching_brace' on clean statement-block and guard
                   spans using the real luau-ast binary. Checks the matching
                   '}' offset is returned.

  brace_skip       Spans whose Luau contains a '}' inside a double-quoted
                   string and inside a backtick interpolation hole. Checks
                   those braces are skipped and the true closer is found.

  brace_malformed  A span that never parses under any candidate '}'. Checks
                   'FragmentSyntaxError' is raised.

  mapper           Source2TargetLocationMapper over an emission of boilerplate,
                   a guard spliced behind 'if ', and a multi-line statement
                   block. Checks line mapping and the two column regimes
                   (first-line prefix vs body indent).

  mapper_gaps      Checks lines with no registered fragment (boilerplate,
                   blanks, provenance comments) resolve to None.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner

from vut.engine.temporal_logic.world.luau.luau_span_oracle   import find_matching_brace, Role, FragmentSyntaxError, LuauOracle
from vut.engine.temporal_logic.world.luau.location_mapper import Source2TargetLocationMapper


ORACLE = LuauOracle()


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


# --------------------------------------------------------------------------
# brace finding
# --------------------------------------------------------------------------

def run_brace_find():
    """RETURN: None. Matching '}' on clean statement-block and guard spans."""
    for label, role, source in [
            ("statement_block", Role.STATEMENT_BLOCK,
             "=> { vehicle.speed = 0 } off"),
            ("guard",           Role.CONDITION,
             "& { event.speed > 0 and not L:empty() } =>")]:
        banner(label)
        print("source :", repr(source))
        end = find_matching_brace(source, source.index("{"), role, ORACLE)
        print("closer :", end, "char", repr(source[end]))
        print("after  :", repr(source[end + 1:]))


def run_brace_skip():
    """RETURN: None. Braces inside strings and interpolation holes are skipped."""
    for label, source in [
            ("brace in string", '=> { x = "a } b" } off'),
            ("brace in interp", "=> { log(`t={x}`) } off"),
            ("brace in single-quote", "=> { if (a == '}') { print('nested') } }") 
        ]:
        banner(label)
        print("source :", repr(source))
        try:
            end = find_matching_brace(source, source.index("{"),
                                      Role.STATEMENT_BLOCK, ORACLE)
            print("closer :", end, "char", repr(source[end]))
            print("after  :", repr(source[end + 1:]))
        except Exception as e:
            print("caught: ", e.__class__.__name__)


def run_brace_malformed():
    """RETURN: None. A span that never parses raises FragmentSyntaxError."""
    source = "& { event.speed > ( } =>"
    banner("malformed")
    print("source :", repr(source))
    try:
        find_matching_brace(source, source.index("{"), Role.CONDITION, ORACLE)
        print("UNEXPECTED: no exception")
    except FragmentSyntaxError as exc:
        print("FragmentSyntaxError raised (expected)")
        print("at off :", exc.open_offset)


# --------------------------------------------------------------------------
# location mapper (no external binary needed)
# --------------------------------------------------------------------------

def _build_mapper():
    """RETURN: Source2TargetLocationMapper, an emission with mixed pieces.

    Layout (target lines):
      0,1   boilerplate
      2     guard fragment, src line 10, indent 2, behind 'if ' (prefix 3)
      3     boilerplate
      4,5,6 statement-block fragment, src lines 20..22, indent 4
      7     boilerplate
    """
    m = Source2TargetLocationMapper()
    m.advance(2)
    m.register_fragment("rules.tl", 10, 1, indent=2, first_line_prefix=3)
    m.advance(1)
    m.register_fragment("rules.tl", 20, 3, indent=4)
    m.advance(1)
    return m


def _show(m, target_line, target_col):
    """RETURN: None. Print a lookup result in a deterministic form."""
    loc = m.source_line_of(target_line, target_col)
    if loc is None:
        print("  target (%d,%d) -> None (generated)" % (target_line, target_col))
    else:
        print("  target (%d,%d) -> %s:%d:%d"
              % (target_line, target_col, loc.file, loc.line, loc.column))


def run_mapper():
    """RETURN: None. Line mapping and the two column regimes."""
    m = _build_mapper()
    banner("guard fragment (line 2, prefix 3, indent 2)")
    _show(m, 2, 5)
    _show(m, 2, 10)
    banner("statement block (lines 4..6, indent 4)")
    _show(m, 4, 4)
    _show(m, 5, 10)
    _show(m, 6, 4)
    banner("total target lines")
    print("count  :", m.target_line_count)


def run_mapper_gaps():
    """RETURN: None. Boilerplate / blank / comment lines resolve to None."""
    m = _build_mapper()
    banner("gaps")
    for t in (0, 1, 3, 7, 99):
        _show(m, t, 0)


HwutRunner(
    argv       = sys.argv,
    title      = "transpiler bottom layer: brace finder and location mapper",
    choice_map = {
        "brace_find":      run_brace_find,
        "brace_skip":      run_brace_skip,
        "brace_malformed": run_brace_malformed,
        "mapper":          run_mapper,
        "mapper_gaps":     run_mapper_gaps,
    },
).run()
