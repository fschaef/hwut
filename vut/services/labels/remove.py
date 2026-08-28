"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.labels.remove' COMMAND LINE -- take a label off
         what a wish selects (disc-8).

    hwut.labels.remove <label> <wish> [--directory=<path>]

A run that did not carry the label is NOT an error and is reported
untouched ('='): removing what is not there is a no-op, not a fault.

A LABEL LEFT WITH NO MEMBERS IS DELETED, and the report says so -- an
empty set is indistinguishable from an absent one, and keeping it
would only mislead 'hwut.labels.list'. A labels file left with no
entries is removed whole: absent and empty mean the same, and only
one spelling can be canonical.

REFUSES A WISH THAT STATES NOTHING: taking a label off EVERYTHING --
deleting the set -- must be asked for in words: '--label <label>'.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       written (or nothing to write: no selected run carried
                the label)
    1  FAULT    the tree cannot be fully read, or the labels file is
                broken, or cannot be written -- nothing is written
    2  REFUSED  the command line cannot be read; the label does not
                stand
    3  EMPTY    the wish selected nothing; nothing is written
______________________________________________________________________________
"""
import sys

from   vut.engine.orchestrator.exploration.task_list \
                                             import SelectionError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                             import RootConfMissing
from   vut.engine.orchestrator.plan.wish     import (HELP as WISH_HELP,
                                                     USAGE_TOKEN_TUPLE,
                                                     WishError,
                                                     parse_wish)
from   .._core                               import usage_line
from   .._exit                               import E_ExitCode
from   .                                     import _file
from   ._faces                               import (selected_key_tuple,
                                                     split_directory)

USAGE = usage_line("hwut.labels.remove",
                   ("<label>",) + USAGE_TOKEN_TUPLE
                   + ("[--directory=<path>]",))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    The report states both halves: '-' the runs the label came off,
    '=' the selected runs it never stood on.
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
    directory, rest_list = split_directory(rest_list)

    if len(rest_list) != 1:
        write("REFUSED: 'hwut.labels.remove' takes ONE label, and "
              "%d stand%s: %s"
              % (len(rest_list), "s" if len(rest_list) == 1 else "",
                 ", ".join(rest_list) if rest_list else "none"))
        write(USAGE)
        return E_ExitCode.REFUSED
    label = rest_list[0]
    if wish.states_nothing_f():
        write("REFUSED: the wish states nothing, and a wish stating "
              "nothing wants EVERYTHING; taking a label off "
              "everything -- deleting the set -- must be asked for "
              "in words: '--label %s'" % label)
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
    if not any(label in label_set for label_set in entry_db.values()):
        write("REFUSED: no label '%s' stands in 'hwut-root.labels'"
              % label)
        return E_ExitCode.REFUSED

    view = _file.view_of(boundary, entry_db)
    try:
        key_tuple, warning_tuple, fault_tuple = \
            selected_key_tuple(directory, wish, view)
    except (SelectionError, RootConfMissing) as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    for warning in warning_tuple: write(warning)
    if fault_tuple:
        for fault in fault_tuple: write("FAULT: %s" % fault)
        write("nothing written: a tree that cannot be fully read "
              "cannot say what it offers")
        return E_ExitCode.FAULT
    if not key_tuple:
        write("EMPTY: the wish selected nothing; nothing is written")
        return E_ExitCode.EMPTY

    removed_list   = []
    untouched_list = []
    for key in sorted(set(key_tuple), key=_file.sort_key):
        label_set = entry_db.get(key, frozenset())
        if label not in label_set:
            untouched_list.append(key)
            continue
        removed_list.append(key)
        label_set = label_set - {label}
        if label_set: entry_db[key] = label_set
        else:         del entry_db[key]
    if removed_list:
        try:
            _file.write_entry_db(boundary, entry_db)
        except OSError as error:
            write("FAULT: '%s' cannot be written -- %s"
                  % (_file.file_path(boundary), error))
            return E_ExitCode.FAULT

    write("%s: %d removed, %d untouched"
          % (label, len(removed_list), len(untouched_list)))
    for key in removed_list:
        write("    - %s" % _file.target_text(key))
    for key in untouched_list:
        write("    = %s" % _file.target_text(key))
    if removed_list \
       and not any(label in label_set
                   for label_set in entry_db.values()):
        write("%s: no member left -- the label is deleted" % label)
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
