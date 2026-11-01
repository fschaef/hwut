#! /usr/bin/env python3
"""app_runner.py -- the test application of numfmt, with hwut's HwutRunner
as front end. One choice per locale. The execution scheme of interactive
mode comes from the environment (APP_PARALLEL=process), so the harness can
run the same application both ways."""
import os, shutil, sys
sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.hwut_runner import HwutRunner
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numfmt


def table(locale):
    numfmt.configure(locale)
    for x in (0, 7.5, 1234.5, 1234567.891):
        print("%-6s %14s" % (locale, numfmt.fmt(x)))


CHOICE_MAP = {"de": lambda: table("de"), "en": lambda: table("en"), "ch": lambda: table("ch")}

if __name__ == "__main__":
    HwutRunner(sys.argv, "numfmt per locale", CHOICE_MAP,
               parallel=os.environ.get("APP_PARALLEL") or None).run()
