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
import vut.engine.compare.potpourri.matching as m
from   typeguard import typechecked

@typechecked
def do(subject_line_list, nominal_line_list, analogy_db, abort_early_f=False):
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

    if not m.complete_pairing_is_possible(state): 
        if abort_early_f: return False, state.pair_db, state.analogy_constraint_db
        else:             aborted_f = True
    
    if (state := m.pairing(state, abort_early_f)).aborted_f: 
        if abort_early_f: return False, state.pair_db, state.analogy_constraint_db
        else:             aborted_f = True

    previous_pair_n = _assert_progress(state, previous_pair_n)

    return not aborted_f, state.pair_db, state.analogy_constraint_db
