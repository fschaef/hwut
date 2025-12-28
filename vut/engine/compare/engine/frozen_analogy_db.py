from __future__ import annotations
from typeguard  import typechecked
from functools  import lru_cache
from typing     import Iterable

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

    @typechecked
    def __new__(cls, adb: dict | None = None, _pair_ids: tuple | None = None):
        """RETURNS: FrozenAnalogyDb that represents the AnalogyDb passed by 'adb'.

        NOTE: AnalogyDb is a 'dict' -- it is accepted here.
        """
        # Get pair_ids required as key for flyweight pool.
        if isinstance(adb, FrozenAnalogyDb): 
            return adb
        elif _pair_ids:
            pair_ids = _pair_ids
        elif adb is None:
            pair_ids = tuple()
        else:
            pair_ids = tuple(sorted(
                cls._Registry.get_pair_id(s, n) for s, n in adb.items()
            ))

        # Flyweight lookup
        if pair_ids in cls._pool:
            return cls._pool[pair_ids]

        # Create and initialize the unique instance
        instance = super().__new__(cls)
        instance._pair_ids = pair_ids
        
        # Build Bitmasks: Each bit represents a Symbol ID
        instance.subj_mask = 0
        instance.nom_mask  = 0
        for pid in pair_ids:
            s_id, n_id = cls._Registry.pair_to_info[pid]
            instance.subj_mask |= (1 << s_id)
            instance.nom_mask |= (1 << n_id)

        cls._pool[pair_ids] = instance
        return instance

    @classmethod
    @typechecked
    def merge_all(cls, adbs: Iterable[FrozenAnalogyDb|None]) -> FrozenAnalogyDb:
        """RETURNS: 'FrozenAnalogyDb' of merged 'adbs'

        NOTE: 'adbs' which are 'None' or empty are tolerated! 
              No need for pre-processing the list.

        Bypasses intermediate object creation and interning steps required 
        by sequential binary merges.
        """
        # Filter out empty or None inputs
        active_adbs = [adb for adb in adbs if adb and adb._pair_ids]
        
        if not active_adbs:
            return FrozenAnalogyDb({}) # Return interned empty DB
        
        if len(active_adbs) == 1:
            return active_adbs[0]

        # Consolidate all Pair-IDs into a single set
        # Using a set handles duplicates automatically
        merged = set()
        for adb in active_adbs:
            merged.update(adb._pair_ids)
            
        return cls(_pair_ids=tuple(sorted(merged)))

    @lru_cache(maxsize=16384)
    def is_all_consistent(self, other: 'FrozenAnalogyDb') -> bool:
        """RETURNS: True, if self is consistent with other.
                    False, else.
        """
        if self is other: return True

        # --- PHASE 1: Bitmask Fast-Fail ---
        # If they share a subject bit, they MUST share the same pair mapping.
        # If they share a nominal bit, they MUST share the same pair mapping.
        shared_subj = self.subj_mask & other.subj_mask
        shared_nom  = self.nom_mask & other.nom_mask
        
        if not (shared_subj | shared_nom):
            return True

        # Deep Validation (Only if bits overlap) 
        # Since we use a Flyweight for the whole DB, we can also use 
        # a Set of Pair IDs for O(1) intersection checks of the components.
        # This is faster than iterating bits for very large masks.
        s_set = set(self._pair_ids)
        for pid in other._pair_ids:
            s_id, n_id = self._Registry.pair_to_info[pid]
            
            # Subject Collision: If other has s_id, I must have the EXACT same pid
            if (1 << s_id) & self.subj_mask:
                if pid not in s_set: return False
            
            # Monogamy Collision: If other has n_id, I must have the EXACT same pid
            if (1 << n_id) & self.nom_mask:
                if pid not in s_set: return False

        return True

    @lru_cache(maxsize=16384)
    def merge(self, other: 'FrozenAnalogyDb') -> 'FrozenAnalogyDb':
        """RETURNS: clone of 'self' merged with content of 'other'.
        """
        if   other is None or other is self: return self
        elif not self._pair_ids:             return other
        elif not other._pair_ids:            return self
        
        # Optimized: Merge integer IDs directly. 
        merged = set(self._pair_ids) | set(other._pair_ids)
        return FrozenAnalogyDb(_pair_ids=tuple(sorted(merged)))

    def __hash__(self):
        return id(self)      # flyweight => equal objects = same objects

    def __eq__(self, other):
        return self is other # flyweight => equal objects = same objects
