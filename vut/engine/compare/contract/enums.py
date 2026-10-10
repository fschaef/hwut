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
    CONSTRAINT_VIOLATION = auto()
    POINT_CLOUD   = auto()
    TABLE         = auto()
    TERMINAL      = auto()
    VOID          = auto()
    NONE          = auto()

#  THE BAD REGIONS (C-21): stretches whose content a comparison can never
#  pass -- 'unaccepted' (nobody has judged it, C-9) and
#  'constraint-violation' (a run found a constraint broken there, services
#  E-123). Both take whatever stands opposite (C-10) and fail while they
#  hold a line; they differ only in what they say.
BAD_CHUNK_SET         = frozenset((E_Chunk.UNACCEPTED,
                                   E_Chunk.CONSTRAINT_VIOLATION))
BAD_REGION_NAME_TUPLE = ("unaccepted", "constraint-violation")

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

    'side' names the stream at fault: "subject" (the output), "nominal"
    (the GOOD file), or None where the raiser cannot tell. THE ZIP STAGE
    SETS IT, since it alone holds one pipe per stream; a fault found
    while comparing is the nominal's by the handlers' own law.
    """
    def __init__(self, line_n, message):
        self.line_n = line_n
        self.side   = None
        super().__init__("line %s: %s" % (line_n, message))
