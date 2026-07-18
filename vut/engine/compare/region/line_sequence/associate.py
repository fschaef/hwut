from   vut.engine.compare.engine.frozen_analogy_db                         import FrozenAnalogyDb
from   vut.engine.compare.core.line_pair                     import LinePair
import vut.engine.compare.core.edit_operations.line_sequence as     edit_operations_line_sequence
from   vut.engine.compare.core.edit_operations.edit          import (E_EditId, 
                                                                                   EditSequence)

def do(subject, nominal, analogy_db):
    """RETURNS: list 'LinePair'-s

    See 'InputChunk.line_pairs()' for further explanations.
    """
    editions: EditSequence = edit_operations_line_sequence.do(subject.line_list,
                                                              nominal.line_list,
                                                              FrozenAnalogyDb(analogy_db))

    if not editions.edit_list:
        return [], editions.analogy_db.to_AnalogyDb()

    def iterable(edit_sequence):
        si, ni = 0, 0
        for edit in edit_sequence:
            if edit.id == E_EditId.SUBSTITUTE:
                subject_seq = subject.line_list[si]
                nominal_seq = nominal.line_list[ni]
            elif   edit.id == E_EditId.GOOD or edit.id == E_EditId.GOOD_TOLERATED:
                subject_seq = subject.line_list[si]
                nominal_seq = nominal.line_list[ni]
            elif edit.id == E_EditId.INSERT or edit.id == E_EditId.GOOD_INSERT:
                subject_seq = None # nominal inserted, no counterpart in subject
                nominal_seq = nominal.line_list[ni]
            elif edit.id == E_EditId.DELETE or edit.id == E_EditId.GOOD_DELETE:
                subject_seq = subject.line_list[si]
                nominal_seq = None # subject inserted, no counterpart in nominal
            else:
                assert edit.id != E_EditId.TRANSPOSE         # pragma: no cover
                assert edit.id != E_EditId.SUBSTITUTE_TYPE   # pragma: no cover
                assert False                                 # pragma: no cover

            yield subject_seq, nominal_seq, edit.edit_list, edit.cost, edit.id
            s_incr, n_incr = edit_operations_line_sequence.position_increment_db[edit.id]
            si += s_incr
            ni += n_incr

    result = [
        LinePair(subject_seq, nominal_seq, edit_list, cost = cost,
                 seq_edit_id = seq_edit_id)
        for subject_seq, nominal_seq, edit_list, cost, seq_edit_id
        in iterable(editions.edit_list)
    ]
    return result, editions.analogy_db.to_AnalogyDb()

