"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE RELATION -- what a tree claims to do, and which test
         runs prove it. The three kinds of statement, read:

    <component>/hwut-composition.conf     what the component does, and
                                          what each part contributes
    <component>/TEST/hwut-features.conf   the features proven in that
                                          TEST directory
    a test's '@hwut { }' block            'features = [...]': the
                                          features the test run proves

    read_feature_file(directory)   -> CFeatureFile | None
    read_composition(directory)    -> CComposition | None
    relation_of_tree(root)         -> CRelation

THE FEATURE FILE

    features {
        id     = "core-proof"
        parent { core = "What 'core' promises, proven." }
        issued = 2
        1 { name        = "line-pairing"
            title       = "Two streams are aligned line by line."
            explanation = "..." }
    }

    An entry whose key is a NUMBER is a feature, the number its id.
    'issued' is the highest number the file ever issued; the scope
    counts from 1 ('bookkeeper' IdScope). An OBJECT under any other key
    but 'parent' is a feature WITHOUT a number. A number standing twice
    is the parser's fault ('duplicate key'): the first stands.

THE COMPOSITION FILE

    component {
        id     = "cmp"
        title  = "Compare"
        does   = "Decides whether an output is equivalent to its nominal."
        parent { eng = "The engine's verdict rests on it." }
        childs {
            core       = "Aligns two streams line by line."
            cmp-proof  = "Proves the whole comparison on real pages."
        }
    }

IDS, 'parent' AND 'childs'
    Each statement file gives ITSELF an 'id': a freely chosen string,
    unique among the childs of its parent. The files relate to each
    other by these ids and by nothing else -- no path is written:

        parent    the id of the statement file of the DIRECTORY ABOVE
                  (its 'hwut-composition.conf'), and how this one
                  serves it:   parent { <id> = "<sentence>" }
                  or, without the sentence:   parent = "<id>"
        childs    the ids of the statement files in the DIRECTORIES
                  DIRECTLY BELOW -- components and the TEST directory's
                  feature file -- and what each contributes:
                      childs { <id> = "<sentence>" ... }
                  or, without sentences:   childs = ["<id>", ...]

    Every relation is so stated twice, and the directories state it a
    third time by where they stand. 'mismatch_list()' compares the
    three; 'feature_adapt.py' adapts the statements to the directories.

THE RELATION
    A feature id means something inside its own file only. A feature is
    addressed as '<path>#<number> <name>', a test run as
    '<path>/<test> [<choice>]', the path RELATIVE to the root asked --
    composed here, at the moment of asking, and stored nowhere.

    state of a feature
        PROVEN     one linked test run or more; all of them pass
        FAILING    one linked test run or more; one of them does not
                   pass, or has no verdict in 'GOOD/book.csv'
        UNPROVEN   no linked test run

    A name is looked up in the feature file of the test's own TEST
    directory and nowhere else.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from vut.test_writing_support.python import hwut_hocon
from vut.test_writing_support.python.hwut_hocon import (ScalarNode,
                                                        ListNode,
                                                        ObjectNode)
from ...bookkeeper.api import (Bookkeeper, ID_LIMIT, IdScope,
                               number_of_decimal)
from .                 import unwrapper
from .fault            import Fault, E_FaultKind, Position
from .finder           import (COMPOSITION_FILE_NAME,       # noqa: F401
                               FEATURE_FILE_NAME, ROOT_CONF_NAME)
from vut.auxiliary.no_entry import entered
from .tree_explorer    import explore_tree_stream



PROVEN   = "PROVEN"
FAILING  = "FAILING"
UNPROVEN = "UNPROVEN"
STATE_TUPLE = (PROVEN, FAILING, UNPROVEN)

#  WHAT THE BOOK SAYS OF A LINKED RUN, as the relation spells it.
PASS       = "PASS"
FAIL       = "FAIL"
NO_VERDICT = "NO VERDICT"


@dataclass(frozen=True)
class CFeature:
    """One feature of one feature file. 'number' is None where the entry
    carries none; 'name' is None where it states none."""
    number:      int | None
    name:        str | None
    title:       str | None = None
    explanation: str | None = None
    key:         str        = ""       # the entry's key, as written
    line_n:      int        = 0


@dataclass(frozen=True)
class CFeatureFile:
    """What one 'hwut-features.conf' states. 'issued' is None where the
    file states none, or one that spells no mark."""
    id:            str | None = None
    parent_id:     str | None = None
    parent_text:   str | None = None   # how it serves its parent
    issued:        int | None = None
    feature_tuple: tuple      = ()     # of CFeature, file order
    fault_tuple:   tuple      = ()     # of Fault
    child_tuple:   tuple      = ()     # a feature file has no childs

    def feature_of_name(self, name):
        """
        RETURN: CFeature, the feature called 'name'
                None, else
        """
        for feature in self.feature_tuple:
            if feature.name == name: return feature
        return None

    def name_tuple(self):
        """RETURN: tuple of str, every feature name the file defines, in
        file order."""
        return tuple(feature.name for feature in self.feature_tuple
                     if feature.name is not None)

    def scope(self):
        """RETURN: IdScope, the feature scope of this file: counting
        from 1, its mark the higher of 'issued' and the highest number
        a feature carries -- so 'allocate()' never issues a number the
        file holds."""
        scope = IdScope("the feature scope", first=1)
        if self.issued is not None: scope.raise_to(self.issued)
        for feature in self.feature_tuple:
            if feature.number is not None: scope.raise_to(feature.number)
        return scope


@dataclass(frozen=True)
class CComposition:
    """What one 'hwut-composition.conf' states. 'child_tuple' holds
    (child id, what it contributes), file order; the sentence is None
    where 'childs' is written as a list."""
    id:          str | None = None
    title:       str | None = None
    does:        str | None = None
    parent_id:   str | None = None
    parent_text: str | None = None     # how it serves its parent
    child_tuple: tuple      = ()
    fault_tuple: tuple      = ()

    def child_id_tuple(self):
        """RETURN: tuple of str, the ids 'childs' lists, file order."""
        return tuple(child_id for child_id, _ in self.child_tuple)

    def child_text(self, child_id):
        """
        RETURN: str, what the child with that id contributes, as stated
                None, 'childs' does not list it, or states no sentence
        """
        for listed_id, text in self.child_tuple:
            if listed_id == child_id: return text
        return None


def read_feature_file(directory):
    """
    RETURN: CFeatureFile, what 'directory/hwut-features.conf' states
            None, no such file stands
    """
    text = _text_of(os.path.join(directory, FEATURE_FILE_NAME))
    if text is None: return None
    return feature_file_of_text(text, FEATURE_FILE_NAME)


def read_composition(directory):
    """
    RETURN: CComposition, what 'directory/hwut-composition.conf' states
            None, no such file stands
    """
    text = _text_of(os.path.join(directory, COMPOSITION_FILE_NAME))
    if text is None: return None
    return composition_of_text(text, COMPOSITION_FILE_NAME)


def _text_of(path):
    """
    RETURN: str, the file's text
            None, no such file stands
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _outer_node(text, file, outer_key, fault_list):
    """
    RETURN: ObjectNode, the object behind the file's one outer key
            'outer_key'
            None, else -- a fault says what stands instead
    """
    document, parse_fault_list = hwut_hocon.parse(
        unwrapper.plain_lines(text), file)
    fault_list.extend(
        Fault(E_FaultKind[f.kind.name], f.file,
              Position(f.position.line, f.position.column), f.message)
        for f in parse_fault_list)
    found = None
    for entry in document.entry_list if document is not None else ():
        if entry.key == outer_key and isinstance(entry.node, ObjectNode):
            found = entry.node
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "the outer node is '%s { }'; not '%s'"
                % (outer_key, entry.key)))
    if found is None and not fault_list:
        fault_list.append(Fault(E_FaultKind.VOCABULARY, file, None,
                                "no '%s { }' stands" % outer_key))
    return found


def _sentence(entry, file, fault_list):
    """
    RETURN: str, the text the entry states
            None, it states no text (fault recorded)
    """
    node = entry.node
    if isinstance(node, ScalarNode) and isinstance(node.value, str):
        return node.value
    fault_list.append(Fault(E_FaultKind.TYPE, file, entry.key_position,
                            "'%s' must be a text" % entry.key))
    return None


def _id(entry, file, fault_list):
    """
    RETURN: str, the id the entry states: a text that is not empty
            None, else (fault recorded)
    """
    value = _sentence(entry, file, fault_list)
    if value is None: return None
    if not value.strip():
        fault_list.append(Fault(E_FaultKind.TYPE, file, entry.key_position,
                                "'id' is a text, and not an empty one"))
        return None
    return value


def _parent(entry, file, fault_list):
    """
    RETURN: (str, str | None), the parent's id and how this one serves
            it -- from  parent { <id> = "<sentence>" }  or
            parent = "<id>"
            (None, None), else (fault recorded)
    """
    node = entry.node
    if isinstance(node, ScalarNode) and isinstance(node.value, str) \
       and node.value.strip():
        return node.value, None
    if isinstance(node, ObjectNode) and len(node.entry_list) == 1:
        text = _sentence(node.entry_list[0], file, fault_list)
        return node.entry_list[0].key, text
    fault_list.append(Fault(
        E_FaultKind.TYPE, file, entry.key_position,
        "'parent' names ONE id: parent = \"<id>\", or "
        "parent { <id> = \"<how this serves it>\" }"))
    return None, None


def _childs(entry, file, fault_list):
    """
    RETURN: tuple of (str, str | None), child id and what it
            contributes -- from  childs { <id> = "<sentence>" ... }  or
            childs = ["<id>", ...]; an id standing twice is a fault and
            its first stands
    """
    node      = entry.node
    pair_list = []
    if isinstance(node, ObjectNode):
        for child in node.entry_list:
            text = _sentence(child, file, fault_list)
            pair_list.append((child.key, text))
    elif isinstance(node, ListNode) \
         and all(isinstance(item, ScalarNode) and isinstance(item.value, str)
                 for item in node.item_list):
        pair_list = [(item.value, None) for item in node.item_list]
    else:
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, entry.key_position,
            "'childs' lists ids: childs { <id> = \"<what it "
            "contributes>\" }, or childs = [\"<id>\", ...]"))
    result, seen_set = [], set()
    for child_id, text in pair_list:
        if child_id in seen_set:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "child id '%s' stands twice; the first stands" % child_id))
            continue
        seen_set.add(child_id)
        result.append((child_id, text))
    return tuple(result)


def feature_file_of_text(text, file=FEATURE_FILE_NAME):
    """RETURN: CFeatureFile, what 'text' states; every fault met stands
    in its 'fault_tuple', and what was readable beside it."""
    fault_list   = []
    outer        = _outer_node(text, file, "features", fault_list)
    own_id       = None
    parent_id    = None
    parent_text  = None
    issued       = None
    feature_list = []
    name_set     = set()
    scope        = IdScope("the feature scope", first=1)
    for entry in outer.entry_list if outer is not None else ():
        number = number_of_decimal(entry.key)
        if entry.key == "id":
            own_id = _id(entry, file, fault_list)
        elif entry.key == "parent":
            parent_id, parent_text = _parent(entry, file, fault_list)
        elif entry.key == "childs":
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "a feature file has no 'childs': its features are its "
                "numbered entries"))
        elif entry.key == "issued":
            node  = entry.node
            value = node.value if isinstance(node, ScalarNode) else None
            if isinstance(value, bool) or not isinstance(value, int) \
               or not scope.mark_of_text(value):
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, entry.key_position,
                    "'issued' is the highest feature number issued: "
                    "a number, 0 at least and below %i" % ID_LIMIT))
            else:
                issued = value
        elif isinstance(entry.node, ObjectNode):
            if number is not None and not 1 <= number < ID_LIMIT:
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, entry.key_position,
                    "feature number '%s': numbers count from 1"
                    % entry.key))
                continue
            feature = _feature(entry, number, file, fault_list)
            if feature.name is not None:
                if feature.name in name_set:
                    fault_list.append(Fault(
                        E_FaultKind.VOCABULARY, file, entry.key_position,
                        "feature name '%s' stands twice; the first "
                        "stands" % feature.name))
                    continue
                name_set.add(feature.name)
            feature_list.append(feature)
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "unknown key '%s' in 'features': 'id', 'parent', "
                "'issued', or a feature '<number> { }'" % entry.key))
    return CFeatureFile(own_id, parent_id, parent_text, issued,
                        tuple(feature_list), tuple(fault_list))


def _feature(entry, number, file, fault_list):
    """RETURN: CFeature, the entry's 'name', 'title' and 'explanation'
    under 'number'; an unknown key inside is a fault and is dropped."""
    field_db = {}
    for inner in entry.node.entry_list:
        if inner.key in ("name", "title", "explanation"):
            value = _sentence(inner, file, fault_list)
            if value is not None: field_db[inner.key] = value
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, inner.key_position,
                "unknown key '%s' in feature '%s': 'name', 'title', "
                "'explanation'" % (inner.key, entry.key)))
    return CFeature(number, field_db.get("name"), field_db.get("title"),
                    field_db.get("explanation"), entry.key,
                    entry.key_position.line)


def composition_of_text(text, file=COMPOSITION_FILE_NAME):
    """RETURN: CComposition, what 'text' states; every fault met stands
    in its 'fault_tuple', and what was readable beside it."""
    fault_list = []
    outer      = _outer_node(text, file, "component", fault_list)
    field_db    = {}
    own_id      = None
    parent_id   = None
    parent_text = None
    child_tuple = ()
    for entry in outer.entry_list if outer is not None else ():
        if entry.key == "id":
            own_id = _id(entry, file, fault_list)
        elif entry.key in ("title", "does"):
            value = _sentence(entry, file, fault_list)
            if value is not None: field_db[entry.key] = value
        elif entry.key == "parent":
            parent_id, parent_text = _parent(entry, file, fault_list)
        elif entry.key == "childs":
            child_tuple = _childs(entry, file, fault_list)
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "unknown key '%s' in 'component': 'id', 'title', 'does', "
                "'parent', 'childs'" % entry.key))
    return CComposition(own_id, field_db.get("title"), field_db.get("does"),
                        parent_id, parent_text, child_tuple,
                        tuple(fault_list))


# -- the relation -------------------------------------------------------

@dataclass(frozen=True)
class CRun:
    """One linked test run and what 'GOOD/book.csv' says of it:
    'PASS', 'FAIL', 'ASPIRANT' or 'NO VERDICT'."""
    test:    str
    choice:  str | None
    verdict: str


@dataclass(frozen=True)
class CFeatureState:
    """One feature, the test runs linked to it, and its state."""
    feature:   CFeature
    run_tuple: tuple                   # of CRun, walk order
    state:     str                     # PROVEN | FAILING | UNPROVEN


@dataclass(frozen=True)
class CTestDirectory:
    """One TEST directory in the relation. 'feature_file' is None where
    none stands. 'unlinked_tuple' holds the runs that link to no
    feature, 'undefined_tuple' the links whose name the directory does
    not define -- (test, choice, name)."""
    path:            str
    feature_file:    CFeatureFile | None
    state_tuple:     tuple = ()        # of CFeatureState, file order
    unlinked_tuple:  tuple = ()        # of (test, choice)
    undefined_tuple: tuple = ()        # of (test, choice, name)


@dataclass(frozen=True)
class CComponent:
    """One component in the relation: a directory that is no TEST
    directory. 'composition' is None where no file stands.
    'part_tuple' names its direct subdirectories that are components,
    'test_directory' its own TEST directory's path, or None."""
    path:           str
    composition:    CComposition | None
    part_tuple:     tuple = ()         # of str, paths, sorted
    test_directory: str | None = None


@dataclass(frozen=True)
class CRelation:
    """The feature relation of one tree: components and TEST
    directories by path, relative to the root asked, '/'-separated;
    '.' is the root itself."""
    component_db:      dict            # path -> CComponent
    test_directory_db: dict            # path -> CTestDirectory
    #  WHAT THE DIRECTORY ABOVE THE ROOT ASKED STATES: its composition,
    #  where the root asked is not the tree's own root and one stands.
    above:             CComposition | None = None
    #  True where the root asked is the tree's own ('hwut-root.conf'
    #  stands in it): it has no parent to state.
    top_f:             bool = True
    #  The name of the directory asked: what its statement file is
    #  called where it gives itself no id.
    root_name:         str  = ""

    def statement_of(self, path):
        """
        RETURN: CComposition | CFeatureFile, the statement file of the
                directory at 'path'
                None, it carries none, or 'path' is not in the relation
        """
        test_directory = self.test_directory_db.get(path)
        if test_directory is not None: return test_directory.feature_file
        component = self.component_db.get(path)
        return None if component is None else component.composition

    def statement_above(self, path):
        """
        RETURN: CComposition, what the directory above 'path' states
                None, it carries no composition file -- or 'path' is
                the top of the tree and has no directory above
        """
        above = parent_of(path)
        if above is None: return self.above
        component = self.component_db.get(above)
        return None if component is None else component.composition

    def below_tuple(self, path):
        """RETURN: tuple of str, the paths directly below the component
        at 'path' that are in the relation: its parts, then its own
        TEST directory."""
        component = self.component_db.get(path)
        if component is None: return ()
        return component.part_tuple + (
            () if component.test_directory is None
            else (component.test_directory,))

    def count_of(self, path):
        """RETURN: dict, state -> how many features stand in it at and
        below 'path' -- a component's own TEST directory and its
        parts', summed; a TEST directory's own."""
        count_db = dict.fromkeys(STATE_TUPLE, 0)
        test_directory = self.test_directory_db.get(path)
        if test_directory is not None:
            for each in test_directory.state_tuple:
                count_db[each.state] += 1
            return count_db
        component = self.component_db.get(path)
        if component is None: return count_db
        below_list = list(component.part_tuple)
        if component.test_directory is not None:
            below_list.append(component.test_directory)
        for below in below_list:
            for state, n in self.count_of(below).items():
                count_db[state] += n
        return count_db


def parent_of(path):
    """
    RETURN: str, the path of the directory above 'path'; '.' for a
            directory standing in the root
            None, 'path' is the root itself
    """
    if path == ".": return None
    head = path.rpartition("/")[0]
    return head or "."


def name_of(path):
    """RETURN: str, the directory's own name -- the last component of
    'path'."""
    return path.rpartition("/")[2]


def state_of(run_tuple):
    """RETURN: str, PROVEN where at least one run is linked and every
    one passes; FAILING where one is linked and one does not pass;
    UNPROVEN where none is linked."""
    if not run_tuple: return UNPROVEN
    if all(run.verdict == PASS for run in run_tuple): return PROVEN
    return FAILING


def _verdict_text(bookkeeper, test, choice):
    """RETURN: str, what 'GOOD/book.csv' says of that run: 'PASS',
    'FAIL', the verdict's own name else ('ASPIRANT'), 'NO VERDICT'
    where the book holds none."""
    entry   = bookkeeper.result(test, choice)
    verdict = None if entry is None else entry.get("verdict")
    if verdict is None:    return NO_VERDICT
    if verdict.passed_f:   return PASS
    if verdict.failed_f:   return FAIL
    return verdict.name


def linked_name_tuple(parameters):
    """RETURN: tuple of str, the feature names a test run with these
    'TestParameters' links to; empty where it links to none."""
    return tuple(parameters.features or ())


def test_directory_of(directory, path, app_set):
    """RETURN: CTestDirectory, the relation inside one TEST directory:
    'directory' where it stands, 'path' how it is addressed, 'app_set'
    what exploration found there."""
    feature_file = read_feature_file(directory)
    bookkeeper   = Bookkeeper(directory)
    run_db       = {}                  # feature name -> [CRun]
    unlinked     = []
    undefined    = []
    for app in app_set:
        for choice, parameters in app.choice_db.items():
            name_tuple = linked_name_tuple(parameters)
            if not name_tuple:
                unlinked.append((app.source_file, choice))
                continue
            for name in name_tuple:
                if feature_file is None \
                   or feature_file.feature_of_name(name) is None:
                    undefined.append((app.source_file, choice, name))
                    continue
                run_db.setdefault(name, []).append(
                    CRun(app.source_file, choice,
                         _verdict_text(bookkeeper, app.source_file,
                                       choice)))
    state_list = []
    for feature in feature_file.feature_tuple if feature_file else ():
        run_tuple = tuple(run_db.get(feature.name, ()))
        state_list.append(CFeatureState(feature, run_tuple,
                                        state_of(run_tuple)))
    return CTestDirectory(path, feature_file, tuple(state_list),
                          tuple(unlinked), tuple(undefined))


def relation_of_tree(root, interview_runner=None, fault_list=None):
    """
    RETURN: CRelation, every TEST directory below 'root' with its
            features and their linked runs, and every component: each
            directory on the way from 'root' down to a TEST directory,
            and each directory that carries a composition file.

    Raises RootConfMissing where no 'hwut-root.conf' bounds the tree.
    """
    return relation_of_exploration(
        root, explore_tree_stream(root, interview_runner, fault_list))


def relation_of_exploration(root, pair_iterable):
    """RETURN: CRelation, as 'relation_of_tree' answers it, from an
    exploration already made: 'pair_iterable' yields (TEST directory
    relative to 'root', ExplorationResult)."""
    test_directory_db = {}
    for relative, result in pair_iterable:
        path = relative.replace(os.sep, "/")
        test_directory_db[path] = test_directory_of(
            os.path.normpath(os.path.join(root, relative)), path,
            result.app_set)

    root_name = os.path.basename(os.path.abspath(root))
    top_f = os.path.isfile(os.path.join(root, ROOT_CONF_NAME))
    above = None if top_f else read_composition(os.path.dirname(
                                    os.path.abspath(root)))
    #  A TEST DIRECTORY ASKED ITSELF has no component below the root.
    if "." in test_directory_db:
        return CRelation({}, test_directory_db, above, top_f, root_name)

    component_set = set()
    for path in test_directory_db:
        above = parent_of(path)
        while above is not None:
            component_set.add(above)
            above = parent_of(above)
    for where, name_list, file_list in os.walk(root):
        relative = os.path.relpath(where, root).replace(os.sep, "/")
        name_list[:] = sorted(
            name for name in entered(where, name_list)
            if (name if relative == "." else "%s/%s" % (relative, name))
                not in test_directory_db)
        if COMPOSITION_FILE_NAME in file_list:
            above = relative
            while above is not None:
                component_set.add(above)
                above = parent_of(above)

    component_db = {}
    for path in sorted(component_set):
        directory = os.path.normpath(os.path.join(root, path))
        component_db[path] = CComponent(
            path,
            read_composition(directory),
            tuple(sorted(each for each in component_set
                         if parent_of(each) == path)),
            next((each for each in sorted(test_directory_db)
                  if parent_of(each) == path), None))
    return CRelation(component_db, test_directory_db, above, top_f,
                     root_name)


# -- parent and childs against the directories ---------------------------

#  THE KINDS OF MISMATCH between what the statement files say and where
#  the directories stand.
NO_ID    = "no-id"      # the statement file gives itself no id
MOVED    = "moved"      # stands below one parent, stated as another's
PARENT   = "parent"     # 'parent' is not the id of the directory above
UNLISTED = "unlisted"   # the directory above does not list it in 'childs'
GONE     = "gone"       # 'childs' lists an id nothing below carries
TWIN     = "twin"       # two childs of one parent carry one id
UNJUDGED = "unjudged"   # the directory above states no id to relate to

#  The kinds 'feature_adapt.adapt_directory' heals, and the one
#  'feature_adapt.child_dropped' heals; the others are the author's.
ADAPTED_KIND_TUPLE = (NO_ID, MOVED, PARENT, UNLISTED)


@dataclass(frozen=True)
class CMismatch:
    """One disagreement. 'path' is the directory whose statement file is
    concerned: the CHILD for every kind but GONE, where it is the parent
    that lists. 'id' is the id concerned, where one is. 'from_path' is,
    for MOVED, the directory whose 'childs' still lists the id."""
    kind:      str
    path:      str
    id:        str | None = None
    from_path: str | None = None


def moved_away_id_set(relation, path):
    """RETURN: set of str, the ids the 'childs' at 'path' still lists
    for directories that stand elsewhere now ('old_lister_of' names
    'path' for them): theirs to carry away, not gone."""
    result = set()
    for other in set(relation.component_db) | set(relation.test_directory_db):
        if parent_of(other) == path: continue
        if old_lister_of(relation, other) == path:
            result.add(relation.statement_of(other).id)
    return result


def unclaimed_id_list(relation, path):
    """RETURN: list of str, the ids the composition at 'path' lists in
    'childs' that no statement directly below carries and no moved
    directory took with it, file order; empty where it states none."""
    statement = relation.statement_of(path)
    if not isinstance(statement, CComposition): return []
    carried_set = {(relation.statement_of(below) or CComposition()).id
                   for below in relation.below_tuple(path)}
    carried_set |= moved_away_id_set(relation, path)
    return [child_id for child_id in statement.child_id_tuple()
            if child_id not in carried_set]


def proposed_id_of(relation, path):
    """RETURN: str, the id a statement file at 'path' that gives itself
    none is to receive: the ONE id its parent's 'childs' lists that
    nothing below the parent carries, where this is the parent's only
    child without an id -- the author named it there first; the
    directory's own name else. 'root_name' names the top directory."""
    above = parent_of(path)
    if above is not None:
        unclaimed_list = unclaimed_id_list(relation, above)
        unnamed_list   = [below for below in relation.below_tuple(above)
                          if relation.statement_of(below) is not None
                          and relation.statement_of(below).id is None]
        if len(unclaimed_list) == 1 and unnamed_list == [path]:
            return unclaimed_list[0]
    return name_of(path) if path != "." else relation.root_name


def old_lister_of(relation, path):
    """
    RETURN: str, the path of the ONE component, other than the directory
            above 'path', whose 'childs' lists the id of the statement
            at 'path' while nothing directly below it carries that id --
            where the directory came from, as the statements still say;
            with several such, the one whose id the statement's
            'parent' names
            None, no such component, or several and none is named
    """
    statement = relation.statement_of(path)
    if statement is None or statement.id is None: return None
    found_list = []
    for other, component in sorted(relation.component_db.items()):
        if other == parent_of(path) or component.composition is None:
            continue
        if statement.id not in component.composition.child_id_tuple():
            continue
        if any((relation.statement_of(below) or CComposition()).id
               == statement.id for below in relation.below_tuple(other)):
            continue
        found_list.append(other)
    if len(found_list) == 1: return found_list[0]
    for other in found_list:
        if relation.component_db[other].composition.id \
           == statement.parent_id:
            return other
    return None


def mismatch_list(relation):
    """
    RETURN: list of CMismatch, every disagreement between 'parent',
            'childs' and where the directories stand, parents before
            their childs; empty where the three agree.

    Judged for every directory that carries a statement file. A
    directory without one states nothing and is not judged. The top of
    the tree states no parent.
    """
    result    = []
    path_list = sorted(set(relation.component_db)
                       | set(relation.test_directory_db),
                       key=lambda path: (path != ".", path.split("/")))
    for path in path_list:
        statement = relation.statement_of(path)
        if statement is not None:
            result.extend(_upward_mismatch_list(relation, path, statement))
        if isinstance(statement, CComposition):
            result.extend(_downward_mismatch_list(relation, path, statement))
    return result


def _upward_mismatch_list(relation, path, statement):
    """RETURN: list of CMismatch, what the statement at 'path' gets
    wrong about itself and the directory above: NO_ID, MOVED, PARENT,
    UNLISTED, UNJUDGED."""
    result = []
    if statement.id is None:
        result.append(CMismatch(NO_ID, path))
    if parent_of(path) is None and relation.top_f:
        return result
    above = relation.statement_above(path)
    if above is None or above.id is None:
        if parent_of(path) is not None or relation.above is not None:
            result.append(CMismatch(UNJUDGED, path, statement.id))
        return result
    if statement.id is None: return result

    parent_f = statement.parent_id == above.id
    listed_f = statement.id in above.child_id_tuple()
    if parent_f and listed_f: return result
    from_path = old_lister_of(relation, path)
    if from_path is not None:
        result.append(CMismatch(MOVED, path, statement.id, from_path))
    else:
        if not parent_f:
            result.append(CMismatch(PARENT, path, statement.id))
        if not listed_f:
            result.append(CMismatch(UNLISTED, path, statement.id))
    return result


def _downward_mismatch_list(relation, path, statement):
    """RETURN: list of CMismatch, what the composition at 'path' gets
    wrong about the directories below: GONE for a listed id nothing
    below carries and nothing elsewhere was moved away with, TWIN for
    an id two childs carry."""
    result   = []
    below_db = {}
    #  A CHILD THAT GIVES ITSELF NO ID YET will be given one
    #  ('proposed_id_of'): an entry under that id is not GONE.
    unnamed_set = set()
    for below in relation.below_tuple(path):
        below_statement = relation.statement_of(below)
        if below_statement is None: continue
        if below_statement.id is None:
            unnamed_set.add(proposed_id_of(relation, below))
            continue
        below_db.setdefault(below_statement.id, []).append(below)
    for child_id, below_list in sorted(below_db.items()):
        if len(below_list) > 1:
            result.append(CMismatch(TWIN, path, child_id))
    moved_id_set = moved_away_id_set(relation, path)
    for child_id in statement.child_id_tuple():
        if child_id in below_db or child_id in moved_id_set: continue
        if child_id in unnamed_set: continue
        result.append(CMismatch(GONE, path, child_id))
    return result
