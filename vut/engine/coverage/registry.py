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
       (RATIONALE D-2). 'hwut.conf' carries a dict whose KEY is a GLOB
       over the LANGUAGE and whose VALUE is an ORDERED LIST OF CANDIDATE
       TOOLS. The first candidate actually available on this machine
       serves.

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
from fnmatch import fnmatch

from .configuration import CoverageRefused


#  THE DEFAULT DICT. 'hwut.conf' overrides it, inherited global to
#  specific; the search for a global conf runs UPWARD, nearest enclosing
#  first. Order inside a list is PREFERENCE, not equivalence.
DEFAULT_TOOL_DB = {
    #  ORDERED BY PREFERENCE, AND THE ORDER IS NOT ARBITRARY: a tool
    #  whose FORMAT this build reads stands FIRST. 'elect' takes the
    #  first candidate the machine HAS, so a table that put an unreadable
    #  tool in front would refuse on a machine that could have been
    #  served. Marked [r] below: read today.
    #
    #  A candidate with no reader is NOT a mistake -- it is how a machine
    #  refuses BY NAME ("no reader for 'simplecov'; this build reads ...")
    #  rather than reporting no coverage at all.

    # -- the gcc family: one flag, one format, many languages -----------
    "c":              ("gcov", "llvm-cov", "kcov"),          # [r][r][r]
    "c++":            ("gcov", "llvm-cov", "kcov"),          # [r][r][r]
    "objective-c":    ("gcov", "llvm-cov"),                  # [r][r]
    "objective-c++":  ("gcov", "llvm-cov"),                  # [r][r]
    "fortran*":       ("gcov", "kcov"),                      # gfortran
    "ada":            ("gcov", "gnatcoverage"),              # gnatcov: own
    "modula-2":       ("gcov",),                             # gm2
    "cobol":          ("gcov",),                             # gcobol
    "vala":           ("gcov",),                             # compiles to C
    "nim":            ("gcov", "lcov"),                      # C backend
    "assembly":       ("kcov", "gcov"),

    # -- languages with a first-class tool of their own -----------------
    "python*":        ("coverage", "slipcover", "trace"),    # [r]
    "cython":         ("coverage",),                         # [r]
    "lua*":           ("luacov",),                          # [r]
    "go":             ("go", "gcov"),                        # [r][r]
    "rust":           ("cargo-llvm-cov", "grcov", "llvm-cov",
                       "kcov", "tarpaulin"),                 # [r][r][r][r]
    "swift":          ("llvm-cov", "xccov"),                 # [r]
    "d":              ("dmd", "gcov", "llvm-cov"),           # dmd: own .lst
    "zig":            ("kcov", "llvm-cov"),                  # [r][r]
    "crystal":        ("kcov",),                             # [r]
    "julia":          ("lcov", "julia"),      # [r] via Coverage.jl export
    "r":              ("covr",),
    "haskell":        ("hpc",),
    "erlang":         ("cover",),
    "elixir":         ("excoveralls", "cover"),
    "ocaml":          ("bisect-ppx",),
    "clojure":        ("cloverage",),
    "common-lisp":    ("sb-cover",),
    "prolog":         ("swipl",),
    "solidity":       ("solidity-coverage",),
    "dart":           ("lcov", "dart"),       # [r] via format_coverage
    "flutter":        ("lcov", "flutter"),    # [r] same road

    # -- the JVM: one binary artifact, several report shapes ------------
    "java":           ("jacoco", "cobertura", "clover",
                       "jcov"),                                # [r][r]
    "kotlin":         ("jacoco", "cobertura", "kover"),            # [r][r]
    "scala":          ("scoverage", "jacoco", "cobertura"),        # [r][r][r]
    "groovy":         ("jacoco", "cobertura"),                     # [r][r]

    # -- the scripting side ---------------------------------------------
    "javascript":     ("lcov", "cobertura", "c8", "nyc",
                       "istanbul"),                                # [r][r]
    "typescript":     ("lcov", "cobertura", "c8", "nyc",
                       "istanbul"),                                # [r][r]
    "ruby":           ("cobertura", "simplecov"),                  # [r]
    "php":            ("cobertura", "phpunit", "xdebug", "pcov",
                       "phpdbg"),                                  # [r]
    "perl":           ("cover", "Devel::Cover"),
    "shell":          ("kcov", "bashcov"),                   # [r]
    "bash":           ("kcov", "bashcov"),                   # [r]
    "zsh":            ("kcov",),                             # [r]
    "powershell":     ("pester",),
    "tcl":            (),      # no candidate this author can vouch for;
                               # an EMPTY list refuses by name, which is
                               # the honest answer to 'we do not know'

    # -- .NET -----------------------------------------------------------
    "c#":             ("coverlet", "cobertura", "dotcover",
                       "opencover", "altcover"),                   # [r][r]
    "f#":             ("coverlet", "cobertura", "altcover"),       # [r][r]
    "vb.net":         ("coverlet", "cobertura", "opencover"),      # [r][r]

    # -- numerical / engineering ----------------------------------------
    "matlab":         ("matlab",),
    "octave":         ("octave",),

    # -- hardware description: SEE DISCUSSIONS disc-9 --------------------
    #  Line coverage of an HDL source is read today where the tool emits
    #  a tracefile. The OTHER coverages a simulator produces -- toggle,
    #  FSM, condition, and FUNCTIONAL (covergroups, bins, assertions) --
    #  have NO LINE NUMBERS and this record cannot hold them. A reader
    #  that dropped them silently would report a design '92% covered'
    #  while discarding the coverage the verification engineer came for.
    "verilog":        ("verilator_coverage", "vcover", "urg", "imc"),  # [r]
    "systemverilog":  ("verilator_coverage", "vcover", "urg", "imc"),  # [r]
    "vhdl":           ("gcov", "vcover", "urg", "imc"),      # [r] ghdl

    # -- and the ones this author will not guess at ----------------------
    #  Pascal: Free Pascal has no first-class story to rely on, and the
    #  Delphi side (DelphiCodeCoverage) emits EMMA XML and possibly LCOV
    #  -- 'possibly' is not good enough to ship. Establish it against a
    #  REAL artifact first (DISCUSSIONS todo-2).
    "pascal":         (),
    "delphi":         (),
}


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
    ".cs":     "c#",
    ".fs":     "f#",       ".fsx":  "f#",
    ".vb":     "vb.net",
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


def candidate_tuple_of(language, tool_db=None):
    """
    RETURN: tuple of str, the candidate tools of 'language', in
            PREFERENCE order -- the first entry whose GLOB matches.

    Raises CoverageRefused where no glob matches, naming the language and
    the globs that were offered.
    """
    db = DEFAULT_TOOL_DB if tool_db is None else tool_db
    for pattern in sorted(db, key=lambda p: (-len(p), p)):
        if fnmatch(language, pattern):
            return tuple(db[pattern])
    raise CoverageRefused(
        "no coverage tool is configured for language '%s'; the "
        "configured globs are %s"
        % (language, ", ".join("'%s'" % p for p in sorted(db))))


def is_available(tool):
    """
    RETURN: True,  'tool' can be launched on this machine.
            False, else.

    Asked of the system, never inferred -- the same discipline the
    procsitter applies to a cap it cannot enforce.
    """
    return shutil.which(tool) is not None


def elect(language, tool_db=None, available=is_available):
    """
    RETURN: str, the FIRST candidate of 'language' that this machine
            actually has.

    Raises CoverageRefused where every candidate is absent, NAMING each
    one -- so the reader of the refusal knows what to install rather than
    what went wrong.

    'available' is a parameter so that a test may state the machine.
    """
    candidate_tuple = candidate_tuple_of(language, tool_db)
    if not candidate_tuple:
        raise CoverageRefused(
            "the candidate list for language '%s' is EMPTY: this build "
            "vouches for no coverage tool there. State one in "
            "'hwut.conf' -- inventing a default would be worse than "
            "saying so." % language)
    for tool in candidate_tuple:
        if available(tool): return tool
    raise CoverageRefused(
        "no coverage tool for language '%s' is available here; looked "
        "for %s" % (language, ", ".join("'%s'" % t
                                        for t in candidate_tuple)))
