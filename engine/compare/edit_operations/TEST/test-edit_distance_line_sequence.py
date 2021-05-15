#! /usr/bin/env python3
#
# PURPOSE: Testing 'Edit Distance' computations for line lists.
#
#
# The edit operations may be used for the line up display side-to-side display
# of two text files (unit test outputs).
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________

import sys
import os
import re

sys.path.insert(0, "../../../../../")

import ut.engine.compare.edit_operations.line_sequence   as     edit_distance_line_sequence
from   ut.engine.compare.edit_operations.line_sequence   import E_EditLineSequence
from   ut.engine.compare.TEST.common               import prepare, print_match_sequences_lists, prepare_line_up
from   ut.engine.compare.engine.line                      import Line

if "--hwut-info" in sys.argv:
    print("Edit Distance: Line list alignment;")
    print("CHOICES: subject, nominal, special;")
    sys.exit()

def print_lineup(subject, nominal, edit_list):

    subject_txt_list, space, nominal_txt_list = prepare_line_up(subject, nominal)

    def _print(subject_i, mid, nominal_i):
        if subject_i is None:                    subject_txt = ""
        elif subject_i >= len(subject_txt_list): subject_txt = "<end>"
        else:                                    subject_txt = subject_txt_list[subject_i]
        if nominal_i is None:                    nominal_txt = ""
        elif nominal_i >= len(nominal_txt_list): nominal_txt = "<end>"
        else:                                    nominal_txt = nominal_txt_list[nominal_i]
        print("   %s %s%s %s" % (subject_txt, space(subject_txt), mid, nominal_txt))

    subject_i, nominal_i = 0, 0
    for edit_id, edit_list in edit_list:
        if edit_id == E_EditLineSequence.GOOD:
            _print(subject_i, "==", nominal_i)
        elif edit_id == E_EditLineSequence.SUBSTITUTE:
            _print(subject_i, "!=", nominal_i)
        elif edit_id == E_EditLineSequence.INSERT:
            _print(None, "-<", nominal_i)
        elif edit_id == E_EditLineSequence.DELETE:
            _print(subject_i, ">-", None)
        else:
            assert False

        subject_i += edit_distance_line_sequence.position_increment_db[edit_id][0]
        nominal_i += edit_distance_line_sequence.position_increment_db[edit_id][1]

def test(a_list, b_list):
    print("------------------------------------")
    print()
    subject = [Line(i, prepare(x)) for i, x in enumerate(a_list) ]
    nominal = [Line(i, prepare(x)) for i, x in enumerate(b_list) ]
    print_match_sequences_lists(subject, nominal)

    print("=>")
    editions = edit_distance_line_sequence.do(subject, nominal)
    print("Cost: (%i, %.6f)" % editions.cost)
    print_lineup(subject, nominal, editions.edit_list)
    if len(editions.analogy_db):
        print("AnalogyDb:")
        print(repr(editions.analogy_db))
    print()


if "subject" in sys.argv:
    test(["s", "S", "Q"], ["s", "S", "Q"])
    test(["s", "S"], ["s", "S", "Q"])
    test(["s", "Q"], ["s", "S", "Q"])
    test(["S", "Q"], ["s", "S", "Q"])

    test(["s"], ["s", "S", "Q"])
    test(["S"], ["s", "S", "Q"])
    test(["Q"], ["s", "S", "Q"])

    test([], ["s", "S", "Q"])
    test([], ["s", "S"])
    test([], ["s"])
    test([], [])

if "nominal" in sys.argv:
    test(["s", "S", "Q"], ["s", "S"])
    test(["s", "S", "Q"], ["s", "Q"])
    test(["s", "S", "Q"], ["S", "Q"])

    test(["s", "S", "Q"], ["s"])
    test(["s", "S", "Q"], ["S"])
    test(["s", "S", "Q"], ["Q"])

    test(["s", "S", "Q"], [])
    test(["s", "S"], [])
    test(["s"], [])

if "special" in sys.argv:
    test(["ssQ", "sSQ", "SsQ", "QsS"], ["SsQ", "SsQ", "QsS"])
    test(["SsQ", "QsS", "sSQ", "ssQ"], ["SsQ", "QsS", "SsQ", ])
    test(["1"], ["2", "3"])

