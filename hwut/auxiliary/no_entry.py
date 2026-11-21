"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
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
       or  it is the 'HWUT' beside 'hwut-root.conf'
                                RECORD_DIRECTORY_NAME: the tree's own
                                files (CR-1)

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
           or own_ground_f(path) or record_directory_f(path)


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


#  WHERE A PROJECT OF ITS OWN BEGINS (RQ-1): a directory holding this file.
ROOT_CONF_NAME = "hwut-root.conf"

#  THE FRAMEWORK'S FILES OF A TREE (CR-1, 2026-11-20): one visible
#  directory beside 'hwut-root.conf', capitals like 'TEST', 'GOOD', 'TMP'
#  and 'OUT'; every file in it named without a 'hwut-' prefix and with an
#  extension an editor opens. 'hwut-root.conf' stays outside: it is the
#  person's file and the marker the root search climbs to. Every name is
#  '/'-separated and relative to the root -- what a message prints, and
#  what 'os.path.join(root, ...)' opens on every platform.
RECORD_DIRECTORY_NAME = "HWUT"
LABELS_FILE_NAME      = RECORD_DIRECTORY_NAME + "/labels.txt"
ROSTER_FILE_NAME      = RECORD_DIRECTORY_NAME + "/directories.txt"
FOREST_FILE_NAME      = RECORD_DIRECTORY_NAME + "/feature-forest.csv"
DOC_FILE_NAME         = RECORD_DIRECTORY_NAME + "/feature-doc.txt"
EXTERNAL_FILE_NAME    = RECORD_DIRECTORY_NAME + "/feature-external-map.csv"
TOOLS_FILE_NAME       = RECORD_DIRECTORY_NAME + "/tools.rst"

#  THE OLD PLACES (CR-4): beside 'hwut-root.conf', before CR-1. A face that
#  finds one refuses by name; 'hwut.renovate' moves it.
OLD_PLACE_DB = {
    "hwut-root.labels":              LABELS_FILE_NAME,
    "hwut-feature-forest.csv":       FOREST_FILE_NAME,
    "hwut-feature-doc.dat":          DOC_FILE_NAME,
    "hwut-feature-external-map.csv": EXTERNAL_FILE_NAME,
    "hwut-tools.rst":                TOOLS_FILE_NAME,
}


def record_directory_f(path):
    """
    RETURN: True,  'path' is a tree's 'HWUT/' -- named so and standing
                   beside a 'hwut-root.conf'
            False, else
    """
    return os.path.basename(path) == RECORD_DIRECTORY_NAME \
           and os.path.isfile(os.path.join(os.path.dirname(path),
                                           ROOT_CONF_NAME))


def made_record_directory(root):
    """
    RETURN: str, the absolute 'HWUT/' of the tree rooted at 'root', made
            where it did not stand. Raises OSError where it cannot be.
    """
    path = os.path.join(os.path.abspath(root), RECORD_DIRECTORY_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def old_place_refusal_list(root):
    """
    RETURN: list of str, one refusal per framework file that still stands
            at its OLD place beside 'hwut-root.conf' in 'root' (CR-4),
            naming it and the remedy -- or two copies, where the new one
            stands as well. Empty where none does.
    """
    result = []
    for old, new in sorted(OLD_PLACE_DB.items()):
        if not os.path.isfile(os.path.join(root, old)): continue
        if os.path.isfile(os.path.join(root, new)):
            result.append("'%s' and '%s' both stand -- two copies of one "
                          "file; keep one" % (old, new))
        else:
            result.append("'%s' is the old place of '%s' => hwut.renovate"
                          % (old, new))
    return result


def inner_root_f(path):
    """
    RETURN: bool, True where the directory 'path' holds a 'hwut-root.conf'
            of its own -- a project a walk from above does not enter (RQ-1).
    """
    return os.path.isfile(os.path.join(path, ROOT_CONF_NAME))


def entered(directory, name_list, boundary_f=True):
    """RETURN: list of str, the names of 'name_list' -- sub-directories
    of 'directory' -- that a walk goes on into, sorted: those 'no_entry_f'
    does not close, whose name does not begin with '.', and -- where
    'boundary_f' holds -- a walk that maintains a root's own files, or
    a wish saying '--no-bubbles' -- that start no bubble of their own
    (RQ-1, RQ-9)."""
    return sorted(name for name in name_list
                  if not name.startswith(".")
                  and not no_entry_f(os.path.join(directory, name))
                  and not (boundary_f
                           and inner_root_f(os.path.join(directory, name))))


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
