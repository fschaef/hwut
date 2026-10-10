"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: ADAPTING THE FEATURE STATEMENTS TO WHERE THINGS STAND -- the
         one implementation behind every face that moves, renames,
         removes or sanitizes: 'hwut.sanitize relate / unrelate',
         'hwut.move', 'hwut.rename', 'hwut.remove'.

    adapt_directory(root, directory)        a directory's statement file
                                            made to agree with the
                                            directory above it
    child_dropped(root, directory, id)      a 'childs' entry nothing
                                            below carries, removed
    test_moved(source, target, test, name)  the features a test proves,
                                            carried after it into the
                                            feature file of its new TEST
                                            directory
    unproven_by_removal(directory, test, choice)
                                            the features a removed test
                                            leaves without a linked run

WHAT 'adapt_directory' DOES, in this order, each step only where the
statements disagree with the directories:

    1  no 'id'                    id = "<the directory's name>" -- or
                                  the ONE id the 'childs' above lists
                                  that nothing carries, where this is
                                  its only child without an id
    2  'parent' is not the id     parent rewritten to that id; the
       of the directory above     sentence it carried stays
    3  the directory above does   an entry '<id> = "<sentence>"' added
       not list the id            to its 'childs' -- and where ANOTHER
                                  component still lists the id while
                                  nothing below it carries it (A DETECTED
                                  MOVE), that entry is CARRIED: removed
                                  there, its sentence written here

TEXT IS MOVED, NEVER COMPOSED. A sentence travels as its author wrote
it; where none is at hand the entry is written with an empty one, which
the author fills. Every edit is text surgery through 'amend.py': what
is not adapted stays byte for byte.

A FEATURE'S NUMBER IS ITS FILE'S. Carried into another feature file it
receives that file's next number ('issued + 1', the mark raised); the
number it leaves behind is never issued again.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from .                 import amend
from .explorer         import explore
from .feature_relation import (ADAPTED_KIND_TUPLE, GONE, MOVED,
                               COMPOSITION_FILE_NAME, FEATURE_FILE_NAME,
                               CComposition, linked_name_tuple,
                               mismatch_list, parent_of, proposed_id_of,
                               read_feature_file,
                               relation_of_tree)


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

def _outer(text, statement):
    """RETURN: amend.Container, the outer braces of a statement file's
    text: 'component { }' or 'features { }'; None where none stands."""
    return amend.named_container(
        text, "component" if isinstance(statement, CComposition)
              else "features")


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
    return value if amend._KEY_RE.fullmatch(value) else _quoted(value)


def id_text_set(text, container, value):
    """RETURN: str, 'text' with 'id = "<value>"' as the container's
    first entry."""
    return amend.entry_add(text, container, "id = %s" % _quoted(value),
                           first_f=True)


def parent_text_set(text, container, parent_id):
    """RETURN: str, 'text' with 'parent' naming 'parent_id': the
    sentence a standing 'parent { <id> = "..." }' carries is kept, a
    standing 'parent = "<id>"' is rewritten in place, and where none
    stands 'parent = "<parent_id>"' is added."""
    entry = _entry(text, container, "parent")
    if entry is None:
        return amend.entry_add(text, container,
                               "parent = %s" % _quoted(parent_id))
    if entry.object_f:
        inner_list = amend.entry_list(text, entry.i_value, entry.i_end - 1)
        if len(inner_list) == 1:
            inner = inner_list[0]
            return text[:inner.i_key] + _key(parent_id) \
                   + text[inner.i_key + _key_length(text, inner):]
    return text[:entry.i_value] + _quoted(parent_id) + text[entry.i_end:]


def _key_length(text, entry):
    """RETURN: int, how many characters the entry's key takes as
    written, its quotes included."""
    if text[entry.i_key] == '"':
        return amend._string_end(text, entry.i_key) + 1 - entry.i_key
    return len(entry.key)


def child_text_added(text, container, child_id, sentence_text):
    """RETURN: str, 'text' with the child 'child_id' listed in 'childs':
    '<id> = <sentence_text>' inside a standing scope ('sentence_text'
    as written, quotes included; '""' where None), the quoted id
    appended to a standing list, and a new 'childs { }' where none
    stands."""
    entry = _entry(text, container, "childs")
    line  = "%s = %s" % (_key(child_id), sentence_text or '""')
    if entry is None:
        return amend.entry_add(text, container, "childs { %s }" % line)
    if entry.object_f:
        return amend.entry_add(
            text, amend.scope_container(text, entry, container), line)
    close_i = entry.i_end - 1
    have_f  = bool(amend.string_list_of(text[entry.i_value:entry.i_end]))
    return text[:close_i] + (", " if have_f else "") + _quoted(child_id) \
           + text[close_i:]


def child_text_removed(text, container, child_id):
    """
    RETURN: [0] str, 'text' without the child 'child_id' in 'childs' --
                its line with it where nothing else stood there
            [1] str, the sentence the entry carried, as written, quotes
                included; None where it carried none or was not listed
    """
    entry = _entry(text, container, "childs")
    if entry is None: return text, None
    if entry.object_f:
        scope = amend.scope_container(text, entry, container)
        for inner in amend.entry_list(text, scope.i_open, scope.i_close):
            if inner.key != child_id: continue
            return amend.entry_remove(text, scope, inner), \
                   amend.value_text(text, inner)
        return text, None
    item_list = amend.string_list_of(text[entry.i_value:entry.i_end])
    if child_id not in item_list: return text, None
    item_list.remove(child_id)
    return text[:entry.i_value] \
           + "[%s]" % ", ".join('"%s"' % item for item in item_list) \
           + text[entry.i_end:], None


# -- files ------------------------------------------------------------------

def statement_path(directory, relation, path):
    """RETURN: str, where the statement file of the directory at 'path'
    stands: the feature file's for a TEST directory, the composition
    file's else."""
    name = FEATURE_FILE_NAME if path in relation.test_directory_db \
           else COMPOSITION_FILE_NAME
    return os.path.join(directory, name)


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


# -- a directory against the directory above --------------------------------

def adapt_directory(root, directory):
    """
    RETURN: CAdapted, what was edited so that the statement file of
            'directory' agrees with the directory above it -- an id
            given, 'parent' set, the entry in the 'childs' above added
            or carried there from where the directory came from;
            'reason' names what stopped it, where something did.

    'root' is the tree asked: a detected move is looked for inside it.
    """
    path     = _path_of(root, directory)
    relation = relation_of_tree(root)
    wanted   = [each for each in mismatch_list(relation)
                if each.path == path and each.kind in ADAPTED_KIND_TUPLE]
    statement = relation.statement_of(path)
    if statement is None:
        return CAdapted(reason="no statement file stands in '%s'" % path)
    if not wanted:
        return CAdapted()

    said_list = []
    own_path  = statement_path(directory, relation, path)
    own_text  = _read(own_path)
    container = _outer(own_text, statement)
    if container is None:
        return CAdapted(reason="'%s' holds no outer node to adapt"
                               % os.path.basename(own_path))
    own_id = statement.id
    if own_id is None:
        own_id   = proposed_id_of(relation, path)
        own_text = id_text_set(own_text, container, own_id)
        _write(own_path, own_text)
        said_list.append("%s: id = \"%s\"" % (path, own_id))

    if parent_of(path) is None and relation.top_f:
        return CAdapted(tuple(said_list))
    above = relation.statement_above(path)
    if above is None or above.id is None:
        return CAdapted(tuple(said_list),
                        "the directory above '%s' gives itself no id" % path)

    if statement.parent_id != above.id:
        own_text = parent_text_set(own_text, _outer(own_text, statement),
                                   above.id)
        _write(own_path, own_text)
        said_list.append("%s: parent = \"%s\"" % (path, above.id))

    if own_id not in above.child_id_tuple():
        sentence = None
        moved    = next((each for each in wanted if each.kind == MOVED), None)
        if moved is not None:
            from_file = os.path.join(_where(root, moved.from_path),
                                     COMPOSITION_FILE_NAME)
            from_text = _read(from_file)
            from_text, sentence = child_text_removed(
                from_text, _outer(from_text, CComposition()), own_id)
            _write(from_file, from_text)
            said_list.append("%s: childs, '%s' taken out"
                             % (moved.from_path, own_id))
        above_directory = os.path.dirname(os.path.abspath(directory))
        above_file      = os.path.join(above_directory, COMPOSITION_FILE_NAME)
        above_text      = _read(above_file)
        _write(above_file, child_text_added(
            above_text, _outer(above_text, CComposition()), own_id,
            sentence))
        said_list.append("%s: childs, '%s' entered%s"
                         % (parent_of(path) or "..", own_id,
                            "" if sentence else ", its sentence empty"))
    return CAdapted(tuple(said_list))


def child_dropped(root, directory, child_id):
    """
    RETURN: CAdapted, the 'childs' entry 'child_id' removed from the
            composition file of 'directory' -- where 'childs' lists that
            id and nothing below carries it; 'reason' says why not,
            where it stands and is carried, and nothing is said or
            reasoned where it is not listed at all.
    """
    path     = _path_of(root, directory)
    relation = relation_of_tree(root)
    statement = relation.statement_of(path)
    if not isinstance(statement, CComposition) \
       or child_id not in statement.child_id_tuple():
        return CAdapted()
    if not any(each.kind == GONE and each.path == path
               and each.id == child_id for each in mismatch_list(relation)):
        return CAdapted(reason="'%s' is carried below '%s', or was moved "
                               "and is carried elsewhere" % (child_id, path))
    file = os.path.join(directory, COMPOSITION_FILE_NAME)
    text = _read(file)
    text, _ = child_text_removed(text, _outer(text, statement), child_id)
    _write(file, text)
    return CAdapted(("%s: childs, '%s' taken out" % (path, child_id),))


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


def test_moved(source_directory, target_directory, name_set,
               staying_name_set):
    """
    RETURN: CAdapted, the features 'name_set' -- those a test that went
            from 'source_directory' to 'target_directory' links to --
            carried after it: each one the source's feature file
            defines and the target's does not is written into the
            target's under the target's next number, and taken out of
            the source's unless 'staying_name_set' (what the tests that
            stay link to) still holds it.

            Nothing is done for a name the source does not define. A
            name the target defines already is not written again: the
            source's entry goes where it is written alike and no
            staying test links to it, and both stand where they differ.
            'reason' says so where the target carries no feature file
            to write into.
    """
    source = read_feature_file(source_directory)
    if source is None or not name_set: return CAdapted()
    carried_list = [feature for feature in source.feature_tuple
                    if feature.name in name_set]
    if not carried_list: return CAdapted()
    target = read_feature_file(target_directory)
    if target is None:
        return CAdapted(reason="no '%s' stands in the target directory: "
                               "%s stay(s) defined in the source"
                               % (FEATURE_FILE_NAME, ", ".join(
                                   "'%s'" % f.name for f in carried_list)))
    source_file = os.path.join(source_directory, FEATURE_FILE_NAME)
    target_file = os.path.join(target_directory, FEATURE_FILE_NAME)
    scope       = target.scope()
    said_list   = []
    for feature in carried_list:
        source_text = _read(source_file)
        container   = amend.named_container(source_text, "features")
        entry       = _entry(source_text, container, feature.key)
        if entry is None: continue
        body     = amend.value_text(source_text, entry)
        staying_f = feature.name in staying_name_set
        standing = target.feature_of_name(feature.name)
        if standing is not None:
            #  THE TARGET DEFINES THAT NAME ALREADY. Written alike, the
            #  source's is a copy and goes with its last link; written
            #  otherwise, both are the author's and both stand.
            target_text  = _read(target_file)
            target_entry = _entry(target_text, amend.named_container(
                                      target_text, "features"), standing.key)
            alike_f = target_entry is not None \
                      and amend.value_text(target_text, target_entry) == body
            if staying_f: continue
            if alike_f:
                _write(source_file, amend.entry_remove(source_text,
                                                       container, entry))
                said_list.append("feature '%s' stands in the target "
                                 "alike: taken out of the source"
                                 % feature.name)
            else:
                said_list.append("feature '%s' stands in both, written "
                                 "differently: both left" % feature.name)
            continue
        number = scope.allocate()
        if number is None:
            return CAdapted(tuple(said_list), scope.refusal_text())
        target_text = _read(target_file)
        target_text = amend.entry_add(
            target_text, amend.named_container(target_text, "features"),
            "%i %s" % (number, body))
        target_text = _issued_text_set(target_text, scope.mark_text())
        _write(target_file, target_text)
        said = "feature '%s' -> #%i" % (feature.name, number)
        if not staying_f:
            _write(source_file, amend.entry_remove(source_text, container,
                                                   entry))
        else:
            said += ", kept in the source: still linked there"
        said_list.append(said)
    return CAdapted(tuple(said_list))


def _issued_text_set(text, mark_text):
    """RETURN: str, 'text' with 'issued = <mark_text>' in its
    'features { }': rewritten where it stands, added as the first entry
    where it does not."""
    container = amend.named_container(text, "features")
    entry     = _entry(text, container, "issued")
    if entry is None:
        return amend.entry_add(text, container, "issued = %s" % mark_text,
                               first_f=True)
    return text[:entry.i_value] + mark_text + text[entry.i_end:]


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
