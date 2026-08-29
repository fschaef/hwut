#! /usr/bin/env python3
#
# @hwut {
#     title      = "Potpourri"
#     choices    = ["info", "judge"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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

from   vut.engine.compare.reading.pattern_finder     import PatternFinder
from   vut.engine.compare.configuration            import Configuration
from   vut.engine.compare.contract.analogy_db        import AnalogyDb
from   vut.engine.compare.TEST.common              import frame_with_potpourri_borders, \
                                                         get_Potpourri, \
                                                         print_friends_pairing_max_result

if "--hwut-info" in sys.argv:
    print("Potpourri;")
    print("CHOICES: judge, info;")
    sys.exit()

config = Configuration()
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
        print("=> %s, %s" % subject.is_equivalent_to_nominal(nominal, AnalogyDb()))

    test(["a", "b"], ["b", "a"])
    test(["a"],      ["b", "a"])

if "info" in sys.argv:

    def test(subject_line_list, nominal_line_list):
        print("--------------------------------")
        print("subject:", subject_line_list)
        print("nominal:", nominal_line_list)
        subject = get_Potpourri(pf, subject_line_list, config)
        nominal = get_Potpourri(pf, nominal_line_list, config)

        line_associations, analogy_db = subject.associate_with_nominal(nominal, AnalogyDb())

        subject_line_list = frame_with_potpourri_borders(subject_line_list)
        nominal_line_list = frame_with_potpourri_borders(nominal_line_list)

        print_friends_pairing_max_result(subject_line_list, nominal_line_list, 0.0,
                                         line_associations, analogy_db, line_offset=1)

    test(["a", "b"], ["b", "a"])
    test(["a"],      ["b", "a b"])
