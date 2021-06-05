"""SPDX License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________

PURPOSE: Definition of core structures, namely 'E_Verdict' and 'Configuration'.
_______________________________________________________________________________
"""
from enum import Enum, auto

class E_Verdict(Enum):
    MISFIT           = auto()
    DIFFERENT        = auto()
    EQUIVALENT       = auto()
    ERROR_IN_SUBJECT = auto()
    ERROR_IN_NOMINAL = auto()

