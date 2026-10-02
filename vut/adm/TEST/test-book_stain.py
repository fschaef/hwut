#! /usr/bin/env python3
#
# @hwut {
#     title   = "adm/book_stain.py: the books to one 'stain' column (B-18)"
#     choices = ["convert"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE-OFF CONVERSION of a tree's books, before the framework
         reads only the new form: 'stain_repeat_n' and 'stain_when' become
         'stain', a count N the keyword 'N repeat'. A book in the new form
         is left alone; the converted book reads back through the
         bookkeeper.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE   = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "book_stain.py")
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))

OLD_BOOK = ("# vut-register 5 generation:5 apps:1 marks:0=4\n"
            "test;choice;verdict;report;coverage;stderr;"
            "stain_repeat_n;stain_when;test_id;choice_id\n"
            "demo.py;one;true;ok;;;;;0;0\n"
            ";two;false;unstable;;;7;2026-09-27T12:00:00Z;0;1\n"
            ";three;true;ok\n")
NEW_BOOK = ("test;choice;verdict;report;coverage;stderr;"
            "stain;test_id;choice_id\n"
            "x.py;;true;ok;;;3 repeat;0;0\n")


def put(path, text):
    """RETURN: None. 'text' is the file at 'path'."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh: fh.write(text)


def call(*word_list):
    """RETURN: None. The script, its output printed."""
    done = subprocess.run([sys.executable, SCRIPT] + list(word_list),
                          capture_output=True, text=True)
    root = word_list[0]
    for line in done.stdout.splitlines():
        print("   %s" % line.replace(root + os.sep, ""))


def test_convert():
    root = tempfile.mkdtemp(prefix="vut_book_stain_")
    try:
        old = os.path.join(root, "a", "TEST", "GOOD", "book.csv")
        new = os.path.join(root, "b", "TEST", "GOOD", "book.csv")
        put(old, OLD_BOOK)
        put(new, NEW_BOOK)
        print("-- without '--apply': said, not done")
        call(root)
        print("-- with '--apply'")
        call(root, "--apply")
        with open(old, encoding="utf-8") as fh: print(fh.read(), end="")
        print("-- again: nothing left to do")
        call(root, "--apply")
        from vut.engine.bookkeeper.api import Bookkeeper
        book = Bookkeeper(os.path.dirname(os.path.dirname(old)))
        print("-- read back through the bookkeeper")
        for choice in ("one", "two", "three"):
            print("   %-6s stain = %s" % (choice, book.stain("demo.py", choice)))
    finally:
        shutil.rmtree(root, ignore_errors=True)


test_convert()
print("<hwut-end>")
