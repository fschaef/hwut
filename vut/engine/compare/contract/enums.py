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

        Delegates to 'contract/semantics.py' -- the single source
        of the comparison semantics. The import is LATE only because
        'semantics' imports this module for its own vocabulary; both
        now sit in the contract, so the pair is a leaf together and
        nothing outside waits on either.
        """
        from vut.engine.compare.contract.semantics import is_equivalent_verdict
        return is_equivalent_verdict(x)

class E_Chunk(Enum):
    LINE_SEQUENCE = auto()
    LINE          = auto()
    POTPOURRI     = auto()
    VERBATIM      = auto()
    IGNORE        = auto()
    UNACCEPTED    = auto()
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


class RegionSyntaxError(Exception):
    """Region framing of the INPUT is broken (unknown handler, bad
    parameter, nesting, stray/missing '####'). Deliberately loud: a
    region marker must never be silently reinterpreted as content.

    IN THE CONTRACT because THE CALLER CATCHES IT: it crosses the
    component's wall, and what crosses is vocabulary, not private
    matter.
    """
    def __init__(self, line_n, message):
        self.line_n = line_n
        super().__init__("line %s: %s" % (line_n, message))
