"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Helper functions for Unit Test prints.

DESCRIPTION:

This module collects some functions which are used accross multiple tests
applications.
______________________________________________________________________________
"""
from   vut.engine.compare.reading.line_element import LineElementString, \
                                                        LineElementNumber, \
                                                        LineElementAnalogy, \
                                                        LineElementVisibleNothing, \
                                                        LineElementEquivalencePattern
from   vut.engine.compare.engine.enums           import E_Chunk
from   vut.engine.compare.engine.line            import Line
from   vut.engine.compare.reading.input_chunk      import InputChunk_factory

from   itertools import zip_longest

def get_Potpourri(pattern_finder, line_text_list, configuration):
    start_line_n = -1
    end_line_n   = len(line_text_list)
    result = InputChunk_factory(E_Chunk.POTPOURRI, 
                                start_line_n, end_line_n,
                                [Line(line_n, line_text, pattern_finder)
                                 for line_n, line_text in enumerate(line_text_list)],
                                configuration)
    ## print("#POT", result)
    return result

def get_sequence_of_Line(pattern_finder, line_text_list, configuration):
    start_line_n = -1
    end_line_n   = len(line_text_list)
    return [
        InputChunk_factory(E_Chunk.LINE, start_line_n, end_line_n,
                           [Line(line_n, line_text, pattern_finder)],
                           configuration)
        for line_n, line_text in enumerate(line_text_list)
    ]

def get_LineSequence(pattern_finder, line_text_list, configuration):
    start_line_n = -1
    end_line_n   = len(line_text_list)
    return InputChunk_factory(E_Chunk.LINE_SEQUENCE, start_line_n, end_line_n,
                              [Line(line_n, line_text, pattern_finder)
                               for line_n, line_text in enumerate(line_text_list)],
                              configuration)


def frame_with_potpourri_borders(line_list):
    return ["##! potpourri"] + line_list + ["####"]


line_element_db = {
    "e":  [ LineElementString("") ],
    "v":  [ LineElementVisibleNothing("nix") ],
    "V":  [ LineElementVisibleNothing("nothing") ],
    "1":  [ LineElementString("a") ],
    "2":  [ LineElementString("b") ],
    "3":  [ LineElementString("a"), 
            LineElementEquivalencePattern("a b"[1:2], [0 ]),
            LineElementString("a b"[2:3])  ],
    "s":  [ LineElementString("string"[0:6]) ],
    "S":  [ LineElementString("strong"[0:6]) ],
    "Q":  [ LineElementString("quant"[0:6]) ],
    "x":  [ LineElementAnalogy("((x))") ],
    "y":  [ LineElementAnalogy("((y))") ],
    "z":  [ LineElementAnalogy("((z))") ],
    "n":  [ LineElementNumber("4711", 0.01) ], 
    "nr": [ LineElementNumber("4711") ]
}

def prepare(x, nominal_f=False):
    for letter in x:
        if letter == "n" and not nominal_f: letter = "nr"
        yield from line_element_db[letter]

def prepare_match_sequence(mseq):
    return ", ".join("%s:%s" % (m.tolerance_id.name, m._string) for m in mseq)

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
            return match_seq.sequence[0]._string, "--" # pragma no cover
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

