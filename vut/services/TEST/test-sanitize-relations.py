#! /usr/bin/env python3
#  @hwut {
#    title   = "hwut.sanitize --relations, and the faces that follow a test"
#    choices = ["apply", "command", "move", "propose", "remove"]
#  }
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE STATEMENTS KEPT IN STEP, through the faces: what
         'hwut.sanitize.propose --relations' proposes, what 'relate' and
         'unrelate' do, and what 'hwut.move' and 'hwut.remove' do to the
         features of the test they act on.

CHOICES: propose, apply, command, move, remove;

DESCRIPTION:

    propose  a tree with a directory MOVED BY HAND, a statement file
             without an id and a 'childs' entry nothing carries: one
             'relate' per directory, the move noted, one 'unrelate';
             what cannot be proposed on stderr. A tree that agrees:
             EMPTY.
    apply    that proposal applied: every command done and what it
             said; proposed again, nothing is left.
    command  'hwut.sanitize relate <dir>' and 'unrelate <dir> <id>' one
             at a time: done, nothing to do, refused.
    move     'hwut.move' of a test into another TEST directory: the
             features it links to are carried into that directory's
             feature file.
    remove   'hwut.remove' of a test: the features it leaves without a
             linked run are named.

The adaption itself is pinned where it stands:
'engine/orchestrator/exploration/TEST/test-feature_adapt.py'.
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile

import config                                                       # noqa: F401

from   vut.engine.bookkeeper.api         import Bookkeeper
from   vut.services                      import sanitize, rename, remove
from   vut.services.lib.sanitize.propose import main as propose_main
from   vut.services.lib.sanitize.apply   import main as apply_main
from   vut.test_writing_support.python.hwut_runner import HwutRunner


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


def _shown(path):
    """RETURN: None. Prints the file at 'path', indented."""
    print("%s:" % path)
    with open(path, encoding="utf-8") as handle:
        for line in handle.read().splitlines(): print("    | %s" % line)


def tree():
    """RETURN: None. In the cwd: all / eng / {cmp / {core, TEST},
    plain}, every statement agreeing with the directories."""
    _write("hwut-root.conf", "hwut {\n}\n")
    _write("hwut-composition.conf",
           'component {\n    id     = "all"\n    childs = ["eng"]\n}\n')
    _write("engine/hwut-composition.conf",
           'component {\n    id     = "eng"\n    parent = "all"\n'
           '    childs {\n'
           '        cmp   = "Gives the verdict."\n'
           '        plain = "Plain things."\n'
           '    }\n}\n')
    _write("engine/compare/hwut-composition.conf",
           'component {\n    id     = "cmp"\n'
           '    parent { eng = "The engine\'s verdict rests on it." }\n'
           '    childs {\n'
           '        core      = "Aligns two streams line by line."\n'
           '        cmp-proof = "Proves the whole comparison."\n'
           '    }\n}\n')
    _write("engine/compare/core/hwut-composition.conf",
           'component {\n    id     = "core"\n'
           '    parent { cmp = "Alignment is what compare shows." }\n'
           '    childs { core-proof = "The proof of pairing." }\n}\n')
    _write("engine/compare/core/TEST/hwut-features.conf",
           'features {\n    id     = "core-proof"\n    parent = "core"\n'
           '    issued = 2\n'
           '    1 { name = "line-pairing"  title = "Lines are paired." }\n'
           '    2 { name = "missing-side"  title = "A lone line is shown." }\n'
           '}\n')
    _write("engine/compare/TEST/hwut-features.conf",
           'features {\n    id     = "cmp-proof"\n    parent = "cmp"\n'
           '    issued = 1\n'
           '    1 { name = "whole-page"  title = "A whole page is judged." }\n'
           '}\n')
    _write("engine/plain/hwut-composition.conf",
           'component {\n    id     = "plain"\n    parent = "eng"\n}\n')
    _test("engine/compare/core/TEST/test-pair.sh",
          ['features = ["line-pairing"]'])
    _test("engine/compare/core/TEST/test-side.sh",
          ['features = ["line-pairing", "missing-side"]'])
    _test("engine/compare/TEST/test-pages.sh", ['features = ["whole-page"]'])
    _test("engine/plain/TEST/test-plain.sh")


def disturbed():
    """RETURN: None. The tree, then: 'core' moved by hand below
    'plain', the feature file of 'engine/compare/TEST' without its id,
    and an entry 'old' in the 'childs' of 'engine'."""
    tree()
    shutil.move("engine/compare/core", "engine/plain/core")
    _write("engine/compare/TEST/hwut-features.conf",
           'features {\n    parent = "cmp"\n    issued = 1\n'
           '    1 { name = "whole-page"  title = "A whole page is judged." }\n'
           '}\n')
    _write("engine/hwut-composition.conf",
           'component {\n    id     = "eng"\n    parent = "all"\n'
           '    childs {\n'
           '        cmp   = "Gives the verdict."\n'
           '        plain = "Plain things."\n'
           '        old   = "Was here once."\n'
           '    }\n}\n')


def _in_tree(build, function):
    """RETURN: None. Calls 'function()' with the cwd at the root of a
    fresh tree that 'build()' filled there; removes it afterwards."""
    ground = tempfile.mkdtemp(prefix="hwut-relations-")
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
        print("    %s" % line.replace(os.getcwd(), "<tree>"))


def _proposed(file_name=None):
    """RETURN: None. Prints what 'hwut.sanitize.propose --relations'
    writes, what it says on stderr, and its status."""
    argv = ["--relations"] + (["-o", file_name] if file_name else [])
    status = propose_main(argv, write=_said,
                          err=lambda text: _said("stderr: %s" % text))
    print("status: %s" % status.name)


def run_propose():
    """RETURN: None. The proposal of a disturbed and of an agreeing
    tree."""
    def body():
        banner("a directory moved by hand, a missing id, a dead entry")
        _proposed()
        banner("two childs under one id, and a parent without an id")
        _write("engine/twin/hwut-composition.conf",
               'component { id = "cmp"  parent = "eng" }\n')
        _test("engine/twin/TEST/test-twin.sh")
        _write("engine/plain/hwut-composition.conf",
               'component {\n    parent = "eng"\n}\n')
        _proposed()
    _in_tree(disturbed, body)
    def agreeing():
        banner("a tree whose statements agree with its directories")
        _proposed()
    _in_tree(tree, agreeing)


def run_apply():
    """RETURN: None. The proposal applied, and proposed again."""
    def body():
        banner("hwut.sanitize.propose --relations -o proposal.txt")
        _proposed("proposal.txt")
        banner("hwut.sanitize.apply proposal.txt")
        status = apply_main(["proposal.txt"], write=_said)
        print("status: %s" % status.name)
        banner("the files")
        for path in ("engine/hwut-composition.conf",
                     "engine/compare/hwut-composition.conf",
                     "engine/plain/hwut-composition.conf",
                     "engine/plain/core/hwut-composition.conf",
                     "engine/compare/TEST/hwut-features.conf"):
            _shown(path)
        banner("proposed again")
        _proposed()
    _in_tree(disturbed, body)


def run_command():
    """RETURN: None. The two commands, one at a time."""
    def body():
        for label, word_list in (
                ("relate: a moved directory",  ["relate", "engine/plain/core"]),
                ("relate: again",              ["relate", "engine/plain/core"]),
                ("relate: no statement file",  ["relate", "engine/plain/TEST"]),
                ("relate: no such directory",  ["relate", "engine/nowhere"]),
                ("unrelate: a dead entry",     ["unrelate", "engine", "old"]),
                ("unrelate: again",            ["unrelate", "engine", "old"]),
                ("unrelate: an id a directory carries",
                                               ["unrelate", "engine", "cmp"]),
                ("unrelate: without the id",   ["unrelate", "engine"])):
            banner(label)
            print("hwut.sanitize %s" % " ".join(word_list))
            status = sanitize.main(word_list, write=_said)
            print("status: %s" % status.name)
    _in_tree(disturbed, body)


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
        banner("the two feature files")
        _shown(core + "/hwut-features.conf")
        _shown(page + "/hwut-features.conf")
        banner("into a directory without a feature file")
        Bookkeeper(page).note_accept("test-pages.sh", None)
        shutil.move(os.path.join(page, "test-pages.sh"),
                    "engine/plain/TEST/test-pages.sh")
        status = rename.main(["test-pages.sh", "-to",
                              "engine/plain/TEST/test-pages.sh", "--dont-ask",
                              "--directory=%s" % page], write=_said)
        print("status: %s" % status.name)
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
        title      = "hwut.sanitize --relations, and the faces that "
                     "follow a test",
        choice_map = {
            "propose": run_propose,
            "apply":   run_apply,
            "command": run_command,
            "move":    run_move,
            "remove":  run_remove,
        },
    ).run()
