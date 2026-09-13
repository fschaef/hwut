#! /usr/bin/env python3
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
fail_book -- why does '--fail' keep selecting a case that passed?

    python3 vut/adm/fail_book.py              # runs 'bin/hwut --fail' itself
    bin/hwut --fail 2>&1 | python3 vut/adm/fail_book.py -

Reads the run's report, takes EVERY CASE THAT CAME OUT [OK], and for
each one prints what its directory's book says NOW -- the row, the
book's header form, the file's mtime, and whether a legacy
'result_db.json' stands beside it. A case that passed and whose row
still says 'false', or has no row, or whose book was not written since
the run began, is the answer.

Finds the tree the way 'TEST/config.py' does.
"""

import os
import re
import sys
import csv
import time
import subprocess

_cur = os.path.abspath(os.path.dirname(__file__))
while os.path.basename(_cur) != "vut":
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        sys.exit("fail_book.py: no directory 'vut' above '%s'" % __file__)
    _cur = _parent
ROOT = _cur

_DIR_RE  = re.compile(r"^DIR\s+(\S+)")
_LINE_RE = re.compile(r"^(?:DONE|START)?\s+(\S+)(?:\s+(\S+))?\s+\.{2,}\s+\[(OK|FAIL)\]")


def ok_cases(report_text):
    """
    RETURN: list of (directory, test, choice), every case the report
            marks [OK]; choice None where the line carries none. A
            ':' in the test column repeats the test of the line
            before, as the display prints it.
    """
    found, directory, last_test = [], None, None
    for line in report_text.splitlines():
        m = _DIR_RE.match(line)
        if m: directory = m.group(1); continue
        m = _LINE_RE.match(line)
        if not m or directory is None: continue
        test, choice, verdict = m.group(1), m.group(2), m.group(3)
        if test == ":": test = last_test
        else:           last_test = test
        if verdict == "OK": found.append((directory, test, choice))
    return found


def book_rows(path):
    """
    RETURN: [0] str, the header line verbatim ('' where no file)
            [1] list of dict, rows with the blank-test continuation
                filled in, as the book spells it
    """
    if not os.path.isfile(path): return "", []
    with open(path, encoding="utf-8", newline="") as fh:
        head = fh.readline().rstrip("\n"); fh.seek(0)
        delim = ";" if ";" in head else ","
        rows, last_test = [], None
        for row in csv.DictReader(fh, delimiter=delim):
            if row.get("test"): last_test = row["test"]
            else:               row["test"] = last_test
            rows.append(row)
    return head, rows


def main(argv):
    """RETURN: int, 0."""
    started = time.time()
    if argv[:1] == ["-"]:
        #  The report's 'DIR' paths are relative to where 'hwut' RAN,
        #  which is where this pipe stands.
        report, base = sys.stdin.read(), os.getcwd()
    else:
        hwut = os.path.join(ROOT, "bin", "hwut")
        report = subprocess.run([hwut, "--fail"], cwd=ROOT, check=False,
                                capture_output=True, text=True).stdout
        base = ROOT
    cases = ok_cases(report)
    print("cases that came out [OK] under --fail: %d" % len(cases))
    for directory, test, choice in cases:
        good = os.path.join(base, directory, "GOOD")
        csv_path  = os.path.join(good, "book.csv")
        if not os.path.exists(csv_path):
            csv_path = os.path.join(good, "result_db.csv")
        json_path = os.path.join(good, "result_db.json")
        head, rows = book_rows(csv_path)
        key = choice if choice is not None else ""
        hit = [r for r in rows if r["test"] == test
               and (r.get("choice") or "") == key]
        print()
        print("== %s  %s%s" % (directory, test,
                               "" if choice is None else " " + choice))
        if not os.path.isfile(csv_path):
            print("   NO book.csv in %s" % os.path.relpath(good, base))
        else:
            age = time.time() - os.path.getmtime(csv_path)
            print("   book header : %s" % head)
            print("   book mtime  : %.0fs ago%s"
                  % (age, "  <-- OLDER THAN THIS RUN" if age > (time.time() - started) + 5 else ""))
            if hit:
                r = hit[0]
                print("   row         : verdict=%s report=%s"
                      % (r.get("verdict"), r.get("report")))
                if str(r.get("verdict")).lower() != "true":   # E_TestVerdict.PASS's token
                    print("   >>> PASSED, BUT THE BOOK STILL SAYS FAIL")
            else:
                near = sorted({r["test"] for r in rows if test.split(".")[0] in (r["test"] or "")})
                print("   row         : NONE for this (test, choice)")
                if near: print("   similar     : %s" % ", ".join(near))
                print("   >>> PASSED, BUT NO ROW -- keyed under another name?")
        if os.path.isfile(json_path):
            print("   legacy      : result_db.json ALSO stands (csv wins on read)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
