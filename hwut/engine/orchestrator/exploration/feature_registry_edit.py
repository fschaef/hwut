"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WRITING THE CENTRAL FILE (spec 23 VERSION 10 sections 3, 8;
         R-96) -- 'hwut-root-features.conf' composed once by
         'hwut.features.init', and amended afterwards by TEXT SURGERY
         ('amend.py'), one line at a time: what is not amended stays byte
         for byte, comments and layout included.

    composed_text(fact_db, id_list=None)       the file of 'init'
    directory_add_list(text, pair_list)        "<id>" = "<path>" lines
    leaf_add_list(text, pair_list)             "<external>" = "<internal>"
                                               at the top of 'tree'
    directory_redirect(text, id, path)         one 'directory_map' line
    leaf_repoint(text, external, internal)     one leaf's right side
    fold(text, later, first)                   a twin id folded into the
                                               first: its line goes, its
                                               leaves move to the first id
    new_directory_id(taken_set, token=None)    8 characters of base64url
    external_id_of(path, name, taken_set)      'gw.router.forward'
    edited(text, new_text)                     refuses an edit that adds a
                                               fault to the file

GUARDED. Every edit is re-read ('registry_of_text'); where the result
states more faults than the text it was made from, it is refused
(EditRefused) and nothing is written. Writing is atomic: a temporary file
beside the central file, renamed over it.
______________________________________________________________________________
"""
import base64
import os
import secrets

from .                 import amend
from .finder           import REGISTRY_FILE_NAME
from .feature_registry import (registry_of_text, word_valid_f,
                               DIRECTORY_ID_RE)

HEADER = """\
# hwut-root-features.conf -- THE ONE PLACE where the features of this tree
# are registered (HWUT, spec 23, RATIONALE R-96).
#
# A REGISTRY, NOT A GENERATED FILE. Keep it under version control; never
# delete it. 'hwut.features.register' will not make a new one where
# features stand, and the history of what was retired, when and by whom,
# is version control's.
#
# directory_map   "<directory id>" = "<path below hwut-root.conf>"
#     A directory whose TEST directory defines features. The ids are
#     generated: never edit one. A directory that moves changes ONE line
#     here ('hwut.features.move'), and every id below it stays valid.
#
# tree            the features as the world reads them
#     an AGGREGATE   <key> { title = "..."  doc = \"\"\"...\"\"\"  keys = [...]
#                            childs { ... } }
#     a LEAF         "<external id>" = "<directory id>:<feature name>"
#     THE EXTERNAL ID, left of a leaf line, is what customers, documents
#     and tickets refer to. It stays constant across every move, rename
#     and regrouping of the tree. Only when such an external reference
#     itself changes is a left side edited -- here, and nowhere else.
#     A new leaf is registered at the top of 'tree', unplaced: move its
#     line into an aggregate. A leaf stands under ONE aggregate; keys say
#     the other categories.
#
# retired         what is no longer claimed, kept as it was
#     ('hwut.features.retire'). Its ids are never given again; revival is
#     by hand: the block back into the tree, the definition back into the
#     TEST directory.
"""


class EditRefused(Exception):
    """An edit that would make the central file state a fault it did not
    state before; its text names the faults."""


# -- ids --------------------------------------------------------------------

def new_directory_id(taken_set, token=None):
    """RETURN: str, a directory id -- 8 characters of base64url, not
    beginning with '-' -- that is not in 'taken_set'. 'token' (a callable returning 6 bytes) stands
    in for the random source in a test."""
    if token is None: token = lambda: secrets.token_bytes(6)  # noqa: E731
    while True:
        candidate = base64.urlsafe_b64encode(token()).decode("ascii")
        #  NO LEADING '-': an id is typed on command lines ('redirect <id>'),
        #  and there it would read as an option.
        if DIRECTORY_ID_RE.match(candidate) and candidate[0] != "-" \
           and candidate not in taken_set:
            return candidate


def _word_of(text):
    """RETURN: str, 'text' made an identifier word: characters a word
    cannot hold become '_'; '_' where nothing is left."""
    word = "".join(each if word_valid_f("a" + each) and each != "." else "_"
                   for each in text)
    if word and not word_valid_f(word): word = "_" + word
    return word or "_"


def external_id_of(path, name, taken_set):
    """RETURN: str, the external id a leaf gets on first sight: the words of
    its directory's path and its name joined by '.' ('gw/router', 'forward'
    -> 'gw.router.forward'), each made a word; where that is in
    'taken_set', '-2', '-3', ... is appended. The root's own ('.') is the
    bare name: its path has no word (the book's D-3)."""
    base = ".".join([_word_of(part) for part in path.split("/")
                     if path != "."] + [name])
    candidate, n = base, 2
    while candidate in taken_set:
        candidate = "%s-%d" % (base, n)
        n += 1
    return candidate


# -- composing (init) ------------------------------------------------------

def composed_text(fact_db, id_list=None, taken_set=frozenset()):
    """RETURN: str, the text of a new central file: the header, one
    'directory_map' line per path of 'fact_db' (sorted), every name it
    defines as an UNPLACED leaf under its generated external id, an empty
    'retired'. 'id_list' gives the ids in path order (a test); else they
    are generated."""
    path_list = sorted(fact_db)
    taken = set(taken_set)
    if id_list is None:
        id_list = []
        for _ in path_list:
            id_list.append(new_directory_id(taken | set(id_list)))
    lines = [HEADER.rstrip("\n"), "features {", "    directory_map {"]
    for i, path in zip(id_list, path_list):
        lines.append('        "%s" = "%s"' % (i, path))
    lines += ["    }", "    tree {"]
    for i, path in zip(id_list, path_list):
        for name in fact_db[path]:
            external = external_id_of(path, name, taken)
            taken.add(external)
            lines.append('        "%s" = "%s:%s"' % (external, i, name))
    lines += ["    }", "    retired {", "    }", "}"]
    return "\n".join(lines) + "\n"


# -- amending ----------------------------------------------------------------

def _outer(text):
    """RETURN: amend.Container, the 'features { }' block; EditRefused where
    none stands."""
    container = amend.named_container(text, "features")
    if container is None:
        raise EditRefused("no 'features { }' stands in '%s'"
                          % REGISTRY_FILE_NAME)
    return container


def _section(text, name):
    """RETURN: tuple (str, amend.Container): 'text' with the section 'name'
    of 'features { }' standing (an empty one added where it is missing),
    and the section as a container."""
    outer = _outer(text)
    for entry in amend.entry_list(text, outer.i_open, outer.i_close):
        if entry.key == name and entry.object_f:
            return text, amend.scope_container(text, entry, outer)
    text = amend.entry_add(text, outer, "%s {\n%s}" % (name, outer.lead))
    return _section(text, name)


def _lines_added(text, name, line_list):
    """RETURN: str, 'text' with the entry lines 'line_list' added at the end
    of the section 'name', in its lead."""
    if not line_list: return text
    text, container = _section(text, name)
    lead = container.lead
    return amend.entry_add(text, container,
                           ("\n" + lead).join(line_list))


def directory_add_list(text, pair_list):
    """RETURN: str, 'text' with one '"<id>" = "<path>"' line per pair added
    to 'directory_map'."""
    return _lines_added(text, "directory_map",
                        ['"%s" = "%s"' % pair for pair in pair_list])


def leaf_add_list(text, pair_list):
    """RETURN: str, 'text' with one '"<external>" = "<internal>"' line per
    pair added at the top level of 'tree' -- unplaced."""
    return _lines_added(text, "tree",
                        ['"%s" = "%s"' % pair for pair in pair_list])


def _value_set(text, entry, value):
    """RETURN: str, 'text' with the value of 'entry' replaced by the quoted
    'value'."""
    return text[:entry.i_value] + '"%s"' % value + text[entry.i_end:]


def _directory_entry(text, directory_id):
    """RETURN: tuple (amend.Entry, amend.Container), the 'directory_map'
    line of 'directory_id'; EditRefused where it does not stand."""
    text, container = _section(text, "directory_map")
    for entry in amend.entry_list(text, container.i_open, container.i_close):
        if entry.key == directory_id and not entry.object_f:
            return entry, container
    raise EditRefused("no directory id '%s' stands" % directory_id)


def directory_redirect(text, directory_id, path):
    """RETURN: str, 'text' with the line of 'directory_id' standing for
    'path'."""
    entry, _ = _directory_entry(text, directory_id)
    return _value_set(text, entry, path)


def _leaf_walk(text, i_open, i_close):
    """YIELD: [0] amend.Entry, a leaf line at any depth of the tree below
                  the braces at 'i_open'..'i_close'
              [1] amend.Container, the braces it stands in, as a container
    """
    lead = amend._lead_of(text, i_open, i_close, "")
    container = amend.Container(i_open, i_close, "", lead)
    for entry in amend.entry_list(text, i_open, i_close):
        if not entry.object_f:
            yield entry, container
            continue
        for inner in amend.entry_list(text, entry.i_value, entry.i_end - 1):
            if inner.key == "childs" and inner.object_f:
                yield from _leaf_walk(text, inner.i_value, inner.i_end - 1)


def _leaf_list(text):
    """RETURN: list of (amend.Entry, amend.Container, str), every leaf line
    of the tree with its value unquoted, in file order."""
    text, container = _section(text, "tree")
    return [(entry, inner, text[entry.i_value:entry.i_end].strip('"'))
            for entry, inner in _leaf_walk(text, container.i_open,
                                           container.i_close)]


def leaf_repoint(text, external, internal):
    """RETURN: str, 'text' with the leaf 'external' bound to 'internal'."""
    text, _ = _section(text, "tree")
    for entry, _, _ in _leaf_list(text):
        if entry.key == external:
            return _value_set(text, entry, internal)
    raise EditRefused("no leaf '%s' stands in the tree" % external)


def fold(text, later, first):
    """RETURN: str, 'text' with the directory id 'later' folded into
    'first': its 'directory_map' line removed; each of its leaves bound to
    'first' -- or removed, where a leaf of 'first' of that name stands
    already (the same feature registered twice)."""
    _directory_entry(text, first)
    while True:
        name_set = {value.partition(":")[2] for _, _, value in _leaf_list(text)
                    if value.partition(":")[0] == first}
        hit = [(entry, container, value) for entry, container, value
               in _leaf_list(text) if value.partition(":")[0] == later]
        if not hit: break
        entry, container, value = hit[-1]
        name = value.partition(":")[2]
        if name in name_set:
            text = amend.entry_remove(text, container, entry)
        else:
            text = _value_set(text, entry, "%s:%s" % (first, name))
    entry, container = _directory_entry(text, later)
    return amend.entry_remove(text, container, entry)


def _aggregate_entry(text, key):
    """RETURN: tuple (amend.Entry, amend.Container), the aggregate 'key' at
    any depth of the tree and the braces it stands in; EditRefused where
    none stands."""
    text, container = _section(text, "tree")

    def walk(i_open, i_close):
        lead = amend._lead_of(text, i_open, i_close, "")
        here = amend.Container(i_open, i_close, "", lead)
        for entry in amend.entry_list(text, i_open, i_close):
            if not entry.object_f: continue
            if entry.key == key: return entry, here
            for inner in amend.entry_list(text, entry.i_value, entry.i_end - 1):
                if inner.key == "childs" and inner.object_f:
                    found = walk(inner.i_value, inner.i_end - 1)
                    if found is not None: return found
        return None

    found = walk(container.i_open, container.i_close)
    if found is None:
        raise EditRefused("no aggregate '%s' stands in the tree" % key)
    return found


def leaf_take(text, external):
    """RETURN: tuple (str, str): 'text' without the leaf line 'external',
    and its internal id; EditRefused where no such leaf stands."""
    for entry, container, value in _leaf_list(text):
        if entry.key == external:
            return amend.entry_remove(text, container, entry), value
    raise EditRefused("no leaf '%s' stands in the tree" % external)


def _block_leaves(block):
    """RETURN: list of (amend.Entry, amend.Container), the leaf lines below
    the aggregate text 'block' ('key { ... childs { ... } }'), at any depth,
    positions within 'block'."""
    i_open = block.index("{")
    for entry in amend.entry_list(block, i_open, len(block) - 1):
        if entry.key == "childs" and entry.object_f:
            return list(_leaf_walk(block, entry.i_value, entry.i_end - 1))
    return []


def aggregate_take(text, key):
    """RETURN: tuple (str, str, list, int): 'text' without the aggregate
    'key'; the aggregate's text as written ('key { ... }'); the (external,
    internal) of every leaf below it, in file order; the column its key
    stood at."""
    entry, container = _aggregate_entry(text, key)
    block = text[entry.i_key:entry.i_end]
    column = entry.i_key - (text.rfind("\n", 0, entry.i_key) + 1)
    leaf_list = [(each.key, block[each.i_value:each.i_end].strip('"'))
                 for each, _ in _block_leaves(block)]
    return amend.entry_remove(text, container, entry), block, leaf_list, \
           column


def leaf_block(external, internal, definition):
    """RETURN: str, a leaf as 'retired' keeps it: '"<external>" { id =
    "<internal>"  <definition> }' -- 'definition' the inner text of its
    TEST directory's entry, moved as written; '' where none stood."""
    inner = definition.strip()
    return '"%s" { id = "%s"%s }' % (external, internal,
                                     "  " + inner if inner else "")


def aggregate_block(block, definition_of):
    """RETURN: str, the aggregate text 'block' as 'retired' keeps it: every
    leaf line inside replaced by its leaf block, the definition of each
    taken from 'definition_of(external, internal)'."""
    for entry, _ in reversed(_block_leaves(block)):
        internal = block[entry.i_value:entry.i_end].strip('"')
        block = block[:entry.i_key] \
                + leaf_block(entry.key, internal,
                             definition_of(entry.key, internal)) \
                + block[entry.i_end:]
    return block


def retired_add(text, block, column=None):
    """RETURN: str, 'text' with 'block' added to the section 'retired'. A
    block that spans lines and stood at 'column' is shifted, line by line,
    to the lead of 'retired' -- layout only, the text is moved as it was."""
    if column is not None and "\n" in block:
        text, container = _section(text, "retired")
        shift = len(container.lead) - column
        line_list = block.split("\n")
        for i in range(1, len(line_list)):
            line = line_list[i]
            if shift >= 0:
                line_list[i] = " " * shift + line if line.strip() else line
            else:
                strip = min(-shift, len(line) - len(line.lstrip(" ")))
                line_list[i] = line[strip:]
        block = "\n".join(line_list)
    return _lines_added(text, "retired", [block])


def directory_prefix_move(text, old, new):
    """RETURN: tuple (str, list): 'text' with every 'directory_map' line
    whose path is 'old' or lies below it standing for the same place below
    'new'; the (id, old path, new path) changed."""
    changed = []
    while True:
        text, container = _section(text, "directory_map")
        hit = None
        for entry in amend.entry_list(text, container.i_open,
                                      container.i_close):
            path = text[entry.i_value:entry.i_end].strip('"')
            if path == old or path.startswith(old + "/"):
                if entry.key not in {each[0] for each in changed}:
                    hit = (entry, path)
                    break
        if hit is None: return text, changed
        entry, path = hit
        moved = new + path[len(old):]
        changed.append((entry.key, path, moved))
        text = _value_set(text, entry, moved)


# -- a TEST directory's feature file -------------------------------------

def _definition_entry(text, name):
    """RETURN: tuple (amend.Entry, amend.Container), the entry of the
    feature 'name' in the 'childs' of a TEST directory's feature file;
    None where it is not defined."""
    outer = amend.named_container(text, "features")
    if outer is None: return None
    for entry in amend.entry_list(text, outer.i_open, outer.i_close):
        if entry.key == "childs" and entry.object_f:
            childs = amend.scope_container(text, entry, outer)
            for inner in amend.entry_list(text, childs.i_open,
                                          childs.i_close):
                if inner.key == name and inner.object_f:
                    return inner, childs
    return None


def definition_renamed(text, name, new):
    """
    RETURN: str, the feature file 'text' with the definition of 'name'
            standing under the key 'new' -- its body, comments and layout
            untouched
            None, where 'name' is not defined
    """
    found = _definition_entry(text, name)
    if found is None: return None
    entry, _ = found
    i_key = entry.i_key
    for spelling in (name, '"%s"' % name):
        if text.startswith(spelling, i_key):
            return text[:i_key] + new + text[i_key + len(spelling):]
    raise EditRefused("the key of '%s' is not written as a name" % name)


def definition_take(text, name):
    """RETURN: tuple (str, str | None): the feature file 'text' without the
    definition of 'name', and the inner text of that definition as written;
    ('text', None) where it is not defined."""
    found = _definition_entry(text, name)
    if found is None: return text, None
    entry, childs = found
    inner = text[entry.i_value + 1:entry.i_end - 1]
    return amend.entry_remove(text, childs, entry), inner


def _key_container(text, entry, outer):
    """RETURN: amend.Container, the braces of 'entry' (a definition or an
    aggregate) to amend its 'keys' in."""
    return amend.scope_container(text, entry, outer)


def keys_of(text, container):
    """RETURN: list of str, the keys the list 'keys' of 'container' holds,
    as written; [] where none stands."""
    for entry in amend.entry_list(text, container.i_open, container.i_close):
        if entry.key == "keys":
            return amend.string_list_of(text[entry.i_value:entry.i_end])
    return []


def keys_without(text, container, key):
    """RETURN: str, 'text' with 'key' taken out of the list 'keys' of
    'container'; the entry removed where the list is left empty."""
    for entry in amend.entry_list(text, container.i_open, container.i_close):
        if entry.key != "keys": continue
        rest = [each for each in
                amend.string_list_of(text[entry.i_value:entry.i_end])
                if each != key]
        if not rest: return amend.entry_remove(text, container, entry)
        return text[:entry.i_value] \
               + "[%s]" % ", ".join('"%s"' % each for each in rest) \
               + text[entry.i_end:]
    return text


def definition_container(text, name):
    """RETURN: amend.Container, the braces of the definition of 'name' in a
    TEST directory's feature file; None where it is not defined."""
    found = _definition_entry(text, name)
    if found is None: return None
    entry, childs = found
    return _key_container(text, entry, childs)


def aggregate_container(text, key):
    """RETURN: amend.Container, the braces of the aggregate 'key' of the
    central file; EditRefused where none stands."""
    entry, container = _aggregate_entry(text, key)
    return _key_container(text, entry, container)


def aggregate_key_list(text):
    """RETURN: list of str, every aggregate key of the tree, outer first."""
    result = []
    text, container = _section(text, "tree")

    def walk(i_open, i_close):
        for entry in amend.entry_list(text, i_open, i_close):
            if not entry.object_f: continue
            result.append(entry.key)
            for inner in amend.entry_list(text, entry.i_value, entry.i_end - 1):
                if inner.key == "childs" and inner.object_f:
                    walk(inner.i_value, inner.i_end - 1)

    walk(container.i_open, container.i_close)
    return result


def edited(text, new_text):
    """RETURN: str, 'new_text' where it states no fault that 'text' did not;
    EditRefused naming the new faults, else."""
    before = {str(f) for f in registry_of_text(text).fault_tuple}
    after  = [str(f) for f in registry_of_text(new_text).fault_tuple]
    fresh  = [each for each in after if each not in before]
    if fresh:
        raise EditRefused("the edit would leave '%s' with a fault:\n  %s"
                          % (REGISTRY_FILE_NAME, "\n  ".join(fresh)))
    return new_text


def write_atomic(path, text):
    """RETURN: None. 'text' written to 'path' through a temporary file
    beside it, renamed over it."""
    temporary = path + ".tmp-%d" % os.getpid()
    with open(temporary, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(temporary, path)

