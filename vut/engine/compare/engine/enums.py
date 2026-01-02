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
        return x in (E_Verdict.EQUIVALENT, 
                     E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING,
                     E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING)

class E_PotpourriBorder(Enum):
    NONE  = auto()
    BEGIN = auto()
    END   = auto()

class E_Chunk(Enum):
    LINE_SEQUENCE = auto()
    POTPOURRI     = auto()
    TERMINAL      = auto()
    EMPTY         = auto()
    NONE          = auto()
