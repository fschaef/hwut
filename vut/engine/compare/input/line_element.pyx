# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: LineElements -- carrying information of patterns found in text lines.
Optimized via Cython for high-speed polymorphic dispatch.
________________________________________________________________________________
"""
import vut.engine.compare.edit_operations.string as edit_distance_string
from vut.engine.compare.engine.core import E_Verdict
import regex as re
import sys

# cpdef enum is the fastest: C-integers inside .pyx, visible constants in Python.
cpdef enum E_ToleranceId:
    STRING = 1
    VISIBLE_NOTHING = 2
    ANALOGY = 3
    NUMERIC = 4
    EQUIVALENCE_PATTERN = 5
    SEPERATOR = 6

cdef class TolerancePattern:
    """Extension class for pattern metadata. Speeds up attribute access in Cython."""
    cdef public int id
    cdef public object pattern, pattern_index
    def __init__(self, int id, object pattern, object pattern_index):
        self.id = id; self.pattern = pattern; self.pattern_index = pattern_index

cdef class LineElement:
    """Base class for all 'LineElement' classes. Optimized via C-structs."""
    cdef public int tolerance_id
    cdef public object start, end, reference
    cdef public str _content
    cdef object __weakref__
    def __init__(self, int tolerance_id, str content):
        self.tolerance_id = tolerance_id
        self._content = sys.intern(content)
    @staticmethod
    def from_match(TolerancePattern pattern, str content, double numeric_tolerance_ratio, pattern_i_set=None):
        cdef int tid = pattern.id
        if tid == 2: return LineElementVisibleNothing(content)
        if tid == 5:
            idx = pattern_i_set if pattern_i_set is not None else {pattern.pattern_index}
            return LineElementEquivalencePattern(content, idx)
        if tid == 4: return LineElementNumber(content, numeric_tolerance_ratio)
        if tid == 3: return LineElementAnalogy(content)
        if tid == 6: return LineElementSeparator(content)
        assert False
    cpdef tuple compare(self, LineElement nominal):
        if self.tolerance_id == 2: # VISIBLE_NOTHING
            return (E_Verdict.EQUIVALENT, None) if nominal.tolerance_id == 2 else (E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING, None)
        elif nominal.tolerance_id == 2: return E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING, None
        elif self.tolerance_id != nominal.tolerance_id: return E_Verdict.MISFIT, None
        cdef bint verdict
        cdef object analogy
        verdict, analogy = self._compare(nominal)
        return (E_Verdict.EQUIVALENT if verdict else E_Verdict.DIFFERENT), analogy
    cpdef double edit_distance_relative(self, LineElement nominal):
        cdef double max_l = max(len(self._content), len(nominal._content))
        return float(edit_distance_string.do(self._content, nominal._content)) / max_l if max_l != 0 else 0.0
    def is_equivalent(self, nominal, analogy_db):
        verdict_id, analogy = self.compare(nominal)
        return verdict_id == E_Verdict.EQUIVALENT and analogy_db.is_consistent(analogy)
    @property
    def string(self): return self._content
    def _compare(self, nominal): assert False
    def __hash__(self): return hash(self.tolerance_id)
    def __len__(self): return len(self._content)
    def __repr__(self): return "%s '%s'" % (E_ToleranceId(self.tolerance_id).name, self._content)
    def __pretty__(self): return "LineElement:%s(\"%s\")" % (E_ToleranceId(self.tolerance_id).name, self._content), []

cdef class LineElementSeparator(LineElement):
    def __init__(self, content): LineElement.__init__(self, 6, content)
    cpdef tuple _compare(self, LineElement nominal): return True, None
    def __hash__(self): return hash(self._content) ^ hash(6)

cdef class LineElementString(LineElement):
    def __init__(self, content): LineElement.__init__(self, 1, content)
    cpdef tuple _compare(self, LineElement nominal): return self._content == nominal._content, None
    def __hash__(self): return hash(self._content) ^ hash(1)

cdef class LineElementAnalogy(LineElement):
    def __init__(self, content): LineElement.__init__(self, 3, content)
    cpdef tuple _compare(self, LineElement nominal): return True, (self._content, nominal._content)
    cpdef double edit_distance_relative(self, LineElement nominal): return 0.0

cdef class LineElementNumber(LineElement):
    cdef public double number, epsilon
    def __init__(self, content, ratio=None):
        LineElement.__init__(self, 4, content)
        self.number = float(content)
        self.epsilon = self.number * ratio if ratio else 0.0
    cpdef double edit_distance_relative(self, LineElement nominal):
        cdef LineElementNumber n = <LineElementNumber>nominal
        if self.number == n.number: return 0.0
        cdef double err = max(abs(self.number - n.number) - n.epsilon, 0.0)
        if err == 0.0: return 0.0
        cdef double mag = max(abs(self.number), abs(n.number))
        return err / mag if mag != 0 else 1.0
    cpdef tuple _compare(self, LineElement nominal):
        return abs(self.number - (<LineElementNumber>nominal).number) <= (<LineElementNumber>nominal).epsilon, None
    def __pretty__(self): return "LineElement:NUMERIC(\"%s,tol=%s\")" % (self.number, self.epsilon), []

cdef class LineElementVisibleNothing(LineElement):
    def __init__(self, content): LineElement.__init__(self, 2, content)
    cpdef double edit_distance_relative(self, LineElement nominal): return 0.0
    cpdef tuple _compare(self, LineElement nominal): return True, None
    def __pretty__(self): return "LineElement:VISIBLE_NOTHING(\"%s\")" % (self._content), []

cdef class LineElementEquivalencePattern(LineElement):
    cdef public object pattern_index_set
    def __init__(self, content, idx_set):
        LineElement.__init__(self, 5, content)
        self.pattern_index_set = set(idx_set)
    cpdef tuple _compare(self, LineElement nominal):
        return not (<LineElementEquivalencePattern>nominal).pattern_index_set.isdisjoint(self.pattern_index_set), None
    cpdef double edit_distance_relative(self, LineElement nominal):
        return 0.0 if self._compare(nominal)[0] else LineElement.edit_distance_relative(self, nominal)
    def __repr__(self): return "%s %s '%s'" % ("EQUIVALENCE_PATTERN", sorted(self.pattern_index_set), self._content)
