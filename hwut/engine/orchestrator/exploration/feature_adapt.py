"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: ADAPTING THE FEATURE STATEMENTS TO WHERE THINGS STAND -- the
         one implementation behind every face that moves, renames,
         removes or sanitizes: 'hwut.sanitize relate / unrelate / retire',
         'hwut.move', 'hwut.rename', 'hwut.remove'.

    adapt_directory(root, directory)        a directory's file, its entry
                                            in the file above, and the
                                            map entries of its features,
                                            made to agree with where
                                            things stand
    child_dropped(root, directory, name)    a 'childs' entry listing a
                                            directory where nothing
                                            stands, removed
    map_retired(root, published)            a map entry whose feature is
                                            gone, bound to none
    test_moved(source, target, test, name)  the features a test proves,
                                            carried after it into the
                                            feature file of its new TEST
                                            directory, and their
                                            published ids with them
    unproven_by_removal(directory, test, choice)
                                            the features a removed test
                                            leaves without a linked run

WHAT 'adapt_directory' DOES, in this order, each step only where the
files disagree with the directories:

    1  the component states no file   'features { }' written, empty (an
       (an explicit tree)             author fills the title)
    2  the file above does not list   an entry '<key> = "./<directory>"'
       the directory                  added to its 'childs' -- and where
                                      ANOTHER file still lists the
                                      directory while it stands elsewhere
                                      now (A DETECTED MOVE), that entry is
                                      CARRIED, KEY AND ALL: removed there,
                                      written here -- so the ids below
                                      keep their keys
    3  a feature has no published     an entry '"<full id>" = "<full id>"'
       id (the map)                   added -- or, where a published id
                                      is bound to a full id that stands
                                      no more and the feature is its
                                      one counterpart (A DETECTED MOVE OF
                                      THE FEATURE), that entry REPOINTED
    4  no map stands                  the map written, an entry per
                                      feature

TEXT IS MOVED, NEVER COMPOSED. A key travels as its author wrote it;
where none is at hand the directory's name is the key. Every edit is text
surgery through 'amend.py': what is not adapted stays byte for byte.

A PUBLISHED ID IS NEVER REWRITTEN BY AN ADAPTION, only what it is bound
to. The one exception is a published id bound to none: RETIRED stays.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from .                 import amend
from .explorer         import explore
from .feature_relation import (ADAPTED_KIND_TUPLE, DANGLING, MOVED, NO_FILE,
                               NO_MAP, UNLISTED, UNMAPPED,
                               FEATURE_FILE_NAME, MAP_FILE_NAME,
                               directory_of_reference, feature_id_list,
                               full_id_of, key_of_name, linked_name_tuple,
                               map_pair_list, mismatch_list, name_of,
                               parent_of, read_feature_file,
                               read_feature_map, relation_of_tree,
                               top_directory_of)


@dataclass(frozen=True)
class CAdapted:
    """WHAT AN ADAPTION DID, as data: 'said_tuple' one line per edit
    made, telegraphic; 'reason' why nothing more could be done, '' where
    nothing was left to do."""
    said_tuple: tuple = ()
    reason:     str   = ""

    def changed_f(self):
        """RETURN: bool, True where at least one file was edited."""
        return bool(self.said_tuple)


# -- text surgery on one statement file -----------------------------------

def _entry(text, container, key):
    """
    RETURN: amend.Entry, the container's top-level entry called 'key'
            None, it holds none
    """
    for entry in amend.entry_list(text, container.i_open, container.i_close):
        if entry.key == key: return entry
    return None


def _quoted(value):
    """RETURN: str, 'value' as a quoted text of the statement language."""
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def _key(value):
    """RETURN: str, 'value' as a key: bare where the language reads it
    bare, quoted else."""
    return value if amend._KEY_RE.fullmatch(value) \
           and "." not in value else _quoted(value)


def _features_container(text):
    """RETURN: amend.Container, the braces of the file's 'features { }';
    None where it holds none."""
    return amend.named_container(text, "features")


def _childs_scope(text):
    """
    RETURN: [0] str, 'text' -- with an empty 'childs { }' added to the
                file's 'features { }' where it held none
            [1] amend.Container, the braces of that 'childs' scope
    """
    container = _features_container(text)
    entry     = _entry(text, container, "childs")
    if entry is None or not entry.object_f:
        text      = amend.entry_add(text, container, "childs {\n    }")
        container = _features_container(text)
        entry     = _entry(text, container, "childs")
    return text, amend.scope_container(text, entry, container)


def child_text_added(text, key, directory):
    """RETURN: str, 'text' with '<key> = "./<directory>"' entered in the
    'childs { }' of its 'features { }' -- a new 'childs { }' where none
    stands."""
    text, scope = _childs_scope(text)
    return amend.entry_add(text, scope,
                           '%s = "./%s"' % (_key(key), directory))


def child_text_removed(text, directory):
    """
    RETURN: [0] str, 'text' without every entry of the 'childs' of its
                'features { }' that lists the directory 'directory' --
                its line with it where nothing else stood there
            [1] str, the key the first of them carried; None where none
                listed it
    """
    found = None
    while True:
        container = _features_container(text)
        entry     = _entry(text, container, "childs") \
                    if container is not None else None
        if entry is None or not entry.object_f: return text, found
        scope = amend.scope_container(text, entry, container)
        hit   = None
        for inner in amend.entry_list(text, scope.i_open, scope.i_close):
            if inner.object_f or text[inner.i_value] != '"': continue
            if directory_of_reference(text[inner.i_value + 1:inner.i_end - 1]) \
               == directory:
                hit = inner
                break
        if hit is None: return text, found
        if found is None: found = hit.key
        text = amend.entry_remove(text, scope, hit)


def map_text_added(text, container, published, target):
    """RETURN: str, 'text' with '"<published>" = "<target>"' added to the
    map's container."""
    return amend.entry_add(text, container,
                           "%s = %s" % (_quoted(published), _quoted(target)))


def map_text_bound(text, container, published, target):
    """
    RETURN: str, 'text' with the entry 'published' bound to the full id
            'target', or -- where 'target' is None -- to none: RETIRED;
            the text unchanged where it holds no such entry
    """
    for entry in amend.entry_list(text, container.i_open, container.i_close):
        if entry.key != published: continue
        return text[:entry.i_value] \
               + ("none" if target is None else _quoted(target)) \
               + text[entry.i_end:]
    return text


# -- files ------------------------------------------------------------------

def _read(path):
    """RETURN: str, the file's text."""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, text):
    """RETURN: None. The file replaced by 'text', atomically."""
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temporary, path)


def _path_of(root, directory):
    """RETURN: str, 'directory' as the relation of 'root' addresses it:
    relative, '/'-separated, '.' for the root itself."""
    return os.path.relpath(os.path.abspath(directory),
                           os.path.abspath(root)).replace(os.sep, "/")


def _where(root, path):
    """RETURN: str, the directory the relation's 'path' names."""
    return os.path.normpath(os.path.join(root, path))


def _map_file(relation):
    """RETURN: str, where the map of the tree stands (or would)."""
    return os.path.join(relation.top_directory, MAP_FILE_NAME)


def _map_container(text):
    """RETURN: amend.Container, the 'map { }' of a map's text; None where
    it holds none."""
    return amend.named_container(text, "map")


# -- a directory against the directory above and the map -------------------

def adapt_directory(root, directory):
    """
    RETURN: CAdapted, what was edited so that the files agree with where
            'directory' stands -- its own file written, its entry in the
            file above added or carried there from where the directory
            came from, the map entries of the features of its TEST
            directory made; 'reason' names what stopped it, where
            something did.

    'root' is the tree asked: a detected move is looked for inside it.
    """
    path     = _path_of(root, directory)
    relation = relation_of_tree(root)
    wanted   = [each for each in mismatch_list(relation)
                if each.path == path and each.kind in ADAPTED_KIND_TUPLE]
    if not wanted: return CAdapted()

    said_list, reason = [], ""
    kind_set = {each.kind for each in wanted}
    if NO_FILE in kind_set:
        _write(os.path.join(directory, FEATURE_FILE_NAME), "features {\n}\n")
        said_list.append("%s: '%s' written, empty" % (path, FEATURE_FILE_NAME))
    if kind_set & {UNLISTED, MOVED}:
        said, reason = _listed(root, relation, directory, path, wanted)
        said_list.extend(said)
    if NO_MAP in kind_set:
        said_list.extend(_map_written(relation, root))
    if UNMAPPED in kind_set:
        said_list.extend(_map_completed(
            relation, [each.id for each in wanted if each.kind == UNMAPPED]))
    return CAdapted(tuple(said_list), reason)


def _listed(root, relation, directory, path, wanted):
    """
    RETURN: [0] list of str, what was said of the entry written into the
                'childs' of the file above 'directory' -- carried from
                where the directory came from, where that was detected
            [1] str, why none was written, '' where one was
    """
    if parent_of(path) is None and relation.top_f:
        return [], ""
    above_directory = os.path.dirname(os.path.abspath(directory))
    if relation.statement_above(path) is None:
        return [], ("the directory above '%s' states no file: relate it "
                    "first" % path)
    name = name_of(path) if path != "." else relation.root_name
    key  = key_of_name(name)
    said_list = []
    moved = next((each for each in wanted if each.kind == MOVED), None)
    if moved is not None:
        from_file = os.path.join(_where(root, moved.from_path),
                                 FEATURE_FILE_NAME)
        from_text = _read(from_file)
        from_text, carried = child_text_removed(from_text, name)
        _write(from_file, from_text)
        said_list.append("%s: childs, '%s' taken out"
                         % (moved.from_path, carried or name))
        key = carried or key
    above_file = os.path.join(above_directory, FEATURE_FILE_NAME)
    above_text = _read(above_file)
    _write(above_file, child_text_added(above_text, key, name))
    said_list.append("%s: childs, '%s' entered%s"
                     % (parent_of(path) or "..", key,
                        ", carried with its key" if moved is not None
                        else ""))
    return said_list, ""


def _map_written(relation, root):
    """RETURN: list of str, what was said of the map file written: one
    entry per feature of the relation, its full id as the published id."""
    lines = ["map {"] + ["    %s = %s" % (_quoted(full_id), _quoted(full_id))
                         for full_id, _, _ in feature_id_list(relation)] \
            + ["}", ""]
    _write(_map_file(relation), "\n".join(lines))
    return ["%s written -- %i feature(s) published under their ids"
            % (MAP_FILE_NAME, len(feature_id_list(relation)))]


def _map_completed(relation, full_id_list):
    """RETURN: list of str, what was said of the map entries made for the
    features 'full_id_list': a published id bound to a full id that
    stands no more and has this feature as its counterpart REPOINTED, an
    entry published under the full id else."""
    pair_db = {new: published for published, new in map_pair_list(relation)}
    file    = _map_file(relation)
    said_list = []
    for full_id in full_id_list:
        text      = _read(file)
        container = _map_container(text)
        if container is None:
            return said_list + ["'%s' holds no 'map { }'" % MAP_FILE_NAME]
        if full_id in pair_db:
            published = pair_db[full_id]
            _write(file, map_text_bound(text, container, published,
                                        full_id))
            said_list.append("map: '%s' now means %s" % (published, full_id))
        else:
            _write(file, map_text_added(text, container, full_id, full_id))
            said_list.append("map: '%s' published" % full_id)
    return said_list


def child_dropped(root, directory, name):
    """
    RETURN: CAdapted, the 'childs' entries of the file of 'directory' that
            list the directory 'name' removed -- where that directory
            stands nowhere as a component; 'reason' says why not, where
            it stands and is listed rightly or was moved and is carried
            elsewhere, and nothing is said or reasoned where it is not
            listed at all.
    """
    path      = _path_of(root, directory)
    relation  = relation_of_tree(root)
    statement = relation.statement_of(path)
    if statement is None or name not in statement.directory_tuple():
        return CAdapted()
    if not any(each.kind == DANGLING and each.path == path
               and each.id == name for each in mismatch_list(relation)):
        return CAdapted(reason="'%s' stands below '%s', or was moved and "
                               "is carried elsewhere" % (name, path))
    file = os.path.join(directory, FEATURE_FILE_NAME)
    text = _read(file)
    text, key = child_text_removed(text, name)
    _write(file, text)
    return CAdapted(("%s: childs, '%s' taken out" % (path, key or name),))


def map_retired(root, published):
    """
    RETURN: CAdapted, the map entry 'published' bound to none -- RETIRED --
            where it is bound to a full id that names no feature;
            'reason' says why not: no map, no such entry, or it names a
            feature that stands
    """
    relation = relation_of_tree(root)
    if relation.feature_map is None:
        return CAdapted(reason="no '%s' stands" % MAP_FILE_NAME)
    if not relation.feature_map.standing_f(published):
        return CAdapted()
    target = relation.feature_map.target_of(published)
    if target is None:
        return CAdapted()
    if target in {each for each, _, _ in feature_id_list(relation)}:
        return CAdapted(reason="'%s' means %s, which stands" % (published,
                                                                 target))
    file = _map_file(relation)
    text = _read(file)
    _write(file, map_text_bound(text, _map_container(text), published, None))
    return CAdapted(("map: '%s' retired" % published,))


# -- a test application moved or removed --------------------------------------

def link_db(directory):
    """RETURN: dict, (test, choice) -> tuple of the feature names that
    test run of the TEST directory 'directory' links to; 'choice' None
    for a test without choices."""
    return {(app.source_file, choice): linked_name_tuple(parameters)
            for app in explore(directory).app_set
            for choice, parameters in app.choice_db.items()}


def linked_name_set(directory, test=None, without=None):
    """RETURN: set of str, the feature names the test applications of
    the TEST directory 'directory' link to -- of 'test' alone where one
    is named, of every application but 'without' where that is named."""
    result = set()
    for (app, _choice), name_tuple in link_db(directory).items():
        if test is not None and app != test:       continue
        if without is not None and app == without: continue
        result.update(name_tuple)
    return result


def unproven_by_removal(directory, test, choice=None):
    """RETURN: tuple of str, the features the feature file of
    'directory' defines that are left without a linked run where
    'test' -- one 'choice' of it where one is named, every choice else
    -- is removed: linked by what goes, by nothing that stays. Sorted;
    empty where no feature file stands or the test is not found."""
    going, staying = set(), set()
    for (app, app_choice), name_tuple in link_db(directory).items():
        if app == test and (choice is None or app_choice == choice):
            going.update(name_tuple)
        else:
            staying.update(name_tuple)
    return test_removed(directory, going, staying)


def _feature_scope(text):
    """RETURN: [0] amend.Container, the container of the file's 'features
    { }'; None where it holds none
               [1] amend.Entry, its 'childs' scope; None where it holds
                   none"""
    container = amend.named_container(text, "features")
    if container is None: return None, None
    entry = _entry(text, container, "childs")
    return container, entry if entry is not None and entry.object_f else None


def _feature_entry(text, name):
    """
    RETURN: amend.Entry, the feature 'name' in the 'childs' of the file's
            text
            None, it holds none
    """
    container, childs = _feature_scope(text)
    if childs is None: return None
    scope = amend.scope_container(text, childs, container)
    for inner in amend.entry_list(text, scope.i_open, scope.i_close):
        if inner.key == name: return inner
    return None


def _feature_removed(text, name):
    """RETURN: str, 'text' without the feature 'name'."""
    container, childs = _feature_scope(text)
    scope = amend.scope_container(text, childs, container)
    return amend.entry_remove(text, scope, _feature_entry(text, name))


def _feature_added(text, name, body):
    """RETURN: str, 'text' with the feature 'name' written into the
    'childs' of its 'features { }'."""
    text, scope = _childs_scope(text)
    return amend.entry_add(text, scope, "%s %s" % (_key(name), body))


def _map_follow(source_directory, target_directory, name, mode):
    """RETURN: list of str, what the map says now of a feature carried
    from the TEST directory 'source_directory' into 'target_directory'.

        'moved'   it left the source: the published ids bound to its old
                  full id FOLLOW it (the entries repointed)
        'merged'  it left the source and the target had it already: the
                  published ids bound to its old full id are RETIRED
        'copy'    it stayed in the source: the copy is published under
                  its own full id

    Nothing where no map stands (NO_MAP says so) or the ids are equal."""
    try:
        top = top_directory_of(source_directory)
    except Exception:
        return []
    map_file = os.path.join(top, MAP_FILE_NAME)
    if not os.path.isfile(map_file): return []
    old_id = full_id_of(source_directory, name)
    new_id = full_id_of(target_directory, name)
    if old_id == new_id: return []
    feature_map = read_feature_map(top)
    target_set  = {target for _, target, _ in feature_map.entry_tuple
                   if target}
    text        = _read(map_file)
    said_list   = []
    if mode in ("moved", "merged"):
        for published, target, _ in feature_map.entry_tuple:
            if target != old_id: continue
            bind = new_id if mode == "moved" and new_id not in target_set \
                   else None
            text = map_text_bound(text, _map_container(text), published,
                                  bind)
            said_list.append("map: '%s' now means %s" % (published, new_id)
                             if bind else "map: '%s' retired" % published)
            if bind: target_set.add(new_id)
    if mode != "merged" and new_id not in target_set:
        text = map_text_added(text, _map_container(text), new_id, new_id)
        said_list.append("map: '%s' published" % new_id)
    if said_list: _write(map_file, text)
    return said_list


def test_moved(source_directory, target_directory, name_set,
               staying_name_set):
    """
    RETURN: CAdapted, the features 'name_set' -- those a test that went
            from 'source_directory' to 'target_directory' links to --
            carried after it: each one the source's feature file
            defines and the target's does not is written into the
            target's, and taken out of the source's unless
            'staying_name_set' (what the tests that stay link to) still
            holds it. A feature that left the source takes its published
            id with it; one that stayed is published anew in the target.

            Nothing is done for a name the source does not define. A
            name the target defines already is not written again: the
            source's entry goes where it is written alike and no
            staying test links to it, and both stand where they differ.
            A target without a feature file receives one.
    """
    source = read_feature_file(source_directory)
    if source is None or not name_set: return CAdapted()
    carried_list = [feature for feature in source.feature_tuple
                    if feature.name in name_set]
    if not carried_list: return CAdapted()
    source_file = os.path.join(source_directory, FEATURE_FILE_NAME)
    target_file = os.path.join(target_directory, FEATURE_FILE_NAME)
    said_list   = []
    target      = read_feature_file(target_directory)
    if target is None:
        #  A LINK MUST RESOLVE WHERE THE TEST STANDS (ruled 2026-10-11,
        #  R-91): the target states no features yet, so the file is
        #  written -- empty, for the carried ones to enter.
        _write(target_file, "features {\n    childs {\n    }\n}\n")
        said_list.append("'%s' written in the target directory"
                         % FEATURE_FILE_NAME)
        target = read_feature_file(target_directory)
    for feature in carried_list:
        source_text = _read(source_file)
        entry       = _feature_entry(source_text, feature.name)
        if entry is None: continue
        body      = amend.value_text(source_text, entry)
        staying_f = feature.name in staying_name_set
        standing  = target.feature_of_name(feature.name)
        if standing is not None:
            #  THE TARGET DEFINES THAT NAME ALREADY. Written alike, the
            #  source's is a copy and goes with its last link; written
            #  otherwise, both are the author's and both stand.
            target_text  = _read(target_file)
            target_entry = _feature_entry(target_text, standing.name)
            alike_f = target_entry is not None \
                      and amend.value_text(target_text, target_entry) == body
            if staying_f: continue
            if alike_f:
                _write(source_file, _feature_removed(source_text,
                                                     feature.name))
                said_list.append("feature '%s' stands in the target "
                                 "alike: taken out of the source"
                                 % feature.name)
                said_list.extend(_map_follow(source_directory,
                                             target_directory,
                                             feature.name, "merged"))
            else:
                said_list.append("feature '%s' stands in both, written "
                                 "differently: both left" % feature.name)
            continue
        target_text = _read(target_file)
        _write(target_file, _feature_added(target_text, feature.name, body))
        target = read_feature_file(target_directory)
        said = "feature '%s' -> %s" % (feature.name,
                                       os.path.basename(
                                           os.path.normpath(
                                               target_directory)))
        if not staying_f:
            _write(source_file, _feature_removed(source_text, feature.name))
        else:
            said += ", kept in the source: still linked there"
        said_list.append(said)
        said_list.extend(_map_follow(source_directory, target_directory,
                                     feature.name,
                                     "copy" if staying_f else "moved"))
    return CAdapted(tuple(said_list))


def test_removed(directory, name_set, staying_name_set):
    """RETURN: tuple of str, the feature names of 'name_set' that the
    feature file of 'directory' defines and no test that stays links
    to: left without a linked run -- UNPROVEN -- by the removal. Sorted;
    empty where no feature file stands."""
    found = read_feature_file(directory)
    if found is None: return ()
    return tuple(sorted(name for name in name_set
                        if name not in staying_name_set
                        and found.feature_of_name(name) is not None))
