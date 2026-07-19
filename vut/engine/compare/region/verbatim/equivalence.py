"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from __future__ import annotations
from vut.engine.compare.engine.analogy_db import AnalogyDb


def _raw(line):
    """RETURNS: str, the raw text of 'line' without the trailing newline --
                     the unit of the byte-exact comparison.
    """
    return line._string.rstrip("\n")


def do(subject, nominal, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if the region's lines agree byte-for-byte, in
                    order, with equal counts. False, else.
                [1] 'analogy_db' -- the global db, UNCHANGED (regions carry
                    no analogy state in or out, DOC/SEMANTICS.txt 5.2; in
                    'verbatim' analogies do not even exist as a concept).
    """
    verdict = ([_raw(l) for l in subject.line_list]
               == [_raw(l) for l in nominal.line_list])
    return verdict, analogy_db
