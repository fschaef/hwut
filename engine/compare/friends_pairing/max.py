import hwut.engine.compare.friends_pairing.core    as     friends_pairing
from   hwut.engine.compare.engine.analogy_db       import AnalogyDb
from   hwut.engine.compare.engine.line_association import LineAssociation
import hwut.engine.compare.edit_operations.line    as     edit_distance_line

import sys


def do(subject_line_list, nominal_line_list, analogy_db, max_comparison_count, abort_f=False):
    """RETURNS: sorted list of LineAssociation (sorted by line number of subject, then nominal)

    This functions tries to find the best combination of subject and nominal
    lines. Lines which are equivalent are already mentioned in 'couples'. The
    remaining lines are matched based on some cost function. The cost function
    measures the amount of diffrerence between two lines.
    """
    verdict, couples, analogy_db = friends_pairing.do(subject_line_list, 
                                                      nominal_line_list, 
                                                      analogy_db, 
                                                      abort_f=abort_f)

    subject_db = dict((x.line_n, x) for x in subject_line_list)  # helper dictionaries:
    nominal_db = dict((x.line_n, x) for x in nominal_line_list)  # line_n -> 'Line' object

    result = []
    for ia, ib in sorted(couples.items()):
        subject_seq, nominal_seq = subject_db[ia], nominal_db[ib]
        cost, edit_list, analogy_db = subject_seq.edit_operations(nominal_seq, analogy_db)
        result.append(LineAssociation(subject_seq, nominal_seq, edit_list, analogy_db))

    if verdict == False:
        # Associate the remaining subject and nominal lines according to similarity,
        # until either no subject or no nominal remains as mating candidate.
        forced_matches,     \
        subjects_remaining, \
        nominals_remaining  = _pair_maximum(couples, subject_db, nominal_db, 
                                            analogy_db, max_comparison_count)

        result.extend(forced_matches)
        # Associate with 'None' what has no counterpart.
        result.extend(LineAssociation(subject_db[ia], None) for ia in sorted(subjects_remaining))
        result.extend(LineAssociation(None, nominal_db[ib]) for ib in sorted(nominals_remaining))

    return result, analogy_db

def _pair_maximum(couples, subject_db, nominal_db, analogy_db, max_comparison_count):
    """RETURNS: [0] sorted remaining subject line indices.
                [1] sorted remaining nominal line indices.

    DOES NOT EFFECT: 'couples'

    The dictionary 'couple' maps: 'ia' --> 'ib' of EQUIVALENT lines in
    subject and nominal. The database might, then contain lines which are
    not equivalent. For side-by-side comparison view, remaining mistfits
    must also be paired. For this, a each subject line is paired with the
    nominal line of minimum 'cost', where cost is a measure of difference
    between the two.

    The couples produces by this functions are 'bad couples', i.e. lines
    are associated which are not equivalent. Thus, they do not impose
    any analogy constraints.
    """
    subjects_taken, nominals_taken = set(couples.keys()), set(couples.values())

    nominals_available_db, nominals_on_call = _nominals(nominal_db,
                                                        nominals_taken, 
                                                        max_comparison_count)
    subjects_available                      = _subjects(subject_db, 
                                                        subjects_taken)

    line_associations,  \
    subjects_remaining, \
    nominals_remaining  = _couple_remainders(subjects_available , 
                                             nominal_db,
                                             nominals_available_db, 
                                             nominals_on_call, 
                                             analogy_db)

    # One remainder must be empty!
    assert (not subjects_remaining) or (not nominals_remaining)

    return line_associations, subjects_remaining, nominals_remaining


def _nominals(nominal_db, nominals_coupled, max_comparison_count):
    """RETURNS: [0] nominals available for comparison:
                    ib -> Line of line ib
                [1] nominals on call, when a nominal from [0]
                    is coupled and therefore no longer available.

    The original list of available nominals is the set of nominals not
    yet coupled in 'couples'.
    """
    remaining = sorted(set(nominal_db.keys()).difference(nominals_coupled))
    if max_comparison_count < len(remaining):
        nominals_on_call = remaining[max_comparison_count:]
        del remaining[max_comparison_count:]
    else:
        nominals_on_call = []

    nominal_db = dict(
        (ib, match_seq) 
        for ib, match_seq in nominal_db.items() 
        if ib in remaining
    )
    return nominal_db, nominals_on_call

def _subjects(subject_db, subjects_coupled):
    """RETURN: list of (ia, match_seq)

    for all subject lines that are not already coupled in 'couples'.
    """
    return [
        match_seq
        for ia, match_seq in subject_db.items()
        if ia not in subjects_coupled
    ]

def _couple_remainders(subjects_available, 
                       nominal_db,
                       nominals_available_db, 
                       nominals_on_call,
                       analogy_db):
    """RETURNS: list of LineAssociation objects.
        
    Find couples in the set of remainders according to a least cost 
    function. The cost is the amount of difference between the line 
    elements.
    """
    if not nominals_available_db: 
        return [], sorted(mseq.line_n for mseq in subjects_available), []

    result = []
    for i, subject_seq in enumerate(sorted(subjects_available)):
        if not nominals_available_db: 
            subjects_remaining = set(mseq.line_n for mseq in subjects_available[i:])
            break
        best = _find_best_match(subject_seq, nominals_available_db, analogy_db)
        result.append(best)

        analogy_db = best.analogy_db

        # 'best.nominal_seq' is no longer available as mate.
        del nominals_available_db[best.nominal_seq.line_n] 

        if nominals_on_call:
            ib = nominals_on_call.pop()
            nominals_available_db[ib] = nominal_db[ib]
    else:
        subjects_remaining = set()

    nominals_remaining = set(nominals_available_db.keys()).union(nominals_on_call)
    return result, sorted(subjects_remaining), sorted(nominals_remaining)

def _find_best_match(subject_seq, nominal_match_db, analogy_db):
    """RETURNS: 'ib' of the line in 'nominal_match_db' that fits best
                 with the given 'subject_match_line'.
    """
    assert nominal_match_db

    # Abort counting as soon as a perfect match has been found (cost = 0).
    best = LineAssociation.empty(subject_seq) # cost = max.
    best_cost = sys.float_info.max
    for ib, nominal_seq in sorted(nominal_match_db.items()):
        cost,      \
        edit_list, \
        analogy_db = edit_distance_line.do(subject_seq.sequence, 
                                           nominal_seq.sequence, 
                                           analogy_db)
        if cost >= best_cost: 
            continue

        best_cost        = cost 
        best.nominal_seq = nominal_seq
        best.edit_list   = edit_list
        best.analogy_db  = analogy_db
        if best_cost == 0:
            # IMPOSSIBLE: Because, if there was a perfect match, then it 
            #             would have been found in 'FriendsPairing.do()'.
            break #       pragma no cover 

    assert not best.is_empty() # since nominal_match_db was not empty
    return best

