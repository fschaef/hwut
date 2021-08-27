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
from   vut.engine.compare.tolerance.line_element import E_ToleranceId
from   vut.engine.compare.engine.line            import Line
from   vut.engine.compare.engine.analogy_db      import AnalogyDb
import vut.engine.compare.edit_operations.line   as     edit_operations_line
from   vut.engine.compare.edit_operations.line   import Edit, Edit_none, E_EditLine
from   vut.external.quex.typed                   import typed

from   collections import namedtuple
import sys

LineElementAssociation = namedtuple("LineElementAssociation", ("edit_id", "subject", "nominal"))

class LineAssociation:
    """An association of a line from the subject input stream and a line
    from the nominal input stream.
    """
    @typed(subject=(None, Line), nominal=(None, Line))
    def __init__(self, subject, nominal, edit_list=tuple()):
        assert edit_list is None or all(isinstance(x, Edit) for x in edit_list)
        self.edit_list = edit_list
        self.subject   = subject
        self.nominal   = nominal

    @staticmethod
    def empty(initial_subject):
        return LineAssociation(subject = initial_subject,
                               nominal = None)

    @staticmethod
    def from_text(subject_line_n, subject_txt, nominal_line_n, nominal_txt):
        subject = Line.from_string(subject_line_n, subject_txt)
        nominal = Line.from_string(nominal_line_n, nominal_txt)
        return LineAssociation(subject, nominal)

    def is_empty(self):
        return self.nominal is None

    def has_analogy_error(self):
        def _is_analogy(le):
            return le is not None and le.tolerance_id == E_ToleranceId.ANALOGY

        def _is_analogy_error(lela):
            if     lela.edit_id != E_EditLine.SUBSTITUTE \
               and lela.edit_id != E_EditLine.SUBSTITUTE_TYPE:
                return False
            else:
                return _is_analogy(lela.subject) or _is_analogy(lela.nominal)

        return any(_is_analogy_error(lela) 
                   for lela in self.line_element_association_list())

    def line_element_association_list(self):
        """RETURNS: list of LineElementAssociation-s

        That is, the line elements of the subject and the nominal lines are combined
        pairwise according to the prescribed edit operations.
        """
        if   self.subject is None:
            result = [
                LineElementAssociation(E_EditLine.NONE, None, n) 
                for n in self.nominal.sequence
            ]
        elif self.nominal is None:
            result = [
                LineElementAssociation(E_EditLine.NONE, s, None) 
                for s in self.subject.sequence
            ]
        elif not self.edit_list:
            result = [
                LineElementAssociation(E_EditLine.NONE, s, n) 
                for s, n in zip(self.subject.sequence, self.nominal.sequence)
            ]
        else:
            subject_length  = len(self.subject.sequence)
            nominal_length  = len(self.nominal.sequence)
            result          = []
            transpose_id_set = set()
            si = ni = 0
            for edit in self.edit_list:
                if edit.id == E_EditLine.TRANSPOSE:
                    transpose_id_set.add(edit.transpose_ai)

                subject = None if si >= subject_length else self.subject.sequence[si]
                nominal = None if ni >= nominal_length else self.nominal.sequence[ni]

                edit_id = edit.id
                if si in transpose_id_set and edit.id != E_EditLine.INSERT:
                    edit_id = E_EditLine.TRANSPOSE
                elif edit.id == E_EditLine.INSERT:
                    subject = None
                elif edit.id == E_EditLine.DELETE:
                    nominal = None
                result.append(LineElementAssociation(edit_id, subject, nominal))

                s_incr, n_incr = edit_operations_line.position_increment_db[edit.id]
                si += s_incr
                ni += n_incr
        return result

    def __lt__(self, other): # pragma no cover
        def adapt(mseq):
            if mseq is None: return sys.float_info.max
            else:            return mseq.line_n

        return adapt(self.subject) < adapt(other.subject)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineAssociation", [
            ("subject",    self.subject),
            ("nominal",    self.nominal),
            ("edit_list",  edit_operations_line.Edit_list_description(self.edit_list)),
        ]
