"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Associating a line from the subject stream with a line of the nominal
         stream

These associations are used for display of similar lines. Such associations
are based on the following procedures:

    -- LineSequence: edit_operation/line_sequence.py
    -- Potpourri:    friends_pairing/core.py

Displaying similar lines shall shed some light on HWUT's tolerant comparison
process while inspecting the output of unit tests.
________________________________________________________________________________
"""
from   vut.engine.compare.tolerance.line_element import E_ToleranceId, \
                                                        LineElement
from   vut.engine.compare.engine.line            import Line
from   vut.engine.compare.engine.core            import E_PotpourriBorder
from   vut.engine.compare.engine.analogy_db      import AnalogyDb
from   vut.engine.compare.edit_operations.edit   import E_EditId, Edit, EditSequence
from   vut.engine.compare.edit_operations.line   import position_increment_db
from   vut.external.quex.typed                   import typed

from   collections import namedtuple
from   typeguard   import typechecked
import sys
from   enum import Enum, auto
from   dataclasses import dataclass
from   abc import ABC

class E_NominalRelationId(Enum):
    OK_GOOD                    = auto()  # Subject and nominal 'element' object are equivalent.
    OK_TOLERATED               = auto()  # == GOOD, only that content may differ (used in diff-display).
    OK_VISIBLE_NOTHING         = auto()  # == GOOD, nominal has a 'visible nothing' where subject has nothing.
    OK_SUBJECT_VISIBLE_NOTHING = auto()  # == GOOD, subject has a 'visible nothing' where nominal has nothing.
    BAD_TRANSPOSE              = auto()  # Heal: Two 'element' objects in subject are transposed.
    BAD_SUBJECT_HAS_NOT        = auto()  # Heal: 'element' from nominal is inserted.
    BAD_SUBJECT_HAS            = auto()  # Heal: 'element' from subject is deleted.
    BAD_SUBJECT_DIFFERS        = auto()  # Bad:  Content of subject and nominal 'element' differs.
    BAD_SUBJECT_TYPE_DIFFERS   = auto()  # Bad:  Type of subject and nominal 'element' differs.

class E_SubjectRelationId(Enum):
    OK_GOOD                    = auto()  # Subject and nominal 'element' object are equivalent.
    OK_TOLERATED               = auto()  # == GOOD, only that content may differ (used in diff-display).
    OK_NOMINAL_VISIBLE_NOTHING = auto()  # == GOOD, nominal has a 'visible nothing' where subject has nothing.
    OK_VISIBLE_NOTHING         = auto()  # == GOOD, subject has a 'visible nothing' where nominal has nothing.
    BAD_TRANSPOSE              = auto()  # Heal: Two 'element' objects in subject are transposed.
    BAD_NOMINAL_HAS            = auto()  # Heal: 'element' from nominal is inserted.
    BAD_NOMINAL_HAS_NOT        = auto()  # Heal: 'element' from nominal is inserted.
    BAD_NOMINAL_DIFFERS        = auto()  # Bad:  Content of subject and nominal 'element' differs.
    BAD_NOMINAL_TYPE_DIFFERS   = auto()  # Bad:  Type of subject and nominal 'element' differs.
    
E_NominalRelationId.db = {
    E_EditId.GOOD:            E_NominalRelationId.OK_GOOD,
    E_EditId.GOOD_TOLERATED:  E_NominalRelationId.OK_TOLERATED,
    E_EditId.GOOD_INSERT:     E_NominalRelationId.OK_VISIBLE_NOTHING,
    E_EditId.GOOD_DELETE:     E_NominalRelationId.OK_SUBJECT_VISIBLE_NOTHING,
    E_EditId.TRANSPOSE:       E_NominalRelationId.BAD_TRANSPOSE,
    E_EditId.INSERT:          E_NominalRelationId.BAD_SUBJECT_HAS_NOT,
    E_EditId.DELETE:          E_NominalRelationId.BAD_SUBJECT_HAS,
    E_EditId.SUBSTITUTE:      E_NominalRelationId.BAD_SUBJECT_DIFFERS,
    E_EditId.SUBSTITUTE_TYPE: E_NominalRelationId.BAD_SUBJECT_TYPE_DIFFERS
}

E_SubjectRelationId.db = {
    E_EditId.GOOD:            E_SubjectRelationId.OK_GOOD,
    E_EditId.GOOD_TOLERATED:  E_SubjectRelationId.OK_TOLERATED,
    E_EditId.GOOD_INSERT:     E_SubjectRelationId.OK_NOMINAL_VISIBLE_NOTHING,
    E_EditId.GOOD_DELETE:     E_SubjectRelationId.OK_VISIBLE_NOTHING,
    E_EditId.TRANSPOSE:       E_SubjectRelationId.BAD_TRANSPOSE,
    E_EditId.INSERT:          E_SubjectRelationId.BAD_NOMINAL_HAS,
    E_EditId.DELETE:          E_SubjectRelationId.BAD_NOMINAL_HAS_NOT,
    E_EditId.SUBSTITUTE:      E_SubjectRelationId.BAD_NOMINAL_DIFFERS,
    E_EditId.SUBSTITUTE_TYPE: E_SubjectRelationId.BAD_NOMINAL_TYPE_DIFFERS
}

@dataclass(frozen=True)
class Cell(ABC):
    relation_id: E_SubjectRelationId | E_NominalRelationId
    tolerance_id: E_ToleranceId

@dataclass(frozen=True)
class SubjectCell(Cell):
    subject:        str | None
    nominal_ref_i:  int

@dataclass(frozen=True)
class NominalCell(Cell):
    nominal:        str | None
    subject_ref_i:  int

class LineElementPair:
   @typechecked 
   def __init__(self, edit_id: E_EditId, subject: LineElement|None, nominal: LineElement|None):
       self.edit_id = edit_id
       self.subject = subject
       self.nominal = nominal

   @staticmethod
   def none(subject, nominal):
       return LineElementPair(E_EditId.NONE, subject, nominal)

   def is_analogy_error(self):
       if     self.edit_id != E_EditId.SUBSTITUTE \
          and self.edit_id != E_EditId.SUBSTITUTE_TYPE:
            return False

       def _is_analogy(le):
           return le is not None and le.tolerance_id == E_ToleranceId.ANALOGY

       return _is_analogy(self.subject) or _is_analogy(self.nominal)

   def string_pair(self):
       return "" if self.subject is None else self.subject.string, \
              "" if self.nominal is None else self.nominal.string
              

class LinePair:
    """An association of a line from the subject input stream and a line
    from the nominal input stream.
    """
    @typechecked 
    def __init__(self, 
                 subject:          Line|None, 
                 nominal:          Line|None, 
                 edit_list         = tuple(), 
                 potpourri_border: E_PotpourriBorder = E_PotpourriBorder.NONE):
        assert edit_list is None or all(isinstance(x, Edit) for x in edit_list)
        self.edit_list = edit_list
        self.subject   = subject
        self.nominal   = nominal
        self.border    = potpourri_border

    @staticmethod
    @typed(subject=(None, Line), nominal=(None, Line), border=E_PotpourriBorder)
    def potpourri_border(subject, nominal, border):
        return LinePair(subject, nominal, [], border)

    @staticmethod
    def empty(initial_subject=None, edit_list=tuple()):
        return LinePair(subject   = initial_subject,
                        nominal   = None, 
                        edit_list = edit_list)

    @staticmethod
    def from_text(subject_line_n, subject_txt, nominal_line_n, nominal_txt):
        subject = Line.from_string(subject_line_n, subject_txt)
        nominal = Line.from_string(nominal_line_n, nominal_txt)
        return LinePair(subject, nominal)

    def is_empty(self):
        return self.nominal is None

    def is_good_or_tolerated(self):
        """RETURNS: True, if all entries are GOOD or GOOD_TOLERATED.
                    False, else.
        """
        if   self.subject is None: 
            return False
        elif self.nominal is None: 
            return False
        elif not self.edit_list:
            return True
        else:
            return all(edit.id == E_EditId.GOOD or edit.id == E_EditId.GOOD_TOLERATED 
                       for edit in self.edit_list)

    def is_good(self):
        """RETURNS: True, if all entries are GOOD.
                    False, else.
        """
        if   self.subject is None: 
            return False
        elif self.nominal is None: 
            return False
        elif not self.edit_list:
            return True
        else:
            return all(edit.id == E_EditId.GOOD for edit in self.edit_list)

    def analogy_errors(self):
        """RETURNS: Set of pairs (subject, nominal) where analogies have not been met.
        """
        return set(
            lep.string_pair()
            for lep in self.line_element_pair_list()
            if lep.is_analogy_error()
        )

    def line_element_pair_list(self) -> list[LineElementPair]:
        """RETURNS: list of LineElementPair-s

        That is, the line elements of the subject and the nominal lines are combined
        pairwise according to the prescribed edit operations.
        """
        ## TODO: a subject list of LineElement and a nominal one
        ##       E_CellInfo.GOOD, TOLERATED, INSERTED, DELETED, TRANSPOSED, etc. for subject.
        ##       E_CellInfo.NOMINAL_AND_SUBJECT_GOOD etc. for nominal line element
        if   self.subject is None and self.nominal is None:
            result = []
        elif self.subject is None:
            result = [
                LineElementPair.none(None, n) for n in self.nominal.sequence
            ]
        elif self.nominal is None:
            result = [
                LineElementPair.none(s, None) for s in self.subject.sequence
            ]
        elif not self.edit_list:
            result = [
                LineElementPair.none(s, n) 
                for s, n in zip(self.subject.sequence, self.nominal.sequence)
            ]
        else:
            subject_length   = len(self.subject.sequence)
            nominal_length   = len(self.nominal.sequence)
            result           = []
            transpose_id_set = set()
            si = ni = 0
            for edit in self.edit_list:
                if si == subject_length and ni == nominal_length:
                    break
                elif edit.id == E_EditId.TRANSPOSE:
                    transpose_id_set.add(edit.transpose_ai)

                subject = None if si >= subject_length else self.subject.sequence[si]
                nominal = None if ni >= nominal_length else self.nominal.sequence[ni]

                edit_id = edit.id
                if si in transpose_id_set and edit.id != E_EditId.INSERT:
                    edit_id = E_EditId.TRANSPOSE
                elif edit.id == E_EditId.INSERT:
                    subject = None
                elif edit.id == E_EditId.DELETE:
                    nominal = None
                result.append(LineElementPair(edit_id, subject, nominal))

                s_incr, n_incr = position_increment_db[edit.id]
                si += s_incr
                ni += n_incr

        return result

    def subject_and_nominal_line_element_lists(self):
            """RETURNS: [0] subject cell list (SubjectCell), 
                        [1] nominal cell list (NominalCell)
            """
            if self.subject is None and self.nominal is None:
                return [], []

            subject_list = []
            nominal_list = []
            si = ni = 0

            # We need to pre-calculate the mapping for Transpositions
            # To know which CELL index a NOMINAL element ended up in.
            nominal_element_to_cell_map = {}
            for cell_i, edit in enumerate(self.edit_list):
                _, n_incr = position_increment_db[edit.id]
                if n_incr > 0:
                    nominal_element_to_cell_map[ni] = cell_i
                ni += n_incr
            
            # Reset ni for the actual extraction loop
            ni = 0

            for cell_i, edit in enumerate(self.edit_list):
                s_incr, n_incr = position_increment_db[edit.id]

                # --- 1. Subject Side ---
                s_txt, s_tol = None, E_ToleranceId.STRING
                if s_incr > 0 and self.subject and si < len(self.subject.sequence):
                    el = self.subject.sequence[si]
                    s_txt, s_tol = el.string, el.tolerance_id
                
                # REFERENCE LOGIC: 
                # Where is the nominal partner in the CELL list?
                if edit.id == E_EditId.TRANSPOSE:
                    # Point to the cell that consumed the transposed nominal index
                    n_ref_cell = nominal_element_to_cell_map.get(edit.transpose_ai, cell_i)
                elif n_incr > 0:
                    # Standard match: the nominal partner is in this same cell row
                    n_ref_cell = cell_i
                else:
                    # It's a DELETE (Subject exists, Nominal is a gap)
                    n_ref_cell = cell_i 

                subject_list.append(SubjectCell(
                    relation_id=E_SubjectRelationId.db[edit.id],
                    tolerance_id=s_tol,
                    subject=s_txt,
                    nominal_ref_i=n_ref_cell # Now referencing CELL index
                ))

                # --- 2. Nominal Side ---
                n_txt, n_tol = None, E_ToleranceId.STRING
                if n_incr > 0 and self.nominal and ni < len(self.nominal.sequence):
                    el = self.nominal.sequence[ni]
                    n_txt, n_tol = el.string, el.tolerance_id

                nominal_list.append(NominalCell(
                    relation_id=E_NominalRelationId.db[edit.id],
                    tolerance_id=n_tol,
                    nominal=n_txt,
                    subject_ref_i=cell_i # Usually this same row
                ))

                si += s_incr
                ni += n_incr

            return subject_list, nominal_list

    def max_character_n(self):
        """RETURNS: Max. number of characters in either subject or nominal.
        """
        subject_n = 0 if self.subject is None else self.subject.character_n()
        nominal_n = 0 if self.nominal is None else self.nominal.character_n()
        return max(subject_n, nominal_n)

    def line_number_strings(self):
        """RETURNS: tuple (subject string, nominal string) 
            
        where each string represents the according line number. No line number is reported 
        as empty string.
        """
        return ("" if self.subject is None else "%s" % self.subject.line_n,
                "" if self.nominal is None else "%s" % self.nominal.line_n)

    def __lt__(self, other): # pragma no cover
        def adapt(mseq):
            if mseq is None: return sys.float_info.max
            else:            return mseq.line_n

        return adapt(self.subject) < adapt(other.subject)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LinePair", [
            ("subject",    self.subject),
            ("nominal",    self.nominal),
            ("edit_list",  EditSequence.describe(self.edit_list)),
        ]
