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

from   vut.engine.orchestrator.plan.label    import (STANDARD_LABEL,
                                                     reserved_reason)
from   vut.engine.orchestrator.plan.wish     import (HELP as WISH_HELP,
                                                     USAGE_TOKEN_TUPLE)
from   ..._core                               import usage_line
from   ..._exit                               import E_ExitCode
from   .                                     import _file
from   .                                    import _editing
from   ._faces                               import Refused, opened

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
    try:
        write, wish, directory, rest_list = opened(argv, write, HELP, USAGE)
    except Refused as refusal:
        return refusal.exit_code

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

    #  ONE ACTION, ONE PLACE ('_editing.py').
    open_labels = _editing.opened(directory, write)
    if open_labels.status is not None: return open_labels.status

    if label != STANDARD_LABEL \
       and not _editing.stands_f(open_labels, label):
        write("REFUSED: no label '%s' stands -- 'hwut.labels.create' "
              "makes a new one; this face only grows, so a typo "
              "cannot silently make a set nobody asked for" % label)
        return E_ExitCode.REFUSED

    key_tuple = _editing.selected(open_labels, directory, wish, write)
    if key_tuple is None: return open_labels.status
    if not key_tuple:
        write("EMPTY: the wish selected nothing; nothing is written")
        return E_ExitCode.EMPTY

    added_list   = []
    already_list = []
    for key in sorted(set(key_tuple), key=_file.sort_key):
        if label in open_labels.entry_db.get(key, frozenset()):
            already_list.append(key)
        else:
            added_list.append(key)
            open_labels.entry_db[key] = \
                open_labels.entry_db.get(key, frozenset()) | {label}
    if added_list and not _editing.written(open_labels, write):
        return open_labels.status

    write("%s: %d added, %d already carrying"
          % (label, len(added_list), len(already_list)))
    for key in added_list:   write("    + %s" % _file.target_text(key))
    for key in already_list: write("    = %s" % _file.target_text(key))
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.labels.add", main))
