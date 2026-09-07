"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: FOLLOWING A NAME -- the ONE PLACE where a test's rename or
         removal reaches the records kept at the TREE'S BOUNDARY
         (disc-8 section 5).

'hwut.rename' re-keys nominals, candidates, book entry and register
entry; 'hwut.remove' forgets them. Those live IN the test directory.
Records at the boundary -- today 'hwut-root.labels', tomorrow whatever
else anchors there -- would otherwise be forgotten BY EVERY FACE
SEPARATELY, and the face that forgets is the one nobody notices: a
label keyed by a name that has changed loses a member SILENTLY, and
the member is not missing, it is UNLABELLED, which looks exactly like
never having been labelled.

So every affected face calls HERE, once, as its LAST step: a crash
before this step leaves a boundary entry naming a name that no longer
exists -- which 'hwut.sanitize --orphans' can find and say aloud
(E-18) -- never a record silently pointing at nothing.

A DIRECTORY OUTSIDE ANY TREE follows nothing: no boundary, no
boundary record, and the faces that work without a root conf keep
working without one. AN ABSENT LABELS FILE PRINTS NOTHING: the
feature unused must cost no line of output.
______________________________________________________________________________
"""
import os

from   vut.engine.orchestrator.exploration.tree_explorer \
                                  import (RootConfMissing,
                                          root_conf_directory)
from   .lib.labels                    import _file


def labels_renamed(test_directory, test, choice, fresh_test,
                   fresh_choice, whole_test_f, write,
                   target_directory=None):
    """
    RETURN: bool, True where the labels file needed nothing or
            followed whole; False where it could not -- announced by
            name, the file left as it stood.

    'whole_test_f' re-keys EVERY entry of the test -- the choice-less
    one and every choice's own -- to the fresh file name; otherwise
    the one entry '(test, choice)' moves to '(test, fresh_choice)'.

    'target_directory', where given and different, is where the fresh
    name STANDS (E-46): the fresh key is made against it. Under the
    same boundary the entries re-key in one file; under another
    boundary they leave the source's file and enter the target's --
    one that stands, or one made for them. A target directory above
    no boundary is a fault: an entry cannot follow to where no labels
    can be kept.

    A fresh key that ALREADY STANDS is a fault, not a merge: two
    entries collapsing into one would answer one question with two
    lines' worth of labels nobody put together on purpose.
    """
    if target_directory is None or _same_place(test_directory,
                                                target_directory):
        target_directory = test_directory
    found = _ground(test_directory)
    if found is None: return True
    boundary, entry_db = found
    if entry_db is False:
        write("    FAULT: labels -- the file cannot be read; entries "
              "of '%s' do not follow" % test)
        return False

    old_key = _key_of(test_directory, test, boundary)
    if whole_test_f:
        move_list = [key for key in entry_db if key[0] == old_key]
    else:
        move_list = [(old_key, choice)] \
                    if (old_key, choice) in entry_db else []
    if not move_list:
        write("    labels: none stood")
        return True

    #  WHERE THE FRESH KEY IS MADE: against the directory the fresh
    #  name stands in, under ITS boundary.
    try:
        target_boundary = root_conf_directory(target_directory)
    except RootConfMissing:
        write("    FAULT: labels -- no boundary stands above '%s'; "
              "entries of '%s' cannot follow there" % (target_directory,
                                                       test))
        return False
    if _same_place(target_boundary, boundary):
        target_db = entry_db
    elif os.path.isfile(_file.file_path(target_boundary)):
        try:
            target_db = _file.read_entry_db(target_boundary)
        except _file.LabelFileError:
            write("    FAULT: labels -- the target boundary's file "
                  "cannot be read; entries of '%s' do not follow" % test)
            return False
    else:
        target_db = {}
    fresh_key = _key_of(target_directory, fresh_test, target_boundary)
    pair_list = [(key, (fresh_key,
                        key[1] if whole_test_f else fresh_choice))
                 for key in move_list]

    for _, target in pair_list:
        if target in target_db:
            write("    FAULT: labels -- '%s' already stands; the "
                  "old entries keep their name for "
                  "'hwut.sanitize --orphans'"
                  % _file.target_text(target))
            return False
    for source, target in pair_list:
        target_db[target] = entry_db.pop(source)
    try:
        _file.write_entry_db(boundary, entry_db)
        if target_db is not entry_db:
            _file.write_entry_db(target_boundary, target_db)
    except OSError as error:
        write("    FAULT: labels -- %s" % error)
        return False
    n = len(pair_list)
    write("    labels: %s (%d entr%s)"
          % ("re-keyed" if target_db is entry_db
             else "carried to the boundary '%s'" % target_boundary,
             n, "y" if n == 1 else "ies"))
    return True


def _same_place(a, b):
    """RETURN: bool, True where the two paths name one directory."""
    return os.path.normcase(os.path.abspath(a)) \
           == os.path.normcase(os.path.abspath(b))


def labels_forgotten(test_directory, test, choice, whole_test_f,
                     write):
    """
    RETURN: bool, True where the labels file needed nothing or forgot
            whole; False where it could not -- announced by name.

    Symmetric with the book and the register, which removal already
    forgets (E-12): a dropped entry may empty a label, and an emptied
    label is deleted; a file left with no entries is removed whole.
    """
    found = _ground(test_directory)
    if found is None: return True
    boundary, entry_db = found
    if entry_db is False:
        write("    FAULT: labels -- the file cannot be read; entries "
              "of '%s' are not forgotten" % test)
        return False

    file_key = _key_of(test_directory, test, boundary)
    if whole_test_f:
        drop_list = [key for key in entry_db if key[0] == file_key]
    else:
        drop_list = [(file_key, choice)] \
                    if (file_key, choice) in entry_db else []
    if not drop_list:
        write("    labels: none stood")
        return True

    for key in drop_list:
        del entry_db[key]
    try:
        _file.write_entry_db(boundary, entry_db)
    except OSError as error:
        write("    FAULT: labels -- %s" % error)
        return False
    write("    labels: dropped (%d entr%s)"
          % (len(drop_list), "y" if len(drop_list) == 1 else "ies"))
    return True


def _ground(test_directory):
    """
    RETURN: (str, dict) -- the boundary and the labels file's entries.
            (str, False)   where the file stands but cannot be read.
            None           where nothing is to follow: no boundary
                           stands above, or no labels file at the one
                           that does -- both silent, by the module
                           purpose.
    """
    try:
        boundary = root_conf_directory(test_directory)
    except RootConfMissing:
        return None
    if not os.path.isfile(_file.file_path(boundary)):
        return None
    try:
        return boundary, _file.read_entry_db(boundary)
    except _file.LabelFileError:
        return boundary, False


def _key_of(test_directory, test, boundary):
    """
    RETURN: str, the labels-file key of 'test' in 'test_directory':
            the path relative to 'boundary', '/'-separated.
    """
    whole = os.path.abspath(os.path.join(test_directory, test))
    return os.path.relpath(whole, boundary).replace(os.sep, "/")
