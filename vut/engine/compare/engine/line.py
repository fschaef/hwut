"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A 'Line' of an input stream represented by a sequence of line elements.

For tolerant comparison, the text of a line is interpreted lexically and
split up into 'LineElements' objects. Such line elements may be numbers,
strings, lexemes which match some pattern, whitespace etc.
________________________________________________________________________________
"""
import vut.engine.compare.edit_operations.line   as     edit_operations_line
from   vut.engine.compare.engine.core            import E_Verdict
from   vut.engine.compare.engine.analogy_db      import AnalogyDb
from   vut.engine.compare.tolerance.line_element import LineElementString, E_ToleranceId

class Line:
    """An interpretation of a text line in terms of a sequence of 'LineElement'
    objects. Additionally, the line number is stored along.
    """
    def __init__(self, line_n, iterable):
        self.line_n   = line_n
        self.sequence = tuple(iterable)

    @staticmethod
    def from_string(line_n, string):
        return Line(line_n, [LineElementString(0, len(string), string)])

    @staticmethod
    def from_potpourri(line_n, begin_f):
        if begin_f:
            return Line.from_string(line_n, "|||| (potpourri: open)")
        else:
            return Line.from_string(line_n, "|||| (potpourri: close)")

    @staticmethod
    def from_nothing():
        return Line.from_string(None, "")

    def compare_quickly(self, nominal_line):
        """RETURNS: A 'cost' approximation > 0

        This function quickly compares two sequence of LineElement-s.  It
        investigates (1) their length, (2) their types, (3) the content of the line
        elements. This is fundamentally *less computationally* expensive than
        determining edit operations (insert, delete, transpose, substitute) and
        then computing their cost. 
        """
        subject   = self.sequence
        nominal   = nominal_line.sequence
        l_subject = len(subject)
        l_nominal = len(nominal)
        l_max     = max(l_subject, l_nominal)
        length_d  = abs(l_subject - l_nominal)
        error_n   = sum(s.tolerance_id != n.tolerance_id or not s._compare(n)[0]
                        for s, n in zip(subject, nominal))

        return (length_d + error_n) / (2 * l_max)

    def compare_safely(self, nominal):
        """RETURNS: True, if it is safe to state self == nominal **without**
                          considering analogies.
                    False, else.
        """
        verdict, analogy_list = self.__compare_core(nominal)
        return verdict and not analogy_list

    def compare(self, nominal, analogy_db):
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.

        In case of failure, the old 'analogy_db' is returned. That is, two lines
        which are not equivalent do not impose new analogies.
        """
        verdict, analogy_list = self.__compare_core(nominal)
        if not verdict:
            return False, analogy_db
            
        new_analogy_db = AnalogyDb()
        for analogy in analogy_list:
            if not new_analogy_db.add_if_consistent(analogy):
                return False, analogy_db

        if new_analogy_db:
            new_analogy_db.mark_line_numbers(self.line_n, nominal.line_n)
            new_analogy_db.update(analogy_db)
            analogy_db = new_analogy_db
        return True, analogy_db

    def edit_operations(self, nominal, analogy_db):
        """RETURNS: EditSequence

        Calls 'edit_operations_line.do()' and sets line numbers in analogy
        database if necessary.

        EditSequence.cost       = cost / max. cost; thus in range of [0...1].
        EditSequence.edit_list  = list of 'Edit' objects
        EditSequence.analogy_db = 'AnalogyDb' required for equivalences to hold.
        """
        result = edit_operations_line.do(self.sequence, nominal.sequence, analogy_db)

        if result.cost == 0:
            result.analogy_db.mark_line_numbers(self.line_n, nominal.line_n)
            result.analogy_db.update(analogy_db)
        else:
            result.analogy_db.assign(analogy_db)

        assert isinstance(result, edit_operations_line.EditSequence)
        return result

    def __compare_core(self, nominal):
        """RETURNS: [0] verdict: True or False
                    [1] list of required analogies for verdict (if True)
        """
        self_sequence    = [ le for le in self.sequence if le.tolerance_id != E_ToleranceId.VISIBLE_NOTHING ]
        nominal_sequence = [ le for le in nominal.sequence if le.tolerance_id != E_ToleranceId.VISIBLE_NOTHING ]
        if len(self_sequence) != len(nominal_sequence):
            return False, []

        analogy_list = []
        for subject_le, nominal_le in zip(self_sequence, nominal_sequence):
            verdict, analogy = subject_le.compare(nominal_le)
            if verdict != E_Verdict.EQUIVALENT:
                return False, []
            elif analogy:
                analogy_list.append(analogy)

        return  True, analogy_list

    def __lt__(self, other): # pragma no cover
        return (self.line_n, len(self.sequence)) < (other.line_n, len(other.sequence))

    def __iter__(self):
        return iter(self.sequence)

    def __repr__(self): # pragma no cover
        return ", ".join("[%s]" % str(x) for x in self.sequence)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "Line", [
            ("line_n",   self.line_n),
            ("sequence", self.sequence)
        ]
