from   vut.engine.compare.engine.enums                  import E_PotpourriBorder, E_Chunk
from   vut.engine.compare.engine.association.line_pair  import LinePair
import vut.engine.compare.engine.potpourri.association  as     potpourri_association

import vut.engine.compare.engine.association.edit_operations.line_sequence as     edit_operations_line_sequence
from   vut.engine.compare.engine.association.edit_operations.edit          import E_EditId, \
                                                                                  EditSequence
def do(subject, nominal, analogy_db):
    """RETURNS: [0] list of 'LinePair'-s
                [1] required analogy_db

    Each 'LinePair' informs about what two lines are to be displayed
    side-by-side to clarify the comparison process and its verdicts. A line
    may be associated with 'None', meaning that there is no line one the
    other side of the display. 'LinePair' objects also report about
    the development of the analogy database.
    """
    assert subject.type() is nominal.type()

    if   subject.type() is E_Chunk.LINE_SEQUENCE: _do = _do_line_sequence
    elif subject.type() is E_Chunk.POTPOURRI:     _do = _do_potpourri
    else:                                         assert False

    return _do(subject, nominal, analogy_db)

def _do_line_sequence(subject, nominal, analogy_db):
    """RETURNS: list 'LinePair'-s

    See 'InputChunk.line_pairs()' for further explanations.
    """
    editions: EditSequence = edit_operations_line_sequence.do(subject.line_list,
                                                              nominal.line_list,
                                                              analogy_db)

    if not editions.edit_list:
        return [], editions.analogy_db

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

            yield subject_seq, nominal_seq, edit.edit_list, edit.cost
            s_incr, n_incr = edit_operations_line_sequence.position_increment_db[edit.id]
            si += s_incr
            ni += n_incr

    result = [
        LinePair(subject_seq, nominal_seq, edit_list, cost = cost)
        for subject_seq, nominal_seq, edit_list, cost in iterable(editions.edit_list)
    ]
    return result, editions.analogy_db

def _do_potpourri(subject, nominal, analogy_db):
    assert len(subject.line_list) >= 2 and len(nominal.line_list) >= 2

    subject_potpourri = subject.line_list[1:-1]    # exclude [0] and [-1]:
    nominal_potpourri = nominal.line_list[1:-1] # first and last line carry Potpourri markers.

    core_result,   \
    new_analogy_db = potpourri_association.do(subject_potpourri,
                                              nominal_potpourri,
                                              analogy_db,
                                              subject.configuration.potpourri_max_comparison_count)

    result = [
        LinePair.potpourri_border(subject.line_list[0], nominal.line_list[0], 
                                  E_PotpourriBorder.BEGIN)
    ]

    def key(x): 
        return (1, x.nominal_line_n) if x.subject_line_n == -1 else (0, x.subject_line_n)
    result.extend(sorted(core_result, key= key))

    result.append(
        LinePair.potpourri_border(subject.line_list[-1], nominal.line_list[-1],
                                  E_PotpourriBorder.END)
    )

    return result, new_analogy_db
