#! /usr/bin/env python3
#
# @hwut {
#     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
#     pype    = "build.pypes"
#     same    = true
#     choices = ["serial", "parallel"]
#     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
#                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
#                 "pype-quantity", "pype-anchors-globs-flush"]
#     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
# }
#
"""
______________________________________________________________________________
SUBJECT  the log of a recursive build -- configure, then the directories
         'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
         a pype system makes of it.
REQUIREMENT  A parallel build builds what the serial build builds: the same
             sources, the same warnings, the same archives and the same
             program, linked from the same parts.

The application only REPORTS the build as it happens, as 'make -w' would.
The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
between it and the comparison (hwut runs it; the application prints no
'<hwut-end>'):

    build.pypes       --> normalise.pype         stdin to the first
                      normalise.pype --> build.pype
    normalise.pype    a parallel build tags each line with its job,
                      'job2: cc -c ...'; the tag goes, every other line
                      passes unchanged ('flush')
    build.pype        the summary, sorted -- see its own comments: modes
                      pushed on 'Entering directory' and popped on
                      'Leaving' (nested: 'app/plugins' inside 'app'),
                      '<entry>'/'<exit>' around each, a vocabulary
                      imported from 'compiler.pype', a repeat group over
                      the parts of a link, durations read as quantities

'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.py.txt'. Serial or
parallel, the summary must be the same -- that is the requirement, and
the header says it once. 'choices' is a list: no choice states anything
of its own.

The laws: the compile times sum to under 5 s ('((compile: ...))', in
s, whatever unit the log used), and nothing in the log broke the build's
grammar ('((breaches: 0))').

A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
build here; a pype that judges time is fed live ('protocol.sh slow').
______________________________________________________________________________
"""
import random
import sys
import threading
import time

#  What each directory does: its sources, warnings and products.
DIRECTORY_DB = {
    "lib": {"source_list":  ["lib/str.c", "lib/num.c", "lib/map.c"],
            "warning_db":   {"lib/num.c": "lib/num.c:14:9: warning: unused variable 'n'"},
            "product":      "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o"},
    "app/plugins":
           {"source_list":  ["app/plugins/png.c", "app/plugins/svg.c"],
            "warning_db":   {"app/plugins/svg.c": "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"},
            "product":      "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o"},
    "app": {"source_list":  ["app/main.c", "app/cli.c"],
            "warning_db":   {},
            "product":      "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a"},
}


def compile_lines(name):
    """RETURN: list of str, what building directory 'name' prints, its
    sources compiled in the time each takes."""
    spec, line_list = DIRECTORY_DB[name], []
    for source in spec["source_list"]:
        took = random.uniform(0.04, 0.12)
        time.sleep(took)
        spent = "%d ms" % (took * 1000) if took < 0.1 else "%.2f s" % took
        line_list.append("cc -c %s -o %s (took %s)" % (source, source[:-2] + ".o", spent))
        if source in spec["warning_db"]:
            line_list.append(spec["warning_db"][source])
    return line_list


def directory_block(name, level, inner=None):
    """RETURN: list of str, the block 'make -w' prints for 'name' at
    'level', the block of 'inner' nested before the product."""
    line_list = ["make[%d]: Entering directory '%s'" % (level, name)]
    line_list += compile_lines(name)
    if inner: line_list += directory_block(inner, level + 1)
    line_list.append(DIRECTORY_DB[name]["product"])
    line_list.append("make[%d]: Leaving directory '%s'" % (level, name))
    return line_list


def configure():
    """RETURN: None. Prints what 'configure' prints, and that make enters
    the top directory."""
    print("configure: checking for cc... cc")
    print("configure: checking for ar... ar")
    print("make: Entering directory 'demo'")


def serial():
    """RETURN: None. Builds one directory after the other."""
    configure()
    for line in directory_block("lib", 1) + directory_block("app", 1, "app/plugins"):
        print(line, flush=True)
    print("make: Leaving directory 'demo'")


def parallel():
    """RETURN: None. Builds 'lib' and 'app' at once. Each job prints its
    block whole when done ('make -O'), every line tagged with the job;
    which job finishes first is the scheduler's."""
    configure()
    lock = threading.Lock()

    def job(slot, name, inner=None):
        block = directory_block(name, 1, inner)
        with lock:
            for line in block:
                print("job%d: %s" % (slot, line), flush=True)

    pool = [threading.Thread(target=job, args=(1, "lib")),
            threading.Thread(target=job, args=(2, "app", "app/plugins"))]
    for thread in pool: thread.start()
    for thread in pool: thread.join()
    print("make: Leaving directory 'demo'")


CHOICE_DB = {"serial": serial, "parallel": parallel}

random.seed(time.time_ns())
choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_DB:
    print("choices: %s" % ", ".join(CHOICE_DB))
    sys.exit(1)
CHOICE_DB[choice]()
