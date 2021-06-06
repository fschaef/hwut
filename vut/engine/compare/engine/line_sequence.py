"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'LineSequence' input chunk.

LineSequence: set of text lines where the sequence matters.

The two main functions of 'LineSequence' are (derived from 'InputChunk')

   .compare()           --> determines whether the chunk is equivalent to
                            another.
   .line_associations() --> determines which lines should be best associated
                            for display.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.core                   import E_Verdict
from   vut.engine.compare.engine.input_chunk            import InputChunk, \
                                                              E_Chunk
from   vut.engine.compare.engine.line_association       import LineAssociation
import vut.engine.compare.edit_operations.line_sequence as     edit_operations_line_sequence
from   vut.engine.compare.edit_operations.line_sequence import E_EditLineSequence, \
                                                              EditsLineSequence

class LineSequence(InputChunk):
    """Set of lines where the sequence matters.
    """
    def type(self):
        return E_Chunk.LINE_SEQUENCE

    def _compare(self, nominal, analogy_db) -> E_Verdict:
        """RETURNS: [0] True, if 'self' and 'nominal' are equivalent.
                        False, else.
                    [1] AnalogyDb required for the equivalents of [0] to hold.
        """
        for subject_line, nominal_line in zip(self.line_list, nominal.line_list):
            verdict, analogy_db = subject_line.compare(nominal_line, analogy_db)
            if verdict == False:
                return E_Verdict.DIFFERENT, analogy_db
        else:
            return E_Verdict.EQUIVALENT, analogy_db

    def _line_associations(self, nominal, analogy_db):
        """RETURNS: list 'LineAssociation'-s

        See 'InputChunk.line_associations()' for further explanations.
        """
        editions = edit_operations_line_sequence.do(self.line_list,
                                                    nominal.line_list,
                                                    analogy_db)
        assert isinstance(editions, EditsLineSequence)

        if not editions.edit_list:
            return [], editions.analogy_db

        def iterable(edit_line_list):
            si, ni = 0, 0
            for edit_id, edit_list in edit_line_list:
                if   edit_id == E_EditLineSequence.GOOD or edit_id == E_EditLineSequence.SUBSTITUTE:
                    subject_seq = self.line_list[si]
                    nominal_seq = nominal.line_list[ni]
                elif edit_id == E_EditLineSequence.INSERT:
                    subject_seq = None # nominal inserted, no counterpart in subject
                    nominal_seq = nominal.line_list[ni]
                elif edit_id == E_EditLineSequence.DELETE:
                    subject_seq = self.line_list[si]
                    nominal_seq = None # subject inserted, no counterpart in nominal
                else:
                    assert False # pragma: no cover

                yield subject_seq, nominal_seq, edit_list
                s_incr, n_incr = edit_operations_line_sequence.position_increment_db[edit_id]
                si += s_incr
                ni += n_incr

        result = [
            LineAssociation(subject_seq, nominal_seq, edit_list)
            for subject_seq, nominal_seq, edit_list in iterable(editions.edit_list)
        ]
        return result, editions.analogy_db

    def __repr__(self): # pragma no cover
        return "\n".join("%03i: %s" % (line.line_n, line) for line in self.line_list)


