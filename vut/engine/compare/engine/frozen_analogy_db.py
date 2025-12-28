from __future__  import annotations
from collections import defaultdict
from functools   import lru_cache
from typing      import Iterable
from typeguard   import typechecked

from .analogy_db import LineNumberPair

# Assumes LineNumberPair and AnalogyDb are available in the namespace
# from vut.engine.compare.engine.analogy_db import AnalogyDb, LineNumberPair

class FrozenAnalogyDb:
    """Fast and efficient representation of 'AnalogyDb'.

    Only two operations required:

        (1) 'is_consistent(other)' -> bool
        (2) 'merge(other)' -> new FrozenAnalogyDb

    The fast and efficient implementation is crucial for performance 
    of related algorithms, particularly in large-scale backtracking search 
    where consistency checks are the primary bottleneck.

    Performance Characteristics:
    --------------------------
    - Flyweight Pattern: Uses __new__ to intern all instances. If two paths 
      result in the same constraints, they share the same memory address, 
      reducing 'is_all_consistent' to an O(1) pointer identity check.

    - Bit-Vector Representation: Subject and Nominal terms are mapped to 
      global integer IDs. Constraints are represented as large bitmasks.

    - O(1) Disjoint Check: Uses bitwise AND on masks to instantly verify 
      consistency between disjoint constraint sets (the most frequent case).

    - Memory Efficiency: Replaces heavy dictionary objects with low-level 
      integer masks and tuples of integer Pair-IDs.

    Algorithm Logic:
    ---------------

    Consistency:

    1. A subject string cannot map to two different nominal strings.

    2. Two different subject strings cannot map to the same nominal string.
    
    By representing (subject, nominal) pairs as unique 'Pair-IDs', the 
    'is_consistent' operation validates these rules using bitwise 
    intersections and Pair-ID set comparisons.
    """
    _pool     = {} # pool of existing objects --> flyweight pattern
    #              # (use references to immutables instead of copies of objects)
    __slots__ = ('_pair_ids', 'subj_mask', 'nom_mask')

    class _Registry:
        """Global mapping of strings and pairs to unique integer IDs."""
        symbols      = {} # string -> int_id
        symbols_inv  = [] # pair_id -> string
        pairs        = {} # (subj_id, nom_id) -> pair_id
        pair_to_info = [] # pair_id -> (subj_id, nom_id)
        
        # Metadata: pair_id -> LineNumberPair | None
        # Dense list that grows on demand.
        pair_provenance = []

        @classmethod
        def get_symbol_id(cls, s: str) -> int:
            if s not in cls.symbols:
                cls.symbols[s] = len(cls.symbols_inv)
                cls.symbols_inv.append(s)
            return cls.symbols[s]

        @classmethod
        def get_pair_id(cls, subj_s: str, nom_s: str) -> int:
            s_id = cls.get_symbol_id(subj_s)
            n_id = cls.get_symbol_id(nom_s)
            pair = (s_id, n_id)
            if pair not in cls.pairs:
                cls.pairs[pair] = len(cls.pair_to_info)
                cls.pair_to_info.append(pair)
            return cls.pairs[pair]

        @classmethod
        def get_provenance(cls, pair_id: int):
            """RETURNS: LineNumberPair for pair_id, or None if out of bounds/unset."""
            if pair_id < len(cls.pair_provenance):
                return cls.pair_provenance[pair_id]
            return None

        @classmethod
        def register_provenance(cls, pair_id: int, lp: LineNumberPair):
            """Extends vector if needed, then assigns lp to pair_id."""
            if lp is None: return
            
            # Intelligent Growth: Extend with None if pair_id is beyond current length
            diff = pair_id - len(cls.pair_provenance) + 1
            if diff > 0:
                cls.pair_provenance.extend([None] * diff)
            
            # Direct assignment
            if cls.pair_provenance[pair_id] is None:
                cls.pair_provenance[pair_id] = lp

        @classmethod
        def string_pair(cls, pair_id):
            """RETURNS: subject string, nominal string that corresponds to pair_id.
            """
            s_id, n_id = cls.pair_to_info[pair_id]
            return cls.symbols_inv[s_id], cls.symbols_inv[n_id]

    @typechecked
    def __new__(cls, adb: dict | None = None, _pair_ids: tuple | None = None):
        """RETURNS: FrozenAnalogyDb that represents the AnalogyDb passed by 'adb'.

        NOTE: AnalogyDb is a 'dict' -- it is accepted here.
        """
        if isinstance(adb, FrozenAnalogyDb): return adb
        
        # Determine pair_ids (Key for the flyweight pool)
        if _pair_ids is not None:
            pair_ids = _pair_ids
        elif adb is None:
            pair_ids = tuple()
        elif not (ln_db := getattr(adb, 'line_number_db', None)):
            # no line number database or empty => quick absorbtion
            pair_ids = tuple(sorted(
                cls._Registry.get_pair_id(s, n) for s, n in adb.items()
            ))
        else:
            # Ingesting a standard dict or AnalogyDb
            ln_db = getattr(adb, 'line_number_db', {})
            p_ids = []
            for s, n in adb.items():
                pid = cls._Registry.get_pair_id(s, n)
                p_ids.append(pid)
                # Register provenance if available
                if s in ln_db:
                    cls._Registry.register_provenance(pid, ln_db[s])
            pair_ids = tuple(sorted(p_ids))

        # Flyweight lookup
        if pair_ids in cls._pool:
            return cls._pool[pair_ids]

        # Initialize unique instance
        instance = super().__new__(cls)
        instance._pair_ids = pair_ids
        
        # Build Bitmasks for O(1) disjoint checks
        instance.subj_mask = 0
        instance.nom_mask  = 0
        for pid in pair_ids:
            s_id, n_id = cls._Registry.pair_to_info[pid]
            instance.subj_mask |= (1 << s_id)
            instance.nom_mask  |= (1 << n_id)

        cls._pool[pair_ids] = instance
        return instance

    def to_AnalogyDb(self):
        """RETURNS: A mutable AnalogyDb containing all analogies and provenance.
        
        Reconstructs the full dictionary and line number metadata from the 
        internal integer IDs.
        """
        # Local import to avoid circular dependency with analogy_db.py
        from .analogy_db import AnalogyDb

        result = AnalogyDb()
        
        # Cache registry lookups for speed
        _str_pair = self._Registry.string_pair
        _get_prov = self._Registry.get_provenance
        
        for pid in self._pair_ids:
            s, n = _str_pair(pid)
            result[s] = n
            
            # Re-attach line number metadata if it exists
            lp = _get_prov(pid)
            if lp is not None:
                result.line_number_db[s] = lp
                
        return result

    @classmethod
    @typechecked
    def merge_all(cls, adbs: Iterable[FrozenAnalogyDb|None]) -> FrozenAnalogyDb:
        """Bulk merges multiple databases bypassing intermediate steps."""
        active = [adb for adb in adbs if adb and adb._pair_ids]
        if not active: return cls({})
        if len(active) == 1: return active[0]

        merged_ids = set()
        _update = merged_ids.update
        for adb in active:
            _update(adb._pair_ids)
        return cls(_pair_ids=tuple(sorted(merged_ids)))

    @lru_cache(maxsize=16384)
    def is_all_consistent(self, other: FrozenAnalogyDb) -> bool:
        if self is other: return True

        # Bitmask Fast-Fail 
        if not (self.subj_mask & other.subj_mask | self.nom_mask & other.nom_mask):
            return True

        # Deep Validation (Only if bits overlap) 
        # Since we use a Flyweight for the whole DB, we can also use 
        # a Set of Pair IDs for O(1) intersection checks of the components.
        # This is faster than iterating bits for very large masks.
        s_set = set(self._pair_ids)
        for pid in other._pair_ids:
            s_id, n_id = self._Registry.pair_to_info[pid]
            # If subject or nominal overlap, the exact Pair ID must match
            if ((1 << s_id) & self.subj_mask) or ((1 << n_id) & self.nom_mask):
                if pid not in s_set: return False
        return True

    @lru_cache(maxsize=16384)
    def merge(self, other: FrozenAnalogyDb|None) -> FrozenAnalogyDb:
        """RETURNS: clone of 'self' merged with content of 'other'.
        """
        if   other is None or other is self: return self
        elif not self._pair_ids:             return other
        elif not other._pair_ids:            return self
        
        # Optimized: Merge integer IDs directly. 
        merged = set(self._pair_ids) | set(other._pair_ids)
        return FrozenAnalogyDb(_pair_ids=tuple(sorted(merged)))

    def items(self):
        """RETURNS: A list of (subject, nominal) string pairs.
        
        This reconstructs the original string representations from the 
        interned integer IDs stored in the registry.
        """
        _get = self._Registry.string_pair
        for pid in self._pair_ids:
            yield _get(pid)

    def get_provenance(self, pair_id):
        return self._Registry.get_provenance(pair_id)

    def __iter__(self):      return iter(self._pair_ids)
    def __hash__(self):      return id(self)      # flyweight: equal <-> identical
    def __eq__(self, other): return self is other # flyweight: equal <-> identical

    def __repr__(self) -> str:
        if not self._pair_ids: return "<empty>"
        
        # Group analogies by their first occurrence for a clean report
        grouped = defaultdict(list)
        for pid in self._pair_ids:
            s, n = self._Registry.string_pair(pid)
            # Safe getter allows lazy growth
            prov = self._Registry.get_provenance(pid)
            # Key is LineNumberPair or None
            grouped[prov].append(f'"{s}"="{n}"')

        def annotation(lp):
            if lp is None: return "[?]-[?] : "
            else:          return f"[{lp.subject_line_n}]-[{lp.nominal_line_n}]: " 

        # Sort keys carefully handling None
        sorted_keys = sorted(grouped.keys(), key=lambda x: (x is None, x))
        
        return "\n".join(f"  {annotation(lp)}{', '.join(sorted(grouped[lp]))}"
                         for lp in sorted_keys)
