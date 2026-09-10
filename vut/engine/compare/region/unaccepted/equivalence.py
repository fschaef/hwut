"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from __future__ import annotations
from vut.engine.compare.contract.analogy_db import AnalogyDb


def do(subject, nominal, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] False where either side holds a line -- an
                    'unaccepted' region has not been judged, and a
                    comparison that meets one cannot pass (E-58).
                    True only where BOTH sides are EMPTY: a region with
                    nothing in it has nothing undecided, and the
                    lawyer, who sees no pair, must agree with the judge.
                [1] 'analogy_db' -- the global db, UNCHANGED.
    """
    undecided_f = bool(subject.line_list) or bool(nominal.line_list)
    return (not undecided_f), analogy_db
