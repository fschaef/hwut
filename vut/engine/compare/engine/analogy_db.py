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

from   typing import Iterable

LineNumberPair = namedtuple("LineNumberPair", ("subject_line_n", "nominal_line_n"))

class AnalogyDb(dict):
    """Maintains pairs of terms which are considered analogies.

    A term in 'subject' is mapped to its counterpart in 'nominal'. Notably,
    the directionality is not automatically inverted.

    self:           map: subject term --> nominal term
    """
    def __init__(self, other=None):
        if other is not None:
            self.update(other)

    def clone(self):
        return AnalogyDb(self)

    def clone_and_add(self, analogy):
        assert analogy is not None
        result = AnalogyDb(self)
        subject, nominal = analogy
        result[subject] = nominal
        return result

    @staticmethod
    def from_iterable(iterable: Iterable[tuple[str,str]]):
        """RETURNS: New AnalogyDb, if analogies in 'iterable' are consistent.
                    None, else.
        """
        subjects = AnalogyDb()
        nominals = {}
        for s, n in iterable:
            if   n in nominals and nominals[n] != s: return None
            elif s in subjects and subjects[s] != n: return None
            subjects[s] = n
            nominals[n] = s
        return subjects

    def update(self, other):
        if other is not None:
            dict.update(self, other)
        return self

    def update_CLONE(self, other):
        if not other: return self
        result = self.clone()
        dict.update(result, other)
        return result

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
        elif type(analogy_db) is list:
            return all(self.is_consistent(item) for item in analogy_db)
        else:
            return all(self.is_consistent(item) for item in analogy_db.items())

    @staticmethod
    def _try_update_analogy_db(analogy_db, analogy_set):
        if analogy_db.is_all_consistent(list(analogy_set)):
            return True, analogy_db.update_CLONE(analogy_set)
        else:
            return False, analogy_db

    def extend_if_consistent(self, analogy_db):
        if analogy_db is None:
            return True    # OK:   nothing added; no inconsistency.
        elif not self.is_all_consistent(analogy_db):
            return False   # FAIL: analogy_db inconsistent with self
        else:
            dict.update(self, analogy_db)
            return True    # OK:   analogy is added without braking consistency.

    def __hash__(self):
        return hash(frozenset(self.items()))

    def __eq__(self, other):
        return dict.__eq__(self, other)

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
            p = LineNumberPair(" ", " ")
            content_db[p].append((subject, nominal))

        txt = [
            (prefix(p, Ls, Ln), show(analogy_list))
            for p, analogy_list in sorted(content_db.items())
        ]
        
        return "AnalogyDb", txt

