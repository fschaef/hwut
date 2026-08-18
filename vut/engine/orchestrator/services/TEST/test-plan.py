#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.plan' FACE -- the test plan the framework intends.

The face is driven through 'main(argv, write)', so what is shown is the
face itself and no process stands between. The directory is stated with
'--directory='; its path is machine-chosen and never printed. The base
questions ('--fail', '--since=', ...) read the directory's own result
base; a base is not laid here, so the wish choices below use globs --
the base questions have their suite in plan/TEST/test-wish.py.

CHOICES: plan, wish, faults, refused, help;

DESCRIPTION:

plan       the plan of everything: nodes, links, the exclusion set,
           the implication marking.

wish       globs reaching the plan; a glob matching nothing -- an
           empty plan and a report, status 0.

faults     a broken header: the fault prints, the plan of what stands
           follows, the status is 1.

refused    an unreadable point, '--fail' beside '--pass', an unknown
           argument: refused at the door, by name. A glob matching
           nothing is NOT among them -- it reports (see 'wish').

help       '--help' answers the full documentation and status 0.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.services.plan import main


FILE_DB = {
    "hwut.conf":   'hwut {\n'
                   '    collision  = ["test-net.py", "test-a.py two"]\n'
                   '    dependency { "test-b.py" = ["test-a.py one"] }\n'
                   '}\n',
    "test-a.py":   '# hwut { title = "A"  build = "make"\n'
                   '#        choices = ["one", "two"] }\n',
    "test-b.py":   '# hwut { title = "B" }\n',
    "test-net.py": '# hwut { title = "Net" }\n',
}


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def build_directory(extra_db=None):
    """
    RETURN: str, a directory holding FILE_DB and whatever 'extra_db'
            adds, for the caller to remove.
    """
    directory = tempfile.mkdtemp(prefix="vut_plan_")
    for name, content in dict(FILE_DB, **(extra_db or {})).items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return directory


def call(directory, argument_list):
    """
    RETURN: None. Shows the command line as an author writes it -- an
            argument carrying a blank in the quotes it needs -- the
            lines the face writes, and the exit status.
    """
    quoted = " ".join('"%s"' % text if " " in text else text
                      for text in argument_list)
    print("$ hwut.plan%s" % (" " + quoted if quoted else ""))
    line_list = []
    status    = main(argument_list + ["--directory=%s" % directory],
                     line_list.append)
    for line in line_list:
        for piece in str(line).split("\n"):
            print("    %s" % piece if piece else "")
    print("    [status %d]" % status)


def test_plan():
    """RETURN: None. The plan of everything."""
    directory = build_directory()
    try:
        banner("the plan of everything")
        call(directory, [])

        banner("implication: 'test-b.py' pulls in what it requires")
        call(directory, ["--glob", "test-b.py"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_wish():
    """RETURN: None. Globs reaching the plan."""
    directory = build_directory()
    try:
        banner("two globs: OR'ed")
        call(directory, ["--glob", "test-net.py", "--glob", "test-b.py"])

        banner("a glob matching nothing: an empty plan, reported")
        call(directory, ["--glob", "test-*.pt"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_faults():
    """RETURN: None. A broken header beside sound ones."""
    directory = build_directory(
        {"test-broken.py": '# hwut { title = "Broken"  numeric = yes }\n'})
    try:
        banner("the fault prints; the plan of what stands follows")
        call(directory, [])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_refused():
    """RETURN: None. What the command line cannot mean."""
    directory = build_directory()
    try:
        banner("an unreadable point")
        call(directory, ["--since=noon"])

        banner("'--fail' beside '--pass'")
        call(directory, ["--fail", "--pass"])

        banner("an argument the face does not take")
        call(directory, ["test-a.py"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_help():
    """RETURN: None. The documentation, on demand."""
    directory = build_directory()
    try:
        banner("--help")
        call(directory, ["--help"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "hwut.plan: the test plan the framework intends;", {
        "plan":    test_plan,
        "wish":    test_wish,
        "faults":  test_faults,
        "refused": test_refused,
        "help":    test_help,
    }).run()
