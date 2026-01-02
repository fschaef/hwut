"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Pairing lines according to similarity (not only equivalent lines).

Where 'exact.py' (or equivalence_check) only tried to find exactly equivalent lines, 
this module tries to associate similar lines. The goal, here, is to provide a 
line-up that can be displayed to expose the 'diff function' via a user interface.
________________________________________________________________________________
"""
from typeguard import typechecked

from   vut.engine.compare.engine.association.line_pair            import LinePair
import vut.engine.compare.engine.association.edit_operations.line as     edit_operations_line
import vut.engine.compare.potpourri.equivalence_check             as     equivalence_check
from   vut.engine.compare.engine.analogy_db                       import AnalogyDb
from   vut.engine.compare.engine.frozen_analogy_db                import FrozenAnalogyDb


def do(subject_line_list, nominal_line_list, analogy_db, max_comparison_count, abort_f=False):
    """RETURNS: sorted list of LinePair objects.
        
    Sort order: sorted by line number of subject. 

    'max_comparison_count' may restrict the number of comparisons. With 
    large number of lines, this may restrict the complexity, therefore,
    feasibility.

    This functions tries to find the best combination of subject and nominal
    lines according to their similarities. Equivalent matches are first found
    using the 'equivalence_check' module. Then, the remaining lines are matched based on
    some cost function that takes their similiarity into account. The cost
    function measures the amount of diffrerence between two lines.
    """
    # 1. STRICT PHASE: High-performance matching
    verdict, couples, analogy_db = equivalence_check.do(subject_line_list,
                                                        nominal_line_list,
                                                        analogy_db,
                                                        abort_early_f=abort_f)

    # Thaw the database to allow 'developing it along the way' in the fuzzy phase
    if isinstance(analogy_db, FrozenAnalogyDb):
        analogy_db = analogy_db.to_AnalogyDb()

    subject_db = dict((x.line_n, x) for x in subject_line_list)  # helper dictionaries:
    nominal_db = dict((x.line_n, x) for x in nominal_line_list)  # line_n -> 'Line' object

    result = []
    
    # 2. INTEGRATE STRICT MATCHES
    # We must calculate the edit operations for strict matches to populate the 
    # visual diff (LinePair) and ensure the analogy_db is fully up to date.
    for si, ni in sorted(couples.items()):
        subject_seq, nominal_seq = subject_db[si], nominal_db[ni]
        
        # NOTE: edit_operations_line.do returns an EditSequence object
        edit_seq = edit_operations_line.do(subject_seq.sequence, 
                                           nominal_seq.sequence, 
                                           analogy_db)
        
        # Adopt the potentially updated analogy_db (strict matches dictate truth)
        analogy_db = edit_seq.analogy_db
        
        result.append(LinePair(subject_seq, 
                               nominal_seq, 
                               edit_seq.edit_list, 
                               cost=edit_seq.cost))

    if not verdict:
        # Associate the remaining subject and nominal lines according to similarity,
        # until either no subject or no nominal remains as mating candidate.
        line_pair_list,     \
        subjects_remaining, \
        nominals_remaining  = _couple_uncoupled(couples, subject_db, nominal_db,
                                                analogy_db, max_comparison_count)

        result.extend(line_pair_list)
        # Associate with 'None' what has no counterpart.
        # Use sys.maxsize for sorting stability later
        result.extend(LinePair(subject_db[ia], None, cost=1.0) for ia in sorted(subjects_remaining))
        result.extend(LinePair(None, nominal_db[ib], cost=1.0) for ib in sorted(nominals_remaining))

    # Final Sort: Restore document order
    def sort_key(lp): return (lp.subject_line_n, lp.nominal_line_n)

    result.sort(key=sort_key)

    return result, analogy_db

def _couple_uncoupled(couples, subject_db, nominal_db, analogy_db, max_comparison_count):
    """RETURNS: [0] list of 'LinePair' objects.
                [1] line numbers of unpaired subject lines
                [2] line numbers of unpaired nominal lines

    subject_db:    line number -> Line object 
    nominal_db:    line number -> Line object 

    DOES NOT AFFECT: 'couples'

    Pairs lines from subject and nominal which are not mentioned in 'couples'.
    """
    # Clone is NOT performed here because the user request is to 
    # "develop the analogy_db along the way".
    
    line_pair_list,     \
    subjects_remaining, \
    nominals_remaining  = _couple_remainders(couples, subject_db, nominal_db, analogy_db, max_comparison_count)

    # One remainder must be empty!
    assert (not subjects_remaining) or (not nominals_remaining)

    return line_pair_list, subjects_remaining, nominals_remaining

@typechecked
def _couple_remainders(couples, subject_db, nominal_db, analogy_db: AnalogyDb | None, max_comparison_count):
    """RETURNS: list of LinePair objects.

    Find couples in the set of remainders according to a least cost
    function. The cost is the amount of difference between the line
    elements.
    """
    subject_done = set(couples.keys())
    nominal_done = set(couples.values())
    
    # Identify available objects for the window calculation
    subjects_avail = [x for x in subject_db.values() if x.line_n not in subject_done]
    nominals_avail = [x for x in nominal_db.values() if x.line_n not in nominal_done]
    
    # Use windowed cost calculation for performance
    cost_db = _get_cost_db(subjects_avail, nominals_avail, max_comparison_count)

    result       = []
    for cost, subject, nominal in cost_db:
        if subject.line_n in subject_done or nominal.line_n in nominal_done:
            continue

        # "Develop analogy_db along the way":
        # We pass the CURRENT analogy_db. If the fuzzy match implies new, 
        # consistent analogies, edit_operations_line returns a new DB containing them.
        edit_seq = edit_operations_line.do(subject.sequence, 
                                           nominal.sequence, 
                                           analogy_db)

        # If consistent, we adopt the new analogies.
        # If inconsistent, edit_operations handles it via substitution costs,
        # and returns an analogy_db that doesn't contain the conflict.
        analogy_db = edit_seq.analogy_db

        result.append(LinePair(subject, nominal, edit_seq.edit_list, cost=edit_seq.cost))
        
        subject_done.add(subject.line_n)
        nominal_done.add(nominal.line_n)

    subjects_remaining = [line_n for line_n in subject_db if line_n not in subject_done]
    nominals_remaining = [line_n for line_n in nominal_db if line_n not in nominal_done]

    return result, sorted(subjects_remaining), sorted(nominals_remaining)

def _get_cost_db(subjects_available, nominals_available, window_size):
    """RETURNS: list of (cost, subject line, nominal line)

    where the list is sorted by cost.
    
    Uses a WINDOWED approach. We only compare lines that are within 
    'window_size' of each other in the remaining lists. This avoids O(N^2).
    """
    cost_db = []
    n_len   = len(nominals_available)
    
    for i, subject in enumerate(subjects_available):
        # Determine window
        start_j = max(0, i - window_size)
        end_j   = min(n_len, i + window_size + 1)
        
        for j in range(start_j, end_j):
            nominal = nominals_available[j]
            
            # Use heuristic quick compare
            cost = subject.compare_quickly(nominal)
            
            # Optimization: Only consider if there is at least some similarity
            if cost < 1.0:
                cost_db.append((cost, subject, nominal))

    # Sort logic: 
    # 1. Cost (lowest first)
    # 2. Physical closeness (how far apart are they in the file?)
    cost_db.sort(key=lambda x: (x[0], abs(x[1].line_n - x[2].line_n))) 
    return cost_db
