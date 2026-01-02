#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Comparison of two potpourris.

CHOICES: judge, info;

'judge': compare two line sequences on equivalence. 
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

from   vut.engine.compare.input.pattern_finder import PatternFinder
from   vut.engine.compare.configuration            import ConfigurationPatternFinder
import vut.engine.compare.engine.equivalence_check.core as equivalence_check
import vut.engine.compare.engine.association.core       as association
from   vut.engine.compare.engine.analogy_db        import AnalogyDb
from   vut.engine.compare.TEST.common              import print_match_sequences_lists, \
                                                          print_friends_pairing_max_result, \
                                                          get_LineSequence

if "--hwut-info" in sys.argv:
    print("Line Sequence;")
    print("CHOICES: judge, info;")
    sys.exit()

config = ConfigurationPatternFinder()
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

        print("=> %s, %s" % equivalence_check.do(subject, nominal, AnalogyDb()))

    test(["a", "b"],     ["b", "a"])
    test(["a"],          ["b", "a"])
    test(["a", "((b))"], ["a", "((2))"])
    test(["b", "a"],     ["a"])

if "info" in sys.argv:

    def test(subject_list, nominal_list):
        print("--------------------------------")
        subject = get_LineSequence(pf, subject_list, config)
        nominal = get_LineSequence(pf, nominal_list, config)
        print_match_sequences_lists(subject.line_list, nominal.line_list)

        line_associations, analogy_db = association.do(subject, nominal, AnalogyDb())

        print_friends_pairing_max_result(subject_list, nominal_list, 0,
                                         line_associations, analogy_db)

    test([],           [])
    test([""],         [""])
    test(["a"],        ["a"])
    test(["a", "b"],   ["a", "b"])
    test(["a", "b"],   ["b", "a"])
    test(["a"],        ["b", "a b"])
    test(["a", "a b"], ["b"])
