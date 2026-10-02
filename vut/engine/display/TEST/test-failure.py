#! /usr/bin/env python3
#
# @hwut {
#     title      = "The failure table: one entry per reason a case fails"
#     choices    = ["brief", "explain", "total"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE FAILURE TABLE (display D-34), 'engine/display/failure.py'.

    brief      the one screen: every failure, its category and the word
               before '[FAIL]', as '_brief_failure_db' states them --
               and the word 'reason_word()' prints for each token is
               that word.
    explain    the paragraphs 'hwut.help' prints for a failure: what it
               means, how it is healed (one fixed opening), and how
               sanitize heals it where it does.
    total      the table covers every report token the operations can
               write ('E_TestRunResult' but 'ok'); every member of
               'E_Failure' has its brief line and its Failure; the
               table is frozen.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.display.failure    import (E_Failure, E_FailureCategory,
                                           HEAL_OPENER_STR,
                                           failure_db, failure_of)
from vut.engine.display.failure    import _brief_failure_db
from vut.engine.display.word       import reason_word, phrase
from vut.engine.operations.result  import E_TestRunResult


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def test_brief():
    for failure_id in sorted(E_Failure, key=lambda f: f.value):
        category, word = _brief_failure_db[failure_id]
        print("%-30s %-12s %s" % (failure_id.value, category.value,
                                  word if word is not None else "-"))
    ok = _check([
        (all(reason_word(f.value) == _brief_failure_db[f][1]
             for f in E_Failure),
         "the word before '[FAIL]' is the brief's, for every failure"),
        (all(phrase(f.value) == failure_db[f].description
             for f in E_Failure),
         "the phrase is the Failure's description, for every failure"),
        (reason_word("a-token-nobody-taught") == "failed",
         "a token the table does not carry still reads 'failed'"),
    ])
    _verdict(ok, "the brief is what the run says.")


def test_explain():
    for token in ("nominal-without-hwut-end", "test-choice-vanished"):
        failure = failure_of(token)
        print("-- %s" % token)
        for paragraph in failure.paragraph_list():
            print("   | %s" % paragraph)
    ok = _check([
        (all(f.paragraph_list()[1].startswith(HEAL_OPENER_STR)
             for f in failure_db.values()),
         "every failure's second paragraph opens '%s'"
         % HEAL_OPENER_STR.strip()),
        (all(len(f.paragraph_list()) == (3 if f.sanitize else 2)
             for f in failure_db.values()),
         "a third paragraph stands exactly where sanitize heals it"),
        (failure_of("ok") is None, "success is no failure"),
        (failure_of("a-token-nobody-taught") is None,
         "an unknown token is no failure of the table"),
    ])
    _verdict(ok, "what it means, how to heal it, what sanitize does.")


def test_total():
    report_set  = {r.value for r in E_TestRunResult} - {"ok"}
    failure_set = {f.value for f in E_Failure}
    missing = sorted(report_set - failure_set)
    print("INSPECT: failures            = %i" % len(E_Failure))
    print("         report tokens absent = %s" % (missing or "none"))
    frozen = False
    try:
        failure_db[E_Failure.UNSTABLE] = None
    except TypeError:
        frozen = True
    ok = _check([
        (not missing, "every report token is a failure of the table"),
        (set(_brief_failure_db) == set(E_Failure),
         "every failure has its brief line"),
        (set(failure_db) == set(E_Failure),
         "every failure has its Failure"),
        (all(failure_db[f].failure_id is f for f in E_Failure),
         "each Failure knows its own id"),
        (all((failure_db[f].comment_before_FAIL_str is None)
             == (failure_db[f].category is E_FailureCategory.DEVIATION)
             for f in E_Failure),
         "exactly the deviations carry no word"),
        (frozen, "the table is frozen"),
    ])
    _verdict(ok, "one entry per reason, and none missing.")


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "The failure table: one entry per reason a case fails;", {
        "brief":   test_brief,
        "explain": test_explain,
        "total":   test_total,
    }).run()
