"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BOUNDARY, OR AN OFFER TO PLACE ONE.

Every face of this framework works inside a TREE, and a tree is what
'hwut-root.conf' bounds. Without it there is no root to make a path
relative to, no place for 'hwut-root.labels', and no answer to 'which
directories are mine'. A face that proceeds without one is guessing.

WHAT A MISSING BOUNDARY USED TO GET: a refusal naming the file. True,
and useless to somebody who has just arrived in a tree they did not
build -- they now know a file is missing and not WHERE IT GOES.

WHAT IT GETS NOW: the refusal, the reason, and AN OFFER. The
candidates are the directory and its parents, up to the home
directory or the file system's root, LETTERED:

    no 'hwut-root.conf' stands in or above 'engine/compare/TEST'.
    A tree needs a boundary: it is the root every path is relative
    to, and the place 'hwut-root.labels' and the register stand.

    Where shall it go?
        A   engine/compare/TEST
        B   engine/compare
        C   engine
        D   .                        <- usually this one
        anything else  --  nothing is written

    choice:

THE LETTERS ADAPT. Eight is the ceiling, not the shape: a directory
three deep offers three. THE COUNT IS WHAT STANDS, never padded to a
number.

ANY OTHER KEY ABORTS, and abort means NOTHING IS WRITTEN. A person who
typed by accident, or who meant a directory not on the list, must be
able to leave without having changed the tree -- and a bare RETURN is
the commonest accident there is.

NOT ASKED WHERE NOBODY CAN ANSWER. Where the input is not a terminal
-- a script, a pipe, a suite -- the offer is not made: a question
nobody can hear is a hang, not a courtesy. The face refuses as before
and says what would have been offered.

WHAT IS WRITTEN IS NOT AN EMPTY BLOCK (E-25). The file carries the
whole 'language-setup' table: every language with its coverage
candidates in preference order, its 'extensions' -- every one owned
by a single entry -- its 'interpreter' where a launcher takes a source file, and
'coverage_target = "%.cov.exe"' for the gcc family. A root conf placed
by hand, or
before this, carries no table and runs only what a she-bang can run;
'hwut.config.show --root-conf-template' prints the template for pasting.
______________________________________________________________________________
"""
import os
import sys

LETTER_TUPLE = ("A", "B", "C", "D", "E", "F", "G", "H")

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
#  listing -- it is how a machine refuses BY NAME. 'hwut.cov formats'
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
}
"""


def candidate_tuple(directory):
    """
    RETURN: tuple[str], the directories a boundary could be placed in
            -- this one and its parents, NEAREST FIRST, stopping at
            the home directory or the file system's root, and at
            'LETTER_TUPLE' many.

    EVERY DIRECTORY OF THE CLIMB IS OFFERED, '/' and '/tmp' included:
    what is unusual is not what is forbidden, and a person who means
    to root a tree at '/tmp' knows better than this code does.

    A DIRECTORY THE PERSON CANNOT WRITE IS STILL OFFERED, and SAID TO
    BE UNWRITEABLE. Leaving it out would make the letters skip, and a
    person counting down the list would wonder what they had missed;
    naming the reason answers that before it is asked.

    THE CLIMB STOPS AT A PROJECT'S TOP where it meets one -- a
    directory holding '.git', 'setup.py', 'pyproject.toml' or
    'Makefile'. That is where a boundary usually belongs, and past it
    lies somebody else's tree.
    """
    TOP_MARK = (".git", "setup.py", "pyproject.toml", "Makefile")
    here     = os.path.abspath(directory)
    found    = []
    while len(found) < len(LETTER_TUPLE):
        found.append(here)
        if any(os.path.exists(os.path.join(here, mark))
               for mark in TOP_MARK):     break
        parent = os.path.dirname(here)
        if parent == here:                break
        here = parent
    return tuple(found)


def writeable_f(path):
    """
    RETURN: bool, True where the person running this may create a file
            in the directory.
    """
    return os.access(path, os.W_OK | os.X_OK)


def shown(path, start):
    """
    RETURN: str, the candidate as a person reads it: relative to
            'start' where that is shorter, '.' for 'start' itself, the
            absolute path where relative would climb further than it
            explains.
    """
    relative = os.path.relpath(path, os.path.abspath(start))
    if relative == ".":                    return "."
    if not relative.startswith(".."):      return relative
    #  A CLIMB READS BADLY as '../../..': the absolute path says more,
    #  and a person choosing a directory must SEE which one.
    return path


def _top_f(path):
    """
    RETURN: bool, True where the directory looks like a project's top
            -- it holds '.git', 'setup.py', 'pyproject.toml' or
            'Makefile'. That is where a boundary usually belongs, and
            saying so saves a person from counting letters.
    """
    return any(os.path.exists(os.path.join(path, mark))
               for mark in (".git", "setup.py", "pyproject.toml",
                            "Makefile"))


def offer_text_tuple(directory):
    """
    RETURN: tuple[str], the lines of the offer -- the problem, the
            reason, and the lettered candidates.

    THE REASON IS GIVEN, not merely the fact: a person who has just
    arrived needs to know what a boundary IS before choosing where to
    put one.
    """
    candidate = candidate_tuple(directory)
    line_list = [
        "REFUSED: no '%s' stands in or above '%s'."
        % (ROOT_CONF_NAME, shown(os.path.abspath(directory), ".")),
        "    A tree needs a boundary: it is the root every path is",
        "    relative to, and the place 'hwut-root.labels' and the",
        "    register stand.",
        ""]
    line_list.append("Where shall it go?")
    for letter, path in zip(LETTER_TUPLE, candidate):
        if not writeable_f(path):
            mark = "   (no write access by user)"
        elif _top_f(path):
            mark = "   <- the project's top"
        else:
            mark = ""
        line_list.append("    %s   %-28s%s"
                         % (letter, shown(path, directory), mark))
    line_list.append("    anything else  --  nothing is written")
    return tuple(line_list)


def placed(directory, write, ask=None):
    """
    RETURN: str, the directory a boundary was written into.
            None where none was -- because nobody could be asked,
            because the answer named no candidate, or because the
            write failed. THE REASON IS ALREADY WRITTEN.

    'ask' takes a prompt and answers a line; 'input' where None, and
    NOT CALLED AT ALL where the input is no terminal.

    NOTHING IS WRITTEN ON ANY ANSWER BUT A LETTER THAT STANDS. A bare
    RETURN is the commonest accident there is, and it must leave the
    tree as it was.
    """
    for text in offer_text_tuple(directory): write(text)

    if ask is None:
        if not sys.stdin.isatty():
            #  A QUESTION NOBODY CAN HEAR IS A HANG, not a courtesy.
            write("")
            write("    (no terminal: nothing is written. Place the "
                  "file yourself,")
            write("     or run this again where a person can answer.)")
            return None
        ask = input

    try:    answer = ask("choice: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        write("")
        return None

    candidate = candidate_tuple(directory)
    if len(answer) != 1 or answer not in LETTER_TUPLE[:len(candidate)]:
        write("nothing written.")
        return None

    where = candidate[LETTER_TUPLE.index(answer)]
    if not writeable_f(where):
        #  THE OFFER SAID SO, and the person chose it anyway. Refuse
        #  by name rather than letting the write fail with an errno.
        write("REFUSED: '%s' cannot be written in -- the offer said "
              "so, and nothing is written." % shown(where, directory))
        return None
    path  = os.path.join(where, ROOT_CONF_NAME)
    try:
        with open(path, "w", encoding="utf-8") as file_handle:
            file_handle.write(ROOT_CONF_TEXT)
    except OSError as error:
        write("FAULT: '%s' cannot be written -- %s" % (path, error))
        return None
    write("written: %s" % path)
    return where
