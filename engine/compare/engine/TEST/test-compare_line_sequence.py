#! /usr/bin/env python3
#
# PURPOSE: Comparison of two lists of lines.
#
# Tests: (1) compare two line lists on equality. Result 'True' or 'False'.
#        (2) compares two line lists and provide according appropriate
#            line associations for display.
#
# The first is used to determine the correctness of unit tests, the later is
# used to display the difference of a subject's output and the nominal output.
#
# NOTE: The line association is done by 'edit_distance/line_list.py'. Detailed
#       unit tests on the functionality are found there.
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________

import sys
import os
import re

sys.path.insert(0, "../../../../../")

from   hwut.engine.compare.tolerance.pattern_finder import PatternFinder
import hwut.engine.compare.engine.core              as     comperator
from   hwut.engine.compare.engine.analogy_db        import AnalogyDb
from   hwut.engine.compare.TEST.common              import \
                                                           print_match_sequences, \
                                                           print_match_sequences_lists, \
                                                           print_friends_pairing_max_result, \
                                                           get_LineSequence


if "--hwut-info" in sys.argv:
    print("Line Sequence;")
    print("CHOICES: judge, info;")
    sys.exit()

config = comperator.Configuration()
config.analogy_f               = True
config.numeric_tolerance_ratio = 0.011
config.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
pf                             = PatternFinder(config)

if "judge" in sys.argv:

    def test(subject_list, nominal_list):
        print("--------------------------------")

        subject = get_LineSequence(pf, subject_list, config)
        nominal = get_LineSequence(pf, nominal_list, config)
        print_match_sequences_lists(subject.line_list, nominal.line_list)

        print("=> %s, %s" % subject.compare(nominal, AnalogyDb()))

    test(["a", "b"],     ["b", "a"])
    test(["a"],          ["b", "a"])
    test(["a", "((b))"], ["a", "((2))"])
    test(["b", "a"],          ["a"])

if "info" in sys.argv:

    def test(subject_list, nominal_list):
        print("--------------------------------")
        subject = get_LineSequence(pf, subject_list, config)
        nominal = get_LineSequence(pf, nominal_list, config)
        print_match_sequences_lists(subject.line_list, nominal.line_list)

        line_associations = subject.line_associations(nominal, AnalogyDb())

        print_friends_pairing_max_result(subject_list, nominal_list, 0,
                                         line_associations, AnalogyDb())

    test([],         [])
    test([""],         [""])
    test(["a"],        ["a"])
    test(["a", "b"],   ["a", "b"])
    test(["a", "b"],   ["b", "a"])
    test(["a"],        ["b", "a b"])
    test(["a", "a b"], ["b"])
