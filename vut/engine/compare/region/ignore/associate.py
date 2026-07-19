"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from vut.engine.compare.core.line_pair              import LinePair
from vut.engine.compare.core.edit_operations.edit   import Edit, E_EditId
from vut.engine.compare.engine.line                 import Line
from vut.engine.compare.engine.input.line_element   import LineElementString


def _display_line(line):
    """RETURNS: Line, a display twin whose element sequence is ONE string
                      element covering the raw text.
    """
    raw    = line._string.rstrip("\n")
    result = Line(line.line_n, raw, line.lexer)
    result._UT_set_sequence((LineElementString(raw),))
    return result


def do(subject, nominal, analogy_db):
    """RETURNS: [0] list of 'LinePair'-s, document order -- every pair is
                    equivalence-NEUTRAL (contents of an 'ignore' region are
                    exempt from judgment; shown as tolerated).
                [1] 'analogy_db' -- the global db, UNCHANGED.
    """
    s_list = list(subject.line_list)
    n_list = list(nominal.line_list)

    result = []
    for s, n in zip(s_list, n_list):
        result.append(LinePair(_display_line(s), _display_line(n),
                               (Edit(E_EditId.GOOD_TOLERATED),),
                               seq_edit_id=E_EditId.GOOD_TOLERATED))
    for s in s_list[len(n_list):]:
        result.append(LinePair(_display_line(s), None,
                               (Edit(E_EditId.GOOD_DELETE),),
                               seq_edit_id=E_EditId.GOOD_DELETE))
    for n in n_list[len(s_list):]:
        result.append(LinePair(None, _display_line(n),
                               (Edit(E_EditId.GOOD_INSERT),),
                               seq_edit_id=E_EditId.GOOD_INSERT))

    return result, analogy_db
