"""SPDX License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________

PURPOSE: Definition of core structures, namely 'E_Verdict' and 'Configuration'.
_______________________________________________________________________________
"""
from enum import Enum, IntEnum, auto

class E_Verdict(Enum):
    MISFIT           = auto()
    DIFFERENT        = auto()
    EQUIVALENT       = auto()
    ERROR_IN_SUBJECT = auto()
    ERROR_IN_NOMINAL = auto()

class E_PotpourriBorder(Enum):
    NONE  = auto()
    BEGIN = auto()
    END   = auto()

class E_EditId(IntEnum):
    """Operations moving/substituting in subject to produce nominal.
    """
    GOOD            = 0  # Subject and nominal 'element' object are equivalent.
    GOOD_TOLERATED  = 1  # == GOOD, only that content may differ (used in diff-display).
    GOOD_INSERT     = 9  # == GOOD, nominal has a 'visible nothing' where subject has nothing.
    GOOD_DELETE     = 8  # == GOOD, subject has a 'visible nothing' where nominal has nothing.
    TRANSPOSE       = 2  # Heal: Two 'element' objects in subject are transposed.
    INSERT          = 3  # Heal: 'element' from nominal is inserted.
    DELETE          = 4  # Heal: 'element' from subject is deleted.
    SUBSTITUTE      = 5  # Bad:  Content of subject and nominal 'element' differs.
    SUBSTITUTE_TYPE = 6  # Bad:  Type of subject and nominal 'element' differs.
    NONE            = 7  # No operation

