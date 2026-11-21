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
       or  it is named 'HWUT_ROOT'
                                RECORD_DIRECTORY_NAME: a tree's root
                                files (E-235)

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


#  THE ROOT OF A TREE (2026-11-21, services E-235): ONE directory,
#  'HWUT_ROOT', holding everything tree-wide -- the person's 'setup.conf'
#  and the framework's records. A project begins where a directory holds
#  'HWUT_ROOT/setup.conf' (RQ-1): THE FILE marks it, not the directory, so
#  an empty 'HWUT_ROOT/' left behind cuts no tree. No walk enters a
#  directory named 'HWUT_ROOT', wherever it stands. Every name below is
#  '/'-separated and relative to the directory holding 'HWUT_ROOT' -- what
#  a message prints, and what 'os.path.join(root, ...)' opens on every
#  platform. Capitals and the underscore: no clash with a 'hwut/' beside
#  it on a file system blind to case.
RECORD_DIRECTORY_NAME = "HWUT_ROOT"
ROOT_CONF_NAME        = RECORD_DIRECTORY_NAME + "/setup.conf"
LABELS_FILE_NAME      = RECORD_DIRECTORY_NAME + "/labels.txt"
ROSTER_FILE_NAME      = RECORD_DIRECTORY_NAME + "/directories.txt"
FOREST_FILE_NAME      = RECORD_DIRECTORY_NAME + "/feature-forest.csv"
DOC_FILE_NAME         = RECORD_DIRECTORY_NAME + "/feature-doc.txt"
EXTERNAL_FILE_NAME    = RECORD_DIRECTORY_NAME + "/feature-external-map.csv"
TOOLS_FILE_NAME       = RECORD_DIRECTORY_NAME + "/tools.rst"

#  THE OLD PLACES (E-234 CR-4, E-235): the flat files of before. A face
#  that finds one refuses by name; 'hwut.renovate' moves it.
OLD_ROOT_CONF_NAME = "hwut-root.conf"
OLD_PLACE_DB = {
    OLD_ROOT_CONF_NAME:              ROOT_CONF_NAME,
    "hwut-root.labels":              LABELS_FILE_NAME,
    "hwut-feature-forest.csv":       FOREST_FILE_NAME,
    "hwut-feature-doc.dat":          DOC_FILE_NAME,
    "hwut-feature-external-map.csv": EXTERNAL_FILE_NAME,
    "hwut-tools.rst":                TOOLS_FILE_NAME,
}


def root_conf_path_f(path):
    """
    RETURN: bool, True where 'path' names a root's setup file -- its last
            two parts are 'HWUT_ROOT' and 'setup.conf' (E-235); a file name
            alone no longer tells.
    """
    parts = os.path.normpath(path).replace(os.sep, "/").split("/")
    return parts[-2:] == ROOT_CONF_NAME.split("/")


def record_directory_f(path):
    """
    RETURN: True,  'path' is named 'HWUT_ROOT' -- a tree's root files, which
                   no walk enters, wherever it stands
            False, else
    """
    return os.path.basename(os.path.normpath(path)) == RECORD_DIRECTORY_NAME


def made_record_directory(root):
    """
    RETURN: str, the absolute 'HWUT_ROOT/' of the tree rooted at 'root', made
            where it did not stand. Raises OSError where it cannot be.
    """
    path = os.path.join(os.path.abspath(root), RECORD_DIRECTORY_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def old_place_refusal_list(root):
    """
    RETURN: list of str, one refusal per framework file that still stands
            at its OLD place in 'root' (E-235): a flat file beside where
            'HWUT_ROOT/' stands or would stand,
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
    RETURN: bool, True where the directory 'path' holds a
            'HWUT_ROOT/setup.conf' of its own -- a project a walk from above
            does not enter (RQ-1).
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
