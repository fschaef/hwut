"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.help' COMMAND LINE -- what failed below here for a
         reason that is not a plain deviation from GOOD, and how each
         such failure is resolved (display D-34).

    hwut.help [--directory=<path>] [<wish>]

DESCRIPTION
       READS THE BOOKS, as 'hwut.report' does: the last results of every
       case the wish selects below '--directory' (the current one where
       none is given). Runs nothing.

       ONCE PER FAILURE, UNDER ITS CATEGORY -- the headings the run's
       HINTS block carries (display D-35). Every failure that occurred is
       explained once: its word before '[FAIL]' and its phrase, how many
       cases it struck, then

           WHAT      what the failure means
           HEAL      how a person resolves it
           SANITIZE  how 'hwut.sanitize' heals it, where a command does
           EXAMPLE   one of the cases that failed so

       A plain difference from GOOD is the ordinary business of a test
       and is not explained here; neither is a case the book never saw.

       The explanations stand in ONE table, 'engine/display/failure.py'.

EXIT STATUS (E-1, services/_exit.py):
    0  something was explained
    3  nothing to explain: no selected case failed for a subtle reason
    2  the command line cannot be read
______________________________________________________________________________
"""
import os
import sys
import textwrap

from   vut.engine.orchestrator.plan.wish import (HELP as WISH_HELP,
                                                 WishError, parse_wish,
                                                 with_targets)
from   vut.engine.display.failure       import (failure_db, failure_of,
                                                subtle_f, category_of,
                                                E_FailureCategory,
                                                CATEGORY_HEADING_DB)
from   vut.services.lib.cmdline         import (face_parser, usage_of,
                                                parse_or_refuse)
from   vut.services.lib.face            import FaceError
from   ._exit                           import E_ExitCode
from   ._target                         import entered
from   .report                          import do, request_of

WRAP_WIDTH = 62          # the text column, after the four-blank indent
                         # and the ten-column label: 76 in all

PARSER = face_parser("hwut.help", "Explain the subtle failures of the "
                                  "last results.",
                     word_help="a test, a test and a choice, a file glob "
                               "and a choice glob",
                     word_metavar="[<file-glob> [choice-glob]...]")
PARSER.add_argument("--directory", default=None)
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


def token_of(row):
    """
    RETURN: str, the failure token a failing book row stands for: the
                 stain's 'unstable' first, 'unaccepted' for an aspirant,
                 the recorded report else.
            None, where the row stood, or the book never saw the case.
    """
    if row.stain_repeat_n is not None: return "unstable"
    if row.verdict_name is None or row.passed_f:  return None
    if row.verdict_name == "aspirant":            return "unaccepted"
    return row.report or None


def occurrence_db_of(block_list):
    """
    RETURN: dict, failure token -> list of (directory, case name), every
            subtle failure among the blocks' rows, in the order met.
    """
    occurrence_db = {}
    for block in block_list:
        for row in block.row_tuple:
            token = token_of(row)
            if not subtle_f(token): continue
            name = row.source_file if row.choice is None \
                   else "%s %s" % (row.source_file, row.choice)
            occurrence_db.setdefault(token, []).append(
                (block.directory, name))
    return occurrence_db


def explanation_line_list(token, case_list):
    """
    RETURN: list of str, the paragraph explaining one failure: its word
            and phrase, how many cases, then the explanation naming the
            first case as the example.
    """
    failure = failure_of(token)
    first_directory, first_name = case_list[0]
    example = "%s  %s" % (first_directory or ".", first_name)
    if failure is None:
        head = "failed -- '%s'" % token
        body = "WHAT      A reason this table does not know.\n" \
               "HEAL      Read the HINTS of 'hwut.run' for the case.\n" \
               "EXAMPLE   %s" % example
    else:
        head = "%s -- %s" % (failure.comment_before_FAIL_str,
                             failure.description)
        body = failure.explanation_f(example)
    line_list = ["%s  [%i case(s)]" % (head, len(case_list))]
    #  WRAPPED UNDER THE TEXT, the label standing alone in its column.
    for line in body.splitlines():
        label, _, text = line.partition("  ")
        wrapped = textwrap.wrap(text.strip(), width=WRAP_WIDTH,
                                break_on_hyphens=False) or [""]
        line_list.append("    %-9s %s" % (label, wrapped[0]))
        line_list.extend("    %-9s %s" % ("", more) for more in wrapped[1:])
    return line_list


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, OK where something was explained, EMPTY where no
            selected case failed for a subtle reason, REFUSED where the
            command line cannot be read.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK
    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED
    arguments, completion_f = parse_or_refuse(PARSER, rest_list, write,
                                              ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    found = entered(arguments.word, arguments.directory or ".", write,
                    USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    block_list = []
    try:
        do(request_of(with_targets(wish, word_list), directory),
           block_list.append)
    except FaceError as error:
        write(error.said)
        return error.code
    occurrence_db = occurrence_db_of(block_list)
    if not occurrence_db:
        write("nothing to explain: no case below '%s' failed for a "
              "reason other than a plain difference from GOOD" % directory)
        return E_ExitCode.EMPTY
    #  UNDER ITS CATEGORY'S HEADING (D-35), as HINTS does, and within it
    #  by the table's order, so the page is the same whatever the walk
    #  met first; a token the table does not carry comes last.
    rank_db = {member.value: i for i, member in enumerate(failure_db)}
    first_f = True
    for category in E_FailureCategory:
        token_list = sorted((t for t in occurrence_db
                             if category_of(t) is category),
                            key=lambda t: (rank_db.get(t, len(rank_db)), t))
        if not token_list: continue
        if not first_f: write("")
        first_f = False
        write(CATEGORY_HEADING_DB[category])
        for token in token_list:
            write("")
            for line in explanation_line_list(token, occurrence_db[token]):
                write("    " + line)
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.help", main))
