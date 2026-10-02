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
    explain    an explanation alone, and with an example case named.
    total      the table covers every report token the operations can
               write ('E_TestRunResult' but 'ok'); every member of
               'E_Failure' has its brief line and its Failure; the
               table is frozen.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.display.failure    import (E_Failure, E_FailureCategory,
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
    failure = failure_of("nominal-without-hwut-end")
    print("-- alone")
    print(failure.explanation_f(None))
    print("-- with an example")
    print(failure.explanation_f("engine/compare/TEST test-exact.py basic"))
    ok = _check([
        (failure_of("ok") is None, "success is no failure"),
        (failure_of("a-token-nobody-taught") is None,
         "an unknown token is no failure of the table"),
    ])
    _verdict(ok, "an explanation names its example last.")


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
