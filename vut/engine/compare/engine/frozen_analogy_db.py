from __future__  import annotations
from functools   import lru_cache
from typing      import Iterable
from typeguard   import typechecked
from typing      import Union

# Assuming local import context exists as per your snippet
from .analogy_db import AnalogyDb

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

    - Hybrid Bit-Vector Representation: For small IDs (< 256), constraints 
      are bitmasks for O(1) checks. For large IDs, bitmasks are disabled 
      to prevent memory explosion, falling back to efficient ID lookups.

    - Memory Efficiency: Replaces heavy dictionary objects with low-level 
      integer masks and tuples of integer Pair-IDs.

    Algorithm Logic:
    ---------------

    Consistency:

    1. A subject string cannot map to two different nominal strings.

    2. Two different subject strings cannot map to the same nominal string.
     
    By representing (subject, nominal) pairs as unique 'Pair-IDs', the 
    'is_consistent' operation validates these rules using bitwise 
    intersections (if small) or Pair-ID set comparisons.
    """
    # Use WeakValueDictionary to prevent memory leaks in backtracking search
    ## _pool     = weakref.WeakValueDictionary() 
    _pool     = {} 
    __slots__ = ('_pair_ids', '_subj_mask', '_nom_mask')
    
    # HYBRID THRESHOLD: If IDs exceed this, we skip bitmask generation.
    # 256 bits = 32 bytes (CPU word efficient)
    _MASK_LIMIT = 256

    @property
    def subj_mask(self) -> int: return self._subj_mask

    @property
    def nom_mask(self) -> int: return self._nom_mask

    @property
    def pair_ids(self) -> tuple: return self._pair_ids

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

        @classmethod
        def string_pair(cls, pair_id):
            """RETURNS: subject string, nominal string that corresponds to pair_id.
            """
            s_id, n_id = cls.pair_to_info[pair_id]
            return cls.symbols_inv[s_id], cls.symbols_inv[n_id]

    @typechecked
    def __new__(cls, adb: FrozenAnalogyDb | dict | None = None, _pair_ids: tuple | None = None):
        """RETURNS: FrozenAnalogyDb that represents the AnalogyDb passed by 'adb'., AnalogyDb

        NOTE: AnalogyDb is a 'dict' -- it is accepted here.
        """
        if isinstance(adb, FrozenAnalogyDb): return adb
        
        # Determine pair_ids (Key for the flyweight pool)
        if _pair_ids is not None:
            pair_ids = _pair_ids
        elif adb is None:
            pair_ids = tuple()
        else:
            # no line number database or empty => quick absorbtion
            pair_ids = tuple(sorted(
                cls._Registry.get_pair_id(s, n) for s, n in adb.items()
            ))

        # Flyweight lookup
        if pair_ids in cls._pool:
            return cls._pool[pair_ids]

        # Initialize unique instance
        instance = super().__new__(cls)
        instance._pair_ids = pair_ids
        
        s_mask, n_mask = 0, 0
        limit = cls._MASK_LIMIT
        
        # --- REPAIR START: Optional Bitmask Generation ---
        # If any ID exceeds the limit, we abort mask generation and set to -1 (All 1s).
        # -1 ensures we fall through to the deep check in is_all_consistent.
        use_masks = True
        
        # Pre-scan (or check during loop) to ensure we don't blow up memory
        for pid in pair_ids:
            s_id, n_id = cls._Registry.pair_to_info[pid]
            if s_id >= limit or n_id >= limit:
                use_masks = False
                break
        
        if use_masks:
            for pid in pair_ids:
                s_id, n_id = cls._Registry.pair_to_info[pid]
                s_mask |= (1 << s_id)
                n_mask |= (1 << n_id)
        else:
            # Disable optimization: -1 means "Assume overlap, check deeply"
            s_mask, n_mask = -1, -1

        instance._subj_mask = s_mask
        instance._nom_mask  = n_mask

        cls._pool[pair_ids] = instance
        return instance

    @staticmethod
    def if_consistent(analogy_list: Iterable) -> Union[FrozenAnalogyDb, None]:
        subject_db = {}
        nominal_db = {}
        for s, n in analogy_list:
            if (exist_n := subject_db.get(s)) is not None and exist_n != n: 
                return None
            if (exist_s := nominal_db.get(n)) is not None and exist_s != s: 
                return None

            subject_db[s] = n
            nominal_db[n] = s
        return FrozenAnalogyDb(subject_db)

    def to_AnalogyDb(self):
        """RETURNS: A mutable AnalogyDb containing all analogies and provenance.
        
        Reconstructs the full dictionary and line number metadata from the 
        internal integer IDs.
        """
        result = AnalogyDb()
        
        # Cache registry lookups for speed
        _str_pair = self._Registry.string_pair
        for pid in self._pair_ids:
            s, n = _str_pair(pid)
            result[s] = n
                
        return result

    @classmethod
    @typechecked
    def merge_all(cls, adbs: Iterable[FrozenAnalogyDb|None]) -> FrozenAnalogyDb:
        """Bulk merges multiple databases bypassing intermediate steps."""
        active = [adb for adb in adbs if adb and adb._pair_ids]
        if   not active:       return cls({})
        elif len(active) == 1: return active[0]

        merged_ids = set()
        _update = merged_ids.update
        for adb in active:
            _update(adb._pair_ids)
        return cls(_pair_ids=tuple(sorted(merged_ids)))

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

    @lru_cache(maxsize=16384)
    def is_all_consistent(self, other: FrozenAnalogyDb) -> bool:
        if self is other: return True

        # Bitmask Fast-Fail 
        # Only use bitmasks if they are enabled (not -1).
        # If disabled, we must fall through to deep ID validation.
        if self._subj_mask != -1 and other._subj_mask != -1:
            if not (self._subj_mask & other._subj_mask | self._nom_mask & other._nom_mask):
                return True

        self_pairs = {}
        self_noms = set()
        _info = self._Registry.pair_to_info
        
        for pid in self._pair_ids:
            s_id, n_id = _info[pid]
            self_pairs[s_id] = n_id
            self_noms.add(n_id)

        for pid in other._pair_ids:
            os_id, on_id = _info[pid]
            if os_id in self_pairs:
                if self_pairs[os_id] != on_id: return False
            elif on_id in self_noms:
                return False
        return True

    def items(self):
        """RETURNS: A list of (subject, nominal) string pairs.
        
        This reconstructs the original string representations from the 
        interned integer IDs stored in the registry.
        """
        _get = self._Registry.string_pair
        for pid in self._pair_ids:
            yield _get(pid)

    def __iter__(self):      return iter(self._pair_ids)
    def __hash__(self):      return id(self)      # flyweight: equal <-> identical
    def __eq__(self, other): return self is other # flyweight: equal <-> identical

    def __repr__(self) -> str:
        if not self._pair_ids: return "<empty>"
        
        # Group analogies by their first occurrence for a clean report
        grouped = []
        for pid in self._pair_ids:
            s, n = self._Registry.string_pair(pid)
            # Key is LineNumberPair or None
            grouped.append(f'"{s}"="{n}"')

        def annotation(lp):
            return ""

        # Sort keys carefully handling None
        return "\n".join(f"  {line}" for line in sorted(grouped))
