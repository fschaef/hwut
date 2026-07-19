"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from vut.engine.compare.core.line_pair              import LinePair
from vut.engine.compare.core.edit_operations.edit   import Edit, E_EditId
from vut.engine.compare.engine.line                 import Line
from vut.engine.compare.engine.input.line_element   import LineElementString
from vut.engine.compare.region.table.core           import Judgment


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

    def key(x):
        return (1, x.nominal_line_n) if x.subject_line_n == -1 \
               else (0, x.subject_line_n)
    return sorted(result, key=key), analogy_db
