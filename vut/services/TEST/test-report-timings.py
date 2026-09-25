#! /usr/bin/env python3
#  @hwut {
#    title   = "hwut.report.timings"
#    choices = ["traditional", "table", "file", "empty", "refused"]
#  }
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.report.timings' -- the traces read back, in both shapes.

CHOICES: traditional, table, file, empty, refused;

DESCRIPTION:

    traditional  one line per case, the run's milliseconds right, the
                 build's in brackets where one stands; the tail counts
                 the cases and sums the RUN times only.
    table        the CSV on stdout: a header, one row per case, the
                 operations spelt 'Run.duration_ms' and so on.
    file         '-o <file>' writes there and says so; stdout holds the
                 one line, the file holds the report.
    empty        a directory whose traces this machine did not write:
                 said as EMPTY, status 3, not faulted.
    refused      a directory that does not stand, and an unknown word.

NO WALL CLOCK REACHES THE GOOD (O-30). The fixture WRITES the traces
this face reads, with numbers chosen by hand, so the page measures the
reading and nothing about the machine that runs it. The system column
is this machine's own key -- the face passes over every other machine's
rows (B-11), so a fixture naming a foreign system would read as empty
everywhere.
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile

import config                                                       # noqa: F401

from   vut.engine.bookkeeper.traces      import system_key
from   vut.services.lib.report           import timings
from   vut.test_writing_support.python.hwut_runner import HwutRunner


ROW_TUPLE = (
    #  test,             choice,     operation, duration, cpu,  memory
    ("test-engine.py",   "first",    "Build",   "1203",   "900",  "12.5"),
    ("test-engine.py",   "first",    "Run",     "412",    "380",  "9.0"),
    ("test-engine.py",   "follow",   "Run",     "390",    "351",  "9.0"),
    ("test-lexer.py",    "",         "Run",     "17",     "12",   "4.0"),
    ("test-nothing.py",  "silent",   "Run",     "",       "",     ""),
)


def fixture(directory, system=None):
    """RETURN: None. Writes the traces file this face reads, with the
              rows above -- a foreign system's row beside them, which
              every reading must pass over (B-11)."""
    system = system or system_key()
    line_list = ["system;test;choice;operation;day;duration_ms;"
                 "cpu_time_ms;peak_memory_mb"]
    for test, choice, operation, duration, cpu, memory in ROW_TUPLE:
        line_list.append(";".join((system, test, choice, operation,
                                   "2026-09-23", duration, cpu, memory)))
    line_list.append(";".join(("some-other-machine", "test-elsewhere.py",
                               "far", "Run", "2026-09-23", "9999",
                               "9999", "99.0")))
    with open(os.path.join(directory, "hwut-traces.csv"), "w",
              encoding="utf-8") as handle:
        handle.write("\n".join(line_list) + "\n")


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _in_fixture(function):
    """RETURN: None. Calls 'function(directory)' in a fresh directory
              holding the traces fixture; removes it afterwards."""
    directory = tempfile.mkdtemp(prefix="hwut-timings-")
    try:
        fixture(directory)
        function(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def run_traditional():
    """RETURN: None. The default shape, and what it sums."""
    def body(directory):
        banner("the traditional report")
        status = timings.do(directory=directory)
        banner("status")
        print("    %s" % status.name)
        banner("the build is NOT summed")
        print("    412 + 390 + 17 = 819 ms, and the tail says 0.82 s")
    _in_fixture(body)


def run_table():
    """RETURN: None. The CSV shape, header and rows."""
    def body(directory):
        banner("--table")
        line_list = timings.table_line_list_of(
            timings.row_list_of([directory]))
        for line in line_list: print("    %s" % line.replace(directory, "."))
        banner("the foreign machine's row stands in no line")
        print("    'test-elsewhere.py' appears: %s"
              % any("test-elsewhere" in line for line in line_list))
    _in_fixture(body)


def run_file():
    """RETURN: None. '-o <file>' writes the report, not stdout."""
    def body(directory):
        out_path = os.path.join(directory, "timings.csv")
        banner("-o <file>: stdout says only where it went")
        status = timings.do(directory=directory, table_f=True,
                            out_path=out_path,
                            write=lambda text: print(
                                "    %s" % text.replace(directory, ".")))
        banner("status")
        print("    %s" % status.name)
        banner("and the file holds the report")
        with open(out_path, encoding="utf-8") as handle:
            for line in handle.read().splitlines()[:3]:
                print("    %s" % line.replace(directory, "."))
    _in_fixture(body)


def run_empty():
    """RETURN: None. A directory this machine never measured."""
    directory = tempfile.mkdtemp(prefix="hwut-timings-")
    try:
        banner("no traces at all")
        status = timings.do(directory=directory,
                            write=lambda text: print(
                                "    %s" % text.replace(directory, ".")))
        print("    status: %s" % status.name)

        banner("traces of ANOTHER machine only (B-11)")
        fixture(directory, system="some-other-machine")
        status = timings.do(directory=directory,
                            write=lambda text: print(
                                "    %s" % text.replace(directory, ".")))
        print("    status: %s" % status.name)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def run_refused():
    """RETURN: None. A directory that does not stand; an unknown word."""
    banner("a directory that does not stand")
    status = timings.do(directory="/no/such/directory",
                        write=lambda text: print("    %s" % text))
    print("    status: %s" % status.name)

    banner("a word the face does not know")
    status = timings.main(["hwut.report.timings", "--sideways"])
    print("    status: %s" % status.name)

    banner("'-o' without a file")
    status = timings.main(["hwut.report.timings", "-o"])
    print("    status: %s" % status.name)


HwutRunner(
    argv       = sys.argv,
    title      = "hwut.report.timings",
    choice_map = {
        "traditional": run_traditional,
        "table":       run_table,
        "file":        run_file,
        "empty":       run_empty,
        "refused":     run_refused,
    },
).run()
