"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DETECTOR (spec 43 section 6; intend/43 T-h, t-5, t-6),
         for 'hwut.features.register' and 'hwut.sanitize.propose
         --relations', in one vocabulary: what the three feature files and
         the test headers disagree about. It detects; it never writes.

    detect(view)                -> tuple of CNote   (the view's, complete)
    detect_of_tree(directory)   -> tuple of CNote   (raises as 'view_of')
    past_file_list(top)         -> list of str      the files of the past

KINDS, every one a NOTE -- neither is a failure of the product:

    unplaced        documented, in no forest line: a promise with no place
    undocumented    a ROOT of the forest that no doc block explains: a
                    promise nobody explained. A NON-root with no block is
                    silent -- a child may lean on its parent's sentence.
    outside         a test run links an id that stands nowhere, or a
                    retired one: OUTSIDE THE RELATION
    prototype       a prototype that no feature aggregates (intend/44 p-8);
                    a member without a block in a prototype without one
                    is noted 'undocumented' 
    past-file       a file of the past -- a TEST directory's
                    'hwut-features.conf', 'hwut-root-features.conf',
                    'hwut-feature-map.conf' -- read by nothing

A fault of the map (an id the forest does not hold) is the map's fault and
stops the view before any note ('feature_external').

Each note ends in 'did you mean' where a known id is near ('suggestion').
THE FINGERPRINT PAIRING IS GONE: position implies no identity any more; a
rename is 'hwut.features.rename', and what the author did not rename is two
different promises.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from .finder        import PAST_FILE_TUPLE
from .suggestion    import did_you_mean
from .feature_view  import OUTSIDE_RETIRED
from .tree_explorer import forest_owner_f

UNPLACED      = "unplaced"
UNDOCUMENTED  = "undocumented"
OUTSIDE       = "outside"
PAST_FILE     = "past-file"
PROTOTYPE     = "prototype"
KIND_TUPLE    = (UNPLACED, UNDOCUMENTED, OUTSIDE, PROTOTYPE, PAST_FILE)

#  What a walk does not enter: the volatile directories of a run and of a
#  checkout (the same the census strips), and every hidden one.
PRUNE_NAME_TUPLE = ("TMP", "OUT", "__pycache__", "htmlcov", "node_modules")


@dataclass(frozen=True)
class CNote:
    """One disagreement: its kind, the id or file it is about, and the
    note as it is printed -- 'NOTE  ...', the remedy after '=>'."""
    kind:    str
    subject: str
    text:    str


def detect(view):
    """RETURN: tuple of CNote, what the three files and the links of
    'view' (feature_view.CView, asked anywhere) disagree about, in this
    order: the unplaced, the undocumented roots, the links outside, the
    prototypes nobody aggregates, the files of the past."""
    features = view.features
    forest   = features.forest
    line_set = sorted(forest.id_set)
    note_list = []
    for each in view.unplaced:
        note_list.append(CNote(UNPLACED, each.id,
            "NOTE  '%s' is documented and stands in no forest line "
            "=> hwut.features.tree%s"
            % (each.id, did_you_mean(each.id, line_set))))
    for each in forest.root_tuple:
        if features.entry_of(each) is None:
            note_list.append(CNote(UNDOCUMENTED, each,
                "NOTE  the root '%s' stands in no block of the doc file "
                "=> '[[%s]]'" % (each, each)))
    seen = set()
    for path, test, choice, feature_id, why in view.outside_tuple:
        if feature_id in seen: continue
        seen.add(feature_id)
        where = test if path == "." else "%s/%s" % (path, test)
        note_list.append(CNote(OUTSIDE, feature_id,
            "NOTE  '%s' is linked by %s%s and %s%s"
            % (feature_id, where, "" if choice is None else " [%s]" % choice,
               "is " if why == OUTSIDE_RETIRED else "", why)))
    used = {each.partition("+")[2] for each in forest.id_set if "+" in each}
    for each in sorted(forest.prototype_db, key=lambda p: forest.line_of[p]):
        if each in used: continue
        note_list.append(CNote(PROTOTYPE, "+" + each,
            "NOTE  the prototype '+%s' is aggregated by no feature "
            "=> '<feature> : +%s'" % (each, each)))
    entry_db = features.doc.entry_db if features.doc is not None else {}
    for member, prototype in forest.member_of.items():
        if member in forest.prototype_db: continue
        if member in entry_db: continue
        around = prototype
        while around is not None and "+" + around not in entry_db:
            around = forest.member_of.get(around)
        if around is not None: continue
        note_list.append(CNote(UNDOCUMENTED, member,
            "NOTE  the member '%s' of '+%s' stands in no block, nor does "
            "a prototype around it => '[[%s]]'" % (member, prototype, member)))
    for each in past_file_list(view.top):
        note_list.append(CNote(PAST_FILE, each,
            "NOTE  '%s' is a file of the past, read by nothing => its "
            "content belongs in the forest and the doc file (spec 43)"
            % each))
    return tuple(note_list)


def detect_of_tree(directory):
    """RETURN: tuple of CNote, 'detect' of the view of the tree
    'directory' stands in. Raises as 'feature_view.view_of'."""
    from .feature_view import view_of
    return detect(view_of(directory))


def past_file_list(top):
    """RETURN: list of str, every file of the past ('PAST_FILE_TUPLE')
    below 'top', relative to it, sorted -- a bubble with a forest of its
    own not entered, the volatile and hidden directories pruned."""
    result = []
    for here, directory_list, file_list in os.walk(top):
        directory_list[:] = sorted(
            each for each in directory_list
            if not each.startswith(".") and each not in PRUNE_NAME_TUPLE
            and not forest_owner_f(os.path.join(here, each)))
        for name in file_list:
            if name in PAST_FILE_TUPLE:
                result.append(os.path.relpath(os.path.join(here, name), top)
                              .replace(os.sep, "/"))
    return sorted(result)


def outside_count(directory):
    """
    RETURN: int, how many links below the forest top of 'directory' name
            an id that stands nowhere or is retired; 0 where no forest
            stands or anything goes wrong -- a hint must never cost a run
            its result.
    """
    try:
        from .feature_view import view_of
        return len(view_of(directory).outside_tuple)
    except Exception:                                   # noqa: BLE001
        return 0

