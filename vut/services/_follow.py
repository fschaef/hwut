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
                   fresh_choice, whole_test_f, write):
    """
    RETURN: bool, True where the labels file needed nothing or
            followed whole; False where it could not -- announced by
            name, the file left as it stood.

    'whole_test_f' re-keys EVERY entry of the test -- the choice-less
    one and every choice's own -- to the fresh file name; otherwise
    the one entry '(test, choice)' moves to '(test, fresh_choice)'.

    A fresh key that ALREADY STANDS is a fault, not a merge: two
    entries collapsing into one would answer one question with two
    lines' worth of labels nobody put together on purpose.
    """
    found = _ground(test_directory)
    if found is None: return True
    boundary, entry_db = found
    if entry_db is False:
        write("    FAULT: labels -- the file cannot be read; entries "
              "of '%s' do not follow" % test)
        return False

    old_key = _key_of(test_directory, test, boundary)
    if whole_test_f:
        fresh_key = _key_of(test_directory, fresh_test, boundary)
        move_list = [(key, (fresh_key, key[1]))
                     for key in entry_db if key[0] == old_key]
    else:
        source = (old_key, choice)
        move_list = [(source, (old_key, fresh_choice))] \
                    if source in entry_db else []
    if not move_list:
        write("    labels: none stood")
        return True

    for _, target in move_list:
        if target in entry_db:
            write("    FAULT: labels -- '%s' already stands; the "
                  "old entries keep their name for "
                  "'hwut.sanitize --orphans'"
                  % _file.target_text(target))
            return False
    for source, target in move_list:
        entry_db[target] = entry_db.pop(source)
    try:
        _file.write_entry_db(boundary, entry_db)
    except OSError as error:
        write("    FAULT: labels -- %s" % error)
        return False
    write("    labels: re-keyed (%d entr%s)"
          % (len(move_list), "y" if len(move_list) == 1 else "ies"))
    return True


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
