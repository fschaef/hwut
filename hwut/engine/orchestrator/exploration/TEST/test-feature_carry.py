#! /usr/bin/env python3
#
# @hwut {
#     title      = "The features a moved or removed test takes along: carried, the central file following"
#     choices {
#         moved   { features = ["features-follow-moved-test"] }
#         removed { features = ["removal-names-unproven"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'feature_carry.py' -- what follows a test that moves to another
         TEST directory or is removed (R-91, R-96 step 6).

CHOICES: moved, removed;

moved    'test_moved' for a feature only the mover links to (moved: the
         definition carried, the leaf repointed), one a staying test still
         links to (copied, kept, the copy not registered), one the target
         defines alike (merged: the source's taken out, its leaf retired),
         one the target defines otherwise (both left); a target with no
         feature file and no id (written, registered, repointed); no
         central file (carried, nothing else).

removed  'unproven_by_removal': the features a test, or one choice of it,
         leaves without a linked run.
______________________________________________________________________________
"""
import os
import re
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration import feature_carry  # noqa E402

CENTRAL = """features {
    directory_map {
        "Srce0001" = "src"
        "Trgt0001" = "dst"
    }
    tree {
        "only"   = "Srce0001:only"
        "shared" = "Srce0001:shared"
        "same"   = "Srce0001:same"
        "differ" = "Srce0001:differ"
        "same-t" = "Trgt0001:same"
    }
    retired {
    }
}
"""


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _write(root, path, text, mode=None):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mode is not None: os.chmod(full, mode)


def _shown(root, path):
    """RETURN: None. Prints the file 'root/path', a fresh id masked."""
    print("%s:" % path)
    with open(os.path.join(root, path), encoding="utf-8") as fh:
        text = fh.read()
    for each in set(re.findall(r'"([A-Za-z0-9_-]{8})" = "', text)) \
                - {"Srce0001", "Trgt0001"}:
        text = text.replace(each, "<new id>")
    for line in text.splitlines(): print("    | %s" % line)


def _tree(central_f=True):
    """RETURN: str, a scratch tree: 'src/TEST' defining four features, a
    test linking 'only', 'same' and 'differ', another linking 'shared';
    'dst/TEST' defining 'same' alike and 'differ' otherwise."""
    root = tempfile.mkdtemp(prefix="hwut-carry-", dir="/tmp")
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    if central_f: _write(root, "hwut-root-features.conf", CENTRAL)
    _write(root, "src/TEST/hwut-features.conf",
           "features {\n    childs {\n"
           "        only   { title = \"Only the mover.\" }\n"
           "        shared { title = \"Both.\" }\n"
           "        same   { title = \"Alike.\" }\n"
           "        differ { title = \"Here.\" }\n"
           "    }\n}\n")
    _write(root, "dst/TEST/hwut-features.conf",
           "features {\n    childs {\n"
           "        same   { title = \"Alike.\" }\n"
           "        differ { title = \"There.\" }\n"
           "    }\n}\n")
    for path, names in (("src/TEST/test-go.sh", "only shared same differ"),
                        ("src/TEST/test-stay.sh", "shared")):
        _write(root, path, "#! /bin/sh\n# @hwut {\n#     title = \"T\"\n"
               "#     features = [%s]\n# }\necho x\n"
               % ", ".join('"%s"' % n for n in names.split()), 0o755)
    return root


def _moved(root, target):
    """RETURN: None. Carries the links of 'test-go.sh' from 'src/TEST' to
    'target/TEST' and prints what was said."""
    source = os.path.join(root, "src/TEST")
    os.makedirs(os.path.join(root, target, "TEST"), exist_ok=True)
    done = feature_carry.test_moved(
        root, source, os.path.join(root, target, "TEST"),
        feature_carry.linked_name_set(source, test="test-go.sh"),
        feature_carry.linked_name_set(source, without="test-go.sh"))
    for line in done.said_tuple:
        print("    %s" % re.sub(r"\b(?!Srce0001|Trgt0001)[A-Za-z0-9_-]{8}"
                                r"(?=:| registered)", "<new id>", line))


def test_moved():
    """RETURN: None. Prints what a move carries and how the central file
    follows."""
    root = _tree()
    try:
        banner("into dst, which defines 'same' alike and 'differ' otherwise")
        _moved(root, "dst")
        for path in ("src/TEST/hwut-features.conf",
                     "dst/TEST/hwut-features.conf",
                     "hwut-root-features.conf"):
            _shown(root, path)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    root = _tree()
    try:
        banner("into new, without a feature file and without an id")
        _moved(root, "new")
        for path in ("new/TEST/hwut-features.conf",
                     "hwut-root-features.conf"):
            _shown(root, path)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    root = _tree(central_f=False)
    try:
        banner("no central file: the definitions alone")
        _moved(root, "new")
        _shown(root, "new/TEST/hwut-features.conf")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_removed():
    """RETURN: None. Prints what a removal leaves without a linked run."""
    root = _tree()
    try:
        source = os.path.join(root, "src/TEST")
        for test in ("test-go.sh", "test-stay.sh", "test-none.sh"):
            print("%-13s %s" % (test, feature_carry.unproven_by_removal(
                source, test)))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The features a moved or removed test takes along: "
                     "carried, the central file following",
        choice_map = {
            "moved":   test_moved,
            "removed": test_removed,
        },
    ).run()
