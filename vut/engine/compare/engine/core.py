"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________

PURPOSE: Definition of core structures, namely 'E_Verdict' and 'Configuration'.
_______________________________________________________________________________
"""
from enum import Enum, IntEnum, auto

class E_Verdict(Enum):
    MISFIT                             = auto()
    DIFFERENT                          = auto()
    EQUIVALENT                         = auto()
    EQUIVALENT_SUBJECT_VISIBLE_NOTHING = auto()
    EQUIVALENT_NOMINAL_VISIBLE_NOTHING = auto()
    ERROR_IN_SUBJECT                   = auto()
    ERROR_IN_NOMINAL                   = auto()

class E_PotpourriBorder(Enum):
    NONE  = auto()
    BEGIN = auto()
    END   = auto()

