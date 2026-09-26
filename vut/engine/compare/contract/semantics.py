"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Single source of the comparison semantics shared by the equivalence
         face (the 'Judge') and the association face (the 'Lawyer') of every
         region kind.

THE LAW (invariant):

    is_equivalent(subject, nominal) is True
        <=>  associate(subject, nominal) yields only equivalent pairs.

The Judge is a fast-fail optimization of the Lawyer, never an independent
authority. Both faces must therefore derive their notion of 'equal' from the
definitions in THIS module -- any change here moves Judge and Lawyer together.

CONTENT:

    E_EditId              edit classes (the vocabulary of the Lawyer)
    GOOD_EDIT_ID_SET      the edit classes that PRESERVE equivalence
    element_cost_db       cost of an edit class at LineElement level
    line_cost_db          cost of an edit class at Line level

IMPORTANT -- equivalence is edit-CLASS membership, never a cost-value test:
cost and equivalence deliberately disagree in the margins.  A GOOD_INSERT /
GOOD_DELETE (visible-nothing skip) is equivalence-preserving but carries a
tiny positive cost (1e-10) so that a plain GOOD alignment is preferred when
both exist.  Conversely a separator INSERT/DELETE may cost 0 after separator
normalization while being non-equivalent.  Use 'is_good_edit()' to ask
"does this edit preserve equivalence?"; use the cost tables only to RANK
alternative edit sequences.
________________________________________________________________________________
"""
from enum import IntEnum

from vut.engine.compare.contract.enums import E_Verdict, E_ToleranceId


class E_EditId(IntEnum):
    GOOD            = 0
    GOOD_TOLERATED  = 1
    GOOD_INSERT     = 9
    GOOD_DELETE     = 8
    INSERT          = 3
    DELETE          = 4
    SUBSTITUTE      = 5
    SUBSTITUTE_TYPE = 6
    NONE            = 7


GOOD_EDIT_ID_SET = frozenset((E_EditId.GOOD,
                              E_EditId.GOOD_TOLERATED,
                              E_EditId.GOOD_INSERT,
                              E_EditId.GOOD_DELETE))


def is_good_edit(edit_id):
    """RETURNS: True, if 'edit_id' is an equivalence-preserving edit class,
                      i.e. subject and nominal count as EQUAL at this position.
                False, else.
    """
    return edit_id in GOOD_EDIT_ID_SET


# Cost of edit classes at the level of 'LineElement' sequences (inside one
# line). Used by 'core/edit_operations/line.py'.
element_cost_db = {
    E_EditId.GOOD:             0,       # good
    E_EditId.GOOD_TOLERATED:   0,       # good, tolerated is better than good insert + delete delete
    E_EditId.GOOD_INSERT:      1e-10,   # good insert visible nothing (slightly worse than 'good')
    E_EditId.GOOD_DELETE:      1e-10,   # good delete visible nothing (slightly worse than 'good')
    E_EditId.SUBSTITUTE:       1,       # good, when content is substituted
    E_EditId.INSERT:           1,       # bad, need to insert element
    E_EditId.DELETE:           1,       # bad, need to remove element
    E_EditId.SUBSTITUTE_TYPE:  1        # bad, need to substitute type and content of element
}

# Cost of edit classes at the level of 'Line' sequences (across lines).
# Used by 'core/edit_operations/line_sequence.py'.
line_cost_db = {
    E_EditId.GOOD:       0.0,
    E_EditId.SUBSTITUTE: 1.0,
    E_EditId.INSERT:     0.5,
    E_EditId.DELETE:     0.5
}


# ------------------------------------------------------------------------------
# LINE SIGNIFICANCE -- which lines take part in the equivalence consideration.
# ------------------------------------------------------------------------------

def is_insignificant_line(string, ignored_line_begin_marker,
                                  ignored_line_end_marker):
    """RETURNS: True, if 'string' is a line WITHOUT significance for the
                      equivalence consideration: blank, or carrying the
                      ignored-line markers.
                False, else.

    THE single definition of 'the Judge does not see this line'. Two users:

      -- the equivalence chunk pipe drops such lines up-front, so the fast
         path never compares them;
      -- the Lawyer's reduction ('LinePair.is_equivalent') neutralizes pairs
         made of such lines -- they are display filler, and counting their
         one-sided cells as damage would break THE LAW.
    """
    stripped = string.strip()
    if not stripped:
        return True
    return (   stripped.startswith(ignored_line_begin_marker)
            or stripped.endswith(ignored_line_end_marker))


# ------------------------------------------------------------------------------
# VERDICT REDUCTION -- collapsing 'E_Verdict' to booleans / edit classes.
# ------------------------------------------------------------------------------

def is_equivalent_verdict(verdict_id):
    """RETURNS: True, if 'verdict_id' expresses equivalence, INCLUDING the two
                      VISIBLE_NOTHING variants (a transparent token on either
                      side still counts as equal).
                False, else.
    """
    return verdict_id in (E_Verdict.EQUIVALENT,
                          E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING,
                          E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING)


def is_plainly_equivalent_verdict(verdict_id):
    """RETURNS: True, if 'verdict_id' is EQUIVALENT proper -- the strict form
                      that does NOT accept the VISIBLE_NOTHING collapse.
                False, else.

    Use this where a transparent token cannot stand in for real content:
      -- the Judge's line check operates on VISIBLE_NOTHING-filtered
         sequences ('Line.sequence_v'), where the collapse cases cannot
         arise, so strict and collapsing reduction coincide;
      -- transposition anchors in the edit search, where only genuinely
         equivalent elements may be swapped into place.
    """
    return verdict_id is E_Verdict.EQUIVALENT


def verdict_to_edit_id(verdict_id, subject_le, nominal_le, analogy_db, analogy):
    """RETURNS: E_EditId, the edit class that the comparison verdict of one
                          (subject, nominal) LineElement pair maps to.

    This is THE mapping between the Judge's vocabulary (E_Verdict) and the
    Lawyer's vocabulary (E_EditId). The GOOD family preserves equivalence;
    everything else does not:

        MISFIT                              -> SUBSTITUTE_TYPE
        DIFFERENT                           -> SUBSTITUTE
        EQUIVALENT_SUBJECT_VISIBLE_NOTHING  -> GOOD_DELETE
        EQUIVALENT_NOMINAL_VISIBLE_NOTHING  -> GOOD_INSERT
        EQUIVALENT, analogy inconsistent    -> SUBSTITUTE
        EQUIVALENT, content differs         -> GOOD_TOLERATED
        EQUIVALENT, analogy tolerance       -> GOOD_TOLERATED
        EQUIVALENT, byte-equal              -> GOOD
    """
    match verdict_id:
        case E_Verdict.MISFIT:
            return E_EditId.SUBSTITUTE_TYPE
        case E_Verdict.DIFFERENT:
            return E_EditId.SUBSTITUTE
        case E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING:
            return E_EditId.GOOD_DELETE
        case E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING:
            return E_EditId.GOOD_INSERT
        case E_Verdict.EQUIVALENT:
            if not analogy_db.is_consistent(analogy):
                return E_EditId.SUBSTITUTE
            elif subject_le._string != nominal_le._string:
                return E_EditId.GOOD_TOLERATED
            elif subject_le.tolerance_id == E_ToleranceId.ANALOGY:
                return E_EditId.GOOD_TOLERATED
            else:
                return E_EditId.GOOD
        case _:
            raise AssertionError(verdict_id)


def analogy_commitment(analogy_db):
    """RETURNS: n, the number of NON-TRIVIAL analogies in 'analogy_db' -- the
                   degree to which accepting these analogies CONSTRAINS all
                   later comparisons.
                0, for None, an empty db, or a db of purely trivial (a = a)
                   analogies.

    THE preference order of ambiguous associations: where several pairings
    are equally cheap, the one that commits LESS must win. A trivial analogy
    imposes nothing on the future; a crossed one (A = B, B = A) can poison
    every subsequent chunk. Both the Judge's and the Lawyer's potpourri
    matcher rank candidates through this function -- so their choice among
    equal-cost matchings cannot drift apart.
    """
    if not analogy_db:
        return 0
    return sum(1 for subject_str, nominal_str in analogy_db.items()
               if subject_str != nominal_str)


# ------------------------------------------------------------------------------
# ANALOGY COMMIT -- the choreography by which line-imposed analogies enter the
# evolving global database of the streaming equivalence check.
# ------------------------------------------------------------------------------

def commit_analogies(analogy_db, analogy_list):
    """RETURNS: True, if 'analogy_list' is consistent with 'analogy_db'; the
                      database HAS ABSORBED the new analogies.
                False, if inconsistent; the database is UNCHANGED.

    THE single commit protocol for the Judge's chunk-by-chunk streaming:

        1. an empty or None list commits trivially (True, no change);
        2. the candidate list is validated against the database (including
           the list's own internal consistency, e.g. A->1 and A->2 in the
           same line is a contradiction);
        3. only on full validation does the database mutate -- there is no
           partial absorption.

    NOTE: callers that pre-check with 'Line.is_equivalent()' (which consults
    the database without mutating it) still commit through here; the commit
    re-validates atomically, so a pre-check is an optimization, never a
    substitute.

    KEY FORM: analogy-db keys are the full MARKER-WRAPPED analogy strings
    ('((B))', never bare 'B') -- one vocabulary for every commit path, or
    sequential consistency checking silently fragments (see
    'PatternFinder.extract_analogy_strings').
    """
    return analogy_db.extend_if_consistent(analogy_list)
