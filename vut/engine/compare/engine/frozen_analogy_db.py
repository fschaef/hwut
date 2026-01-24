from __future__  import annotations
from functools   import lru_cache
from typing      import Iterable
from typing      import Union

import weakref

# Assuming local import context exists as per your snippet
from .analogy_db import AnalogyDb

class FrozenAnalogyRegistry:
    """Global mapping of strings and pairs to unique integer IDs."""
    # Use WeakValueDictionary to prevent memory leaks in backtracking search.
    def __init__(self):
        self.pool            = weakref.WeakValueDictionary()
        self.symbols         = {} # string -> int_id
        self.symbols_inv     = [] # pair_id -> string
        self.pairs           = {} # (subj_id, nom_id) -> pair_id
        self.pair_to_info    = [] # pair_id -> (subj_id, nom_id)
        self._EMPTY_INSTANCE = None # Singleton for empty databases
        # HYBRID THRESHOLD: If IDs exceed this, we skip bitmask generation.
        # 256 bits = 32 bytes (CPU word efficient)
        self._MASK_LIMIT     = 256
    
    def get_symbol_id(self, s: str) -> int:
        if s not in self.symbols:
            self.symbols[s] = len(self.symbols_inv)
            self.symbols_inv.append(s)
        return self.symbols[s]

    def get_pair_id(self, subj_s: str, nom_s: str) -> int:
        s_id = self.get_symbol_id(subj_s)
        n_id = self.get_symbol_id(nom_s)
        pair = (s_id, n_id)
        if pair not in self.pairs:
            self.pairs[pair] = len(self.pair_to_info)
            self.pair_to_info.append(pair)
        return self.pairs[pair]

    def string_pair(self, pair_id):
        """RETURNS: subject string, nominal string that corresponds to pair_id.
        """
        s_id, n_id = self.pair_to_info[pair_id]
        return self.symbols_inv[s_id], self.symbols_inv[n_id]

frozen_analogy_registry = FrozenAnalogyRegistry()

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
    # Lazy-lookup cache slots: _s2n (subject-to-nominal), _n2s (nominal-to-subject)
    __slots__ = ('_registry', '_pair_ids', '_subj_mask', '_nom_mask', '_s2n', '_n2s', '__weakref__')
    
    @property
    def subj_mask(self) -> int: return self._subj_mask

    @property
    def nom_mask(self) -> int: return self._nom_mask

    @property
    def pair_ids(self) -> tuple: return self._pair_ids

    # @typechecked -- way to expensive during CSP
    def __new__(cls, adb: AnalogyDb | FrozenAnalogyDb | dict | None = None, _pair_ids: tuple | None = None):
        """RETURNS: FrozenAnalogyDb that represents the AnalogyDb passed by 'adb'., AnalogyDb

        NOTE: AnalogyDb is a 'dict' -- it is accepted here.
        """
        global frozen_analogy_registry
        registry = frozen_analogy_registry
        if adb.__class__ is cls: return adb
        
        # Determine pair_ids (Key for the flyweight pool)
        if _pair_ids is not None:
            pair_ids = _pair_ids
        elif not adb:
            if registry._EMPTY_INSTANCE: return registry._EMPTY_INSTANCE
            pair_ids = tuple()
        else:
            # Optimization: Localize registry lookup for speed in loop
            get_pid = registry.get_pair_id
            pair_ids = tuple(sorted(get_pid(s, n) for s, n in adb.items()))

        # Flyweight lookup
        if (instance := registry.pool.get(pair_ids)) is not None:
            return instance

        # Initialize unique instance
        instance = super().__new__(cls)
        instance._registry = registry
        instance._pair_ids = pair_ids
        
        s_mask, n_mask = 0, 0
        limit = registry._MASK_LIMIT
        _info = registry.pair_to_info
        
        # Single-pass mask generation
        for pid in pair_ids:
            s_id, n_id = _info[pid]
            if s_id >= limit or n_id >= limit:
                s_mask = n_mask = -1
                break
            s_mask |= (1 << s_id)
            n_mask |= (1 << n_id)

        instance._subj_mask = s_mask
        instance._nom_mask  = n_mask
        
        if not pair_ids and not registry._EMPTY_INSTANCE:
            registry._EMPTY_INSTANCE = instance

        registry.pool[pair_ids] = instance
        return instance

    def _ensure_lookups(self):
        """Lazy-initialize lookup tables for O(N) deep consistency checks."""
        try:
            return self._s2n
        except AttributeError:
            s2n, n2s = {}, {}
            _info = self._registry.pair_to_info
            for pid in self._pair_ids:
                sid, nid = _info[pid]
                s2n[sid] = nid
                n2s[nid] = sid
            self._s2n, self._n2s = s2n, n2s
            return s2n

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
        _str_pair = self._registry.string_pair # Cache registry lookups for speed
        return AnalogyDb(_str_pair(pid) for pid in self._pair_ids)

    @classmethod
    # @typechecked -- wait to expensive during CSP
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

    @lru_cache(maxsize=8196)
    def merge(self, other: FrozenAnalogyDb|None) -> FrozenAnalogyDb:
        """RETURNS: clone of 'self' merged with content of 'other'.
        """
        if   other is None or other is self: return self
        elif not self._pair_ids:             return other
        elif not other._pair_ids:            return self
        
        # Optimized: Merge integer IDs directly. 
        s1, s2 = set(self._pair_ids), set(other._pair_ids)
        if   s1.issuperset(s2): return self
        elif s2.issuperset(s1): return other
        
        return FrozenAnalogyDb(_pair_ids=tuple(sorted(s1 | s2)))

    @lru_cache(maxsize=8196)
    def is_all_consistent(self, other: FrozenAnalogyDb) -> bool:
        if self is other: return True

        # Bitmask Fast-Fail 
        # Only use bitmasks if they are enabled (not -1).
        # If disabled, we must fall through to deep ID validation.
        if self._subj_mask != -1 and other._subj_mask != -1:
            # If they involve the same symbols but are different Flyweights, they MUST conflict.
            if self._subj_mask == other._subj_mask and self._nom_mask == other._nom_mask:
                # They involve the same symbols but are different Flyweight instances.
                # Therefore, the mappings MUST differ.
                return False
            # Disjointness check
            elif not (self._subj_mask & other._subj_mask or self._nom_mask & other._nom_mask):
                return True

        # Optimized Deep Check
        self._ensure_lookups()
        _info = self._registry.pair_to_info
        
        # Bi-directional O(1) check per pair in 'other'
        for pid in other._pair_ids:
            os_id, on_id = _info[pid]
            if os_id in self._s2n and self._s2n[os_id] != on_id: return False
            if on_id in self._n2s and self._n2s[on_id] != os_id: return False
        return True

    def clone(self):
        """Interface compatibility with AnalogyDb: immutable, so return self."""
        return self

    def update(self, other):
        """Interface compatibility with AnalogyDb: alias for merge."""
        return self.merge(other)

    def clone_and_add(self, analogy: tuple[str, str]):
        """Interface compatibility with AnalogyDb: returns new instance with analogy added."""
        return self.merge(FrozenAnalogyDb({analogy[0]: analogy[1]}))

    def is_consistent(self, analogy: tuple[str, str]):
        """Interface compatibility with AnalogyDb."""
        if analogy is None: return True
        return self.is_all_consistent(FrozenAnalogyDb({analogy[0]: analogy[1]}))
    def items(self):
        """RETURNS: A list of (subject, nominal) string pairs.
        
        This reconstructs the original string representations from the 
        interned integer IDs stored in the registry.
        """
        _get = self._registry.string_pair
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
            s, n = self._registry.string_pair(pid)
            # Key is LineNumberPair or None
            grouped.append(f'"{s}"="{n}"')

        def annotation(lp):
            return ""

        # Sort keys carefully handling None
        return "\n".join(f"  {line}" for line in sorted(grouped))
