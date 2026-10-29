"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE PATH GLOB OF A WISH -- '--glob', '--exclude', '--dir',
         '--exclude-dir' and the lines of a wishlist -- matched LEVEL BY
         LEVEL (ruled 2026-10-29, services E-206):

    *        any run of characters inside ONE level -- never '/'
    ?  [..]  one character, as fnmatch has them -- never '/'
    **       a whole level: any number of levels, none included

    'a/*/x'     matches 'a/b/x', not 'a/b/c/x'
    'a/**/x'    matches 'a/x', 'a/b/x', 'a/b/c/x'

The rule '-F' feature globs follow, and '.gitignore''s. A glob WITHOUT '/'
is a bare name and does not come here: it is matched against one name.
MEASURED before: fnmatch's '*' crossed '/', so 'a/*/x' matched 'a/b/c/x'
while '-F a/*' meant one level.
______________________________________________________________________________
"""
from fnmatch import fnmatchcase


def path_glob_f(glob, path):
    """
    RETURN: True,  the '/'-separated 'glob' names the '/'-separated 'path'
                   in whole, level by level ('**' any number of levels);
            False, else.
    """
    return _levels_f(tuple(glob.split("/")), tuple(path.split("/")))


def _levels_f(glob_tuple, part_tuple):
    """
    RETURN: True,  the glob levels match the path parts in whole;
            False, else.
    """
    if not glob_tuple: return not part_tuple
    head, rest = glob_tuple[0], glob_tuple[1:]
    if head == "**":
        #  '**' AT THE END wants at least nothing; elsewhere it may stand
        #  for no level at all ('a/**/x' names 'a/x').
        return any(_levels_f(rest, part_tuple[i:])
                   for i in range(len(part_tuple) + 1))
    if not part_tuple: return False
    return fnmatchcase(part_tuple[0], head) and _levels_f(rest, part_tuple[1:])
