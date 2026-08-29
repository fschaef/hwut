"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from __future__ import annotations
from vut.engine.compare.contract.analogy_db       import AnalogyDb
from vut.engine.compare.region.table.core       import Judgment


def do(subject, nominal, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if the subject table satisfies the NOMINAL side's
                    row-matching rules (see 'chunk.py'). False, else.
                [1] 'analogy_db' -- the global db, UNCHANGED.
    """
    return Judgment(subject, nominal).verdict, analogy_db
