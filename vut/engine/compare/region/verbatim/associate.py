"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from vut.engine.compare.core.line_pair              import LinePair
from vut.engine.compare.core.edit_operations.edit   import Edit, E_EditId
from vut.engine.compare.engine.line                 import Line
from vut.engine.compare.reading.line_element   import LineElementString


def _display_line(line):
    """RETURNS: Line, a display twin of 'line' whose element sequence is ONE
                      string element covering the raw text -- verbatim cells
                      show whole lines, never tolerance-lexed tokens.
    """
    raw    = line._string.rstrip("\n")
    result = Line(line.line_n, raw, line.lexer)
    result._UT_set_sequence((LineElementString(raw),))
    return result


def do(subject, nominal, analogy_db):
    """RETURNS: [0] list of 'LinePair'-s, document order.
                [1] 'analogy_db' -- the global db, UNCHANGED.

    Byte-exact positional alignment: content line k pairs with content
    line k (GOOD if identical, SUBSTITUTE else); count-mismatch tails are
    one-sided (DELETE/INSERT). Insignificant lines are neutral display
    filler, exactly as in the outer text.
    """
    def split(chunk):
        content, filler = [], []
        for line in chunk.line_list:
            (filler if line.is_insignificant() else content).append(line)
        return content, filler

    s_content, s_filler = split(subject)
    n_content, n_filler = split(nominal)

    result = []
    for s, n in zip(s_content, n_content):
        s_d, n_d = _display_line(s), _display_line(n)
        if s_d._string == n_d._string:
            result.append(LinePair(s_d, n_d, (Edit(E_EditId.GOOD),),
                                   seq_edit_id=E_EditId.GOOD))
        else:
            result.append(LinePair(s_d, n_d, (Edit(E_EditId.SUBSTITUTE),),
                                   cost=1.0,
                                   seq_edit_id=E_EditId.SUBSTITUTE))

    for s in s_content[len(n_content):]:
        result.append(LinePair(_display_line(s), None, (), cost=1.0,
                               seq_edit_id=E_EditId.DELETE))
    for n in n_content[len(s_content):]:
        result.append(LinePair(None, _display_line(n), (), cost=1.0,
                               seq_edit_id=E_EditId.INSERT))

    result.extend(LinePair(line, None, ()) for line in s_filler)
    result.extend(LinePair(None, line, ()) for line in n_filler)

    def key(x):
        return (1, x.nominal_line_n) if x.subject_line_n == -1 \
               else (0, x.subject_line_n)
    return sorted(result, key=key), analogy_db
