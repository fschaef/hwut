"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Find what a TEST directory offers: 'hwut.conf', if present, and
         the source file candidates -- the directory's files minus what is
         ignored.

Ignored by default: '*.txt', '*.xml', '*.json', '*.pype', and THE
FRAMEWORK'S OWN FILES -- 'hwut.conf', 'HWUT_ROOT/setup.conf', 'hwut-info.dat',
'hwut-traces.csv', 'HWUT_ROOT/labels.txt' (README section 0). The directory's own 'ignore'
globs add to these. The walk is one directory deep: a TEST directory
stands alone, and so does its file list.

A CONFIGURATION FILE IS NOT A SOURCE FILE. Offered as a candidate it is
read by the HEADER reader, whose vocabulary is a different one -- and
the complaint that comes back ("'title' is required and absent") is
nonsense twice over: 'title' belongs to a test application, and the file
was never a test application to begin with. The exclusion is by NAME and
not by glob: these are the framework's own file names, not a pattern an
author may widen or narrow.

A COPY OF A SOURCE FILE IS NOT A SOURCE FILE (E-41). 'test-x.py.backup',
'test-x.py~', 'test-x.py.orig' carry the header they were copied with,
and would read as a test application. These names are WALLFLOWERS
(R-103, 2026-11-22; ignored 2026-10-17, refused by name before): named
by the run, their header never read, until 'ignore' in 'hwut.conf'
silences them. The shapes are the editors' and the tools'
('BACKUP_NAME_GLOB_TUPLE'); 'admit' takes a glob out of them -- a
backup-shaped name meant as a test stands as one again.
______________________________________________________________________________
"""
import os

from fnmatch import fnmatch

CONF_NAME          = "hwut.conf"
from hwut.auxiliary.no_entry import ROOT_CONF_NAME       # noqa: E402  (E-235)

#  THE FRAMEWORK'S OWN FILES: never source file candidates. The book
#  and the traces stand in every TEST directory (X-INTERVIEW): they were
#  MEASURED interviewed on every walk, two programs run per directory
#  to answer nothing.
#  THE FEATURE FILES (spec 43), in the 'HWUT_ROOT/' that begins
#  the features of a tree: the forest, the explanation, the map to the
#  outside's names. The files of the past -- a TEST directory's feature
#  file, the central registry, the map of published ids -- are read by
#  nothing; they stay framework files, never source file candidates.
from hwut.auxiliary.no_entry import (FOREST_FILE_NAME,      # noqa: E402,F401
                                     DOC_FILE_NAME,
                                     EXTERNAL_FILE_NAME)


def refuse_old_place(top, old, fault_class):
    """
    RETURN: None. Raises 'fault_class' with the refusal where the file
            'old' still stands at its OLD place in 'HWUT_ROOT/' in
            'top' (CR-4): 'hwut.renovate' moves it into 'HWUT_ROOT/'.
    """
    from hwut.auxiliary.no_entry import old_place_refusal_list
    for text in old_place_refusal_list(top):
        if text.startswith("'%s'" % old): raise fault_class("REFUSED: " + text)


PAST_FILE_TUPLE       = ("hwut-features.conf", "hwut-feature-map.conf",
                         "hwut-root-features.conf")

OWN_FILE_TUPLE     = (CONF_NAME, ROOT_CONF_NAME, "hwut-root.conf",
                      "hwut-info.dat",
                      "hwut-traces.csv", "hwut-root.labels",
                      FOREST_FILE_NAME, DOC_FILE_NAME,
                      EXTERNAL_FILE_NAME) + PAST_FILE_TUPLE
#  NOTHING IS IGNORED BY DEFAULT (ruled 2026-11-22, exploration R-102,
#  superseding the silent set '*.txt *.xml *.json *.pype *.pypes'): a file
#  in a test directory is a test, ignored by the author's 'ignore', or a
#  WALLFLOWER the run names. "No reason to distinguish between ignored
#  and helper and forgotten": a data file, a pype and a test whose header
#  was forgotten are all a file nobody spoke for, and a silent default
#  hid the third behind the first two. A test that WAS recorded and lost
#  its header is the book's to say ('in book, no such test').
DEFAULT_IGNORE_SET = ()

#  BACKUP-SHAPED NAMES ARE WALLFLOWERS (ruled 2026-11-22, R-103,
#  superseding their silent ignoring of 2026-10-17): "backup files are
#  wallflowers until they are ignored". Not ignored -- the run names them
#  -- and NOT READ for a header either: a copy carries the header it was
#  copied with and would stand as a second test (measured: 'test-x.sh~'
#  beside 'test-x.sh' ran as a test, 'no GOOD file'). 'ignore' silences
#  them; 'admit', or an entry under 'apps', makes one a candidate again.
BACKUP_NAME_GLOB_TUPLE = ("*~", "#*#", "*.bak", "*.backup", "*.orig",
                          "*.old", "*.save", "*.rej", "*.copy", "*.swp",
                          "*.tmp")


def backup_shaped_f(directory, name, admit=()):
    """
    RETURN: bool, True where 'name' is backup-shaped
            ('BACKUP_NAME_GLOB_TUPLE') and no 'admit' glob takes it out --
            a wallflower whose header is not read (R-103).
            False, else.
    """
    return any(fnmatch(name, glob) for glob in BACKUP_NAME_GLOB_TUPLE) \
           and not any(glob_matches_f(directory, name, glob) for glob in admit)


def anchored_glob(glob, base):
    """
    RETURN: str, the 'ignore'/'admit' glob 'glob' as the walk matches it
            (R-103, like '.gitignore', inherited): a glob WITHOUT '/'
            unchanged -- a NAME, matched in every test directory below
            the configuration that states it; a glob WITH '/' anchored at
            'base', the directory that configuration speaks for -- an
            absolute, '/'-separated pattern matched against a file's
            whole path. A leading '/' only anchors ('/x.log': 'x.log'
            beside that configuration).
    """
    if "/" not in glob: return glob
    whole = os.path.join(os.path.abspath(base), glob.lstrip("/"))
    return os.path.normpath(whole).replace(os.sep, "/")


def glob_matches_f(directory, name, glob):
    """
    RETURN: bool, True where the file 'name' in 'directory' matches
            'glob' -- by its name where 'glob' is a name, by its whole
            path where 'glob' was anchored ('anchored_glob').
    """
    if "/" not in glob: return fnmatch(name, glob)
    whole = os.path.abspath(os.path.join(directory, name))
    return fnmatch(whole.replace(os.sep, "/"), glob)


def conf_text(directory):
    """
    RETURN: str,  the content of the directory's 'hwut.conf'.
            None, the directory has none.
    """
    path = os.path.join(directory, CONF_NAME)
    if not os.path.isfile(path): return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def candidate_list(directory, extra_ignore=(), admit=()):
    """
    RETURN: list[str], sorted names of the directory's files that are not
            ignored -- the source file candidates.

    IGNORED, silently: the configured 'extra_ignore' globs, names or
    anchored paths ('anchored_glob') -- less a name any 'admit' glob
    matches, which is a candidate again. The directory's own files
    ('hwut.conf', ...) are never candidates, 'admit' or not. There is no
    default set (R-102); a backup-shaped name is a candidate here and
    a wallflower to the explorer ('backup_shaped_f', R-103).
    """
    ignore_set = DEFAULT_IGNORE_SET + tuple(extra_ignore)
    result     = []
    for name in sorted(os.listdir(directory)):
        if not os.path.isfile(os.path.join(directory, name)): continue
        if any(fnmatch(name, glob) for glob in OWN_FILE_TUPLE): continue
        if any(glob_matches_f(directory, name, glob) for glob in ignore_set) \
           and not any(glob_matches_f(directory, name, glob)
                       for glob in admit):
            continue
        result.append(name)
    return result
