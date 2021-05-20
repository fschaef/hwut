"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Pairing lines according to similarity (not only equivalent lines).

Where 'exact.py' only tried to find exactly equivalent lines, this module
tries to associate similar lines. The goal, here, is to provide a line-up
that can be displayed to expose the 'diff function' via a user interface.
________________________________________________________________________________
"""
from   ut.engine.compare.engine.analogy_db       import AnalogyDb
from   ut.engine.compare.engine.line_association import LineAssociation
import ut.engine.compare.edit_operations.line    as     edit_operations_line
import ut.engine.compare.friends_pairing.exact   as     friends_pairing

import sys


def do(subject_line_list, nominal_line_list, analogy_db, max_comparison_count, abort_f=False):
    """RETURNS: sorted list of LineAssociation objects.
        
    Sort order: sorted by line number of subject. 

    'max_comparison_count' may restrict the number of comparisons. With 
    large number of lines, this may restrict the complexity, therefore,
    feasibility.

    This functions tries to find the best combination of subject and nominal
    lines according to their similarities. Equivalent matches are first found
    using the 'exact.py' module. Then, the remaining lines are matched based on
    some cost function that takes their similiarity into account. The cost
    function measures the amount of diffrerence between two lines.
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
    """RETURNS: [0] list of 'LineAssociation' objects.
                [1] line numbers of unpaired subject lines
                [2] line numbers of unpaired nominal lines

    DOES NOT AFFECT: 'couples'
                     'analogy_db'

    Pairs lines from subject and nominal which are not mentioned in 'couples',
    For this, a each subject line is paired with the nominal line of minimum
    'cost', where cost is a measure of difference between the two.

    The couples produced by this functions are 'not ideal couples', i.e. lines
    are associated which are similar but not equivalent. Thus, they do not
    impose any analogy constraints.
    """
    subjects_taken, nominals_taken = set(couples.keys()), set(couples.values())
    analogy_db                     = analogy_db.clone() # isolate

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
    """RETURNS: [0] 'nominal_db': nominals available for comparison
                    ib -> Line object for line 'ib'
                [1] line number of nominals Line-s on 'call'.

    'max_comparison_count' restricts the number of comparisons for
    each subject line. This is achieved by restricting the number of
    entries in the returned 'nominal_db'. On the other hand, if an
    entry is used from 'nominal_db', another entry from 'nominals on
    call' can take its place-the number of available nominals remains
    smaller or equal to 'max_comparison_count'.

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
    """RETURN: list of (ia, subject Line object for 'ia')

    for all subject lines that are not already coupled in 'couples'.
    """
    return [
        line
        for ia, line in subject_db.items()
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
        analogy_db = edit_operations_line.do(subject_seq.sequence,
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

