#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify 'GeneratedCodeChecker' against the real 'luau-analyze' binary:
         clean programs, type errors, syntax errors, boilerplate errors, multi-
         line fragments, two fragments separated by a gap, and strict mode.

CHOICES: clean, type_error, syntax_error, boilerplate_error,
         multiline_fragment, gap_between_fragments, strict_mode;

DESCRIPTION:

  clean               A well-typed assembled program produces no diagnostics.
                      Confirms the checker returns an empty list and does not
                      generate false positives.

  type_error          A type mismatch in a single-line fragment traces back to
                      the correct rule-file line and column.

  syntax_error        A syntax error inside a fragment (missing 'end') is
                      caught and traces back to the fragment's source line.

  boilerplate_error   An error deliberately placed in generated scaffolding
                      (not in any registered fragment) is reported as
                      'is_in_generated_code' and never blamed on author code.

  multiline_fragment  A three-line fragment with a type error on the second
                      line. Checks the linear offset arithmetic across multiple
                      lines and that the source line is source_base + 1.

  gap_between_fragments  Two fragments separated by boilerplate. An error in
                         the second fragment maps to the second fragment's
                         source origin, not the first's. Confirms the binary-
                         search interval lookup is correct across a gap.

  strict_mode         The '--!strict' directive is emitted as the first line
                      (registered as boilerplate) and activates stricter type
                      checking. An error that only appears under strict is
                      reported and traces back to the fragment.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner

from vut.engine.temporal_logic.world.luau.location_mapper      import Source2TargetLocationMapper
from vut.engine.temporal_logic.world.luau.generated_code_checker import GeneratedCodeChecker, format_diagnostic


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _assemble(*pieces):
    """RETURN: (str, Source2TargetLocationMapper) for a sequence of pieces.

    Each piece is either:
      ('boilerplate', text)   -- one or more lines, no source mapping
      ('fragment',    text, source_file, source_line, indent, prefix)

    The mapper is built in emission order. The assembled text is the
    concatenation of all piece texts, each terminated with a newline.
    """
    mapper = Source2TargetLocationMapper()
    lines  = []
    for piece in pieces:
        kind = piece[0]
        text = piece[1]
        count = text.count("\n") + (0 if text.endswith("\n") else 1)
        lines.append(text if text.endswith("\n") else text + "\n")
        if kind == "boilerplate":
            mapper.advance(count)
        else:
            _, _, source_file, source_line, indent, prefix = piece
            mapper.register_fragment(source_file, source_line, count,
                                     indent=indent, first_line_prefix=prefix)
    return "".join(lines), mapper


def _run(text, mapper):
    """RETURN: list of Diagnostic, sorted by target line for determinism."""
    checker = GeneratedCodeChecker(mapper)
    diags   = checker.analyze_text(text)
    return sorted(diags, key=lambda d: (d.target_line, d.target_column))


# --------------------------------------------------------------------------

def run_clean():
    """RETURN: None. A well-typed program produces no diagnostics."""
    text, mapper = _assemble(
        ("boilerplate", "--!strict"),
        ("boilerplate", "local function add(a: number, b: number): number"),
        ("boilerplate", "  return a + b"),
        ("boilerplate", "end"),
        ("fragment",    "local _ = add(1, 2)", "rules.tl", 10, 0, 0),
    )
    banner("program")
    print(text)
    banner("diagnostics")
    diags = _run(text, mapper)
    print("count:", len(diags))
    for d in diags:
        print(format_diagnostic(d))


def run_type_error():
    """RETURN: None. Type mismatch in a fragment traces to correct source."""
    text, mapper = _assemble(
        ("boilerplate", "--!strict"),
        ("boilerplate", "local function f(x: number) end"),
        ("fragment",    'f("wrong")', "rules.tl", 42, 0, 0),
    )
    banner("program")
    print(text)
    banner("diagnostics")
    for d in _run(text, mapper):
        print(format_diagnostic(d))


def run_syntax_error():
    """RETURN: None. Syntax error in a fragment traces to the fragment line."""
    text, mapper = _assemble(
        ("boilerplate", "--!strict"),
        ("fragment",    "do\n  local x = 1\n", "rules.tl", 7, 0, 0),
        # 'do' block without 'end' -- deliberate syntax error
    )
    banner("program")
    print(text)
    banner("diagnostics")
    for d in _run(text, mapper):
        print(format_diagnostic(d))


def run_boilerplate_error():
    """RETURN: None. Error in scaffolding is flagged as generated, not author."""
    # Boilerplate calls a function with the wrong type; the fragment is clean.
    text, mapper = _assemble(
        ("boilerplate", "--!strict"),
        ("boilerplate", "local function f(x: number) end"),
        ("boilerplate", 'f("in scaffolding")'),          # error here
        ("fragment",    "local x = 1", "rules.tl", 99, 0, 0),
    )
    banner("program")
    print(text)
    banner("diagnostics")
    for d in _run(text, mapper):
        print("is_generated:", d.is_in_generated_code)
        print(format_diagnostic(d))


def run_multiline_fragment():
    """RETURN: None. Error on line 2 of a 3-line fragment maps to source+1."""
    text, mapper = _assemble(
        ("boilerplate", "--!strict"),
        ("boilerplate", "local function f(x: number) end"),
        ("fragment",
         "local a = 1\n"
         'f("wrong")\n'
         "local b = 2",
         "rules.tl", 20, 2, 0),
    )
    banner("program")
    print(text)
    banner("diagnostics")
    for d in _run(text, mapper):
        print(format_diagnostic(d))


def run_gap_between_fragments():
    """RETURN: None. Error in second fragment maps to second fragment's source."""
    text, mapper = _assemble(
        ("boilerplate", "--!strict"),
        ("boilerplate", "local function f(x: number) end"),
        ("fragment",    "local x = 1",   "rules.tl", 10, 0, 0),
        ("boilerplate", "-- generated join"),
        ("fragment",    'f("wrong")',     "rules.tl", 50, 0, 0),
    )
    banner("program")
    print(text)
    banner("diagnostics")
    for d in _run(text, mapper):
        print(format_diagnostic(d))


def run_strict_mode():
    """RETURN: None. '--!strict' directive activates strict type checking."""
    # Without strict the implicit 'any' type would silence this error.
    text, mapper = _assemble(
        ("boilerplate", "--!strict"),
        ("boilerplate", "local function f(x: number): number return x + 1 end"),
        ("fragment",    'local y: string = f(1)', "rules.tl", 33, 0, 0),
    )
    banner("program")
    print(text)
    banner("diagnostics")
    for d in _run(text, mapper):
        print(format_diagnostic(d))


HwutRunner(
    argv       = sys.argv,
    title      = "generated code checker: luau-analyze integration",
    choice_map = {
        "clean":                 run_clean,
        "type_error":            run_type_error,
        "syntax_error":          run_syntax_error,
        "boilerplate_error":     run_boilerplate_error,
        "multiline_fragment":    run_multiline_fragment,
        "gap_between_fragments": run_gap_between_fragments,
        "strict_mode":           run_strict_mode,
    },
).run()
