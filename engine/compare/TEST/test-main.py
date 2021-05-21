"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: API of compare module

CHOICES: compare, line_associations;

DESCRIPTION:

The main API provides two functions:

    compare(): judges on equivalence of subject and nominal.

    edit_operations(): determines how to transform subject into nominal. This 
                       is to be used for diff-display.

The first function provides a verdict, the second provides line associations.
In this test each function is tested by a specific 'CHOICE'.

This is the outer shell of the compare module. The tests are trivial as the
complexity of the process is hidden in the submodules located in the sub
directory of this module.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../")

import ut.engine.compare.engine.core as     comperator
import ut.engine.compare.main        as     main
from   ut.engine.compare.TEST.common import print_match_sequences_lists, \
                                              print_list_sequence_pairs, \
                                              print_friends_pairing_max_result
from   io import StringIO


if "--hwut-info" in sys.argv:
    print("Line Comparison;")
    print("CHOICES: compare, line_associations;")
    sys.exit()

config = comperator.Configuration()
config.pattern_finder.analogy_f               = False
config.pattern_finder.whitespace_f            = True
config.pattern_finder.backslash_f             = False
config.pattern_finder.numeric_tolerance_ratio = 0
config.pattern_finder.equivalent_pattern_list = []

def test_core(subject_txt, nominal_txt):
    print("--------------------------------------------------\n")
    print()
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)
    subject_line_list = subject_txt.splitlines()
    max_length = max(len(txt) for txt in subject_line_list)
    def space(txt):
        return " " * (max_length - len(txt))
    print_list_sequence_pairs(subject_txt.splitlines(), space, nominal_txt.splitlines(),
                              line_numbers_f=True)
    return subject, nominal

if "compare" in sys.argv:
    def test(subject_txt, nominal_txt):
        subject, nominal = test_core(subject_txt, nominal_txt)
        print()
        print("=> verdict: %s" % main.compare(config, subject, nominal))
        print()

if "line_associations" in sys.argv:
    def test(subject_txt, nominal_txt):
        subject_line_list = subject_txt.splitlines()
        nominal_line_list = nominal_txt.splitlines()
        subject, nominal = test_core(subject_txt, nominal_txt)
        print()
        print("=> ")
        print()
        line_association_chunk_list = list(main.line_associations(config, subject, nominal))
        for chunk in line_association_chunk_list:
            print("TYPE:", chunk.type().name)
            print_friends_pairing_max_result(subject_line_list, nominal_line_list, 0, chunk.line_association_list(), [], line_offset=-1)
        print()

test("Hallo\nWelt", "Hallo\nWelt")
test("Welt X", "Welt Y")
test("Hallo\nWorld", "Hallo\nWelt")
test("Hallo\nWelt 1\nWelt 2", "Hallo\n\nWelt 1\n   \nWelt  2")
test("Hallo\n||||\nWelt", "Hallo\n||||\nWelt\n||||")
test("Hallo\n||||\nWelt\n||||", "Hallo\n||||\nWelt")
test("Hallo\n||||\nWelt\nLe Monde\n||||", "Hallo\n||||\nLe Monde\nWelt\n||||")

test("Hallo##\n##Welt\nGood", "##Hello\nWorld##\nGood")
test("||||\nHallo##\n##Welt\nGood\n||||", "||||\n##Hello\nWorld##\nGood\n||||")

test("Hallo\nWelt",                 "||||\nHello\nWorld\n||||")
test("||||\nHello\nLe Monde\n||||", "||||\nHello\nWorld\n||||")
