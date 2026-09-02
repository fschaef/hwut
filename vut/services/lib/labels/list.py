"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.labels.list' COMMAND LINE -- every label that
         stands, with the number of its members beside it (disc-8).

    hwut.labels.list [--directory=<path>]

prints

    concern   14
    meta       7

THE NUMBER IS A COUNT, NEVER A HANDLE. Numbering for reference invites
'--label 3', and a number that shifts when a label is added is a
target that moves under the author.

A tree that labels nothing prints nothing at all -- not a note, not a
blank line; the status carries the news.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       at least one label stands, and it is printed
    1  FAULT    the labels file is broken; named, nothing printed
    2  REFUSED  the command line cannot be read
    3  EMPTY    no label stands -- the file is absent, and absent
                means: no label exists, which is not an error
______________________________________________________________________________
"""
import sys

from   vut.engine.orchestrator.exploration.tree_explorer \
                                             import RootConfMissing
from   ..._core                               import usage_line
from   ..._exit                               import E_ExitCode
from   .                                     import _file
from   ._faces                               import split_directory

USAGE = usage_line("hwut.labels.list", ("[--directory=<path>]",))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    directory, rest_list = split_directory(argv)
    if rest_list:
        write("REFUSED: 'hwut.labels.list' does not take: %s"
              % ", ".join(sorted(rest_list)))
        write(USAGE)
        return E_ExitCode.REFUSED

    try:
        boundary = _file.boundary_of(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    try:
        entry_db = _file.read_entry_db(boundary)
    except _file.LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT

    count_db = {}
    for label_set in entry_db.values():
        for label in label_set:
            count_db[label] = count_db.get(label, 0) + 1
    if not count_db:
        return E_ExitCode.EMPTY

    width = max(len(label) for label in count_db)
    for label in sorted(count_db):
        write("%-*s %4d" % (width, label, count_db[label]))
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
