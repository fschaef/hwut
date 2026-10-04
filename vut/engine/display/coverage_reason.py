"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE VOCABULARY OF THE COVERAGE RUN (D-40) -- '[REC]' where a
         run left a coverage record, '[NO REC]' with its reason where
         it left none.

ONE TABLE of the reasons a coverage run answers with ('E_CoverageResult'
tokens, coverage D-19, D-38): the word before '[NO REC]', the phrase in
HINTS, and the category the case is listed under. Nowhere else is any
of the three spelt.

A TOKEN THIS TABLE DOES NOT CARRY IS THE TEST RUN'S -- a build that
failed, a GOOD file that is missing -- and is said in the test run's
own words, from 'failure.py'.
______________________________________________________________________________
"""
from dataclasses import dataclass
from enum        import Enum

from .failure    import (CATEGORY_HEADING_DB, HEAL_OPENER_STR,
                         HELP_HINT_STR, E_FailureCategory)
from .failure    import category_of as run_category_of
from .vocabulary import CFlowVocabulary
from .word       import phrase as run_phrase
from .word       import reason_word as run_reason_word


class E_NoRecordCategory(Enum):
    """WHY NO RECORD STANDS, by where the cause lies:

        SETUP   the case cannot be measured as the tree stands
        RUN     the application ran and did not testify
        TOOL    the tool ran and left nothing usable
    """
    SETUP = "setup"
    RUN   = "run"
    TOOL  = "tool"


HEADING_DB = {
    E_NoRecordCategory.SETUP: "SETUP -- no coverage run possible",
    E_NoRecordCategory.RUN:   "RUN -- application did not testify",
    E_NoRecordCategory.TOOL:  "TOOL -- no usable data from tool",
}


@dataclass(frozen=True)
class NoRecord:
    """ONE REASON a coverage run left no record.

    'word'      what stands before '[NO REC]' in the flow
    'phrase'    the line in HINTS, telegraphic
    'category'  the HINTS group
    'what'      what it means, for 'hwut.help'
    'heal'      how it is resolved; 'hwut.help' opens it 'In order to
                heal, '
    """
    word:     str
    phrase:   str
    category: E_NoRecordCategory
    what:     str
    heal:     str

    def paragraph_list(self):
        """RETURN: list of str, the paragraphs 'hwut.help' prints for
        this reason: what it means, then how it is healed."""
        return [self.what,
                HEAL_OPENER_STR + self.heal[0].lower() + self.heal[1:]]


no_record_db = {
    "no-coverage-target": NoRecord(
        "no target",
        "no 'coverage_target' in 'language-setup'",
        E_NoRecordCategory.SETUP,
        "The test is compiled, and its language entry in "
        "'hwut-root.conf' names no 'coverage_target'. A coverage run "
        "builds that target in place of the executable; without the "
        "name there is nothing instrumented to run, so the case was "
        "not run.",
        "State 'coverage_target' for the language in 'language-setup' "
        "of 'hwut-root.conf' -- '%' is the source file's stem -- and "
        "let the build rules instrument that target."),
    "not-registered": NoRecord(
        "not in book",
        "no run id in GOOD/book.csv; accept first",
        E_NoRecordCategory.SETUP,
        "'GOOD/book.csv' holds no run id for the case. A coverage "
        "record is attributed by that id, and a coverage run reads "
        "the book without writing it, so the case was not run.",
        "Run the case once with 'hwut.run', which enters it into "
        "'GOOD/book.csv', or accept it with 'hwut.accept'."),
    "run-incomplete": NoRecord(
        "incomplete",
        "run did not end with <hwut-end>; nothing read",
        E_NoRecordCategory.RUN,
        "The application did not testify under the coverage tool: it "
        "was killed, could not be started, or its output did not end "
        "in '<hwut-end>'. Lines touched by such a run are a claim of "
        "nothing, so the tool's data was not read. Where 'hwut.run' "
        "passes the same case, the tool's call is at fault, not the "
        "application.",
        "Run the case with 'hwut.run.play' to see what it prints "
        "without the tool, then make the tool's call by hand in the "
        "test directory and read what it says."),
    "no-data-provided": NoRecord(
        "no data",
        "tool left nothing in OUT/COVERAGE",
        E_NoRecordCategory.TOOL,
        "The run ended well and the coverage tool left no artefact "
        "under 'OUT/COVERAGE'. Either the application is not "
        "instrumented, or the tool wrote its data elsewhere.",
        "Check that the build instruments the coverage target, and "
        "that the tool writes into 'OUT/COVERAGE' of the test "
        "directory."),
    "report-failed": NoRecord(
        "report failed",
        "tool's report call failed",
        E_NoRecordCategory.TOOL,
        "The run ended well, and the tool's second call -- the one "
        "that turns its raw data into a readable artefact -- did not.",
        "Make that call by hand in the test directory; "
        "'hwut.cov.formats' names the tool."),
}


def reason_word(token):
    """
    RETURN: str,  the word before '[NO REC]' for 'token': this table's,
                  else the test run's word for it.
            None, where no word stands.
    """
    entry = no_record_db.get(token)
    return entry.word if entry is not None else run_reason_word(token)


def phrase(token):
    """RETURN: str, the HINTS phrase of 'token': this table's, else the
    test run's."""
    entry = no_record_db.get(token)
    return entry.phrase if entry is not None else run_phrase(token)


def category_of(token):
    """RETURN: the HINTS category of 'token': an E_NoRecordCategory
    where this table carries it, the test run's E_FailureCategory
    else."""
    entry = no_record_db.get(token)
    return entry.category if entry is not None else run_category_of(token)


COVERAGE_VOCABULARY = CFlowVocabulary(
    tag_good       = "[REC]",
    tag_bad        = "[NO REC]",
    count_good     = "rec",
    count_bad      = "no rec",
    reason_word    = reason_word,
    phrase         = phrase,
    category_of    = category_of,
    category_tuple = tuple(E_NoRecordCategory) + tuple(E_FailureCategory),
    heading_db     = {**HEADING_DB, **CATEGORY_HEADING_DB},
    quiet_category = None,
    frame_category = E_FailureCategory.ENVIRONMENT,
    subtle_f       = lambda token: token in no_record_db,
    help_hint      = HELP_HINT_STR,
    directory_tag_tuple = ("[COMPLETE]", "[PARTIAL]", "[OMITTED]"))
