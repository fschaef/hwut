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
______________________________________________________________________________
"""
import os

from fnmatch import fnmatch

CONF_NAME          = "hwut.conf"
ROOT_CONF_NAME     = "hwut-root.conf"

#  THE FRAMEWORK'S OWN FILES: never source file candidates.
OWN_FILE_TUPLE     = (CONF_NAME, ROOT_CONF_NAME)
DEFAULT_IGNORE_SET = ("*.txt", "*.xml", "*.json")


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
    RETURN: list[str], sorted names of the directory's files that are not
            ignored -- the source file candidates.

    'extra_ignore' are the configured globs, added to the default set.
    """
    ignore_set = DEFAULT_IGNORE_SET + tuple(extra_ignore) + OWN_FILE_TUPLE
    result     = []
    for name in sorted(os.listdir(directory)):
        if not os.path.isfile(os.path.join(directory, name)): continue
        if any(fnmatch(name, glob) for glob in ignore_set):    continue
        result.append(name)
    return result
