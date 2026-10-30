"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THE 'hwut.good' FACES SHARE -- reading a path as a GOOD file
         or a test directory, and saying a path from where hwut was called.
______________________________________________________________________________
"""
import os
import shutil
from   pathlib import Path

from ....engine.bookkeeper.api import (GOOD_OWNED_FILE_TUPLE, LINK_SUFFIX,
                                       LinkFault, link_target, links_to,
                                       text_path_of)

GOOD_NAME = "GOOD"


def shown(path):
    """RETURN: str, 'path' from where hwut was called, '/' between."""
    return os.path.relpath(os.path.abspath(str(path))).replace(os.sep, "/")


def good_directory_of(directory):
    """
    RETURN: Path, the GOOD/ of the test directory 'directory' -- or
            'directory' itself where it IS a GOOD/.
    """
    path = Path(directory)
    return path if path.name == GOOD_NAME else path / GOOD_NAME


def in_good_f(path):
    """RETURN: bool, True where 'path' names a file inside a GOOD/."""
    return Path(os.path.abspath(str(path))).parent.name == GOOD_NAME


def text_tuple_of(directory):
    """
    RETURN: tuple[Path], every '.txt' nominal in the GOOD/ of the test
            directory 'directory', sorted -- the book and the register
            are not nominals.
    """
    good = good_directory_of(directory)
    if not good.is_dir(): return ()
    return tuple(good / name for name in sorted(os.listdir(str(good)))
                 if name.endswith(".txt") and name not in GOOD_OWNED_FILE_TUPLE
                 and (good / name).is_file())


def link_text_of(link):
    """RETURN: str, what the '.link' 'link' names, from where hwut was
               called; '(<why>)' where it names nothing it may."""
    try:               return shown(link_target(link))
    except LinkFault as fault:  return "(%s)" % fault


def isolated(link):
    """
    RETURN: Path, the '.txt' that now stands in place of the '.link'
            'link': a copy of the text it named. The link is gone.

    Raises LinkFault where the link names nothing it may.
    """
    target = link_target(link)
    own    = text_path_of(link)
    shutil.copyfile(str(target), str(own))
    Path(link).unlink()
    return own


def link_name_of(name):
    """RETURN: str, the '.link' name of the nominal file name 'name' --
               'x--c.txt' and 'x--c.link' both give 'x--c.link'."""
    stem, _, _ = name.rpartition(".")
    return "%s.%s" % (stem or name, LINK_SUFFIX)


def remedy_text(text_path):
    """
    RETURN: str, what to type where 'text_path' cannot go because links
            name it -- the three ways out, for every face that refuses.
    """
    p = shown(text_path)
    return ("'hwut.good.link.show %s' names them; 'hwut.good.isolate %s' "
            "gives each its own copy; 'hwut.good.rebase %s <other.txt>' "
            "points them elsewhere" % (p, p, p))


__all__ = ("GOOD_NAME", "shown", "good_directory_of", "in_good_f",
           "text_tuple_of", "link_text_of", "isolated", "link_name_of",
           "remedy_text",
           "links_to")
