#! /usr/bin/env python3
#
# @hwut {
#     title      = "Refresh: the faces that read a recording execute no step (E-165)"
#     features   = ["accept-refresh"]
#     choices    = ["accept", "diff", "interactive"]
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ENGINES OF THE FACES THAT READ A RECORDING -- 'hwut.accept',
         'hwut.merge', 'hwut.diff' -- RUN NOTHING (services E-165, ruled
         2026-10-22: "the user accepts on recorded fixed output, not on
         content that might be produced in the background"):

    accept       'services/accept.py main' ('--force --dont-ask')
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
         the step itself. Ruled (E-165): no step, in any circumstance --
         the recording is made by 'hwut.play' or 'hwut.run' alone.

         MEASURED 2026-10-22 before (E-40's REFRESH, E-122): accept, diff
         and interactive ran where no candidate stood or the source was
         newer, and compiled where the source changed.
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
            application's file name -- recorded by 'hwut.play' and
            accepted through the face ('hwut.accept --force'), so a
            candidate and a nominal stand.
    """
    root = tempfile.mkdtemp(prefix="hwut_refresh_")
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
    subprocess.run([sys.executable, "-m", "hwut.services.lib.run.play",
                    name, "c", "--plain", "--directory=%s" % test],
                   cwd=root, env=ENV, capture_output=True, text=True)
    subprocess.run([sys.executable, "-m", "hwut.services.accept",
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
    from hwut.engine.orchestrator.plan.wish import parse_wish
    from hwut.services._cases import select
    silent = lambda text: None                                 # noqa: E731
    wish, _ = parse_wish([])
    selected, _ = select(wish, [], test, True, silent, "")
    if engine == "accept":
        from hwut.services import accept
        accept.main(["--directory=%s" % test, "--force", "--dont-ask"],
                    write=silent)
    elif engine == "interactive":
        from hwut.services.lib.accept import interactive
        interactive.keys_of(selected, silent)
    else:
        from hwut.services.lib.run import diff
        diff.keys_of(selected, silent)


def count(path):
    """RETURN: int, the lines of the log at 'path'; 0 where none stands."""
    if not os.path.exists(path): return 0
    with open(path) as file_handle: return len(file_handle.read().splitlines())


EXPECTED_DB = {("absent",  False): (0, 0), ("absent",  True): (0, 0),
               ("present", False): (0, 0), ("present", True): (0, 0),
               ("source",  False): (0, 0), ("source",  True): (0, 0)}


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
