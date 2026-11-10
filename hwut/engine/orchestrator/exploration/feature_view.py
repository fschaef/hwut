"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURES OF A TREE, joined with the test runs that prove them
         (spec 43 section 4) -- what 'hwut.report.features', the feature
         document, the faces of the features and the label 'f/<id>' read.

    features_of(directory)   -> CFeatures  the three files, read and checked
    view_of(directory)       -> CView      the files joined with the links
    view_kept(view, id_set)  -> CView      cut to some features' subtrees
    feature_label_case_set(root, name)     the runs of 'f/<id>'

THE THREE FILES stand beside the 'hwut-root.conf' that begins the features
of the tree ('tree_explorer.forest_top'): 'hwut-feature-forest.csv', the
place; 'hwut-feature-doc.dat', the explanation; 'hwut-feature-external-
map.csv', the outside's names. THE LINKS are the relation's
('feature_relation', the test headers' 'features = [...]'), read over the
whole tree below the top, whichever directory is asked: a feature has no
directory (t-1), so the directory asked cuts nothing of the page; it only
says from where the paths are written (spec 43 section 5, t-13).

KNOWN IDS: those of the forest's lines and those the doc file documents,
the retired excepted. A documented id in no forest line is UNPLACED -- a
promise with no place. A link to an id that is not known stands OUTSIDE
THE RELATION; so does a link to a retired one.

THE STATES (HOWTO-FEATURES section 1, spec 43 section 4): a feature folds
ITS OWN RUNS AND ITS CHILDREN'S (T-n, t-2). IMPLEMENTED where it has runs
or children and no child is OPEN; OPEN else. Its verdict is the worst
below it: fail, then untested, then ok. A feature with neither children
nor runs is OPEN untested. RETIRED has no verdict. The COUNTS are those of
the features with no children, as they were the leaves'.
______________________________________________________________________________
"""
import fnmatch
import os
from   dataclasses import dataclass, field

from .feature_forest   import read_forest, ForestFault
from .feature_doc      import read_doc, DocFault, effective_entry
from .feature_external import read_external, ExternalFault
from .feature_relation import (relation_of_tree, PASS, NO_VERDICT)
from .finder           import FOREST_FILE_NAME
from .suggestion       import did_you_mean
from .tree_explorer    import forest_top

#  THE IMPLEMENTATION AXIS and the verdict beside it.
IMPLEMENTED = "IMPLEMENTED"
OPEN        = "OPEN"
RETIRED     = "RETIRED"
OK          = "ok"
FAIL        = "fail"
UNTESTED    = "untested"          # no verdict measured (ruled 2026-10-17)

#  WHY A LINK STANDS OUTSIDE THE RELATION, as the page says it.
OUTSIDE_UNKNOWN = "stands in no forest line and no doc block"
OUTSIDE_RETIRED = "a retired feature"
OUTSIDE_MEMBER  = "a member of a prototype -- link '<owner>+<id>'"
OUTSIDE_PROTOTYPE = "a prototype -- no feature, link one of its instances"

#  WHAT MAKES A WORD OF 'f/' A GLOB (intend/44 P-g).
GLOB_CHARACTER_SET = frozenset("*?[")


class ViewRefused(Exception):
    """No features: no forest stands at the top, or one of the three files
    states a fault. The text says which, and what to do."""


@dataclass(frozen=True)
class CState:
    """A claim's state on the two axes. 'implementation' is IMPLEMENTED,
    OPEN or RETIRED; 'verdict' is OK, FAIL or UNTESTED, None where
    RETIRED. THE AXES ARE INDEPENDENT (ruled 2026-10-17): an open claim
    has no measured verdict -- it is UNTESTED, not FAIL."""
    implementation: str
    verdict:        str | None


def _verdict_folded(verdict_list):
    """RETURN: str, the worst of 'verdict_list': FAIL where one fails,
    else UNTESTED where one is untested, else OK."""
    if FAIL in verdict_list:     return FAIL
    if UNTESTED in verdict_list: return UNTESTED
    return OK


def feature_state(run_verdict_tuple, child_state_tuple):
    """RETURN: CState, the state of a feature whose own linked runs have
    the verdicts 'run_verdict_tuple' (PASS, FAIL, NO_VERDICT, ...) and
    whose children stand in 'child_state_tuple': neither -- OPEN
    untested; else OPEN where a child is OPEN, IMPLEMENTED otherwise; the
    verdict the worst of the runs' and the children's."""
    if not run_verdict_tuple and not child_state_tuple:
        return CState(OPEN, UNTESTED)
    verdict_list = [OK if each == PASS else UNTESTED if each == NO_VERDICT
                    else FAIL for each in run_verdict_tuple] \
                   + [each.verdict for each in child_state_tuple]
    implementation = OPEN if any(each.implementation == OPEN
                                 for each in child_state_tuple) \
                     else IMPLEMENTED
    return CState(implementation, _verdict_folded(verdict_list))


def retired_state():
    """RETURN: CState, the state of a retired claim: RETIRED, no verdict."""
    return CState(RETIRED, None)


@dataclass(frozen=True)
class CFeatures:
    """The three files of one top, read and checked against each other.
    'doc' is None where no doc file stands, 'external_db' empty where no
    map does."""
    top:         str
    forest:      object                 # CForest
    doc:         object | None          # CDoc
    external_db: dict = field(default_factory=dict)

    def known_set(self):
        """RETURN: frozenset of str, every id a link and 'f/<id>' may
        name: the forest's -- instances included -- and the documented
        features, not the retired; no prototype, no bare member."""
        return frozenset(set(self.forest.id_set) | set(self.unplaced_tuple()))

    def unplaced_tuple(self):
        """RETURN: tuple of str, the documented features in no forest
        line, doc order: no prototype, no member, no instance."""
        if self.doc is None: return ()
        return tuple(each for each in self.doc.entry_db
                     if each not in self.forest.id_set
                     and not each.startswith("+") and "+" not in each
                     and not self.forest.prototype_f(each))

    def retired_set(self):
        """RETURN: frozenset of str, the ids of the retired blocks."""
        return frozenset(self.doc.retired_db) if self.doc else frozenset()

    def retired_f(self, feature_id):
        """RETURN: True, 'feature_id' is retired, or an instance of a
        retired member ('<owner>+<member>'); False else."""
        retired = self.retired_set()
        return feature_id in retired \
               or ("+" in feature_id and feature_id.partition("+")[2] in retired)

    def entry_of(self, feature_id):
        """
        RETURN: CDocEntry, the block documenting 'feature_id' -- for an
                instance, its own or its member's or prototype's
                ('feature_doc.effective_entry')
                None, none does
        """
        if self.doc is None: return None
        return effective_entry(self.doc.entry_db, self.forest, feature_id)


def features_of(directory):
    """
    RETURN: CFeatures, the three files governing the tree 'directory'
            stands in.

    RAISES: RootConfMissing, where no root bounds the tree; ViewRefused,
            where no forest stands at the top, or a file states a fault --
            the text names the file and the remedy.
    """
    top = forest_top(os.path.abspath(directory))
    try:
        forest = read_forest(top)
        if forest is None:
            raise ViewRefused("no '%s' stands at '%s' => hwut.features.init"
                              % (FOREST_FILE_NAME, top))
        doc         = read_doc(top, forest)
        external_db = read_external(top, forest) or {}
    except (ForestFault, DocFault, ExternalFault) as fault:
        raise ViewRefused(str(fault)) from fault
    return CFeatures(top, forest, doc, external_db)


@dataclass(frozen=True)
class CNode:
    """One feature of the view: its id, the ids above it ('tree_path',
    '/' between, its own last), its doc block (None: undocumented), its
    own linked runs, its children in forest order, its state, the counts
    of the childless features at and below it, its audiences and the
    outside's names for it."""
    id:             str
    tree_path:      str
    entry:          object | None        # CDocEntry
    run_tuple:      tuple                # of CRun, its own
    child_tuple:    tuple                # of CNode
    state:          CState
    count_db:       dict
    audience_tuple: tuple = ()
    external_tuple: tuple = ()


@dataclass(frozen=True)
class CView:
    """The view of one tree: the roots of the forest (file order), the
    unplaced -- documented, in no forest line -- the retired blocks, the
    links outside the relation, the relation joined, the files, where the
    top stands and where the view was asked."""
    relation:        object              # CRelation
    features:        CFeatures
    root_tuple:      tuple               # of CNode
    unplaced:        tuple               # of CNode
    retired_tuple:   tuple               # of CDocEntry, file order
    outside_tuple:   tuple               # of (path, test, choice, id, why)
    top:             str
    asked:           str

    def node_list(self):
        """RETURN: list of CNode, every feature of the view, the parent
        before its children: the forest's, then the unplaced."""
        result = []

        def walk(node_tuple):
            for each in node_tuple:
                result.append(each)
                walk(each.child_tuple)

        walk(self.root_tuple)
        walk(self.unplaced)
        return result

    def node_of(self, feature_id):
        """
        RETURN: CNode, the feature 'feature_id' of the view
                None, the view holds none
        """
        for each in self.node_list():
            if each.id == feature_id: return each
        return None

    def count_db(self):
        """RETURN: dict, IMPLEMENTED, OPEN, OK, FAIL, UNTESTED -> how many
        childless features of the view stand so."""
        return _count_of([each for each in self.node_list()
                          if not each.child_tuple])

    def run_path(self, run):
        """RETURN: str, the TEST directory of 'run', addressed from the
        directory the view was asked in ('/' between; '.' itself)."""
        return os.path.relpath(os.path.join(self.top, run.path),
                               self.asked).replace(os.sep, "/")


def _count_of(node_list):
    """RETURN: dict, IMPLEMENTED, OPEN, OK, FAIL, UNTESTED -> how many of
    the nodes stand so."""
    count_db = dict.fromkeys((IMPLEMENTED, OPEN, OK, FAIL, UNTESTED), 0)
    for each in node_list:
        count_db[each.state.implementation] += 1
        count_db[each.state.verdict] += 1
    return count_db


def view_of(directory):
    """
    RETURN: CView, the features of the tree 'directory' stands in, joined
            with every link below their top; paths written from
            'directory'.

    RAISES: RootConfMissing, where no root bounds the tree; ViewRefused,
            as 'features_of' says.
    """
    asked    = os.path.abspath(directory)
    features = features_of(asked)
    relation = relation_of_tree(features.top)
    return _view_joined(features, relation, asked)


def _view_joined(features, relation, asked):
    """RETURN: CView, 'features' joined with 'relation' (asked at the
    top), as asked from 'asked'."""
    forest, doc = features.forest, features.doc
    run_db      = relation.run_db()
    known       = features.known_set()
    audience_db = doc.audience_db if doc else {}

    def node(feature_id, above):
        here       = above + "/" + feature_id if above else feature_id
        child_list = [node(each, here)
                      for each in forest.children_of.get(feature_id, ())]
        run_tuple  = run_db.get(feature_id, ())
        state      = feature_state(tuple(run.verdict for run in run_tuple),
                                   tuple(each.state for each in child_list))
        leaf_list  = []
        for each in child_list:
            leaf_list += _childless(each)
        count_db = _count_of(leaf_list) if child_list else _count_of(
            [CNode(feature_id, here, None, (), (), state, {})])
        return CNode(feature_id, here, features.entry_of(feature_id),
                     run_tuple, tuple(child_list), state, count_db,
                     audience_db.get(feature_id, ()),
                     features.external_db.get(feature_id, ()))

    root_tuple = tuple(node(each, "") for each in forest.root_tuple)
    unplaced   = tuple(node(each, "") for each in features.unplaced_tuple())
    outside = []
    for path in sorted(relation.test_directory_db):
        each = relation.test_directory_db[path]
        for test, choice, feature_id in each.link_tuple:
            if feature_id in known: continue
            why = OUTSIDE_RETIRED if features.retired_f(feature_id) \
                  else OUTSIDE_PROTOTYPE \
                  if feature_id.lstrip("+") in forest.prototype_db \
                  else OUTSIDE_MEMBER if feature_id in forest.member_of \
                  else OUTSIDE_UNKNOWN + did_you_mean(feature_id, sorted(known))
            outside.append((path, test, choice, feature_id, why))
    return CView(relation, features, root_tuple, unplaced,
                 tuple(doc.retired_db.values()) if doc else (),
                 tuple(outside), features.top, asked)


def _childless(node):
    """RETURN: list of CNode, the childless features at and below
    'node'."""
    if not node.child_tuple: return [node]
    result = []
    for each in node.child_tuple:
        result += _childless(each)
    return result


def view_kept(view, id_set):
    """
    RETURN: CView, 'view' cut to the subtrees of the ids 'id_set' (T-u):
            each kept with everything below it, the features above it as
            headers -- folded and counted over what is kept -- several a
            union; no unplaced but those named, no retired, no outside.
    """
    def kept(node_tuple):
        result = []
        for each in node_tuple:
            if each.id in id_set:
                result.append(each)
                continue
            child_list = kept(each.child_tuple)
            if not child_list: continue
            leaf_list = []
            for child in child_list: leaf_list += _childless(child)
            result.append(CNode(
                each.id, each.tree_path, each.entry, (), tuple(child_list),
                feature_state((), tuple(c.state for c in child_list)),
                _count_of(leaf_list), each.audience_tuple,
                each.external_tuple))
        return result

    return CView(view.relation, view.features, tuple(kept(view.root_tuple)),
                 tuple(each for each in view.unplaced if each.id in id_set),
                 (), (), view.top, view.asked)


# -- the label 'f/<id>' ------------------------------------------------------

_feature_label_db = {}


def forget_views():
    """RETURN: None. Drops every feature label answered so far -- for a
    test that rebuilds a tree under one path."""
    _feature_label_db.clear()


def feature_label_case_set(root, name, strict_f=True):
    """
    RETURN: frozenset of (absolute test file, choice), the runs linked to
            the feature the label 'name' ('f/<id>', plan/label) names, or
            to any feature below it in the forest -- if success;
            raises SelectionError, else: no readable forest, a RETIRED
            feature, or ('strict_f') an id that is not known. Not strict,
            an unknown feature holds no run: a derived label of
            'hwut-root.labels' naming it must not refuse every selection
            that never asks for it.
    """
    from .task_list     import SelectionError
    from .tree_explorer import RootConfMissing, forest_inner_tuple
    root = os.path.abspath(root)
    mark = (root, name, strict_f)
    if mark in _feature_label_db: return _feature_label_db[mark]
    feature_id = name[2:]
    #  EVERY FOREST ANSWERS FOR ITS OWN RUNS (services E-200): the one
    #  above the root, and every bubble below with a forest of its own.
    #  A refusal stands where none knows the id.
    case_set, known, error = frozenset(), set(), None
    glob_f = bool(GLOB_CHARACTER_SET & set(feature_id))
    matched = False
    if feature_id.startswith("+"):
        raise SelectionError("'%s': a prototype names no instance -- "
                             "'f/*%s', every instance of it"
                             % (name, feature_id))
    for top in (root,) + forest_inner_tuple(root):
        try:
            features = features_of(top)
        except (ViewRefused, RootConfMissing) as refusal:
            error = error or SelectionError("'%s' asks for a feature: %s"
                                            % (name, refusal))
            continue
        if not glob_f and features.retired_f(feature_id):
            raise SelectionError("'%s' names a RETIRED feature: no longer "
                                 "claimed, no run proves it any more"
                                 % name)
        if not glob_f and features.forest.prototype_f(feature_id):
            raise SelectionError("'%s' names a member of a prototype, no "
                                 "feature -- 'f/<owner>+%s', or "
                                 "'f/*+%s' for every instance"
                                 % (name, feature_id, feature_id))
        own = features.known_set()
        known |= own
        wanted_id = [each for each in own
                     if fnmatch.fnmatchcase(each, feature_id)] if glob_f \
                    else ([feature_id] if feature_id in own else [])
        if not wanted_id: continue
        matched  = True
        relation = relation_of_tree(features.top)
        wanted   = set()
        for each in wanted_id:
            wanted |= set(features.forest.subtree_tuple(each))
        case_set |= frozenset(
            (os.path.normpath(os.path.join(features.top, path, test)),
             choice)
            for path, each in relation.test_directory_db.items()
            for test, choice, linked in each.link_tuple if linked in wanted)
    if not matched and strict_f:
        if error is not None and not known: raise error
        if glob_f:
            raise SelectionError(
                "'%s' matches no feature: no id of '%s' or of the doc file "
                "fits the glob => hwut.features.tree --list"
                % (name, FOREST_FILE_NAME))
        raise SelectionError(
            "'%s' names no feature: '%s' stands in no line of '%s' and no "
            "block of the doc file => hwut.features.tree --list%s"
            % (name, feature_id, FOREST_FILE_NAME,
               did_you_mean(feature_id, sorted(known))))
    _feature_label_db[mark] = case_set
    return case_set


def outside_link_list(directory):
    """
    RETURN: list of (path, test, choice, feature id), every link of a test
            run at or below 'directory' -- the path its TEST directory,
            relative to 'directory' -- to an id that stands in no forest
            line and no doc block, or a retired one; [] where no forest
            governs the tree. Only the runs below are read: cheap enough
            for the end of every 'hwut.run'.

    Raises RootConfMissing where no root bounds the tree, ViewRefused
    where a feature file states a fault.
    """
    try:
        features = features_of(directory)
    except ViewRefused as refusal:
        if "=> hwut.features.init" in str(refusal): return []
        raise
    known    = features.known_set()
    relation = relation_of_tree(os.path.abspath(directory))
    return [(path, test, choice, feature_id)
            for path in sorted(relation.test_directory_db)
            for test, choice, feature_id
            in relation.test_directory_db[path].link_tuple
            if feature_id not in known]


def unproven_by_removal(directory, test, choice=None):
    """
    RETURN: tuple of str, the known features left without a linked run
            where 'test' of the TEST directory 'directory' -- one 'choice'
            of it where one is named, every choice else -- is removed:
            linked by what goes, by no other run below the forest's top.
            Sorted; empty where no forest stands or the test links none.
    """
    from .tree_explorer import RootConfMissing
    try:
        features = features_of(directory)
    except (ViewRefused, RootConfMissing):
        return ()
    here = os.path.normpath(os.path.abspath(directory))
    going, staying = set(), set()
    for path, each in relation_of_tree(features.top).test_directory_db.items():
        same = os.path.normpath(os.path.join(features.top, path)) == here
        for app, app_choice, feature_id in each.link_tuple:
            if same and app == test \
               and (choice is None or app_choice == choice):
                going.add(feature_id)
            else:
                staying.add(feature_id)
    known = features.known_set()
    return tuple(sorted(each for each in going - staying if each in known))
