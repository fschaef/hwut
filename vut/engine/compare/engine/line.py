"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A 'Line' of an input stream represented by a sequence of line elements.

For tolerant comparison, the text of a line is interpreted lexically and
split up into 'LineElements' objects. Such line elements may be numbers,
strings, lexemes which match some pattern, whitespace etc.
________________________________________________________________________________
"""
from   vut.engine.compare.input.line_element     import E_ToleranceId
from   vut.engine.compare.input.pattern_finder   import PatternFinder
import vut.engine.compare.engine.association.line_sequence.edit_operations.line   as     edit_operations_line
from   vut.engine.compare.engine.enums           import E_Verdict
from   vut.engine.compare.engine.analogy_db      import AnalogyDb
from   vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb

from   dataclasses import dataclass

@dataclass
class LineRaw:
    string: str
    lexer:  PatternFinder

class Line:
    """An interpretation of a text line in terms of a sequence of 'LineElement'
    objects. Additionally, the line number is stored along.
    """
    __slots__ = ("line_n", "_string", "__analogy_f", "__analogy_strings", "__uniform_string", "__sequence", "__sequence_v", "lexer")

    def __init__(self, line_n, line:str , pattern_finder: PatternFinder):
        self.line_n            = line_n
        self._string           = line
        self.__analogy_f       = None
        self.__analogy_strings = None
        self.__uniform_string  = None
        self.__sequence        = None
        self.__sequence_v      = None
        self.lexer             = pattern_finder

    def has_analogy(self):
        if self.__analogy_f is None:
            self.__analogy_f = self.lexer.has_analogy(self._string)
        return self.__analogy_f

    def _UT_set_sequence(self, sequence):
        self.__sequence = sequence

    def uniform_string(self):
        if self.__uniform_string is None:
            self.__uniform_string = self.lexer.uniform(self._string)
        return self.__uniform_string

    def analogy_strings(self):
        if self.__analogy_strings is not None: 
            self.__analogy_strings = self.lexer.extract_analogy_strings(self._string)
        return self.__analogy_strings

    def is_literally_equivalent_to(self, nominal):
        """RETURNS: [0] True, if subject and nominal line textually EQUAL
                        False, they are not literally EQUAL but may be EQUIVALENT
                    [1] in case of 'True' the list of required analogies.

        In case of [0] == True, the analogies still need to hold.
        """
        if not (self._string == nominal._string or self.uniform_string() == nominal.uniform_string()):
            return False, []
        elif self.has_analogy():
            # If two lines are textually equal, then all the analogies must be trivial
            return True, [ (a, a) for a in self.analogy_strings()]
        else:
            return True, []

    @property
    def sequence(self):
        if self.__sequence is None:
            self.__sequence = self.lexer.do(self._string)
        return self.__sequence

    @property
    def sequence_v(self):
        if self.__sequence_v is None:
            # 'self.sequence' instantiates lazily. see property 'sequence'
            self.__sequence_v = [ 
                le for le in self.sequence 
                if le.tolerance_id != E_ToleranceId.VISIBLE_NOTHING 
            ]
        return self.__sequence_v

    def character_n(self):
        """RETURNS: Number of characters in present in the line.
        """
        return sum(len(le._string) for le in self.sequence)

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
        error_n   = sum(s._string != n._string for s, n in zip(subject, nominal))

        return (length_d + error_n) / (2 * l_max)

    def is_equivalent(self, nominal, analogy_db):
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] required list of analogy pairs

        IMPORTANT: 'analogy_db' evolves here, it absorbs the new analogies.

        The equivalence check plainly aborts, if the analogy check fails. Thus,
        for the line-by-line stepping this function can be called. It adapts the
        global analogy db. If it fails, the equivalence check anyways aborts,
        and the analogy_db is of no use anymore.
        """
        verdict, analogy_list = self.__compare_core(nominal)
        if not verdict:
            return False, analogy_list
        elif not analogy_db.is_all_consistent(analogy_list):
            return False, analogy_list
        else:
            return True, analogy_list

    def compare_and_provide_analogies(self, nominal):
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold,
                        None, else

        IMPORTANT: 'analogy_db' does not evolve here, 
                   a new one is created with updated content.

        In case of failure, the old 'analogy_db' is returned. That is, two lines
        which are not equivalent do not impose new analogies.
        """
        verdict, analogy_list = self.__compare_core(nominal)
        if not verdict:        return False, None
        elif not analogy_list: return True, None
            
        analogy_db = FrozenAnalogyDb.if_consistent(analogy_list)
        # analogy_db = AnalogyDb.from_iterable(analogy_list)
        if analogy_db is None: return False, None
        else:                  return True, analogy_db

    def __compare_core(self, nominal):
        """RETURNS: [0] verdict: True or False
                    [1] list of required analogies for verdict (if True)
        """
        self_sequence    = self.sequence_v
        nominal_sequence = nominal.sequence_v
        if len(self_sequence) != len(nominal_sequence):
            return False, []

        analogy_list = []
        for subject_le, nominal_le in zip(self_sequence, nominal_sequence):
            verdict, analogy = subject_le.compare(nominal_le)
            if verdict != E_Verdict.EQUIVALENT:
                return False, []
            elif analogy:
                analogy_list.append(analogy)

        return True, analogy_list

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
            result.analogy_db = result.analogy_db.update(analogy_db)
        else:
            result.analogy_db = analogy_db.clone() if analogy_db else AnalogyDb()

        # too slow for mios of operations
        # assert isinstance(result, edit_operations_line.EditSequence)
        return result

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
