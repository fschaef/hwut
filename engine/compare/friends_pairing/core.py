"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'Friends pairing' algorithm to associate lines of Potpourri.

________________________________________________________________________________
"""
from   hwut.engine.compare.friends_pairing.match_db import LineElementDb
from   hwut.engine.quex.typed                       import typed 

from   collections import defaultdict

@typed(subject_line_list=tuple, nominal_line_list=tuple)  
def do(subject_line_list, nominal_line_list, analogy_db, abort_f=False):
    """RETURNS: [0] verdict
                [1] map: 'ia' --> 'ib'
                [2] analogy_db 

    Where 'ia' is the index of a line in 'subject_lines' that is equivalent
    and, thus, associated with 'ib' which is a line from 'nominal_lines'.
    """
    pre_verdict = True
    L           = max(len(subject_line_list), len(nominal_line_list))

    # -- Find for each subject line the matching candidates of nominal lines.
    #
    match_db = _get_match_db(subject_line_list, nominal_line_list, abort_f)

    if match_db is None or len(match_db) != L:  
        if abort_f: return False, None, None  # Not every subject has a counterpart
        else:       pre_verdict = False

    elif match_db.count_nominals() != L:
        if abort_f: return False, None, None  # Not every nominal has a counterpart
        else:       pre_verdict = False

    # -- Extract those matches for which there is no alternative.
    # -- Extract those subject and nominal lines, that cannot match at all.
    couples = match_db.extract_ultimates_and_hopeless(analogy_db, abort_f)
    if abort_f and couples is None:
        return False, None, None 

    if not match_db:
        # If no match possiblities are left, the task is either complete or failed.
        return len(couples) == L, couples, analogy_db

    elif len(match_db) + len(couples) != L:
        if abort_f: return False, None, None  # Not every subject has a counterpart
        else:       pre_verdict = False

    elif match_db.count_nominals() + len(couples) != L:
        if abort_f: return False, None, None  # Not every nominal has a counterpart
        else:       pre_verdict = False

    # -- Take out match candidates where analogies interfere with 'analogy_db'
    pre_verdict = pre_verdict and match_db.filter_analogy_interference(analogy_db, abort_f)
    if abort_f and not pre_verdict:
        return False, None, None

    # -- Find solution for possible pairings.
    verdict, couples, analogy_db = match_db.pairing(couples, analogy_db)
    return pre_verdict and verdict, couples, analogy_db


def _get_match_db(subject_line_list, nominal_line_list, abort_f=False):
    """RETURNS: A 'LineElementDb' where

        subject line number --> list of (nominal line number, analogy_db)

                None, if a subject line has no counterpart.

    That is, it lists for each subject line number the possible 'mates' 
    from the nominal line number list together with the required 
    analogies.
    """
    def _match_candidates(subject_le_seq, nominal_hash_db):
        """YIELDS: [0] line number in nominal line list where
                       subject_le_seq is equivalent to nominal line.
                   [1] analogy_db required for the equivalence to hold.
        """
        subject_hash = hash(subject_le_seq.sequence)
        for nominal_le_seq in nominal_hash_db.get(subject_hash, []):
            verdict, analogy_db = subject_le_seq.compare(nominal_le_seq, None)
            if verdict: 
                yield nominal_le_seq.line_n, analogy_db

    def _iterable(subject_line_list, nominal_hash_db, abort_f):
        for subject_le_seq in subject_line_list:
            mate_list = list(_match_candidates(subject_le_seq, nominal_hash_db))
            # 'mate_list' = list of (nominal line number, analogy_db) 
            if not mate_list: 
                if abort_f: 
                    raise ValueError
            else:
                yield subject_le_seq.line_n, mate_list

    # Hash bucket => find comparison candidates quickly.
    nominal_hash_db = defaultdict(list)
    for le_sequence in nominal_line_list:
        nominal_hash_db[hash(le_sequence.sequence)].append(le_sequence)

    try:
        return LineElementDb(_iterable(subject_line_list, nominal_hash_db, abort_f))
    except ValueError:
        return None


