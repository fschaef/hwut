#! /usr/bin/env python3
#
# @hwut {
#     title      = "Line Comparison"
#     choices    = ["info", "judge"]
# }
#
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

        "s": LineElementString("string")      # strings
        "S": LineElementString("strong")
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

from   vut.engine.compare.engine.line          import Line
from   vut.engine.compare.contract.analogy_db    import AnalogyDb
from   vut.engine.compare.TEST.common          import prepare, print_match_sequences
from   vut.engine.compare.reading.pattern_finder import PatternFinder
from   vut.engine.compare.configuration        import Configuration


if "--hwut-info" in sys.argv:
    print("Line Comparison;")
    print("CHOICES: judge, info;")
    sys.exit()


def _make_string_again(x):
    return " ".join(_._string for _ in x)

cfg = Configuration()
cfg.pattern_finder.numeric_tolerance_ratio = 0.01
pattern_finder = PatternFinder(cfg.pattern_finder)

if "judge" in sys.argv:

    def test(a, b):
        subject = Line(66, _make_string_again(prepare(a)), pattern_finder)
        nominal = Line(4711, _make_string_again(prepare(b, True)), pattern_finder)
        print_match_sequences(subject.sequence, nominal.sequence)

        verdict, analogy_db = subject.compare_and_provide_analogies(nominal)
        if analogy_db is None:
            analogy_db = AnalogyDb()
        else:
            analogy_db = analogy_db.to_AnalogyDb()
        print("=> %s, %s" % (verdict, analogy_db))

    test("sS", "sS")
    test("sn", "sS")
    test("ss", "sS")
    test("xx", "yz")
    test("xy", "yz")
    test("xy", "yzy")
    test("xyx", "yz")


if "info" in sys.argv:

    def test(a, b):
        subject = Line(66, _make_string_again(prepare(a)), pattern_finder)
        nominal = Line(4711, _make_string_again(prepare(b, True)), pattern_finder)
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
