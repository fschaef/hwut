"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: OPENING 'hwut-root.labels' FOR EDITING -- climb, read, build
         the view, select what the wish states.

'create', 'add' and 'remove' had the IDENTICAL nine lines apiece:

    boundary  = _file.boundary_of(directory)   -- climb, or REFUSED
    entry_db  = _file.read_entry_db(boundary)  -- read,  or FAULT
    view      = _file.view_of(boundary, entry_db)
    selected  = selected_key_tuple(directory, wish, view)

and then wrote the file at the end. Three verbs on one entry set is
one action, and it was written three times. The face inventory
(disc-9) found it by comparing what each face DOES rather than what it
is called.

TWO DOORS AND A REFUSAL KIND:

    opened(directory, write)      -> COpenLabels | None
    selected(open, directory, wish, write) -> keys | None
    written(open, write)          -> bool

EACH ANSWERS 'None' OR 'False' WHERE IT ALREADY SPOKE. A face that
gets None returns the status the brick named -- REFUSED where the tree
has no boundary, FAULT where the file cannot be read or written. THE
FACE STILL OWNS ITS EXIT: the brick says what went wrong and hands the
code back, because a face's status is part of its contract with a
script and no shared module may decide it (E-1).
______________________________________________________________________________
"""
from   dataclasses import dataclass

from   vut.engine.orchestrator.exploration.task_list \
                                             import SelectionError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                             import RootConfMissing
from   .._exit                               import E_ExitCode
from   .                                     import _file
from   ._faces                               import selected_key_tuple


@dataclass
class COpenLabels:
    """The tree's labels, open for editing.

    'boundary'  where 'hwut-root.conf' stands, and the labels file
                beside it.
    'entry_db'  what the file assigns, mutable: a face edits it and
                asks for it to be written.
    'view'      the same, in the shape a selection reads.
    'status'    what a face should answer where the opening failed --
                REFUSED for a tree with no boundary, FAULT for a file
                that cannot be meant."""
    boundary: str  = None
    entry_db: dict = None
    view:     object = None
    status:   object = None


def opened(directory, write):
    """
    RETURN: COpenLabels, ready to edit, where the tree has a boundary
            and its labels file can be read.
            COpenLabels carrying only 'status' where it cannot -- and
            the reason is ALREADY WRITTEN, so a face adds nothing.

    THE FACE STILL OWNS ITS EXIT: the status is handed back rather
    than raised, because what a face answers is part of its contract
    with a script (E-1).
    """
    try:
        boundary = _file.boundary_of(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return COpenLabels(status=E_ExitCode.REFUSED)
    try:
        entry_db = _file.read_entry_db(boundary)
    except _file.LabelFileError as error:
        write("FAULT: %s" % error)
        return COpenLabels(status=E_ExitCode.FAULT)
    return COpenLabels(boundary = boundary,
                       entry_db = entry_db,
                       view     = _file.view_of(boundary, entry_db))


def stands_f(open_labels, label):
    """
    RETURN: bool, True where the label is assigned to at least one
            run. The three writers ask this and answer differently:
            'create' refuses where it stands, 'add' and 'remove'
            refuse where it does not.
    """
    return any(label in label_set
               for label_set in open_labels.entry_db.values())


def selected(open_labels, directory, wish, write):
    """
    RETURN: tuple[(str, str | None)], the runs the wish selects, as
            entry keys -- warnings already written, faults already
            reported.
            None where the selection could not be made or the tree
            could not be fully read; the reason is written, and
            'open_labels.status' says what to answer.

    NOTHING IS WRITTEN WHERE A FAULT STANDS: a tree that cannot be
    fully read cannot say what it offers, and a label built on half a
    tree is a label nobody asked for.
    """
    try:
        key_tuple, warning_tuple, fault_tuple = \
            selected_key_tuple(directory, wish, open_labels.view)
    except (SelectionError, RootConfMissing) as error:
        write("REFUSED: %s" % error)
        open_labels.status = E_ExitCode.REFUSED
        return None
    for warning in warning_tuple: write(warning)
    if fault_tuple:
        for fault in fault_tuple: write("FAULT: %s" % fault)
        write("nothing written: a tree that cannot be fully read "
              "cannot say what it offers")
        open_labels.status = E_ExitCode.FAULT
        return None
    return key_tuple


def written(open_labels, write):
    """
    RETURN: bool, True where the file now says what 'entry_db' says.
            False where it could not be written -- the reason written,
            and 'open_labels.status' set to FAULT.
    """
    try:
        _file.write_entry_db(open_labels.boundary,
                             open_labels.entry_db)
    except OSError as error:
        write("FAULT: '%s' cannot be written -- %s"
              % (_file.file_path(open_labels.boundary), error))
        open_labels.status = E_ExitCode.FAULT
        return False
    return True
