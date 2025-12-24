"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Helper functions for Unit Test prints.

DESCRIPTION:

This module collects some functions which are used accross multiple tests
applications.
______________________________________________________________________________
"""
from   vut.engine.compare.tolerance.line_element import LineElementString, \
                                                        LineElementNumber, \
                                                        LineElementAnalogy, \
                                                        LineElementVisibleNothing, \
                                                        LineElementEquivalencePattern
from   vut.engine.compare.engine.line            import Line
from   vut.engine.compare.engine.potpourri       import Potpourri
from   vut.engine.compare.engine.line_sequence   import LineSequence

from   itertools import zip_longest

def get_Potpourri(pattern_finder, line_text_list, configuration):
    start_line_n = -1
    end_line_n   = len(line_text_list)
    return Potpourri(start_line_n, end_line_n,
                     (tuple(Line(line_n, pattern_finder.do(line_text))
                            for line_n, line_text in enumerate(line_text_list))),
                     configuration)

def get_LineSequence(pattern_finder, line_text_list, configuration):
    start_line_n = -1
    end_line_n   = len(line_text_list)
    return LineSequence(start_line_n, end_line_n,
                        (Line(line_n, pattern_finder.do(line_text))
                         for line_n, line_text in enumerate(line_text_list)),
                        configuration)


def frame_with_potpourri_borders(line_list):
    return ["||||"] + line_list + ["||||"]


line_element_db = {
    "e":  [ LineElementString(0,0,"") ],
    "v":  [ LineElementVisibleNothing(0,3,"nix") ],
    "V":  [ LineElementVisibleNothing(0,7,"nothing") ],
    "1":  [ LineElementString(0,1,"a") ],
    "2":  [ LineElementString(0,1,"b") ],
    "3":  [ LineElementString(0,1,"a b"), 
            LineElementEquivalencePattern(1,2, "a b", [0 ]),
            LineElementString(2,3,"a b")  ],
    "s":  [ LineElementString(0,6,"string") ],
    "S":  [ LineElementString(0,6,"strong") ],
    "Q":  [ LineElementString(0,6,"quant") ],
    "x":  [ LineElementAnalogy(0,5,"((x))") ],
    "y":  [ LineElementAnalogy(0,5,"((y))") ],
    "z":  [ LineElementAnalogy(0,5,"((z))") ],
    "n":  [ LineElementNumber(0,4,"4711", 0.01) ], 
    "nr": [ LineElementNumber(0,4,"4711") ]
}
def prepare(x, nominal_f=False):
    for letter in x:
        if letter == "n" and not nominal_f: letter = "nr"
        yield from line_element_db[letter]

def prepare_match_sequence(mseq):
    return ", ".join("%s:%s" % (m.tolerance_id.name, m.string) for m in mseq)

def print_match_sequences(subject, nominal):
    print("subject:  %s" % prepare_match_sequence(subject))
    print("nominal:  %s" % prepare_match_sequence(nominal))

def prepare_line_up(subject, nominal):
    subject_txt_list = [
        prepare_match_sequence(mseq) for mseq in subject
    ]

    if subject_txt_list:
        subject_max_length = max(len(txt) for txt in subject_txt_list)
    else:
        subject_max_length = 5

    nominal_txt_list = [
        prepare_match_sequence(mseq) for mseq in nominal
    ]

    if subject_txt_list:
        subject_max_length = max([len(txt) for txt in subject_txt_list] + [5])
    else:
        subject_max_length = 5

    def space(txt):
        return " " * (subject_max_length - len(txt) + 3)

    return subject_txt_list, space, nominal_txt_list

def print_match_sequences_lists(subject, nominal):
    subject_txt_list, space, nominal_txt_list = prepare_line_up(subject, nominal)
    print_list_sequence_pairs(subject_txt_list, space, nominal_txt_list)

def print_list_sequence_pairs(subject_txt_list, space, nominal_txt_list, line_numbers_f=False):
    if line_numbers_f:
        def line_number_str(line_n): return "[%02i] " % line_n
    else:
        def line_number_str(line_n): return ""

    line_n = 0
    for s_text, n_text in zip_longest(subject_txt_list, nominal_txt_list, fillvalue=""):
        line_n += 1
        print("   %s%s%s %s" % (line_number_str(line_n), s_text, space(s_text), n_text))

def print_friends_pairing_max_result(subject_line_list, nominal_line_list, cost, \
                                     line_associations, analogy_db, line_offset=0):
    print("cost: %.5f; line_associations: %i;" % (cost, len(line_associations)))

    def _name(line_list, match_seq):
        if match_seq is None:
            return "None", "--"
        elif match_seq.line_n is None:
            return match_seq.sequence[0].string, "--" # pragma no cover
        elif match_seq.line_n + line_offset < len(line_list):
            return line_list[match_seq.line_n + line_offset], "%02i" % match_seq.line_n
        else:
            return "<end>", "%02i" % match_seq.line_n # pragma no cover

    for lina in line_associations:
        subject_txt, subject_line_n = _name(subject_line_list, lina._raw.subject)
        nominal_txt, nominal_line_n = _name(nominal_line_list, lina._raw.nominal)

        space  = " " * (23 - len(subject_txt))
        space2 = " " * (23 - len(nominal_txt))
        if lina._raw.edit_list is None: edit_list = []
        else:                           edit_list = lina._raw.edit_list
        edit_txt = ", ".join(edit.id.name for edit in edit_list)
        # lina has itself no information about, insert, delete, substitute of lines.
        print("   [%s] %s%s --> [%s] %s %s{%s}" % (subject_line_n, subject_txt,
                                                   space,
                                                   nominal_line_n, nominal_txt,
                                                   space2,
                                                   edit_txt))

    if cost == 0:
        print("AnalogyDb:")
        print(analogy_db)

