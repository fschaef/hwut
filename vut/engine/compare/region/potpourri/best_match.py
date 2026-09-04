"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Pairing lines according to similarity (not only equivalent lines).

Where 'exact.py' (or equivalence_check) only tried to find exactly equivalent lines,
this module tries to associate similar lines. The goal, here, is to provide a
line-up that can be displayed to expose the 'diff function' via a user interface.
________________________________________________________________________________
"""
from typeguard import typechecked

import vut.engine.compare.core.edit_operations.line as     edit_operations_line
from   vut.engine.compare.core.line_pair            import LinePair, display_twin
from   vut.engine.compare.core.edit_operations.edit import Edit, E_EditId
import vut.engine.compare.region.potpourri.pairing                as     pairing
from   vut.engine.compare.contract.analogy_db                       import AnalogyDb
from   vut.engine.compare.contract.frozen_analogy_db                import FrozenAnalogyDb

def do(subject, nominal, analogy_db, max_comparison_count,
       subset_f=False):
    """RETURNS: [0] list of (subject line number, nominal line number)
                [1] required analogy db

    This function (tries to) associates subject lines with nominal lines
    as good as possible. The analogy db reflects an attempt to find
    consistent analogies. Since we do not assume equivalence, the analogy
    db may be inconsistent with some of the entries.
    """
    # non-analogy lines can never match with analogy lines, and vice versa.
    # => treat them separately

    # pair non-analogy lines
    first_result, \
    _             = _core_non_analogy(subject.non_analogy_line_list,
                                      nominal.non_analogy_line_list,
                                      max_comparison_count,
                                      abort_early_f=False,
                                      subset_f=subset_f)

    # pair analogy lines
    second_result, \
    analogy_db     = _core(subject.analogy_line_list,
                           nominal.analogy_line_list,
                           analogy_db,
                           max_comparison_count,
                           abort_early_f=False,
                           analogies_involved_f = True,
                           subset_f=subset_f)

    return first_result + second_result, analogy_db

def _core_non_analogy(subject_line_list, nominal_line_list,
                      max_comparison_count,
                      abort_early_f=False, subset_f=False):

    verdict, couples = pairing._core_non_analogy(subject_line_list,
                                                 nominal_line_list,
                                                 abort_early_f = abort_early_f)

    subject_db = dict((x.line_n, x) for x in subject_line_list)  # helper dictionaries:
    nominal_db = dict((x.line_n, x) for x in nominal_line_list)  # line_n -> 'Line' object

    if subset_f:
        verdict = (len(couples) == len(subject_line_list)
                   and len(subject_line_list) <= len(nominal_line_list))
    else:
        verdict = (len(couples) == len(nominal_line_list) == len(subject_line_list))
    return _get_line_pairs(verdict, couples, subject_db, nominal_db,
                           FrozenAnalogyDb(), max_comparison_count, subset_f)

def _core(subject_line_list,
          nominal_line_list,
          analogy_db, max_comparison_count,
          abort_early_f=False, analogies_involved_f = True, subset_f=False):
    """RETURNS: sorted list of LinePair objects.

    Sort order: sorted by line number of subject.

    'max_comparison_count' may restrict the number of comparisons. With
    large number of lines, this may restrict the complexity, therefore,
    feasibility.

    This functions tries to find the best combination of subject and nominal
    lines according to their similarities. Equivalent matches are first found
    using the 'pairing' module. Then, the remaining lines are matched based on
    some cost function that takes their similiarity into account. The cost
    function measures the amount of diffrerence between two lines.
    """
    # 1. STRICT PHASE: High-performance matching
    verdict, couples, analogy_db = pairing._core(subject_line_list,
                                                 nominal_line_list,
                                                 analogy_db,
                                                 abort_early_f=abort_early_f,
                                                 analogies_involved_f = analogies_involved_f,
                                                 subset_f=subset_f)

    subject_db = dict((x.line_n, x) for x in subject_line_list)  # helper dictionaries:
    nominal_db = dict((x.line_n, x) for x in nominal_line_list)  # line_n -> 'Line' object

    if subset_f:
        verdict = (verdict
                   and len(couples) == len(subject_line_list)
                   and len(subject_line_list) <= len(nominal_line_list))
    return _get_line_pairs(verdict, couples, subject_db, nominal_db,
                           FrozenAnalogyDb(analogy_db), max_comparison_count,
                           subset_f)

def _get_line_pairs(verdict, couples, subject_db, nominal_db, analogy_db,
                    max_comparison_count, subset_f=False):
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
        nominals_remaining  = _couple_remainders(couples, subject_db, nominal_db,
                                                 analogy_db, max_comparison_count)

        result.extend(line_pair_list)
        # Associate with 'None' what has no counterpart.
        # Use sys.maxsize for sorting stability later
        result.extend(LinePair(subject_db[ia], None, cost=1.0) for ia in sorted(subjects_remaining))
        if subset_f:
            # surplus nominal lines are LEGAL in subset mode: neutral.
            result.extend(LinePair(None, display_twin(nominal_db[ib]),
                                   (Edit(E_EditId.GOOD_INSERT),),
                                   seq_edit_id=E_EditId.GOOD_INSERT)
                          for ib in sorted(nominals_remaining))
        else:
            result.extend(LinePair(None, nominal_db[ib], cost=1.0) for ib in sorted(nominals_remaining))

    # Final Sort: Restore document order
    def sort_key(lp): return (lp.subject_line_n, lp.nominal_line_n)

    result.sort(key=sort_key)

    return result, analogy_db.to_AnalogyDb()

@typechecked
def _couple_remainders(couples,
                       subject_db,
                       nominal_db,
                       analogy_db: AnalogyDb | FrozenAnalogyDb | None, max_comparison_count):
    """RETURNS: [0] list of 'LinePair' objects.
                [1] line numbers of unpaired subject lines
                [2] line numbers of unpaired nominal lines

    subject_db:    line number -> Line object
    nominal_db:    line number -> Line object


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

    # cheap sort before windowing
    def key(le_seq):
        return tuple(len(le._string) for le in le_seq)
    subjects_available.sort(key=key)
    nominals_available.sort(key=key)

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
