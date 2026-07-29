#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE PRODUCTS, THE DERIVED RESULT, AND THE PROGRESS SEAM.

    UNIT     'Provision' / 'Comparison' -- what each sub-process returns;
             'TestResult' -- what is derived from them; the observer seam.

    CAUSAL CONTRACT
             a failed build is a FAILED TEST with no comparison at all;
             the report is the FIRST reason by precedence; an observer
             never reaches the verdict.

    CONSISTENCY CONTRACT
             every failure token of the vocabulary has a rank, so a new
             token must be PLACED rather than silently ranked last; an
             empty comparison is not a pass.
______________________________________________________________________________
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.auxiliary.test_run_result import E_TestRunResult      # noqa E402
import vut.engine.test_run.report    as     report_module        # noqa E402
from   vut.engine.test_run.report    import (Provision,          # noqa E402
                                             Comparison,
                                             TestResult,
                                             first_by_precedence)
from   vut.engine.test_run.observer  import (ConsoleObserver,    # noqa E402
                                             NullObserver,
                                             ObserverGroup,
                                             notify)


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


def test_failed_build():
    """A failed build is a FAILED TEST, not 'the test could not run'.
    Failing to build is a shortcoming of the code under test."""
    result = TestResult("parse", Provision(report=E_TestRunResult.BUILD_FAILED))
    print("INSPECT: verdict    = %s" % result.verdict)
    print("         report     = %s" % result.report)
    print("         comparison = %s" % result.comparison)
    print("         footprint  = %s" % result.footprint_facts())
    ok = _check([
        (result.verdict is False,
         "the test FAILED -- it is not excused"),
        (result.report is E_TestRunResult.BUILD_FAILED,
         "and the report names the build"),
        (result.comparison is None,
         "no comparison happened: an ABSENCE, not a half-filled type"),
    ])
    _verdict(ok, "a failed build is a failed test, with its reason.")


def test_precedence():
    """Where several reasons could speak, the FIRST by precedence does:
    source and build outrank the run, the run outranks the subjects."""
    case_list = [
        ("build beats a missing output file",
         [E_TestRunResult.OUTPUT_FILE_NOT_FOUND, E_TestRunResult.BUILD_FAILED],
         E_TestRunResult.BUILD_FAILED),
        ("the run beats the canonicaliser",
         [E_TestRunResult.PYPE_FAILED, E_TestRunResult.TEST_APP_STALLED],
         E_TestRunResult.TEST_APP_STALLED),
        ("a mismatch is the quietest failure",
         [E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL,
          E_TestRunResult.NOMINAL_FILE_NOT_FOUND],
         E_TestRunResult.NOMINAL_FILE_NOT_FOUND),
        ("no failure at all",
         [E_TestRunResult.OK, E_TestRunResult.OK],
         E_TestRunResult.OK),
    ]
    outcome_list = []
    for title, reason_list, expected in case_list:
        got = first_by_precedence(reason_list)
        outcome_list.append((title, got, got is expected))
        print("INSPECT: %-34s -> %s" % (title, got))

    unplaced = [e.name for e in E_TestRunResult
                if e is not E_TestRunResult.OK and e not in report_module._RANK]
    print("         unranked failure tokens = %s" % (unplaced or "none"))
    ok = _check([
        (all(holds for _, _, holds in outcome_list),
         "every case picks the reason that outranks the others"),
        (not unplaced,
         "every failure token has a rank -- a new one must be PLACED"),
    ])
    _verdict(ok, "one reason speaks, and it is the loudest one.")


def test_empty_comparison():
    """An empty comparison is NOT a pass. Nothing was held against
    anything, and a green light nobody earned is the failure mode that
    hides itself."""
    nothing = TestResult("parse", Provision(), Comparison({}))
    partial = TestResult("parse", Provision(),
                         Comparison({"stdout": True, "stderr": False}))
    passing = TestResult("parse", Provision(),
                         Comparison({"stdout": True, "stderr": True}))
    for title, result in (("no subject compared", nothing),
                          ("one of two differs", partial),
                          ("both match", passing)):
        print("INSPECT: %-20s -> verdict = %-5s report = %s"
              % (title, result.verdict, result.report))
    ok = _check([
        (nothing.verdict is False,
         "comparing nothing is not success"),
        (partial.verdict is False,
         "one differing subject fails the test"),
        (passing.verdict is True,
         "all matching passes"),
        (passing.report is E_TestRunResult.OK,
         "and reports OK"),
    ])
    _verdict(ok, "a verdict must be earned by a comparison that happened.")


def test_products_unmerged():
    """Each sub-process returns its OWN product. A field's origin is
    readable from its type, not by convention."""
    provision = Provision(records=("record-a", "record-b"))
    result    = TestResult("parse", provision,
                           Comparison({"stdout": True}))
    stored    = TestResult("parse", Provision())     # provision by storage
    print("INSPECT: provision.records = %s" % list(result.provision.records))
    print("         stored.records    = %s (nothing ran)"
          % list(stored.provision.records))
    print("         comparison holds  = %s"
          % sorted(result.comparison.subject_verdict_db))
    ok = _check([
        (result.provision.records == ("record-a", "record-b"),
         "attribution records belong to PROVISION"),
        (not hasattr(result.comparison, "records"),
         "and not to the comparison"),
        (stored.provision.records == (),
         "provision by stored data carries no records: nothing was contained"),
        (result.provision.delivered is True,
         "provision says whether it delivered"),
    ])
    _verdict(ok, "two products, two types, no merging.")


def test_observer_cannot_reach_the_verdict():
    """An observer WATCHES. A broken one must not turn a passing test
    into a failing one, and a missing method is not a fault."""
    line_list = []

    class Broken:
        def started(self, *_):  raise RuntimeError("boom")
        def verdict(self, *_):  raise RuntimeError("boom")

    group = ObserverGroup(Broken(), ConsoleObserver(write=line_list.append),
                          NullObserver())
    group.started("parse", "Run")
    group.verdict("stdout", True)
    group.verdict("stderr", False)
    notify(NullObserver(), "a_method_no_observer_has", 1, 2)
    notify(None, "started", "parse", "Run")

    result = TestResult("parse", Provision(), Comparison({"stdout": True}))
    group.finished(result)

    print("INSPECT: the console observer still received:")
    for line in line_list: print("           %s" % line)
    ok = _check([
        (len(line_list) == 4,
         "every notification reached the healthy observer"),
        (result.verdict is True,
         "the verdict is untouched by a raising observer"),
    ])
    _verdict(ok, "observers add, and none of them reaches the verdict.")


def test_console_observer_writes():
    """ConsoleObserver's real writer, and the 'built' notification a
    build sends. Both exist to be seen, so both are exercised as they
    would be in use."""
    import io
    import contextlib
    from vut.engine.test_run.observer import ConsoleObserver

    captured = io.StringIO()
    observer = ConsoleObserver()
    with contextlib.redirect_stdout(captured):
        observer.started("parse", "Run")
        observer.built(E_TestRunResult.OK)
        observer.verdict("stdout", True)
        observer.finished(TestResult("parse", Provision(),
                                     Comparison({"stdout": True})))
    line_list = captured.getvalue().rstrip("\n").split("\n")

    print("INSPECT: the console observer wrote")
    for line in line_list: print("           %s" % line)
    ok = _check([
        (len(line_list) == 4,
         "one line per notification, including 'built'"),
        (line_list[0].startswith("...") and line_list[-1].startswith("==="),
         "the arc is bracketed, so a scrolling log stays readable"),
        ("build" in line_list[1],
         "a build's outcome is announced as it happens"),
    ])
    _verdict(ok, "progress is written where a person can see it.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Products, the derived result, and the progress seam",
        choice_map = {
            "failed_build":     test_failed_build,
            "precedence":       test_precedence,
            "empty_comparison": test_empty_comparison,
            "products":         test_products_unmerged,
            "observer":         test_observer_cannot_reach_the_verdict,
            "console":          test_console_observer_writes,
        },
        happy      = "SUCCESS.*",
    ).run()
