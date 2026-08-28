#! /usr/bin/env python3
#
# @hwut {
#     title      = "Task list: select, or refuse at the door"
#     choices    = ["all", "named", "refused"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: SELECT -- 'get_test_cases(CTestAppSet) -> CTestCaseSequence',
         the whole interface; and refusal at the door, by name.

CHOICES: all, named, refused;

DESCRIPTION:

all      every choice of every application; files sorted, choices
         sorted within a file; the choice-less application yields its
         single 'None' case. A case whose dependencies cannot be met
         is SELECTED and carries '[MISDEP]' -- it is reported, not
         silently dropped.

named    a stated subset: whole files and single choices; the sequence
         carries exactly what was named, resolved records attached.

refused  a wish naming an application or a choice that does not exist:
         SelectionError, stating the name AND what the set offers.
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.explorer         import explore
from vut.engine.orchestrator.exploration.task_list        import (CTestTaskListAll,
                                                     CTestTaskListNamed,
                                                     SelectionError)


def stated(record):
    """RETURN: str, a record's STATED fields only -- 'None' is absence
    and absence prints nothing; '-' where nothing at all is stated."""
    if record is None: return "-"
    text_list = ["%s=%r" % (name, getattr(record, name))
                 for name in record.__dataclass_fields__
                 if getattr(record, name) is not None]
    return "{%s}" % " ".join(text_list) if text_list else "-"


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def build_app_set():
    """RETURN: [0] CTestAppSet  three applications, mixed shapes.
               [1] str          the directory, for the caller to remove.
    """
    directory = tempfile.mkdtemp(prefix="vut_select_")
    file_db = {
        "hwut.conf": 'hwut {\n'
                     '    dependency { "test-c.py y" = ["test-z.py"] }\n'
                     '}\n',
        "test-a.py": '# @hwut {\n#     title   = "A"\n'
                     '#     numeric = 0.01\n'
                     '#     caps    { timeout_sec = 30  network = false }\n'
                     '#     choices { one { }\n'
                     '#               two { numeric = 0.05\n'
                     '#                     caps { timeout_sec = 5 } } }\n'
                     '# }\n',
        "test-b.sh": '# @hwut { title = "B" }\n',
        "test-c.py": '# @hwut {\n#     title   = "C"\n'
                     '#     choices = [\"x\", \"y\"]\n# }\n',
    }
    for name, content in file_db.items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    result = explore(directory)
    return result.app_set, directory


def show(sequence):
    """RETURN: None. Prints a CTestCaseSequence."""
    print("%d cases:" % len(sequence))
    for case in sequence:
        choice = "-" if case.choice is None else case.choice
        print("    %-10s %-5s numeric=%-6r caps=%-40s %s"
              % (case.source_file, choice, case.parameters.numeric,
                 stated(case.parameters.caps), case.token()))


def test_all():
    """RETURN: None. Everything."""
    banner("all")
    app_set, directory = build_app_set()
    try:     show(CTestTaskListAll().get_test_cases(app_set))
    finally: shutil.rmtree(directory, ignore_errors=True)


def test_named():
    """RETURN: None. Whole file and single choice."""
    banner("named: all of test-a.py, only 'y' of test-c.py")
    app_set, directory = build_app_set()
    try:
        task = CTestTaskListNamed({"test-a.py": None,
                                   "test-c.py": ["y"]})
        show(task.get_test_cases(app_set))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_refused():
    """RETURN: None. Unknown file; unknown choice."""
    app_set, directory = build_app_set()
    try:
        banner("an application that does not exist")
        try:
            CTestTaskListNamed({"test-z.py": None}).get_test_cases(app_set)
        except SelectionError as error:
            print("REFUSED: %s" % error)
        banner("a choice that does not exist")
        try:
            CTestTaskListNamed({"test-a.py": ["three"]}) \
                .get_test_cases(app_set)
        except SelectionError as error:
            print("REFUSED: %s" % error)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Task list: select, or refuse at the door;", {
        "all":     test_all,
        "named":   test_named,
        "refused": test_refused,
    }).run()
