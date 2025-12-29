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
from   typing      import Any
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

    Instead of extraing a string corresponding to the LineElement, it 
    refers to the according sub-string by indices into a global string 
    '.reference'.

     .start          index pointing into '.reference' where the 
                     according pattern gettings.
     .end            index pointing into '.reference' after the 
                     last character.
     .reference      text fragment where the pattern occured.
    """
    # OPTIMIZATION: __slots__ saves massive memory by removing __dict__ overhead
    __slots__ = ('tolerance_id', 'start', 'end', 'reference', '_content')

    # @typechecked -- likely to be too expensive, called mio-s of times!
    def __init__(self, tolerance_id: E_ToleranceId, content):
        self.tolerance_id = tolerance_id
        
        # OPTIMIZATION: Snapshot + Interning (The "Pool" Approach)
        # We slice ONCE here. Accessing .string later is now O(1).
        # sys.intern() deduplicates memory, so 1000 "foo" objects share 1 address.
        self._content = sys.intern(content)

    @staticmethod
    # @typechecked likely to be too expensive: called mios of times
    def from_match(pattern: TolerancePattern, m: Any, global_string: str, numeric_tolerance_ratio: float, pattern_i_set=None):
        """RETURNS: A 'LineElement' object based on the provided match data
                    inside this object.
        """
        tolerance_id = pattern.id
        start, end   = m.span()
        # LineElementString objects are the 'waste' of pattern finding.
        # They are not generated from tokens.
        assert tolerance_id != E_ToleranceId.STRING

        match tolerance_id:
            case E_ToleranceId.VISIBLE_NOTHING:
                return LineElementVisibleNothing(global_string[start:end])
            case E_ToleranceId.EQUIVALENCE_PATTERN:
                indices = pattern_i_set if pattern_i_set is not None else {pattern.pattern_index}
                return LineElementEquivalencePattern(start, end, global_string, indices)
            case E_ToleranceId.NUMERIC:
                return LineElementNumber(global_string[start:end], numeric_tolerance_ratio)
            case E_ToleranceId.ANALOGY:
                return LineElementAnalogy(start, end, global_string)
            case E_ToleranceId.SEPERATOR:
                return LineElementSeparator(global_string[start:end])
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
        if self.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
            if nominal.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
                return E_Verdict.EQUIVALENT, None
            else:
                return E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING, None
        elif nominal.tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
            return E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING, None

        elif self.tolerance_id != nominal.tolerance_id:
            return E_Verdict.MISFIT, None

        verdict, analogy = self._compare(nominal)
        if verdict:
            return E_Verdict.EQUIVALENT, analogy
        else:
            return E_Verdict.DIFFERENT, analogy

    def edit_distance_relative(self, nominal):
        """RETURNS: ratio of edit distance / max. possible edit distance.
        """
        # VISIBLE_NOTHING *must* be removed before the comparison of two sequences!
        assert self.tolerance_id    != E_ToleranceId.VISIBLE_NOTHING
        assert nominal.tolerance_id != E_ToleranceId.VISIBLE_NOTHING

        # Use cached _content for fast length check
        max_length = max(len(self._content), len(nominal._content))
        if max_length == 0:
            return 0
        else:
            # Use cached _content to avoid re-slicing
            return float(edit_distance_string.do(self._content, nominal._content)) / max_length

    def is_equivalent(self, nominal, analogy_db):
        """RETURNS: True, if self is equivalent to 'nominal' under the given
                          analogy_db; 
                    False, else.
        """
        verdict_id, analogy = self.compare(nominal)
        if   verdict_id != E_Verdict.EQUIVALENT:    return False
        elif not analogy_db.is_consistent(analogy): return False
        else:                                       return True

    @property
    def string(self):
        return self._content

    def _compare(self, nominal):
        """RETURNS: [0] True, any way.
                    [1] None
        """
        assert False # pragma no cover

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
        """RETURNS: [0] True, any way.
                    [1] None
        """
        return True, None

    def __hash__(self):
        return hash(self.string) ^ hash(E_ToleranceId.SEPERATOR)

class LineElementString(LineElement):
    def __init__(self, start, end, string):
        LineElement.__init__(self, E_ToleranceId.STRING,  string[start:end])

    def _compare(self, nominal):
        """RETURNS: [0] True, any way.
                    [1] None
        """
        return self.string == nominal.string, None

    def __hash__(self):
        return hash(self.string) ^ hash(self.tolerance_id)

class LineElementAnalogy(LineElement):
    def __init__(self, start, end, string):
        LineElement.__init__(self, E_ToleranceId.ANALOGY,  string[start:end])

    def _compare(self, nominal):
        """RETURNS: [0] True, any way.
                    [1] Required analogy

        The judgement whether the subject and the nominal fit must be made
        by the analogy_db.
        """
        return True, (self.string, nominal.string)

    def edit_distance_relative(self, nominal):
        return 0 # Analogies are never wrong

    # NOTE: '__hash__' cannot be overwritten here.
    #       Equivalence is derived later as a function of consistency.

class LineElementNumber(LineElement):
    __slots__ = ('number', 'numeric_tolerance_ratio')

    def __init__(self, content, numeric_tolerance_ratio=None):
        assert numeric_tolerance_ratio is None or 0.0 <= numeric_tolerance_ratio <= 1.0
        LineElement.__init__(self, E_ToleranceId.NUMERIC, content)
        self.number  = float(self.string)
        self.numeric_tolerance_ratio = 0 if numeric_tolerance_ratio is None \
                                       else numeric_tolerance_ratio

    def edit_distance_relative(self, nominal):
        max_number = max(self.number, nominal.number)
        delta      = abs(self.number - nominal.number)
        if max_number == 0: return 0.0 # Guard against div/0
        return delta / max_number

    def _compare(self, nominal):
        """RETURNS: [0] True, if number 'subject' lies in the epsilon range
                              of number 'nominal'.
                        False, else.
                    [1] None (no analogy required)
        """
        ## assert self.epsilon is None        # Subject does not define precision!
        nominal_epsilon = self.number * nominal.numeric_tolerance_ratio

        verdict = abs(self.number - nominal.number) <= nominal_epsilon
        return verdict, None

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineElement:%s(\"%s,tol=%s\")" % (self.tolerance_id.name, self.string, self.numeric_tolerance_ratio), []

    # NOTE: '__hash__' cannot be overwritten here; see '_compare()'.
    #       Equivalence is based on deviation. Equivalency can ONLY
    #       be investigated by relating to LineElement-objects.

class LineElementVisibleNothing(LineElement):
    def __init__(self, content):
        LineElement.__init__(self, E_ToleranceId.VISIBLE_NOTHING, content)

    def edit_distance_relative(self, nominal):
        return 0

    def _compare(self, nominal):
        """RETURNS: [0] True, if number 'subject' lies in the epsilon range
                              of number 'nominal'.
                        False, else.
                    [1] None (no analogy required)
        """
        return True, None

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineElement:%s(\"%s\")" % (self.tolerance_id.name, self.string), []

class LineElementEquivalencePattern(LineElement):
    __slots__ = ('pattern_index_set',)

    def __init__(self, start, end, string, pattern_index_set):
        LineElement.__init__(self, E_ToleranceId.EQUIVALENCE_PATTERN,  string[start:end])
        # Indices of patterns which are matched.
        self.pattern_index_set = set(pattern_index_set)

    def _compare(self, nominal):
        """RETURNS: [0] True, any way.
                    [1] None
        """
        return not nominal.pattern_index_set.isdisjoint(self.pattern_index_set), None

    def edit_distance_relative(self, nominal):
        if self._compare(nominal)[0]:
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

