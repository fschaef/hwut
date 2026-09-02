"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE LABEL FACES -- 'hwut.labels.<verb>' <=> 'services/lib/labels/<verb>.py'
(the naming law's dotted clause, disc-8): 'create', 'add', 'remove',
'list', 'query', five acts on one file, 'hwut-root.labels'. The
underscore modules are theirs alone: '_file.py' reads and writes the
file, '_faces.py' holds what the five share. The GRAMMAR lives with
the engine ('plan/label.py'), because the selection evaluates it.

'view_at(directory)' is the ONE DOOR through which any other face
obtains the label view it hands to a selection -- 'hwut.run',
'hwut.plan', 'hwut.wishlist', 'hwut.accept', 'hwut.report' and what
rides them. The engine never opens 'hwut-root.labels'; a face builds
the view here and hands it down.
______________________________________________________________________________
"""
from vut.engine.orchestrator.exploration.tree_explorer \
                        import RootConfMissing, root_conf_directory
from .          import _file


def view_at(directory):
    """
    RETURN: CLabelView (plan/label.py), what 'hwut-root.labels'
            assigns in the tree 'directory' stands in -- an EMPTY view
            where the file is absent, which imposes nothing: no label
            exists, no silence, and a selection behaves as one with no
            view at all.

    Raises RootConfMissing (tree_explorer) where the tree has no
    boundary, and LabelFileError (_file) where the file cannot be
    meant -- a face answers the first REFUSED and the second FAULT,
    and does not run: a selection whose silence cannot be determined
    must not guess at it.
    """
    boundary = root_conf_directory(directory)
    return _file.view_of(boundary, _file.read_entry_db(boundary))


def view_at_or_offer(directory, write):
    """
    RETURN: CLabelView where a boundary stands -- or where the person
            accepted an offer to place one, in which case the tree now
            has one and the view is empty.
            None where no boundary stands and none was placed; the
            offer is already written, and the face answers REFUSED.

    A FACE MAY NOT PROCEED WITHOUT A BOUNDARY, and a person who has
    just arrived in a tree they did not build should be told WHERE ONE
    GOES, not merely that one is missing ('services/_boundary.py').
    """
    from ..._boundary import placed
    try:
        return view_at(directory)
    except RootConfMissing:
        pass
    if placed(directory, write) is None: return None
    return view_at(directory)
