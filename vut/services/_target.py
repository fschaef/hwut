# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
______________________________________________________________________________
PURPOSE: A TEST NAMED BY PATH -- 'a/TEST/keep.sh' -- means 'the test
         "keep.sh" in the directory "a/TEST"', on every face.

A face that takes bare test names and a '--directory=<path>' has two
ways to say the same thing, and a reader who types the path he can see
in a run's report expects it to work. 'split_words' makes it work in
ONE PLACE: the directory is read off the words, the words become bare
names, and the face carries on as if '--directory' had been said.

THE RULE. A word with a '/' in it is a path; its directory part is the
test directory, its base name the test. Every path-bearing word must
name the SAME directory -- a face that works in one directory cannot
be asked to work in two -- and none may disagree with an explicit
'--directory'. A word without '/' is a bare name in the directory that
stands.
______________________________________________________________________________
"""
import os


class TargetError(Exception):
    """The words name more than one directory, or disagree with
    '--directory'."""


def split_words(word_list, directory="."):
    """
    RETURN: [0] str   the directory the words stand in -- the one
                      their paths name, or 'directory' where none of
                      them carries a path
            [1] list  the words with any path part removed, so a face
                      reads bare test names

    Raises TargetError where two words name different directories, or
    a word's directory disagrees with a 'directory' that was said.

    A CHOICE WORD IS LEFT ALONE. Only a word carrying '/' is read as a
    path; 'keep.sh one two' passes through as three bare words with
    the directory untouched.
    """
    found = None
    out   = []
    for word in word_list:
        if "/" not in word:
            out.append(word); continue
        where, name = os.path.split(word)
        where = os.path.normpath(where) if where else "."
        if found is None:
            found = where
        elif os.path.normpath(found) != where:
            raise TargetError("the words name two directories: '%s' and "
                              "'%s'" % (found, where))
        out.append(name)
    if found is None:
        return directory, out
    if directory != "." and os.path.normpath(directory) != found:
        raise TargetError("'--directory=%s' and the path '%s' disagree"
                          % (directory, found))
    return found, out
