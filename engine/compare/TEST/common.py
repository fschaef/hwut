from   ut.engine.compare.tolerance.line_element import LineElementString, LineElementNumber, LineElementAnalogy, LineElementEquivalencePattern
from   ut.engine.compare.engine.line            import Line
from   ut.engine.compare.engine.input_chunk     import Potpourri
from   ut.engine.compare.engine.input_chunk     import LineSequence

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


def prepare(x, nominal_f=False):
    for letter in x:
        if   letter == "e":
            yield LineElementString(0,6,"")
        elif letter == "1":
            yield LineElementString(0,1,"a")
        elif letter == "2":
            yield LineElementString(0,1,"b")
        elif letter == "3":
            yield LineElementString(0,1,"a b")
            yield LineElementEquivalencePattern(1,2, "a b", [0])
            yield LineElementString(2,3,"a b")
        elif letter == "s":
            yield LineElementString(0,6,"string")
        elif   letter == "S":
            yield LineElementString(0,6,"strong")
        elif   letter == "Q":
            yield LineElementString(0,6,"quant")
        elif   letter == "x":
            yield LineElementAnalogy(0,5,"((x))")
        elif   letter == "y":
            yield LineElementAnalogy(0,5,"((y))")
        elif   letter == "z":
            yield LineElementAnalogy(0,5,"((z))")
        elif letter == "n":
            if nominal_f:
                yield LineElementNumber(0,4,"4711", 0.01)
            else:
                yield LineElementNumber(0,4,"4711")
        else:
            assert False

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
        line_number_str = lambda line_n: "[%02i] " % line_n
    else:
        line_number_str = lambda line_n: ""

    line_n = 0
    for s_text, n_text in zip_longest(subject_txt_list, nominal_txt_list, fillvalue=""):
        line_n += 1
        print("   %s%s%s %s" % (line_number_str(line_n), s_text, space(s_text), n_text))

def print_friends_pairing_max_result(subject_line_list, nominal_line_list, cost, line_associations, analogy_db, line_offset=0):
    print("cost: %.5f; line_associations: %i;" % (cost, len(line_associations)))

    def _name(line_list, match_seq):
        if match_seq is None:
            return "None", "--"
        elif match_seq.line_n is None:
            return match_seq.sequence[0].string, "--"
        elif match_seq.line_n + line_offset < len(line_list):
            return line_list[match_seq.line_n + line_offset], "%02i" % match_seq.line_n
        else:
            return "<end>", "%02i" % match_seq.line_n

    for lina in line_associations:
        subject_txt, subject_line_n = _name(subject_line_list, lina.subject_seq)
        nominal_txt, nominal_line_n = _name(nominal_line_list, lina.nominal_seq)

        space  = " " * (23 - len(subject_txt))
        space2 = " " * (23 - len(nominal_txt))
        if lina.edit_list is None: edit_list = []
        else:                      edit_list = lina.edit_list
        edit_txt = ", ".join(edit_id.name for edit_id, transpose_ai in edit_list)
        print("   [%s] %s%s --> [%s] %s %s{%s}" % (subject_line_n, subject_txt,
                                                   space,
                                                   nominal_line_n, nominal_txt,
                                                   space2,
                                                   edit_txt))

    if cost == 0:
        print("AnalogyDb:")
        print(analogy_db)

