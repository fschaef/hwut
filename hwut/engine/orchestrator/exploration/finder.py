"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Find what a TEST directory offers: 'hwut.conf', if present, and
         the source file candidates -- the directory's files minus what is
         ignored.

Ignored by default: '*.txt', '*.xml', '*.json', '*.pype', and THE
FRAMEWORK'S OWN FILES -- 'hwut.conf', 'hwut-root.conf', 'hwut-info.dat',
'hwut-traces.csv', 'hwut-root.labels' (README section 0). The directory's own 'ignore'
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
and would read as a test application. These names are IGNORED, as the
default set is (ruled 2026-10-17, services E-159; they were refused by
name before). The shapes are the editors' and the tools'
('BACKUP_NAME_GLOB_TUPLE'); 'ignore' in 'hwut.conf' adds the author's
own, 'admit' takes a glob out of the whole ignore set -- a backup-shaped
name meant as a test stands as one again.
______________________________________________________________________________
"""
import os

from fnmatch import fnmatch

CONF_NAME          = "hwut.conf"
ROOT_CONF_NAME     = "hwut-root.conf"

#  THE FRAMEWORK'S OWN FILES: never source file candidates. The book
#  and the traces stand in every TEST directory (X-INTERVIEW): they were
#  MEASURED interviewed on every walk, two programs run per directory
#  to answer nothing.
#  THE FEATURES A TEST DIRECTORY PROVES ('feature_relation.py'), and the
#  map of published ids of the past (R-94): read by nothing, named by the
#  detector as old vocabulary (R-96).
FEATURE_FILE_NAME     = "hwut-features.conf"
MAP_FILE_NAME         = "hwut-feature-map.conf"
#  THE CENTRAL FILE (R-96, spec 23 VERSION 10), beside 'hwut-root.conf':
#  directory ids, the tree of features, the retired ones.
REGISTRY_FILE_NAME    = "hwut-root-features.conf"

OWN_FILE_TUPLE     = (CONF_NAME, ROOT_CONF_NAME, "hwut-info.dat",
                      "hwut-traces.csv", "hwut-root.labels",
                      FEATURE_FILE_NAME, MAP_FILE_NAME,
                      REGISTRY_FILE_NAME)
#  A PYPE IS A CANONICALISER, NOT A TEST. It stands beside the test
#  that names it ('pype = "strip.pype"') and filters that test's
#  output; it is never a candidate and the nominal gate (E-41) never
#  sees it. Ignored by NAME here, rather than left for the header
#  reader to find no '@hwut' in -- a file that is not a test should
#  not be READ as one to be found not to be one.
DEFAULT_IGNORE_SET = ("*.txt", "*.xml", "*.json", "*.pype")

#  BACKUP-SHAPED NAMES ARE IGNORED (ruled 2026-10-17, superseding their
#  refusal by name, E-41): silent, as every ignored name is. 'admit' in
#  'hwut.conf' takes a glob out of the ignore set, this one included.
BACKUP_NAME_GLOB_TUPLE = ("*~", "#*#", "*.bak", "*.backup", "*.orig",
                          "*.old", "*.save", "*.rej", "*.copy", "*.swp",
                          "*.tmp")


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

    IGNORED, silently: the default set, the backup-shaped names, and the
    configured 'extra_ignore' globs -- less a name any 'admit' glob
    matches, which is a candidate again. The directory's own files
    ('hwut.conf', ...) are never candidates, 'admit' or not.
    """
    ignore_set = DEFAULT_IGNORE_SET + BACKUP_NAME_GLOB_TUPLE \
                 + tuple(extra_ignore)
    result     = []
    for name in sorted(os.listdir(directory)):
        if not os.path.isfile(os.path.join(directory, name)): continue
        if any(fnmatch(name, glob) for glob in OWN_FILE_TUPLE): continue
        if any(fnmatch(name, glob) for glob in ignore_set) \
           and not any(fnmatch(name, glob) for glob in admit):
            continue
        result.append(name)
    return result
