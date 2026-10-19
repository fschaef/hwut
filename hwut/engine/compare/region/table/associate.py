"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer"""
from ...core.line_pair import LinePair, filler_pair_list
from ...core.edit_operations.edit import Edit, E_EditId
from ...engine.line import Line
from ...reading.line_element import LineElementString
from .core import Judgment


def _display_line(line):
    """RETURNS: Line, a display twin whose element sequence is ONE string
                      element covering the raw text.
    """
    raw    = line._string.rstrip("\n")
    result = Line(line.line_n, raw, line.lexer)
    result._UT_set_sequence((LineElementString(raw),))
    return result


def do(subject, nominal, analogy_db):
    """RETURNS: [0] list of 'LinePair'-s, document order; classification
                    from the SAME core.Judgment as the Judge (THE LAW by
                    construction).
                [1] 'analogy_db' -- the global db, UNCHANGED.
    """
    judgment = Judgment(subject, nominal)
    n_lines  = [line for line, _ in nominal.row_list]

    result       = []
    used_nominal = set()
    for si, (s_line, _) in enumerate(subject.row_list):
        kind, info = judgment.subject_class[si]
        if kind == "ok":
            used_nominal.add(info)
            result.append(LinePair(_display_line(s_line),
                                   _display_line(n_lines[info]),
                                   (Edit(E_EditId.GOOD_TOLERATED),),
                                   seq_edit_id=E_EditId.GOOD_TOLERATED))
        elif si in judgment.differs_db:
            #  HELD AGAINST A NOMINAL ROW AND DIFFERING FROM IT: shown
            #  side by side, as verbatim shows a changed line -- not as
            #  a lone subject row and a lone nominal row (the book's
            #  D-15).
            ni = judgment.differs_db[si]
            used_nominal.add(ni)
            result.append(LinePair(_display_line(s_line),
                                   _display_line(n_lines[ni]),
                                   (Edit(E_EditId.SUBSTITUTE),), cost=1.0,
                                   seq_edit_id=E_EditId.SUBSTITUTE))
        else:
            result.append(LinePair(_display_line(s_line), None, (),
                                   cost=1.0,
                                   seq_edit_id=E_EditId.DELETE))

    for ni in sorted(judgment.nominal_uncovered):
        result.append(LinePair(None, _display_line(n_lines[ni]), (),
                               cost=1.0,
                               seq_edit_id=E_EditId.INSERT))
    for ni, n_line in enumerate(n_lines):
        if ni in used_nominal or ni in judgment.nominal_uncovered:
            continue
        result.append(LinePair(None, _display_line(n_line),
                               (Edit(E_EditId.GOOD_INSERT),),
                               seq_edit_id=E_EditId.GOOD_INSERT))

    #  INSIGNIFICANT LINES are neutral display filler, as in verbatim
    #  and the outer text; they are no rows ('chunk.row_list_split_by').
    result.extend(filler_pair_list(subject.line_list, nominal.line_list))

    def key(x):
        return (1, x.nominal_line_n) if x.subject_line_n == -1 \
               else (0, x.subject_line_n)
    return sorted(result, key=key), analogy_db
