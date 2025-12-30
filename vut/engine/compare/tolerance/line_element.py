"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Polymorphic Slotted LineElements (High Performance).

OPTIMIZATIONS:
- Polymorphic Dispatch: Bypasses 'match' overhead for hot-loop comparisons.
- Manual __slots__: Minimal memory footprint per type.
- Base-Class Pooling: Centralized Flyweight logic in LineElement.__new__.
- Immutability: Protected against assignment via __setattr__ lock.
________________________________________________________________________________
"""
import vut.engine.compare.edit_operations.string as edit_distance_string
from   vut.engine.compare.engine.core            import E_Verdict
from   enum         import IntEnum
from   dataclasses  import dataclass
import regex        as re
import sys
import weakref

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
    """Base class for all LineElements. 
    Handles Flyweight pooling and immutability.
    """
    __slots__ = ('tolerance_id', '_content', '__weakref__')
    _pool = weakref.WeakValueDictionary()

    def __new__(cls, tolerance_id, content, *args):
        # 1. Fast Interning
        content = sys.intern(content)
        
        # 2. Pooling logic (Selective: Numbers and Patterns are usually unique)
        if tolerance_id in (E_ToleranceId.NUMERIC, E_ToleranceId.EQUIVALENCE_PATTERN):
            instance = object.__new__(cls)
            object.__setattr__(instance, 'tolerance_id', tolerance_id)
            object.__setattr__(instance, '_content', content)
            return instance

        key = (cls, tolerance_id, content)
        if (instance := cls._pool.get(key)):
            return instance

        # 3. Create new polymorphic instance
        instance = object.__new__(cls)
        object.__setattr__(instance, 'tolerance_id', tolerance_id)
        object.__setattr__(instance, '_content', content)
        cls._pool[key] = instance
        return instance

    def __init__(self, *args): pass

    def __setattr__(self, name, value):
        raise AttributeError("LineElement is read-only")

    @staticmethod
    def from_match(tid: E_ToleranceId, content: str, numeric_tolerance_ratio: float, pattern_i_set=None):
        match tid:
            case E_ToleranceId.NUMERIC:
                return LineElementNumber(content, numeric_tolerance_ratio)
            case E_ToleranceId.EQUIVALENCE_PATTERN:
                return LineElementEquivalencePattern(content, pattern_i_set)
            case E_ToleranceId.VISIBLE_NOTHING:
                return LineElementVisibleNothing(content)
            case E_ToleranceId.ANALOGY:
                return LineElementAnalogy(content)
            case E_ToleranceId.SEPERATOR:
                return LineElementSeparator(content)
            case _:
                return LineElementString(content)

    def compare(self, nominal):
        """Standard polymorphic entrance."""
        if self is nominal:
            return E_Verdict.EQUIVALENT, None
        
        # Cross-type logic (Visible Nothing)
        s_tid, n_tid = self.tolerance_id, nominal.tolerance_id
        if s_tid == E_ToleranceId.VISIBLE_NOTHING:
            return (E_Verdict.EQUIVALENT if n_tid == E_ToleranceId.VISIBLE_NOTHING 
                    else E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING), None
        if n_tid == E_ToleranceId.VISIBLE_NOTHING:
            return E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING, None

        if s_tid != n_tid:
            return E_Verdict.MISFIT, None

        return self._compare(nominal)

    def is_equivalent(self, nominal, analogy_db):
        if self is nominal: return True
        verdict_id, analogy = self.compare(nominal)
        return verdict_id == E_Verdict.EQUIVALENT and analogy_db.is_consistent(analogy)

    @property
    def string(self): return self._content
    def __len__(self): return len(self._content)
    def __hash__(self): return id(self)
    def __repr__(self): return "%s '%s'" % (self.tolerance_id.name, self._content)

class LineElementString(LineElement):
    __slots__ = ()
    def __new__(cls, content):
        return LineElement.__new__(cls, E_ToleranceId.STRING, content)
    def _compare(self, nominal):
        if self._content == nominal._content:
            return E_Verdict.EQUIVALENT, None
        return E_Verdict.DIFFERENT, None
    def edit_distance_relative(self, nominal):
        max_l = max(len(self._content), len(nominal._content))
        if max_l == 0: return 0.0
        return float(edit_distance_string.do(self._content, nominal._content)) / max_l

class LineElementNumber(LineElement):
    __slots__ = ('number', 'epsilon')
    def __new__(cls, content, ratio=0.0):
        instance = LineElement.__new__(cls, E_ToleranceId.NUMERIC, content)
        try:              v = float(content)
        except Exception: v = 0.0
        object.__setattr__(instance, 'number', v)
        object.__setattr__(instance, 'epsilon', abs(v * (ratio or 0.0)))
        return instance

    def _compare(self, nominal):
        if abs(self.number - nominal.number) <= nominal.epsilon:
            return E_Verdict.EQUIVALENT, None
        return E_Verdict.DIFFERENT, None

    def edit_distance_relative(self, nominal):
        diff = abs(self.number - nominal.number)
        error = diff - nominal.epsilon
        if error <= 0: return 0.0
        mag = max(abs(self.number), abs(nominal.number))
        return error / mag if mag != 0 else 1.0

class LineElementEquivalencePattern(LineElement):
    __slots__ = ('indices',)
    def __new__(cls, content, indices):
        instance = LineElement.__new__(cls, E_ToleranceId.EQUIVALENCE_PATTERN, content)
        object.__setattr__(instance, 'indices', frozenset(indices))
        return instance

    def _compare(self, nominal):
        if not self.indices.isdisjoint(nominal.indices):
            return E_Verdict.EQUIVALENT, None
        return E_Verdict.DIFFERENT, None

    def edit_distance_relative(self, nominal):
        if not self.indices.isdisjoint(nominal.indices): return 0.0
        max_l = max(len(self._content), len(nominal._content))
        if max_l == 0: return 0.0
        return float(edit_distance_string.do(self._content, nominal._content)) / max_l

class LineElementAnalogy(LineElement):
    __slots__ = ()
    def __new__(cls, content):
        return LineElement.__new__(cls, E_ToleranceId.ANALOGY, content)
    def _compare(self, nominal):
        return E_Verdict.EQUIVALENT, (self._content, nominal._content)
    def edit_distance_relative(self, nominal): return 0.0

class LineElementSeparator(LineElement):
    __slots__ = ()
    def __new__(cls, content):
        return LineElement.__new__(cls, E_ToleranceId.SEPERATOR, content)
    def _compare(self, nominal): return E_Verdict.EQUIVALENT, None
    def edit_distance_relative(self, nominal):
        max_l = max(len(self._content), len(nominal._content))
        if max_l == 0: return 0.0
        return float(edit_distance_string.do(self._content, nominal._content)) / max_l

class LineElementVisibleNothing(LineElement):
    __slots__ = ()
    def __new__(cls, content):
        return LineElement.__new__(cls, E_ToleranceId.VISIBLE_NOTHING, content)
    def _compare(self, nominal): return E_Verdict.EQUIVALENT, None
    def edit_distance_relative(self, nominal): return 0.0

