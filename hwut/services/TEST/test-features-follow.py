#! /usr/bin/env python3
#  @hwut {
#    title   = "hwut.move and hwut.remove: the features of the test they act on"
#    choices {
#        move    { features = ["move-features-follow"] }
#        remove  { features = ["remove-names-features"] }
#    }
#  }
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT 'hwut.move' AND 'hwut.remove' DO TO THE FEATURES of the test
         they act on (R-91, R-96 step 6).

CHOICES: move, remove;

DESCRIPTION:

    move     'hwut.move' of a test into another TEST directory: the features
             it links to are carried into that directory's feature file --
             one still linked by a test that stays is copied, the copy not
             registered -- and the central file follows: the leaf is
             repointed to the target's directory id. Into a directory
             without a feature file and without an id: the file is written,
             the directory registered, the leaf repointed.
    remove   'hwut.remove' of a test: the features it leaves without a
             linked run are named.

The carrying itself: 'engine/orchestrator/exploration/feature_carry.py'.
______________________________________________________________________________
"""
import os
import re
import sys
import shutil
import tempfile

import config                                                       # noqa: F401

from hwut.engine.bookkeeper.api import Bookkeeper
from hwut.services import rename, remove
from hwut.test_writing_support.python.hwut_runner import HwutRunner


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _write(path, text):
    """RETURN: None. Writes 'text' to 'path' below the cwd, directories
    made."""
    if os.path.dirname(path): os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _test(path, body=()):
    """RETURN: None. Writes a shell test at 'path' whose block holds a
    title and the lines of 'body'."""
    _write(path, "#! /bin/sh\n# @hwut {\n#     title = \"T\"\n%s# }\necho x\n"
           % "".join("#     %s\n" % line for line in body))
    os.chmod(path, 0o755)


def _masked(text):
    """RETURN: str, 'text' with every directory id the central file
    issued by chance written '<new id>'."""
    if not os.path.isfile("hwut-root-features.conf"): return text
    with open("hwut-root-features.conf", encoding="utf-8") as handle:
        issued = set(re.findall(r'"([A-Za-z0-9_-]{8})" = "',
                                handle.read())) - {"Core0001", "Cmp00001"}
    for each in issued: text = text.replace(each, "<new id>")
    return text


def _shown(path):
    """RETURN: None. Prints the file at 'path', indented."""
    print("%s:" % path)
    with open(path, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            print("    | %s" % _masked(line))


def tree():
    """RETURN: None. In the cwd: engine / {compare / {core}, plain}, two
    TEST directories stating features, both registered in the central
    file."""
    _write("hwut-root.conf", "hwut {\n}\n")
    _write("engine/compare/core/TEST/hwut-features.conf",
           'features {\n    childs {\n'
           '        line-pairing { title = "Lines are paired." }\n'
           '        missing-side { title = "A lone line is shown." }\n'
           '    }\n}\n')
    _write("engine/compare/TEST/hwut-features.conf",
           'features {\n    childs {\n'
           '        whole-page { title = "A whole page is judged." }\n'
           '    }\n}\n')
    _write("hwut-root-features.conf",
           'features {\n'
           '    directory_map {\n'
           '        "Core0001" = "engine/compare/core"\n'
           '        "Cmp00001" = "engine/compare"\n'
           '    }\n'
           '    tree {\n'
           '        "pairing"    = "Core0001:line-pairing"\n'
           '        "lone-line"  = "Core0001:missing-side"\n'
           '        "whole-page" = "Cmp00001:whole-page"\n'
           '    }\n'
           '    retired {\n    }\n'
           '}\n')
    _test("engine/compare/core/TEST/test-pair.sh",
          ['features = ["line-pairing"]'])
    _test("engine/compare/core/TEST/test-side.sh",
          ['features = ["line-pairing", "missing-side"]'])
    _test("engine/compare/TEST/test-pages.sh", ['features = ["whole-page"]'])
    _test("engine/plain/TEST/test-plain.sh")


def _in_tree(build, function):
    """RETURN: None. Calls 'function()' with the cwd at the root of a
    fresh tree that 'build()' filled there; removes it afterwards."""
    ground = tempfile.mkdtemp(prefix="hwut-follow-", dir="/tmp")
    root   = os.path.join(ground, "tree")
    here   = os.getcwd()
    try:
        os.makedirs(root)
        os.chdir(root)
        build()
        function()
    finally:
        os.chdir(here)
        shutil.rmtree(ground, ignore_errors=True)


def _said(text):
    """RETURN: None. Prints one line a face wrote, the tree's place
    taken out of it."""
    for line in str(text).rstrip("\n").split("\n"):
        print("    %s" % _masked(line.replace(os.getcwd(), "<tree>")))


def run_move():
    """RETURN: None. A test moved into another TEST directory."""
    def body():
        core, page = "engine/compare/core/TEST", "engine/compare/TEST"
        Bookkeeper(core).note_accept("test-side.sh", None)
        banner("the author moves the application; hwut.move follows")
        shutil.move(os.path.join(core, "test-side.sh"),
                    os.path.join(page, "test-side.sh"))
        status = rename.main(["test-side.sh", "-to", "%s/test-side.sh" % page,
                              "--dont-ask", "--directory=%s" % core],
                             write=_said)
        print("status: %s" % status.name)
        banner("the two feature files, and the central file")
        _shown(core + "/hwut-features.conf")
        _shown(page + "/hwut-features.conf")
        _shown("hwut-root-features.conf")
        banner("into a directory without a feature file")
        Bookkeeper(page).note_accept("test-pages.sh", None)
        shutil.move(os.path.join(page, "test-pages.sh"),
                    "engine/plain/TEST/test-pages.sh")
        status = rename.main(["test-pages.sh", "-to",
                              "engine/plain/TEST/test-pages.sh", "--dont-ask",
                              "--directory=%s" % page], write=_said)
        print("status: %s" % status.name)
        _shown("engine/plain/TEST/hwut-features.conf")
        _shown("hwut-root-features.conf")
    _in_tree(tree, body)


def run_remove():
    """RETURN: None. A test removed, and the features it leaves."""
    def body():
        core = "engine/compare/core/TEST"
        for test in ("test-pair.sh", "test-side.sh"):
            Bookkeeper(core).note_accept(test, None)
        banner("a test whose features another test still proves")
        status = remove.main(["test-pair.sh", "--dont-ask",
                              "--directory=%s" % core], write=_said)
        print("status: %s" % status.name)
        banner("the last test proving them")
        status = remove.main(["test-side.sh", "--dont-ask",
                              "--directory=%s" % core], write=_said)
        print("status: %s" % status.name)
    _in_tree(tree, body)


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.move and hwut.remove: the features of the "
                     "test they act on",
        choice_map = {
            "move":    run_move,
            "remove":  run_remove,
        },
    ).run()
