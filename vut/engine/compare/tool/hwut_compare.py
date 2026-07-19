#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Colorized preview of how the compare engine's TOLERANCE LEXER
         interprets ONE input stream -- an authoring aid for writing GOOD
         files, not a two-file comparison. It shows, line by line, which
         parts of the text the engine treats as an analogy, a number, an
         equivalence ("happy") pattern, a constraint binding, and so on --
         BEFORE you run an actual test.

USAGE:
    hwut_compare.py < file                 read from standard input
    hwut_compare.py <file>                 read the named file
    hwut_compare.py --config cfg.py <file> use a project's real lexer
                                           configuration (see CONFIG below)
    hwut.compare <file>                    thin wrapper, same as above

COLORS (defaults):
    STRING                        plain (terminal default)
    ANALOGY              ((..))    ORANGE on WHITE
    NUMERIC                        BLUE
    EQUIVALENCE_PATTERN            GREEN on GREY   ("happy patterns")
    CONSTRAINT_BINDING   ((n: v))  MAGENTA, bold
    VISIBLE_NOTHING / SEPERATOR    dim
    Region framing (##! .../####)  bold CYAN
    BLANK / IGNORED lines          dim, whole line

Colors are disabled automatically when stdout is not a terminal; force
with --color, suppress with --no-color or NO_COLOR=1.

REGIONS THAT DO NOT TOLERANCE-LEX (DOC/SEMANTICS.txt section 7): verbatim,
ignore, point-cloud, and table never route their content through the
tolerance lexer -- only the outer sequential text and 'potpourri' do. This
tool shows such regions' content PLAIN, with a one-line note, so it is not
mistaken for un-lexed real text.

CONFIG: a project's actual lexer settings are a 'Configuration' object,
never a file this tool can just read cold. '--config cfg.py' loads a
plain Python file that may set any of the following module-level names
(unset ones keep the built-in preview default shown after each):

    analogy_f = True;  whitespace_f = True;  backslash_f = True
    strip_whitespace_f = True;      constraint_f = True
    numeric_tolerance_ratio    = 0.1     # any nonzero value enables
                                         # NUMERIC lexing here -- the exact
                                         # ratio does not change this
                                         # preview's coloring, only a real
                                         # comparison's verdict
    equivalent_pattern_list      = []    # e.g. [r"happy|glad"]
    visible_nothing_pattern_list = []
    ignored_line_begin_marker  = "##";   ignored_line_end_marker  = "##"
    analogy_begin_marker       = "((";   analogy_end_marker       = "))"
    constraint_db = {}                   # e.g. {"y": "y >= x"}

Without '--config' this tool uses the defaults above -- NOT the bare
'Configuration()' default, which leaves 'numeric_tolerance_ratio' at 0 and
'equivalent_pattern_list' empty (nothing would ever be lexed as NUMERIC or
EQUIVALENCE_PATTERN). The preview default turns numeric lexing on so
'BLUE' has something to show; it configures no demo equivalence pattern,
since those are always project-specific -- pass '--config' for those.
________________________________________________________________________________
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "../../../.."))

import vut.engine.compare.configuration                as     configuration     # noqa: E402
from   vut.engine.compare.engine.input.pattern_finder   import PatternFinder    # noqa: E402
from   vut.engine.compare.engine.input.line_scanner     import (classify,       # noqa: E402
                                                                 E_LineClass,
                                                                 REGION_BEGIN_MARKER)
from   vut.engine.compare.engine.enums                  import E_ToleranceId    # noqa: E402


RESET = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"


def fg(n): return "\033[38;5;%dm" % n
def bg(n): return "\033[48;5;%dm" % n


STYLE_DB = {
    E_ToleranceId.STRING:              "",
    E_ToleranceId.ANALOGY:             fg(208) + bg(255),   # orange on white
    E_ToleranceId.NUMERIC:             fg(33),              # blue
    E_ToleranceId.EQUIVALENCE_PATTERN: fg(34) + bg(240),    # green on grey
    E_ToleranceId.VISIBLE_NOTHING:     DIM,
    E_ToleranceId.SEPERATOR:           DIM,
    E_ToleranceId.CONSTRAINT_BINDING:  BOLD + fg(201),      # magenta, bold
}

REGION_STYLE = BOLD + fg(51)   # cyan
DIM_STYLE    = DIM

# Regions whose content is NEVER routed through the tolerance lexer (see
# module docstring); everything else (the outer text, 'potpourri', or an
# unrecognized handler) is lexed -- 'region/registry.py' alone enforces
# what handlers actually exist, this preview stays permissive.
NOT_LEXED_HANDLER_SET = frozenset(("verbatim", "ignore", "point-cloud", "table"))


def make_pattern_finder(config_path):
    """RETURNS: PatternFinder built from the preview defaults, optionally
                overridden by a '--config' Python file (see module
                docstring for the recognized names).
    """
    pf_config = configuration.ConfigurationPatternFinder()
    pf_config.numeric_tolerance_ratio = 0.1   # preview default (see docstring)

    if config_path:
        namespace = {}
        with open(config_path, "r", encoding="utf-8") as fh:
            exec(compile(fh.read(), config_path, "exec"), namespace)  # noqa: S102
        for name in ("analogy_f", "whitespace_f", "backslash_f",
                     "strip_whitespace_f", "constraint_f",
                     "numeric_tolerance_ratio", "equivalent_pattern_list",
                     "visible_nothing_pattern_list",
                     "ignored_line_begin_marker", "ignored_line_end_marker",
                     "analogy_begin_marker", "analogy_end_marker"):
            if name in namespace:
                setattr(pf_config, name, namespace[name])

    return PatternFinder(pf_config)


def use_color(args):
    """RETURNS: True, if element styling should be emitted; False, else.

    Auto-detects a non-terminal stdout (e.g. piped to a file); '--color'
    forces it on, '--no-color' or NO_COLOR forces it off.
    """
    if "--no-color" in args or os.environ.get("NO_COLOR"):
        return False
    if "--color" in args:
        return True
    return sys.stdout.isatty()


def paint(text, style, color_f):
    if not color_f or not style:
        return text
    return style + text + RESET


def handler_of(shebang_line):
    """RETURNS: the handler NAME token of a '##! <handler> ...' line, or
                None if the line carries no token after the marker.

    Best-effort only: this preview tool tolerates malformed shebangs (a
    broken region is 'region/registry.py's business, loudly, not this
    tool's); it just needs the FIRST token to pick a lexing mode.
    """
    tail = shebang_line.strip()[len(REGION_BEGIN_MARKER):].strip()
    return tail.split()[0] if tail else None


def render_content(line, pf, color_f):
    for element in pf.do(line.rstrip("\n")):
        style = STYLE_DB.get(element.tolerance_id, "")
        sys.stdout.write(paint(element._string, style, color_f))
    sys.stdout.write("\n")


def run(stream, pf, color_f):
    """RETURNS: None -- writes the colorized preview of 'stream' to stdout.
    """
    handler       = None   # None == outer text; also lexed, like potpourri
    noted_handler = object()   # sentinel: force the first region's note

    for raw_line in stream:
        line_class = classify(raw_line, pf)

        if line_class is E_LineClass.REGION_BEGIN:
            handler       = handler_of(raw_line)
            noted_handler = object()
            print(paint(raw_line.rstrip("\n"), REGION_STYLE, color_f))
        elif line_class is E_LineClass.REGION_END:
            handler = None
            print(paint(raw_line.rstrip("\n"), REGION_STYLE, color_f))
        elif line_class in (E_LineClass.BLANK, E_LineClass.IGNORED):
            print(paint(raw_line.rstrip("\n"), DIM_STYLE, color_f))
        elif handler in NOT_LEXED_HANDLER_SET:
            if noted_handler != handler:
                print(paint("  # '%s' does not tolerance-lex its content "
                            "-- shown plain" % handler, DIM_STYLE, color_f))
                noted_handler = handler
            print(paint(raw_line.rstrip("\n"), "", color_f))
        else:
            render_content(raw_line, pf, color_f)


def main(argv):
    args = argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0

    positional = [a for a in args if not a.startswith("-")]
    config_path = None
    if "--config" in args:
        i = args.index("--config")
        config_path = args[i + 1]
        positional = [a for a in positional if a != config_path]

    color_f = use_color(args)
    try:
        pf = make_pattern_finder(config_path)
    except OSError as e:
        print("error: cannot read config %r: %s" % (config_path, e),
              file=sys.stderr)
        return 1

    try:
        if positional:
            try:
                fh = open(positional[0], "r", encoding="utf-8")
            except OSError as e:
                print("error: cannot read %r: %s" % (positional[0], e),
                      file=sys.stderr)
                return 1
            with fh:
                run(fh, pf, color_f)
        else:
            run(sys.stdin, pf, color_f)
    except BrokenPipeError:
        # Downstream (e.g. 'head') closed early -- not an error for a
        # streaming preview tool; exit quietly like well-behaved *nix tools.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
