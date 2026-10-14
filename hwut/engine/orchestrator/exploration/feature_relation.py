"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE RELATION -- what a tree claims to do, and which test
         runs prove it. ONE FILE KIND, 'hwut-features.conf', and ONE MAP:

    <dir>/hwut-features.conf         a COMPONENT's claim: its title, doc,
                                     documents, keys, and the directories
                                     below it that are its parts
    <dir>/TEST/hwut-features.conf    the FEATURES proven in that TEST
                                     directory, inline
    <top>/hwut-feature-map.conf      the PUBLISHED ids, each bound to
                                     the feature it names now
    a test's '@hwut { }' block       'features = [...]': the features
                                     the test run proves

    read_feature_file(directory)     -> CFeatureFile | None   (TEST)
    read_claim(directory)            -> CClaim | None         (component)
    read_feature_map(top)            -> CFeatureMap | None
    relation_of_tree(root)           -> CRelation

ONE KIND OF THING, A CLAIM (R-93): a sentence of what the software does,
and what implements it. A component is a claim implemented by claims, a
feature a claim implemented by test runs. Both carry 'title' (one line),
'doc' (triple quotes), 'documents' (where more is said) and 'keys'.

THE FILE
    features {
        title     = "Compare"                       # component only
        doc       = \"\"\"...\"\"\"                      # component only
        documents = ["README.txt", "spec.txt#3"]    # component only
        keys      = ["computational"]
        childs {
            core = "./core"                         # component file: a
                                                    #  directory below, one
            line-pairing {                          # TEST file: a feature
                title     = "Two streams are aligned line by line."
                doc       = \"\"\"...\"\"\"
                documents = ["../README.txt"]
                keys      = ["heavy-test"] }
        }
    }

THE ID OF A CLAIM IS NAMED BY ITS PARENT. The key in the 'childs' of the
file above is the id of what it refers to; the full id is the chain of
keys from the directory that holds 'hwut-root.conf' down to the claim,
joined by '.': 'engine.compare.core.line-pairing'. A key is an
identifier, '[A-Za-z0-9_][A-Za-z0-9_-]*': digits may lead ('007'), a dot
may not. A file states no 'id' and no 'parent'.

    A TREE THAT STATES NO COMPONENT -- no 'hwut-features.conf' outside a
    TEST directory, above or below -- IS NOT JUDGED (feature files alone
    are complete, E-144): its directories are its components, a
    directory's name its key (invalid characters become '_').
    A TREE THAT STATES ONE is judged whole (the 'explicit' tree): every
    component has a file, every file is listed by its parent, every
    listed directory stands.

    A component's TEST directory is the component's own and is listed
    nowhere: its features belong to the component, 'engine.compare' for
    'engine/compare/TEST'. Components are never in a TEST directory.

KEYS TRAVEL DOWNWARD. A key stated on a claim applies to that claim and
to every claim below it, never to what is above. A feature's EFFECTIVE
keys are its own, those of its TEST file, and those of every component
above it ('effective_key_tuple').

THE MAP binds a PUBLISHED id -- the one a customer was told -- to the full
id it means now; the structure may change, the published id stays:

    map {
        "xyz"       = "engine.compare.core.line-pairing"
        "old-intro" = none                  # RETIRED: no longer claimed
    }

Every feature has an entry; 'hwut.sanitize' writes it on first sight, and
'hwut.move' / 'hwut.rename' repoint the right side. The map holds the
CURRENT state; history is configuration management's.

THE RELATION
    A feature is addressed by its full id, a test run as
    '<path>/<test> [<choice>]', the path RELATIVE to the root asked --
    composed here, at the moment of asking, and stored nowhere.

    state of a feature
        PROVEN     one linked test run or more; all of them pass
        FAILING    one linked test run or more; one of them does not
                   pass, or has no verdict in 'GOOD/book.csv'
        UNPROVEN   no linked test run
    RETIRED, a map entry bound to none, is the fourth: it is not counted
    in any component, it is listed in 'retired_tuple'.

    A name is looked up in the feature file of the test's own TEST
    directory and nowhere else.
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
from .finder           import (FEATURE_FILE_NAME, MAP_FILE_NAME,
                               ROOT_CONF_NAME)
from ....auxiliary.no_entry import entered
from .tree_explorer    import explore_tree_stream, root_conf_directory, \
                              RootConfMissing



PROVEN   = "PROVEN"
FAILING  = "FAILING"
UNPROVEN = "UNPROVEN"
STATE_TUPLE = (PROVEN, FAILING, UNPROVEN)

#  WHAT THE BOOK SAYS OF A LINKED RUN, as the relation spells it.
PASS       = "PASS"
FAIL       = "FAIL"
NO_VERDICT = "NO VERDICT"

#  A KEY, a feature's name, a component's key: the identifier of one
#  level of an id. A dot would end the level.
KEY_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]*\Z")

#  THE TEST DIRECTORY'S NAME, the one no component is ever made of.
TEST_NAME = "TEST"


def key_valid_f(text):
    """RETURN: True, 'text' is a key: an identifier, digits may lead and a
    dot may not; False else."""
    return isinstance(text, str) and KEY_RE.match(text) is not None


def key_of_name(name):
    """RETURN: str, the key a directory called 'name' stands under where
    no file names it: the name itself, characters a key cannot hold
    replaced by '_'."""
    key = re.sub(r"[^A-Za-z0-9_\-]", "_", name)
    return key if key and key_valid_f(key) else "_" + key


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


@dataclass(frozen=True)
class CChild:
    """One part a component's file lists: 'key' is the id of what the
    directory 'directory' (one level below, its name) is called there."""
    key:       str
    directory: str
    line_n:    int = 0


@dataclass(frozen=True)
class CClaim:
    """What one component's 'hwut-features.conf' states."""
    title:          str | None = None
    doc:            str | None = None
    document_tuple: tuple      = ()
    key_tuple:      tuple      = ()
    child_tuple:    tuple      = ()    # of CChild, file order
    fault_tuple:    tuple      = ()

    def child_of_directory(self, directory):
        """
        RETURN: CChild, the first part that refers to the directory
                called 'directory'
                None, none does
        """
        for child in self.child_tuple:
            if child.directory == directory: return child
        return None

    def directory_tuple(self):
        """RETURN: tuple of str, the directories the file lists, file
        order."""
        return tuple(child.directory for child in self.child_tuple)


@dataclass(frozen=True)
class CFeatureMap:
    """What 'hwut-feature-map.conf' states: (published id, full id it
    means, line) in file order; the full id is None where the entry is
    bound to none -- RETIRED."""
    entry_tuple: tuple = ()
    fault_tuple: tuple = ()

    def target_of(self, published):
        """
        RETURN: str, the full id 'published' means
                None, it is retired, or the map has no such entry
        """
        for each, target, _ in self.entry_tuple:
            if each == published: return target
        return None

    def published_tuple(self):
        """RETURN: tuple of str, every published id, file order."""
        return tuple(each for each, _, _ in self.entry_tuple)

    def standing_f(self, published):
        """RETURN: True, the map holds an entry for 'published' -- bound
        or retired."""
        return published in self.published_tuple()


def read_feature_file(directory):
    """
    RETURN: CFeatureFile, what 'directory/hwut-features.conf' states of
            a TEST directory's features
            None, no such file stands
    """
    text = _text_of(os.path.join(directory, FEATURE_FILE_NAME))
    if text is None: return None
    return feature_file_of_text(text, FEATURE_FILE_NAME)


def read_claim(directory):
    """
    RETURN: CClaim, what 'directory/hwut-features.conf' states of a
            component
            None, no such file stands
    """
    text = _text_of(os.path.join(directory, FEATURE_FILE_NAME))
    if text is None: return None
    return claim_of_text(text, FEATURE_FILE_NAME)


def read_feature_map(top):
    """
    RETURN: CFeatureMap, what 'top/hwut-feature-map.conf' states
            None, no such file stands
    """
    text = _text_of(os.path.join(top, MAP_FILE_NAME))
    if text is None: return None
    return feature_map_of_text(text, MAP_FILE_NAME)


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


def directory_of_reference(text):
    """
    RETURN: str, the name of the directory one level below that the
            reference 'text' means: "./core", "core" and "./core/" mean
            'core'
            None, the reference is not one directory below
    """
    name = text[2:] if text.startswith("./") else text
    name = name.rstrip("/")
    if not name or "/" in name or name in (".", "..") or "\\" in name:
        return None
    return name


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


def _child_list(entry, file, fault_list, test_f):
    """
    RETURN: [0] list of CChild, the directories 'childs' refers to --
                what a COMPONENT's file lists
            [1] list of CFeature, the inline features -- what a TEST
                directory's file holds
            A child of the other kind is a fault and left out, as is a
            key that is no key and a key standing twice (the first
            stands).
    """
    node = entry.node
    if not isinstance(node, ObjectNode):
        fault_list.append(Fault(
            E_FaultKind.TYPE, file, entry.key_position,
            "'childs' is a scope: childs { <key> = \"./<directory>\" } "
            "in a component's file, childs { <name> { ... } } in a TEST "
            "directory's"))
        return [], []
    child_list, feature_list, seen_set = [], [], set()
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
            if not test_f:
                fault_list.append(Fault(
                    E_FaultKind.VOCABULARY, file, child.key_position,
                    "'%s' is a feature, and features stand in the TEST "
                    "directory's file: a component's file lists "
                    "directories, %s = \"./<directory>\"" % (child.key,
                                                            child.key)))
                continue
            feature_list.append(_feature(child, file, fault_list))
        elif isinstance(child.node, ScalarNode) \
             and isinstance(child.node.value, str):
            if test_f:
                fault_list.append(Fault(
                    E_FaultKind.VOCABULARY, file, child.key_position,
                    "'%s' refers to a directory, and components are not "
                    "in a TEST directory: the feature is '%s { title = "
                    "\"...\" }'" % (child.key, child.key)))
                continue
            directory = directory_of_reference(child.node.value)
            if directory is None:
                fault_list.append(Fault(
                    E_FaultKind.TYPE, file, child.key_position,
                    "'%s' refers to '%s': a reference names ONE directory "
                    "below, \"./<directory>\"" % (child.key,
                                                  child.node.value)))
                continue
            child_list.append(CChild(child.key, directory,
                                     child.key_position.line))
        else:
            fault_list.append(Fault(
                E_FaultKind.TYPE, file, child.key_position,
                "'%s' is a directory (\"./<directory>\") or a feature "
                "({ title = \"...\" })" % child.key))
    return child_list, feature_list


def _read_fields(outer, file, fault_list, test_f):
    """
    RETURN: [0] dict, 'title' and 'doc' as stated
            [1] tuple of str, 'documents'
            [2] tuple of str, 'keys'
            [3] list of CChild
            [4] list of CFeature
            In a TEST directory's file only 'keys' and 'childs' stand: a
            component's 'title', 'doc' and 'documents' are its own
            file's.
    """
    field_db, document_tuple, key_tuple = {}, (), ()
    child_list, feature_list = [], []
    for entry in outer.entry_list if outer is not None else ():
        if entry.key in ("title", "doc", "documents") and test_f:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "'%s' states a component, and a TEST directory is not one: "
                "it belongs in the 'hwut-features.conf' of the directory "
                "above" % entry.key))
        elif entry.key in ("title", "doc"):
            value = _sentence(entry, file, fault_list)
            if value is not None: field_db[entry.key] = value
        elif entry.key == "documents":
            found = _text_list(entry, file, fault_list,
                               "a list of file names: documents = "
                               "[\"README.txt\", ...]")
            if found is not None: document_tuple = found
        elif entry.key == "keys":
            key_tuple = _key_list(entry, file, fault_list)
        elif entry.key == "childs":
            child_list, feature_list = _child_list(entry, file, fault_list,
                                                   test_f)
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "unknown key '%s' in 'features': %s" % (
                    entry.key,
                    "'keys', 'childs'" if test_f else
                    "'title', 'doc', 'documents', 'keys', 'childs'")))
    return field_db, document_tuple, key_tuple, child_list, feature_list


def feature_file_of_text(text, file=FEATURE_FILE_NAME):
    """RETURN: CFeatureFile, what 'text' states as a TEST directory's
    features; every fault met stands in its 'fault_tuple', and what was
    readable beside it. A feature name standing twice is a fault and the
    first stands."""
    fault_list = []
    outer      = _outer_node(text, file, "features", fault_list)
    _, _, key_tuple, _, feature_list = _read_fields(outer, file, fault_list,
                                                    True)
    return CFeatureFile(tuple(feature_list), tuple(fault_list), key_tuple)


def claim_of_text(text, file=FEATURE_FILE_NAME):
    """RETURN: CClaim, what 'text' states as a component; every fault met
    stands in its 'fault_tuple', and what was readable beside it."""
    fault_list = []
    outer      = _outer_node(text, file, "features", fault_list)
    field_db, document_tuple, key_tuple, child_list, _ = _read_fields(
        outer, file, fault_list, False)
    return CClaim(field_db.get("title"), field_db.get("doc"), document_tuple,
                  key_tuple, tuple(child_list), tuple(fault_list))


def feature_map_of_text(text, file=MAP_FILE_NAME):
    """RETURN: CFeatureMap, what 'text' states: each entry 'map {
    "<published>" = "<full id>" }', or bound to none -- RETIRED. Every
    fault met stands in its 'fault_tuple'; an entry that is neither a
    text nor none is left out."""
    fault_list = []
    outer      = _outer_node(text, file, "map", fault_list)
    entry_list = []
    for entry in outer.entry_list if outer is not None else ():
        node = entry.node
        if not entry.key.strip():
            fault_list.append(Fault(E_FaultKind.VOCABULARY, file,
                                    entry.key_position,
                                    "a published id is not empty"))
        elif isinstance(node, ScalarNode) and node.value is None:
            entry_list.append((entry.key, None, entry.key_position.line))
        elif isinstance(node, ScalarNode) and isinstance(node.value, str) \
             and node.value.strip():
            entry_list.append((entry.key, node.value,
                               entry.key_position.line))
        else:
            fault_list.append(Fault(
                E_FaultKind.TYPE, file, entry.key_position,
                "'%s' is bound to the full id it means (\"a.b.c\"), or to "
                "none: retired" % entry.key))
    return CFeatureMap(tuple(entry_list), tuple(fault_list))


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
    run_tuple:       tuple = ()        # of (test, choice): EVERY run of
                                       #  the directory, walk order
    app_tuple:       tuple = ()        # of (test, title, doc): every
                                       #  application, walk order
    verdict_db:      dict  = None      # (test, choice) -> verdict text,
                                       #  for every run of the directory


@dataclass(frozen=True)
class CComponent:
    """One component in the relation: a directory that is no TEST
    directory. 'claim' is None where no file stands. 'key' is its level
    of every id below it; 'part_tuple' names its direct subdirectories
    that are components, 'test_directory' its own TEST directory's path,
    or None."""
    path:           str
    claim:          CClaim | None
    part_tuple:     tuple = ()         # of str, paths, sorted
    test_directory: str | None = None
    key:            str = ""


@dataclass(frozen=True)
class CRelation:
    """The feature relation of one tree: components and TEST
    directories by path, relative to the root asked, '/'-separated;
    '.' is the root itself."""
    component_db:      dict            # path -> CComponent
    test_directory_db: dict            # path -> CTestDirectory
    #  WHAT THE DIRECTORY ABOVE THE ROOT ASKED STATES: its claim, where
    #  the root asked is not the tree's own root and one stands.
    above:             CClaim | None = None
    #  True where the root asked is the tree's own ('hwut-root.conf'
    #  stands in it): it has no parent to state.
    top_f:             bool = True
    #  The name of the directory asked.
    root_name:         str  = ""
    #  THE KEYS OF THE CHAIN from the tree's top down to the root asked:
    #  where the root asked is not the top, its ids begin with them.
    prefix_tuple:      tuple = ()
    #  The keys the claims ABOVE the root asked carry: they travel down.
    above_key_tuple:   tuple = ()
    #  True where the tree states components (a 'hwut-features.conf'
    #  outside a TEST directory, in the tree or directly above it).
    explicit_f:        bool = False
    #  The directory holding 'hwut-root.conf' and so the map, absolute.
    top_directory:     str | None = None
    feature_map:       CFeatureMap | None = None

    def statement_of(self, path):
        """
        RETURN: CClaim, the file of the component at 'path'
                None, it carries none, 'path' is a TEST directory
                (components are not in one), or 'path' is not in the
                relation
        """
        component = self.component_db.get(path)
        return None if component is None else component.claim

    def statement_above(self, path):
        """
        RETURN: CClaim, what the directory above 'path' states
                None, it carries no file -- or 'path' is the top of the
                tree and has no directory above
        """
        above = parent_of(path)
        if above is None: return self.above
        component = self.component_db.get(above)
        return None if component is None else component.claim

    def below_tuple(self, path):
        """RETURN: tuple of str, the components directly below the
        component at 'path' -- its parts. Its TEST directory is not
        among them: it is the component's own."""
        component = self.component_db.get(path)
        if component is None: return ()
        return component.part_tuple

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

    def owner_of(self, path):
        """RETURN: str, the path of the component a TEST directory at
        'path' belongs to: the directory above it; '.' where the TEST
        directory is the root asked (the component is then above the
        root, and the prefix names it)."""
        if path in self.test_directory_db and path != ".":
            return parent_of(path)
        return path

    def chain_tuple(self, path):
        """RETURN: tuple of str, the keys from the top of the tree down
        to the component at 'path' -- or, for a TEST directory, to the
        component it belongs to: the id of the claim, without its own
        last level."""
        path, part_list = self.owner_of(path), []
        while path is not None and path != ".":
            component = self.component_db.get(path)
            part_list.append(component.key if component is not None
                             else key_of_name(name_of(path)))
            path = parent_of(path)
        return self.prefix_tuple + tuple(reversed(part_list))

    def id_of(self, path, name):
        """RETURN: str, the full id of the feature 'name' of the TEST
        directory at 'path': the keys of the chain to its component and
        its name, joined by '.'."""
        return ".".join(self.chain_tuple(path) + (name,))

    def published_of(self, full_id):
        """
        RETURN: str, the published id bound to 'full_id'; the first, where
                several are
                None, the map binds none to it, or no map stands
        """
        if self.feature_map is None: return None
        for each, target, _ in self.feature_map.entry_tuple:
            if target == full_id: return each
        return None

    def retired_tuple(self):
        """RETURN: tuple of str, the published ids the map binds to none:
        features no longer claimed, in file order."""
        if self.feature_map is None: return ()
        return tuple(each for each, target, _
                     in self.feature_map.entry_tuple if target is None)

    def effective_key_tuple(self, path, feature):
        """RETURN: tuple of str, the keys a feature carries, sorted, each
        once: its own, those of its TEST file, and those of every
        component above it -- keys travel downward and never up."""
        test_directory = self.test_directory_db[path]
        found = set(self.above_key_tuple) | set(feature.key_tuple)
        if test_directory.feature_file is not None:
            found |= set(test_directory.feature_file.key_tuple)
        owner = self.owner_of(path)
        while owner is not None:
            component = self.component_db.get(owner)
            if component is not None and component.claim is not None:
                found |= set(component.claim.key_tuple)
            owner = parent_of(owner)
        return tuple(sorted(found))

    def derived_key_tuple(self, path):
        """RETURN: tuple of str, the keys some feature at and below the
        component (or TEST directory) at 'path' carries, sorted: what
        "this component has key k" means -- derived, never written."""
        found = set()
        for test_path, each in self.test_directory_db.items():
            if test_path != path and not test_path.startswith(
                    "" if path == "." else path + "/"):
                continue
            for state in each.state_tuple:
                found |= set(self.effective_key_tuple(test_path,
                                                      state.feature))
        return tuple(sorted(found))


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
    state_list = []
    for feature in feature_file.feature_tuple if feature_file else ():
        run_tuple = tuple(run_db.get(feature.name, ()))
        state_list.append(CFeatureState(feature, run_tuple,
                                        state_of(run_tuple)))
    return CTestDirectory(path, feature_file, tuple(state_list),
                          tuple(unlinked), tuple(undefined), tuple(every),
                          tuple(app_list), verdict_db)


def relation_of_tree(root, interview_runner=None, fault_list=None):
    """
    RETURN: CRelation, every TEST directory below 'root' with its
            features and their linked runs, and every component: each
            directory on the way from 'root' down to a TEST directory,
            and each directory that carries a 'hwut-features.conf'
            outside a TEST directory.

    Raises RootConfMissing where no 'hwut-root.conf' bounds the tree.
    """
    return relation_of_exploration(
        root, explore_tree_stream(root, interview_runner, fault_list))


def top_directory_of(directory):
    """RETURN: str, the absolute directory holding the 'hwut-root.conf'
    that bounds the tree 'directory' stands in -- where the map stands.

    Raises RootConfMissing where no such file stands above it."""
    return root_conf_directory(directory)


def full_id_of(test_directory, name):
    """RETURN: str, the full id the feature 'name' of the TEST directory
    'test_directory' has: the keys of the chain from the top of the tree
    to the component it belongs to, and the name. Read from the files
    standing; nothing is explored.

    Raises RootConfMissing where no root bounds the tree."""
    directory = os.path.abspath(test_directory)
    prefix, _, _ = _chain_above(root_conf_directory(directory), directory,
                                True)
    return ".".join(prefix + (name,))


def _key_of_child(parent_claim, name):
    """RETURN: str, the key the directory 'name' stands under in the
    file 'parent_claim': the key its reference gives it; the name's own
    key where the file lists it not, or no file stands."""
    if parent_claim is not None:
        child = parent_claim.child_of_directory(name)
        if child is not None: return child.key
    return key_of_name(name)


def _chain_above(top, root, test_root_f):
    """
    RETURN: [0] tuple of str, the keys from 'top' down to the root asked
                (to the component a TEST root belongs to)
            [1] tuple of str, the keys the claims above carry
            [2] CClaim, the claim of the directory directly above the
                root asked; None where it states none or the root is the
                top
    """
    relative = os.path.relpath(root, top)
    part_list = [] if relative == "." else relative.split(os.sep)
    if test_root_f and part_list: part_list = part_list[:-1]
    key_list, above_key_list, claim = [], [], None
    directory = top
    last = len(part_list) + (1 if test_root_f else 0)
    for i in range(len(part_list) + 1):
        claim = read_claim(directory)
        if i < last and claim is not None:
            above_key_list.extend(claim.key_tuple)
        if i < len(part_list):
            key_list.append(_key_of_child(claim, part_list[i]))
            directory = os.path.join(directory, part_list[i])
    if test_root_f:
        claim = read_claim(os.path.dirname(root))
    elif part_list:
        claim = read_claim(os.path.dirname(root))
    else:
        claim = None
    return tuple(key_list), tuple(dict.fromkeys(above_key_list)), claim


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

    root_name = os.path.basename(root)
    top_f = os.path.isfile(os.path.join(root, ROOT_CONF_NAME))
    try:
        top = root_conf_directory(root)
    except RootConfMissing:
        top = root
    prefix, above_keys, above = _chain_above(top, root,
                                             "." in test_directory_db)
    feature_map = read_feature_map(top)
    #  A TEST DIRECTORY ASKED ITSELF has no component below the root.
    if "." in test_directory_db:
        return CRelation({}, test_directory_db, above, top_f, root_name,
                         prefix, above_keys, above is not None, top,
                         feature_map)

    component_set = set()
    for path in test_directory_db:
        up = parent_of(path)
        while up is not None:
            component_set.add(up)
            up = parent_of(up)
    claim_db = {}
    for where, name_list, file_list in os.walk(root):
        relative = os.path.relpath(where, root).replace(os.sep, "/")
        name_list[:] = sorted(
            name for name in entered(where, name_list)
            if name != TEST_NAME
            and (name if relative == "." else "%s/%s" % (relative, name))
                not in test_directory_db)
        if FEATURE_FILE_NAME in file_list \
           and os.path.basename(where) != TEST_NAME:
            claim_db[relative] = read_claim(where)
            up = relative
            while up is not None:
                component_set.add(up)
                up = parent_of(up)

    explicit_f = any(claim is not None for claim in claim_db.values()) \
                 or above is not None
    #  A component's KEY is the one the file of its parent gives it: the
    #  claim of the directory above, 'above' for a directory standing in
    #  the root asked.
    component_db = {}
    for path in sorted(component_set):
        up = parent_of(path)
        if path == ".":      key = ""
        else:                key = _key_of_child(claim_db.get(up),
                                                 name_of(path))
        component_db[path] = CComponent(
            path, claim_db.get(path),
            tuple(sorted(each for each in component_set
                         if parent_of(each) == path)),
            next((each for each in sorted(test_directory_db)
                  if parent_of(each) == path), None), key)
    return CRelation(component_db, test_directory_db, above, top_f,
                     root_name, prefix, above_keys, explicit_f, top,
                     feature_map)


# -- the claims against the directories ----------------------------------

#  THE KINDS OF MISMATCH between what the files say and where the
#  directories stand.
NO_FILE   = "no-file"    # an explicit tree: the component states no file
UNLISTED  = "unlisted"   # a file stands; the directory above lists it not
DANGLING  = "dangling"   # a file lists a directory where nothing stands
TWIN      = "twin"       # a file lists one directory under two keys
MOVED     = "moved"      # stands below one parent, still listed by another
NO_MAP    = "no-map"     # features stand and no 'hwut-feature-map.conf'
UNMAPPED  = "unmapped"   # a feature no published id names
MAP_GONE  = "map-gone"   # an entry binds an id that names no feature
MAP_TWIN  = "map-twin"   # two entries bind one feature
MAP_CLASH = "map-clash"  # a retired id is a standing feature's full id

#  The kinds 'feature_adapt' heals by itself; the others are the
#  author's -- 'child_dropped' removes a DANGLING entry, 'map_retired' a
#  MAP_GONE one.
ADAPTED_KIND_TUPLE = (NO_FILE, UNLISTED, MOVED, NO_MAP, UNMAPPED)


@dataclass(frozen=True)
class CMismatch:
    """One disagreement. 'path' is the directory whose file is concerned:
    the CHILD for NO_FILE, UNLISTED and MOVED, the PARENT that lists for
    DANGLING and TWIN, the directory holding the map (relative to the
    root asked, '..' where it stands above) for the map kinds. 'id' is
    the directory name, the full id or the published id concerned;
    'from_path' is, for MOVED, the directory whose file still lists it."""
    kind:      str
    path:      str
    id:        str | None = None
    from_path: str | None = None


def claims_stated_f(relation):
    """
    RETURN: True, the tree states components: a 'hwut-features.conf'
            stands outside a TEST directory, in it or directly above
            False, it holds feature files in TEST directories only --
            nothing asks for a file at any other level
    """
    return relation.explicit_f


def _listed_directory_set(relation, path):
    """RETURN: set of str, the directories the claim at 'path' lists."""
    statement = relation.statement_of(path)
    return set() if statement is None else set(statement.directory_tuple())


def old_lister_of(relation, path):
    """
    RETURN: str, the path of the ONE component, other than the directory
            above 'path', whose file lists the directory called as 'path'
            while that directory does not stand below it -- where the
            directory came from, as the files still say
            None, no such component, or several
    """
    name  = name_of(path)
    found = []
    for other, component in sorted(relation.component_db.items()):
        if other == parent_of(path) or component.claim is None: continue
        child = component.claim.child_of_directory(name)
        if child is None: continue
        target = name if other == "." else "%s/%s" % (other, name)
        if target in relation.component_db: continue
        found.append(other)
    return found[0] if len(found) == 1 else None


def mismatch_list(relation):
    """
    RETURN: list of CMismatch, every disagreement between the files, the
            directories and the map, parents before their childs;
            empty where all agree.

    A TREE THAT STATES NO COMPONENT is not judged at all (E-144) -- but
    the map is: features stand, they are published.
    """
    result = []
    if relation.explicit_f:
        path_list = sorted(relation.component_db,
                           key=lambda path: (path != ".", path.split("/")))
        for path in path_list:
            result.extend(_upward_mismatch_list(relation, path))
            result.extend(_downward_mismatch_list(relation, path))
    result.extend(_map_mismatch_list(relation))
    return result


def _upward_mismatch_list(relation, path):
    """RETURN: list of CMismatch, what is wrong with the component at
    'path' against the directory above: NO_FILE where it states none,
    UNLISTED (MOVED where it came from elsewhere) where the file above
    does not list it."""
    result = []
    component = relation.component_db[path]
    if component.claim is None:
        result.append(CMismatch(NO_FILE, path))
    if parent_of(path) is None and relation.top_f:
        return result
    above = relation.statement_above(path)
    if above is None or component.claim is None:
        return result          # the directory above is mended first
    if above.child_of_directory(
            name_of(path) if path != "." else relation.root_name) is not None:
        return result
    from_path = old_lister_of(relation, path)
    if from_path is not None:
        result.append(CMismatch(MOVED, path, name_of(path), from_path))
    else:
        result.append(CMismatch(UNLISTED, path, name_of(path)))
    return result


def _downward_mismatch_list(relation, path):
    """RETURN: list of CMismatch, what the file of the component at
    'path' gets wrong about the directories below: DANGLING for a listed
    directory where no component stands (and none was moved away), TWIN
    for a directory listed under two keys."""
    result    = []
    statement = relation.statement_of(path)
    if statement is None: return result
    seen_db = {}
    for child in statement.child_tuple:
        seen_db.setdefault(child.directory, []).append(child)
    for directory, child_list in seen_db.items():
        if len(child_list) > 1:
            result.append(CMismatch(TWIN, path, directory))
    for directory in seen_db:
        target = directory if path == "." else "%s/%s" % (path, directory)
        if target in relation.component_db: continue
        if _moved_to(relation, path, directory) is not None: continue
        result.append(CMismatch(DANGLING, path, directory))
    return result


def _moved_to(relation, path, directory):
    """
    RETURN: str, the path of the component that is the directory called
            'directory' listed at 'path' and standing elsewhere now --
            the ONE other component of that name that states a file and
            is not listed by the directory above it
            None, none or several
    """
    found = []
    for other, component in relation.component_db.items():
        if name_of(other) != directory or other == ".": continue
        if parent_of(other) == path or component.claim is None: continue
        above = relation.statement_above(other)
        if above is not None \
           and above.child_of_directory(directory) is not None:
            continue
        found.append(other)
    return found[0] if len(found) == 1 else None


def feature_id_list(relation):
    """RETURN: list of (str, str, str), (full id, TEST directory path,
    feature name) of every feature in the relation, directories sorted,
    file order."""
    return [(relation.id_of(path, each.feature.name), path,
             each.feature.name)
            for path in sorted(relation.test_directory_db)
            for each in relation.test_directory_db[path].state_tuple]


def map_path_of(relation, root):
    """RETURN: str, where the map stands relative to 'root', the root
    asked: '.' where the root is the top of the tree, '..'-steps else."""
    if relation.top_directory is None: return "."
    return os.path.relpath(relation.top_directory,
                           os.path.abspath(root)).replace(os.sep, "/")


def _suffix_n(first, second):
    """RETURN: int, how many levels two full ids share, counted from
    their ends."""
    a, b, n = first.split("."), second.split("."), 0
    while n < len(a) and n < len(b) and a[-1 - n] == b[-1 - n]: n += 1
    return n


def map_pair_list(relation):
    """
    RETURN: list of (str, str), (published id, new full id) for every
            entry whose full id names no feature and that has a
            COUNTERPART: the one unmapped feature sharing the most levels
            with it, counted from the end, at least the feature's name.
            Where several entries or several features tie, none is
            paired: that is the author's.

    A directory moved by hand leaves exactly this behind -- entries of
    ids that are gone, features no entry names -- and the pairing
    carries the published ids to where the features stand now.
    """
    standing_set = {each for each, _, _ in feature_id_list(relation)}
    mapped_set   = {target for _, target, _ in
                    (relation.feature_map.entry_tuple
                     if relation.feature_map else ()) if target}
    unmapped = sorted(standing_set - mapped_set)
    gone     = [(each, target) for each, target, _ in
                (relation.feature_map.entry_tuple
                 if relation.feature_map else ())
                if target is not None and target not in standing_set]
    best_db, pair_list = {}, []
    for published, target in gone:
        score_db = {}
        for new in unmapped:
            n = _suffix_n(target, new)
            if n >= 1: score_db[new] = n
        if not score_db: continue
        top = max(score_db.values())
        winner_list = [new for new, n in score_db.items() if n == top]
        if len(winner_list) == 1:
            best_db[published] = (winner_list[0], top)
    for published, (new, n) in best_db.items():
        rival = [other for other, (other_new, other_n) in best_db.items()
                 if other_new == new and other != published]
        if rival: continue
        pair_list.append((published, new))
    return pair_list


def _map_mismatch_list(relation):
    """RETURN: list of CMismatch, what the map gets wrong about the
    features: NO_MAP, UNMAPPED, MAP_GONE (the pairing of 'map_pair_list'
    is NOT judged here: it is a healing, not a different fact), MAP_TWIN,
    MAP_CLASH. Empty where no feature stands. The entries are judged
    against the features only where the root asked is the top of the
    tree: below it, features outside are unseen."""
    feature_list = feature_id_list(relation)
    if not feature_list: return []
    where = "." if relation.top_f else ".."
    if relation.feature_map is None:
        return [CMismatch(NO_MAP, where, MAP_FILE_NAME)]
    result, target_db = [], {}
    for published, target, _ in relation.feature_map.entry_tuple:
        if target is not None: target_db.setdefault(target, []).append(
                                                        published)
    for target, published_list in sorted(target_db.items()):
        if len(published_list) > 1:
            result.append(CMismatch(MAP_TWIN, where, target))
    standing_set = {each for each, _, _ in feature_list}
    retired_set  = set(relation.retired_tuple())
    for full_id, path, _ in feature_list:
        if full_id in target_db: continue
        if full_id in retired_set:
            result.append(CMismatch(MAP_CLASH, where, full_id))
        else:
            result.append(CMismatch(UNMAPPED, path, full_id))
    if relation.top_f:
        paired_set = {published for published, _ in map_pair_list(relation)}
        for published, target, _ in relation.feature_map.entry_tuple:
            if target is None or target in standing_set: continue
            if published in paired_set: continue
            result.append(CMismatch(MAP_GONE, where, published))
    return result
