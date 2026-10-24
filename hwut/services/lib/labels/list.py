"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
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

DERIVED LABELS (D-56), where the file's '[derived]' section holds any,
follow under 'DERIVED': the expression beside each, the count of the
file's targets that carry it, and the names the expression mentions
that nothing assigns or derives -- 'missing in expression evaluation'.
The count is over the targets the file names; a run the file names
nowhere carries no label and is not counted.

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

from   hwut.engine.orchestrator.exploration.tree_explorer \
                                             import RootConfMissing
from   ..._core                               import usage_line
from   ..._exit                               import E_ExitCode
from   .                                     import _file
from   .                                     import _faces
from   ._faces                               import split_directory

USAGE = usage_line("usage: hwut.labels.list", ("[--directory=<path>]",))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from ..._core import man_page
        write(man_page("hwut.labels.list", HELP))
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

    standing     = _faces.standing_of(entry_db)
    derived_list = _file.derivation_tuple(boundary, entry_db)
    if not standing.row_tuple and not derived_list:
        return E_ExitCode.EMPTY
    if standing.row_tuple: printed(standing, write)
    if derived_list:       derived_printed(derived_list, write)
    return E_ExitCode.OK


def printed(standing, write):
    """RETURN: None. The page 'hwut.labels.list' has always written:
               one label per line, its members counted, the names
               padded to the longest."""
    width = max(len(label) for label, _ in standing.row_tuple)
    for label, member_n in standing.row_tuple:
        write("%-*s %4d" % (width, label, member_n))


def derived_printed(derived_list, write):
    """RETURN: None. The derived labels (D-56), below the assigned ones:
               one per line, the expression beside it, the count of the
               file's targets that carry it at the end, and under it the
               names its expression mentions that nothing assigns or
               derives."""
    write("")
    write("DERIVED")
    width   = max(len(label) for label, _, _, _ in derived_list)
    e_width = max(len(text) for _, text, _, _ in derived_list)
    for label, text, member_n, missing in derived_list:
        write("    %-*s = %-*s %4d" % (width, label, e_width, text, member_n))
        if missing:
            write("    %*s   missing in expression evaluation: %s"
                  % (width, "", ", ".join(missing)))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.labels.list", main))
