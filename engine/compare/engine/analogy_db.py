"""SPDX License: MIT; (C) Frank-Rene Schäfer; Project: hwut
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
from   hwut.engine.quex.typed import typed 
from   collections            import namedtuple, defaultdict

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

    def update(self, other):
        if other is not None:
            dict.update(self, other)
            if isinstance(other, AnalogyDb):
                self.line_number_db.update(other.line_number_db)
        return self

    def assign(self, other):
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
            return not nominal in self.values()
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

    def __repr__(self):
        content_db = defaultdict(list)
        for subject, nominal in self.items():
            content_db[self.line_number_db.get(subject)].append((subject, nominal))

        def prefix(line_number_pair):
            if line_number_pair is not None:
                return "[%s]:[%s] " % line_number_pair
            else:
                return ""

        def show(analogy_list):
            return ", ".join('"%s":"%s"' % (subject, nominal) for subject, nominal in sorted(analogy_list))

        return "; ".join(
            '%s%s' % (prefix(line_number_pair), show(analogy_list))
            for line_number_pair, analogy_list in sorted(content_db.items())
        )

