"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.labels.create' COMMAND LINE -- a NEW label, from a
         wish (disc-8).

    hwut.labels.create <label> <wish> [--directory=<path>]

REFUSES A LABEL THAT ALREADY STANDS, naming 'hwut.labels.add' as the
verb for growing one. That refusal is the whole reason this is a
separate face: A TYPO IN A LABEL NAME MUST NOT SILENTLY GROW THE WRONG
SET.

    hwut.labels.create concern --fail

labels what is failing NOW. The set is a SNAPSHOT of what the wish
selected, and the report says so, RUN BY RUN: a person who globbed
must see what the pattern caught before it becomes a set.

REFUSES A WISH THAT STATES NOTHING. A bare wish wants everything, so
'create concern' would quietly enrol the whole tree. Naming a set is
the one act where 'everything' must be asked for in words:
'--label all'.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       the label is created and written
    1  FAULT    the tree cannot be fully read, or the labels file is
                broken, or cannot be written -- nothing is written
    2  REFUSED  the command line cannot be read; the label stands, or
                is reserved; the wish states nothing
    3  EMPTY    the wish selected nothing -- AND NO LABEL IS CREATED,
                because an empty set is not a set anybody wanted
______________________________________________________________________________
"""
import sys

from   vut.engine.orchestrator.exploration.task_list \
                                             import SelectionError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                             import RootConfMissing
from   vut.engine.orchestrator.plan.label    import reserved_reason
from   vut.engine.orchestrator.plan.wish     import (HELP as WISH_HELP,
                                                     USAGE_TOKEN_TUPLE,
                                                     WishError,
                                                     parse_wish)
from   .._core                               import usage_line
from   .._exit                               import E_ExitCode
from   .                                     import _file
from   ._faces                               import (selected_key_tuple,
                                                     split_directory)

USAGE = usage_line("hwut.labels.create",
                   ("<label>",) + USAGE_TOKEN_TUPLE
                   + ("[--directory=<path>]",))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    The set is written only where every door was passed: the wish
    reads, the label is new, the tree reads whole, and at least one
    run was selected.
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
        write("REFUSED: 'hwut.labels.create' takes ONE label, and "
              "%d stand%s: %s"
              % (len(rest_list), "s" if len(rest_list) == 1 else "",
                 ", ".join(rest_list) if rest_list else "none"))
        write(USAGE)
        return E_ExitCode.REFUSED
    label  = rest_list[0]
    reason = reserved_reason(label)
    if reason is not None:
        write("REFUSED: %s" % reason)
        return E_ExitCode.REFUSED
    if wish.states_nothing_f():
        write("REFUSED: the wish states nothing, and a wish stating "
              "nothing wants EVERYTHING; naming a set is the one act "
              "where everything must be asked for in words -- "
              "'--label all'")
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
    if any(label in label_set for label_set in entry_db.values()):
        write("REFUSED: the label '%s' already stands -- "
              "'hwut.labels.add' grows a standing set; this face "
              "only creates, so a typo cannot silently grow the "
              "wrong one" % label)
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
        write("EMPTY: the wish selected nothing; no label is created "
              "-- an empty set is not a set anybody wanted")
        return E_ExitCode.EMPTY

    for key in key_tuple:
        entry_db[key] = entry_db.get(key, frozenset()) | {label}
    try:
        _file.write_entry_db(boundary, entry_db)
    except OSError as error:
        write("FAULT: '%s' cannot be written -- %s"
              % (_file.file_path(boundary), error))
        return E_ExitCode.FAULT

    write("%s: created, %d member%s -- a snapshot of what the wish "
          "selected"
          % (label, len(key_tuple),
             "" if len(key_tuple) == 1 else "s"))
    for key in sorted(set(key_tuple), key=_file.sort_key):
        write("    + %s" % _file.target_text(key))
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
