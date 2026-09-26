#! /usr/bin/env python3
#
# @hwut {
#     title      = "The traces table: a machine class, and 'the one above'"
#     choices    = ["key", "table", "elision"]
#     tolerance { eq_pattern = ["SUCCESS.*", "FAILURE.*",
#                               "[0-9]{4}-[0-9]{2}-[0-9]{2}"] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
'TEST/hwut-traces.csv' (B-11, B-12): what a run COST, per machine
CLASS, beside the tests -- committed, replaced per key, deletable.

    key       the system key names a class, not a host: the vendor
              string with its noise gone, the MODEL NUMBER kept, cut
              at a token boundary; the cores the process may use
    table     a row per (system, test, choice, operation), REPLACED
              where the key stands, so the file grows only on a
              machine class not seen before
    elision   an empty 'system' or 'test' is the one above; an empty
              'choice' is a test that has none, and an empty number is
              one the platform did not measure

THE DAY A ROW WAS WRITTEN is the recording's calendar, not the table's
behaviour: the page's eq_pattern takes any ISO date.
______________________________________________________________________________
"""
import os
import re
import shutil
import sys
import tempfile
import config                                                     # noqa F401
from   config import HwutRunner                                   # noqa E402
from   vut.engine.bookkeeper import traces                        # noqa E402

LINUX = "linux-i7-13700k-16c-x86_64"
MAC   = "darwin-m1-pro-10c-arm64"


def _check(pair_list):
    """RETURN: bool, True where every (condition, text) held; each printed."""
    ok = True
    for condition, text in pair_list:
        print("  %s: %s" % ("OK  " if condition else "FAIL", text))
        ok = ok and condition
    return ok


def _verdict(ok, text):
    """RETURN: None. The choice's closing word."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", text))


def _db(system=LINUX):
    """RETURN: (TraceDb, str), a table on fresh ground, and its
    directory; the system key is forced, so the output does not
    depend on the machine that runs the test."""
    directory = tempfile.mkdtemp(prefix="vut_traces_")
    traces._SYSTEM_KEY = system
    return traces.TraceDb(directory), directory


def test_key():
    """The vendor string becomes a class."""
    pair_list = []
    for raw, wanted in (
            ("Intel(R) Core(TM) i7-13700K CPU @ 3.40GHz",  "i7-13700k"),
            ("AMD Ryzen 7 5800X 8-Core Processor",         "ryzen-7-5800x"),
            ("Apple M1 Pro",                               "m1-pro"),
            ("Intel(R) Xeon(R) Platinum 8375C CPU @ 2.90GHz",
                                                  "xeon-platinum-8375c"),
            ("Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz",
                                                 "xeon-platinum-8259cl"),
            ("Intel(R) Xeon(R) CPU E5-2686 v4 @ 2.30GHz",
                                                      "xeon-e5-2686-v4"),
            ("AMD EPYC 7R32 48-Core Processor",            "epyc-7r32"),
            ("",                                           "cpu")):
        got = traces.cpu_tag(raw)
        print("  %-46s -> %s" % (raw[:44] or "''", got))
        pair_list.append((got == wanted, "%r" % (wanted,)))
    long_tag = traces.cpu_tag("Some Vendor Model 1234567890 ABCDEFGHIJ KLMNOP")
    pair_list.append((len(long_tag) <= traces.TAG_MAX_N
                      and not long_tag.endswith("-"),
                      "a long string is cut at a token boundary: %r"
                      % long_tag))
    traces._SYSTEM_KEY = None
    here = traces.system_key()
    #  THIS MACHINE'S KEY IS THE MACHINE'S, NOT THE PAGE'S: which class
    #  the recording computer was is foreign to what the key does. The
    #  FORM is the page's; the value is shown only where it breaks it.
    form_f = re.fullmatch(r"[a-z0-9]+-[a-z0-9-]+-[0-9]+c-[a-z0-9-]+",
                          here) is not None
    pair_list.append((form_f, "this machine's key has the form "
                              "'<os>-<cpu>-<n>c-<arch>'"))
    pair_list.append((here == traces.system_key(),
                      "this machine's key is stable within the process"))
    print("  this machine: %s" % ("<os>-<cpu>-<n>c-<arch>" if form_f
                                  else here))
    _verdict(_check(pair_list), "the key names a class; the model number "
                                "survives the cut.")


def test_table():
    """A row per key, replaced where it stands."""
    db, directory = _db()
    db.note("test-a.py", "one", "Run", duration_ms=142, cpu_time_ms=136)
    db.note("test-a.py", "two", "Run", duration_ms=141)
    first = db.read()[(LINUX, "test-a.py", "one", "Run")]["duration_ms"]
    db.note("test-a.py", "one", "Run", duration_ms=999, cpu_time_ms=900)
    again = db.read()
    traces._SYSTEM_KEY = MAC
    db.note("test-a.py", "one", "Run", duration_ms=98)
    with_mac = db.read()
    print("  after three notes and one machine more:")
    for key in sorted(with_mac):
        print("    %-28s %-11s %-4s %s" % (key[0], key[1], key[2],
                                           with_mac[key]["duration_ms"]))
    ok = _check([
        (first == "142", "the first note stands"),
        (again[(LINUX, "test-a.py", "one", "Run")]["duration_ms"] == "999",
         "a second note REPLACES it -- the last run's numbers, not a history"),
        (len(again) == 2, "and adds no row"),
        (len(with_mac) == 3,
         "another machine CLASS adds a row; that is the only growth"),
        (again[(LINUX, "test-a.py", "two", "Run")]["cpu_time_ms"] == "",
         "what was not measured is empty, never a zero"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "an entry is replaced; a new machine class adds one.")


def test_elision():
    """'The one above', and what does not elide."""
    db, directory = _db()
    db.note("test-a.py", "one", "Run", duration_ms=142, cpu_time_ms=136)
    db.note("test-a.py", "two", "Run", duration_ms=141)
    db.note("test-b.py", None,  "Run", duration_ms=167)
    traces._SYSTEM_KEY = MAC
    db.note("test-a.py", "one", "Run", duration_ms=98)
    text = open(db.path, encoding="utf-8").read()
    print("  the file:")
    for line in text.splitlines(): print("    %s" % line)
    line_list = text.splitlines()[1:]
    back = db.read()
    #  A FIRST ROW WITH NOTHING ABOVE IT: the file reads as empty.
    headless = os.path.join(directory, traces.FILE_NAME)
    open(headless, "w", encoding="utf-8").write(
        text.splitlines()[0] + "\n;;one;Run;2026-01-01;5;;\n")
    ok = _check([
        (line_list[2].startswith(";;"),
         "a repeated system AND test elide to ';;'"),
        (line_list[3].startswith(";test-b.py;;"),
         "a new test carries its name; its EMPTY CHOICE is not an elision"),
        (line_list[0].startswith(MAC + ";test-a.py;"),
         "a new machine class writes both again (sorted, so it leads)"),
        (len(back) == 4 and back[(LINUX, "test-b.py", "", "Run")]
                                ["duration_ms"] == "167",
         "and all four rows read back whole"),
        (traces.TraceDb(directory).read() == {},
         "a first row with nothing above it reads as EMPTY, not a guess"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the eye reads a group; the reader reads every row.")


if __name__ == "__main__":
    HwutRunner(argv=sys.argv, title="The traces table",
               choice_map={"key": test_key, "table": test_table,
                           "elision": test_elision}).run()
