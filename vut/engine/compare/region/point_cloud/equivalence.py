"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from __future__ import annotations
from vut.engine.compare.engine.analogy_db            import AnalogyDb
from vut.engine.compare.region.point_cloud.core      import Judgment


def do(subject, nominal, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if the point clouds satisfy the NOMINAL side's
                    criteria (limit/dist/pair coverage or matching, and/or
                    constraint) -- see 'chunk.py' for the full semantics.
                    False, else.
                [1] 'analogy_db' -- the global db, UNCHANGED (regions carry
                    no analogy state, DOC/SEMANTICS.txt 5.2).
    """
    return Judgment(subject, nominal).verdict, analogy_db
