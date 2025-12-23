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
from    vut.engine.compare.tolerance.line_element import E_ToleranceId
from    vut.engine.compare.engine.line            import Line
from    vut.engine.compare.engine.core            import E_PotpourriBorder
from    vut.engine.compare.edit_operations.edit   import E_EditId, Edit, EditSequence
from    vut.engine.compare.edit_operations.line   import position_increment_db
from    vut.external.quex.typed                   import typed

from    typeguard   import typechecked
import  sys
from    enum import Enum, auto
from    dataclasses import dataclass
from    abc import ABC

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

@dataclass(frozen=True)
class LinePairRaw:
    """Encapsulates the raw objects needed for expansion."""
    subject:   Line | None
    nominal:   Line | None
    edit_list: tuple[Edit, ...]

    def expand(self) -> tuple[list[SubjectCell], list[NominalCell]]:
        if self.subject is None and self.nominal is None:
            return [], []
        elif not self.edit_list:
            return self._handle_missing_side()

        subject_list, nominal_list = [], []
        si = ni = 0

        # Pre-calculate transposition mapping for cell references
        nominal_element_to_cell_map = {}
        for cell_i, edit in enumerate(self.edit_list):
            _, n_incr = position_increment_db[edit.id]
            if n_incr > 0:
                nominal_element_to_cell_map[ni] = cell_i
            ni += n_incr
        
        ni = 0 # Reset
        for cell_i, edit in enumerate(self.edit_list):
            s_incr, n_incr = position_increment_db[edit.id]

            # Extract Subject Data
            if s_incr > 0 and self.subject and si < len(self.subject.sequence):
                s_txt, s_tol = self.subject.sequence[si].string, self.subject.sequence[si].tolerance_id
            else: 
                s_txt, s_tol = None, E_ToleranceId.STRING

            if edit.id == E_EditId.TRANSPOSE:
                n_ref = nominal_element_to_cell_map.get(edit.transpose_ai, cell_i) 
            else: 
                n_ref = cell_i

            # Extract Subject Data
            subject_list.append(SubjectCell(relation_id=E_SubjectRelationId.db[edit.id],
                                            tolerance_id=s_tol,
                                            subject=s_txt,
                                            nominal_ref_i=n_ref)) # Now referencing CELL index

            # Extract Nominal Data
            if n_incr > 0 and self.nominal and ni < len(self.nominal.sequence):
                n_txt, n_tol = self.nominal.sequence[ni].string, self.nominal.sequence[ni].tolerance_id
            else:
                n_txt, n_tol = None, E_ToleranceId.STRING

            nominal_list.append(NominalCell(relation_id=E_NominalRelationId.db[edit.id],
                                            tolerance_id=n_tol,
                                            nominal=n_txt,
                                            subject_ref_i=cell_i)) # Usually this same row

            si += s_incr
            ni += n_incr

        return subject_list, nominal_list

    def _handle_missing_side(self):
        subject_list, nominal_list = [], []
        if self.subject and not self.nominal:
            subject_list = [
                SubjectCell(E_SubjectRelationId.BAD_NOMINAL_HAS_NOT, el.tolerance_id, el.string, -1) 
                for el in self.subject.sequence
            ]
        elif self.nominal and not self.subject:
            nominal_list = [
                NominalCell(E_NominalRelationId.BAD_SUBJECT_HAS, el.tolerance_id, el.string, -1) 
                for el in self.nominal.sequence
            ]
        return subject_list, nominal_list


class LinePair:
    """An association of a line from the subject input stream and a line
    from the nominal input stream.
    """
    @typechecked 
    def __init__(self, 
                 subject:          Line|None, 
                 nominal:          Line|None, 
                 edit_list         = tuple(), 
                 potpourri_border: E_PotpourriBorder = E_PotpourriBorder.NONE,
                 cost:             float = 0.0):
        # Store ingredients in the raw container
        self._raw = LinePairRaw(subject, nominal, edit_list)
        
        # JIT Cache
        self._subject_cell_list = None
        self._nominal_cell_list = None
        
        # Publicly accessible metadata
        self.border = potpourri_border
        self.cost   = cost
        self.subject_line_n = subject.line_n if subject else -1
        self.nominal_line_n = nominal.line_n if nominal else -1
        self.subject_char_n = 0 if subject is None else subject.character_n()
        self.nominal_char_n = 0 if nominal is None else nominal.character_n(),

    @staticmethod
    @typed(subject=(None, Line), nominal=(None, Line), border=E_PotpourriBorder)
    def potpourri_border(subject, nominal, border):
        return LinePair(subject, nominal, tuple(), border)

    @staticmethod
    def empty(initial_subject=None, edit_list=tuple()):
        return LinePair(subject=initial_subject, nominal=None, edit_list=edit_list)

    def _ensure_expanded(self):
        if self._raw is not None:
            self._subject_cell_list, self._nominal_cell_list = self._raw.expand()
            self._raw = None  # The kill-switch for memory reclamation:

    def subject_list(self) -> list[SubjectCell]:
        self._ensure_expanded()
        return self._subject_cell_list

    def nominal_list(self) -> list[NominalCell]:
        self._ensure_expanded()
        return self._nominal_cell_list

    def is_empty(self):
        return self.nominal_line_n == -1

    def analogy_errors(self):
        errors = set()
        for s_c, n_c in zip(self.subject_cell_list(), self.nominal_list()):
            if s_c.tolerance_id != E_ToleranceId.ANALOGY: 
                continue
            elif s_c.relation_id in (E_SubjectRelationId.OK_GOOD, E_SubjectRelationId.OK_TOLERATED):
                continue
            else:
                errors.add((s_c.subject or "", n_c.nominal or ""))
        return errors

    def __lt__(self, other):
        def adapt(x): 
            return sys.float_info.max if x == -1 else x
        return adapt(self.subject_line_n) < adapt(other.subject_line_n)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LinePair", [
            ("subject", self.subject_list()),
            ("nominal", self.nominal_list()),
            ("cost",    self.cost),
        ]
