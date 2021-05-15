#! /usr/bin/env python3
#
# PURPOSE: Comparison of two potpourris.
#
# Tests: (1) compare two potpourris on equality. Result 'True' or 'False'.
#        (2) compares two potpourris and provide according appropriate 
#            line associations for display.
#
# The first is used to determine the correctness of unit tests, the later is 
# used to display the difference of a subject's output and the nominal output.
#
# NOTE: The line pairing is done by 'friends_pairing/max.py'. Detailed
#       unit tests on the functionality are found there.
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________
 
import sys
import os
import re

sys.path.insert(0, "../../../../../")

from   hwut.engine.compare.tolerance.pattern_finder import PatternFinder
import hwut.engine.compare.engine.core               as     comperator
from   hwut.engine.compare.engine.analogy_db               import AnalogyDb
from   hwut.engine.compare.TEST.common              import \
                                                           print_match_sequences, \
                                                           frame_with_potpourri_borders, \
                                                           get_Potpourri, \
                                                           print_friends_pairing_max_result

if "--hwut-info" in sys.argv:
    print("Potpourri;")
    print("CHOICES: judge, info;")
    sys.exit()

config = comperator.Configuration()
config.analogy_f               = True
config.numeric_tolerance_ratio = 0.011
config.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
pf                             = PatternFinder(config)

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

        line_associations = subject.line_associations(nominal, AnalogyDb())

        subject_line_list = frame_with_potpourri_borders(subject_line_list)
        nominal_line_list = frame_with_potpourri_borders(nominal_line_list)

        print_friends_pairing_max_result(subject_line_list, nominal_line_list, 0.0, 
                                         line_associations, AnalogyDb(), line_offset=1)

    test(["a", "b"], ["b", "a"])
    test(["a"],      ["b", "a b"])
