"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report.wishlist' COMMAND LINE -- print, one per line, every
         test application and choice the given wish selects.

prints

    ./<path>/<test-app> [<choice>]

THE ROUND TRIP CLOSES. What this face PRINTS is what '--wishlist'
READS, so an author asks once, prunes and comments the file, and keeps
it as text:

    hwut.report.wishlist --fail > messaging.txt     ask
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
from   dataclasses import dataclass, field

from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.exploration          import selection
from   vut.services.lib.labels                           import view_at
from   vut.services.lib.labels._file                     import LabelFileError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                     import RootConfMissing
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish,
                                                             with_targets,
                                                             Wish)
from   vut.services._exit                            import E_ExitCode
from   vut.services._target                          import entered
from   vut.services.lib.cmdline                      import (face_parser, usage_of,
                                                             parse_or_refuse)
from   vut.services.lib.face                         import Refused, Fault, answered


#  THE STANDARD READER (E-84): the parser IS the vocabulary and the
#  usage line is generated from it.
PARSER = face_parser("hwut.report.wishlist",
                     "Print every case the wish selects as a wishlist "
                     "line, fit to redirect into a file.",
                     word_help="a test, a test and a choice, a file glob "
                               "and a choice glob",
                     word_metavar="[<file-glob> [choice-glob]...]")
PARSER.add_argument("--directory", default=None,
                    help="ONE test directory (default: the tree below "
                         "the cwd)")
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

#  The licence line and the rule are the FILE'S, not the face's.
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


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.report.wishlist' (E-101): the directory and the wish."""
    directory: str  = "."
    wish:      Wish = field(default_factory=Wish)


@dataclass(frozen=True)
class Result:
    """WHAT HAPPENED: the wishlist lines in walk order, and whatever the
    selection warned about."""
    line_tuple:    tuple = ()
    warning_tuple: tuple = ()


def request_of(wish, directory, word_list):
    """RETURN: Request, the record of a Wish and a directory."""
    return Request(
        directory = directory,
        wish      = with_targets(wish, list(word_list))
    )


def wish_of(request):
    """RETURN: Wish, the engine's, as 'request' states it."""
    return request.wish


def do(request):
    """
    RETURN: Result, the wishlist lines the request selects, in walk
            order, and the selection's warnings.

            An EMPTY selection is a Result with no line and whatever
            the selection warned: the caller decides what that means.

    RAISES: Refused, where the directory does not stand, no root conf
            is above it, or the wish names what the tree does not hold;
            Fault, where a label file cannot be read.

    IT NEVER PRINTS (E-101).
    """
    directory = request.directory or "."
    if not os.path.isdir(directory):
        raise Refused("REFUSED: the directory '%s' does not exist" % directory)
    warning_list = []
    try:
        line_list = list(line_tuple_of(os.path.abspath(directory),
                                       wish_of(request), warning_list))
    except (RootConfMissing, SelectionError) as error:
        raise Refused("REFUSED: %s" % error) from error
    except LabelFileError as error:
        raise Fault("FAULT: %s" % error) from error
    #  AN EMPTY SELECTION STILL WARNED: the warning says WHY nothing
    #  stands ('the glob met only runs the standard label silences'),
    #  so it is the answer, not a casualty of it. MEASURED: raising
    #  Empty before it was written lost that line from the page.
    return Result(line_tuple=tuple(line_list),
                  warning_tuple=tuple(warning_list))


def printed(result, write):
    """RETURN: E_ExitCode, OK where a line stands, EMPTY else. The
               warnings, then the lines -- the page 'hwut.report.wishlist' has
               always written."""
    for text in result.warning_tuple: write(text)
    for line in result.line_tuple:    write(line)
    return E_ExitCode.OK if result.line_tuple else E_ExitCode.EMPTY


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

    arguments, completion_f = parse_or_refuse(
        PARSER, rest_list, lambda text: write(text), ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    directory = arguments.directory or "."
    word_list = arguments.word
    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    return answered(do, request_of(wish, directory, word_list), write,
                    printed)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from   vut.services._exit import guarded
    sys.exit(guarded("hwut.report.wishlist", main))

