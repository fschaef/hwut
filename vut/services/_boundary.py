"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BOUNDARY -- WHAT IS WRITTEN, AND WHERE IT MAY GO.

Every face of this framework works inside a TREE, and a tree is what
'hwut-root.conf' bounds. Without it there is no root to make a path
relative to, no place for 'hwut-root.labels', and no answer to 'which
directories are mine'. A face that proceeds without one is guessing,
so every face refuses -- and HINTS at the way out
('tree_explorer.ROOT_CONF_HINT_STR').

PLACING ONE IS 'hwut.sanitize's (services E-25, amended 2026-10-08):
'hwut.sanitize.propose' proposes 'root <directory>' and
'hwut.sanitize.apply' -- or 'hwut.sanitize root <directory>' -- writes
it. This module holds the TEXT that is written and the CANDIDATES;
the asking is the sanitize face's.

THE CANDIDATES (ruled 2026-10-08) are the REPOSITORY ROOTS at or above
the directory -- of the open-source version control tools, each by
the marker it leaves ('REPOSITORY_MARK_TUPLE') -- and THE CURRENT
DIRECTORY.
'hwut.sanitize root' with no directory puts them before a person as a
menu; 'hwut.sanitize.propose' writes them as commands.

WHAT IS WRITTEN IS NOT AN EMPTY BLOCK (E-25). The file carries the
whole 'language-setup' table: every language with its coverage
candidates in preference order, its 'extensions' -- every one owned
by a single entry -- its 'interpreter' where a launcher takes a source
file, and 'coverage_target = "%.cov.exe"' for the gcc family.
'hwut.config.show --root-conf-template' prints the same text.
______________________________________________________________________________
"""
import os

CANDIDATE_MAX_N = 8

#  THE MARKER OF A REPOSITORY'S ROOT, and the system's name. OPEN-SOURCE
#  TOOLS ONLY (ruled 2026-10-08), each known by a directory or file it
#  leaves at the root -- nothing is run to find one.
REPOSITORY_MARK_TUPLE = ((".git",      "git"),
                         (".hg",       "mercurial"),
                         (".svn",      "svn"),
                         (".jj",       "jujutsu"),
                         (".bzr",      "bazaar"),
                         ("_darcs",    "darcs"),
                         (".pijul",    "pijul"),
                         (".fslckout", "fossil"),
                         ("_FOSSIL_",  "fossil"))

ROOT_CONF_NAME = "hwut-root.conf"

#  WHAT IS WRITTEN (E-25): the boundary WITH the language table. Every
#  per-language default HWUT once carried in code -- the coverage
#  candidates of coverage D-2, the interpreters of the adapter -- stands
#  here, in the one file an author reads, and nowhere else (exploration
#  R-73, coverage D-26). This text is the ONE template; 'offered_text'
#  shows it, 'placed' writes it, byte for byte.
ROOT_CONF_TEXT = """\
#  SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#  --------------------------------------------------------------------------
#
#  THE ROOT OF THIS TREE, and the boundary of the climb.
#
#  Every face ASCENDS from where it is called, collecting each
#  'hwut.conf' it passes, until it reaches this file. What is collected
#  is then applied OUTERMOST FIRST -- this file first of all -- so the
#  innermost word wins and a test directory's own 'hwut.conf' has the
#  last word before the source headers.
#
#  It plays TWO ROLES: it is the MOST DOMINANT configuration there is,
#  and it STOPS the climb, so nothing above this project can reach into
#  it. An empty block is a complete statement -- it says only 'the tree
#  ends here', which is what this one says.
#
#  LOCAL KEYS ARE REFUSED HERE -- 'on_entry', 'on_exit', 'collision',
#  'dependency' and the directory's own targets name local matters and
#  belong in a test directory's own 'hwut.conf'.
#
#  'language-setup' STANDS HERE AND NOWHERE ELSE (exploration R-73): one
#  block per language, holding everything HWUT does WITH that language.
#  The block's NAME is the language; a source file's 'language' word
#  selects it by that name, and the name is free -- 'dep4711_c' is a
#  language. Where a header states no language, 'extensions' selects.
#
#      extensions       the file extensions that select this entry
#      interpreter      the call for an interpreted test; the entry's
#                       own name where unstated
#      coverage         the candidate coverage tools, PREFERENCE ORDER;
#                       the first one this machine has serves, and an
#                       EMPTY LIST IS AN ANSWER: nobody vouches for a tool
#      coverage_target  the coverage-capable build target of a compiled
#                       test; '%' is the source file's stem (R-74)
#
#  THE ORDER OF A 'coverage' LIST IS PART OF THE TABLE: a tool whose
#  format this build reads stands first, since election takes the first
#  candidate the machine HAS. A candidate with no reader is still worth
#  listing -- it is how a machine refuses BY NAME. 'hwut.cov.formats'
#  prints what this build reads.
#
#  WHAT IS LEFT OUT IS LEFT OUT ON PURPOSE. No 'interpreter' where a
#  language is compiled, or where no launcher takes a source file as
#  its first argument. Every extension is owned by ONE entry: '.m' is
#  objective-c's (a MATLAB or Octave file states 'language'), '.pl' is
#  perl's (Prolog has '.pro'), '.sh' is bash's ('shell' names 'sh' and
#  claims nothing). '.h' is not claimed: a header is not a test. A
#  language's name is a bare word, shell-safe: 'csharp', 'fsharp',
#  'vbdotnet'.
#  --------------------------------------------------------------------------
hwut {
    language-setup {
        c             { extensions      = [".c"]
                        coverage        = ["gcov", "llvm-cov", "kcov"]
                        coverage_target = "%.cov.exe" }
        c++           { extensions      = [".cpp", ".cc", ".cxx"]
                        coverage        = ["gcov", "llvm-cov", "kcov"]
                        coverage_target = "%.cov.exe" }
        objective-c   { extensions      = [".m"]
                        coverage        = ["gcov", "llvm-cov"]
                        coverage_target = "%.cov.exe" }
        objective-c++ { extensions      = [".mm"]
                        coverage        = ["gcov", "llvm-cov"]
                        coverage_target = "%.cov.exe" }
        fortran       { extensions      = [".f", ".for", ".f77", ".f90", ".f95", ".f03", ".f08"]
                        coverage        = ["gcov", "kcov"]
                        coverage_target = "%.cov.exe" }
        ada           { extensions      = [".adb", ".ads"]
                        coverage        = ["gcov", "gnatcoverage"]
                        coverage_target = "%.cov.exe" }
        modula-2      { extensions      = [".mod", ".def"]
                        coverage        = ["gcov"]
                        coverage_target = "%.cov.exe" }
        cobol         { extensions      = [".cob", ".cbl"]
                        coverage        = ["gcov"]
                        coverage_target = "%.cov.exe" }
        vala          { extensions      = [".vala"]
                        coverage        = ["gcov"]
                        coverage_target = "%.cov.exe" }
        nim           { extensions      = [".nim"]
                        interpreter     = "nim r"
                        coverage        = ["gcov", "lcov"] }
        assembly      { extensions      = [".s", ".asm"]
                        coverage        = ["kcov", "gcov"]
                        coverage_target = "%.cov.exe" }
        python        { extensions      = [".py", ".pyw"]
                        interpreter     = "python3"
                        coverage        = ["coverage", "slipcover", "trace"] }
        cython        { extensions      = [".pyx"]
                        coverage        = ["coverage"] }
        lua           { extensions      = [".lua"]
                        interpreter     = "luau"
                        coverage        = ["luacov"] }
        go            { extensions      = [".go"]
                        interpreter     = "go run"
                        coverage        = ["go", "gcov"] }
        rust          { extensions      = [".rs"]
                        coverage        = ["cargo-llvm-cov", "grcov", "llvm-cov", "kcov", "tarpaulin"] }
        swift         { extensions      = [".swift"]
                        interpreter     = "swift"
                        coverage        = ["llvm-cov", "xccov"] }
        d             { extensions      = [".d", ".di"]
                        interpreter     = "rdmd"
                        coverage        = ["dmd", "gcov", "llvm-cov"] }
        zig           { extensions      = [".zig"]
                        interpreter     = "zig run"
                        coverage        = ["kcov", "llvm-cov"] }
        crystal       { extensions      = [".cr"]
                        interpreter     = "crystal run"
                        coverage        = ["kcov"] }
        julia         { extensions      = [".jl"]
                        interpreter     = "julia"
                        coverage        = ["lcov", "julia"] }
        r             { extensions      = [".r", ".R"]
                        interpreter     = "Rscript"
                        coverage        = ["covr"] }
        haskell       { extensions      = [".hs", ".lhs"]
                        interpreter     = "runghc"
                        coverage        = ["hpc"] }
        erlang        { extensions      = [".erl", ".hrl"]
                        interpreter     = "escript"
                        coverage        = ["cover"] }
        elixir        { extensions      = [".ex", ".exs"]
                        interpreter     = "elixir"
                        coverage        = ["excoveralls", "cover"] }
        ocaml         { extensions      = [".ml", ".mli"]
                        interpreter     = "ocaml"
                        coverage        = ["bisect-ppx"] }
        clojure       { extensions      = [".clj", ".cljs", ".cljc"]
                        interpreter     = "clojure"
                        coverage        = ["cloverage"] }
        common-lisp   { extensions      = [".lisp", ".lsp"]
                        interpreter     = "sbcl --script"
                        coverage        = ["sb-cover"] }
        prolog        { extensions      = [".pro"]
                        interpreter     = "swipl"
                        coverage        = ["swipl"] }
        solidity      { extensions      = [".sol"]
                        coverage        = ["solidity-coverage"] }
        dart          { extensions      = [".dart"]
                        interpreter     = "dart"
                        coverage        = ["lcov", "dart"] }
        flutter       { coverage        = ["lcov", "flutter"] }
        java          { extensions      = [".java"]
                        interpreter     = "java"
                        coverage        = ["jacoco", "cobertura", "clover", "jcov"] }
        kotlin        { extensions      = [".kt", ".kts"]
                        interpreter     = "kotlinc -script"
                        coverage        = ["jacoco", "cobertura", "kover"] }
        scala         { extensions      = [".scala", ".sc"]
                        interpreter     = "scala"
                        coverage        = ["scoverage", "jacoco", "cobertura"] }
        groovy        { extensions      = [".groovy"]
                        interpreter     = "groovy"
                        coverage        = ["jacoco", "cobertura"] }
        javascript    { extensions      = [".js", ".mjs", ".cjs", ".jsx"]
                        interpreter     = "node"
                        coverage        = ["node", "c8", "lcov", "cobertura", "nyc", "istanbul"] }
        typescript    { extensions      = [".ts", ".tsx"]
                        interpreter     = "ts-node"
                        coverage        = ["node", "c8", "lcov", "cobertura", "nyc", "istanbul"] }
        ruby          { extensions      = [".rb"]
                        interpreter     = "ruby"
                        coverage        = ["cobertura", "simplecov"] }
        php           { extensions      = [".php"]
                        interpreter     = "php"
                        coverage        = ["cobertura", "phpunit", "xdebug", "pcov", "phpdbg"] }
        perl          { extensions      = [".pl", ".pm", ".t"]
                        interpreter     = "perl"
                        coverage        = ["cover", "Devel::Cover"] }
        shell         { interpreter     = "sh"
                        coverage        = ["kcov", "bashcov"] }
        bash          { extensions      = [".sh", ".bash"]
                        interpreter     = "bash"
                        coverage        = ["kcov", "bashcov"] }
        zsh           { extensions      = [".zsh"]
                        interpreter     = "zsh"
                        coverage        = [] }
        powershell    { extensions      = [".ps1"]
                        interpreter     = "pwsh"
                        coverage        = ["pester"] }
        tcl           { extensions      = [".tcl"]
                        interpreter     = "tclsh"
                        coverage        = [] }
        csharp        { extensions      = [".cs", ".csx"]
                        coverage        = ["coverlet", "cobertura", "dotcover", "opencover", "altcover"] }
        fsharp        { extensions      = [".fs", ".fsx"]
                        interpreter     = "dotnet fsi"
                        coverage        = ["coverlet", "cobertura", "altcover"] }
        vbdotnet      { extensions      = [".vb"]
                        coverage        = ["coverlet", "cobertura", "opencover"] }
        matlab        { coverage        = ["matlab"] }
        octave        { interpreter     = "octave"
                        coverage        = ["octave"] }
        verilog       { extensions      = [".v", ".vh"]
                        coverage        = ["verilator", "verilator_coverage", "vcover", "urg", "imc"] }
        systemverilog { extensions      = [".sv", ".svh"]
                        coverage        = ["verilator", "verilator_coverage", "vcover", "urg", "imc"] }
        vhdl          { extensions      = [".vhd", ".vhdl"]
                        coverage        = ["gcov", "ghdl", "vcover", "urg", "imc"] }
        pascal        { extensions      = [".pas", ".pp"]
                        coverage        = [] }
        delphi        { extensions      = [".dpr"]
                        coverage        = [] }
    }

    #  HOW DIFFERENCES ARE ALIGNED FOR DISPLAY (compare C-16). These shape
    #  what a diff SHOWS -- which line stands beside which -- and never a
    #  verdict. Every application of the tree receives them through
    #  'app_defaults'; a test directory's 'hwut.conf' may state its own.
    app_defaults {
        diff_display_parameters {
            search_budget = 20000   # expansions a section may search
            margin        = 0.1     # 'clearly the closest' by this much
            lowest_n      = 4       # else the n cheapest pairs anchor
            context_k     = 1       # lines either side in a pair's cost
        }
    }
}
"""


def _repository_of(path):
    """
    RETURN: str, the version control system whose repository ROOT 'path'
                 is -- 'git', 'mercurial', 'svn', ... as its marker
                 says
            None, where it is the root of none

    Subversion before 1.7 kept a '.svn' in EVERY directory: the root is
    the one whose parent holds none.
    """
    for mark, name in REPOSITORY_MARK_TUPLE:
        if not os.path.exists(os.path.join(path, mark)): continue
        if mark == ".svn" and os.path.exists(
               os.path.join(os.path.dirname(path), mark)): continue
        return name
    return None


def candidate_list(directory):
    """
    RETURN: list[(str, str)], (absolute directory, what it is) for every
            place a boundary is offered at, in the order offered: each
            REPOSITORY ROOT at or above 'directory', nearest first --
            'the git repository's root', ... -- and then 'the current
            directory', unless it is one of those already.

    THAT IS THE WHOLE LIST (ruled 2026-10-08): where a project is under
    version control its root is where a boundary belongs, and where it
    is not, the person stands where they mean. Any other directory is
    named in words: 'hwut.sanitize root <dir>'.

    THE CLIMB ENDS WHERE THE CONFIGURATION CLIMB ENDS (exploration
    R-76): a test directory's transient ground 'TEST/TMP' is not
    looked at, nor anything above it -- a fixture built there must not
    be handed the enclosing project as the place for its boundary.
    """
    from vut.engine.orchestrator.exploration.tree_explorer \
                                               import transient_ground_f
    start     = os.path.abspath(directory)
    found     = []
    here      = start
    while len(found) < CANDIDATE_MAX_N:
        name = _repository_of(here)
        if name is not None:
            found.append((here, "the %s repository's root" % name))
        parent = os.path.dirname(here)
        if parent == here or transient_ground_f(parent): break
        here = parent
    if start not in [path for path, _ in found]:
        found.append((start, "the current directory"))
    return found


def writeable_f(path):
    """
    RETURN: bool, True where the person running this may create a file
            in the directory.
    """
    return os.access(path, os.W_OK | os.X_OK)


def written(directory):
    """
    RETURN: str, the path of the 'hwut-root.conf' written into
                 'directory' -- the template, whole
            raises OSError, where the file cannot be written
    """
    path = os.path.join(directory, ROOT_CONF_NAME)
    with open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(ROOT_CONF_TEXT)
    return path
