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
from   collections              import defaultdict
from   bidict                   import bidict

from   typing import Iterable

class AnalogyDb(bidict):
    """Maintains pairs of terms which are considered analogies.

    A term in 'subject' is mapped to its counterpart in 'nominal'. Notably,
    the directionality is not automatically inverted.

    self:           map: subject term --> nominal term
    """
    def __init__(self, other=None):
        if other is not None:
            super().__init__(other)
        else:
            super().__init__()

    def clone(self):
        return AnalogyDb(self)

    def clone_and_add(self, analogy):
        assert analogy is not None
        result = AnalogyDb(self)
        subject, nominal = analogy
        # Note: This might raise ValueDuplicationError if nominal is already 
        # assigned to a different subject, ensuring integrity.
        result[subject] = nominal
        return result

    @staticmethod
    def from_iterable(iterable: Iterable[tuple[str,str]]):
        """RETURNS: New AnalogyDb, if analogies in 'iterable' are consistent.
                    None, else.
        """
        subjects = AnalogyDb()
        # bidict maintains the inverse automatically, so we can check it cheaply.
        for s, n in iterable:
            # Check 1: Is nominal 'n' already used by a different subject?
            if n in subjects.inverse and subjects.inverse[n] != s: return None
            # Check 2: Is subject 's' already mapped to a different nominal?
            elif s in subjects and subjects[s] != n: return None
            
            subjects[s] = n
        return subjects

    def update(self, other):
        if other is not None:
            if isinstance(other, (AnalogyDb, dict, bidict, list, set, tuple)):
                super().update(other)
            else:
                super().update(other.items())
        return self

    def is_consistent(self, analogy):
        """RETURNS: True, if analogy = tuple(subject, nominal) is consistent
                          with all entries in database; False, else.
        """
        if analogy is None:
            return True

        subject, nominal = analogy
        related_nominal  = self.get(subject)
        if related_nominal is None:
            # Efficient O(1) check using the inverse map from bidict
            return nominal not in self.inverse
        else:
            return related_nominal == nominal

    def is_all_consistent(self, analogy_db):
        """RETURNS: True, if analogy_db is consistent with self.
                    False, else.
        """
        if analogy_db is None:
            return True

        # HERE: Check internal consistency of the incoming data
        # If the input itself is contradictory (e.g. A->1 and A->2), 
        # it cannot be consistent with us.
        if isinstance(analogy_db, (list, tuple)):
             if AnalogyDb.from_iterable(analogy_db) is None:
                 return False
        # If it is a raw dict (not an AnalogyDb/bidict), check for value uniqueness
        elif isinstance(analogy_db, dict) and not isinstance(analogy_db, bidict):
             if len(set(analogy_db.values())) != len(analogy_db):
                 return False

        if type(analogy_db) is list:
            return all(self.is_consistent(item) for item in analogy_db)
        else:
            return all(self.is_consistent(item) for item in analogy_db.items())

    def extend_if_consistent(self, analogy_db):
        if analogy_db is None:
            return True    # OK:   nothing added; no inconsistency.
        elif not self.is_all_consistent(analogy_db):
            return False   # FAIL: analogy_db inconsistent with self
        else:
            self.update(analogy_db)
            return True    # OK:   analogy is added without braking consistency.

    def to_AnalogyDb(self):
        return self

    def __hash__(self):
        return hash(frozenset(self.items()))

    def __eq__(self, other):
        return bidict.__eq__(self, other)

    def __repr__(self):
        name, txt = self.__pretty__()
        return "\n".join("%s: %s" % (x, y) for x, y in txt)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        def length(n):
            if   n is None:          return 1 # -> " "
            elif isinstance(n, str): return len(n)
            elif n <= 1:             return 1
            else:                    return number_of_decimal_digits(n) 

        def prefix(p, Ls, Ln):
            return ""

        def show(analogy_list):
            return ", ".join('"%s"="%s"' % (subject, nominal) for subject, nominal in sorted(analogy_list))

        Ls, Ln = 0, 0

        content_db = defaultdict(list)
        for subject, nominal in self.items():
            content_db[4711].append((subject, nominal))

        txt = [
            (prefix(p, Ls, Ln), show(analogy_list))
            for p, analogy_list in sorted(content_db.items())
        ]
        
        return "AnalogyDb", txt
