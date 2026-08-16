#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: DETERMINATION -- a wish and a directory turned into a plan,
         shown through the canonical print.

CHOICES: whole, closure, pruned, empty, misdep, deterministic;

DESCRIPTION:

whole    the whole directory: builds, a session, ordering links out of
         'dependency', the collision group as an exclusion set.

closure  a wish naming ONE dependant: what it requires enters the plan
         by implication, marked with the target that required it, and
         the implication runs to a fixed point through a chain.

pruned   a wish naming part of a collision group: a group left with one
         member constrains nothing and is dropped; a group keeping two
         stands.

empty    a wish matching nothing: an empty plan and a report, not a
         refusal.

misdep   an unsatisfiable case: marked in the plan, its dependant
         likewise, and the ordering link between them stands while a
         link out of the closure is never offered.

deterministic  the same wish on the same directory, determined ten
         times: one print, byte for byte.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.explorer        import explore
from vut.engine.orchestrator.exploration.task_list_query import \
                                                         CTestTaskListQuery
from vut.engine.orchestrator.plan.determine import determine
from vut.engine.orchestrator.plan.printer   import print_plan
from vut.engine.orchestrator.plan.wish      import Wish


CONF = ('hwut {\n'
        '    collision  = ["test-net.py", "test-port.py two"]\n'
        '    dependency { "test-b.py"     = ["test-a.py one"]\n'
        '                 "test-c.py"     = ["test-b.py"]\n'
        '                 "test-lost.py"  = ["test-ghost.py"]\n'
        '                 "test-heir.py"  = ["test-lost.py"] }\n'
        '}\n')

FILE_DB = {
    "hwut.conf":     CONF,
    "test-a.py":     '# hwut { title = "A"  build = "make"\n'
                     '#        choices = ["one", "two"] }\n',
    "test-b.py":     '# hwut { title = "B" }\n',
    "test-c.py":     '# hwut { title = "C" }\n',
    "test-i.py":     '# hwut { title = "I"  interactive = yes\n'
                     '#        choices = ["x", "y"] }\n',
    "test-net.py":   '# hwut { title = "Net" }\n',
    "test-port.py":  '# hwut { title = "Port"  choices = ["one", "two"] }\n',
    "test-lost.py":  '# hwut { title = "Lost" }\n',
    "test-heir.py":  '# hwut { title = "Heir" }\n',
}


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def build_directory():
    """
    RETURN: [0] CTestAppSet  the directory of FILE_DB, explored.
            [1] str          the directory, for the caller to remove.
    """
    directory = tempfile.mkdtemp(prefix="vut_determine_")
    for name, content in FILE_DB.items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return explore(directory).app_set, directory


def determined(app_set, wish):
    """RETURN: None. Prints the wish, the reports and the plan."""
    plan, report_list = determine(app_set,
                                  CTestTaskListQuery(wish))
    print("WISH: %s" % wish)
    for report in report_list:
        print("REPORT: %s" % report)
    print_plan(plan)


def test_whole():
    """RETURN: None. The whole directory."""
    app_set, directory = build_directory()
    try:
        banner("everything the directory offers")
        determined(app_set, Wish())
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_closure():
    """RETURN: None. Implication, marked, to a fixed point."""
    app_set, directory = build_directory()
    try:
        banner("'test-b.py' alone: 'test-a.py one' enters by implication")
        determined(app_set, Wish(glob_tuple=("test-b.py",)))

        banner("'test-c.py' alone: the chain runs to its end")
        determined(app_set, Wish(glob_tuple=("test-c.py",)))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_pruned():
    """RETURN: None. A collision group pruned to the plan."""
    app_set, directory = build_directory()
    try:
        banner("both members stand: the group stands")
        determined(app_set, Wish(glob_tuple=("test-net.py",
                                             "test-port.py *")))

        banner("one member stands: the group constrains nothing")
        determined(app_set, Wish(glob_tuple=("test-net.py",)))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_empty():
    """RETURN: None. A wish matching nothing."""
    app_set, directory = build_directory()
    try:
        banner("a glob matching nothing")
        determined(app_set, Wish(glob_tuple=("test-*.pt",)))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_misdep():
    """RETURN: None. Unsatisfiable cases in the plan."""
    app_set, directory = build_directory()
    try:
        banner("'test-lost.py' names a target the directory lacks")
        determined(app_set, Wish(glob_tuple=("test-lost.py",
                                             "test-heir.py")))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_deterministic():
    """RETURN: None. Ten determinations, one print."""
    app_set, directory = build_directory()
    try:
        text_set = set()
        line_list = []
        for _ in range(10):
            plan, _report = determine(app_set, CTestTaskListQuery(Wish()))
            line_list = []
            print_plan(plan, line_list.append)
            text_set.add("\n".join(line_list))
        banner("ten determinations of one directory")
        print("    distinct prints: %d" % len(text_set))
        print("    lines of the one print: %d" % len(line_list))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Determination: a wish and a directory become a plan;", {
        "whole":         test_whole,
        "closure":       test_closure,
        "pruned":        test_pruned,
        "empty":         test_empty,
        "misdep":        test_misdep,
        "deterministic": test_deterministic,
    }).run()
