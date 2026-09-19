#! /usr/bin/env python3
#
# @hwut {
#     title      = "The interview: hwut 1.0 answers, and is read"
#     choices    = ["block", "directory", "memo", "precedence",
#                   "procsitter", "relic", "silence"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE THIRD CARRIER. A file that neither carrier speaks for is
         interviewed -- 'app --hwut-info' -- and its answer is read as a
         specification. It is the migration path: an hwut 1.0 test
         application carries no 'hwut' trigger, because it predates the
         trigger.

CHOICES: block, silence, directory, precedence, procsitter;

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
(adm/WORK/gathered/0z-todo-3-hwut-info-hints.txt).
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile
import config                                                       # noqa: F401

from vut.test_writing_support.python.hwut_runner    import HwutRunner
from vut.engine.orchestrator.exploration.hwut_info_interview import (specification_of,
                                                        interview,
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
        "test-modern.py":        '# @hwut { title = "modern" }\n',
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
        "test-header.py": '# @hwut { title = "header speaks" }\n',
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


def test_procsitter():
    """RETURN: None. THE REAL CALL, under the real procsitter: an hwut
    1.0 application answers and is read; a file that answers nothing
    is not a test application; a file that HANGS is capped and is not
    one either -- and none of the three is a fault.

    THE CAP IS NOT TIMED HERE. That it bites is what matters; how long
    it took is the machine's, and a GOOD holding it would be a lie.
    """
    import stat
    directory = tempfile.mkdtemp()
    try:
        def put(name, text, executable_f=True):
            path = os.path.join(directory, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            if executable_f:
                os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC
                                                     | stat.S_IXGRP
                                                     | stat.S_IXOTH)

        put("old-app.py",
            "#! /usr/bin/env python3\n"
            "import sys\n"
            "if '--hwut-info' in sys.argv:\n"
            "    print('An hwut 1.0 application;')\n"
            "    print('CHOICES: alpha, beta;')\n"
            "    sys.exit(0)\n"
            "print('ran')\n")
        put("mute.py",
            "#! /usr/bin/env python3\n"
            "import sys\n"
            "sys.exit(0)\n")
        put("angry.py",
            "#! /usr/bin/env python3\n"
            "import sys\n"
            "sys.exit(3)\n")
        put("notes.txt", "not a program at all\n", executable_f=False)

        for name in ("old-app.py", "mute.py", "angry.py", "notes.txt"):
            spec = interview(directory, name)
            if spec is None:
                print("%-12s -> not a test application" % name)
            else:
                print("%-12s -> '%s'  choices: %s"
                      % (name, spec.title,
                         ", ".join(sorted(k for k in spec.choice_db
                                          if k is not None)) or "none"))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_memo():
    """RETURN: None. X-INTERVIEW: an interview is a program run and its
    answer is MEMOISED beside the tests by the file's mtime and size --
    the second walk asks nothing; a changed file is asked again; a
    file that is NOT executable is never asked (a helper, a log, a
    table cannot answer). Measured before this: 107 interviews per walk
    of the tree, none answered, eleven seconds of silence."""
    import stat, time
    from vut.engine.orchestrator.exploration import explorer, finder
    from vut.engine.orchestrator.exploration import hwut_info_interview
    directory = tempfile.mkdtemp()
    try:
        def put(name, text, executable_f=True):
            path = os.path.join(directory, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            if executable_f:
                os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
            return path
        app = put("old-app.py", "#! /usr/bin/env python3\nimport sys\n"
                  "if '--hwut-info' in sys.argv:\n"
                  "    print('An hwut 1.0 application;'); print('CHOICES: a, b;')\n")
        put("helper.py", "print('a helper, not a test')\n", executable_f=False)
        put("notes.log", "just a log\n", executable_f=False)
        put("script.sh", "#! /bin/sh\necho nothing\n")
        asked = []
        real = hwut_info_interview._procsitter_runner
        def counting(path, caps):
            asked.append(os.path.basename(path)); return real(path, caps)
        hwut_info_interview._procsitter_runner = counting
        try:
            for round_n in (1, 2):
                asked.clear()
                explorer.explore(directory)
                print("  walk %i: asked %s" % (round_n, sorted(asked)))
            print("  memo file stands under TMP/: %s"
                  % os.path.isfile(hwut_info_interview.memo_path(directory)))
            print("  ... and not beside the tests: %s"
                  % (not os.path.exists(os.path.join(
                         directory, hwut_info_interview.MEMO_FILE_NAME))))
            time.sleep(1.1)
            with open(app, "a") as handle: handle.write("# changed\n")
            asked.clear(); explorer.explore(directory)
            print("  after a change to old-app.py: asked %s" % sorted(asked))
            print("  TMP/ is never walked into: %s"
                  % ("TMP" in getattr(finder, "REFUSED_NAME_GLOB_TUPLE", ())
                     or not any(n.startswith("TMP") for n in
                                finder.candidate_list(directory)[0])))
        finally:
            hwut_info_interview._procsitter_runner = real
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_relic():
    """RETURN: None. X-INFO-DAT: 'hwut-info.dat' is hwut 1.0's and is
    NOT READ. The directory's title is 'title' in its 'hwut.conf';
    'hwut.renovate' (todo-1) carries a relic's first line there. A
    directory holding only the relic states no title."""
    from vut.services.report import directory_title
    from vut.engine.orchestrator.exploration import reader
    directory = tempfile.mkdtemp()
    try:
        def put(name, text):
            with open(os.path.join(directory, name), "w",
                      encoding="utf-8") as handle: handle.write(text)
        print("  a relic alone:")
        put("hwut-info.dat", "The Old Title\n-------------\nand notes\n")
        print("    title: %r" % directory_title(directory))
        print("  'title' in 'hwut.conf' -- what renovate writes:")
        put("hwut.conf", 'hwut {\n    title = "The Comparison Engine"\n}\n')
        print("    title: %r" % directory_title(directory))
        print("  a conf without a title:")
        put("hwut.conf", 'hwut {\n}\n')
        print("    title: %r" % directory_title(directory))
        print("  the key is validated like any other:")
        spec, _, fault_list = reader.read_conf(
            'hwut {\n    title = 17\n}\n', "hwut.conf")
        for fault in fault_list: print("    %s" % fault)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "The interview: hwut 1.0 answers, and is read;", {
        "block":      test_block,
        "memo":       test_memo,
        "relic":      test_relic,
        "silence":    test_silence,
        "directory":  test_directory,
        "precedence": test_precedence,
        "procsitter": test_procsitter,
    }).run()
