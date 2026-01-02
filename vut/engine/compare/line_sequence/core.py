"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'LineSequence' input chunk.

LineSequence: set of text lines where the sequence matters.

The two main functions of 'LineSequence' are (derived from 'InputChunk')

   .compare()           --> determines whether the chunk is equivalent to
                            another.
   .line_pairs() --> determines which lines should be best associated
                            for display.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.enums                  import E_Verdict
from   vut.engine.compare.input.input_chunk             import InputChunk, \
                                                               E_Chunk
from   vut.engine.compare.engine.association.line_pair                     import LinePair
import vut.engine.compare.engine.association.edit_operations.line_sequence as     edit_operations_line_sequence
from   vut.engine.compare.engine.association.edit_operations.edit          import E_EditId, \
                                                                                  EditSequence


class LineSequence(InputChunk):
    """Set of lines where the sequence matters.
    """
    def type(self):
        return E_Chunk.LINE_SEQUENCE

    def _is_equivalent(self, filtered_subject_line_list, filtered_nominal_line_list, analogy_db) -> E_Verdict:
        """RETURNS: [0] True, if 'self' and 'nominal' are equivalent.
                        False, else.
                    [1] AnalogyDb required for the equivalents of [0] to hold.
        """
        # Compare line by line
        for subject_line, nominal_line in zip(filtered_subject_line_list, filtered_nominal_line_list):
            verdict, analogy_db = subject_line.compare(nominal_line, analogy_db)
            if not verdict:
                return E_Verdict.DIFFERENT, analogy_db
        else:
            return E_Verdict.EQUIVALENT, analogy_db

    def _associate_lines(self, nominal, analogy_db):
        """RETURNS: list 'LinePair'-s

        See 'InputChunk.line_pairs()' for further explanations.
        """
        editions: EditSequence = edit_operations_line_sequence.do(self.line_list,
                                                                  nominal.line_list,
                                                                  analogy_db)

        if not editions.edit_list:
            return [], editions.analogy_db

        def iterable(edit_sequence):
            si, ni = 0, 0
            for edit in edit_sequence:
                if edit.id == E_EditId.SUBSTITUTE:
                    subject_seq = self.line_list[si]
                    nominal_seq = nominal.line_list[ni]
                elif   edit.id == E_EditId.GOOD or edit.id == E_EditId.GOOD_TOLERATED:
                    subject_seq = self.line_list[si]
                    nominal_seq = nominal.line_list[ni]
                elif edit.id == E_EditId.INSERT or edit.id == E_EditId.GOOD_INSERT:
                    subject_seq = None # nominal inserted, no counterpart in subject
                    nominal_seq = nominal.line_list[ni]
                elif edit.id == E_EditId.DELETE or edit.id == E_EditId.GOOD_DELETE:
                    subject_seq = self.line_list[si]
                    nominal_seq = None # subject inserted, no counterpart in nominal
                else:
                    assert edit.id != E_EditId.TRANSPOSE         # pragma: no cover
                    assert edit.id != E_EditId.SUBSTITUTE_TYPE   # pragma: no cover
                    assert False                                 # pragma: no cover

                yield subject_seq, nominal_seq, edit.edit_list, edit.cost
                s_incr, n_incr = edit_operations_line_sequence.position_increment_db[edit.id]
                si += s_incr
                ni += n_incr

        result = [
            LinePair(subject_seq, nominal_seq, edit_list, cost = cost)
            for subject_seq, nominal_seq, edit_list, cost in iterable(editions.edit_list)
        ]
        return result, editions.analogy_db

    def __repr__(self): # pragma no cover
        return "\n".join("%03i: %s" % (line.line_n, line) for line in self.line_list)


