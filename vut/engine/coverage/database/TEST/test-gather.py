#! /usr/bin/env python3
#
# @hwut {
#     title      = "The gather: many directories, one index, one bundle"
#     choices    = ["bundle", "fold", "groups", "refused", "stale"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE GATHER -- many directories, one index, one bundle (RATIONALE D-25).

    THE FIXTURE, two directories over ONE source file:

        parser/TEST/  test-parse--basic   reaches core.py 1..5
                      test-parse--deep    reaches core.py 4..7
        other/TEST/   test-other          reaches core.py 8..9

    Every directory numbers its own runs from 0, so ids ALONE cannot
    say who reached a line across the tree; the gather qualifies each
    with the directory it found the record in.

CHOICES: fold, groups, bundle, stale, refused;

fold       the index over both directories: one file, segments cut
           where the set of runs changes, keys carrying their
           directory.
groups     the GROUP OF GROUPS: a set of (directory, local group)
           pairs as one number, and the CHAIN that decodes it back to
           test applications and choices -- which is what the number
           is for.
bundle     the delivery: the gather's own table and index, plus one
           snapshot per directory carrying the register and group
           table AS TEXT with the generation each was taken at. It
           writes into NO directory's 'GOOD/'.
stale      the bundle read back: silent while the tree stands, naming
           the directory when it moves. The ids still decode -- an id
           is issued once -- so this says the TREE moved, not that the
           answer is wrong.
refused    a bundle that is no bundle, a version this build does not
           read, a gathered group the bundle does not carry.
______________________________________________________________________________
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.coverage.database.gather  import (gathered_index,       # noqa E402
                                           snapshot_db_of, bundle_of,
                                           gathered_group_db,
                                           write_bundle, read_bundle,
                                           stale_tuple, name_iterable,
                                           GatherFault, FORMAT_VERSION)
from   vut.engine.coverage.database.record  import (CoverageRecord,       # noqa E402
                                           FileCoverage, ranges_of,
                                           seated)
from   vut.engine.coverage.database.binary  import pack_record            # noqa E402
from   vut.engine.bookkeeper.api import TestIdDb          # noqa E402

FIXTURE = (
    ("parser/TEST", (("test-parse", "basic", (1, 2, 3, 4, 5)),
                     ("test-parse", "deep",  (4, 5, 6, 7)))),
    ("other/TEST",  (("test-other", None,    (8, 9)),)),
)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def fixture():
    """
    RETURN: str, a tree root holding the two directories described in
            the header, each with its own register and its records --
            for the caller to remove.
    """
    root = tempfile.mkdtemp(prefix="vut_gather_")
    for directory, app_tuple in FIXTURE:
        full = os.path.join(root, directory)
        os.makedirs(full)
        register = TestIdDb(full)
        for app, choice, line_tuple in app_tuple:
            run_id = register.run_id_of(app, choice, allocate_f=True)
            record = seated(CoverageRecord(
                "python", "coverage", "coverage.py-json",
                file_db={"../core.py": FileCoverage(
                    "../core.py", ranges_of(range(1, 11)),
                    ranges_of(line_tuple))}), run_id)
            stem = app if choice is None else "%s--%s" % (app, choice)
            with io.open(os.path.join(full, stem + ".cover"), "wb") as fh:
                fh.write(pack_record(record))
    return root


def gathered(root):
    """RETURN: (index, directory_tuple, snapshot_db, bundle)."""
    index, directory_tuple = gathered_index(root)
    snapshot_db = snapshot_db_of(root, directory_tuple)
    return (index, directory_tuple, snapshot_db,
            bundle_of(root, index, directory_tuple, snapshot_db))


# ------------------------------------------------------------- choices

def test_fold():
    """One index over two directories."""
    root = fixture()
    index, directory_tuple, _, _ = gathered(root)

    banner("what was found")
    print("INSPECT: directories %s" % ", ".join(directory_tuple))
    print("         files       %s" % ", ".join(index.path_tuple))

    banner("parser/core.py, segment by segment")
    for (begin, end), group_id in \
            index.group_segment_iterable("parser/core.py"):
        key_tuple = sorted(index.group_table.key_set_of(group_id), key=str)
        print("         [%2i,%2i)  group %s  %s"
              % (begin, end, group_id,
                 ", ".join(str(k) for k in key_tuple) or "<nobody>"))

    banner("who reached one line")
    for line in (2, 4, 8):
        print("         core.py line %-2i -> %s"
              % (line, ", ".join(sorted(str(k) for k in
                                        index.of_line("parser/core.py",
                                                      line)))
                 or "<nobody>"))

    keys = sorted(str(k) for k in index.of_line("parser/core.py", 4))
    ok = check([
        (directory_tuple == ("other/TEST", "parser/TEST"),
         "both directories were walked"),
        (keys == ["parser/TEST:0.0", "parser/TEST:0.1"],
         "a line both choices reached names both, each carrying the "
         "directory it was found in"),
        (index.of_line("parser/core.py", 2)
         != index.of_line("parser/core.py", 4),
         "the segment boundary stands where the set of runs changes"),
        ("other/TEST" in "".join(sorted(str(k) for k in
                                        index.run_key_set)),
         "a run id of ANOTHER directory is told apart though both "
         "count from 0"),
    ])
    shutil.rmtree(root)
    verdict(ok, "ids are directory-local; the gather qualifies them.")


def test_groups():
    """The group of groups, and the chain that decodes it."""
    root = fixture()
    index, _, snapshot_db, bundle = gathered(root)

    banner("each gathered group, as (directory, local group) pairs")
    for group_id, pair_tuple in sorted(
            gathered_group_db(index, snapshot_db).items()):
        print("         g'%s -> %s"
              % (group_id,
                 ", ".join("(%s, %s)" % p for p in pair_tuple) or "{}"))

    banner("the chain walked: what each gathered group MEANS")
    for group_id in sorted(bundle["group_of_groups"], key=int):
        if not bundle["group_of_groups"][group_id]: continue
        said = ["%s %s%s" % (directory, app,
                             "" if choice is None else " [%s]" % choice)
                for directory, app, choice
                in name_iterable(bundle, int(group_id))]
        print("         g'%s -> %s" % (group_id, "; ".join(said)))

    shared = None
    for group_id in bundle["group_of_groups"]:
        said = list(name_iterable(bundle, int(group_id))) \
               if bundle["group_of_groups"][group_id] else []
        if len(said) == 2: shared = said

    ok = check([
        (shared is not None,
         "one gathered group names TWO runs -- the lines 4..5 both "
         "choices reached"),
        (shared == [("parser/TEST", "test-parse", "basic"),
                    ("parser/TEST", "test-parse", "deep")],
         "and the chain decodes it to test applications and CHOICES: "
         "which is what the number is for"),
        (bundle["group_of_groups"]["0"] == [],
         "the empty group stays empty across the gather too"),
    ])
    shutil.rmtree(root)
    verdict(ok, "a set of (directory, group) pairs, as one number.")


def test_bundle():
    """The delivery, and what it does NOT touch."""
    root = fixture()
    _, directory_tuple, _, bundle = gathered(root)
    path = write_bundle(bundle, os.path.join(root, "bundle.json"))
    back = read_bundle(path)

    banner("what the bundle carries")
    print("INSPECT: format %s  directories %s"
          % (back["format"], ", ".join(back["directories"])))
    print("         gathered groups %i  files %i"
          % (len(back["group_of_groups"]), len(back["index"])))
    for directory in sorted(back["snapshot"]):
        entry = back["snapshot"][directory]
        print("         %-14s register generation %s, groups generation %s"
              % (directory, entry["register_generation"],
                 entry["groups_generation"]))

    banner("a snapshot is the table AS TEXT")
    for line in back["snapshot"]["parser/TEST"]["register"].splitlines():
        print("           | %s" % line)

    banner("the gather wrote into no directory's GOOD/")
    written = [d for d in directory_tuple
               if os.path.exists(os.path.join(root, d, "GOOD",
                                              "group_ids.dat"))]
    print("         directories whose group table now exists: %s"
          % (", ".join(written) or "none"))

    ok = check([
        (back == bundle, "the bundle round-trips"),
        (back["format"] == FORMAT_VERSION,
         "and names the version it was written in"),
        (not written,
         "NOTHING was written back: a gather's table is a function of "
         "the root the caller chose, and nothing it makes is identity"),
        (sorted(back["snapshot"]) == list(back["directories"]),
         "one snapshot per directory the fold touched"),
        ("##VUT-TEST-IDS" in back["snapshot"]["parser/TEST"]["register"],
         "the register travels as its own text format"),
    ])
    shutil.rmtree(root)
    verdict(ok, "a delivery is the index and a versioned copy of every "
                "table that decodes it.")


def test_stale():
    """What moved since the snapshot."""
    root = fixture()
    _, _, _, bundle = gathered(root)
    path = write_bundle(bundle, os.path.join(root, "bundle.json"))

    banner("the tree as it was taken")
    print("         %s" % (list(stale_tuple(read_bundle(path), root))
                           or "nothing moved"))

    banner("after an accept in one directory")
    TestIdDb(os.path.join(root, "parser/TEST")).run_id_of(
        "test-new", None, allocate_f=True)
    after = list(stale_tuple(read_bundle(path), root))
    for directory, what, how in after:
        print("         %-14s %s %s" % (directory, what, how))

    banner("the ids of the bundle still decode")
    said = list(name_iterable(read_bundle(path),
                              next(int(g) for g in bundle["group_of_groups"]
                                   if bundle["group_of_groups"][g])))
    print("         %s" % "; ".join("%s %s" % (d, a) for d, a, _ in said))

    banner("and after the directory is gone")
    shutil.rmtree(os.path.join(root, "other/TEST"))
    gone = list(stale_tuple(read_bundle(path), root))
    for directory, what, how in gone:
        print("         %-14s %s %s" % (directory, what, how))

    ok = check([
        (after == [("parser/TEST", "register", "moved")],
         "the directory that moved is named, and only it"),
        (said, "the bundle still decodes: an id is issued once, so a "
               "snapshot read against a NEWER register still resolves"),
        (("other/TEST", "both", "gone") in gone,
         "a directory that no longer reads is named 'gone', not "
         "silently skipped"),
    ])
    shutil.rmtree(root)
    verdict(ok, "the generation says whether the tree moved, not "
                "whether the answer is wrong.")


def test_refused():
    """What the reader refuses."""
    root = tempfile.mkdtemp(prefix="vut_gather_")

    def refusal(name, text):
        """RETURN: str, the refusal's own words, or 'nothing'."""
        path = os.path.join(root, name)
        with io.open(path, "w", encoding="utf-8") as fh: fh.write(text)
        try:               read_bundle(path)
        except GatherFault as fault: return str(fault).replace(root, "<dir>")
        return "nothing"

    banner("bundles that cannot be read")
    case_list = [
        ("not json",             "a.json", "not json at all"),
        ("a version this build does not read",
                                 "b.json", json.dumps({"format": 99})),
        ("no 'snapshot'",        "c.json",
         json.dumps({"format": FORMAT_VERSION, "directories": [],
                     "group_of_groups": {}, "index": {}})),
    ]
    result_list = []
    for label, name, text in case_list:
        said = refusal(name, text)
        print("         %-38s -> %s" % (label, said))
        result_list.append((said != "nothing", "refused: %s" % label))

    banner("a gathered group the bundle does not carry")
    empty = {"format": FORMAT_VERSION, "directories": [],
             "group_of_groups": {}, "index": {}, "snapshot": {}}
    try:               list(name_iterable(empty, 7)); said = "nothing"
    except GatherFault as fault: said = str(fault)
    print("         %-38s -> %s" % ("group 7, in an empty bundle", said))
    result_list.append((said != "nothing",
                        "refused: a group the bundle does not carry"))

    banner("a bundle naming a directory it carries no snapshot of")
    lying = dict(empty, group_of_groups={"1": [["parser/TEST", 2]]})
    try:               list(name_iterable(lying, 1)); said = "nothing"
    except GatherFault as fault: said = str(fault)
    print("         %-38s -> %s" % ("group 1 -> an absent snapshot", said))
    result_list.append((said != "nothing",
                        "refused: a pair whose snapshot is missing -- "
                        "the chain is broken and says so"))

    ok = check(result_list)
    shutil.rmtree(root)
    verdict(ok, "a delivery half understood is a report that lies.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The gather: many directories, one index, one bundle",
        choice_map = {
            "fold":    test_fold,
            "groups":  test_groups,
            "bundle":  test_bundle,
            "stale":   test_stale,
            "refused": test_refused,
        },
        happy      = "SUCCESS.*",
    ).run()
