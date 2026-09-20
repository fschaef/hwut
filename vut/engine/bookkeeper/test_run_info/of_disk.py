"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: BUILD A LIVE ENTRY FROM WHAT STANDS ON DISK -- the one place
         that reads both witnesses, so that no caller ever again asks
         one of the three questions and calls the answer a standing
         (B-15).

'of_case' is what every gate, face and walk should call. It opens the
nominals only as far as it must: the mark and the terminal token are
peeked on fresh readers, exactly as 'operations/consume' peeked them
at compare time, and the readers are consumed and closed.
______________________________________________________________________________
"""
import os

from   .info import CTestRunInfo, of_row


TERMINAL_TOKEN   = "<hwut-end>"
UNACCEPTED_OPENER = "##!"


def carries_unaccepted_f(path):
    """
    RETURN: bool, whether the file opens an 'unaccepted' region
            anywhere -- a line '##! unaccepted', optionally followed by
            parameters (compare C-9). False where it cannot be read:
            an unreadable nominal is sanitize's finding, not a state.

    The name is read as a scanner reads a shebang: the first word
    after '##!', case as written.
    """
    try:
        with open(path, "r", errors="replace") as reader:
            for line in reader:
                stripped = line.strip()
                if not stripped.startswith(UNACCEPTED_OPENER): continue
                word_list = stripped[len(UNACCEPTED_OPENER):].split()
                if word_list and word_list[0] == "unaccepted": return True
    except OSError:
        return False
    return False


def ends_in_terminal_f(path):
    """
    RETURN: bool, whether the file's last NON-EMPTY line is the
            terminal token -- trailing blank lines carry no
            information and are forgiven (R-70). False where it cannot
            be read.
    """
    last = None
    try:
        with open(path, "r", errors="replace") as reader:
            for line in reader:
                stripped = line.rstrip("\r\n")
                if stripped: last = stripped
    except OSError:
        return False
    return last == TERMINAL_TOKEN


def of_case(directory, test, choice=None, bookkeeper=None):
    """
    RETURN: CTestRunInfo, the case as it stands in 'directory': the
            member state from THE FILES, every other field from the
            book's row where a bookkeeper is given.

    THE ONE DOOR. A caller that wants to know whether a case may be
    run asks '.is_runnable()' of what this answers; it does not ask
    whether a nominal stands and decide for itself.
    """
    #  Imported here: 'bookkeeper.py' imports this module's package,
    #  and the top-level import would close the circle.
    from ..bookkeeper import nominal_path_list

    path_list = nominal_path_list(directory, test, choice)
    mark_f    = any(carries_unaccepted_f(path) for path in path_list)
    row_db = None
    if bookkeeper is not None:
        row_db = bookkeeper.result(test, choice)
    return of_row(test, choice, row_db, bool(path_list), mark_f)


__all__ = ["of_case", "carries_unaccepted_f", "ends_in_terminal_f",
           "CTestRunInfo"]
