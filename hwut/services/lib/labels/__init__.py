"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE LABEL FACES -- 'hwut.labels.<verb>' <=> 'services/lib/labels/<verb>.py'
(the naming law's dotted clause, disc-8): 'create', 'add', 'remove',
'list', 'query', five acts on one file, 'hwut-root.labels'. The
underscore modules are theirs alone: '_file.py' reads and writes the
file, '_faces.py' holds what the five share. The GRAMMAR lives with
the engine ('plan/label.py'), because the selection evaluates it.

'view_at(directory)' is the ONE DOOR through which any other face
obtains the label view it hands to a selection -- 'hwut.run',
'hwut.plan', 'hwut.report.list', 'hwut.accept', 'hwut.report' and what
rides them. The engine never opens 'hwut-root.labels'; a face builds
the view here and hands it down.
______________________________________________________________________________
"""
from dataclasses import replace

from hwut.engine.orchestrator.exploration.tree_explorer \
                        import root_conf_directory, inner_root_tuple
from .          import _file


def view_at(directory):
    """
    RETURN: CLabelView (plan/label.py), what 'hwut-root.labels'
            assigns in the tree 'directory' stands in -- an EMPTY view
            where the file is absent, which imposes nothing: no label
            exists, no silence, and a selection behaves as one with no
            view at all. Every BUBBLE below 'directory' (an inner
            'hwut-root.conf', RQ-9) brings its own file's view in
            'inner_tuple'; 'defined' holds the labels of all of them.

    Raises RootConfMissing (tree_explorer) where the tree has no
    boundary, and LabelFileError (_file) where a file cannot be
    meant -- a face answers the first REFUSED and the second FAULT,
    and does not run: a selection whose silence cannot be determined
    must not guess at it.
    """
    boundary = root_conf_directory(directory)
    view     = _file.view_of(boundary, _file.read_entry_db(boundary))
    inner_tuple = tuple(_file.view_of(inner, _file.read_entry_db(inner))
                        for inner in inner_root_tuple(directory))
    if not inner_tuple: return view
    defined = view.defined
    for inner in inner_tuple: defined = defined | inner.defined
    return replace(view, inner_tuple=inner_tuple, defined=defined)

