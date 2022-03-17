"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Difftool command line

______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../..")

from   vut.user_interface.difference_display.console.TEST.cases import *
if "--hwut-info" in sys.argv:
    print("Display Scenarios;")
    print("CHOICES: similar, padding, potpourri, mix, analogy, error, error2, comment;")
    # Call with 'GO' on command line to interact with a TUI

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio = 0.01
config.pattern_finder.equivalent_pattern_list = ["rot|orange", "Röslein|Tülplein"]
config.pattern_finder.visible_nothing_pattern_list = [", hm,", ", wtf,", "\(who cares\)"]

if "similar" in sys.argv:
    # Testing all kinds of similarity
    test(subject_txt, nominal_txt, both=True)

elif "padding" in sys.argv:
    test(subject_modified_txt, nominal_txt, level=2)
    test(subject_modified_txt, nominal_txt, level=1)
    test(subject_modified_txt, nominal_txt, level=0)

elif "potpourri" in sys.argv:
    test("||||\n"
         + subject_modified_txt 
         + "||||\n",
         "||||\n"
         + nominal_txt
         + "||||\n", both=True)

elif "mix" in sys.argv:
    test(mix_subject
         + "||||\n"
         + mix_subject 
         + "||||\n"
         + mix_subject,
         mix_nominal
         + "||||\n"
         + mix_nominal
         + "||||\n"
         + mix_nominal, both=True)

elif "analogy" in sys.argv:
    test(analogy_subject, analogy_nominal, mode=E_LinePairSelectionMode.ANALOGIES, level=2)
    test(analogy_subject, analogy_nominal, mode=E_LinePairSelectionMode.ANALOGIES, level=1)
    test(analogy_subject, analogy_nominal, mode=E_LinePairSelectionMode.ANALOGIES, level=0)

elif "error" in sys.argv:
    test(subject_error_txt, nominal_error_txt, mode=E_LinePairSelectionMode.ERRORS, level=2)
    test(subject_error_txt, nominal_error_txt, mode=E_LinePairSelectionMode.ERRORS, level=1)
    test(subject_error_txt, nominal_error_txt, mode=E_LinePairSelectionMode.ERRORS, level=0)

elif "error2" in sys.argv:
    test(subject_error2_txt, nominal_error_txt, mode=E_LinePairSelectionMode.ERRORS, level=2)
    test(subject_error2_txt, nominal_error_txt, mode=E_LinePairSelectionMode.ERRORS, level=1)
    test(subject_error2_txt, nominal_error_txt, mode=E_LinePairSelectionMode.ERRORS, level=0)

elif "comment" in sys.argv:
    test(subject_comment_txt, nominal_comment_txt, mode=E_LinePairSelectionMode.ERRORS, both=False, level=2)

