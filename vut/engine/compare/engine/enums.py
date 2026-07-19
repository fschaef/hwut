"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________

PURPOSE: Definition of core structures, namely 'E_Verdict' and 'Configuration'.
_______________________________________________________________________________
"""
from enum import Enum, auto

class E_Verdict(Enum):
    MISFIT                             = auto()
    DIFFERENT                          = auto()
    EQUIVALENT                         = auto()
    EQUIVALENT_SUBJECT_VISIBLE_NOTHING = auto()
    EQUIVALENT_NOMINAL_VISIBLE_NOTHING = auto()

    @staticmethod
    def is_equivalent(x):
        """RETURNS: True, if 'x' expresses equivalence (incl. VISIBLE_NOTHING
                          collapse).
                    False, else.

        Delegates to 'engine/semantics.py' -- the single source of the
        comparison semantics (late import avoids a module cycle).
        """
        from vut.engine.compare.engine.semantics import is_equivalent_verdict
        return is_equivalent_verdict(x)

class E_PotpourriBorder(Enum):
    NONE  = auto()

class E_Chunk(Enum):
    LINE_SEQUENCE = auto()
    LINE          = auto()
    POTPOURRI     = auto()
    VERBATIM      = auto()
    IGNORE        = auto()
    POINT_CLOUD   = auto()
    TABLE         = auto()
    TERMINAL      = auto()
    VOID          = auto()
    NONE          = auto()

class E_ToleranceId(int, Enum):
    STRING              = 1
    VISIBLE_NOTHING     = 2
    ANALOGY             = 3
    NUMERIC             = 4
    EQUIVALENCE_PATTERN = 5
    SEPERATOR           = 6
    CONSTRAINT_BINDING  = 7

