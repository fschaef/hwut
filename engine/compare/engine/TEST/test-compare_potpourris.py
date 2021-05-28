#! /usr/bin/env python3
"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
______________________________________________________________________________


PURPOSE: Comparison of two potpourris.

CHOICES: judge, info;

'judge': compare two potpourris on equivalence. 
         Result: 'True' or 'False'.

'info':  provide information about similarity.
         Result: line associations.

The first is used to determine the correctness of unit tests, the later is
used to display the difference of a subject's output and the nominal output.

These tests only examine the outer layer of the API. The detailed functioning
test are done in 'friends_pairing/TEST'.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../../")

from   ut.engine.compare.tolerance.pattern_finder import PatternFinder
import ut.engine.compare.engine.core              as     comperator
from   ut.engine.compare.engine.analogy_db        import AnalogyDb
from   ut.engine.compare.TEST.common              import frame_with_potpourri_borders, \
                                                         get_Potpourri, \
                                                         print_friends_pairing_max_result

if "--hwut-info" in sys.argv:
    print("Potpourri;")
    print("CHOICES: judge, info;")
    sys.exit()

config = comperator.Configuration()
config.pattern_finder.analogy_f               = True
config.pattern_finder.numeric_tolerance_ratio = 0.011
config.pattern_finder.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
pf = PatternFinder(config.pattern_finder)

if "judge" in sys.argv:

    def test(subject_line_list, nominal_line_list):
        print("--------------------------------")
        print("subject:", subject_line_list)
        print("nominal:", nominal_line_list)
        subject = get_Potpourri(pf, subject_line_list, config)
        nominal = get_Potpourri(pf, nominal_line_list, config)
        print("=> %s, %s" % subject.compare(nominal, AnalogyDb()))

    test(["a", "b"], ["b", "a"])
    test(["a"],      ["b", "a"])

if "info" in sys.argv:

    def test(subject_line_list, nominal_line_list):
        print("--------------------------------")
        print("subject:", subject_line_list)
        print("nominal:", nominal_line_list)
        subject = get_Potpourri(pf, subject_line_list, config)
        nominal = get_Potpourri(pf, nominal_line_list, config)

        line_associations, analogy_db = subject.line_associations(nominal, AnalogyDb())

        subject_line_list = frame_with_potpourri_borders(subject_line_list)
        nominal_line_list = frame_with_potpourri_borders(nominal_line_list)

        print_friends_pairing_max_result(subject_line_list, nominal_line_list, 0.0,
                                         line_associations, analogy_db, line_offset=1)

    test(["a", "b"], ["b", "a"])
    test(["a"],      ["b", "a b"])
