#! /usr/bin/env python3
#
# @hwut {
#     title      = "Refresh: the provisioning steps each engine executes (E-122)"
#     choices    = ["accept", "diff", "interactive"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ENGINES, NOT THE FACES -- the function each face runs to hold a
         current candidate before it works on it:

    accept       'services/accept.py refresh_cases'
    interactive  'services/lib/accept/interactive.py keys_of'
    diff         'services/lib/run/diff.py keys_of'

         Each is driven through the same circumstances, in a fresh scratch
         tree each time, for an application that needs NO build (a bash
         script) and one that does (a C program, built by 'make'):

    absent        nothing changed, but no candidate stands
    present       nothing changed, and the candidate stands
    source        the source changed after the candidate was recorded

         THE ONLY THING OBSERVED IS WHICH PROVISIONING STEPS WERE EXECUTED,
         by what they leave behind: the Makefile's recipe appends a line to
         'compile.log' when it compiles, and each application appends one
         to 'run.log' when it runs. Neither log is written by anything but
         the step itself. The steps ruled (E-40's REFRESH, E-122):

                          no build            build ('make' decides)
    absent                run                 compiled?-no, run
    present               -                   compiled-no, no run
    source                run                 compiled, run

         'build invoked' is not observable apart from 'compiled' where
         'make' finds nothing to do -- 'make' deciding is the ruling (B.1),
         and what it decided is what the log shows.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ENV  = dict(os.environ, PYTHONPATH=os.path.dirname(ROOT))

SCRIPT = ('#!/bin/bash\n'
          '# @hwut { title = "I"  choices = ["c"] }\n'
          'echo run >> "$(dirname "$0")/run.log"\n'
          'echo "interpreted $1"\n'
          'echo "<hwut-end>"\n')
PROGRAM = ('/* @hwut { title = "B"  choices = ["c"]\n'
           '           build { framework = "make"  executable = "app" } } */\n'
           '#include <stdio.h>\n'
           '#include <string.h>\n'
           'int main(int argc, char** argv) {\n'
           '    char path[4096]; char* slash;\n'
           '    strncpy(path, argv[0], sizeof(path) - 16); path[sizeof(path) - 16] = 0;\n'
           '    slash = strrchr(path, 47);\n'
           '    strcpy(slash ? slash + 1 : path, "../../run.log");\n'
           '    FILE* log = fopen(path, "a"); if (log) { fputs("run\\n", log); fclose(log); }\n'
           '    printf("built %s\\n<hwut-end>\\n", argc > 1 ? argv[1] : "-");\n'
           '    return 0;\n'
           '}\n')
MAKEFILE = ('app: ../../test-b.c\n'
            '\techo compiled >> ../../compile.log\n'
            '\tcc -o app ../../test-b.c\n')


def put(path, text, executable_f=False):
    """RETURN: None. 'text' is the file at 'path'."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as file_handle: file_handle.write(text)
    if executable_f: os.chmod(path, 0o755)


def age(path, second_n):
    """RETURN: None. 'path' was last modified 'second_n' seconds ago --
               so no clock's granularity can decide what is younger."""
    moment = time.time() - second_n
    os.utime(path, (moment, moment))


def tree_of(built_f):
    """
    RETURN: (str, str, str), the scratch root, its TEST directory, and the
            application's file name -- accepted once, through the face
            ('hwut.accept --force'), so a candidate and a nominal stand.
    """
    root = tempfile.mkdtemp(prefix="vut_refresh_")
    test = os.path.join(root, "suite", "TEST")
    put(os.path.join(root, "hwut-root.conf"), "hwut {\n}\n")
    put(os.path.join(test, "hwut.conf"),
        'hwut {\n    ignore = ["run.log", "compile.log"]\n}\n')
    if built_f:
        name = "test-b.c"
        put(os.path.join(test, name), PROGRAM)
        put(os.path.join(test, "BUILD", name, "Makefile"), MAKEFILE)
    else:
        name = "test-i.sh"
        put(os.path.join(test, name), SCRIPT, executable_f=True)
    subprocess.run([sys.executable, "-m", "vut.services.accept",
                    "--directory=%s" % test, "--force", "--dont-ask"],
                   cwd=root, env=ENV, capture_output=True, text=True)
    return root, test, name


def prepared(circumstance, built_f):
    """RETURN: (str, str), the root and TEST directory of a scratch tree
               put in the circumstance -- the logs emptied last."""
    root, test, name = tree_of(built_f)
    candidate = os.path.join(test, "OUT", name + "--c.txt")
    source    = os.path.join(test, name)
    built     = os.path.join(test, "BUILD", name, "app")
    for path in (source, built):
        if os.path.exists(path): age(path, 120)
    if os.path.exists(candidate): age(candidate, 60)
    if circumstance == "absent":
        os.remove(candidate)
    elif circumstance == "source":
        with open(source, "a") as file_handle:
            file_handle.write("\n" if built_f else "# edited\n")
    for log in ("run.log", "compile.log"):
        path = os.path.join(test, log)
        if os.path.exists(path): os.remove(path)
    return root, test


def engine_run(engine, test):
    """RETURN: None. The engine, over the scratch TEST directory, as its
               face runs it; what it says is not observed."""
    from vut.engine.orchestrator.plan.wish import parse_wish
    from vut.services._cases              import select
    silent = lambda text: None                                 # noqa: E731
    wish, _ = parse_wish([])
    selected, _ = select(wish, [], test, True, silent, "")
    if engine == "accept":
        from vut.services import accept
        for where in selected.where_list:
            accept.refresh_cases(selected.whole(where),
                                 selected.found.result_db[where],
                                 selected.found.bookkeeper_db[where],
                                 selected.case_db[where], False, silent)
    elif engine == "interactive":
        from vut.services.lib.accept import interactive
        interactive.keys_of(selected, silent)
    else:
        from vut.services.lib.run import diff
        diff.keys_of(selected, silent)


def count(path):
    """RETURN: int, the lines of the log at 'path'; 0 where none stands."""
    if not os.path.exists(path): return 0
    with open(path) as file_handle: return len(file_handle.read().splitlines())


EXPECTED_DB = {("absent",  False): (0, 1), ("absent",  True): (0, 1),
               ("present", False): (0, 0), ("present", True): (0, 0),
               ("source",  False): (0, 1), ("source",  True): (1, 1)}


def test_engine(engine):
    print("-- the engine of '%s': the steps executed" % engine)
    print("   %-9s %-9s %-9s %-5s" % ("", "build", "compiled", "ran"))
    ok_f = True
    for circumstance in ("absent", "present", "source"):
        for built_f in (False, True):
            root, test = prepared(circumstance, built_f)
            try:
                engine_run(engine, test)
                compiled = count(os.path.join(test, "compile.log"))
                ran      = count(os.path.join(test, "run.log"))
            finally:
                shutil.rmtree(root, ignore_errors=True)
            expected = EXPECTED_DB[(circumstance, built_f)]
            right_f  = (compiled, ran) == expected
            ok_f     = ok_f and right_f
            print("   %-9s %-9s %-9s %-5s %s"
                  % (circumstance, "make" if built_f else "none",
                     "-" if not built_f else ("yes" if compiled else "no"),
                     "yes" if ran else "no",
                     "" if right_f else "  WRONG: expected compiled %i, ran %i"
                                        % expected))
    print("SUCCESS" if ok_f else "FAILURE")


choice = sys.argv[1] if len(sys.argv) > 1 else "accept"
if choice not in ("accept", "diff", "interactive"):
    print("no such choice: %s" % choice)
    sys.exit(1)
test_engine(choice)

#  THE STREAM COMPLETED (R-70).
print("<hwut-end>")
