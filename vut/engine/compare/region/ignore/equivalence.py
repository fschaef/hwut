"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer"""
from __future__ import annotations
from vut.engine.compare.contract.analogy_db import AnalogyDb


def do(subject, nominal, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, always -- the contents of an 'ignore' region are
                    exempt from judgment (the framing itself was already
                    matched by the chunk alignment).
                [1] 'analogy_db' -- the global db, UNCHANGED.
    """
    return True, analogy_db
