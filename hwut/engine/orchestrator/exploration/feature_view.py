"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURES AS THE CENTRAL FILE GROUPS THEM, joined with the test
         runs that prove them (spec 23 VERSION 10 sections 5, 6; R-96) --
         what 'hwut.report.features', the feature document and the wish read
         where 'hwut-root-features.conf' stands.

    view_of(directory)   -> CView     (raises ViewRefused, RootConfMissing)

THE JOIN. The links and the verdicts are the relation's, per TEST
directory ('feature_relation.relation_of_tree' -- 'test_directory_db', which
knows no component and no id). The tree, the ids and the keys above a leaf
are the central file's. A leaf finds its TEST directory through its
directory id: '<path of the id>/TEST', and there its feature by name.

    leaf        IMPLEMENTED where a run is linked, else OPEN; the verdict ok
                where every linked run passes. A leaf whose directory or
                name stands nowhere is OPEN (the detector names it).
    aggregate   folded from the claims below it ('aggregate_state').

ASKED BELOW THE TOP, the view holds the leaves whose TEST directory stands
at or below the directory asked, under the aggregates that hold them; an
aggregate with none of them is left out. Asked at the top, every aggregate
stands, an empty one OPEN.

EFFECTIVE KEYS of a leaf: its own, those of its TEST file, those of every
aggregate above it. The directory nesting adds none.

A LINK BY INTERNAL ID (the book's D-8) is resolved here, where the ids
are known: '<directory id>:<name>' from any TEST directory of the
relation adds its run to that leaf, the run carrying its own TEST
directory ('CRun.path'). One that does not resolve -- an id in no
'directory_map' line, a name its directory does not define, a retired
leaf -- stands in 'foreign_outside'. A link never changes a verdict.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from dataclasses import replace

from .feature_registry import (read_registry, CLeaf, CAggregate,
                               leaf_state, aggregate_state, IMPLEMENTED,
                               OPEN, OK, FAIL, UNTESTED, leaf_list,
                               retired_internal_set)
from .feature_relation import (relation_of_tree, read_feature_file,
                               CRun, TEST_NAME)
from .tree_explorer    import root_conf_directory
from .finder           import REGISTRY_FILE_NAME


class ViewRefused(Exception):
    """No view: no central file stands at the top, or it states a fault.
    The text says which, and what to do."""


@dataclass(frozen=True)
class CLeafView:
    """One leaf of the view. 'test_path' is its TEST directory relative to
    the directory asked (the relation's key), None where it is not in the
    relation; 'feature_state' the relation's CFeatureState of it, None where
    its TEST directory defines it not."""
    leaf:           CLeaf
    tree_path:      str                 # the aggregates above, '/'; ''
    directory_path: str | None          # the id's path below the top
    test_path:      str | None
    feature_state:  object | None
    key_tuple:      tuple               # effective keys, sorted
    state:          object              # CState


@dataclass(frozen=True)
class CAggregateView:
    """One aggregate of the view, the claims below it in file order (those
    in the view), its folded state and its counts."""
    aggregate:   CAggregate
    tree_path:   str
    child_tuple: tuple                  # of CAggregateView | CLeafView
    state:       object                 # CState
    count_db:    dict                   # IMPLEMENTED, OPEN, OK, FAIL, UNTESTED -> n


@dataclass(frozen=True)
class CView:
    """The view of one tree: the aggregates and the unplaced leaves, the
    retired claims, the relation it was joined with, and where it was
    asked."""
    relation:     object                # CRelation
    registry:     object                # CRegistry
    top_tuple:    tuple                 # of CAggregateView (file order)
    unplaced:     tuple                 # of CLeafView
    top:          str                   # the directory holding the root conf
    asked:        str                   # the directory asked, absolute
    foreign_outside: tuple = ()         # of (test path, test, choice,
                                        #  internal id, why): the links by
                                        #  internal id that do not resolve

    def leaf_list(self):
        """RETURN: list of CLeafView, every leaf of the view: the tree's in
        file order, then the unplaced."""
        result = []

        def walk(child_tuple):
            for each in child_tuple:
                if isinstance(each, CLeafView): result.append(each)
                else:                           walk(each.child_tuple)

        walk(self.top_tuple)
        return result + list(self.unplaced)

    def count_db(self):
        """RETURN: dict, IMPLEMENTED, OPEN, OK, FAIL, UNTESTED -> how many leaves of
        the view stand so."""
        return _count_of(self.leaf_list())

    def leaf_of_feature(self, test_path, name):
        """
        RETURN: CLeafView, the leaf the feature 'name' of the TEST directory
                'test_path' is registered as
                None, it is registered as none
        """
        for each in self.leaf_list():
            if each.test_path == test_path and each.leaf.name == name:
                return each
        return None


def _count_of(leaf_list):
    """RETURN: dict, IMPLEMENTED, OPEN, OK, FAIL, UNTESTED -> how many of the leaves
    stand so."""
    count_db = dict.fromkeys((IMPLEMENTED, OPEN, OK, FAIL, UNTESTED), 0)
    for each in leaf_list:
        count_db[each.state.implementation] += 1
        count_db[each.state.verdict] += 1
    return count_db


def view_of(directory):
    """
    RETURN: CView, the features of the tree 'directory' stands in, as the
            central file groups them, below 'directory'.

    RAISES: RootConfMissing, where no root bounds the tree; ViewRefused,
            where no 'hwut-root-features.conf' stands at the top, or it
            states a fault -- the text names the file and the remedy.
    """
    asked    = os.path.abspath(directory)
    top      = root_conf_directory(asked)
    registry = read_registry(top)
    if registry is None:
        raise ViewRefused("no '%s' stands at '%s' => hwut.features.init"
                          % (REGISTRY_FILE_NAME, top))
    if registry.fault_tuple:
        raise ViewRefused("'%s' cannot be read: %s"
                          % (REGISTRY_FILE_NAME,
                             "; ".join(str(f) for f in registry.fault_tuple)))
    relation = relation_of_tree(asked)
    whole_f  = os.path.normpath(asked) == os.path.normpath(top)
    foreign_db, foreign_outside = _foreign_of(relation, registry, top)

    def leaf_view(leaf, tree_path, key_above):
        directory_line = registry.directory_of_id(leaf.directory_id)
        path = None if directory_line is None else directory_line.path
        test_path, state_found = None, None
        if path is not None:
            relative = os.path.relpath(os.path.join(top, path, TEST_NAME),
                                       asked).replace(os.sep, "/")
            if relative == ".." or relative.startswith("../"):
                return None
            test_path = relative
            test_directory = relation.test_directory_db.get(relative)
            if test_directory is not None:
                state_found = next((each for each in test_directory
                                    .state_tuple
                                    if each.feature.name == leaf.name), None)
        elif not whole_f:
            return None
        if state_found is not None and leaf.internal in foreign_db:
            state_found = replace(state_found, run_tuple=(
                state_found.run_tuple + tuple(foreign_db[leaf.internal])))
        key_set = set(key_above)
        if state_found is not None:
            key_set |= set(state_found.feature.key_tuple)
            feature_file = relation.test_directory_db[test_path].feature_file
            if feature_file is not None:
                key_set |= set(feature_file.key_tuple)
        verdict_tuple = () if state_found is None else tuple(
            run.verdict for run in state_found.run_tuple)
        return CLeafView(leaf, tree_path, path, test_path, state_found,
                         tuple(sorted(key_set)), leaf_state(verdict_tuple))

    def aggregate_view(aggregate, tree_path, key_above):
        here    = tree_path + "/" + aggregate.key if tree_path \
                  else aggregate.key
        key_now = key_above + tuple(k for k in aggregate.key_tuple
                                    if k not in key_above)
        child_list = []
        for each in aggregate.child_tuple:
            found = leaf_view(each, here, key_now) \
                    if isinstance(each, CLeaf) \
                    else aggregate_view(each, here, key_now)
            if found is not None: child_list.append(found)
        if not child_list and not whole_f: return None
        leaf_list = _leaves(child_list)
        return CAggregateView(aggregate, here, tuple(child_list),
                              aggregate_state(tuple(each.state
                                                    for each in child_list)),
                              _count_of(leaf_list))

    top_list, unplaced = [], []
    for each in registry.tree_tuple:
        if isinstance(each, CLeaf):
            found = leaf_view(each, "", ())
            if found is not None: unplaced.append(found)
        else:
            found = aggregate_view(each, "", ())
            if found is not None: top_list.append(found)
    return CView(relation, registry, tuple(top_list), tuple(unplaced),
                 top, asked, foreign_outside)


#  WHY A LINK BY INTERNAL ID DOES NOT RESOLVE, as the page says it.
FOREIGN_NO_ID      = "no directory id"
FOREIGN_UNDEFINED  = "not defined in its directory"
FOREIGN_RETIRED    = "a retired feature"


def _foreign_of(relation, registry, top):
    """
    RETURN: [0] dict, internal id -> list of CRun: the runs linking a live
                leaf by its internal id, each with its own TEST directory
            [1] tuple of (test path, test, choice, internal id, why), the
                links that do not resolve, in walk order
    """
    live     = {leaf.internal for _, leaf in leaf_list(registry)}
    retired  = retired_internal_set(registry)
    defined  = {}                     # directory id -> names, read once
    found_db, outside = {}, []
    for path in sorted(relation.test_directory_db):
        each = relation.test_directory_db[path]
        for test, choice, internal in each.foreign_tuple:
            directory_id, _, name = internal.partition(":")
            line = registry.directory_of_id(directory_id)
            why  = None
            if internal in retired:
                why = FOREIGN_RETIRED
            elif line is None:
                why = FOREIGN_NO_ID
            else:
                if directory_id not in defined:
                    feature_file = read_feature_file(
                        os.path.join(top, line.path, TEST_NAME))
                    defined[directory_id] = set() if feature_file is None \
                        else {f.name for f in feature_file.feature_tuple}
                if name not in defined[directory_id] or internal not in live:
                    why = FOREIGN_UNDEFINED
            if why is not None:
                outside.append((path, test, choice, internal, why))
                continue
            found_db.setdefault(internal, []).append(
                CRun(test, choice, each.verdict_db[(test, choice)], path))
    return found_db, tuple(outside)


def view_kept(view, keep_f):
    """
    RETURN: CView, 'view' with only the leaves for which 'keep_f(leaf
            view)' is true -- every aggregate that keeps none dropped, the
            others folded and counted anew over what they keep -- and no
            retired claims: a cut names live claims only.
    """
    def kept(child_tuple):
        result = []
        for each in child_tuple:
            if isinstance(each, CLeafView):
                if keep_f(each): result.append(each)
                continue
            child_list = kept(each.child_tuple)
            if not child_list: continue
            result.append(CAggregateView(
                each.aggregate, each.tree_path, tuple(child_list),
                aggregate_state(tuple(c.state for c in child_list)),
                _count_of(_leaves(child_list))))
        return result

    registry = replace(view.registry, retired_tuple=())
    return CView(view.relation, registry, tuple(kept(view.top_tuple)),
                 tuple(each for each in view.unplaced if keep_f(each)),
                 view.top, view.asked, view.foreign_outside)


def _leaves(child_list):
    """RETURN: list of CLeafView, every leaf at and below 'child_list'."""
    result = []
    for each in child_list:
        if isinstance(each, CLeafView): result.append(each)
        else:                           result += _leaves(each.child_tuple)
    return result
