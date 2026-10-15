#! /usr/bin/env python3
#
# @hwut {
#     title      = "The feature wish where the central file stands: -F tree paths and internal ids, -e external ids, -k"
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

PURPOSE: THE FEATURE WISH where 'hwut-root-features.conf' stands (spec 23
         VERSION 10 section 11, R-96), asked through 'hwut.report.list',
         which prints the selection as a wishlist -- on the scratch tree of
         'test-report.py': gateway/forwarding (router.forward,
         router.keep-order), gateway/buses (can.decode), gateway/later
         (empty), unplaced router.drop; retired can.old, router.old.

CHOICES: path, ext, keys, together;

path      '-F' over tree paths: an aggregate brings its subtree, a leaf by
          its path, '*', '**', '{a,b}', a bare word anywhere, the lines of
          'hwut.features.tree --list' as they stand; an internal id, '*' in
          one; a retired internal id refused; a path naming nothing (empty).

ext       '-e' over external ids: exact, '*'; an id naming nothing and a
          retired one refused by name; the long spellings.

keys      '-k' over the effective keys: an aggregate's key reaches every
          leaf below it, a TEST file's every feature of it; a key nobody
          carries refused.

together  '-F' and '-e' one union; '-k' narrowing it; the wishlist the
          selection prints; '-e' where no central file stands: refused.
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
    """RETURN: None. Prints what '-F' selects."""
    def body(root):
        banner("tree paths")
        for glob in ("gateway/forwarding", "gateway",
                     "gateway/forwarding/router.keep-order",
                     "gateway/*/can.decode", "**/router.forward",
                     "gateway/{buses,forwarding}", "router.*",
                     "buses", "gateway/later", "router.drop", "nothing"):
            _ask(root, "-F", glob)
        banner("the lines of hwut.features.tree --list")
        text, _ = FIXTURE._launch(root, "hwut.features.tree", "--list")
        for line in text.split():
            _ask(root, "-F", line)
        banner("internal ids")
        _ask(root, "-F", "Aaaaaaa1:decode")
        _ask(root, "-F", "Bbbbbbb2:*")
        _ask(root, "-F", "Aaaaaaa1:old")
    _case(body)


def test_ext():
    """RETURN: None. Prints what '-e' selects and refuses."""
    def body(root):
        for argv in (["-e", "can.decode"], ["-e", "router.*"],
                     ["--feature-ext", "router.forward"],
                     ["--feature-ext=router.keep-order"],
                     ["-e", "router.drop"], ["-e", "nope"],
                     ["-e", "can.old"], ["-e"], ["--feature-ext="]):
            _ask(root, *argv)
    _case(body)


def test_keys():
    """RETURN: None. Prints what '-k' selects."""
    def body(root):
        for expression in ("product", "routing", "latency",
                           "product AND NOT latency", "nobody"):
            _ask(root, "-k", expression)
    _case(body)


def test_together():
    """RETURN: None. Prints '-F', '-e' and '-k' together."""
    def body(root):
        _ask(root, "-F", "gateway/buses", "-e", "router.forward")
        _ask(root, "-F", "gateway", "-k", "latency")
        _ask(root, "-e", "can.decode", "-k", "routing")
        _ask(root, "-F", "gateway/forwarding", "--fail")
        _ask(root, "-F", "gateway/buses", "--fail")
        os.remove(os.path.join(root, "hwut-root-features.conf"))
        _ask(root, "-e", "can.decode")
    _case(body)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The feature wish where the central file stands: -F "
                     "tree paths and internal ids, -e external ids, -k",
        choice_map = {
            "path":     test_path,
            "ext":      test_ext,
            "keys":     test_keys,
            "together": test_together,
        },
    ).run()
