#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Comparison of two lines.

CHOICES: judge, info;

DESCRIPTION:

'judge': compare two lines on equivalence. 
         Result: 'True' or 'False'.

'info':  provide information about similarity.
         Result: edit operations.

The first is used to determine the correctness of unit tests, the later is
used to display the difference of a subject's output and the nominal output.

The tests play with several line elements, indicated in the tests by 
characters, namely:

        "s": LineElementString(0,6,"string")      # strings
        "S": LineElementString(0,6,"strong")
        "x": LineElementAnalogy(0,5,"((x))")      # analogies 
        "y": LineElementAnalogy(0,5,"((y))")
        "z": LineElementAnalogy(0,5,"((z))")
        "n": LineElementNumber("4711", 0.01)  # number

The tests compose a 'Line' object as a sequence of line elements. With 
these 'Line' objects '.compare()' and '.edit_operations()' is called.
______________________________________________________________________________
"""

import sys

sys.path.insert(0, "../../../../../")

from   vut.engine.compare.engine.line       import Line
from   vut.engine.compare.engine.analogy_db import AnalogyDb
from   vut.engine.compare.TEST.common       import prepare, print_match_sequences


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
