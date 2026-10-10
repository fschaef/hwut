#! /usr/bin/env python3
#  @hwut {
#    title   = "hwut.report.features"
#    choices = ["empty", "outside", "refused", "test_directory", "tree"]
#  }
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.report.features' -- the page of a tree: component, part,
         feature, test runs and their verdicts.

CHOICES: tree, test_directory, outside, empty, refused;

DESCRIPTION:

    tree            called at the root: every component with its id,
                    counts and statements, every feature with its state
                    and its linked runs; then what stands outside --
                    where 'parent' and 'childs' disagree with the
                    directories included.
    test_directory  called inside a TEST directory: that directory is
                    the whole page, addressed as '.'.
    outside         a tree where nothing is linked and no statement
                    stands: no feature, and every directory named.
    empty           a tree without a TEST directory: said as EMPTY,
                    status 3.
    refused         a directory that does not stand, a tree no root
                    bounds, and an unknown word.

NOTHING IS RUN. The fixture's verdicts are written by the bookkeeper,
so the page measures the reading of 'GOOD/book.csv' and nothing about
the machine.
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile

import config                                                       # noqa: F401

from   vut.engine.bookkeeper.api         import Bookkeeper
from   vut.services.lib.report           import features
from   vut.services.lib.face             import record_check
from   vut.test_writing_support.python.hwut_runner import HwutRunner


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def _test(root, path, body):
    """RETURN: None. Writes a shell test at 'root/path' whose block
    holds the lines of 'body'."""
    _write(root, path, "#! /bin/sh\n# @hwut {\n%s\n# }\necho x\n"
           % "\n".join("#     " + line for line in body))
    os.chmod(os.path.join(root, path), 0o755)


def fixture(root):
    """RETURN: None. A tree of two components with statements, one
    without, and the verdicts of their runs."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "hwut-composition.conf",
           'component {\n'
           '    id     = "all"\n'
           '    title  = "All"\n'
           '    childs { eng = "Runs and judges."  old = "Was here once." }\n'
           '}\n')
    _write(root, "engine/hwut-composition.conf",
           'component {\n'
           '    id     = "eng"\n'
           '    title  = "Engine"\n'
           '    does   = "Runs tests and judges them."\n'
           '    parent = "all"\n'
           '    childs { cmp = "Gives the verdict." }\n'
           '}\n')
    _write(root, "engine/compare/hwut-composition.conf",
           'component {\n'
           '    id     = "cmp"\n'
           '    title  = "Compare"\n'
           '    does   = "Decides whether an output is equivalent to its nominal."\n'
           '    parent { eng = "The engine\'s verdict rests on it." }\n'
           '    childs {\n'
           '        core      = "Aligns two streams line by line."\n'
           '        cmp-proof = "Proves the whole comparison on real pages."\n'
           '    }\n'
           '}\n')
    _write(root, "engine/compare/core/hwut-composition.conf",
           'component {\n'
           '    id     = "core"\n'
           '    title  = "Core"\n'
           '    does   = "Pairs lines."\n'
           '    parent { cmp = "Alignment is what compare shows." }\n'
           '    owner  = "nobody"\n'
           '}\n')
    _write(root, "engine/compare/core/TEST/hwut-features.conf",
           'features {\n'
           '    parent { core = "What \'core\' promises, proven." }\n'
           '    issued = 3\n'
           '    1 { name  = "line-pairing"\n'
           '        title = "Two streams are aligned line by line." }\n'
           '    2 { name  = "missing-side"\n'
           '        title = "A line present on one side only is shown whole." }\n'
           '    3 { name  = "untested" }\n'
           '    fresh { name = "not-numbered" }\n'
           '}\n')
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n'
           '    id     = "cmp-proof"\n'
           '    parent = "cmp"\n'
           '    issued = 2\n'
           '    1 { name = "whole-page"  title = "A whole page is judged." }\n'
           '    2 { name = "never-run"   title = "Linked, and not in the book." }\n'
           '}\n')
    _test(root, "engine/compare/core/TEST/test-pair.sh",
          ['title    = "Pairing"', 'features = ["line-pairing"]',
           'choices {', '    plain { }',
           '    gap   { features = ["line-pairing", "missing-side"] }',
           '    odd   { features = [] }', '}'])
    _test(root, "engine/compare/core/TEST/test-stray.sh",
          ['title    = "Stray"', 'features = ["no-such"]'])
    _test(root, "engine/compare/TEST/test-pages.sh",
          ['title    = "Pages"', 'features = ["whole-page"]',
           'choices = ["small", "large"]'])
    _test(root, "engine/compare/TEST/test-fresh.sh",
          ['title    = "Fresh"', 'features = ["never-run"]'])
    _test(root, "engine/plain/TEST/test-plain.sh", ['title = "Plain"'])

    core = Bookkeeper(os.path.join(root, "engine/compare/core/TEST"))
    core.note_accept("test-pair.sh", "plain")
    core.note_accept("test-pair.sh", "gap", equivalent_f=False)
    page = Bookkeeper(os.path.join(root, "engine/compare/TEST"))
    page.note_accept("test-pages.sh", "small")
    page.note_accept("test-pages.sh", "large")


def _in_tree(build, function):
    """RETURN: None. Calls 'function()' with the cwd at the root of a
    fresh tree that 'build(root)' filled; removes the tree afterwards."""
    ground = tempfile.mkdtemp(prefix="hwut-features-")
    root   = os.path.join(ground, "tree")
    here   = os.getcwd()
    try:
        os.makedirs(root)
        build(root)
        os.chdir(root)
        function()
    finally:
        os.chdir(here)
        shutil.rmtree(ground, ignore_errors=True)


def _page(argv):
    """RETURN: None. Prints the face's page for 'argv', and its
    status."""
    status = features.main(argv, write=lambda text: print("    %s" % text))
    print("status: %s" % status.name)


def run_tree():
    """RETURN: None. The page of the whole tree, and its record."""
    def body():
        banner("hwut.report.features")
        _page([])
        banner("the same tree, as a record")
        result = features.do(features.Request("."))
        print("    counts: %s" % ", ".join("%s=%i" % pair
                                         for pair in result.count_tuple))
        print("    not plain: %s" % (record_check(result) or "nothing"))
        banner("--directory=engine/compare: paths from there")
        _page(["--directory=engine/compare"])
    _in_tree(fixture, body)


def run_test_directory():
    """RETURN: None. The page asked inside one TEST directory."""
    def body():
        os.chdir("engine/compare/core/TEST")
        banner("called inside engine/compare/core/TEST")
        _page([])
    _in_tree(fixture, body)


def run_outside():
    """RETURN: None. A tree with tests and no statement at all."""
    def build(root):
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _test(root, "a/TEST/test-a.sh", ['title = "A"'])
        _test(root, "a/b/TEST/test-b.sh",
              ['title = "B"', 'features = ["wanted"]'])
    def body():
        banner("no feature file, no composition file")
        _page([])
    _in_tree(build, body)


def run_empty():
    """RETURN: None. A tree that holds no TEST directory."""
    def build(root):
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _write(root, "a/hwut-composition.conf",
               'component { title = "A" }\n')
    def body():
        banner("no TEST directory below")
        _page([])
    _in_tree(build, body)


def run_refused():
    """RETURN: None. What the face does not take."""
    def body():
        banner("a directory that does not stand")
        _page(["--directory=nowhere"])
        banner("an unknown word")
        _page(["--verbose"])
    _in_tree(fixture, body)
    def rootless(root):
        _test(root, "a/TEST/test-a.sh", ['title = "A"'])
    def unbounded():
        banner("a tree no 'hwut-root.conf' bounds")
        status = features.main([], write=lambda text: print(
            "    %s" % text.replace(os.getcwd(), "<tree>")))
        print("status: %s" % status.name)
    _in_tree(rootless, unbounded)


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.report.features",
        choice_map = {
            "tree":           run_tree,
            "test_directory": run_test_directory,
            "outside":        run_outside,
            "empty":          run_empty,
            "refused":        run_refused,
        },
    ).run()
