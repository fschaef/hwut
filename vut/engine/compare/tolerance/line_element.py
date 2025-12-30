"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Unified "Boxed" LineElement using a frozen dataclass.

- Uses a frozen dataclass for automatic immutability (read-only attributes).
- slots=True ensures a minimal memory footprint (no __dict__).
- Flyweight pooling is implemented in __new__.
- Maintains the homogeneous "Box" structure with generic val/aux slots.
- Backward compatible factories and __repr__.
________________________________________________________________________________
"""
import vut.engine.compare.edit_operations.string as edit_distance_string
from   vut.engine.compare.engine.core            import E_Verdict
from   enum         import IntEnum
from   dataclasses  import dataclass
import regex        as re
import sys
import weakref
from   typing       import Any

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

@dataclass(frozen=True, slots=True, repr=False)
class LineElement:
    """A homogeneous frozen 'Box' for all line element types.
    
    The @dataclass(frozen=True) decorator automatically prevents assignment.
    The Flyweight pattern is implemented in __new__.
    """
    tolerance_id: E_ToleranceId
    _content:     str
    val:          Any = None
    aux:          Any = None
    __weakref__:  Any

    _pool = weakref.WeakValueDictionary()

    def __new__(cls, tolerance_id, content, val=None, aux=None):
        # 1. Standard Interning
        interned_content = sys.intern(content)
        
        # 2. Identity Key
        key = (tolerance_id, interned_content, val, aux)
        
        if (instance := cls._pool.get(key)):
            return instance

        # 3. Create the frozen instance
        instance = object.__new__(cls)
        # We must use object.__setattr__ because the instance is 'frozen' 
        # from the moment it is created.
        object.__setattr__(instance, 'tolerance_id', tolerance_id)
        object.__setattr__(instance, '_content', interned_content)
        object.__setattr__(instance, 'val', val)
        object.__setattr__(instance, 'aux', aux)
        
        cls._pool[key] = instance
        return instance

    def __init__(self, *args, **kwargs):
        # Dataclass generated __init__ is ignored as state is set in __new__
        pass

    @staticmethod
    def from_match(pattern: TolerancePattern, content: str, numeric_tolerance_ratio: float, pattern_i_set=None):
        tid = pattern.id
        match tid:
            case E_ToleranceId.NUMERIC:
                try:
                    num_val = float(content)
                except ValueError:
                    num_val = 0.0
                epsilon = abs(num_val * (numeric_tolerance_ratio or 0.0))
                return LineElement(tid, content, val=num_val, aux=epsilon)
            
            case E_ToleranceId.EQUIVALENCE_PATTERN:
                indices = frozenset(pattern_i_set if pattern_i_set is not None else (pattern.pattern_index,))
                return LineElement(tid, content, val=indices)
            
            case E_ToleranceId.VISIBLE_NOTHING | E_ToleranceId.ANALOGY | E_ToleranceId.SEPERATOR:
                return LineElement(tid, content)
            
            case _:
                return LineElement(E_ToleranceId.STRING, content)

    def compare(self, nominal):
        """Unified dispatch logic using match."""
        if self is nominal:
            return E_Verdict.EQUIVALENT, None

        s_tid, n_tid = self.tolerance_id, nominal.tolerance_id
        if s_tid != n_tid:
            return E_Verdict.MISFIT, None

        match s_tid:
            case E_ToleranceId.VISIBLE_NOTHING:
                return E_Verdict.EQUIVALENT, None
            case E_ToleranceId.NUMERIC:
                if abs(self.val - nominal.val) <= nominal.aux:
                    return E_Verdict.EQUIVALENT, None
                return E_Verdict.DIFFERENT, None
            case E_ToleranceId.EQUIVALENCE_PATTERN:
                if not self.val.isdisjoint(nominal.val):
                    return E_Verdict.EQUIVALENT, None
                return E_Verdict.DIFFERENT, None
            case E_ToleranceId.ANALOGY:
                return E_Verdict.EQUIVALENT, (self._content, nominal._content)
            case E_ToleranceId.SEPERATOR:
                return E_Verdict.EQUIVALENT, None
            case _: # STRING
                if self._content == nominal._content:
                    return E_Verdict.EQUIVALENT, None
                return E_Verdict.DIFFERENT, None

    def is_equivalent(self, nominal, analogy_db):
        if self is nominal: return True
        verdict_id, analogy = self.compare(nominal)
        return verdict_id == E_Verdict.EQUIVALENT and analogy_db.is_consistent(analogy)

    def edit_distance_relative(self, nominal):
        if self is nominal: return 0.0
        match self.tolerance_id:
            case E_ToleranceId.VISIBLE_NOTHING:
                return 0.0
            case E_ToleranceId.ANALOGY:
                return 0.0
            case E_ToleranceId.EQUIVALENCE_PATTERN:
                if not self.val.isdisjoint(nominal.val): return 0
                # Diff like a normal string
                max_l = max(len(self._content), len(nominal._content))
                if max_l == 0: return 0.0
                return float(edit_distance_string.do(self._content, nominal._content)) / max_l
            case E_ToleranceId.NUMERIC:
                if self.val == nominal.val: return 0 # quick pass
                # diff - tolerance (aux): distance is 0 if within dead-zone.
                error = max(abs(self.val - nominal.val) - nominal.aux, 0.0)
                if error == 0.0: return 0.0 # quick pass
                mag = max(abs(self.val), abs(nominal.val))
                # NOTE: 'mag' cannot be zero, because self.val != nominal.val
                #       => check mag != 0 only as a guard rail against numeric weird events
                return error / mag if mag != 0 else 1.0 
            case _:
                max_l = max(len(self._content), len(nominal._content))
                if max_l == 0: return 0.0
                return float(edit_distance_string.do(self._content, nominal._content)) / max_l

    @property
    def string(self):
        return self._content

    def __len__(self):
        return len(self._content)

    def __repr__(self):
        match self.tolerance_id:
            case E_ToleranceId.EQUIVALENCE_PATTERN:
                return "%s %s '%s'" % (self.tolerance_id.name, sorted(self.val), self._content)
            case _:
                return "%s '%s'" % (self.tolerance_id.name, self._content)

# ______________________________________________________________________________
# BACKWARD COMPATIBILITY FACTORY FUNCTIONS

def LineElementString(content):
    return LineElement(E_ToleranceId.STRING, content)

def LineElementSeparator(content):
    return LineElement(E_ToleranceId.SEPERATOR, content)

def LineElementAnalogy(content):
    return LineElement(E_ToleranceId.ANALOGY, content)

def LineElementNumber(content, numeric_tolerance_ratio=0.0):
    try:
        num_val = float(content)
    except ValueError:
        num_val = 0.0
    epsilon = abs(num_val * (numeric_tolerance_ratio or 0.0))
    return LineElement(E_ToleranceId.NUMERIC, content, val=num_val, aux=epsilon)

def LineElementVisibleNothing(content):
    return LineElement(E_ToleranceId.VISIBLE_NOTHING, content)

def LineElementEquivalencePattern(content, indices):
    return LineElement(E_ToleranceId.EQUIVALENCE_PATTERN, content, val=frozenset(indices))
