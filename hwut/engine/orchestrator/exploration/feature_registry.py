"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CENTRAL FILE OF THE FEATURES, read (exploration R-96, spec 23
         VERSION 10). ONE file, 'hwut-root-features.conf', beside
         'hwut-root.conf', registers the features of the whole tree:

    features {
        directory_map {                 # id -> where it stands
            "Qm9xB_2a" = "gateway/router"
        }
        tree {                          # the feature perspective
            gateway {                   # an AGGREGATE
                title  = "CAN-MOST gateway"
                keys   = ["product"]
                childs {
                    forwarding {
                        title  = "Frames reach their destination."
                        childs { "router.forward" = "Qm9xB_2a:forward" }
                    }                    #  ^ a LEAF: external = internal
                }
            }
            "new-thing" = "Qm9xB_2a:new-thing"   # registered, not placed
        }
        retired {                       # no longer claimed, as it was
            "scroll-old" { id = "Qm9xB_2a:scroll"  title = "..." }
            "old-group"  { title = "..."  childs { ... } }
        }
    }

    registry_of_text(text)    -> CRegistry   (every fault met is in it)
    read_registry(root)       -> CRegistry | None
    retired_internal_set(registry) -> set of str
    name_set(registry)        -> set of str  (the one namespace)
    leaf_list(registry)       -> list of (tree path, CLeaf)
    aggregate_list(registry)  -> list of (tree path, CAggregate)
    leaf_state / aggregate_state              (spec 23 section 6, o-14)

LAZY. Nothing is read at import, nor by a face that does not ask: the file
is read by 'read_registry', once per call.

A child of 'tree' that is a block is an AGGREGATE, one that is a text is a
LEAF: the key is its EXTERNAL id, the text its INTERNAL id,
'<directory id>:<name>'. Leaves at the top of 'tree' are UNPLACED. A leaf
stands under exactly one aggregate. In 'retired' a block with 'id' is a
leaf, a block with 'childs' an aggregate.

EVERY ID STANDS ONCE: an internal id in one place (tree or retired), an
external id once, an aggregate key once; aggregate keys and external ids
share ONE namespace. What stands twice is a fault and the first stands;
what the tree states that 'retired' states too is left out of the tree.

IDENTIFIERS (o-10): names, aggregate keys and the words of an external id
are Unicode identifiers (UAX #31: XID_Start, XID_Continue), widened by
DIGITS at the start and '-' in the continue part, in NFC, case kept. An
external id is such words joined by '.'. 'str.isidentifier()' implements
the classes. The 'keys' of a claim are read as 'feature_relation.key_valid_f'
reads them, and so are the names of a TEST file (o-10 not yet applied there).

A DIRECTORY ID is 8 characters of base64url, '[A-Za-z0-9_-]{8}'.
______________________________________________________________________________
"""
import os
import posixpath
import re
import unicodedata
from   dataclasses import dataclass

from ....test_writing_support.python.hwut_hocon import (ScalarNode,
                                                        ObjectNode)
from .fault            import Fault, E_FaultKind, Position
from .finder           import REGISTRY_FILE_NAME
from .feature_relation import (_outer_node, _sentence, _text_list,
                               _key_list, _text_of, PASS, NO_VERDICT)

DIRECTORY_ID_RE = re.compile(r"[A-Za-z0-9_\-]{8}\Z")

#  THE IMPLEMENTATION AXIS and the verdict beside it (spec 23 section 6).
IMPLEMENTED = "IMPLEMENTED"
OPEN        = "OPEN"
RETIRED     = "RETIRED"
OK          = "ok"
FAIL        = "fail"
UNTESTED    = "untested"          # no verdict measured (ruled 2026-10-17)


# -- identifiers (o-10) -------------------------------------------------

def word_valid_f(word):
    """RETURN: True, 'word' is one identifier word: not empty, in NFC,
    starting with an XID_Start character, '_' or a digit, continuing with
    XID_Continue characters or '-'; False else."""
    if not isinstance(word, str) or not word: return False
    if not unicodedata.is_normalized("NFC", word): return False
    first = word[0]
    if not (first.isidentifier() or first.isdecimal()): return False
    return all(("a" + each).isidentifier() or each == "-"
               for each in word[1:])


def external_id_valid_f(text):
    """RETURN: True, 'text' is an external id: identifier words joined by
    '.', none empty; False else. Blank, '/', ':', '*', '{' and ',' make
    it none."""
    return isinstance(text, str) \
           and all(word_valid_f(word) for word in text.split("."))


def internal_id_split(text):
    """
    RETURN: tuple (directory id, name), the two halves of an internal id
            '<directory id>:<name>'
            None, 'text' is none: a directory id of the wrong shape, no
            ':' or a name that is no identifier word
    """
    if not isinstance(text, str) or text.count(":") != 1: return None
    directory_id, name = text.split(":")
    if DIRECTORY_ID_RE.match(directory_id) and word_valid_f(name):
        return directory_id, name
    return None


def path_valid_f(path):
    """RETURN: True, 'path' is the directory holding 'hwut-root.conf' ('.',
    whose own TEST directory may define features too -- the book's D-3) or
    a path below it: relative, normal, no '..', not empty; False else."""
    return isinstance(path, str) and bool(path) \
           and not os.path.isabs(path) \
           and posixpath.normpath(path) == path \
           and ".." not in path.split("/")


# -- what the file states -----------------------------------------------

@dataclass(frozen=True)
class CDirectory:
    """One line of 'directory_map': the id 'id' stands for the directory
    'path', below the directory holding 'hwut-root.conf'."""
    id:     str
    path:   str
    line_n: int = 0


@dataclass(frozen=True)
class CLeaf:
    """One leaf line of the tree: 'external' is the id the world knows,
    'directory_id' and 'name' make the internal id."""
    external:     str
    directory_id: str
    name:         str
    line_n:       int = 0

    @property
    def internal(self):
        """RETURN: str, '<directory id>:<name>'."""
        return "%s:%s" % (self.directory_id, self.name)


@dataclass(frozen=True)
class CAggregate:
    """One aggregate of the tree: a claim implemented by the claims in
    'child_tuple' (CAggregate | CLeaf, file order)."""
    key:            str
    title:          str | None = None
    doc:            str | None = None
    document_tuple: tuple      = ()
    key_tuple:      tuple      = ()     # of str: keys for everything below
    child_tuple:    tuple      = ()
    line_n:         int        = 0


@dataclass(frozen=True)
class CRetired:
    """One claim of 'retired', as it was. 'internal' is the internal id of
    a leaf, None for an aggregate; 'child_tuple' (of CRetired) is empty for
    a leaf."""
    name:           str                  # external id | aggregate key
    internal:       str | None = None
    title:          str | None = None
    doc:            str | None = None
    document_tuple: tuple      = ()
    key_tuple:      tuple      = ()
    child_tuple:    tuple      = ()
    line_n:         int        = 0

    @property
    def leaf_f(self):
        """RETURN: True, it is a leaf; False, an aggregate."""
        return self.internal is not None


@dataclass(frozen=True)
class CRegistry:
    """What the central file states, and every fault met."""
    directory_tuple: tuple = ()        # of CDirectory, file order
    tree_tuple:      tuple = ()        # of CAggregate | CLeaf, file order
    retired_tuple:   tuple = ()        # of CRetired, file order
    fault_tuple:     tuple = ()        # of Fault

    def directory_of_id(self, directory_id):
        """
        RETURN: CDirectory, the line of 'directory_id'
                None, no such id stands
        """
        for each in self.directory_tuple:
            if each.id == directory_id: return each
        return None

    def directory_of_path(self, path):
        """
        RETURN: CDirectory, the first line that stands for 'path'
                None, none does
        """
        for each in self.directory_tuple:
            if each.path == path: return each
        return None


# -- reading --------------------------------------------------------------

def read_registry(root):
    """
    RETURN: CRegistry, what 'root/hwut-root-features.conf' states
            None, no such file stands
    """
    text = _text_of(os.path.join(root, REGISTRY_FILE_NAME))
    if text is None: return None
    return registry_of_text(text, REGISTRY_FILE_NAME)


def registry_of_text(text, file=REGISTRY_FILE_NAME):
    """RETURN: CRegistry, what 'text' states. Every fault met stands in its
    'fault_tuple'; what stands twice, or is no identifier, is left out and
    the first stands."""
    fault_list      = []
    outer           = _outer_node(text, file, "features", fault_list)
    directory_tuple = ()
    tree_tuple      = ()
    retired_tuple   = ()
    for entry in outer.entry_list if outer is not None else ():
        if not isinstance(entry.node, ObjectNode):
            fault_list.append(Fault(
                E_FaultKind.TYPE, file, entry.key_position,
                "'%s' is a block: %s { ... }" % (entry.key, entry.key)))
        elif entry.key == "directory_map":
            directory_tuple = _directory_tuple(entry.node, file, fault_list)
        elif entry.key == "tree":
            tree_tuple = _tree_tuple(entry.node, file, fault_list, False)
        elif entry.key == "retired":
            retired_tuple = _retired_tuple(entry.node, file, fault_list)
        else:
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, file, entry.key_position,
                "unknown key '%s' in 'features': 'directory_map', 'tree', "
                "'retired'" % entry.key))
    tree_tuple = _without_retired(tree_tuple, retired_tuple, file,
                                  fault_list)
    tree_tuple = _once(tree_tuple, retired_tuple, file, fault_list)
    return CRegistry(directory_tuple, tree_tuple, retired_tuple,
                     tuple(fault_list))


def _fault(file, entry, kind, message, fault_list):
    """RETURN: None. Records a fault at the key of 'entry'."""
    fault_list.append(Fault(kind, file, entry.key_position, message))


def _line_fault(file, line_n, message):
    """RETURN: Fault, a VOCABULARY fault at the start of line 'line_n'."""
    return Fault(E_FaultKind.VOCABULARY, file, Position(line_n, 1), message)


def _directory_tuple(node, file, fault_list):
    """RETURN: tuple of CDirectory, the lines of 'directory_map'; a line
    whose id is no directory id, or whose path is not a path below the
    root, is a fault and left out."""
    result = []
    for entry in node.entry_list:
        value = entry.node.value if isinstance(entry.node, ScalarNode) \
                else None
        if not DIRECTORY_ID_RE.match(entry.key):
            _fault(file, entry, E_FaultKind.VOCABULARY,
                   "'%s' is no directory id: 8 characters of base64url "
                   "(letters, digits, '_', '-')" % entry.key, fault_list)
        elif not path_valid_f(value):
            _fault(file, entry, E_FaultKind.TYPE,
                   "'%s' stands for a path below the root: relative, "
                   "no '..'; '.' is the root itself" % entry.key, fault_list)
        else:
            result.append(CDirectory(entry.key, value,
                                     entry.key_position.line))
    return tuple(result)


def _fields(entry, file, fault_list, known):
    """RETURN: dict, the fields of the block 'entry' among 'known' ('title',
    'doc', 'documents', 'keys', 'childs', 'id'): the value as read; a field
    that is not read is a fault and absent; an unknown key is a fault."""
    result = {}
    for inner in entry.node.entry_list:
        if inner.key not in known:
            _fault(file, inner, E_FaultKind.VOCABULARY,
                   "unknown key '%s' in '%s': %s"
                   % (inner.key, entry.key,
                      ", ".join("'%s'" % each for each in known)),
                   fault_list)
        elif inner.key in ("title", "doc", "id"):
            value = _sentence(inner, file, fault_list)
            if value is not None: result[inner.key] = value
        elif inner.key == "documents":
            found = _text_list(inner, file, fault_list,
                               "a list of file names: documents = "
                               "[\"README.txt\", ...]")
            if found is not None: result["documents"] = found
        elif inner.key == "keys":
            result["keys"] = _key_list(inner, file, fault_list)
        elif inner.key == "childs":
            if isinstance(inner.node, ObjectNode):
                result["childs"] = inner
            else:
                _fault(file, inner, E_FaultKind.TYPE,
                       "'childs' is a block: childs { ... }", fault_list)
    return result


def _tree_tuple(node, file, fault_list, nested_f):
    """RETURN: tuple of CAggregate | CLeaf, the children of the block
    'node'. A block is an aggregate, a text a leaf; anything else, and a
    name that is no identifier, is a fault and left out. Leaves at the top
    are unplaced; 'none' is not written in the tree (a claim leaves it
    through 'retire')."""
    result = []
    for entry in node.entry_list:
        if isinstance(entry.node, ObjectNode):
            if not word_valid_f(entry.key):
                _fault(file, entry, E_FaultKind.VOCABULARY,
                       "'%s' is no aggregate key: an identifier of one "
                       "word, no dot" % entry.key, fault_list)
                continue
            field_db = _fields(entry, file, fault_list,
                               ("title", "doc", "documents", "keys",
                                "childs"))
            inner = field_db.get("childs")
            result.append(CAggregate(
                entry.key, field_db.get("title"), field_db.get("doc"),
                field_db.get("documents", ()), field_db.get("keys", ()),
                _tree_tuple(inner.node, file, fault_list, True)
                if inner is not None else (),
                entry.key_position.line))
        elif isinstance(entry.node, ScalarNode) \
             and isinstance(entry.node.value, str):
            split = internal_id_split(entry.node.value)
            if not external_id_valid_f(entry.key):
                _fault(file, entry, E_FaultKind.VOCABULARY,
                       "'%s' is no external id: identifier words joined "
                       "by '.'" % entry.key, fault_list)
            elif split is None:
                _fault(file, entry, E_FaultKind.TYPE,
                       "'%s' is bound to an internal id "
                       "\"<directory id>:<name>\"" % entry.key, fault_list)
            else:
                result.append(CLeaf(entry.key, split[0], split[1],
                                    entry.key_position.line))
        elif isinstance(entry.node, ScalarNode) and entry.node.value is None:
            _fault(file, entry, E_FaultKind.TYPE,
                   "'%s' is none: a claim that is no more stands in "
                   "'retired' (hwut.features.retire)" % entry.key,
                   fault_list)
        else:
            _fault(file, entry, E_FaultKind.TYPE,
                   "'%s' is an aggregate (a block) or a leaf (its internal "
                   "id)" % entry.key, fault_list)
    return tuple(result)


def _retired_tuple(node, file, fault_list):
    """RETURN: tuple of CRetired, the claims of 'retired'. A block with 'id'
    is a leaf, one with 'childs' an aggregate; both or neither is a fault
    and the block is left out."""
    result = []
    for entry in node.entry_list:
        if not isinstance(entry.node, ObjectNode):
            _fault(file, entry, E_FaultKind.TYPE,
                   "'%s' is a block: a leaf { id = ... } or an aggregate "
                   "{ childs { ... } }" % entry.key, fault_list)
            continue
        field_db = _fields(entry, file, fault_list,
                           ("id", "title", "doc", "documents", "keys",
                            "childs"))
        has_id, has_childs = "id" in field_db, "childs" in field_db
        if has_id and has_childs:
            _fault(file, entry, E_FaultKind.VOCABULARY,
                   "'%s' is a leaf ('id') or an aggregate ('childs'), "
                   "not both" % entry.key, fault_list)
        elif has_id:
            internal = field_db["id"]
            if internal_id_split(internal) is None:
                _fault(file, entry, E_FaultKind.TYPE,
                       "'id' of '%s' is an internal id \"<directory "
                       "id>:<name>\"" % entry.key, fault_list)
            elif not external_id_valid_f(entry.key):
                _fault(file, entry, E_FaultKind.VOCABULARY,
                       "'%s' is no external id" % entry.key, fault_list)
            else:
                result.append(CRetired(
                    entry.key, internal, field_db.get("title"),
                    field_db.get("doc"), field_db.get("documents", ()),
                    field_db.get("keys", ()), (), entry.key_position.line))
        elif not word_valid_f(entry.key):
            _fault(file, entry, E_FaultKind.VOCABULARY,
                   "'%s' is no aggregate key" % entry.key, fault_list)
        else:
            inner = field_db.get("childs")
            result.append(CRetired(
                entry.key, None, field_db.get("title"), field_db.get("doc"),
                field_db.get("documents", ()), field_db.get("keys", ()),
                _retired_tuple(inner.node, file, fault_list)
                if inner is not None else (), entry.key_position.line))
    return tuple(result)


def _retired_name_set(retired_tuple):
    """RETURN: tuple of three sets: [0] the names (external ids and
    aggregate keys), [1] the internal ids, of everything retired, to any
    depth."""
    name_set, internal_set = set(), set()
    for each in retired_tuple:
        name_set.add(each.name)
        if each.internal is not None: internal_set.add(each.internal)
        inner_name, inner_internal = _retired_name_set(each.child_tuple)
        name_set |= inner_name
        internal_set |= inner_internal
    return name_set, internal_set


def retired_internal_set(registry):
    """RETURN: set of str, every internal id the registry retired, at any
    depth: none of them is ever bound again."""
    return _retired_name_set(registry.retired_tuple)[1]


def name_set(registry):
    """RETURN: set of str, every name of the ONE namespace the registry
    holds -- external ids and aggregate keys, of the tree and of
    'retired' -- none of which a new leaf may take."""
    result = _retired_name_set(registry.retired_tuple)[0]

    def walk(child_tuple):
        for each in child_tuple:
            if isinstance(each, CLeaf):
                result.add(each.external)
            else:
                result.add(each.key)
                walk(each.child_tuple)

    walk(registry.tree_tuple)
    return result


def _without_retired(tree_tuple, retired_tuple, file, fault_list):
    """RETURN: tuple of CAggregate | CLeaf, 'tree_tuple' without what
    'retired' states too: an external id, an aggregate key or an internal
    id that was retired is never bound again (a fault; the retired stands)."""
    name_set, internal_set = _retired_name_set(retired_tuple)
    result = []
    for each in tree_tuple:
        if isinstance(each, CLeaf):
            if each.external in name_set or each.internal in internal_set:
                fault_list.append(_line_fault(
                    file, each.line_n,
                    "'%s' (%s) is retired; it is never bound again"
                    % (each.external, each.internal)))
                continue
            result.append(each)
        else:
            if each.key in name_set:
                fault_list.append(_line_fault(
                    file, each.line_n,
                    "'%s' is retired; it is never bound again" % each.key))
                continue
            result.append(CAggregate(
                each.key, each.title, each.doc, each.document_tuple,
                each.key_tuple,
                _without_retired(each.child_tuple, retired_tuple, file,
                                 fault_list), each.line_n))
    return tuple(result)


def _once(tree_tuple, retired_tuple, file, fault_list):
    """RETURN: tuple of CAggregate | CLeaf, 'tree_tuple' where every name
    (aggregate keys and external ids share one namespace) and every
    internal id stands once; the first stands, a second is a fault and
    left out."""
    name_seen, internal_seen = {}, {}

    def walk(child_tuple):
        result = []
        for each in child_tuple:
            name = each.external if isinstance(each, CLeaf) else each.key
            if name in name_seen:
                fault_list.append(_line_fault(
                    file, each.line_n,
                    "'%s' stands twice (line %d); the first stands"
                    % (name, name_seen[name])))
                continue
            if isinstance(each, CLeaf) and each.internal in internal_seen:
                fault_list.append(_line_fault(
                    file, each.line_n,
                    "internal id '%s' stands twice (line %d); the first "
                    "stands" % (each.internal,
                                internal_seen[each.internal])))
                continue
            name_seen[name] = each.line_n
            if isinstance(each, CLeaf):
                internal_seen[each.internal] = each.line_n
                result.append(each)
            else:
                result.append(CAggregate(
                    each.key, each.title, each.doc, each.document_tuple,
                    each.key_tuple, walk(each.child_tuple), each.line_n))
        return tuple(result)

    return walk(tree_tuple)


# -- the tree, as paths ---------------------------------------------------

def leaf_list(registry):
    """RETURN: list of (str, CLeaf), every leaf of the tree in file order
    with its tree path: the aggregate keys above it joined by '/'; '' for an
    unplaced leaf."""
    result = []

    def walk(child_tuple, path):
        for each in child_tuple:
            if isinstance(each, CLeaf):
                result.append((path, each))
            else:
                walk(each.child_tuple, path + "/" + each.key if path
                     else each.key)

    walk(registry.tree_tuple, "")
    return result


def aggregate_list(registry):
    """RETURN: list of (str, CAggregate), every aggregate with its tree
    path ('gateway/forwarding'), parents before children."""
    result = []

    def walk(child_tuple, path):
        for each in child_tuple:
            if isinstance(each, CAggregate):
                here = path + "/" + each.key if path else each.key
                result.append((here, each))
                walk(each.child_tuple, here)

    walk(registry.tree_tuple, "")
    return result


def aggregate_key_tuple(registry, external):
    """
    RETURN: tuple of str, the keys of the aggregates above the leaf
            'external', outermost first, each once (keys travel
            downward only)
            None, no such leaf stands in the tree
    """
    def walk(child_tuple, key_list):
        for each in child_tuple:
            if isinstance(each, CLeaf):
                if each.external == external: return tuple(key_list)
            else:
                found = walk(each.child_tuple,
                             key_list + [key for key in each.key_tuple
                                         if key not in key_list])
                if found is not None: return found
        return None

    return walk(registry.tree_tuple, [])


# -- states (spec 23 section 6, o-14) -----------------------------------

@dataclass(frozen=True)
class CState:
    """A claim's state on the two axes. 'implementation' is IMPLEMENTED,
    OPEN or RETIRED; 'verdict' is OK, FAIL or UNTESTED, None where
    RETIRED. THE AXES ARE INDEPENDENT (ruled 2026-10-17): an open claim
    has no measured verdict -- it is UNTESTED, not FAIL."""
    implementation: str
    verdict:        str | None


def leaf_state(verdict_tuple):
    """RETURN: CState, the state of a leaf whose linked test runs have the
    verdicts 'verdict_tuple' (PASS, FAIL, NO_VERDICT): no run is OPEN
    untested; runs are IMPLEMENTED -- fail where one fails, else untested
    where one has no verdict (it never ran), else ok."""
    if not verdict_tuple: return CState(OPEN, UNTESTED)
    return CState(IMPLEMENTED, _verdict_folded(
        [OK if each == PASS else UNTESTED if each == NO_VERDICT else FAIL
         for each in verdict_tuple]))


def _verdict_folded(verdict_list):
    """RETURN: str, the verdict of a claim from those below it, worst
    first: FAIL where one fails, else UNTESTED where one is untested,
    else OK."""
    if FAIL in verdict_list:     return FAIL
    if UNTESTED in verdict_list: return UNTESTED
    return OK


def retired_state():
    """RETURN: CState, the state of a retired claim: RETIRED, no verdict."""
    return CState(RETIRED, None)


def aggregate_state(state_tuple):
    """RETURN: CState, the state of an aggregate whose claims below it have
    the states 'state_tuple': RETIRED where every one is retired;
    otherwise the retired are ignored, and the two axes fold apart: it is
    IMPLEMENTED only if every remaining one is (else OPEN); its verdict is
    the worst below it ('_verdict_folded'). An aggregate with nothing
    below it is OPEN untested (ASSUMED, o-14, unconfirmed: retire the
    aggregate, not its leaves one by one)."""
    if not state_tuple: return CState(OPEN, UNTESTED)
    standing = [each for each in state_tuple if each.implementation != RETIRED]
    if not standing: return CState(RETIRED, None)
    implementation = OPEN if any(each.implementation == OPEN
                                 for each in standing) else IMPLEMENTED
    return CState(implementation,
                  _verdict_folded([each.verdict for each in standing]))
