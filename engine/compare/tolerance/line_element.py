"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
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
import ut.engine.compare.edit_operations.string as     edit_distance_string
from   ut.engine.compare.engine.core           import E_Verdict
from   ut.engine.quex.typed                   import typed

from   enum import IntEnum

class E_ToleranceId(IntEnum):
    STRING              = 1
    VISIBLE_NOTHING     = 2
    ANALOGY             = 3
    NUMERIC             = 4
    EQUIVALENCE_PATTERN = 5


class Token:
    """The PatternFinder calls a function 
        
           _find_first_match()          --> 'Token'
    
    which returns an object of class 'Token'. By means of this object the
    'LineElement' is according produced via:

           LineElement.from_Token(...)  --> 'LineElement'

    """
    def __init__(self):
        self.tolerance_id  = None
        self.start         = None
        self.end           = None
        self.pattern_i_set = None

    def set(self, tolerance, span):
        self.start        = span[0]
        self.end          = span[1]
        self.tolerance_id = tolerance.id
        if tolerance.id == E_ToleranceId.EQUIVALENCE_PATTERN:
            self.pattern_i_set = set([tolerance.pattern_index])

    def add(self, tolerance):
        if self.tolerance_id == E_ToleranceId.EQUIVALENCE_PATTERN:
            self.pattern_i_set.add(tolerance.pattern_index)
        else:
            self.tolerance_id  = tolerance.id
            self.pattern_i_set = set([tolerance.pattern_index])


class LineElement:
    """Base class for all 'LineElement' classes. It contains:

     .tolerance_id:  identifies the line element type, i.e. the 
                     type of tolerance which is to be applied.
     .reference      text fragment where the pattern occured.
     .start          index pointing into '.reference' where the 
                     according pattern gettings.
     .end            index pointing into '.reference' after the 
                     last character.
    """
    @typed(tolerance_id=E_ToleranceId)
    def __init__(self, tolerance_id, start, end, string):
        self.tolerance_id = tolerance_id
        self.start        = start
        self.end          = end
        self.reference    = string

    @classmethod
    @typed(token=Token, global_string=str)
    def from_Token(cls, token, global_string, numeric_tolerance_ratio):
        """RETURNS: A 'LineElement' object based on the provided match data
                    inside this object.
        """
        # LineElementString objects are the 'waste' of pattern finding.
        # They are not generated from tokens.
        assert token.tolerance_id != E_ToleranceId.STRING

        tolerance_id = token.tolerance_id
        start, end   = token.start, token.end

        if tolerance_id == E_ToleranceId.VISIBLE_NOTHING:
            return None
        elif tolerance_id == E_ToleranceId.EQUIVALENCE_PATTERN:
            return LineElementEquivalencePattern(start, end, global_string,
                                          token.pattern_i_set)
        elif tolerance_id == E_ToleranceId.NUMERIC:
            return LineElementNumber(start, end, global_string,
                               numeric_tolerance_ratio)
        elif tolerance_id == E_ToleranceId.ANALOGY:
            return LineElementAnalogy(start, end, global_string)
        else:
            assert False # pragma: no cover

    def compare(self, nominal):
        """RETURNS: [0] MISFIT,     if 'other' is of another class.
                        DIFFERENT,  if 'other' is of same kind, but content differs.
                        EQUIVALENT, if 'other' is equivalent to 'self'.
                    [1] analogy required for the EQUIVALENT to hold,
                        if it is equivalent.
        """
        if self.tolerance_id != nominal.tolerance_id:
            return E_Verdict.MISFIT, None

        verdict, analogy = self._compare(nominal)
        if verdict:
            return E_Verdict.EQUIVALENT, analogy
        else:
            return E_Verdict.DIFFERENT, analogy

    def edit_distance_relative(self, nominal):
        """RETURNS: ratio of edit distance / max. possible edit distance.
        """
        max_length = max(len(self.string), len(nominal.string))
        if max_length == 0:
            return 0
        else:
            return float(edit_distance_string.do(self.string, nominal.string)) / max_length

    def is_equivalent(self, nominal, analogy_db):
        """RETURNS: True, if self is equivalent to 'nominal' under the given
                          analogy_db; False, else.
        """
        verdict_id, analogy = self.compare(nominal)
        if   verdict_id != E_Verdict.EQUIVALENT:    return False
        elif not analogy_db.is_consistent(analogy): return False
        else:                                       return True

    @property
    def string(self):
        return self.reference[self.start:self.end]

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
        return "(%i,%i): %s '%s'" % (self.start, self.end, self.tolerance_id.name, self.string)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'ut.engine.pretty.do()'.
        """
        return "LineElement:%s(\"%s\")" % (self.tolerance_id.name, self.string), []

class LineElementString(LineElement):
    def __init__(self, start, end, string):
        LineElement.__init__(self, E_ToleranceId.STRING, start, end, string)

    def _compare(self, nominal):
        """RETURNS: [0] True, any way.
                    [1] None
        """
        return self.string == nominal.string, None

    def __hash__(self):
        return hash(self.string) ^ hash(self.tolerance_id)

class LineElementAnalogy(LineElement):
    def __init__(self, start, end, string):
        LineElement.__init__(self, E_ToleranceId.ANALOGY, start, end, string)

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
    def __init__(self, start, end, string, numeric_tolerance_ratio=None):
        assert numeric_tolerance_ratio is None or 0.0 <= numeric_tolerance_ratio <= 1.0
        LineElement.__init__(self, E_ToleranceId.NUMERIC, start, end, string)
        self.number  = float(self.string)
        self.numeric_tolerance_ratio = 0 if numeric_tolerance_ratio is None \
                                       else numeric_tolerance_ratio

    def edit_distance_relative(self, nominal):
        max_number = max(self.number, nominal.number)
        delta      = abs(self.number - nominal.number)
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
        """RETURNS: Representation of object state formatted by 'ut.engine.pretty.do()'.
        """
        return "LineElement:%s(\"%s,tol=%s\")" % (self.tolerance_id.name, self.string, self.numeric_tolerance_ratio), []

    # NOTE: '__hash__' cannot be overwritten here; see '_compare()'.
    #       Equivalence is based on deviation. Equivalency can ONLY
    #       be investigated by relating to LineElement-objects.


class LineElementEquivalencePattern(LineElement):
    def __init__(self, start, end, string, pattern_index_set):
        LineElement.__init__(self, E_ToleranceId.EQUIVALENCE_PATTERN, start, end, string)
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
        return "(%i,%i): %s %s '%s'" % (self.start, self.end, self.tolerance_id.name,
                                        list(sorted(self.pattern_index_set)), self.string)

