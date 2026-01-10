"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A 'Line' of an input stream represented by a sequence of line elements.

For tolerant comparison, the text of a line is interpreted lexically and
split up into 'LineElements' objects. Such line elements may be numbers,
strings, lexemes which match some pattern, whitespace etc.
________________________________________________________________________________
"""
from   vut.engine.compare.input.line_element     import LineElementString, E_ToleranceId
from   vut.engine.compare.input.pattern_finder   import PatternFinder
import vut.engine.compare.engine.association.edit_operations.line   as     edit_operations_line
from   vut.engine.compare.engine.enums           import E_Verdict
from   vut.engine.compare.engine.analogy_db      import AnalogyDb
from   vut.engine.compare.configuration          import ConfigurationPatternFinder

from   dataclasses import dataclass
from   typeguard   import typechecked

@dataclass
class LineRaw:
    string: str
    lexer:  PatternFinder

    def expand(self):
        return self.lexer.do(self.string)

    __analogy_possible_f:  bool = None
    __analogy_strings:     tuple[str] = None

    def may_have_analogy(self):
        """RETURNS: True, if there may be analogies
                    False, if there is no way there are analogies.

        The 'False' case is the safe assumption! We only apply a quick test 
        checking for the opening analogy bracket.
        """
        if self.__analogy_possible_f is not None: return self.__analogy_possible_f
        self.__analogy_possible_f = self.lexer.may_have_analogy(self.string)

    def analogy_strings(self):
        if self.__analogy_strings is not None: return self.__analogy_strings
        self.__analogy_strings = self.lexer.extract_analogy_strings(self.string)

class Line:
    """An interpretation of a text line in terms of a sequence of 'LineElement'
    objects. Additionally, the line number is stored along.
    """
    def __init__(self, line_n, iterable):
        self.line_n             = line_n
        self._raw              = None
        if iterable is None:
            self.__sequence     = None
            self.__sequence_v   = None
        else:
            self.__sequence     = tuple(iterable)
            self.__sequence_v   = [ le for le in self.sequence if le.tolerance_id != E_ToleranceId.VISIBLE_NOTHING ]
            ## self._structural_hash   = hash(bytes(x.tolerance_id for x in self.sequence))

    @typechecked
    @staticmethod
    def from_raw_line(line_n, line:str , pattern_finder: PatternFinder):
        result = Line(line_n, iterable=None)
        result._raw = LineRaw(line, pattern_finder)
        return result

    @staticmethod
    def from_string(line_n, string):
        return Line(line_n, [LineElementString(string)])

    @staticmethod
    def from_potpourri(line_n, begin_f):
        marker = ConfigurationPatternFinder.potpourri_begin_end_marker
        if begin_f:
            return Line.from_string(line_n, "%s (potpourri: open)" % marker)
        else:
            return Line.from_string(line_n, "%s (potpourri: close)" % marker)

    @staticmethod
    def from_nothing():
        return Line.from_string(None, "")
    @property
    def sequence(self):
        if self.__sequence is None:
            self.__sequence = self._raw.expand()
            # self._raw      = None # let the garbage collector deal with it
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
                    [1] adapted analogy_db required for equivalence to hold.

        IMPORTANT: 'analogy_db' evolves here, it absorbs the new analogies.

        The equivalence check plainly aborts, if the analogy check fails. Thus,
        for the line-by-line stepping this function can be called. It adapts the
        global analogy db. If it fails, the equivalence check anyways aborts,
        and the analogy_db is of no use anymore.
        """
        verdict, analogy_list = self.__compare_core(nominal)
        if not verdict:
            return False, analogy_db
        elif not analogy_db.is_all_consistent(analogy_list):
            return False, analogy_db
        else:
            analogy_db.update(analogy_list)
            return True, analogy_db

    def compare(self, nominal, analogy_db):
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.

        IMPORTANT: 'analogy_db' does not evolve here, 
                   a new one is created with updated content.

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

    def compare_raw(self, nominal):
        """RETURNS: [0] True, if subject and nominal line textually EQUAL
                        False, they are not textually EQUAL but may be EQUIVALENT
                    [1] in case of 'True' the list of required analogies.

        In case of [0] == True, the analogies still need to hold.
        """
        if self._raw and nominal._raw and self._raw.string == nominal._raw.string:
            if self._raw.may_have_analogy():
                # If two lines are textually equal, then all the analogies must be trivial
                return True, [ (a, a) for a in self._raw.analogy_strings()]
            else:
                return True, []
        return False, None

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
            result.analogy_db.mark_line_numbers(self.line_n, nominal.line_n)
            result.analogy_db.update(analogy_db)
        else:
            result.analogy_db.assign(analogy_db)

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
