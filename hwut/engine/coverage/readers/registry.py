"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHICH TOOL SERVES THIS LANGUAGE -- and which reader serves that
         tool.

DESCRIPTION
       ONE TOOL PER LANGUAGE, NAMED (RATIONALE D-46). 'language-setup.
       <lang>.coverage' names the tool, '.format' optionally the format;
       'serving_framework' resolves both or refuses BY NAME. Nothing is
       elected: a tool absent from the machine is a refusal, and no
       second tool is tried. THE TABLE IS NOT HERE (D-26): it stands in
       'HWUT_ROOT/setup.conf', and the boundary face writes the shipped
       table into a new root conf.
       THE LANGUAGE IS THE KEY, not the interpreter: it is the one thing
       all three source kinds have. An EXECUTABLE and a COMPILED test
       have no interpreter to match on, and 'python3' and 'pypy3' are one
       language under two names.

       WHERE THE LANGUAGE IS NOT STATED it is DERIVED from the source
       file's extension -- stated, never silent: the language that served
       appears in the record's header and in every refusal.

       A REFUSAL NAMES the language and the tool. A skipped measurement
       reads as an absent one, and absence and emptiness do not
       collapse.
______________________________________________________________________________
"""
import shutil

from ..configuration import CoverageRefused


#  EXTENSION -> LANGUAGE, for the derivation. A source kind that carries
#  no extension carries no derivation either, and the language must be
#  stated.
EXTENSION_DB = {
    ".py":     "python",   ".pyw":  "python",   ".pyx":  "cython",
    ".lua":    "lua",
    ".c":      "c",        ".h":    "c",
    ".cpp":    "c++",      ".cc":   "c++",      ".cxx":  "c++",
    ".hpp":    "c++",      ".hh":   "c++",      ".hxx":  "c++",
    ".ipp":    "c++",
    ".m":      "objective-c",                   ".mm":   "objective-c++",
    ".f":      "fortran",  ".for":  "fortran",  ".f77":  "fortran",
    ".f90":    "fortran",  ".f95":  "fortran",  ".f03":  "fortran",
    ".f08":    "fortran",
    ".adb":    "ada",      ".ads":  "ada",
    ".mod":    "modula-2", ".def":  "modula-2",
    ".cob":    "cobol",    ".cbl":  "cobol",
    ".vala":   "vala",
    ".nim":    "nim",
    ".s":      "assembly", ".asm":  "assembly",
    ".go":     "go",
    ".rs":     "rust",
    ".swift":  "swift",
    ".d":      "d",        ".di":   "d",
    ".zig":    "zig",
    ".cr":     "crystal",
    ".jl":     "julia",
    ".r":      "r",        ".R":    "r",
    ".hs":     "haskell",  ".lhs":  "haskell",
    ".erl":    "erlang",   ".hrl":  "erlang",
    ".ex":     "elixir",   ".exs":  "elixir",
    ".ml":     "ocaml",    ".mli":  "ocaml",
    ".clj":    "clojure",  ".cljs": "clojure",  ".cljc": "clojure",
    ".lisp":   "common-lisp",                   ".lsp":  "common-lisp",
    ".pl":     "perl",     ".pm":   "perl",     ".t":    "perl",
    ".sol":    "solidity",
    ".dart":   "dart",
    ".java":   "java",
    ".kt":     "kotlin",   ".kts":  "kotlin",
    ".scala":  "scala",    ".sc":   "scala",
    ".groovy": "groovy",
    ".js":     "javascript",                    ".mjs":  "javascript",
    ".cjs":    "javascript",                    ".jsx":  "javascript",
    ".ts":     "typescript",                    ".tsx":  "typescript",
    ".rb":     "ruby",
    ".php":    "php",
    ".sh":     "shell",    ".bash": "bash",     ".zsh":  "zsh",
    ".ps1":    "powershell",
    ".tcl":    "tcl",
    ".cs":     "csharp",
    ".fs":     "fsharp",       ".fsx":  "fsharp",
    ".vb":     "vbdotnet",
    ".pas":    "pascal",   ".pp":   "pascal",   ".dpr":  "delphi",
    ".v":      "verilog",  ".sv":   "systemverilog",
    ".svh":    "systemverilog",                 ".vh":   "verilog",
    ".vhd":    "vhdl",     ".vhdl": "vhdl",
    #  '.m' is MATLAB's too, and Objective-C's, and Mercury's. It is
    #  given to Objective-C above because that is the language this
    #  component is most likely to meet beside C. A MATLAB tree must
    #  STATE its language -- which the derivation exists to make
    #  visible rather than silent (D-2).
}


def language_of(source_file, stated=None):
    """
    RETURN: str, the language: 'stated' where it is stated, else the one
            the source file's EXTENSION derives.

    Raises CoverageRefused where nothing is stated and the extension
    derives nothing -- a guessed language selects a guessed tool, and a
    tool that measures the wrong thing reports a green nobody earned.
    """
    if stated: return stated

    from pathlib import Path
    suffix = Path(source_file).suffix.lower()
    language = EXTENSION_DB.get(suffix)
    if language is None:
        raise CoverageRefused(
            "no language is stated for '%s' and its extension '%s' "
            "derives none. State 'language' in the coverage "
            "configuration." % (source_file, suffix or "<none>"))
    return language


def is_available(tool):
    """
    RETURN: True,  'tool' can be launched on this machine.
            False, else.

    Asked of the system, never inferred -- the same discipline the
    procsitter applies to a cap it cannot enforce.
    """
    return shutil.which(tool) is not None


def serving_framework(language, tool, format_name=None,
                      available=is_available):
    """
    RETURN: (CCoverageFramework, str), the framework of the ONE tool
            the language names and the format it is asked to write --
            'format_name', else the tool's default (D-46).

    Raises CoverageRefused, naming the language and the tool, where the
    language names no tool, where the tool is one hwut does not drive,
    where it offers no such format, or where this machine lacks it.
    No other tool is tried: the configuration says which tool measures,
    never the machine.

    'available' is a parameter so that a test may state the machine.
    """
    from .reader import callable_tuple, framework_of
    if tool is None:
        raise CoverageRefused(
            "language '%s' names no coverage tool in 'language-setup'; "
            "tools hwut drives: %s"
            % (language, ", ".join("'%s'" % t for t in callable_tuple())))
    framework = framework_of(tool)
    if not framework.offered_format_tuple:
        raise CoverageRefused(
            "coverage tool '%s' of language '%s' is read only: hwut does "
            "not drive it; tools hwut drives: %s"
            % (tool, language,
               ", ".join("'%s'" % t for t in callable_tuple())))
    if format_name is None:
        format_name = framework.offered_format_tuple[0]
    elif format_name not in framework.offered_format_tuple:
        raise CoverageRefused(
            "coverage tool '%s' offers no format '%s'; it offers %s"
            % (tool, format_name,
               ", ".join("'%s'" % f for f in framework.offered_format_tuple)))
    if not available(tool):
        raise CoverageRefused(
            "coverage tool '%s' of language '%s' is not on this machine "
            "=> install it; no other tool is tried" % (tool, language))
    return framework, format_name
