"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: VUT
_______________________________________________________________________________
PURPOSE: A database for terms to be treated as 'analogies'.

An analogy, in HWUT terms, is the equivalence relationship between a string 'a'
that may occur in the subject and a string 'b' that may occur in the nominal.
At its first occurrence, an analogy is determined. If 'a' occurs consistently
whenever 'b' is expected, the analogies hold. Else, subject and nominal are not
equivalent. The 'AnalogyDb' maintains the analogies at their first occurrence.

Notably, HWUT only considers analogies in strings which are bracketted by '(('
and '))'.

EXAMPLE:

An application prints output containing hash values, which may differ but
consistence must be maintained. Let a nominal text output be given as:

      ((0x249d3efa)) --> 12 to ((0x5ea931ef));  551 to ((0x249d3efa));
      ((0x249d3efa)) -->  7 to ((0x6729aef3));  554 to ((0x249d3efa));
      ((0x249d3efa)) --> 28 to ((0x4513e8a9));  526 to ((0x249d3efa));
      ((0x6729aef3)) -->  3 to ((0x5ea931ef));    4 to ((0x6729aef3));

If in another test, other hash values are computed (based on real randomness,
for example), the subject's output may look like

      ((0x89c0ffeb)) --> 12 to ((0x1a2b3e81));  551 to ((0x249d3efa));
      ((0x89c0ffeb)) -->  7 to ((0xaf43ff12));  554 to ((0x249d3efa));
      ((0x89c0ffeb)) --> 28 to ((0xfe3187a1));  526 to ((0x249d3efa));
      ((0xaf43ff12)) -->  3 to ((0x1a2b3e81));    4 to ((0xaf43ff12));

Both texts are still equivalent, since the following terms are used
consistently one for the other:

                     in subject:     in nominal:

                     0x249d3efa <--> 0x89c0ffeb
                     0x6729aef3 <--> 0xaf43ff12
                     0x5ea931ef <--> 0x1a2b3e81
                     0x4513e8a9 <--> 0xfe3187a1

The table above, is what is stored in the analogy database, along with line
number information about the analogies first occurrence.
_______________________________________________________________________________
"""
from   vut.system.helper        import number_of_decimal_digits
from   collections              import namedtuple, defaultdict
from   functools                import lru_cache

LineNumberPair = namedtuple("LineNumberPair", ("subject_line_n", "nominal_line_n"))

class AnalogyDb(dict):
    """Maintains pairs of terms which are considered analogies.

    A term in 'subject' is mapped to its counterpart in 'nominal'. Notably,
    the directionality is not automatically inverted.

    self:           map: subject term --> nominal term
    line_number_db: map: subject term --> LineNumberPair
    """
    def __init__(self, other=None):
        self.line_number_db = {}
        if other is not None:
            self.update(other)

    def clone(self):
        return AnalogyDb(self)

    def clone_updated(self, other):
        """RETURNS: updated clone, if other is consistent with self
                    None, else
        """
        result = self.clone()
        if other is not None: result.update(other)
        return result

    def update(self, other):
        if other is not None:
            dict.update(self, other)
            if isinstance(other, AnalogyDb):
                self.line_number_db.update(other.line_number_db)
        return self

    def assign(self, other):
        if id(self) != id(other): # ESSENTIAL: otherwise, self is just emptied.
            dict.clear(self)
            self.line_number_db.clear()
            self.update(other)

    def is_consistent(self, analogy):
        """RETURNS: True, if analogy = tuple(subject, nominal) is consistent
                          with all entries in database; False, else.
        """
        if analogy is None:
            return True

        subject, nominal = analogy
        related_nominal  = self.get(subject)
        if related_nominal is None:
            return nominal not in self.values()
        else:
            return related_nominal == nominal

    def is_all_consistent(self, analogy_db):
        """RETURNS: True, if analogy_db is consistent with self.
                    False, else.
        """
        if analogy_db is None:
            return True
        else:
            return all(self.is_consistent(item) for item in analogy_db.items())

    def add(self, analogy):
        assert analogy is not None
        subject, nominal = analogy
        self[subject] = nominal

    def extend(self, analogy_db, subject_line_n, nominal_line_n):
        dict.update(self, analogy_db)
        self.mark_line_numbers(subject_line_n, nominal_line_n, analogy_db.keys())
        return self

    def add_if_consistent(self, analogy):
        if analogy is None:
            return True    # OK:   nothing added; no inconsistency.
        elif not self.is_consistent(analogy):
            return False   # FAIL: analogy inconsistent with others.
        else:
            self.add(analogy)
            return True    # OK:   analogy is added without braking consistency.

    def extend_if_consistent(self, analogy_db, subject_line_n, nominal_line_n):
        if analogy_db is None:
            return True    # OK:   nothing added; no inconsistency.
        elif not self.is_all_consistent(analogy_db):
            return False   # FAIL: analogy_db inconsistent with self
        else:
            self.extend(analogy_db, subject_line_n, nominal_line_n)
            return True    # OK:   analogy is added without braking consistency.

    def mark_line_numbers(self, subject_line_n, nominal_line_n, subject_iterable=None):
        """Marks 'subject_line_n' and 'nominal_line_n' as the pair of lines
        where the analogies in this databse occurred the first time. If
        'subject_iterable' is specified, only those subjects are considered.
        """
        if subject_iterable is None:
            subject_iterable = self.keys()

        line_number_pair = LineNumberPair(subject_line_n, nominal_line_n)
        for subject in subject_iterable:
            entry = self.line_number_db.get(subject)
            if entry is None or entry.subject_line_n > subject_line_n:
                self.line_number_db[subject] = line_number_pair

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        def length(n):
            if   n is None:          return 1 # -> " "
            elif isinstance(n, str): return len(n)
            elif n <= 1:             return 1
            else:                    return number_of_decimal_digits(n) 

        def prefix(p, Ls, Ln):
            if p is not None:
                return ":%s%s&%s%s" % (" " * (Ls - length(p.subject_line_n)), p.subject_line_n,
                                       " " * (Ln - length(p.nominal_line_n)), p.nominal_line_n)
            else:
                return ""

        def show(analogy_list):
            return ", ".join('"%s"="%s"' % (subject, nominal) for subject, nominal in sorted(analogy_list))

        if self.line_number_db:
            Ls = max(length(p.subject_line_n) for p in self.line_number_db.values())
            Ln = max(length(p.nominal_line_n) for p in self.line_number_db.values())
        else:
            Ls, Ln = 0, 0

        content_db = defaultdict(list)
        for subject, nominal in self.items():
            p = self.line_number_db.get(subject)
            if p is None: p = LineNumberPair(" ", " ")
            content_db[p].append((subject, nominal))

        txt = [
            (prefix(p, Ls, Ln), show(analogy_list))
            for p, analogy_list in sorted(content_db.items())
        ]
        
        return "AnalogyDb", txt

    def __hash__(self):
        a = hash(frozenset(self.items()))
        b = hash(frozenset(self.line_number_db.items()))
        return hash((a, b))

    def __eq__(self, other):
        return dict.__eq__(self, other) and self.line_number_db == other.line_number_db

    def __repr__(self):
        name, txt = self.__pretty__()
        return "\n".join("%s: %s" % (x, y) for x, y in txt)

class FrozenAnalogyDb:
    """
    A canonicalized, interned representation of Analogy constraints.
    Multiple 'creations' of the same data return the same object.
    """
    _POOL = {}  # The internal reference pool (hash -> instance)

    def __new__(cls, adb_dict: dict):
        # 1. Canonicalize the data to create a stable hash
        # We sort by subject to ensure {A:1, B:2} and {B:2, A:1} are identical
        items = tuple(sorted(adb_dict.items()))

        # 2. Check the pool
        existing = cls._POOL.get(items)
        if existing is not None:
            return existing

        # 3. Create new instance if not found
        instance = super().__new__(cls)
        cls._POOL[items] = instance
        
        # Initialize the new instance
        instance._items    = items
        instance._subjects = tuple(s for s, n in items)
        instance._nominals = tuple(n for s, n in items)
        instance._nominal_set = set(instance._nominals)
        
        # 4. Store in pool and return
        return instance

    def items(self):
        return  self._items

    def merge(self, other: 'FrozenAnalogyDb') -> 'FrozenAnalogyDb':
        """RETURNS: new interned FrozenAnalogyDb representing the union 
                    of two consistent databases.
        """
        if other is None or not other._items:
            return self
        if not self._items:
            return other
            
        # Since the solver ensures consistency before merging, 
        # we can just combine and re-intern.
        combined_dict = dict(self._items)
        combined_dict.update(other._items)
        return FrozenAnalogyDb(combined_dict)
    
    @lru_cache(maxsize=8196)
    def is_all_consistent(self, other: 'FrozenAnalogyDb') -> bool:
        """
        Check consistency. Identity check handles interned duplicates in O(1).
        Otherwise, performs a Sorted-Merge Scan in O(N+M).
        """
        # Identity comparison: Extremely fast thanks to interning
        if self is other: 
            return True

        i, j = 0, 0
        n1, n2 = len(self._subjects), len(other._subjects)
        
        # Parallel Sorted-Merge Scan
        while i < n1 and j < n2:
            s1, s2 = self._subjects[i], other._subjects[j]
            
            if s1 == s2:
                if self._nominals[i] != other._nominals[j]:
                    return False
                i += 1
                j += 1
            elif s1 < s2:
                if self._nominals[i] in other._nominal_set:
                    return False
                i += 1
            else:
                if other._nominals[j] in self._nominal_set:
                    return False
                j += 1

        # Final cleanup for remaining unique subjects
        while i < n1:
            if self._nominals[i] in other._nominal_set: return False
            i += 1
        while j < n2:
            if other._nominals[j] in self._nominal_set: return False
            j += 1

        return True

    def __hash__(self):      return id(self)
    def __eq__(self, other): return self is other
