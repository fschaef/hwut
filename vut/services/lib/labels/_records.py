"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THE FIVE LABEL FACES ARE ASKED AND WHAT THEY ANSWER
         (services E-106) -- one Request and one Result for the family,
         since all five take the same line and edit the same file.

DESCRIPTION
       'hwut.labels.create', '.add', '.remove', '.list', '.query' differ
       in ONE verb over one entry set. They share their door
       ('_faces.opened'), their editing layer ('_editing') and their
       file ('_file'), so they share their records too: a Request that
       is a wish, a directory and the label words; a Result that says
       what the set holds NOW and what the verb changed.

       THE SELECTION IS AN ANSWER, NOT A PRINTOUT: '_editing.selected'
       used to write its warnings and faults and stash an exit code;
       'Selection' carries them, and the face says them. That is the
       same cut as E-103's, one layer down.
______________________________________________________________________________
"""
from dataclasses import dataclass

from vut.services._exit import E_ExitCode


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of a label face: the wish as plain fields, where
    to look, and the words the verb takes (a label, mostly)."""
    directory:     str = "."
    word_tuple:    tuple = ()          # the label(s) the verb names
    #  the wish
    fail_f:        bool = False
    pass_f:        bool = False
    since_spec:    str | None = None
    until_spec:    str | None = None
    glob_tuple:    tuple = ()
    exclude_tuple: tuple = ()
    dir_tuple:     tuple = ()
    exclude_dir_tuple: tuple = ()
    wishlist_f:    bool = False
    label_spec:    str | None = None
    language_tuple:tuple = ()
    faster_than_ms:int | None = None
    unaccepted_f:  bool = False


@dataclass(frozen=True)
class Selection:
    """WHAT THE WISH SELECTED, and what reading the tree had to say.

    'key_tuple' is empty where nothing was selected; 'fault_tuple'
    non-empty means NOTHING MAY BE WRITTEN -- a tree that cannot be
    fully read cannot say what it offers.
    """
    key_tuple:     tuple = ()          # of (target text, choice or None)
    warning_tuple: tuple = ()
    fault_tuple:   tuple = ()
    refusal:       str | None = None   # the wish itself was refused

    def good_f(self):
        """RETURN: bool, True where the selection may be acted upon."""
        return self.refusal is None and not self.fault_tuple


@dataclass(frozen=True)
class Result:
    """WHAT THE VERB DID: the label it names, the members it touched,
    and what the set holds now."""
    label:         str = ""
    member_tuple:  tuple = ()          # of str, the entries said
    added_tuple:   tuple = ()
    removed_tuple: tuple = ()
    deleted_f:     bool = False        # the label itself is gone
    untouched_n:   int  = 0


def code_of(selection):
    """RETURN: E_ExitCode, what a face answers where 'selection' is not
               good: REFUSED where the wish was, FAULT where the tree
               was."""
    if selection.refusal is not None: return E_ExitCode.REFUSED
    return E_ExitCode.FAULT
