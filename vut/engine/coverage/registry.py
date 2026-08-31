"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHICH TOOL SERVES THIS LANGUAGE -- and which reader serves that
         tool.

DESCRIPTION
       THE TABLE'S ORDER IS PART OF THE TABLE. 'elect' takes the first
       candidate the machine HAS, so a shipped list puts the tools whose
       FORMAT this build reads in front. A candidate with no reader is
       still worth listing: it is how a machine refuses BY NAME rather
       than reporting no coverage at all.

       AN EMPTY CANDIDATE LIST IS AN ANSWER. Where this author can vouch
       for no tool -- Pascal, Tcl -- the list is empty and the language
       refuses by name. Inventing a candidate would be worse: a tool that
       is wrong about what it measures reports a green nobody earned.

       THE CONFIGURATION NAMES A TOOL; THE COMPONENT RESOLVES THE READER
       (RATIONALE D-2). THE TABLE IS NOT HERE (D-26): the candidate
       tools of a language stand in 'language-setup.<lang>.coverage' of
       'hwut-root.conf', and the boundary face writes the shipped table
       into a new root conf. 'elect' takes the candidate tuple it is
       handed; this module ships no table of its own.

       THE LANGUAGE IS THE KEY, not the interpreter: it is the one thing
       all three source kinds have. An EXECUTABLE and a COMPILED test
       have no interpreter to match on, and 'python3' and 'pypy3' are one
       language under two names.

       WHERE THE LANGUAGE IS NOT STATED it is DERIVED from the source
       file's extension -- stated, never silent: the language that served
       appears in the record's header and in every refusal.

       NO CANDIDATE AVAILABLE IS A REFUSAL, naming what was looked for. A
       skipped measurement reads as an absent one, and absence and
       emptiness do not collapse.
______________________________________________________________________________
"""
import shutil

from .configuration import CoverageRefused


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


def elect(language, candidate_tuple, available=is_available):
    """
    RETURN: str, the FIRST of 'candidate_tuple' that this machine
            actually has -- the tool that serves 'language'.

    Raises CoverageRefused where the tuple is EMPTY (the language's
    entry vouches for no tool: an answer, D-2) or where every candidate
    is absent, NAMING each one -- so the reader of the refusal knows
    what to install rather than what went wrong.

    'available' is a parameter so that a test may state the machine.
    """
    if not candidate_tuple:
        raise CoverageRefused(
            "the 'coverage' list of language '%s' is EMPTY in "
            "'language-setup': it vouches for no coverage tool. Name "
            "one there -- inventing a default would be worse than "
            "saying so." % language)
    for tool in candidate_tuple:
        if available(tool): return tool
    raise CoverageRefused(
        "no coverage tool for language '%s' is available here; looked "
        "for %s" % (language, ", ".join("'%s'" % t
                                         for t in candidate_tuple)))
