#! /usr/bin/env python3
#
# @hwut {
#     title      = "The feature label f/<feature> where the central file stands: tree paths, external ids, internal ids; -F, -e, -k refused on a run face"
#     choices {
#         path     { features = ["wish-reads-registry"] }
#         ext      { features = ["wish-reads-registry"] }
#         keys     { features = ["wish-reads-registry"] }
#         together { features = ["wish-reads-registry"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE LABEL 'f/<feature>' where 'hwut-root-features.conf'
         stands (intend/three-worlds, ruled 2026-10-31; R-96 for what a
         feature path is), asked through 'hwut.report.list', which prints
         the selection as a wishlist -- on the scratch tree of
         'test-report.py': gateway/forwarding (router.forward,
         router.keep-order), gateway/buses (can.decode), gateway/later
         (empty), unplaced router.drop; retired can.old, router.old.

CHOICES: path, ext, keys, together;

path      'f/' over tree paths: an aggregate brings its subtree, a leaf by
          its path, a bare word anywhere, the lines of 'hwut.features.tree
          --list' as they stand; an internal id; a glob refused (a label
          names ONE feature); a retired internal id and a feature named
          nowhere refused by name; an empty aggregate (empty).

ext       'f/<external id>', the bare word; '-e' and '--feature-ext' refused
          on a run face, naming 'f/'.

keys      '-k' refused on a run face: keys select FEATURES, and the
          feature world's face answers them ('hwut.report.features -k').

together  feature labels combined as labels: a union, a difference, NOT; a
          derived label of 'hwut-root.labels' over a feature and a label;
          '-l f/...' beside '--fail' refused (combine in labels); a
          feature's runs frozen into a label ('hwut.labels.create -l
          f/...'); 'f/' where no central file stands: refused.
______________________________________________________________________________
"""
import importlib.util
import os
import shutil
import sys

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _fixture():
    """RETURN: module, 'test-report.py' -- its scratch tree is this test's
    too."""
    spec = importlib.util.spec_from_file_location(
        "test_report", os.path.join(HERE, "test-report.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = _fixture()


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _ask(root, *argv):
    """RETURN: None. Prints the wish, what 'hwut.report.list' selects for
    it, and its exit status."""
    text, code = FIXTURE._launch(root, "hwut.report.list", *argv)
    print(">>> %s" % " ".join(argv))
    for line in text.rstrip("\n").split("\n"):
        if line.strip(): print("    " + line)
    print("    exit %d" % code)


def _case(body):
    """RETURN: None. Calls 'body(root)' on a fresh scratch tree."""
    root = FIXTURE._tree()
    try:
        body(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_path():
    """RETURN: None. Prints what 'f/<tree path>' selects and refuses."""
    def body(root):
        banner("tree paths")
        for path in ("gateway/forwarding", "gateway",
                     "gateway/forwarding/router.keep-order",
                     "buses", "gateway/later", "router.drop"):
            _ask(root, "-l", "f/" + path)
        banner("the lines of hwut.features.tree --list")
        text, _ = FIXTURE._launch(root, "hwut.features.tree", "--list")
        for line in text.split():
            _ask(root, "-l", "f/" + line)
        banner("internal ids")
        _ask(root, "-l", "f/Aaaaaaa1:decode")
        _ask(root, "-l", "f/Aaaaaaa1:old")
        banner("refused: a glob, a feature named nowhere")
        _ask(root, "-l", "f/gateway/*/can.decode")
        _ask(root, "-l", "f/nothing")
    _case(body)


def test_ext():
    """RETURN: None. Prints what 'f/<external id>' selects, and the
    refused '-e'."""
    def body(root):
        for argv in (["-l", "f/can.decode"], ["-l", "f/router.forward"],
                     ["-l", "f/router.keep-order"], ["-l", "f/router.drop"],
                     ["-l", "f/can.old"],
                     ["-e", "can.decode"], ["--feature-ext=router.keep-order"],
                     ["-F", "gateway"]):
            _ask(root, *argv)
    _case(body)


def test_keys():
    """RETURN: None. '-k' on a run face is refused; the feature world's
    face answers it."""
    def body(root):
        _ask(root, "-k", "latency")
        text, code = FIXTURE._launch(root, "hwut.report.features", "-k",
                                     "latency")
        print(">>> hwut.report.features -k latency")
        for line in text.rstrip("\n").split("\n"):
            if line.strip(): print("    " + line)
        print("    exit %d" % code)
    _case(body)


def test_together():
    """RETURN: None. Feature labels combined in the label world."""
    def body(root):
        _ask(root, "-l", "f/gateway/buses OR f/router.forward")
        _ask(root, "-l", "f/gateway AND NOT f/gateway/buses")
        _ask(root, "-l", "NOT f/gateway")
        with open(os.path.join(root, "hwut-root.labels"), "w") as fh:
            fh.write("./gw/router/TEST/test-route.sh burst : slow\n"
                     "\n[derived]\n"
                     "focus = f/gateway/forwarding AND NOT slow\n")
        _ask(root, "-l", "focus")
        _ask(root, "-l", "slow OR f/gateway/buses")
        _ask(root, "-l", "f/gateway/buses", "--fail")
        text, code = FIXTURE._launch(root, "hwut.labels.create", "buses_today",
                                     "-l", "f/gateway/buses")
        print(">>> hwut.labels.create buses_today -l f/gateway/buses")
        for line in text.rstrip("\n").split("\n"):
            if line.strip(): print("    " + line)
        print("    exit %d" % code)
        _ask(root, "-l", "buses_today")
        os.remove(os.path.join(root, "hwut-root-features.conf"))
        _ask(root, "-l", "f/can.decode")
    _case(body)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The feature label f/<feature> where the central file "
                     "stands: tree paths, external ids, internal ids; -F, "
                     "-e, -k refused on a run face",
        choice_map = {
            "path":     test_path,
            "ext":      test_ext,
            "keys":     test_keys,
            "together": test_together,
        },
    ).run()
