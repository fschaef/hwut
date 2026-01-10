"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'Friends pairing' -- finding as many EXACT matches of subject lines
                              matching equivalent nominal lines.

In contrast to a 'LineSequence', the 'Potpourri' input chunk does not require
the lines to appear in the sequence that they are registered in the nominal.

The algorithm matches subject lines and nominal lines which are equivalent.

The additional 'abort_f' flag may instruct the algorithm to abort, as soon
as a complete solution is impossible. Such a quit abort means, that the two 
Potpourri cannot be equivalent (compare() --> False).
________________________________________________________________________________
"""
import vut.engine.compare.engine.potpourri.matching as m
from   typeguard import typechecked

def do(subject, nominal, analogy_db, abort_early_f):
    # non-analogy lines can never match with analogy lines, and vice versa.
    # => treat them separately

    # pair non-analogy lines
    first_verdict, \
    first_pair_db, \
    _              = _core(subject.non_analogy_line_list, 
                           nominal.non_analogy_line_list, 
                           {}, abort_early_f,
                           analogies_involved_f = False)

    if first_verdict is False and abort_early_f:
        return False, first_pair_db, analogy_db

    # pair analogy lines
    second_verdict, \
    second_pair_db, \
    analogy_db      = _core(subject.analogy_line_list, 
                            nominal.analogy_line_list, 
                            analogy_db, abort_early_f,
                            analogies_involved_f = True)

    return first_verdict and second_verdict, \
           first_pair_db | second_pair_db,   \
           analogy_db

@typechecked
def _core(subject_line_list, nominal_line_list, analogy_db, abort_early_f=False, analogies_involved_f=True):
    """RETURNS: [0] verdict
                [1] map: subject line number --> nominal line number
                [2] analogy_db

    Where 'ia' is the index of a line in 'subject_lines' that is equivalent
    and, thus, associated with 'ib' which is a line from 'nominal_lines'.
    """
    def _assert_progress(state, previous_pair_n):
        assert previous_pair_n <= (pair_n := len(state.pair_db))
        return pair_n
        
    aborted_f = False
    if (state := m.get_initial_state(subject_line_list, nominal_line_list, abort_early_f)).aborted_f:
        if abort_early_f: return False, state.pair_db, state.analogy_constraint_db
        else:             aborted_f = True

    if state.potential_pair_db is None:
        return False, state.pair_db, state.analogy_constraint_db

    previous_pair_n = _assert_progress(state, 0)

    if not m.complete_pairing_is_possible(state): 
        if abort_early_f: return False, state.pair_db, state.analogy_constraint_db
        else:             aborted_f = True
    
    if (state := m.extract_ultimates_and_hopeless(state, abort_early_f)).aborted_f:
        if abort_early_f: return False, state.pair_db, state.analogy_constraint_db
        else:             aborted_f = True

    previous_pair_n = _assert_progress(state, previous_pair_n)

    if state.required_pair_n == len(state.pair_db):
        return True, state.pair_db, state.analogy_constraint_db

    elif not m.complete_pairing_is_possible(state): 
        if abort_early_f: return False, state.pair_db, state.analogy_constraint_db
        else:             aborted_f = True
    
    if analogies_involved_f: state = m.pairing_analogy_lines(state)
    else:                    state = m.pairing_non_analogy_lines(state)

    if state.aborted_f:
        if abort_early_f: return False, state.pair_db, state.analogy_constraint_db
        else:             aborted_f = True

    previous_pair_n = _assert_progress(state, previous_pair_n)

    return not aborted_f, state.pair_db, state.analogy_constraint_db
