#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Edit distance and edit operations between LineSequence-s.

CHOICES: subject, nominal, special;

DESCRIPTION:

This test checks on the line association. Similar to the edit operation
investigation of strings and 'Line'-s, line associations are accomplished
by means of minimum edit distance between two 'LineSequences'. The operations
involved, though, are only 'substitute', 'insert', and 'delete'. A 'transpose'
operation does not make sense, since the sequence of lines is imperativ.

The tests take a sequence of subject and nominal lines and display their
line up. 
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../" * 8)

import vut.engine.compare.engine.association.line_sequence.edit_operations.line_sequence  as     edit_distance_line_sequence
from   vut.engine.compare.engine.association.line_sequence.edit_operations.edit           import E_EditId
from   vut.engine.compare.TEST.common                    import prepare, print_match_sequences_lists, prepare_line_up
from   vut.engine.compare.engine.line                    import Line
from   vut.engine.compare.input.pattern_finder import PatternFinder
from   vut.engine.compare.configuration        import Configuration

if "--hwut-info" in sys.argv:
    print("Edit Distance: Line list alignment;")
    print("CHOICES: subject, nominal, special;")
    sys.exit()


def _make_string_again(x):
    return " ".join(_._string for _ in x)

cfg = Configuration()
cfg.pattern_finder.numeric_tolerance_ratio = 0.01
cfg.pattern_finder.equivalent_pattern_list = [ r"black|white" ]

pattern_finder = PatternFinder(cfg.pattern_finder)

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

    print_db = {
        E_EditId.GOOD:       lambda subject_i, nominal_i: _print(subject_i, "==", nominal_i),
        E_EditId.SUBSTITUTE: lambda subject_i, nominal_i: _print(subject_i, "!=", nominal_i),
        E_EditId.INSERT:     lambda subject_i, nominal_i: _print(None,      "-<", nominal_i),
        E_EditId.DELETE:     lambda subject_i, nominal_i: _print(subject_i, ">-", None),
    }

    subject_i, nominal_i = 0, 0
    for edit in edit_list:
        print_db[edit.id](subject_i, nominal_i)

        subject_i += edit_distance_line_sequence.position_increment_db[edit.id][0]
        nominal_i += edit_distance_line_sequence.position_increment_db[edit.id][1]

def test(a_list, b_list, take_string_f=False):
    print("------------------------------------")
    print()
    if not take_string_f:
        subject = [Line.from_raw_line(i, _make_string_again(prepare(x)), pattern_finder) for i, x in enumerate(a_list) ]
        nominal = [Line.from_raw_line(i, _make_string_again(prepare(x)), pattern_finder) for i, x in enumerate(b_list) ]
    else:
        subject = [Line.from_raw_line(i, line, pattern_finder) for i, line in enumerate(a_list)]
        nominal = [Line.from_raw_line(i, line, pattern_finder) for i, line in enumerate(b_list)]
    print_match_sequences_lists(subject, nominal)

    print("=>")
    editions = edit_distance_line_sequence.do(subject, nominal)
    print("Cost: %.6f" % editions.cost)
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
    test(["a"], ["b ", "ablackb"], take_string_f=True)

