#! /usr/bin/env python3
#
# @hwut {
#     title      = "The one detector: the central file against the tree, the pairings named"
#     choices {
#         clean     { features = ["detector-judges"] }
#         new       { features = ["detector-judges"] }
#         moved     { features = ["detector-pairs"] }
#         swapped   { features = ["detector-pairs"] }
#         leaves    { features = ["detector-pairs"] }
#         twin      { features = ["detector-judges"] }
#         old       { features = ["detector-judges"] }
#         below     { features = ["detector-judges"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DETECTOR (spec 23 VERSION 10 section 7, R-96): the central
         file 'hwut-root-features.conf' judged against how a scratch tree
         stands. Every pairing is NAMED on its proposal line; where the
         detector cannot tell, it says 'unpaired' and lists the candidates.

CHOICES: clean, new, moved, swapped, leaves, twin, old, below;

clean    a tree that agrees with its file: nothing is found. No central
         file: None.

new      what is not registered yet: a directory without an id, a name
         defined in a registered directory, an unplaced leaf, a name that was
         retired and is defined again.

moved    a directory moved or renamed by hand: paired by the fingerprint of
         its feature names; renamed leaves beside; a component moved with two
         TEST directories; two candidates that cannot be told apart.

swapped  two directories that exchanged their contents under unchanged
         paths; one that did so with a directory without an id.

leaves   a leaf renamed (the only gone, the only new), two renamed at once
         (unpaired), a block moved to another directory by hand, a leaf
         whose directory is gone.

twin     one path under two ids.

old      a component file and a map file that stand: no longer read.

below    the same findings restricted to a directory.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration import feature_detector as fd  # noqa E402


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def _features(root, component, name_list):
    """RETURN: None. Writes 'component/TEST/hwut-features.conf' defining the
    names 'name_list'."""
    _write(root, component + "/TEST/hwut-features.conf",
           "features {\n  childs {\n%s  }\n}\n" % "".join(
               '    %s { title = "%s." }\n' % (name, name)
               for name in name_list))


def _central(root, directory_db, leaf_list, retired=""):
    """RETURN: None. Writes the central file: 'directory_db' id -> path, and
    'leaf_list' of (external, id, name), all in one aggregate 'g', except the
    leaves whose external id begins with '!' (unplaced)."""
    lines = ["features {", "  directory_map {"]
    lines += ['    "%s" = "%s"' % (i, p) for i, p in directory_db.items()]
    lines += ["  }", "  tree {", "    g { childs {"]
    lines += ['      "%s" = "%s:%s"' % (e, i, n)
              for e, i, n in leaf_list if not e.startswith("!")]
    lines += ["    } }"]
    lines += ['    "%s" = "%s:%s"' % (e[1:], i, n)
              for e, i, n in leaf_list if e.startswith("!")]
    lines += ["  }", "  retired {%s}" % retired, "}"]
    _write(root, "hwut-root-features.conf", "\n".join(lines) + "\n")


def _tree(fact_db, directory_db, leaf_list, retired=""):
    """RETURN: str, the root of a scratch tree: 'fact_db' path -> names
    defined; the central file as given."""
    root = tempfile.mkdtemp(prefix="hwut-detector-")
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    for path, name_list in fact_db.items():
        _features(root, path, name_list)
    _central(root, directory_db, leaf_list, retired)
    return root


def _show(root, below=None):
    """RETURN: None. Prints what the detector finds in 'root'."""
    found = fd.detect(root, below)
    if found is None:
        print("  no central file")
        return
    if not found:
        print("  nothing found")
    for each in found:
        print("  %-12s %s%s" % (each.kind, each.text,
                                "   (hint)" if each.hint_f else ""))
        for line in each.proposal:
            print("  %-12s     => %s" % ("", line))


def _case(label, fact_db, directory_db, leaf_list, retired="", below=None):
    """RETURN: None. Builds a scratch tree, prints the findings, removes it."""
    banner(label)
    root = _tree(fact_db, directory_db, leaf_list, retired)
    try:
        _show(root, below)
    finally:
        shutil.rmtree(root, ignore_errors=True)


A, B, C, D = "Aaaaaaa1", "Bbbbbbb2", "Ccccccc3", "Ddddddd4"
CAN = [("c.decode", A, "decode"), ("c.encode", A, "encode")]
MOST = [("m.send", B, "send"), ("m.receive", B, "receive")]
BASE_DIR = {A: "gw/can", B: "gw/most"}
BASE_FACT = {"gw/can": ["decode", "encode"], "gw/most": ["send", "receive"]}


def test_clean():
    """RETURN: None. Prints the findings of a tree that agrees with its
    file, and of a tree without one."""
    _case("a tree that agrees with its file", BASE_FACT, BASE_DIR, CAN + MOST)
    banner("no central file")
    root = tempfile.mkdtemp(prefix="hwut-detector-")
    try:
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _features(root, "gw/can", ["decode"])
        _show(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    banner("a TEST directory without a feature file is no component")
    root = _tree(BASE_FACT, BASE_DIR, CAN + MOST)
    try:
        _write(root, "gw/misc/TEST/test-x.sh", "#! /bin/bash\n")
        _show(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_new():
    """RETURN: None. Prints what is not registered."""
    fact = dict(BASE_FACT)
    fact["gw/router"] = ["forward", "keep-order"]
    _case("a directory without an id", fact, BASE_DIR, CAN + MOST)
    fact = dict(BASE_FACT)
    fact["gw/can"] = ["decode", "encode", "reset"]
    _case("a name defined in a registered directory, in no line", fact,
          BASE_DIR, CAN + MOST)
    banner("an unplaced leaf")
    root = tempfile.mkdtemp(prefix="hwut-detector-")
    try:
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _features(root, "gw/can", ["decode", "encode"])
        _central(root, {A: "gw/can"}, [("c.decode", A, "decode"),
                                       ("!c.encode", A, "encode")])
        _show(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    fact = dict(BASE_FACT)
    fact["gw/can"] = ["decode", "encode", "scroll"]
    _case("a name that was retired and is defined again", fact, BASE_DIR,
          CAN + MOST,
          '\n "scroll-old" { id = "%s:scroll" title = "S" }\n' % A)
    #  THE ROOT IS A DIRECTORY LIKE ANY OTHER (the book's D-3). MEASURED
    #  2026-10-19: 'root-test ... no directory id can stand for it (hint)'.
    banner("the root's own TEST directory: a directory without an id")
    root = _tree(BASE_FACT, BASE_DIR, CAN + MOST)
    try:
        _features(root, ".", ["top"])
        _show(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    #  ITS ID IS NEVER SENT ELSEWHERE: the root does not move. Its names
    #  defined below it instead are a new directory; its leaves are gone.
    fact = dict(BASE_FACT)
    fact["top/x"] = ["top"]
    dir_db = dict(BASE_DIR)
    dir_db["RootId01"] = "."
    _case("the root's names defined elsewhere: no redirect of its id", fact,
          dir_db, CAN + MOST + [("top", "RootId01", "top")])


def test_moved():
    """RETURN: None. Prints what a directory moved by hand makes of the
    file."""
    _case("renamed: gw/can -> gw/bus-can",
          {"gw/bus-can": ["decode", "encode"], "gw/most": ["send", "receive"]},
          BASE_DIR, CAN + MOST)
    _case("moved and one leaf renamed (half of the names stand)",
          {"gw/bus-can": ["decode", "transmit"], "gw/most": ["send", "receive"]},
          BASE_DIR, CAN + MOST)
    _case("moved and only a third of the names stand",
          {"x/can": ["decode", "p", "q"], "gw/most": ["send", "receive"]},
          BASE_DIR, CAN + [("c.third", A, "third")] + MOST)
    _case("a component moved with two TEST directories",
          {"new/gw/can": ["decode", "encode"], "new/gw/most": ["send", "receive"]},
          BASE_DIR, CAN + MOST)
    _case("two candidates that cannot be told apart (a copy and the original gone)",
          {"gw/can-a": ["decode", "encode"], "gw/can-b": ["decode", "encode"],
           "gw/most": ["send", "receive"]},
          BASE_DIR, CAN + MOST)
    _case("a directory deleted: its leaves are said by the directory",
          {"gw/most": ["send", "receive"]}, BASE_DIR, CAN + MOST)
    _case("a copy next to the original: the original stands, the copy is new",
          {"gw/can": ["decode", "encode"], "gw/can-copy": ["decode", "encode"],
           "gw/most": ["send", "receive"]}, BASE_DIR, CAN + MOST)


def test_swapped():
    """RETURN: None. Prints what directories that exchanged their contents
    make of the file."""
    _case("gw/can and gw/most exchanged their contents",
          {"gw/can": ["send", "receive"], "gw/most": ["decode", "encode"]},
          BASE_DIR, CAN + MOST)
    _case("gw/can now holds what gw/most held; gw/most holds something else",
          {"gw/can": ["send", "receive"], "gw/most": ["other"]},
          BASE_DIR, CAN + MOST)
    _case("features removed from a directory that stands: no swap",
          {"gw/can": ["decode"], "gw/most": ["send", "receive"]},
          BASE_DIR, CAN + MOST)


def test_leaves():
    """RETURN: None. Prints what leaves renamed and moved make of the
    file."""
    _case("one leaf renamed: the only gone and the only new",
          {"gw/can": ["decode", "encode-frame"],
           "gw/most": ["send", "receive"]}, BASE_DIR, CAN + MOST)
    _case("two leaves renamed at once: not paired",
          {"gw/can": ["decode-frame", "encode-frame"],
           "gw/most": ["send", "receive"]}, BASE_DIR, CAN + MOST)
    _case("a leaf deleted from its file",
          {"gw/can": ["decode"], "gw/most": ["send", "receive"]},
          BASE_DIR, CAN + MOST)
    _case("a block moved to another directory by hand (the same name)",
          {"gw/can": ["decode"], "gw/most": ["send", "receive", "encode"]},
          BASE_DIR, CAN + MOST)
    _case("moved by hand, and the name exists twice there",
          {"gw/can": ["decode"], "gw/most": ["send", "receive", "encode"],
           "gw/spare": ["encode"]},
          {A: "gw/can", B: "gw/most", C: "gw/spare"},
          CAN + MOST)


def test_twin():
    """RETURN: None. Prints one path under two ids."""
    _case("gw/can under two ids", BASE_FACT,
          {A: "gw/can", B: "gw/most", C: "gw/can"}, CAN + MOST)


def test_old():
    """RETURN: None. Prints the vocabulary of the past that stands."""
    banner("a component file, a map file, a TEST file")
    root = _tree(BASE_FACT, BASE_DIR, CAN + MOST)
    try:
        _write(root, "gw/hwut-features.conf", 'features {\n title = "G"\n}\n')
        _write(root, "hwut-feature-map.conf", "map {\n}\n")
        _write(root, "TMP/gw/hwut-features.conf", "features {\n}\n")
        _write(root, ".git/x/hwut-features.conf", "features {\n}\n")
        _show(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_below():
    """RETURN: None. Prints the findings restricted to a directory."""
    fact = {"gw/bus-can": ["decode", "encode"], "gw/most": ["send"],
            "other/x": ["y"]}
    for below in (None, ".", "gw", "gw/most", "gw/bus-can", "other", "zz"):
        _case("below %r" % (below,), fact, BASE_DIR, CAN + MOST,
              below=below)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The one detector: the central file against the tree, "
                     "the pairings named",
        choice_map = {
            "clean":   test_clean,
            "new":     test_new,
            "moved":   test_moved,
            "swapped": test_swapped,
            "leaves":  test_leaves,
            "twin":    test_twin,
            "old":     test_old,
            "below":   test_below,
        },
    ).run()
