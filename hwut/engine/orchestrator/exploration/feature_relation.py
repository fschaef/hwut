"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURES OF THE TEST DIRECTORIES, and the test runs that
         prove them -- per TEST directory, knowing no tree above it:

    <dir>/TEST/hwut-features.conf    the FEATURES proven in that TEST
                                     directory, inline
    a test's '@hwut { }' block       'features = [...]': the features
                                     the test run proves

    read_feature_file(directory)     -> CFeatureFile | None
    relation_of_tree(root)           -> CRelation

WHERE THE FEATURES STAND IN THE WORLD -- their external ids, the tree of
aggregates, the retired -- is the central file's, 'hwut-root-features.conf'
('feature_registry', spec 23 VERSION 10, R-96); 'feature_view' joins the
two. A component file and 'hwut-feature-map.conf' are the vocabulary of
the past: nothing here reads them, the detector names them (R-96 step 6).

THE FILE
    features {
        keys   = ["heavy-test"]                     # every feature carries it
        childs {
            line-pairing {
                title     = "Two streams are aligned line by line."
                doc       = \"\"\"...\"\"\"
                documents = ["../README.txt"]
                keys      = ["heavy-test"] }
        }
    }

    A feature's name is its key in 'childs': '[A-Za-z0-9_][A-Za-z0-9_-]*',
    digits may lead, a dot may not.

THE RELATION
    A test run is addressed as '<path>/<test> [<choice>]', the path
    RELATIVE to the root asked -- composed at the moment of asking, and
    stored nowhere. A name is looked up in the feature file of the test's
    own TEST directory and nowhere else. The verdict of a run is what
    'GOOD/book.csv' says: PASS, FAIL, the verdict's own name, NO VERDICT.
______________________________________________________________________________
"""
import os
import posixpath
import re
from   dataclasses import dataclass

from ....test_writing_support.python import hwut_hocon
from ....test_writing_support.python.hwut_hocon import (ScalarNode,
                                                        ListNode,
                                                        ObjectNode)
from ...bookkeeper.api import Bookkeeper
from .                 import unwrapper
from .fault            import Fault, E_FaultKind, Position
from .finder           import FEATURE_FILE_NAME
from .tree_explorer    import explore_tree_stream


#  WHAT THE BOOK SAYS OF A LINKED RUN, as the relation spells it.
PASS       = "PASS"
FAIL       = "FAIL"
NO_VERDICT = "NO VERDICT"

#  A KEY, a feature's name: an identifier. A dot would end it.
KEY_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]*\Z")

#  THE TEST DIRECTORY'S NAME.
TEST_NAME = "TEST"


def key_valid_f(text):
    """RETURN: True, 'text' is a key: an identifier, digits may lead and a
    dot may not; False else."""
    return isinstance(text, str) and KEY_RE.match(text) is not None


@dataclass(frozen=True)
class CFeature:
    """One feature of one TEST directory's feature file. 'name' is its
    key in the file's 'childs' -- the last level of its id."""
    name:        str
    title:       str | None = None
    doc:         str | None = None     # what more there is to say (R-93)
    key_tuple:   tuple      = ()       # of str: the keys it states itself
    line_n:      int        = 0
    document_tuple: tuple   = ()       # of str: where more is said --
                                       #  paths from the feature file's
                                       #  directory ('#<anchor>' may
                                       #  follow), or URLs

    @property
    def key(self):
        """RETURN: str, the feature's name -- its key in 'childs'."""
        return self.name


@dataclass(frozen=True)
class CFeatureFile:
    """What one TEST directory's 'hwut-features.conf' states: the
    features, in file order, and the keys that apply to all of them."""
    feature_tuple: tuple      = ()     # of CFeature, file order
    fault_tuple:   tuple      = ()     # of Fault
    key_tuple:     tuple      = ()     # of str: every feature carries them

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
        return tuple(feature.name for feature in self.feature_tuple)



def read_feature_file(directory):
    """
    RETURN: CFeatureFile, what 'directory/hwut-features.conf' states of
            a TEST directory's features
            None, no such file stands
    """
    text = _text_of(os.path.join(directory, FEATURE_FILE_NAME))
    if text is None: return None
    return feature_file_of_text(text, FEATURE_FILE_NAME)



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


def _text_list(entry, file, fault_list, what):
    """
    RETURN: tuple of str, the texts the list 'entry' holds, none empty
            None, it is no such list (fault recorded: "'<key>' is <what>")
    """
    node = entry.node
    if isinstance(node, ListNode) \
       and all(isinstance(item, ScalarNode) and isinstance(item.value, str)
               and item.value for item in node.item_list):
        return tuple(item.value for item in node.item_list)
    fault_list.append(Fault(E_FaultKind.VOCABULARY, file, entry.key_position,
                            "'%s' is %s" % (entry.key, what)))
    return None


def _key_list(entry, file, fault_list):
    """
    RETURN: tuple of str, the keys the list 'entry' states, each once; an
            entry that is no key, or stands twice, is a fault and left
            out
    """
    found = _text_list(entry, file, fault_list,
                       "a list of keys: keys = [\"gui\", ...]")
    result = []
    for key in found or ():
        if not key_valid_f(key):
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "'%s' is no key: letters, digits, '_' and '-' -- no dot"
                % key))
        elif key in result:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "key '%s' stands twice; the first stands" % key))
        else:
            result.append(key)
    return tuple(result)



def _feature(entry, file, fault_list):
    """RETURN: CFeature, the entry's 'title', 'doc', 'documents' and
    'keys' under its key as the name; an unknown key inside, and
    'documents' that is no list of strings, is a fault and is dropped."""
    field_db      = {}
    document_list = []
    key_tuple     = ()
    for inner in entry.node.entry_list:
        if inner.key in ("title", "doc"):
            value = _sentence(inner, file, fault_list)
            if value is not None: field_db[inner.key] = value
        elif inner.key == "documents":
            found = _text_list(inner, file, fault_list,
                               "a list of file names: documents = "
                               "[\"README.txt\", ...]")
            if found is not None: document_list = list(found)
        elif inner.key == "keys":
            key_tuple = _key_list(inner, file, fault_list)
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, inner.key_position,
                "unknown key '%s' in feature '%s': 'title', 'doc', "
                "'documents', 'keys'" % (inner.key, entry.key)))
    return CFeature(entry.key, field_db.get("title"), field_db.get("doc"),
                    key_tuple, entry.key_position.line,
                    tuple(document_list))


def _child_list(entry, file, fault_list):
    """
    RETURN: list of CFeature, the features 'childs' holds inline. A child
            that is no feature, a key that is no key and a key standing
            twice are faults and left out (the first stands).
    """
    node = entry.node
    if not isinstance(node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, entry.key_position,
            "'childs' is a scope: childs { <name> { title = \"...\" } }"))
        return []
    feature_list, seen_set = [], set()
    for child in node.entry_list:
        if not key_valid_f(child.key):
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, child.key_position,
                "'%s' is no key: letters, digits, '_' and '-' -- no dot "
                "(digits may lead)" % child.key))
            continue
        if child.key in seen_set:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, child.key_position,
                "'%s' stands twice in 'childs'; the first stands"
                % child.key))
            continue
        seen_set.add(child.key)
        if isinstance(child.node, ObjectNode):
            feature_list.append(_feature(child, file, fault_list))
        else:
            fault_list.append(Fault(
                E_FaultKind.TYPE, file, child.key_position,
                "'%s' is a feature: %s { title = \"...\" }; the tree above "
                "the features stands in 'hwut-root-features.conf'"
                % (child.key, child.key)))
    return feature_list


def feature_file_of_text(text, file=FEATURE_FILE_NAME):
    """RETURN: CFeatureFile, what 'text' states as a TEST directory's
    features; every fault met stands in its 'fault_tuple', and what was
    readable beside it. A feature name standing twice is a fault and the
    first stands."""
    fault_list   = []
    outer        = _outer_node(text, file, "features", fault_list)
    key_tuple    = ()
    feature_list = []
    for entry in outer.entry_list if outer is not None else ():
        if entry.key == "keys":
            key_tuple = _key_list(entry, file, fault_list)
        elif entry.key == "childs":
            feature_list = _child_list(entry, file, fault_list)
        elif entry.key in ("title", "doc", "documents"):
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "'%s' states an aggregate, and aggregates stand in "
                "'hwut-root-features.conf'" % entry.key))
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "unknown key '%s' in 'features': 'keys', 'childs'"
                % entry.key))
    return CFeatureFile(tuple(feature_list), tuple(fault_list), key_tuple)


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
    """One feature and the test runs linked to it."""
    feature:   CFeature
    run_tuple: tuple                   # of CRun, walk order


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
    run_tuple:       tuple = ()        # of (test, choice): EVERY run of
                                       #  the directory, walk order
    app_tuple:       tuple = ()        # of (test, title, doc): every
                                       #  application, walk order
    verdict_db:      dict  = None      # (test, choice) -> verdict text,
                                       #  for every run of the directory


@dataclass(frozen=True)
class CRelation:
    """The relation of one tree: its TEST directories by path, relative to
    the root asked, '/'-separated; '.' is the root itself."""
    test_directory_db: dict            # path -> CTestDirectory
    root_name:         str = ""        # the name of the directory asked


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


def document_place(path, document):
    """
    RETURN: [0] str, where a feature's document stands, addressed from
                the directory the relation was asked in ('/' between);
                the document itself where it is a URL
            [1] str, its '#<anchor>', '' where it names none
            [2] bool, True where it is a URL ('<scheme>://...'), which
                nothing here looks up

    'path' is the directory whose file states the document, as the
    relation addresses it; 'document' what the file states, a path from
    that directory.
    """
    if "://" in document: return document, "", True
    name, mark, anchor = document.partition("#")
    place = posixpath.normpath(posixpath.join(path, name))
    return place, mark + anchor, False


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
    every        = []
    app_list     = []
    verdict_db   = {}
    for app in app_set:
        app_list.append((app.source_file, app.title,
                         getattr(app, "doc", None)))
        for choice, parameters in app.choice_db.items():
            every.append((app.source_file, choice))
            verdict_db[(app.source_file, choice)] = _verdict_text(
                bookkeeper, app.source_file, choice)
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
                         verdict_db[(app.source_file, choice)]))
    state_list = [CFeatureState(feature, tuple(run_db.get(feature.name, ())))
                  for feature in (feature_file.feature_tuple
                                  if feature_file else ())]
    return CTestDirectory(path, feature_file, tuple(state_list),
                          tuple(unlinked), tuple(undefined), tuple(every),
                          tuple(app_list), verdict_db)


def relation_of_tree(root, interview_runner=None, fault_list=None):
    """
    RETURN: CRelation, every TEST directory below 'root' with its
            features and their linked runs.

    Raises RootConfMissing where no 'hwut-root.conf' bounds the tree.
    """
    return relation_of_exploration(
        root, explore_tree_stream(root, interview_runner, fault_list))


def relation_of_exploration(root, pair_iterable):
    """RETURN: CRelation, as 'relation_of_tree' answers it, from an
    exploration already made: 'pair_iterable' yields (TEST directory
    relative to 'root', ExplorationResult)."""
    root = os.path.abspath(root)
    test_directory_db = {}
    for relative, result in pair_iterable:
        path = relative.replace(os.sep, "/")
        test_directory_db[path] = test_directory_of(
            os.path.normpath(os.path.join(root, relative)), path,
            result.app_set)
    return CRelation(test_directory_db, os.path.basename(root))
