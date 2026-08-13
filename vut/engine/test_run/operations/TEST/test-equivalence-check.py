#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

EQUIVALENCE CHECK: READ -> VERDICT.

    UNIT     'EquivalenceCheck' -- the arrangement that holds each
             subject against its nominal and derives one result.

    CAUSAL CONTRACT
             a matching subject passes; a differing one fails and names
             the mismatch; a nominal that cannot be read is a FAULT, not
             a pass; failed provision leaves the comparison ABSENT.

    CONSISTENCY CONTRACT
             subjects are compared in NAME ORDER, so a fast-fail reports
             the SAME first difference on every run; a subject absent
             from the map is not judged at all.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.test_run.result       import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.procsitter    import ProcsitterConfig # noqa E402
from   vut.engine.test_run.provision.build import (BuildConfig,   # noqa E402
                                                   E_BuildSystem)
from   vut.engine.test_run.configuration   import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   E_SourceKind)
from   vut.engine.test_run.operations.equivalence_check import (            # noqa E402
                                                              EquivalenceCheck,
                                                              EquivalenceCheckConfig)
from   vut.engine.test_run.nominal         import (BytesNominal, # noqa E402
                                                   RecordNominal)
from   vut.engine.test_run.observer        import ObserverGroup  # noqa E402
from   vut.engine.test_run.provision.core  import Run, Replay    # noqa E402
from   vut.engine.orchestrator.bookkeeper.bookkeeper import (    # noqa E402
                                                   Bookkeeper)
from   vut.engine.test_run.store           import Store          # noqa E402


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


def _place(body):
    """RETURN: str, a fresh test directory holding 'demo.py'."""
    directory = tempfile.mkdtemp(prefix="vut_eq_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(body)
    return directory


def _configuration(directory):
    """RETURN: TestConfiguration, an INTERPRETED test in 'directory'."""
    return TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = {None: TestChoiceConfiguration()})


def _run(directory, subject_db, fast_fail=True, observer=None):
    """RETURN: TestResult, of one EquivalenceCheck over a fresh Run."""
    return asyncio.run(EquivalenceCheck(
        EquivalenceCheckConfig(name       = "demo",
                               groundwork = Run(_configuration(directory)),
                               subjects   = subject_db,
                               fast_fail  = fast_fail),
        observer=observer).run())


def test_verdict():
    """A matching subject passes; a differing one fails and the report
    says which kind of failure it was."""
    directory = _place("print('alpha'); print('beta')\n")
    same      = _run(directory, {"stdout": BytesNominal("alpha\nbeta\n")})
    differs   = _run(directory, {"stdout": BytesNominal("alpha\nGAMMA\n")})

    for title, result in (("subject matches", same),
                          ("subject differs", differs)):
        print("INSPECT: %-16s -> verdict = %-5s report = %s"
              % (title, result.verdict, result.report))
        print("                     per subject = %s"
              % result.comparison.subject_verdict_db)
    ok = _check([
        (same.verdict is True and same.report is E_TestRunResult.OK,
         "a matching subject passes and reports OK"),
        (differs.verdict is False,
         "a differing subject fails"),
        (differs.report is E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL,
         "and the report names the MISMATCH, nothing else being wrong"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the verdict follows the comparison, and names itself.")


def test_unreadable_nominal_is_a_fault():
    """A nominal that is NAMED and cannot be read is a FAULT. Treating it
    as 'nothing to compare against, therefore fine' would be a green
    light nobody earned."""
    directory = _place("print('alpha')\n")
    result    = _run(directory,
                     {"stdout": RecordNominal("/nowhere/never-accepted.txt")})

    print("INSPECT: verdict = %s" % result.verdict)
    print("         report  = %s" % result.report)
    ok = _check([
        (result.verdict is False,
         "an unreadable nominal FAILS the test"),
        (result.report is E_TestRunResult.NOMINAL_FILE_NOT_FOUND,
         "and the report names the nominal, not the subject"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a missing nominal is a fault, never a pass.")


def test_unjudged_subject():
    """Absence from the map is how a caller says 'do not hold this one
    against anything'. It is not a failure and not a pass -- it is not
    judged."""
    directory = _place("import sys\n"
                       "print('alpha')\n"
                       "sys.stderr.write('noise nobody promised\\n')\n")
    result = _run(directory, {"stdout": BytesNominal("alpha\n")})

    print("INSPECT: judged   = %s" % sorted(result.comparison.subject_verdict_db))
    print("         verdict  = %s, report = %s" % (result.verdict, result.report))
    ok = _check([
        ("stderr" not in result.comparison.subject_verdict_db,
         "stderr was produced but never judged: it is not in the map"),
        (result.verdict is True,
         "and its content cannot fail the test"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "what is not held against anything is not judged.")


def test_fast_fail_is_deterministic():
    """Subjects are compared in NAME ORDER, so a fast-fail stops at the
    SAME first difference every time. A fast-fail that stopped somewhere
    else each run would report a deterministic fault erratically."""
    directory = _place("import sys\n"
                       "print('WRONG')\n"
                       "sys.stderr.write('ALSO WRONG\\n')\n")
    subject_db = {"stdout": BytesNominal("right\n"),
                  "stderr": BytesNominal("right\n")}
    stopping   = _run(directory, subject_db, fast_fail=True)
    exhaustive = _run(directory, subject_db, fast_fail=False)

    print("INSPECT: fast-fail  judged %s"
          % sorted(stopping.comparison.subject_verdict_db))
    print("         exhaustive judged %s"
          % sorted(exhaustive.comparison.subject_verdict_db))
    repeat_list = [sorted(_run(directory, subject_db).comparison
                          .subject_verdict_db) for _ in range(3)]
    print("         three more fast-fail runs judged %s"
          % (repeat_list[0] if len(set(map(tuple, repeat_list))) == 1
             else repeat_list))
    ok = _check([
        (sorted(stopping.comparison.subject_verdict_db) == ["stderr"],
         "fast-fail stops at the FIRST subject by name"),
        (len(set(map(tuple, repeat_list))) == 1,
         "and stops at the same one on every run"),
        (sorted(exhaustive.comparison.subject_verdict_db)
             == ["stderr", "stdout"],
         "without fast-fail every subject is judged"),
        (stopping.verdict is False and exhaustive.verdict is False,
         "both fail -- economy does not change the verdict"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a deterministic fault is reported deterministically.")


def test_failed_provision_leaves_no_comparison():
    """Provision that failed ENDS it: the comparison is ABSENT, not a
    half-filled type, and the report names the build."""
    directory = tempfile.mkdtemp(prefix="vut_eq_")
    os.makedirs(os.path.join(directory, "BUILD", "broke"))
    with open(os.path.join(directory, "BUILD", "broke", "Makefile"), "w") as fh:
        fh.write("app:\n\tfalse\n")
    configuration = TestConfiguration(
        source_file    = "broke.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        build          = BuildConfig(E_BuildSystem.MAKE, ["app"]),
        choice_db      = {None: TestChoiceConfiguration()})
    result = asyncio.run(EquivalenceCheck(EquivalenceCheckConfig(
        name       = "broke",
        groundwork = Run(configuration),
        subjects   = {"stdout": BytesNominal("anything\n")})).run())

    print("INSPECT: verdict    = %s" % result.verdict)
    print("         report     = %s" % result.report)
    print("         comparison = %s" % result.comparison)
    ok = _check([
        (result.verdict is False,
         "the test FAILED"),
        (result.report is E_TestRunResult.BUILD_FAILED,
         "and the report names the build"),
        (result.comparison is None,
         "no comparison happened -- an ABSENCE"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a failed build is a failed test, with no comparison.")


def test_blind_to_provenance():
    """The same check over Run and over Replay yields the same verdict:
    the operation never learns which provision it got."""
    directory = _place("print('alpha'); print('beta')\n")
    store     = Store(Bookkeeper(directory))
    executed  = _run(directory, {"stdout": BytesNominal("alpha\nbeta\n")})
    store.write_candidate("demo", None, "stdout", "alpha\nbeta\n")
    store.write_candidate("demo", None, "stderr", "")

    replayed = asyncio.run(EquivalenceCheck(EquivalenceCheckConfig(
        name       = "demo",
        groundwork = Replay(store, "demo"),
        subjects   = {"stdout": BytesNominal("alpha\nbeta\n")})).run())

    print("INSPECT: over Run    -> verdict %s, report %s, records %i"
          % (executed.verdict, executed.report,
             len(executed.provision.records)))
    print("         over Replay -> verdict %s, report %s, records %i"
          % (replayed.verdict, replayed.report,
             len(replayed.provision.records)))
    ok = _check([
        (executed.verdict == replayed.verdict is True,
         "the verdict is the same over either provision"),
        (executed.report is replayed.report,
         "and so is the report"),
        (len(executed.provision.records) == 1
             and len(replayed.provision.records) == 0,
         "they differ only in the EVIDENCE: one ran a process, one did not"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the check never learns where its subjects came from.")


def test_observer_sees_the_arc():
    """The observer watches the arc unfold: the start, each subject's
    verdict as it lands, and the derived result."""
    directory = _place("print('alpha')\n")
    line_list = []

    class Watcher:
        def started(self, name, kind):  line_list.append("start %s [%s]"
                                                         % (name, kind))
        def verdict(self, name, ok):    line_list.append("  %s %s"
                                                         % (name, ok))
        def finished(self, result):     line_list.append("end %s"
                                                         % result.report)

    _run(directory, {"stdout": BytesNominal("alpha\n")},
         observer=ObserverGroup(Watcher()))
    print("INSPECT: the observer saw")
    for line in line_list: print("           %s" % line)
    ok = _check([
        (line_list[0] == "start demo [Run]",
         "the start names the operation and its groundwork"),
        (line_list[1] == "  stdout True",
         "each subject's verdict arrives as it lands"),
        (line_list[-1] == "end ok",
         "and the derived result closes the arc"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the arc is watchable without changing it.")


def test_named_but_not_produced():
    """A subject NAMED in the map that the run never produced is a
    FAULT. It is the opposite of an unnamed subject: the caller said to
    hold this one against something, and there is nothing to hold."""
    directory = _place("print('only stdout here')\n")
    result = _run(directory,
                  {"stdout":            BytesNominal("only stdout here\n"),
                   "OUT/never-written": BytesNominal("expected\n")},
                  fast_fail=False)

    print("INSPECT: judged  = %s"
          % sorted(result.comparison.subject_verdict_db))
    print("         verdict = %s, report = %s"
          % (result.verdict, result.report))
    ok = _check([
        (result.comparison.subject_verdict_db["OUT/never-written"] is False,
         "the named-but-absent subject FAILS"),
        (result.report is E_TestRunResult.OUTPUT_FILE_NOT_FOUND,
         "and the report names the missing output, not a mismatch"),
        (result.comparison.subject_verdict_db["stdout"] is True,
         "while the subject that WAS produced is judged normally"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "named and absent is a fault; unnamed is not judged.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "EquivalenceCheck: read -> verdict",
        choice_map = {
            "verdict":           test_verdict,
            "nominal_missing":   test_unreadable_nominal_is_a_fault,
            "unjudged":          test_unjudged_subject,
            "fast_fail":         test_fast_fail_is_deterministic,
            "provision_failed":  test_failed_provision_leaves_no_comparison,
            "blind":             test_blind_to_provenance,
            "observer":          test_observer_sees_the_arc,
            "named_absent":      test_named_but_not_produced,
        },
        happy      = "SUCCESS.*",
    ).run()
