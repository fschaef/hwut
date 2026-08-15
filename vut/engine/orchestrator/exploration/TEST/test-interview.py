#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE THIRD CARRIER. A file that neither carrier speaks for is
         interviewed -- 'app --hwut-info' -- and its answer is read as a
         specification. It is the migration path: an hwut 1.0 test
         application carries no 'hwut' trigger, because it predates the
         trigger.

CHOICES: block, silence, directory, precedence;

DESCRIPTION:

block       every line 'HwutRunner' emits, read into a specification:
            the title, 'CHOICES:', 'HAPPY:' (zero or more), 'SAME;' and
            'INTERACTIVE;'. A choice-less application emits no
            'CHOICES:' line and yields the single 'None' choice. A line
            the block carries beyond these is passed over in silence.

silence     every way of failing to be a test application yields no
            specification and NO FAULT: an answer that is no block, an
            empty answer, and a runner reporting that the file did not
            answer at all.

directory   a 1.0 application beside a modern one: both explore, the
            first through the interview, the second through its header.
            The origin says which is which.

precedence  the interview is reached ONLY where both carriers are
            silent. A file carrying a header is never run to be read,
            and neither is a file named under 'apps'.

The runner is a parameter here: what is under test is the reading of the
answer and the place of the interview in the order, not the running of a
process. The procsitter call is owed at integration
(DISCUSSIONS/todo-3-hwut-info-hints.txt).
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.orchestrator.exploration.hwut_info_interview import (specification_of,
                                                        INTERVIEW_CAPS)
from vut.engine.orchestrator.exploration.explorer            import explore


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def show(spec):
    """RETURN: None. Prints what an interview yielded."""
    if spec is None:
        print("not a test application")
        return
    print("title '%s'  origin %s" % (spec.title, spec.origin.name))
    stated = ["%s=%r" % (name, getattr(spec.root_parameters, name))
              for name in spec.root_parameters.__dataclass_fields__
              if getattr(spec.root_parameters, name) is not None]
    print("root: %s" % ("  ".join(stated) if stated else "(nothing)"))
    print("choices: %s"
          % ", ".join("-" if c is None else c
                      for c in sorted(spec.choice_db,
                                      key=lambda c: (c is None, c or ""))))


def test_block():
    """RETURN: None. Every line the info block carries."""
    banner("a full block")
    show(specification_of("My Title;\n"
                          "CHOICES: alpha, beta;\n"
                          "HAPPY: [0-9]+;\n"
                          "HAPPY: 0x[0-9a-f]+;\n"
                          "SAME;\n"
                          "INTERACTIVE;\n", "otto-von-bismarck.bas"))

    banner("a choice-less application")
    show(specification_of("Solitary;\nINTERACTIVE;\n", "old.sh"))

    banner("the least a block can be")
    show(specification_of("Bare;\n", "old.sh"))

    banner("a line beyond the block is passed over in silence")
    show(specification_of("My Title;\n"
                          "CHOICES: one;\n"
                          "FUTURE-KEYWORD: whatever;\n"
                          "warning: deprecated flag\n"
                          "INTERACTIVE;\n", "old.bas"))


def test_silence():
    """RETURN: None. Failing to be a test application is not a fault."""
    banner("an answer that is no block")
    show(specification_of("bash: --hwut-info: unknown option\n", "x.sh"))

    banner("an empty answer")
    show(specification_of("", "x.sh"))

    banner("keywords but no title")
    show(specification_of("CHOICES: one, two;\nSAME;\n", "x.sh"))


def test_directory():
    """RETURN: None. A 1.0 application beside a modern one."""
    banner("both explore; the origin says which carrier spoke")
    directory = tempfile.mkdtemp(prefix="vut_interview_")
    file_db = {
        "otto-von-bismarck.bas": "REM an hwut 1.0 test application\n",
        "test-modern.py":        '# hwut { title = "modern" }\n',
        "not-a-test.dat":        "just data\n",
    }
    for name, content in file_db.items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)

    answer_db = {
        "otto-von-bismarck.bas": "Iron and Blood;\n"
                                 "CHOICES: one, two;\n"
                                 "SAME;\nINTERACTIVE;\n",
    }

    def runner(path, caps):
        """RETURN: str, the answer of 'path'; None where it does not
        answer. Caps are shown once, so what an interview permits is
        visible."""
        return answer_db.get(os.path.basename(path))

    try:
        print("interview caps: %r" % (INTERVIEW_CAPS,))
        result = explore(directory, interview_runner=runner)
        for app in result.app_set:
            print("%-24s %-9s '%s'  choices: %s"
                  % (app.source_file, app.origin.name, app.title,
                     ", ".join("-" if c is None else c
                               for c in sorted(app.choice_db,
                                               key=lambda c: (c is None,
                                                              c or "")))))
        for fault in result.fault_list:
            print("FAULT %s" % fault)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_precedence():
    """RETURN: None. The interview is the LAST resort."""
    banner("a header-carrying file and an 'apps' entry are never run")
    directory = tempfile.mkdtemp(prefix="vut_interview_")
    file_db = {
        "test-header.py": '# hwut { title = "header speaks" }\n',
        "legacy.bas":     "REM named under apps\n",
        "hwut.conf":      'hwut {\n'
                          '    apps { legacy.bas { title = "conf speaks" } }\n'
                          '}\n',
    }
    for name, content in file_db.items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)

    asked_list = []

    def runner(path, caps):
        """RETURN: None. Records who was asked; answers nothing."""
        asked_list.append(os.path.basename(path))
        return None

    try:
        result = explore(directory, interview_runner=runner)
        for app in result.app_set:
            print("%-16s %s  '%s'"
                  % (app.source_file, app.origin.name, app.title))
        print("interviewed: %s" % (sorted(asked_list) or "nobody"))
        for fault in result.fault_list:
            print("FAULT %s" % fault)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "The interview: hwut 1.0 answers, and is read;", {
        "block":      test_block,
        "silence":    test_silence,
        "directory":  test_directory,
        "precedence": test_precedence,
    }).run()
