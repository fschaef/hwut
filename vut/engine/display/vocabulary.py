"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE VOCABULARY OF A FLOW (D-40) -- what ONE renderer says
         where it renders two kinds of run.

'plain.CPlainFlow' draws the flow, the DIRECTORIES roll-call, HINTS and
the RESULTS bar. WHAT STANDS IN THE BADGE, which word counts the good
and the bad, and what a reason token is called, is not the renderer's:
it is handed in, as one 'CFlowVocabulary'.

    RUN_VOCABULARY        the test run: '[OK]' / '[FAIL]', 'ok' /
                          'fail', every reason from 'failure.py'
    COVERAGE_VOCABULARY   the coverage run: '[REC]' / '[NO REC]', in
                          'coverage_reason.py'

A WIRE VERDICT STAYS 'ok': the vocabulary decides what is PRINTED, not
what the event stream carries.
______________________________________________________________________________
"""
from dataclasses import dataclass
from typing      import Callable, Mapping, Optional, Sequence

from .failure import (CATEGORY_HEADING_DB, E_FailureCategory,
                      HELP_HINT_STR, category_of, subtle_f)
from .word    import phrase, reason_word


@dataclass(frozen=True)
class CFlowVocabulary:
    """WHAT A FLOW SAYS, where the renderer is one and the runs are
    two.

    'tag_good', 'tag_bad'      the badges at the end of a flow line
    'count_good', 'count_bad'  the words counting them, in DIRECTORIES,
                               RESULTS and the bars
    'reason_word(token)'       the word before the bad badge; None
                               where none stands
    'phrase(token)'            the token in telegraphic English, for
                               HINTS
    'category_of(token)'       the HINTS group of a token
    'category_tuple'           every category, in the order HINTS
                               prints them
    'heading_db'               category -> its HINTS heading
    'quiet_category'           the category HINTS does not list (the
                               test run's DEVIATION); None where every
                               bad case is listed
    'frame_category'           the category of a failed frame script
    'subtle_f(token)'          whether the token earns the closing hint
    'help_hint'                the closing hint; None where the run has
                               none
    """
    tag_good:       str
    tag_bad:        str
    count_good:     str
    count_bad:      str
    reason_word:    Callable
    phrase:         Callable
    category_of:    Callable
    category_tuple: Sequence
    heading_db:     Mapping
    quiet_category: object
    frame_category: object
    subtle_f:       Callable
    help_hint:      Optional[str]


RUN_VOCABULARY = CFlowVocabulary(
    tag_good       = "[OK]",
    tag_bad        = "[FAIL]",
    count_good     = "ok",
    count_bad      = "fail",
    reason_word    = reason_word,
    phrase         = phrase,
    category_of    = category_of,
    category_tuple = tuple(E_FailureCategory),
    heading_db     = CATEGORY_HEADING_DB,
    quiet_category = E_FailureCategory.DEVIATION,
    frame_category = E_FailureCategory.ENVIRONMENT,
    subtle_f       = subtle_f,
    help_hint      = HELP_HINT_STR)
