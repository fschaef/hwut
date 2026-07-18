"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Core functionality of friends-pairing algorithm.

A 'MatchDb' maintains equivalence relationships between lines from the subject
output and the nominal lines. The main function is '.pairing()' which performs
the pairing process. This pairing, however, can be very expensive computational-
wise. For that, several steps can be applied to avoid an exhaustive pairing 
process:

  .complete_pairing_possible():
     
     tells whether with the current setup it is possible to achieve a 100% 
     pairing.

  .extract_ultimates_and_hopeless():

     extracts those entries from the database, which only have one possible 
     match and those, for which there is no possible match.

The 'MatchDb' is used by the 'exact.py' module.
________________________________________________________________________________
"""
import vut.engine.compare.region.potpourri.solver.maximum_bipartite_matching     as solver_max_bpm
import vut.engine.compare.region.potpourri.solver.csp_backtracking_mrv           as solver_csp_mrv
###
## The following algorithms are 'on hold' since the former algos outperformed them in any scenario
## However, they have been left in place, in the case that someone finds solutions for the bottle-necks.
##
## import vut.engine.compare.region.potpourri.solver.csp_arc_consistency            as solver_csp_arc
## import vut.engine.compare.region.potpourri.solver.csp_chronological_backtracking as solver_csp_chbt


from   vut.engine.compare.engine.analogy_db        import AnalogyDb
from   vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb

from   .potential_pair_db  import PotentialPairDb
from   .result             import PairedGraph, Result

from   typeguard import typechecked

def get_initial_state(subject_line_list, nominal_line_list, analogy_db, abort_early_f: bool) -> Result:
    potential_pair_db = PotentialPairDb.from_raw(subject_line_list, 
                                                 nominal_line_list, 
                                                 abort_early_f)
    subject_n = 0 if not subject_line_list else len(subject_line_list)
    nominal_n = 0 if not nominal_line_list else len(nominal_line_list)

    return Result(potential_pair_db     = potential_pair_db, 
                  pair_db               = PairedGraph(), 
                  analogy_constraint_db = analogy_db if analogy_db is not None else AnalogyDb,
                  required_pair_n       = max(subject_n, nominal_n), 
                  aborted_f             = potential_pair_db is None)

def complete_pairing_is_possible(state: Result) -> bool:
    """RETURNS: True, if a complete pairing is possible under the given 
                      cicumstances.
                False, else.
    """
    if state.aborted_f: return False

    pair_n          = len(state.pair_db)
    db              = state.potential_pair_db
    required_pair_n = state.required_pair_n
    # every subject has a counterpart?
    if   pair_n + len(db)             != required_pair_n: return False 
    # every nominal has a counterpart?
    elif pair_n + db.count_nominals() != required_pair_n: return False 
    # else: there may be a solution where all lines are matched
    else:                                                 return True

def extract_ultimates_and_hopeless(state: Result, abort_early_f: bool) -> Result:
    db         = state.potential_pair_db
    pair_db    = state.pair_db
    analogy_db = state.analogy_constraint_db

    # Iterate until no further improvements are made
    previous_pair_n = -1
    pair_n          = len(pair_db)
    ok_f            = True
    while pair_n > previous_pair_n:
        previous_pair_n = pair_n

        # Extract those pairs, for which there is no alternative
        # => constraints on analogies
        ok_f, analogy_db = db.extract_ultimate_subject_partners(pair_db, analogy_db, abort_early_f)
        if not ok_f:
            if abort_early_f: break

        ok_f, analogy_db = db.extract_ultimate_nominal_partners(pair_db, analogy_db, abort_early_f)
        if not ok_f:
            if abort_early_f: break

        pair_n = len(pair_db)

        # Extract those potential pairs, which interfere with imposed analogies
        if not (ok_f := db.remove_pairs_with_analogy_interferences(analogy_db, abort_early_f)):
            if abort_early_f: break

    return Result(potential_pair_db     = db,
                  pair_db               = pair_db,
                  analogy_constraint_db = analogy_db,
                  required_pair_n       = state.required_pair_n,
                  aborted_f             = not ok_f)

@typechecked 
def pairing_analogy_lines(state: Result) -> Result:
    db = state.potential_pair_db.clone_with_FrozenAnalogyDb()

    state.analogy_constraint_db = FrozenAnalogyDb(state.analogy_constraint_db)

    return solver_csp_mrv.do(db, 
                             state.analogy_constraint_db, 
                             state.pair_db, 
                             state.required_pair_n)

@typechecked 
def pairing_non_analogy_lines(state: Result) -> Result:
    db = state.potential_pair_db
    if not db: return state 
    
    # unconstrained_db: subject_i -> set of nominal_i
    # easy definition of the problem
    unconstrained_db = db.extract_unconstrained()

    new_pair_db      = solver_max_bpm.do(unconstrained_db)
    state.pair_db   |= new_pair_db
    is_complete      = len(new_pair_db) == len(unconstrained_db)
    if not is_complete: state.aborted_f = True
 
    return state

@typechecked
def pairing(state: Result, abort_early_f: bool) -> Result:
    """RETURNS: Result

    Pairing first separates unconstrained potential pairs from those who
    are constrained. Each set has a separate dedicated solving algorithm.
    """
    db = state.potential_pair_db
    if not db: return state 
    
    if unconstrained_db := db.extract_unconstrained():
        # unconstrained_db: subject_i -> set of nominal_i
        new_pair_db = solver_max_bpm.do(unconstrained_db)
        state.pair_db |= new_pair_db
        if len(new_pair_db) != len(unconstrained_db):
            state.aborted_f = True
            if abort_early_f: return state

    if abort_early_f:
        # EARLY ABORT: Before diving deeply into the evolving constraints
        #              algorithms, find quickly out, if a solution exists
        #              for the case that no constraints evolve.
        pseudo_new_pair_db = solver_max_bpm.do(db.unconstrained_clone())
        if len(pseudo_new_pair_db) != len(db):
            # No solution for case with no evolving constraints
            # => no solution possible for case of evolving constraints
            state.aborted_f = True
            return state

    if state.aborted_f or not db: return state

    # HERE: 'db' = potential_pair_db with non-analogies extracted
    db = db.clone_with_FrozenAnalogyDb()
    state.analogy_constraint_db = FrozenAnalogyDb(state.analogy_constraint_db)
    return solver_csp_mrv.do(db, state.analogy_constraint_db, 
                             state.pair_db, 
                             state.required_pair_n)
