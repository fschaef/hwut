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
import vut.engine.compare.friends_pairing.pairing_core  as p
from   vut.engine.compare.engine.analogy_db             import AnalogyDb

from   .unpaired_candidate_graph          import UnpairedCandidateGraph
from   .result                            import PairedGraph, Result


def get_initial_state(subject_line_list, nominal_line_list, abort_early_f: bool) -> Result:
    potential_pair_db = UnpairedCandidateGraph.from_raw(subject_line_list, 
                                                        nominal_line_list, 
                                                        abort_early_f)
    subject_n = 0 if not subject_line_list else len(subject_line_list)
    nominal_n = 0 if not nominal_line_list else len(nominal_line_list)

    return Result(potential_pair_db     = potential_pair_db, 
                  pair_db               = PairedGraph(), 
                  analogy_constraint_db = AnalogyDb(),
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
        if not (ok_f := db.extract_ultimate_subject_partners(pair_db, analogy_db, abort_early_f)):
            if abort_early_f: break
        if not (ok_f := db.extract_ultimate_nominal_partners(pair_db, analogy_db, abort_early_f)):
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

def pairing(state: Result) -> Result:
    return p.pair_with_analogy_constraints(state)
