#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'execute' (R-68) -- the call itself, stated verbatim.

CHOICES: stated, refused;

DESCRIPTION:

stated   'execute' at the root and inside a choice, the R-26 merging;
         '$file', '$choice' and '$filestem' pass validation.

refused  an unknown '$word' named at validation; 'execute' beside
         'interactive' refused at resolution -- the file yields no
         application.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.explorer import explore


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def explored(file_db):
    """
    RETURN: ExplorationResult of a directory holding 'file_db', the
            directory removed before the answer stands.
    """
    directory = tempfile.mkdtemp(prefix="vut_execute_")
    try:
        for name, content in file_db.items():
            with open(os.path.join(directory, name), "w") as fh:
                fh.write(content)
        return explore(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_stated():
    """RETURN: None. The parameter, root and per-choice."""
    result = explored({
        "test-awk.py": '# hwut {\n'
                       '#     title   = "Awk"\n'
                       '#     execute = "awk -f $file -v c=$choice"\n'
                       '#     choices { one { }\n'
                       '#               two { execute = '
                       '"awk -f $filestem.aux" } }\n'
                       '# }\n'})
    banner("root word holds; the choice's own word wins")
    for app in result.app_set:
        for choice in sorted(app.choice_db):
            print("    %-12s %-6s execute=%r"
                  % (app.source_file, choice,
                     app.choice_db[choice].execute))
    print("    faults: %d" % len(result.fault_list))


def test_refused():
    """RETURN: None. The two refusals, by name."""
    banner("an unknown '$word'")
    result = explored({
        "test-a.py": '# hwut { title = "A"\n'
                     '#        execute = "run $file --tag=$version" }\n'})
    for fault in result.fault_list:
        print("    %s" % fault)
    print("    applications: %d" % len(result.app_set.app_db))

    banner("'execute' beside 'interactive'")
    result = explored({
        "test-i.py": '# hwut { title = "I"  interactive = yes\n'
                     '#        execute = "awk -f $file"\n'
                     '#        choices = ["x"] }\n'})
    for fault in result.fault_list:
        print("    %s" % fault)
    print("    applications: %d" % len(result.app_set.app_db))


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "'execute': the call itself, stated verbatim;", {
        "stated":  test_stated,
        "refused": test_refused,
    }).run()
