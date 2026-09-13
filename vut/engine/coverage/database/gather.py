"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE GATHER -- coverage of MANY directories folded into one
         index, and the BUNDLE that carries it away (RATIONALE D-25).

DESCRIPTION
       IDS ARE DIRECTORY-LOCAL (D-14), so a fold across directories has
       exactly one honest key: the directory, relative to the gather
       root the caller chose, beside the local run id -- 'Gathered'.

       A GATHERED GROUP is what a stretch of source is reached by, seen
       from the gather: a SET OF (directory, local group) PAIRS, one
       pair per directory involved. It answers "which test applications
       and choices, across the whole tree, executed this range" as ONE
       number.

           D1: book.csv (register)  group_ids.dat  records
           D2: book.csv (register)  group_ids.dat  records
                       |
                 hwut.cov gather (one root)
                       v
           g' <-> { (D1, g3), (D2, g7) }     the gather's own table
           segment -> g'                      the gather's own index

       EPHEMERAL TO HWUT. The gathered table is made in this process
       and written into NO directory's 'GOOD/': it is a function of the
       root the caller chose, exactly as transient as that choice.

       DECODING IS A CHAIN, each link a table: gathered group -> pairs
       -> that directory's group table -> run ids -> that directory's
       register -> names. So a DELIVERY is a BUNDLE: the gather's own
       index and table, plus a SNAPSHOT of each directory's register
       and group table, keyed by directory relative to the root, valid
       only as one bundle.

       A SNAPSHOT NAMES ITS GENERATION. A copy without a version is a
       claim that it still matches; both tables count their mutations
       ('G:' / 'R:'), the bundle records the number it copied, and
       'stale_tuple' says which directories have moved since. The
       bundle is not thereby wrong -- ids are ISSUED ONCE (bookkeeper
       B-2), so a snapshot decoded against a NEWER register still
       resolves, and a removed test's id decodes to 'no longer
       registered', which is true rather than misattributed. The
       generation says whether the tree has moved, not whether the
       answer is safe.

       THE GATHER NEVER WRITES BACK. Nothing it makes is identity.
______________________________________________________________________________
"""
import io
import json
import os

from .index     import index_of, record_iterable
from ...bookkeeper.api  import Bookkeeper, TestIdDb, TestIdFault
from ...bookkeeper.api import (GroupDb, GroupFault,
                                      parse_group_table)

BUNDLE_FILE    = "coverage-bundle.json"
FORMAT_VERSION = 1


class GatherFault(ValueError):
    """A bundle that cannot be read, or a snapshot that names a
    directory the bundle does not carry."""
    pass


def gathered_index(root, suffix=None):
    """
    RETURN: [0] TestIndex, over every record under 'root', its run keys
                'Gathered' -- the directory relative to 'root' beside
                the local run id.
            [1] tuple of str, the directories a record was found in,
                relative to 'root', sorted; 'None' spelt '.' for the
                root itself.

    A record that does not parse, or that names no run, is skipped and
    said on stderr ('record_iterable'): one broken record must not cost
    a whole gather, and it must not vanish either.
    """
    pair_list = list(record_iterable(root) if suffix is None
                     else record_iterable(root, suffix))
    directory_set = {"." if key.directory is None else key.directory
                     for key, _ in pair_list}
    return index_of(pair_list), tuple(sorted(directory_set))


def gathered_group_db(index, snapshot_db):
    """
    RETURN: dict, gathered group id -> tuple of (directory, local group
            id) pairs, sorted -- the GROUP OF GROUPS (D-25).

    The gathered index interns SETS OF GATHERED KEYS; this turns each
    into the per-directory groups that decode it, using each
    directory's own group table from 'snapshot_db'. A directory whose
    group table the snapshot does not carry contributes no pair, and
    the caller learns that from 'stale_tuple'.
    """
    result = {}
    for group_id, key_tuple in index.group_table.item_iterable():
        by_directory = {}
        for key in key_tuple:
            directory = "." if key.directory is None else key.directory
            by_directory.setdefault(directory, set()).add(key.run_id)
        pair_list = []
        for directory in sorted(by_directory):
            table = snapshot_db.get(directory, {}).get("groups")
            if table is None: continue
            pair_list.append((directory,
                              table.group_of(by_directory[directory])))
        result[group_id] = tuple(pair_list)
    return result


def snapshot_db_of(root, directory_tuple):
    """
    RETURN: dict, directory -> {'register': TestIdDb, 'groups':
            GroupTable, 'register_generation': int,
            'groups_generation': int} -- what each directory's tables
            said AT THIS MOMENT.

    THE GROUP TABLE IS AN IN-MEMORY COPY, not the directory's 'GroupDb'.
    A gather interns sets the directory never folded, and interning
    into its own file would be the gather WRITING BACK -- which nothing
    it makes deserves (D-25). The copy carries the generation it was
    taken at; whatever the gather adds lives in the bundle.

    A directory whose register cannot be read is left out: a gather
    reports what it could gather and names what it could not, rather
    than failing whole.
    """
    result = {}
    for directory in directory_tuple:
        path = root if directory == "." else os.path.join(root, directory)
        #  THE REGISTER IS READ THROUGH THE BOOKKEEPER (B-9): text and
        #  generation, nothing written.
        try:
            keeper   = Bookkeeper(path)
            register_text       = keeper.register_text()
            register_generation = keeper.register_generation()
            stored   = GroupDb(path)
            groups   = parse_group_table(stored.format())
        except (TestIdFault, GroupFault):
            continue
        result[directory] = {
            "register":            register_text,
            "groups":              groups,
            "register_generation": register_generation,
            "groups_generation":   stored.generation}
    return result


def bundle_of(root, index, directory_tuple, snapshot_db):
    """
    RETURN: dict, the DELIVERY: the gather's own group-of-groups table
            and its index's segments, plus one snapshot per directory
            -- the register and group table AS TEXT, with the
            generation each was copied at.

    Text, not binary: a bundle is read by whoever renders a report, and
    both tables are small and are their own text format already.
    """
    return {
        "format":      FORMAT_VERSION,
        "root":        os.path.basename(os.path.abspath(root)),
        "directories": list(directory_tuple),
        "group_of_groups": {
            str(group_id): [list(pair) for pair in pair_tuple]
            for group_id, pair_tuple
            in gathered_group_db(index, snapshot_db).items()},
        "index": {path: [[begin, end, group_id]
                         for (begin, end), group_id
                         in index.group_segment_iterable(path)]
                  for path in index.path_tuple},
        "snapshot": {
            directory: {
                "register":            entry["register"],
                "register_generation": entry["register_generation"],
                "groups":              entry["groups"].format(),
                "groups_generation":   entry["groups_generation"]}
            for directory, entry in sorted(snapshot_db.items())}}


def write_bundle(bundle, path):
    """RETURN: str, where the bundle was written."""
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, indent=1, sort_keys=True)
    return path


def read_bundle(path):
    """
    RETURN: dict, the bundle at 'path'.

    Raises GatherFault where it is no bundle of a version this build
    reads: a delivery half understood is a report that lies.
    """
    try:
        with io.open(path, encoding="utf-8") as handle:
            bundle = json.load(handle)
    except (OSError, ValueError) as fault:
        raise GatherFault("'%s' is no bundle: %s" % (path, fault)) from None
    version = bundle.get("format")
    if version != FORMAT_VERSION:
        raise GatherFault("bundle version %s is not %i -- this build "
                          "does not pretend to read it"
                          % (version, FORMAT_VERSION))
    for key in ("directories", "group_of_groups", "index", "snapshot"):
        if key not in bundle:
            raise GatherFault("the bundle names no '%s'" % key)
    return bundle


def stale_tuple(bundle, root):
    """
    YIELD: [0] str   a directory of the bundle whose tables have MOVED
                     since the snapshot, relative to the gather root
           [1] str   what moved: 'register', 'groups', or 'both'
           [2] str   'moved', 'gone' where the directory no longer
                     stands, 'unreadable' where its tables refuse

    The bundle is not thereby wrong: ids are issued once, so a snapshot
    decoded against a newer register still resolves (bookkeeper B-2).
    This says whether the TREE has moved, so a reader knows whether to
    gather again.
    """
    for directory in sorted(bundle["snapshot"]):
        entry = bundle["snapshot"][directory]
        path  = root if directory == "." else os.path.join(root, directory)
        #  A VANISHED DIRECTORY reads as an EMPTY register -- a missing
        #  file is a fresh directory, by the register's own law. So the
        #  question is asked of the FILE SYSTEM, not of an exception.
        if not os.path.isdir(path):
            yield directory, "both", "gone"
            continue
        try:
            register_generation = Bookkeeper(path).register_generation()
            groups   = GroupDb(path)
        except (TestIdFault, GroupFault):
            yield directory, "both", "unreadable"
            continue
        moved = []
        if register_generation != entry["register_generation"]:
            moved.append("register")
        if groups.generation != entry["groups_generation"]:
            moved.append("groups")
        if moved:
            yield (directory, "both" if len(moved) == 2 else moved[0],
                   "moved")


def name_iterable(bundle, group_id):
    """
    YIELD: [0] str  the directory a run stands in, relative to the
                    gather root
           [1] str  the test application's name, as its register spells
                    it -- or '<no longer registered>' where the id
                    decodes to nothing
           [2] str  the choice's name, or None

    THE WHOLE CHAIN, walked: gathered group -> (directory, local group)
    pairs -> that directory's group table -> run ids -> that
    directory's register -> names. What a gathered group MEANS, in the
    only form a reader can use.
    """
    pair_list = bundle["group_of_groups"].get(str(group_id))
    if pair_list is None:
        raise GatherFault("the bundle carries no gathered group %s"
                          % group_id)
    for directory, local_group in pair_list:
        entry = bundle["snapshot"].get(directory)
        if entry is None:
            raise GatherFault("the bundle names directory '%s' and "
                              "carries no snapshot of it" % directory)
        table    = parse_group_table(entry["groups"])
        register = _register_of_text(entry["register"])
        for run_id in sorted(table.key_set_of(local_group)):
            name = register.name_of(run_id)
            if name is None:
                yield directory, "<no longer registered>", None
            else:
                yield directory, name[0], name[1]


def _register_of_text(text):
    """
    RETURN: TestIdDb holding what the text says, bound to no directory
            -- a SNAPSHOT, which is read and never written.
    """
    register = TestIdDb(os.devnull + "-snapshot")
    register._parse(text)
    return register
