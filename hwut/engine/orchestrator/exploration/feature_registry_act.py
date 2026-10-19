"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ACTS ON THE CENTRAL FILE THAT TOUCH MORE THAN IT (spec 23
         VERSION 10 section 8, R-96) -- each computes every new text first,
         holds each against its faults, and only then writes; what it did is
         returned as lines for the face to print.

    retire(root, name)              a leaf, or an aggregate with all below
                                    it, moved into 'retired' AS IT WAS: the
                                    definitions leave their TEST directories
    move(root, old, new)            the directory 'old' renamed to 'new' and
                                    every 'directory_map' line at or below
                                    it following
    key_add(root, name, key)        a key on a leaf (in its TEST directory's
                                    definition) or an aggregate
    key_remove(root, name, key)     the key it states itself taken off
    key_remove_all(root, key)       the key taken off every claim stating it

'name' is an external id (a leaf) or an aggregate key: one namespace. Paths
are relative to 'root', '/'-separated. Every refusal is ActRefused with the
reason; nothing is written then.
______________________________________________________________________________
"""
import os

import re

from .feature_registry      import (registry_of_text, leaf_list,
                                    aggregate_list, name_set,
                                    retired_internal_set, word_valid_f)
from .feature_relation      import (feature_file_of_text, key_valid_f,
                                    TEST_NAME)
from .finder                import FEATURE_FILE_NAME, REGISTRY_FILE_NAME
from .                      import amend
from .feature_registry_edit import (EditRefused, edited, write_atomic,
                                    leaf_take, aggregate_take, leaf_block,
                                    aggregate_block, retired_add,
                                    directory_prefix_move, definition_take,
                                    definition_renamed, leaf_repoint,
                                    definition_container,
                                    aggregate_container, aggregate_key_list,
                                    keys_of, keys_without)


class ActRefused(Exception):
    """The act is refused; its text says why. Nothing was written."""


class ActFault(ActRefused):
    """The central file states what is not read; 'fault_list' holds the
    faults as text. Nothing was written."""

    def __init__(self, text, fault_list):
        ActRefused.__init__(self, text)
        self.fault_list = list(fault_list)


# -- reading ---------------------------------------------------------------

def _central(root):
    """RETURN: tuple (str, str, CRegistry): the path of the central file,
    its text, what it states. ActRefused where it does not stand or states
    a fault."""
    path = os.path.join(root, REGISTRY_FILE_NAME)
    if not os.path.exists(path):
        raise ActRefused("no '%s' stands => hwut.features.init"
                         % REGISTRY_FILE_NAME)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    registry = registry_of_text(text)
    if registry.fault_tuple:
        fault_list = [str(f) for f in registry.fault_tuple]
        raise ActFault("'%s' states what is not read:\n  %s"
                       % (REGISTRY_FILE_NAME, "\n  ".join(fault_list)),
                       fault_list)
    return path, text, registry


def _claim(registry, name):
    """RETURN: tuple (str, object): ('leaf', CLeaf) or ('aggregate',
    CAggregate) for 'name'. ActRefused where neither stands -- naming a
    retired one as such."""
    for _, leaf in leaf_list(registry):
        if leaf.external == name: return "leaf", leaf
    for _, aggregate in aggregate_list(registry):
        if aggregate.key == name: return "aggregate", aggregate
    if name in name_set(registry):
        raise ActRefused("'%s' is retired" % name)
    raise ActRefused("'%s' is no leaf and no aggregate of the tree => "
                     "hwut.features.tree -e" % name)


def _test_file(root, registry, leaf):
    """RETURN: tuple (str, str | None): the path of the feature file of the
    TEST directory defining 'leaf', and its text (None where it does not
    stand, or its directory id has no line)."""
    directory = registry.directory_of_id(leaf.directory_id)
    if directory is None: return None, None
    path = os.path.join(root, directory.path, TEST_NAME, FEATURE_FILE_NAME)
    if not os.path.exists(path): return path, None
    with open(path, encoding="utf-8") as fh:
        return path, fh.read()


def _test_edited(path, text, new_text):
    """RETURN: str, 'new_text' where the feature file states no fault the
    old 'text' did not; ActRefused else."""
    before = {str(f) for f in feature_file_of_text(text).fault_tuple}
    fresh  = [str(f) for f in feature_file_of_text(new_text).fault_tuple
              if str(f) not in before]
    if fresh:
        raise ActRefused("the edit would leave '%s' with a fault:\n  %s"
                         % (path, "\n  ".join(fresh)))
    return new_text


def _guarded(call, *argument):
    """RETURN: what 'call(*argument)' returns; its EditRefused as
    ActRefused."""
    try:
        return call(*argument)
    except EditRefused as error:
        raise ActRefused(str(error)) from None


def _relative(root, path):
    """RETURN: str, 'path' relative to 'root', '/'-separated."""
    return os.path.relpath(path, root).replace(os.sep, "/")


# -- retire ------------------------------------------------------------------

def retire(root, name):
    """RETURN: list of str, what was done: the leaf, or the aggregate with
    everything below it, moved into 'retired' as it was, each definition
    taken out of its TEST directory's feature file. ActRefused where
    'name' is no claim of the tree, or an edit would leave a fault."""
    path, text, registry = _central(root)
    kind, claim = _claim(registry, name)
    leaf_of = {leaf.external: leaf for _, leaf in leaf_list(registry)}
    if kind == "leaf":
        new_text, internal = _guarded(leaf_take, text, name)
        pair_list, column = [(name, internal)], None
    else:
        new_text, block, pair_list, column = _guarded(aggregate_take, text,
                                                      name)
    file_db, definition_db, line_list = {}, {}, []
    for external, internal in pair_list:
        leaf = leaf_of[external]
        test_path, test_text = _test_file(root, registry, leaf)
        if test_path is not None and test_text is not None:
            file_db.setdefault(test_path, [test_text, test_text])
            file_db[test_path][1], inner = definition_take(
                file_db[test_path][1], leaf.name)
        else:
            inner = None
        definition_db[internal] = inner or ""
        line_list.append("retired  %s  (%s)%s" % (
            external, internal,
            "" if inner is not None else "  -- no definition stood"))
    if kind == "leaf":
        block = leaf_block(name, pair_list[0][1],
                           definition_db[pair_list[0][1]])
    else:
        block = aggregate_block(block,
                                lambda e, i: definition_db.get(i, ""))
        line_list.insert(0, "retired  %s  (aggregate, %d leaf/leaves)"
                         % (name, len(pair_list)))
    new_text = _guarded(edited, text, _guarded(retired_add, new_text, block,
                                               column))
    for test_path, (old, new) in file_db.items():
        _test_edited(_relative(root, test_path), old, new)
    for test_path, (old, new) in sorted(file_db.items()):
        if new != old:
            write_atomic(test_path, new)
            line_list.append("    definition taken out of %s"
                             % _relative(root, test_path))
    write_atomic(path, new_text)
    return line_list


# -- rename ------------------------------------------------------------------

def rename(root, external, new):
    """
    RETURN: list of str, what was done: the feature behind the leaf
            'external' renamed to 'new' in the three places that name it --
            its definition in its TEST directory's 'hwut-features.conf',
            every link to it in that directory's test headers, the leaf's
            internal id in 'hwut-root-features.conf' -- the external id
            unchanged (the book's D-7; ruled 2026-10-17 "A").

    ActRefused where 'external' is no leaf, 'new' is no identifier word,
    is defined there already or names a retired claim, the definition does
    not stand, or an edit would leave a file with a fault. Nothing is
    written where anything is refused.
    """
    from .explorer import explore
    path, text, registry = _central(root)
    kind, leaf = _claim(registry, external)
    if kind != "leaf":
        raise ActRefused("'%s' is an aggregate: a key of the central file, "
                         "edited there" % external)
    if not word_valid_f(new):
        raise ActRefused("'%s' is no identifier word" % new)
    test_path, test_text = _test_file(root, registry, leaf)
    if test_text is None:
        raise ActRefused("no '%s' stands for '%s'" % (FEATURE_FILE_NAME,
                                                      external))
    new_internal = "%s:%s" % (leaf.directory_id, new)
    if new_internal in retired_internal_set(registry):
        raise ActRefused("'%s' is retired: never bound again" % new_internal)
    if definition_renamed(test_text, new, new) is not None:
        raise ActRefused("'%s' is defined already in %s"
                         % (new, _relative(root, test_path)))
    new_test_text = _guarded(definition_renamed, test_text, leaf.name, new)
    if new_test_text is None:
        raise ActRefused("'%s' is not defined in %s"
                         % (leaf.name, _relative(root, test_path)))
    _test_edited(_relative(root, test_path), test_text, new_test_text)
    new_text = _guarded(edited, text,
                        _guarded(leaf_repoint, text, external, new_internal))
    test_directory = os.path.dirname(test_path)
    link_db = {}
    for app in sorted(explore(test_directory).app_set,
                      key=lambda each: each.source_file):
        source = os.path.join(test_directory, app.source_file)
        with open(source, encoding="utf-8") as fh: before = fh.read()
        after = _links_renamed(before, leaf.name, new)
        if after != before: link_db[source] = after
    #  THE LINKS BY INTERNAL ID, from every other directory (D-8, R-4).
    foreign_db = {source: after for source, after in internal_links_planned(
                      root, lambda link: new_internal
                      if link == leaf.internal else None).items()
                  if source not in link_db}
    write_atomic(test_path, new_test_text)
    for source, after in link_db.items():
        mode = os.stat(source).st_mode
        write_atomic(source, after)
        os.chmod(source, mode)
    write_atomic(path, new_text)
    line_list = ["renamed  %s  %s -> %s" % (external, leaf.internal,
                                            new_internal),
                 "    definition renamed in %s" % _relative(root, test_path)]
    line_list += ["    link renamed in %s" % _relative(root, each)
                  for each in link_db]
    line_list += links_written(root, foreign_db)
    return line_list


_LINK_LIST_RE = re.compile(r"\bfeatures\s*=\s*\[[^\]]*\]", re.DOTALL)
_QUOTED_RE    = re.compile(r'"([^"]*)"')


def _links_mapped(text, map_f):
    """
    RETURN: str, the source 'text' with every quoted link inside a
            'features = [...]' of its '@hwut { }' header replaced by
            'map_f(link)' where that is not None -- the rest byte for byte
    """
    container = amend.header_container(text)
    if container is None: return text

    def quoted(match):
        found = map_f(match.group(1))
        return match.group(0) if found is None else '"%s"' % found

    head = text[container.i_open:container.i_close]
    head = _LINK_LIST_RE.sub(lambda m: _QUOTED_RE.sub(quoted, m.group(0)),
                             head)
    return text[:container.i_open] + head + text[container.i_close:]


def internal_links_planned(root, map_f):
    """
    RETURN: dict, source path -> its new text: every test application of
            the tree below 'root' whose header links by INTERNAL ID
            something 'map_f(internal id)' rewrites (the book's D-8, R-4)
            -- a name of a test's own directory is never touched. Nothing
            is written here.
    """
    from .feature_relation import internal_link_f
    from .tree_explorer    import explore_tree_stream

    def mapped(link):
        return map_f(link) if internal_link_f(link) else None

    plan_db = {}
    for relative, result in explore_tree_stream(root):
        directory = os.path.normpath(os.path.join(root, relative))
        for app in sorted(result.app_set, key=lambda a: a.source_file):
            source = os.path.join(directory, app.source_file)
            try:
                with open(source, encoding="utf-8") as fh: before = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            after = _links_mapped(before, mapped)
            if after != before: plan_db[source] = after
    return plan_db


def links_written(root, plan_db):
    """RETURN: list of str, one 'link rewritten in <file>' line per file of
    'plan_db' (path -> text), each written, its mode kept."""
    line_list = []
    for source in sorted(plan_db):
        mode = os.stat(source).st_mode
        write_atomic(source, plan_db[source])
        os.chmod(source, mode)
        line_list.append("    link rewritten in %s" % _relative(root, source))
    return line_list


def _links_renamed(text, old, new):
    """
    RETURN: str, the source 'text' with every '"old"' inside a
            'features = [...]' of its '@hwut { }' header written '"new"'
            -- the rest byte for byte
    """
    container = amend.header_container(text)
    if container is None: return text
    head = text[container.i_open:container.i_close]
    head = _LINK_LIST_RE.sub(lambda m: m.group(0).replace('"%s"' % old,
                                                          '"%s"' % new),
                             head)
    return text[:container.i_open] + head + text[container.i_close:]


# -- move --------------------------------------------------------------------

def move(root, old, new):
    """RETURN: list of str, what was done: the directory 'old' renamed to
    'new' (both relative to 'root'), every 'directory_map' line at or below
    it following. ActRefused where 'old' is the root or no directory, 'new'
    stands already, lies inside 'old', or its parent does not stand; the
    rename is undone where the central file cannot be written."""
    path, text, _ = _central(root)
    old, new = old.strip("/"), new.strip("/")
    if old in ("", ".") or new in ("", "."):
        raise ActRefused("the root itself is not moved")
    source, target = os.path.join(root, old), os.path.join(root, new)
    if not os.path.isdir(source):
        raise ActRefused("'%s' is no directory" % old)
    if os.path.lexists(target):
        raise ActRefused("'%s' stands already" % new)
    if new == old or new.startswith(old + "/"):
        raise ActRefused("'%s' lies inside '%s'" % (new, old))
    if not os.path.isdir(os.path.dirname(target)):
        raise ActRefused("the directory '%s' does not stand"
                         % (os.path.dirname(new) or "."))
    new_text, changed = _guarded(directory_prefix_move, text, old, new)
    new_text = _guarded(edited, text, new_text)
    os.rename(source, target)
    try:
        if changed: write_atomic(path, new_text)
    except OSError:
        os.rename(target, source)
        raise
    line_list = ["moved  %s -> %s" % (old, new)]
    line_list += ["    %s  %s -> %s" % each for each in changed]
    if not changed:
        line_list.append("    no directory id stands at or below it")
    return line_list


# -- keys --------------------------------------------------------------------

def _key_place(root, text, registry, name):
    """RETURN: tuple (str, str, amend.Container | None, bool): the path of
    the file the claim 'name' states its keys in, its text, the braces of
    the claim there, and whether it is the central file."""
    kind, claim = _claim(registry, name)
    if kind == "aggregate":
        return None, text, _guarded(aggregate_container, text, name), True
    test_path, test_text = _test_file(root, registry, claim)
    container = definition_container(test_text, claim.name) \
                if test_text is not None else None
    if container is None:
        raise ActRefused("'%s' (%s) is defined in no TEST directory"
                         % (name, claim.internal))
    return test_path, test_text, container, False


def key_add(root, name, key):
    """RETURN: list of str, what was done: 'key' added to the keys the claim
    'name' states itself. ActRefused where 'key' is no key, or the claim
    states it already."""
    if not key_valid_f(key):
        raise ActRefused("'%s' is no key: letters, digits, '_' and '-' -- "
                         "no dot" % key)
    path, text, registry = _central(root)
    file, file_text, container, central_f = _key_place(root, text,
                                                       registry, name)
    if key in keys_of(file_text, container):
        raise ActRefused("'%s' states the key '%s' already" % (name, key))
    new = amend.list_extend(file_text, container, "keys", [key])
    if central_f:
        write_atomic(path, _guarded(edited, text, new))
        where = REGISTRY_FILE_NAME
    else:
        write_atomic(file, _test_edited(_relative(root, file), file_text,
                                        new))
        where = _relative(root, file)
    return ["key '%s' added to %s  (%s)" % (key, name, where)]


def key_remove(root, name, key):
    """RETURN: list of str, what was done: 'key' taken off the keys the
    claim 'name' states itself. ActRefused where it states no such key --
    a key it carries from above is said so."""
    path, text, registry = _central(root)
    file, file_text, container, central_f = _key_place(root, text,
                                                       registry, name)
    if key not in keys_of(file_text, container):
        raise ActRefused("'%s' states no key '%s' of its own (a key from "
                         "above is taken off where it is stated)"
                         % (name, key))
    new = keys_without(file_text, container, key)
    if central_f:
        write_atomic(path, _guarded(edited, text, new))
        where = REGISTRY_FILE_NAME
    else:
        write_atomic(file, _test_edited(_relative(root, file), file_text,
                                        new))
        where = _relative(root, file)
    return ["key '%s' taken off %s  (%s)" % (key, name, where)]


def key_remove_all(root, key):
    """RETURN: list of str, what was done: 'key' taken off every aggregate,
    every definition of a registered leaf, and every TEST directory's
    feature file that states it for all its features. ActRefused where no
    claim states it."""
    path, text, registry = _central(root)
    line_list, new_text = [], text
    for aggregate_key in aggregate_key_list(text):
        container = aggregate_container(new_text, aggregate_key)
        if key in keys_of(new_text, container):
            new_text = keys_without(new_text, container, key)
            line_list.append("key '%s' taken off %s  (%s)"
                             % (key, aggregate_key, REGISTRY_FILE_NAME))
    file_db = {}
    for _, leaf in leaf_list(registry):
        test_path, test_text = _test_file(root, registry, leaf)
        if test_text is None: continue
        file_db.setdefault(test_path, [test_text, test_text])
        container = definition_container(file_db[test_path][1], leaf.name)
        if container is not None \
           and key in keys_of(file_db[test_path][1], container):
            file_db[test_path][1] = keys_without(file_db[test_path][1],
                                                 container, key)
            line_list.append("key '%s' taken off %s  (%s)"
                             % (key, leaf.external,
                                _relative(root, test_path)))
    for test_path, pair in sorted(file_db.items()):
        outer = amend.named_container(pair[1], "features")
        if outer is not None and key in keys_of(pair[1], outer):
            pair[1] = keys_without(pair[1], outer, key)
            line_list.append("key '%s' taken off every feature of %s"
                             % (key, _relative(root, test_path)))
    if not line_list:
        raise ActRefused("no claim states the key '%s'" % key)
    new_text = _guarded(edited, text, new_text)
    for test_path, (old, new) in file_db.items():
        _test_edited(_relative(root, test_path), old, new)
    for test_path, (old, new) in sorted(file_db.items()):
        if new != old: write_atomic(test_path, new)
    if new_text != text: write_atomic(path, new_text)
    return line_list


# -- register, and the proposals of the detector ---------------------------

def register(root, below=".", token=None):
    """RETURN: tuple (list, list, tuple): [0] (directory id, path) of every
    directory registered; [1] (external id, internal id) of every leaf
    registered -- the features of the new directories and those of
    registered ones that stood in no line, unplaced, under their first
    external ids; [2] what the detector finds afterwards (CDetection).
    Below 'below' only. ActRefused where no central file stands, it states a
    fault, or the edit would leave one. 'token' stands in for the random
    source of directory ids (a test)."""
    from .feature_detector      import (detect, fact_db_of_tree,
                                        DIR_NEW, LEAF_NEW, LEAF_GONE)
    from .feature_registry_edit import (directory_add_list, leaf_add_list,
                                        external_id_of, new_directory_id)
    path, text, registry = _central(root)
    found = detect(root, below)
    fact_db, _ = fact_db_of_tree(root)
    taken_id   = {each.id for each in registry.directory_tuple}
    taken_name = name_set(registry)
    id_of_path = {each.path: each.id for each in registry.directory_tuple}
    directory_list, leaf_pair_list, new_leaf = [], [], {}
    for directory in sorted(each.subject for each in found
                            if each.kind == DIR_NEW):
        directory_id = new_directory_id(taken_id, token)
        taken_id.add(directory_id)
        id_of_path[directory] = directory_id
        directory_list.append((directory_id, directory))
        new_leaf[directory] = set(fact_db.get(directory, ()))
    #  A DIRECTORY WITH A GONE LEAF THAT CANNOT BE PAIRED registers
    #  nothing new: its new names are the candidates of the gone ones,
    #  and an id minted for them would take the place of the external id
    #  the world knows (the book's D-7). The author pairs ('repoint') or
    #  renames ('hwut.features.rename'); what is new stays named until then.
    unpaired_directory = {each.path_tuple[0] for each in found
                          if each.kind == LEAF_GONE
                          and each.unpaired is not None and each.path_tuple}
    for each in found:
        if each.kind == LEAF_NEW \
           and each.path_tuple[0] not in unpaired_directory:
            new_leaf.setdefault(each.path_tuple[0], set()).add(
                each.subject.partition(":")[2])
    for directory in sorted(new_leaf):
        for name in fact_db.get(directory, ()):
            if name not in new_leaf[directory]: continue
            external = external_id_of(directory, name, taken_name)
            taken_name.add(external)
            leaf_pair_list.append(
                (external, "%s:%s" % (id_of_path[directory], name)))
    if directory_list or leaf_pair_list:
        new_text = _guarded(edited, text, leaf_add_list(
            directory_add_list(text, directory_list), leaf_pair_list))
        write_atomic(path, new_text)
        found = detect(root, below)
    return directory_list, leaf_pair_list, found


def apply_proposal(root, verb, word_tuple):
    """
    RETURN: list of str, what was done for the proposal line '<verb>
            <words>' ('redirect', 'repoint', 'fold') -- JUDGED AGAIN first:
            done only where the detector still proposes exactly that line;
            a redirect that is half of a swap takes its mate along in the
            same edit
            None, the detector proposes it no more: nothing to do
    ActRefused where no central file stands, it states a fault, or the edit
    would leave one.
    """
    from .feature_detector      import detect
    from .feature_registry_edit import (directory_redirect, leaf_repoint,
                                        fold)
    path, text, _ = _central(root)
    found = detect(root)
    wanted = (verb, tuple(word_tuple))
    hit = [each for each in found
           if any((v, w) == wanted for v, w, _ in each.command_tuple)]
    if not hit: return None
    line_list = []
    if verb == "redirect":
        pair_list = [tuple(word_tuple)]
        mate = [w for each in found if each.kind == "dir-swapped"
                for v, w, _ in each.command_tuple
                if v == "redirect" and w != tuple(word_tuple)
                and hit[0].kind == "dir-swapped"
                and w[1] in hit[0].path_tuple]
        pair_list += mate[:1]
        new_text = text
        for directory_id, new_path in pair_list:
            new_text = _guarded(directory_redirect, new_text, directory_id,
                                new_path)
            line_list.append("%s now stands for %s" % (directory_id,
                                                       new_path))
    elif verb == "repoint":
        new_text = _guarded(leaf_repoint, text, *word_tuple)
        line_list.append("%s now binds %s" % tuple(word_tuple))
        #  THE LINKS FOLLOW THE ID (the book's D-8, R-4).
        old = next((leaf.internal for _, leaf in leaf_list(registry_of_text(
                        text)) if leaf.external == word_tuple[0]), None)
        plan_db = {} if old is None else internal_links_planned(
            root, lambda link: word_tuple[1] if link == old else None)
    elif verb == "fold":
        new_text = _guarded(fold, text, *word_tuple)
        line_list.append("%s folded into %s" % tuple(word_tuple))
        later, first = word_tuple
        plan_db = internal_links_planned(
            root, lambda link: first + ":" + link.partition(":")[2]
            if link.partition(":")[0] == later else None)
    else:
        raise ActRefused("'%s' is no proposal of the detector" % verb)
    write_atomic(path, _guarded(edited, text, new_text))
    if verb != "redirect": line_list += links_written(root, plan_db)
    return line_list
