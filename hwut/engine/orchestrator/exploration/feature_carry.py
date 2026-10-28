"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURES A TEST APPLICATION TAKES ALONG -- what 'hwut.move'
         and 'hwut.remove' do to the features a test links to (spec 23
         VERSION 10 section 8, R-96 step 6):

    link_db(directory)                     (test, choice) -> linked names
    linked_name_set(directory, ...)        the names some tests link to
    unproven_by_removal(directory, test)   left without a linked run
    test_moved(root, source, target, name_set, staying_name_set)
                                           the definitions carried, the
                                           central file following

A MOVED TEST TAKES ITS FEATURES ALONG: a link must resolve where the test
stands (R-91). Each feature it links to that the source's TEST file defines
and the target's does not is written into the target's, and taken out of
the source's unless a test that stays still links to it. THE CENTRAL FILE
FOLLOWS, so that what a customer holds keeps its meaning:

    moved    the leaf of '<source id>:<name>' is repointed to '<target
             id>:<name>'; a target directory without an id gets one first
    merged   the target defined the name already, written alike, and the
             source's definition went: the source's leaf is retired where
             the target's is registered, repointed where it is not
    linked   the source keeps it (still linked there) and NOTHING IS
             COPIED: the moved test's link is rewritten to the leaf's
             internal id, '<source id>:<name>' -- one definition, one leaf
             (the book's D-8, R-5)

WHERE AN INTERNAL ID CHANGES ('moved', 'merged'), every link by that id in
the tree follows (R-4), each file named.

Where no readable central file stands, the definitions are carried --
copied where still linked, as no internal id can be written -- and nothing
else is done.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

#  A FEATURE FILE THAT DEFINES NOTHING YET -- the frame a first carried
#  definition is written into.
EMPTY_FEATURE_FILE_TEXT = "features {\n    childs {\n    }\n}\n"

from .                      import amend
from .explorer              import explore
from .feature_relation      import linked_name_tuple, read_feature_file
from .finder                import FEATURE_FILE_NAME, REGISTRY_FILE_NAME
from .feature_registry      import registry_of_text
from .feature_registry_edit import (EditRefused, edited, write_atomic,
                                    directory_add_list, leaf_repoint,
                                    leaf_take, leaf_block, retired_add,
                                    definition_take, new_directory_id,
                                    _definition_entry)


@dataclass(frozen=True)
class CCarried:
    """WHAT A CARRYING DID: 'said_tuple' one line per edit, telegraphic;
    'reason' why something could not be done, '' else."""
    said_tuple: tuple = ()
    reason:     str   = ""


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
    """RETURN: tuple of str, the features the feature file of 'directory'
    defines that are left without a linked run where 'test' -- one 'choice'
    of it where one is named, every choice else -- is removed: linked by
    what goes, by nothing that stays. Sorted; empty where no feature file
    stands or the test is not found."""
    going, staying = set(), set()
    for (app, app_choice), name_tuple in link_db(directory).items():
        if app == test and (choice is None or app_choice == choice):
            going.update(name_tuple)
        else:
            staying.update(name_tuple)
    found = read_feature_file(directory)
    if found is None: return ()
    return tuple(sorted(name for name in going
                        if name not in staying
                        and found.feature_of_name(name) is not None))


def _read(path):
    """RETURN: str, the file's text."""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _added(text, name, body):
    """RETURN: str, the feature file 'text' with '<name> { <body> }' in the
    'childs' of its 'features { }' -- a 'childs { }' made where none
    stands."""
    outer = amend.named_container(text, "features")
    childs = next((entry for entry in amend.entry_list(text, outer.i_open,
                                                       outer.i_close)
                   if entry.key == "childs" and entry.object_f), None)
    if childs is None:
        text   = amend.entry_add(text, outer, "childs {\n    }")
        outer  = amend.named_container(text, "features")
        childs = next(entry for entry in amend.entry_list(
            text, outer.i_open, outer.i_close) if entry.key == "childs")
    return amend.entry_add(text, amend.scope_container(text, childs, outer),
                           "%s {%s}" % (name, body))


def _central_followed(root, source_path, target_path, name, mode):
    """RETURN: list of str, what the central file at 'root' says now of the
    feature 'name' carried from the directory 'source_path' to
    'target_path' (paths below 'root', '/'), as 'mode' ('moved', 'merged')
    asks; [] where no readable central file stands, or the source's leaf
    stands in no line."""
    path = os.path.join(root, REGISTRY_FILE_NAME)
    if not os.path.isfile(path): return []
    text     = _read(path)
    registry = registry_of_text(text)
    if registry.fault_tuple:
        return ["NOTE  '%s' states a fault: not followed" % REGISTRY_FILE_NAME]
    id_of = {each.path: each.id for each in registry.directory_tuple}
    source_id, target_id = id_of.get(source_path), id_of.get(target_path)
    if source_id is None: return []
    old_internal = "%s:%s" % (source_id, name)
    external = next((leaf.external for leaf in _leaves(registry)
                     if leaf.internal == old_internal), None)
    if external is None: return []
    said_list, new_text = [], text
    try:
        if mode == "merged" and target_id is not None \
           and any(leaf.internal == "%s:%s" % (target_id, name)
                   for leaf in _leaves(registry)):
            new_text, _ = leaf_take(new_text, external)
            new_text = retired_add(new_text, leaf_block(external,
                                                        old_internal, ""))
            said_list.append("'%s' retired: the target's '%s' is the same"
                             % (external, name))
        else:
            if target_id is None:
                target_id = new_directory_id({each.id for each
                                              in registry.directory_tuple})
                new_text = directory_add_list(new_text,
                                              [(target_id, target_path)])
                said_list.append("%s registered for %s" % (target_id,
                                                           target_path))
            new_text = leaf_repoint(new_text, external,
                                    "%s:%s" % (target_id, name))
            said_list.append("'%s' now binds %s:%s" % (external, target_id,
                                                       name))
        write_atomic(path, edited(text, new_text))
    except EditRefused as error:
        return ["NOTE  '%s' not followed: %s" % (REGISTRY_FILE_NAME, error)]
    return said_list


def _internal_of(root, path, name):
    """RETURN: str, '<id of the directory path>:<name>' as the central file
    at 'root' registers it; None where no readable file stands or it gives
    the path no id."""
    central = os.path.join(root, REGISTRY_FILE_NAME)
    if not os.path.isfile(central): return None
    registry = registry_of_text(_read(central))
    if registry.fault_tuple: return None
    found = next((each.id for each in registry.directory_tuple
                  if each.path == path), None)
    return None if found is None else "%s:%s" % (found, name)


def _links_followed(root, old, new):
    """RETURN: list of str, the links by internal id 'old' in the tree
    rewritten to 'new', one line per file; [] where either is None."""
    from .feature_registry_act import internal_links_planned, links_written
    if old is None or new is None or old == new: return []
    return links_written(root, internal_links_planned(
        root, lambda link: new if link == old else None))


def _leaves(registry):
    """RETURN: list of CLeaf, every leaf of the tree, unplaced included."""
    from .feature_registry import leaf_list
    return [leaf for _, leaf in leaf_list(registry)]


def test_moved(root, source_directory, target_directory, name_set,
               staying_name_set, test_path=None):
    """
    RETURN: CCarried, the features 'name_set' -- those a test that went
            from the TEST directory 'source_directory' to
            'target_directory' links to -- carried after it, and the
            central file at 'root' following (see the module's text).

            Nothing is done for a name the source does not define. A name
            the target defines already is not written again: the source's
            entry goes where it is written alike and no staying test links
            to it, and both stand where they differ. A target without a
            feature file receives one. A name a staying test still links
            is not copied: the moved test's link, in 'test_path' (where it
            stands now), becomes the leaf's internal id (the book's D-8).
    """
    source = read_feature_file(source_directory)
    if source is None or not name_set: return CCarried()
    carried_list = [feature.name for feature in source.feature_tuple
                    if feature.name in name_set]
    if not carried_list: return CCarried()

    def below(directory):
        """RETURN: str, the directory owning the TEST directory, below
        'root', '/'. ABSOLUTE FIRST: the dirname of '.' -- a move called
        inside the source TEST directory -- is '' (D-1 of the book)."""
        return os.path.relpath(os.path.dirname(os.path.abspath(directory)),
                               os.path.abspath(root)).replace(os.sep, "/")

    source_file = os.path.join(source_directory, FEATURE_FILE_NAME)
    target_file = os.path.join(target_directory, FEATURE_FILE_NAME)
    source_path, target_path = below(source_directory), \
                               below(target_directory)
    said_list = []
    #  THE TARGET'S FILE IS WRITTEN WHEN A DEFINITION GOES INTO IT, not
    #  before: a test whose features all stay in the source (still linked
    #  there) leaves no empty file behind. MEASURED before (book D-74): an
    #  empty 'hwut-features.conf' in the target, and 'hwut.features.register'
    #  then gave that directory an id of its own for no feature.
    def target_text_now():
        """RETURN: str, the target's feature file as it stands, or the
        empty one it would be -- nothing written."""
        if os.path.isfile(target_file): return _read(target_file)
        return EMPTY_FEATURE_FILE_TEXT
    for name in carried_list:
        source_text = _read(source_file)
        found = _definition_entry(source_text, name)
        if found is None: continue
        body      = source_text[found[0].i_value + 1:found[0].i_end - 1]
        staying_f = name in staying_name_set
        internal  = _internal_of(root, source_path, name)
        if staying_f and internal is not None and test_path is not None \
           and os.path.isfile(test_path):
            #  ONE DEFINITION, ONE LEAF (R-5): the link follows by id.
            from .feature_registry_act import _links_mapped
            before = _read(test_path)
            after  = _links_mapped(before, lambda link: internal
                                   if link == name else None)
            if after != before:
                mode = os.stat(test_path).st_mode
                write_atomic(test_path, after)
                os.chmod(test_path, mode)
            said_list.append("feature '%s' stays in the source, still linked "
                             "there: the moved test links it as '%s'"
                             % (name, internal))
            continue
        target_text = target_text_now()
        standing = _definition_entry(target_text, name)
        if standing is not None:
            #  THE TARGET DEFINES THAT NAME ALREADY. Written alike, the
            #  source's is a copy and goes with its last link; written
            #  otherwise, both are the author's and both stand.
            alike_f = target_text[standing[0].i_value + 1:
                                  standing[0].i_end - 1].strip() \
                      == body.strip()
            if staying_f: continue
            if alike_f:
                write_atomic(source_file,
                             definition_take(source_text, name)[0])
                said_list.append("feature '%s' stands in the target alike: "
                                 "taken out of the source" % name)
                said_list += _central_followed(root, source_path,
                                               target_path, name, "merged")
                said_list += _links_followed(
                    root, internal, _internal_of(root, target_path, name))
            else:
                said_list.append("feature '%s' stands in both, written "
                                 "differently: both left" % name)
            continue
        if not os.path.isfile(target_file):
            said_list.append("'%s' written in the target directory"
                             % FEATURE_FILE_NAME)
        write_atomic(target_file, _added(target_text, name, body))
        said = "feature '%s' -> %s" % (name, target_path)
        if staying_f:
            said_list.append(said + ", kept in the source: still linked "
                             "there; the copy is not registered => "
                             "hwut.features.register")
            continue
        write_atomic(source_file, definition_take(source_text, name)[0])
        said_list.append(said)
        said_list += _central_followed(root, source_path, target_path, name,
                                       "moved")
        said_list += _links_followed(root, internal,
                                     _internal_of(root, target_path, name))
    return CCarried(tuple(said_list))
