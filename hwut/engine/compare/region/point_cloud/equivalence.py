"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer"""
from __future__ import annotations
from ...contract.analogy_db import AnalogyDb
from .core import Judgment


def do(subject, nominal, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if the point clouds satisfy the NOMINAL side's
                    criteria (limit/dist/pair coverage or matching, and/or
                    constraint) -- see 'chunk.py' for the full semantics.
                    False, else.
                [1] 'analogy_db' -- the global db, UNCHANGED (regions carry
                    no analogy state, DOC/SEMANTICS.txt 5.2).
    """
    return Judgment(subject, nominal).verdict, analogy_db
