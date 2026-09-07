# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
______________________________________________________________________________
PURPOSE: A TEST NAMED BY PATH -- 'a/TEST/keep.sh' -- means 'ENTER the
         directory "a/TEST" and perform "keep.sh" there', on every face
         (E-45, E-47).

A face that takes test words and a '--directory=<path>' has two ways to
say the same thing, and a reader who types the path he can see in a
run's report expects it to work. 'split_words' makes it work in ONE
PLACE: the directory is read off the words, the words become bare
names, and the face carries on as if '--directory' had been said.

THE RULE. A word with a '/' in it whose DIRECTORY PART IS LITERAL --
no '*', '?' or '[' in it -- is a path; its directory part is the test
directory, its base name the test. A RELATIVE path is read against
'--directory' where one was said ('--directory=tree a/TEST/x.sh'
enters 'tree/a/TEST'), against the current directory otherwise. An
ABSOLUTE path stands on its own; beside a '--directory' it must lie
within it, or it is refused. Every path-bearing word must name the
SAME directory -- a face that works in one directory cannot be asked
to work in two. A word without '/' is a bare name in the directory
that stands. A word whose directory part carries a glob metacharacter
is NOT a path: it is a WISH GLOB with a path member (E-15), and is
left to the wish. The base name may glob either way:
'a/TEST/test-*.py' enters 'a/TEST' and asks for 'test-*.py'.
"""
import os

GLOB_METACHARACTER_TUPLE = ("*", "?", "[")


class TargetError(Exception):
    """The words name more than one directory, or an absolute path
    lies outside '--directory'."""


def split_words(word_list, directory="."):
    """
    RETURN: [0] str   the directory the words stand in: the one their
                      paths name, read against 'directory' where
                      relative; 'directory' itself where no word
                      carries a path
            [1] list  the words with any path part removed, so a face
                      reads bare test names

    Raises TargetError where two words name different directories, or
    an absolute path lies outside a 'directory' that was said.

    A CHOICE WORD IS LEFT ALONE. Only a word carrying '/' with a
    literal directory part is read as a path; 'keep.sh one two' passes
    through as three bare words with the directory untouched, and so
    does 'a/*/TEST/keep.sh' -- a glob, the wish's.
    """
    found = None
    out   = []
    for word in word_list:
        if not path_f(word):
            out.append(word); continue
        where, name = os.path.split(word)
        if not os.path.isabs(where):
            where = os.path.join(directory, where)
        where = os.path.normpath(where)
        if found is None:
            found = where
        elif found != where:
            raise TargetError("the words name two directories: '%s' and "
                              "'%s'" % (found, where))
        out.append(name)
    if found is None:
        return directory, out
    if os.path.isabs(found) and directory != ".":
        base = os.path.abspath(directory)
        if os.path.commonpath([base, found]) != base:
            raise TargetError("the path '%s' lies outside "
                              "'--directory=%s'" % (found, directory))
    return found, out


def path_f(word):
    """
    RETURN: True,  'word' is a path: it carries '/' and its directory
                   part holds no glob metacharacter.
            False, otherwise -- a bare name, or a wish glob.
    """
    if "/" not in word: return False
    where = word.rsplit("/", 1)[0]
    return not any(c in where for c in GLOB_METACHARACTER_TUPLE)


def entered(word_list, directory, write, usage=None):
    """
    RETURN: (str, list), the directory entered and the bare words --
            'split_words' applied.
            None, where the words refuse to be read: the refusal is
            written, with 'usage' where given.

    The one call every face makes between reading its words and
    checking its directory.
    """
    try:
        return split_words(word_list, directory)
    except TargetError as error:
        write("REFUSED: %s" % error)
        if usage is not None: write(usage)
        return None
