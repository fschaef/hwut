"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ROSTER, 'HWUT/directories.txt' (CR-2, 2026-11-20) -- the TEST
         directories of a tree that hold records, one root-relative path
         per line, sorted, rewritten whole:

             #  HWUT/directories.txt -- the TEST directories of this tree
             #  that hold records. Written by hwut; ...
             ./game/TEST
             ./physics/TEST

DESCRIPTION
       THE BOOKS ARE THE DIRECTORY'S (bookkeeper B-9, coverage D-14), so a
       TEST directory deleted whole takes its own evidence with it: the run
       grows smaller and stays green. The roster is the one record above the
       directories, and it says no more than WHICH directories hold records
       -- no counts, no names -- so it changes only when a directory enters
       or leaves, and two branches rarely touch it at once.

       ONE WRITER, TWO TRANSITIONS: 'registered(directory, holds_f)' is asked
       by the Bookkeeper each time it writes a book; it writes the roster
       only where the answer differs from what the roster says -- a
       directory's first record, a directory's last record gone.

       THE READERS: 'gone_tuple' -- the entries whose directory does not
       stand, within the scope a walk covered; 'forgotten' and 'moved' --
       sanitize's two healings (CR-3).

       A DIRECTORY BELOW GROUND NO WALK ENTERS ('TMP', 'OUT', a no-entry
       marker) is never entered: a scratch tree a test builds inside its
       own TMP is no member of the project.

       ONE WRITE AT A TIME: the first run of a tree writes many books at
       once. The roster is changed under an exclusive 'flock' of the file
       itself, read under a shared one; where the platform has no 'fcntl'
       the change is made unlocked, which is the old risk and no new one.
______________________________________________________________________________
"""
import os

from ...auxiliary.no_entry import (ROOT_CONF_NAME, ROSTER_FILE_NAME,
                                   below_no_entry_f, entered)

try:
    import fcntl
except ImportError:                                  # not on every platform
    fcntl = None

HEADER = (
    "#  HWUT/directories.txt -- the TEST directories of this tree that hold",
    "#  records. Written by hwut when a directory gets its first record and",
    "#  when it loses its last. An entry whose directory is gone FAILS the",
    "#  run: 'hwut.sanitize.propose' says whether it moved or went.",
)


def root_of(directory):
    """
    RETURN: str, the absolute directory holding the nearest
                 'hwut-root.conf' at or above 'directory'
            None, where none stands
    """
    here = os.path.abspath(directory)
    while True:
        if os.path.isfile(os.path.join(here, ROOT_CONF_NAME)): return here
        parent = os.path.dirname(here)
        if parent == here: return None
        here = parent


def path_of(root):
    """RETURN: str, where the roster of the tree rooted at 'root' stands."""
    return os.path.join(root, ROSTER_FILE_NAME)


def entry_of(root, directory):
    """
    RETURN: str, 'directory' as the roster spells it: './' and the path
            relative to 'root', '/'-separated.
    """
    relative = os.path.relpath(os.path.abspath(directory), root)
    return "./" + relative.replace(os.sep, "/")


def directory_of(root, entry):
    """RETURN: str, the absolute directory a roster 'entry' names."""
    return os.path.normpath(os.path.join(root, entry[2:] if entry.startswith("./")
                                         else entry))


def _entry_set_of_text(text):
    """RETURN: set of str, the entries of a roster text: every line that is
    neither empty nor a comment, stripped."""
    return {line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")}


def _text_of(entry_set):
    """RETURN: str, the whole roster: the header, then the entries
    sorted."""
    return "\n".join(HEADER + tuple(sorted(entry_set))) + "\n"


def entry_tuple(root):
    """
    RETURN: tuple of str, the roster's entries, sorted; empty where no
            roster stands or it cannot be read.
    """
    path = path_of(root)
    try:
        with open(path, encoding="utf-8") as fh:
            if fcntl is not None: fcntl.flock(fh, fcntl.LOCK_SH)
            return tuple(sorted(_entry_set_of_text(fh.read())))
    except OSError:
        return ()


def _changed(root, change):
    """
    RETURN: bool, True where the roster changed. 'change(entry_set)'
            returns the new set; the file is rewritten only where it
            differs, under an exclusive lock of the file itself.
            Raises OSError where it cannot be written.
    """
    path = path_of(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+", encoding="utf-8") as fh:
        if fcntl is not None: fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        old = _entry_set_of_text(fh.read())
        new = change(set(old))
        if new == old: return False
        fh.seek(0)
        fh.truncate()
        fh.write(_text_of(new))
        fh.flush()
        return True


def _member_f(root, directory):
    """RETURN: bool, True where 'directory' is a TEST directory of the
    tree 'root' a walk enters: strictly below the root, below no ground no
    walk enters."""
    directory = os.path.abspath(directory)
    if not directory.startswith(root + os.sep): return False
    return not below_no_entry_f(directory, lambda here: here == root)


def _book_holds_f(directory):
    """RETURN: bool, True where 'directory/GOOD/book.csv' holds a row."""
    try:
        with open(os.path.join(directory, "GOOD", "book.csv"),
                  encoding="utf-8") as fh:
            return any(line.strip() and not line.startswith("#")
                       and not line.startswith("test;") for line in fh)
    except OSError:
        return False


def found_entry_set(root):
    """
    RETURN: set of str, the entries of every TEST directory below 'root'
            whose book holds a row -- the roster as the disk would write it,
            walked as every walk walks (no ground no walk enters, no inner
            root).
    """
    result = set()
    for here, name_list, _ in os.walk(root):
        name_list[:] = entered(here, name_list)
        if here != root and _book_holds_f(here):
            result.add(entry_of(root, here))
    return result


def registered(directory, holds_f):
    """
    RETURN: bool, True where the roster changed: 'directory' entered where
            it now holds records ('holds_f') and was not on it, removed
            where it holds none and was. False where nothing changed --
            no root above, a directory below ground no walk enters, the
            roster agreeing already, or it cannot be written (a book
            written is never undone for its roster).
    """
    root = root_of(directory)
    if root is None or not _member_f(root, directory): return False
    entry = entry_of(root, directory)
    #  A TREE WITHOUT A ROSTER BEGINS ONE FROM EVERY BOOK THAT STANDS (CR-2),
    #  once: a directory no run here reaches -- another platform's -- is
    #  then on it from the start.
    if not os.path.isfile(path_of(root)):
        if not holds_f: return False
        try:
            return _changed(root, lambda s: s | found_entry_set(root)
                                              | {entry})
        except OSError:
            return False
    #  THE COMMON CASE IS AGREEMENT, asked without a lock.
    if (entry in entry_tuple(root)) == bool(holds_f): return False
    try:
        if holds_f: return _changed(root, lambda s: s | {entry})
        if not os.path.isfile(path_of(root)): return False
        return _changed(root, lambda s: s - {entry})
    except OSError:
        return False


def gone_tuple(root, start=None, wanted_f=None):
    """
    RETURN: tuple of str, the roster's entries whose directory does not
            stand, within the scope a walk covered: below 'start' (the
            root where None), and accepted by 'wanted_f(relative path)'
            where one is given. Sorted.

    ONLY WHAT WAS WALKED IS JUDGED: a directory outside the scope is not
    gone, it was not asked about.
    """
    start = os.path.abspath(start or root)
    result = []
    for entry in entry_tuple(root):
        directory = directory_of(root, entry)
        if os.path.isdir(directory): continue
        if directory != start and not directory.startswith(start + os.sep):
            continue
        relative = os.path.relpath(directory, root).replace(os.sep, "/")
        if wanted_f is not None and not wanted_f(relative): continue
        result.append(entry)
    return tuple(result)


def forgotten(root, entry):
    """
    RETURN: bool, True where 'entry' was on the roster and is no more.
            Raises OSError where the roster cannot be written.
    """
    if entry not in entry_tuple(root): return False
    return _changed(root, lambda s: s - {entry})


def moved(root, old, new):
    """
    RETURN: bool, True where the entry 'old' was replaced by 'new'.
            Raises OSError where the roster cannot be written.
    """
    if old not in entry_tuple(root): return False
    return _changed(root, lambda s: (s - {old}) | {new})
