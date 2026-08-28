"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.labels.add' COMMAND LINE -- grow a STANDING label
         by what a wish selects (disc-8).

    hwut.labels.add <label> <wish> [--directory=<path>]

DOES NOT CREATE a label that does not stand: it refuses, and names
'hwut.labels.create'. Same argument that separated the two faces --
'add cocnern --wishlist list.txt' would otherwise make a set nobody
asked for, silently. The STANDARD label 'meta' always stands and
needs no create.

THE EXPANSION IS REPORTED RUN BY RUN: '+' enrolled, '=' already
carrying. A glob is SPENT here, at write time, never stored -- a test
added later does not join the set, and running 'add' again is how it
catches up.

REFUSES A WISH THAT STATES NOTHING, as 'create' does: growing a set by
'everything' must be asked for in words -- '--label all'.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       written (or nothing to write: every run already there)
    1  FAULT    the tree cannot be fully read, or the labels file is
                broken, or cannot be written -- nothing is written
    2  REFUSED  the command line cannot be read; the label does not
                stand, or is no label
    3  EMPTY    the wish selected nothing; nothing is written
______________________________________________________________________________
"""
import sys

from   vut.engine.orchestrator.exploration.task_list \
                                             import SelectionError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                             import RootConfMissing
from   vut.engine.orchestrator.plan.label    import (STANDARD_LABEL,
                                                     reserved_reason)
from   vut.engine.orchestrator.plan.wish     import (HELP as WISH_HELP,
                                                     USAGE_TOKEN_TUPLE,
                                                     WishError,
                                                     parse_wish)
from   .._core                               import usage_line
from   .._exit                               import E_ExitCode
from   .                                     import _file
from   ._faces                               import (selected_key_tuple,
                                                     split_directory)

USAGE = usage_line("hwut.labels.add",
                   ("<label>",) + USAGE_TOKEN_TUPLE
                   + ("[--directory=<path>]",))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    A run already carrying the label is a no-op, reported '=': adding
    what is there is not a fault, and the report says which half of
    the selection was news.
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
        write("REFUSED: 'hwut.labels.add' takes ONE label, and "
              "%d stand%s: %s"
              % (len(rest_list), "s" if len(rest_list) == 1 else "",
                 ", ".join(rest_list) if rest_list else "none"))
        write(USAGE)
        return E_ExitCode.REFUSED
    label  = rest_list[0]
    reason = reserved_reason(label)
    if reason is not None and label != STANDARD_LABEL:
        write("REFUSED: %s" % reason)
        return E_ExitCode.REFUSED
    if wish.states_nothing_f():
        write("REFUSED: the wish states nothing, and a wish stating "
              "nothing wants EVERYTHING; growing a set by everything "
              "must be asked for in words -- '--label all'")
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
    if label != STANDARD_LABEL \
       and not any(label in label_set
                   for label_set in entry_db.values()):
        write("REFUSED: no label '%s' stands -- 'hwut.labels.create' "
              "makes a new one; this face only grows, so a typo "
              "cannot silently make a set nobody asked for" % label)
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

    added_list   = []
    already_list = []
    for key in sorted(set(key_tuple), key=_file.sort_key):
        if label in entry_db.get(key, frozenset()):
            already_list.append(key)
        else:
            added_list.append(key)
            entry_db[key] = entry_db.get(key, frozenset()) | {label}
    if added_list:
        try:
            _file.write_entry_db(boundary, entry_db)
        except OSError as error:
            write("FAULT: '%s' cannot be written -- %s"
                  % (_file.file_path(boundary), error))
            return E_ExitCode.FAULT

    write("%s: %d added, %d already carrying"
          % (label, len(added_list), len(already_list)))
    for key in added_list:   write("    + %s" % _file.target_text(key))
    for key in already_list: write("    = %s" % _file.target_text(key))
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
