"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: LineElements -- carrying information of patterns found in text lines.

The 'PatternFinder' identifies patterns in text and writes their meaning or
content into dedicated objects, namely 'LineElements'.

A 'LineElement' stands for a specific kind of tolerance to be applied. For
example 'LineElementNumber' applies numeric precision constraints. Other
line elements only require that the string matches some regular expressions.

LineElement provide:

   .compare(other)  --> if line element is equivalent to 'other'.
   
   .edit_distance_relative(other) --> a value between 0 to 1 indicating 
                                     the amount of edit operations to 
                                     transform 'self' to 'other'.
________________________________________________________________________________
"""
import vut.engine.compare.edit_operations.string as     edit_distance_string
from   vut.engine.compare.engine.core            import E_Verdict

from   enum        import IntEnum
import regex       as re
from   dataclasses import dataclass
import sys  # REQUIRED for sys.intern optimization => store same strings once

class E_ToleranceId(IntEnum):
    STRING              = 1
    VISIBLE_NOTHING     = 2
    ANALOGY             = 3
    NUMERIC             = 4
    EQUIVALENCE_PATTERN = 5
    SEPERATOR           = 6

@dataclass
class TolerancePattern:
    id:            int
    pattern:       re.Pattern | None
    pattern_index: int | None

class LineElement:
    """Base class for all 'LineElement' classes. It contains:

     .tolerance_id:  identifies the line element type, i.e. the type of 
                     tolerance which is to be applied.

     .string:   reference to a string in the sys.intern() string pool 
                => same strings are kept as same objects.
    """
    # OPTIMIZATION: __slots__ saves massive memory by removing __dict__ overhead
    __slots__ = ('tolerance_id', 'string')

    # @typechecked -- likely to be too expensive, called mio-s of times!
    def __init__(self, tolerance_id: E_ToleranceId, content):
        self.tolerance_id = tolerance_id
        
        # OPTIMIZATION: Snapshot + Interning (The "Pool" Approach)
        # We slice ONCE here. Accessing .string later is now O(1).
        # sys.intern() deduplicates memory, so 1000 "foo" objects share 1 address.
        self.string = sys.intern(content)

    def __lt__(self, other):
        return id(self) < id(other) # quick tiebreaker

    @staticmethod
    # @typechecked likely to be too expensive: called mios of times
    def from_match(pattern: TolerancePattern, content: str, numeric_tolerance_ratio: float, pattern_i_set=None):
        """RETURNS: A 'LineElement' object based on the provided match data
                    inside this object.
        """
        tolerance_id = pattern.id
        # LineElementString objects are the 'waste' of pattern finding.
        # They are not generated from tokens.
        assert tolerance_id != E_ToleranceId.STRING

        match tolerance_id:
            case E_ToleranceId.VISIBLE_NOTHING:
                return LineElementVisibleNothing(content)
            case E_ToleranceId.EQUIVALENCE_PATTERN:
                indices = pattern_i_set if pattern_i_set is not None else {pattern.pattern_index}
                return LineElementEquivalencePattern(content, indices)
            case E_ToleranceId.NUMERIC:
                return LineElementNumber(content, numeric_tolerance_ratio)
            case E_ToleranceId.ANALOGY:
                return LineElementAnalogy(content)
            case E_ToleranceId.SEPERATOR:
                return LineElementSeparator(content)
            case _:
                assert False # pragma: no cover

    def compare(self, nominal):
        """RETURNS: [0] MISFIT,     if 'other' is of another class.
                        DIFFERENT,  if 'other' is of same kind, but content differs.
                        EQUIVALENT, if 'other' is equivalent to 'self'.
                    [1] analogy required for the EQUIVALENT to hold,
                        if it is equivalent.
        """
        # VISIBLE_NOTHING *must* be removed before the comparison of two sequences!
        # LineElementAnalogy implements 'compare()' completely self
        # LineElementVisibleNothing implements 'compare()' 
        # NOT: 'if analogy_db and not analogy_db.is_consistent(analogy): return False'
        if self.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
            if nominal.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
                return E_Verdict.EQUIVALENT, None
            else:
                return E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING, None
        elif nominal.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
            return E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING, None

        elif self.tolerance_id != nominal.tolerance_id:
            return E_Verdict.MISFIT, None

        verdict = self._compare(nominal)
        if verdict: return E_Verdict.EQUIVALENT, None
        else:       return E_Verdict.DIFFERENT, None

    def edit_distance_relative(self, nominal):
        """RETURNS: ratio of edit distance / max. possible edit distance.
        """
        # VISIBLE_NOTHING *must* be removed before the comparison of two sequences!
        ## assert self.tolerance_id    != E_ToleranceId.VISIBLE_NOTHING
        ## assert nominal.tolerance_id != E_ToleranceId.VISIBLE_NOTHING

        # Use cached string for fast length check
        max_length = max(len(self.string), len(nominal.string))
        if max_length == 0:
            return 0
        else:
            # Use cached string to avoid re-slicing
            return float(edit_distance_string.do(self.string, nominal.string)) / max_length

    def is_equivalent(self, nominal, analogy_db):
        """RETURNS: True, if self is equivalent to 'nominal' under the given
                          analogy_db; 
                    False, else.
        """
        verdict_id, _ = self.compare(nominal)
        # LineElementAnalogy implements 'is_equivalent()' completely self
        # NOT: 'if analogy_db and not analogy_db.is_consistent(analogy): return False'
        return verdict_id == E_Verdict.EQUIVALENT

    def _compare(self, nominal):
        raise NotImplementedError

    def __hash__(self):
        # NOTE: This function is only overwritten if it is safe to assume
        #       that two equivalent 'LineElement' objects have the same hash value!
        return hash(self.tolerance_id)

    def __repr__(self):
        return "%s '%s'" % (self.tolerance_id.name, self.string)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineElement:%s(\"%s\")" % (self.tolerance_id.name, self.string), []

class LineElementSeparator(LineElement):
    def __init__(self, content):
        LineElement.__init__(self, E_ToleranceId.SEPERATOR, content)

    def _compare(self, nominal):
        return True

    def __hash__(self):
        return hash(self.string) ^ hash(E_ToleranceId.SEPERATOR)

class LineElementString(LineElement):
    def __init__(self, content):
        LineElement.__init__(self, E_ToleranceId.STRING, content)

    def _compare(self, nominal):
        return self.string == nominal.string

    def __hash__(self):
        return hash(self.string) ^ hash(self.tolerance_id)

class LineElementAnalogy(LineElement):
    def __init__(self, content):
        LineElement.__init__(self, E_ToleranceId.ANALOGY, content)

    def compare(self, nominal):
        """RETURNS: [0] MISFIT,     if 'other' is of another class.
                        DIFFERENT,  if 'other' is of same kind, but content differs.
                        EQUIVALENT, if 'other' is equivalent to 'self'.
                    [1] analogy required for the EQUIVALENT to hold,
                        if it is equivalent.
        """
        # VISIBLE_NOTHING *must* be removed before the comparison of two sequences!
        if nominal.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
            return E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING, None
        elif self.tolerance_id != nominal.tolerance_id:
            return E_Verdict.MISFIT, None
        else:
            # 'LineElementAnalogy' implements its own 'self.compare()'
            return E_Verdict.EQUIVALENT, (self.string, nominal.string)

    def is_equivalent(self, nominal, analogy_db):
        if self.tolerance_id != nominal.tolerance_id: 
            return False
        elif self.string == nominal.string:       
            return True
        else:
            # IMPORTANT: analogy_db MUST be defined here!
            #            this is the somewhat 'global' analogy_db
            return analogy_db.is_consistent((self.string, nominal.string))

    def edit_distance_relative(self, nominal):
        return 0 # Analogies are never wrong

    # NOTE: '__hash__' cannot be overwritten here.
    #       Equivalence is derived later as a function of consistency.

class LineElementNumber(LineElement):
    __slots__ = ('number', 'epsilon')

    def __init__(self, content, numeric_tolerance_ratio=None):
        assert numeric_tolerance_ratio is None or 0.0 <= numeric_tolerance_ratio <= 1.0
        LineElement.__init__(self, E_ToleranceId.NUMERIC, content)
        self.number  = float(self.string)
        self.epsilon = self.number * numeric_tolerance_ratio if numeric_tolerance_ratio else 0.0

    def edit_distance_relative(self, nominal):
        if self.number == nominal.number: return 0 # quick pass
        # diff - tolerance (aux): distance is 0 if within dead-zone.
        error = max(abs(self.number - nominal.number) - self.epsilon, 0.0)
        if error == 0.0: return 0.0 # quick pass
        mag = max(abs(self.number), abs(nominal.number))
        # NOTE: 'mag' cannot be zero, because self.val != nominal.val
        #       => check mag != 0 only as a guard rail against numeric weird events
        return error / mag if mag != 0 else 1.0 

    def _compare(self, nominal):
        """RETURNS: True, if number 'subject' lies in the epsilon range
                          of number 'nominal'.
                    False, else.
                    None (no analogy required)
        """
        return abs(self.number - nominal.number) <= nominal.epsilon

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineElement:%s(\"%s,tol=%s\")" % (self.tolerance_id.name, self.number, self.epsilon), []

    # NOTE: '__hash__' cannot be overwritten here; see '_compare()'.
    #       Equivalence is based on deviation. Equivalency can ONLY
    #       be investigated by relating to LineElement-objects.

class LineElementVisibleNothing(LineElement):
    def __init__(self, content):
        LineElement.__init__(self, E_ToleranceId.VISIBLE_NOTHING, content)

    def edit_distance_relative(self, nominal):
        return 0

    def compare(self, nominal):
        """RETURNS: [0] MISFIT,     if 'other' is of another class.
                        DIFFERENT,  if 'other' is of same kind, but content differs.
                        EQUIVALENT, if 'other' is equivalent to 'self'.
                    [1] None, anyways
        """
        if nominal.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
            return E_Verdict.EQUIVALENT, None
        else:
            return E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING, None

    def _compare(self, nominal):
        return True

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineElement:%s(\"%s\")" % (self.tolerance_id.name, self.string), []

class LineElementEquivalencePattern(LineElement):
    __slots__ = ('pattern_index_set',)

    def __init__(self, content, pattern_index_set):
        LineElement.__init__(self, E_ToleranceId.EQUIVALENCE_PATTERN, content)
        # Indices of patterns which are matched.
        self.pattern_index_set = set(pattern_index_set)

    def _compare(self, nominal):
        """RETURNS: True, if subject and nominal match a common pattern
                    False, else.
        """
        return not nominal.pattern_index_set.isdisjoint(self.pattern_index_set)

    def edit_distance_relative(self, nominal):
        if not nominal.pattern_index_set.isdisjoint(self.pattern_index_set):
            return 0
        else:
            return LineElement.edit_distance_relative(self, nominal)

    # NOTE: '__hash__' cannot be overwritten here; see '_compare()'.
    #       Equivalence is based on intersection. Equivalency can ONLY
    #       be investigated by relating two LineElement-objects.

    def __repr__(self):
        tolerance_str   = self.tolerance_id.name
        pattern_ids_str = list(sorted(self.pattern_index_set)) 
        content_str     = self.string
        return "%s %s '%s'" % (tolerance_str, pattern_ids_str, content_str)

