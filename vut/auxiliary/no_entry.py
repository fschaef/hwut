"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHERE hwut DOES NOT ITERATE -- the one marker and the two
         directory names that say so, each defined ONCE, here.

DESCRIPTION
       A DIRECTORY IS NOT ENTERED by any walk of a tree -- exploration,
       'hwut.run', 'hwut.execute', the reports, sanitize -- where

           it carries the file  'hwut.no-entry-here.marker'
                                NO_ENTRY_MARKER_FILE; EMPTY: it says
                                nothing but 'do not iterate in here',
                                whoever placed it -- hwut in the output
                                of a coverage run, or a person
       or  it is the 'TMP' or 'OUT' of a test directory
                                TRANSIENT_DIRECTORY_NAME,
                                OUT_DIRECTORY_NAME: hwut's own two
                                grounds, standing beside 'GOOD'

           no_entry_f(path)         the question every walk asks
           marked_no_entry(path)    the marker placed
           entered(directory, name_list)
                                    the sub-directories a walk goes on
                                    into

       THE NAMES ARE REFERRED TO, NEVER RESPELT: every other module
       builds its paths from these constants ('TMP/store', 'TMP/lock',
       'TMP/session', 'OUT/<key>.err').

       'TMP' AND 'OUT' ARE KNOWN BY NAME, not by a marker inside them:
       they are made by many hands -- a run, an exploration's memo, a
       report's list -- and removed whole by 'hwut.sanitize'; beside a
       'GOOD' the name is hwut's own and needs no second witness.
______________________________________________________________________________
"""
import os

NO_ENTRY_MARKER_FILE     = "hwut.no-entry-here.marker"
TRANSIENT_DIRECTORY_NAME = "TMP"
OUT_DIRECTORY_NAME       = "OUT"

#  THE NOMINALS' DIRECTORY: what a 'TMP' or an 'OUT' stands beside.
NOMINAL_DIRECTORY_NAME   = "GOOD"

#  hwut's own two grounds in a test directory, in the order sanitize
#  names them (services E-24).
OWN_GROUND_NAME_TUPLE    = (OUT_DIRECTORY_NAME, TRANSIENT_DIRECTORY_NAME)


def own_ground_f(path, name_tuple=OWN_GROUND_NAME_TUPLE):
    """
    RETURN: True,  'path' is a test directory's own ground: named as one
                   of 'name_tuple' ('OUT', 'TMP') and standing beside a
                   'GOOD'
            False, else
    """
    return os.path.basename(path) in name_tuple \
           and os.path.isdir(os.path.join(os.path.dirname(path),
                                          NOMINAL_DIRECTORY_NAME))


def no_entry_f(path):
    """
    RETURN: True,  no walk enters the directory 'path': it carries
                   'hwut.no-entry-here.marker', or it is the 'TMP' or
                   'OUT' of a test directory
            False, else
    """
    return os.path.isfile(os.path.join(path, NO_ENTRY_MARKER_FILE)) \
           or own_ground_f(path)


def marked_no_entry(path):
    """
    RETURN: str, 'path' -- the directory now carrying the empty file
            'hwut.no-entry-here.marker'; a marker standing there is
            left as it is.

    Raises OSError where 'path' is no directory, or cannot be written.
    """
    marker = os.path.join(path, NO_ENTRY_MARKER_FILE)
    if not os.path.isfile(marker):
        with open(marker, "w", encoding="utf-8"): pass
    return path


def entered(directory, name_list):
    """RETURN: list of str, the names of 'name_list' -- sub-directories
    of 'directory' -- that a walk goes on into, sorted: those 'no_entry_f'
    does not close and whose name does not begin with '.'."""
    return sorted(name for name in name_list
                  if not name.startswith(".")
                  and not no_entry_f(os.path.join(directory, name)))


def below_no_entry_f(start, top_f):
    """
    RETURN: True,  'start' is a directory no walk enters, or stands
                   below one -- asked upward until 'top_f(directory)'
                   says the tree's top is reached
            False, else
    """
    here = os.path.abspath(start)
    while True:
        if no_entry_f(here): return True
        parent = os.path.dirname(here)
        if parent == here or top_f(here): return False
        here = parent
