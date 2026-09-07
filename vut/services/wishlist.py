"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.wishlist' COMMAND LINE -- print, one per line, every
         test application and choice the given wish selects.

prints

    ./<path>/<test-app> [<choice>]

THE ROUND TRIP CLOSES. What this face PRINTS is what '--wishlist'
READS, so an author asks once, prunes and comments the file, and keeps
it as text:

    hwut.wishlist --fail > messaging.txt     ask
    $EDITOR messaging.txt                    prune, comment
    hwut.run --wishlist messaging.txt        spend

'messaging.txt' then names a suite BY INTENT, not by pattern -- 'the
tests that quick-check the messaging framework' -- which is a thing a
person maintains and a glob is not.

THE LEADING './' IS THE LIST'S OWN GROUND. A wishlist read back
resolves './' against the DIRECTORY OF THE WISHLIST FILE, so a list
beside the tree it describes travels with it. This face prints from
the run's root, so a list saved at the root reads back unchanged, and
a list saved elsewhere is relative to where it sits.

WHAT IS PRINTED IS A TARGET, not a report: no verdict, no time, no
count. A comment an author adds is theirs; this face adds none, so
that its output may be redirected into a file without editing.

A CHOICE-LESS TEST prints its file alone -- which, read back, means
every choice of it, as a bare target always has (R-34).

EXIT STATUS (E-1, services/_exit.py):
    0  the wish selected at least one case, and they are printed
    2  the command line cannot be read
    3  the command line reads, and selects nothing
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.exploration          import selection
from   vut.services.lib.labels                           import view_at
from   vut.services.lib.labels._file                     import LabelFileError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                     import (RootConfMissing)
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish,
                                                             with_targets)
from   ._core                                        import usage_line
from   ._exit                                        import E_ExitCode
from   ._target                                      import entered

USAGE = usage_line("usage: hwut.wishlist",
                   ("[<wish>]", "[<file-glob> [choice-glob]...]",
                    "[--directory=<path>]"))

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


def target_line(relative_directory, source_file, choice):
    """
    RETURN: str, the case written as a wishlist line --
            './<path>/<file>' or './<path>/<file> <choice>'.

    The leading './' is not decoration: it is what marks the path as
    the LIST'S OWN, so that reading the file back resolves it against
    the file's directory rather than the reader's.
    """
    where = relative_directory.replace(os.sep, "/").strip("/")
    if where in ("", "."): path = "./%s" % source_file
    else:                  path = "./%s/%s" % (where, source_file)
    return path if choice is None else "%s %s" % (path, choice)


def line_tuple_of(root, wish, warning_list=None):
    """
    YIELD: [0] str  one wishlist line per selected case, in WALK ORDER
                    -- the order a run would take them, so a list read
                    top to bottom reads as the run reads.

    Raises SelectionError where the wish names what the tree does not
    hold -- refused at the door, as everywhere.
    """
    if warning_list is None: warning_list = []
    found = selection.of_tree(root, wish, view_at(root))
    warning_list.extend(found.warning_tuple)
    for entry in found.case_list:
        #  THE WALK'S 'directory' IS RELATIVE to the root -- the very
        #  form a wishlist line carries.
        yield target_line(entry.directory, entry.case.source_file,
                          entry.case.choice)


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where at least one
            case was selected and printed, REFUSED where the command
            line cannot be read, EMPTY where it reads and selects
            nothing.

    An EMPTY selection prints nothing at all -- not a note, not a
    blank line. The status carries the news, and the output stays fit
    to redirect into a file.
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

    directory = "."
    unknown   = []
    word_list = []
    for argument in rest_list:
        if argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        else:
            if argument.startswith("-"): unknown.append(argument)
            else:                        word_list.append(argument)
    if unknown:
        write("REFUSED: 'hwut.wishlist' does not take: %s"
              % ", ".join(sorted(unknown)))
        write(USAGE)
        return E_ExitCode.REFUSED
    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    try:
        wish = with_targets(wish, word_list)
        warning_list = []
        line_list = list(line_tuple_of(os.path.abspath(directory), wish,
                                       warning_list))
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT

    for text in warning_list: write(text)
    for line in line_list: write(line)
    return E_ExitCode.OK if line_list else E_ExitCode.EMPTY


if __name__ == "__main__":
    sys.exit(main())
