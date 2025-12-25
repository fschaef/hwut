"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Pairing lines according to similarity (not only equivalent lines).

Where 'exact.py' only tried to find exactly equivalent lines, this module
tries to associate similar lines. The goal, here, is to provide a line-up
that can be displayed to expose the 'diff function' via a user interface.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.line_pair        import LinePair
import vut.engine.compare.edit_operations.line    as     edit_operations_line
import vut.engine.compare.friends_pairing.compare as     pair_compare
from   vut.engine.compare.engine.analogy_db       import AnalogyDb

from   typeguard import typechecked


def do(subject_line_list, nominal_line_list, analogy_db, max_comparison_count, abort_f=False):
    """RETURNS: sorted list of LinePair objects.
        
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
    verdict, couples, analogy_db = pair_compare.do(subject_line_list,
                                                   nominal_line_list,
                                                   analogy_db,
                                                   abort_early_f=abort_f)

    subject_db = dict((x.line_n, x) for x in subject_line_list)  # helper dictionaries:
    nominal_db = dict((x.line_n, x) for x in nominal_line_list)  # line_n -> 'Line' object

    result = []
    for si, ni in sorted(couples.items()):
        subject_seq, nominal_seq = subject_db[si], nominal_db[ni]
        cost, edit_list, analogy_db = subject_seq.edit_operations(nominal_seq, analogy_db)
        result.append(LinePair(subject_seq, nominal_seq, edit_list, cost = cost))

    if not verdict:
        # Associate the remaining subject and nominal lines according to similarity,
        # until either no subject or no nominal remains as mating candidate.
        line_pair_list,     \
        subjects_remaining, \
        nominals_remaining  = _couple_uncoupled(couples, subject_db, nominal_db,
                                                analogy_db, max_comparison_count)

        result.extend(line_pair_list)
        # Associate with 'None' what has no counterpart.
        result.extend(LinePair(s, None, cost = 1.0) for s in sorted(subjects_remaining, key=lambda x: x.line_n))
        result.extend(LinePair(None, n, cost = 1.0) for n in sorted(nominals_remaining, key=lambda x: x.line_n))

    return result, analogy_db

def _couple_uncoupled(couples, subject_db, nominal_db, analogy_db, max_comparison_count):
    """RETURNS: [0] list of 'LinePair' objects.
                [1] line numbers of unpaired subject lines
                [2] line numbers of unpaired nominal lines

    subject_db:    line number -> Line object 
    nominal_db:    line number -> Line object 

    DOES NOT AFFECT: 'couples'
                     'analogy_db'

    Pairs lines from subject and nominal which are not mentioned in 'couples',
    For this, a each subject line is paired with the nominal line of minimum
    'cost', where cost is a measure of difference between the two.

    The couples produced by this functions are 'not ideal couples', i.e. lines
    are associated which are similar but not equivalent. Thus, they do not
    impose any analogy constraints.
    """
    analogy_db          = None if not analogy_db else analogy_db.clone() # isolate

    line_pair_list,     \
    subjects_remaining, \
    nominals_remaining  = _couple_remainders(couples, subject_db, nominal_db, analogy_db)

    # One remainder must be empty!
    assert (not subjects_remaining) or (not nominals_remaining)

    return line_pair_list, subjects_remaining, nominals_remaining

@typechecked
def _couple_remainders(couples, subject_db, nominal_db, analogy_db: AnalogyDb | None):
    """RETURNS: list of LinePair objects.

    Find couples in the set of remainders according to a least cost
    function. The cost is the amount of difference between the line
    elements.
    """
    subject_done = set(couples.keys())
    nominal_done = set(couples.values())
    cost_db      = _get_cost_db(subject_db, nominal_db, subject_done, nominal_done)

    result       = []
    for cost, subject, nominal in cost_db:
        if subject.line_n in subject_done or nominal.line_n in nominal_done:
            continue

        cost, edit_list, analogy_db = edit_operations_line.do(subject.sequence, nominal.sequence, analogy_db)

        result.append(LinePair(subject, nominal, edit_list, cost = cost))
        subject_done.add(subject.line_n)
        nominal_done.add(nominal.line_n)

    subjects_remaining = [x for line_n, x in subject_db.items() if line_n not in subject_done]
    nominals_remaining = [x for line_n, x in nominal_db.items() if line_n not in nominal_done]

    # One of them must be empty; otherwise we would not have paired at max.
    assert not subjects_remaining or not nominals_remaining

    return result, sorted(subjects_remaining), sorted(nominals_remaining)

def _get_cost_db(subject_db, nominal_db, subject_done, nominal_done):
    """RETURNS: list of (cost, subject line, nominal line)

    where the list ist sorted by cost.
    """
    cost_db = [
        (subject.compare_quickly(nominal), subject, nominal)
        for sn, subject in subject_db.items()
        for nn, nominal in nominal_db.items()
        if sn not in subject_done and nn not in nominal_done
    ]
    cost_db.sort(key=lambda x: (x[0], x[1].line_n, x[2].line_n)) 
    return cost_db

