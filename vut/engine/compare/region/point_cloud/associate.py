"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from vut.engine.compare.core.line_pair              import LinePair
from vut.engine.compare.core.edit_operations.edit   import Edit, E_EditId
from vut.engine.compare.engine.line                 import Line
from vut.engine.compare.engine.input.line_element   import LineElementString
from vut.engine.compare.region.point_cloud.core     import Judgment


def _display_line(line):
    """RETURNS: Line, a display twin whose element sequence is ONE string
                      element covering the raw text.
    """
    raw    = line._string.rstrip("\n")
    result = Line(line.line_n, raw, line.lexer)
    result._UT_set_sequence((LineElementString(raw),))
    return result


def do(subject, nominal, analogy_db):
    """RETURNS: [0] list of 'LinePair'-s, document order: each subject
                    point paired with its counterpart (GOOD_TOLERATED) or
                    marked BAD ('bad' classification of core.Judgment);
                    uncovered nominal points appear one-sided BAD; in
                    constraint-only mode counts are irrelevant, so
                    counterpart-less points are neutral.
                [1] 'analogy_db' -- the global db, UNCHANGED.

    Verdict-relevant classification comes from the SAME core.Judgment as
    the Judge -- THE LAW by construction.
    """
    judgment = Judgment(subject, nominal)
    n_lines  = [line for line, _ in nominal.point_list]

    result       = []
    used_nominal = set()
    for si, (s_line, _) in enumerate(subject.point_list):
        kind, info = judgment.subject_class[si]
        if kind == "ok" and info is not None:
            used_nominal.add(info)
            result.append(LinePair(_display_line(s_line),
                                   _display_line(n_lines[info]),
                                   (Edit(E_EditId.GOOD_TOLERATED),),
                                   seq_edit_id=E_EditId.GOOD_TOLERATED))
        elif kind == "ok":
            # constraint-only mode: no counterpart concept -- neutral.
            result.append(LinePair(_display_line(s_line), None,
                                   (Edit(E_EditId.GOOD_DELETE),),
                                   seq_edit_id=E_EditId.GOOD_DELETE))
        else:
            result.append(LinePair(_display_line(s_line), None, (),
                                   cost=1.0,
                                   seq_edit_id=E_EditId.DELETE))

    if nominal.limit is not None:
        for ni in sorted(judgment.nominal_uncovered):
            result.append(LinePair(None, _display_line(n_lines[ni]), (),
                                   cost=1.0,
                                   seq_edit_id=E_EditId.INSERT))
        for ni, (n_line, _) in enumerate(nominal.point_list):
            if ni in used_nominal or ni in judgment.nominal_uncovered:
                continue
            # covered, but not displayed as anyone's counterpart: neutral.
            result.append(LinePair(None, _display_line(n_line),
                                   (Edit(E_EditId.GOOD_INSERT),),
                                   seq_edit_id=E_EditId.GOOD_INSERT))
    else:
        for n_line, _ in nominal.point_list:
            result.append(LinePair(None, _display_line(n_line),
                                   (Edit(E_EditId.GOOD_INSERT),),
                                   seq_edit_id=E_EditId.GOOD_INSERT))

    def key(x):
        return (1, x.nominal_line_n) if x.subject_line_n == -1 \
               else (0, x.subject_line_n)
    return sorted(result, key=key), analogy_db
