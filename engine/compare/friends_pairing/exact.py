"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
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
from   ut.engine.compare.friends_pairing.match_db import MatchDb
from   ut.engine.quex.typed                       import typed

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

    # -- find for each subject line the matching candidates of nominal lines.
    #
    match_db = MatchDb(subject_line_list, nominal_line_list, abort_f)

    if not match_db.complete_pairing_possible():
        if abort_f: return False, None, None  
        else:       pre_verdict = False

    # -- extract matches for which there is no alternative.
    # -- extract subject and nominal lines, that cannot match at all.
    couples = match_db.extract_ultimates_and_hopeless(analogy_db, abort_f)

    if len(match_db) == 0:
        return len(couples) == match_db.max_size, couples, analogy_db

    elif not match_db.complete_pairing_possible(len(couples)):
        if abort_f: return False, None, None  
        else:       pre_verdict = False

    # -- Find solution for possible pairings.
    verdict, couples, analogy_db = match_db.pairing(couples, analogy_db)
    return pre_verdict and verdict, couples, analogy_db


