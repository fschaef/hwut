"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DOOR from selection to the LOCAL OBSERVATION DATABASE
         (services E-22).

Selection asks two questions this machine alone can answer -- when did
this last run, and how long did it take -- and both are observations,
not decisions, so they are not in the book. This module is the only
place selection reaches for them, so the address is stated once.
______________________________________________________________________________
"""


def observation_of_case(bookkeeper, case, operation):
    """
    RETURN: Observation | None -- what this machine last observed of
            that case's 'operation'; None where it observed none.

    A local file that cannot be read answers None: an unreadable
    observation selects nothing, and must never refuse a whole run.
    """
    from ...bookkeeper.api import ObservationDb, ObservationFault
    directory = getattr(bookkeeper, "directory", None)
    #  A BOOK THAT NAMES NO DIRECTORY observed nothing: a stub in a
    #  test, or a reader over a base handed in whole.
    if directory is None: return None
    try:
        return ObservationDb(directory).get(
                   case.source_file, case.choice, operation)
    except (ObservationFault, OSError):
        return None
