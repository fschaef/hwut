#! /usr/bin/env python3
#
# @hwut {
#     title      = "The one test for an 'unaccepted' region (B-26)"
#     choices    = ["lines", "booked"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

WHICH LINES OPEN AN 'unaccepted' REGION (B-26): '##!', blanks, the word
'unaccepted', then a blank, a parameter or the line's end -- and no
other '##!' line, however it is spelt.

    lines    every spelling, through 'carries_unaccepted_text_f' and
             the file reader 'carries_unaccepted_f' alike.
    booked   'hwut.accept' books by the SAME test: a GOOD carrying a
             '##! potpourri' region is booked 'true', one carrying
             '##! unaccepted' is booked 'aspirant'. The old test
             ('any line starting ##!') booked both 'aspirant'.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.bookkeeper.api import (Bookkeeper, E_TestVerdict,  # noqa: E402
                                       carries_unaccepted_f,
                                       carries_unaccepted_text_f)
from vut.services.accept        import main as accept_main   # noqa: E402

ROOT_CONF = "hwut {\n}\n"
SCRIPT = ('#! /usr/bin/env python3\n'
          '# @hwut { title = "%s" }\n'
          'print("""%s""")\n')


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


CASE_TUPLE = (
    ("##! unaccepted",                 True),
    ("##! unaccepted 3 lines",         True),
    ("   ##!   unaccepted",            True),
    ("x\n##! unaccepted\n####",        True),
    ("##!unaccepted",                  False),   # no blank after '##!'
    ("##! unacceptedness",             False),   # a longer word
    ("##! potpourri",                  False),
    ("##! constraint-violation",       False),
    ("##! table unaccepted",           False),   # the second word
    ("## unaccepted",                  False),   # a comment, no '!'
    ("unaccepted",                     False),
    ("",                               False),
)


def test_lines():
    directory = tempfile.mkdtemp(prefix="vut_unacc_")
    ok = True
    for text, expected in CASE_TUPLE:
        path = os.path.join(directory, "n.txt")
        with open(path, "w") as fh: fh.write(text + "\n")
        by_text = carries_unaccepted_text_f(text)
        by_file = carries_unaccepted_f(path)
        holds   = (by_text is expected) and (by_file is expected)
        if not holds: ok = False
        print("  %s  %-6s %r" % ("OK  " if holds else "FAIL",
                                 expected, text))
    ok = _check([(ok, "every spelling judged alike by text and by file"),
                 (carries_unaccepted_f(os.path.join(directory, "none"))
                  is False, "an unreadable file carries nothing")]) and ok
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "'##!', blanks, 'unaccepted', and nothing else.")


def test_booked():
    root = tempfile.mkdtemp(prefix="vut_unacc_")
    with open(os.path.join(root, "hwut-root.conf"), "w") as fh:
        fh.write(ROOT_CONF)
    test = os.path.join(root, "TEST")
    os.makedirs(test)
    with open(os.path.join(test, "hwut.conf"), "w") as fh: fh.write("hwut {\n}\n")
    for stem, body in (("region", "##! potpourri\\na\\n####\\n<hwut-end>"),
                       ("plain",  "x\\n<hwut-end>")):
        path = os.path.join(test, "test-%s.py" % stem)
        with open(path, "w") as fh: fh.write(SCRIPT % (stem, body))
        os.chmod(path, 0o755)
    accept_main(["test-region.py", "--whole", "--dont-ask",
                 "--directory=%s" % test], write=lambda _: None)
    accept_main(["test-plain.py", "--dont-ask",
                 "--directory=%s" % test], write=lambda _: None)
    book = Bookkeeper(test)
    region = book.result("test-region.py", None) or {}
    plain  = book.result("test-plain.py", None) or {}
    good   = os.path.join(test, "GOOD")
    print("INSPECT: region GOOD carries unaccepted: %s"
          % carries_unaccepted_f(os.path.join(good, "test-region.py.txt")))
    print("         region booked : %s" % region.get("verdict"))
    print("         plain  GOOD carries unaccepted: %s"
          % carries_unaccepted_f(os.path.join(good, "test-plain.py.txt")))
    print("         plain  booked : %s" % plain.get("verdict"))
    ok = _check([
        (region.get("verdict") is E_TestVerdict.PASS,
         "a GOOD with a '##! potpourri' region is booked accepted"),
        (plain.get("verdict") is E_TestVerdict.ASPIRANT,
         "a first acceptance ('##! unaccepted') is booked aspirant"),
    ])
    shutil.rmtree(root, ignore_errors=True)
    _verdict(ok, "accept books by the bookkeeper's own test.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The one test for an 'unaccepted' region (B-26)",
        choice_map = {"lines": test_lines, "booked": test_booked}).run()
