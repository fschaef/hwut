#! /usr/bin/env python3
#
# PURPOSE: Comparison of two lines.
#
# Tests: (1) compare two lines on equality. Result 'True' or 'False'.
#        (2) compares two lines with the result of a list of edit operations.
#
# The first is used to determine the correctness of unit tests, the later is 
# used to display the difference of a subject's output and the nominal output.
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________
 
import sys
import os
import re

sys.path.insert(0, "../../../../../")

from   ut.engine.compare.engine.line          import Line
from   ut.engine.compare.engine.analogy_db    import AnalogyDb
from   ut.engine.compare.TEST.common   import prepare, print_match_sequences


if "--hwut-info" in sys.argv:
    print("Line Comparison;")
    print("CHOICES: judge, info;")
    sys.exit()


if "judge" in sys.argv:

    def test(a, b):
        subject = Line(66, list(prepare(a)))
        nominal = Line(4711, list(prepare(b, True)))
        print_match_sequences(subject.sequence, nominal.sequence)
        print("=> %s, %s" % subject.compare(nominal, AnalogyDb()))

    test("sS", "sS")
    test("sn", "sS")
    test("ss", "sS")
    test("xx", "yz")
    test("xy", "yz")
    test("xy", "yzy")
    test("xyx", "yz")

    
if "info" in sys.argv:

    def test(a, b):
        subject = Line(66, list(prepare(a)))
        nominal = Line(4711, list(prepare(b, True)))
        print_match_sequences(subject.sequence, nominal.sequence)
        cost,      \
        edit_list, \
        analogy_db = subject.edit_operations(nominal, AnalogyDb())
        print("Cost: %.6f" % cost)
        for i, edit in enumerate(edit_list):
            if edit.transpose_ai is not None:
                print("[%i] %s (%s)" % (i, edit.id.name, edit.transpose_ai))
            else:
                print("[%i] %s"      % (i, edit.id.name))
        print("AnalogyDb:")
        print(repr(analogy_db))

    test("sS", "sS")
    test("sn", "sS")
    test("ss", "sS")
    test("xx", "yz")
    test("xy", "yz")
    test("xy", "yzy")
    test("xyx", "yz")
