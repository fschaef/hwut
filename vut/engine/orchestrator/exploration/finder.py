"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Find what a TEST directory offers: 'hwut.conf', if present, and
         the source file candidates -- the directory's files minus what is
         ignored.

Ignored by default: '*.txt', '*.xml', '*.json', and THE FRAMEWORK'S OWN
FILES -- 'hwut.conf' and 'hwut-root.conf'. The directory's own 'ignore'
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
and read as a test application: one that fails to launch, and enters
the book as it fails. These names are REFUSED, not ignored: an ignored
file is silent, a refused one is named, with its reason, in the run's
closing REFUSED block. The shapes are the editors' and the tools'
('REFUSED_NAME_GLOB_TUPLE'); 'ignore' in 'hwut.conf' remains the
author's own word for silence.
______________________________________________________________________________
"""
import os

from fnmatch import fnmatch

CONF_NAME          = "hwut.conf"
ROOT_CONF_NAME     = "hwut-root.conf"

#  THE FRAMEWORK'S OWN FILES: never source file candidates.
OWN_FILE_TUPLE     = (CONF_NAME, ROOT_CONF_NAME)
#  A PYPE IS A CANONICALISER, NOT A TEST. It stands beside the test
#  that names it ('pype = "strip.pype"') and filters that test's
#  output; it is never a candidate and the nominal gate (E-41) never
#  sees it. Ignored by NAME here, rather than left for the header
#  reader to find no '@hwut' in -- a file that is not a test should
#  not be READ as one to be found not to be one.
DEFAULT_IGNORE_SET = ("*.txt", "*.xml", "*.json", "*.pype")

#  BACKUP-SHAPED NAMES: refused as source candidates, by name (E-41).
REFUSED_NAME_GLOB_TUPLE = ("*~", "#*#", "*.bak", "*.backup", "*.orig",
                           "*.old", "*.save", "*.rej", "*.copy", "*.swp",
                           "*.tmp")
REFUSED_NAME_REASON     = "backup-shaped name: not a source candidate"


def conf_text(directory):
    """
    RETURN: str,  the content of the directory's 'hwut.conf'.
            None, the directory has none.
    """
    path = os.path.join(directory, CONF_NAME)
    if not os.path.isfile(path): return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def candidate_list(directory, extra_ignore=()):
    """
    RETURN: [0] list[str], sorted names of the directory's files that are
                neither ignored nor refused -- the source file candidates.
            [1] list[(str, str)], sorted (name, reason) of the files
                REFUSED as candidates: backup-shaped names. Empty where
                none stands.

    'extra_ignore' are the configured globs, added to the default set;
    an ignored file is silent, a refused one is reported.
    """
    ignore_set   = DEFAULT_IGNORE_SET + tuple(extra_ignore) + OWN_FILE_TUPLE
    result       = []
    refused_list = []
    for name in sorted(os.listdir(directory)):
        if not os.path.isfile(os.path.join(directory, name)): continue
        if any(fnmatch(name, glob) for glob in ignore_set):    continue
        if any(fnmatch(name, glob) for glob in REFUSED_NAME_GLOB_TUPLE):
            refused_list.append((name, REFUSED_NAME_REASON))
            continue
        result.append(name)
    return result, refused_list
