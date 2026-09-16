#! /usr/bin/env python3
#
# @hwut {
#     title      = "'did you mean' -- the one suggester (E-73)"
#     choices    = ["case", "completion", "faces", "listed", "parser",
#                   "phantom", "prefix", "threshold"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE SUGGESTER ITSELF (services E-73). Nine faces shape their refusals
with 'services/lib/cmdline.py'; until now it was exercised only through
those refusals. Here each of its rules is asked directly.

    threshold   1 edit up to four characters, 2 up to eight, 3 beyond --
                each length asked AT its limit and ONE PAST it.
    prefix      a prefix matches at any distance, both ways round;
                nearest first, ties in the caller's order, at most
                three.
    case        dashes and case are ignored for the comparison and kept
                for the answer; '=value' is cut off; the word itself is
                never suggested back.
    listed      where the refusal already prints the list, one name
                earns no suggestion and two do; nothing near says
                nothing.
    phantom     'option_tuple' takes a word only where a dash BEGINS it
                -- '<test-glob>' contributes nothing.
    faces       the vocabulary each face offers, read off its PARSER
                through the completion table it prints (E-84).
    parser      the argparse road (E-81): the suggestion against the
                parser's own options, against an option's WORDS where
                'arg_db' lists them, no abbreviation, a refusal that
                never exits the process.
    completion  the table '--intern-cmd-get-completion-info' prints.
______________________________________________________________________________
"""
import sys
import importlib

from   config import HwutRunner                                  # noqa F401,E402
from   vut.services.lib.cmdline import (did_you_mean,            # noqa: E402
                                        nearest_tuple,
                                        option_tuple,
                                        option_tuple_of_parser,
                                        did_you_mean_of_parser,
                                        completion_table,
                                        parse_or_refuse)

FACE_TUPLE = ("accept", "plan", "play", "rename", "report", "run",
              "sanitize", "stability", "wishlist")
#  The wish words each wish-taking face also accepts are the wish's,
#  and are not in its own table: 'parse_wish' reads them first.


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def ask(word, candidate_sequence, among_listed_f=False):
    """RETURN: None. One question to the suggester, and its answer, on
               one line -- '(nothing)' where the answer is empty."""
    answer = did_you_mean(word, candidate_sequence,
                          among_listed_f=among_listed_f)
    print("    %-16s -> %s" % (word, answer.strip() or "(nothing)"))


def test_threshold():
    """RETURN: None. Each length band, at its limit and one past it."""
    banner("up to 4 characters: 1 edit")
    ask("--abxd", ["--abcd"])            # 1 edit, length 4
    ask("--axyd", ["--abcd"])            # 2 edits, length 4
    banner("up to 8 characters: 2 edits")
    ask("--abcdxy", ["--abcdef"])        # 2 edits, length 6
    ask("--abcxyz", ["--abcdef"])        # 3 edits, length 6
    ask("--abcdefxy", ["--abcdefgh"])    # 2 edits, length 8
    banner("longer: 3 edits")
    ask("--abcdefxyz", ["--abcdefghi"])  # 3 edits, length 9
    ask("--abcdewxyz", ["--abcdefghi"])  # 4 edits, length 9
    banner("the band is the TYPED word's, not the candidate's")
    ask("--ayz", ["--abcyz"])            # 2 edits; typed length 3: no
    ask("--abcyz", ["--ayz"])            # 2 edits; typed length 5: yes


def test_prefix():
    """RETURN: None. Prefixes, ordering and the limit."""
    option_list = ["--dont-ask", "--directory", "--dir", "--force",
                   "--faster-than", "--format", "--fail"]
    banner("a prefix, far away by distance")
    ask("--dont", option_list)
    banner("the typed word runs PAST a candidate")
    ask("--forcefully", option_list)
    banner("several prefixes: at most three, in the caller's order")
    ask("--f", option_list)
    print("    %-16s -> %s" % ("(limit 10)",
          ", ".join(nearest_tuple("--f", option_list, limit_n=10))))
    banner("nearest first: a prefix (0) before a slip (1)")
    ask("--fai", ["--fax", "--failure"])


def test_case():
    """RETURN: None. What is ignored, what is kept."""
    option_list = ["--force", "--width", "--plain"]
    banner("case: the capital letter is the whole problem")
    ask("--Force", option_list)
    ask("--PLAIN", option_list)
    banner("dashes: one, two, none")
    ask("-plain", option_list)
    ask("plian", option_list)
    banner("'=value' is not part of the word")
    ask("--WIDTH=70", option_list)
    ask("--widht=70", option_list)
    banner("the exact word is never suggested back")
    ask("--force", option_list)


def test_listed():
    """RETURN: None. The suggestion must earn its place."""
    banner("the refusal prints the list: one name")
    ask("test-hare.sh", ["test-here.sh"], among_listed_f=True)
    banner("the refusal prints the list: two names")
    ask("test-hare.sh", ["test-here.sh", "test-there.sh"],
        among_listed_f=True)
    banner("the list is NOT printed: one name is worth naming")
    ask("test-hare.sh", ["test-here.sh"])
    banner("nothing near: nothing said")
    ask("--quux", ["--force", "--width"])
    ask("",       ["--force"])
    ask("--",     ["--force"])


def test_phantom():
    """RETURN: None. Only a word a dash BEGINS is an option."""
    for text in ("usage: hwut.x <test-glob> [--dry-run]",
                 "usage: hwut.x [-v|--verbose] (--a,--b)",
                 "usage: hwut.x --width=<n> --out <file> non-option",
                 "usage: hwut.x --force ... --force again",
                 "usage: hwut.x -- -1 --9lives",
                 ""):
        print("    %-52r %s" % (text, list(option_tuple(text))))


def parser_of(prog):
    """RETURN: (ArgumentParser, dict), a parser shaped like a face's,
               and its 'arg_db'."""
    import argparse
    parser = argparse.ArgumentParser(prog=prog, allow_abbrev=False)
    parser.add_argument("word", nargs="*")
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--directory", default=None)
    parser.add_argument("--format", choices=["a", "b"])
    parser.add_argument("--editor", default=None)
    return parser, {"--directory": True, "--editor": True,
                    "--format": ("traditional", "junit")}


def test_parser():
    """RETURN: None. The argparse road, case by case."""
    parser, arg_db = parser_of("hwut.x")
    banner("the options, off the parser")
    print("    %s" % " ".join(option_tuple_of_parser(parser)))
    banner("a slip in an option")
    for word in ("--plian", "--forc", "-F", "--widht=3"):
        print("    %-14s -> %s" % (word, did_you_mean_of_parser(
            word, parser, arg_db).strip() or "(nothing)"))
    banner("a slip in a WORD the option takes")
    for word in ("--format=junti", "--format=x", "--editor=vim"):
        print("    %-14s -> %s" % (word, did_you_mean_of_parser(
            word, parser, arg_db).strip() or "(nothing)"))
    banner("parse_or_refuse: refused on 'err', never an exit")
    err_list = []
    for argv in (["a", "--plian"], ["--forc"], ["--width", "x"],
                 ["--plain", "a", "b"]):
        arguments, completion_f = parse_or_refuse(parser, argv,
                                                  err_list.append, arg_db)
        print("    %-22s -> %s" % (" ".join(argv),
              "refused" if arguments is None else
              "ok: plain=%s word=%s" % (arguments.plain, arguments.word)))
    for line in err_list: print("       %s" % line)


def test_completion():
    """RETURN: None. The table, and the option that asks for it."""
    parser, arg_db = parser_of("hwut.x")
    for line in completion_table(parser, arg_db):
        print("    %s" % line.replace("\t", "  |  "))
    banner("asked on the line: printed, parsed nothing")
    import io, contextlib
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        arguments, completion_f = parse_or_refuse(
            parser, ["--intern-cmd-get-completion-info"], print, arg_db)
    print("    arguments=%s completion_f=%s lines=%d"
          % (arguments, completion_f, len(out.getvalue().splitlines())))


def test_faces():
    """RETURN: None. Every face's vocabulary, read off its PARSER (E-84):
               the completion table each prints, one row per face."""
    import subprocess, sys
    for module in ["vut.services.%s" % name for name in FACE_TUPLE] \
                  + ["vut.services.diff",
                     "vut.services.lib.accept.interactive"]:
        run = subprocess.run([sys.executable, "-m", module,
                              "--intern-cmd-get-completion-info"],
                             capture_output=True, text=True)
        row_list = [line.split("\t") for line in run.stdout.splitlines()]
        print("    %-38s exit %i  %2d  %s"
              % (module, run.returncode, len(row_list),
                 " ".join(r[0] + ("" if r[1] == "flag" else "=<%s>" % r[1])
                          for r in row_list)))


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "'did you mean' -- the one suggester (E-73)",
        choice_map = {
            "case":       test_case,
            "completion": test_completion,
            "parser":     test_parser,
            "faces":      test_faces,
            "listed":    test_listed,
            "phantom":   test_phantom,
            "prefix":    test_prefix,
            "threshold": test_threshold,
        }).run()
