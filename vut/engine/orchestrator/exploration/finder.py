"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Find what a TEST directory offers: 'hwut.conf', if present, and
         the source file candidates -- the directory's files minus what is
         ignored.

Ignored by default: '*.txt', '*.xml', '*.json', and 'hwut.conf' itself.
The directory's own 'ignore' globs add to these. The walk is one directory
deep: a TEST directory stands alone, and so does its file list.
______________________________________________________________________________
"""
import os

from fnmatch import fnmatch

CONF_NAME          = "hwut.conf"
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
    ignore_set = DEFAULT_IGNORE_SET + tuple(extra_ignore) + (CONF_NAME,)
    result     = []
    for name in sorted(os.listdir(directory)):
        if not os.path.isfile(os.path.join(directory, name)): continue
        if any(fnmatch(name, glob) for glob in ignore_set):    continue
        result.append(name)
    return result
