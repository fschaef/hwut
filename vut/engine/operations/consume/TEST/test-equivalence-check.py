#! /usr/bin/env python3
#
# @hwut {
#     title      = "EquivalenceCheck: read -> verdict"
#     choices    = ["blind", "fast_fail", "named_absent",
#                   "nominal_missing", "observer", "provision_failed",
#                   "terminated", "unexpected_stderr", "unjudged",
#                   "verdict"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
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

from   vut.engine.operations.result       import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.api    import ProcsitterConfig # noqa E402
from   vut.engine.operations.build_action import (BuildConfig,   # noqa E402
                                                   E_BuildSystem)
from   vut.engine.operations.configuration   import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   E_SourceKind)
from   vut.engine.operations.consume.equivalence_check import (            # noqa E402
                                                              EquivalenceCheck,
                                                              EquivalenceCheckConfig)
from   vut.engine.operations.nominal         import (BytesNominal, # noqa E402
                                                   RecordNominal)
from   vut.engine.operations.observer        import ObserverGroup  # noqa E402
from   vut.engine.operations.run.core  import Run            # noqa E402
from   vut.engine.bookkeeper.api import Store  # noqa E402
from   vut.engine.bookkeeper.api import Bookkeeper      # noqa E402
from   vut.engine.operations.consume.loaded import loaded        # noqa E402
from   vut.engine.bookkeeper.api import (    # noqa E402
                                                   Bookkeeper)
from   vut.engine.bookkeeper.api           import Store          # noqa E402


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
         "and the report names the MISMATCH, nothing else being "
         "wrong -- the SHAPE of it is 'hwut.report''s, afterwards, "
         "since comparison aborts before either text is whole"),
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
    half-filled type, and the report names the launch -- the
    application is provided ABOVE (BUILD nodes), so an absent artifact
    is execution's failure here."""
    directory = tempfile.mkdtemp(prefix="vut_eq_")
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
        (result.report is E_TestRunResult.TEST_APP_LAUNCH_FAILED,
         "and the report names the launch"),
        (result.comparison is None,
         "no comparison happened -- an ABSENCE"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a failed provision is a failed test, "
                 "with no comparison.")


def test_blind_to_provenance():
    """The same check over Run and over 'loaded' yields the same
    verdict: the operation never learns which provision it got."""
    directory = _place("print('alpha'); print('beta')\n")
    store     = Store(Bookkeeper(directory))
    executed  = _run(directory, {"stdout": BytesNominal("alpha\nbeta\n")})
    store.write_candidate("demo", None, "stdout", "alpha\nbeta\n")
    store.write_candidate("demo", None, "stderr", "")

    class _Loaded:
        """The loaded groundwork: 'provide()' answers the store."""
        stage_execute = None
        def __init__(self):  self.last_provided = None
        async def provide(self, stop_event=None):
            self.last_provided = loaded(store, "demo")
            return self.last_provided

    replayed = asyncio.run(EquivalenceCheck(EquivalenceCheckConfig(
        name       = "demo",
        groundwork = _Loaded(),
        subjects   = {"stdout": BytesNominal("alpha\nbeta\n")})).run())

    print("INSPECT: over Run    -> verdict %s, report %s, records %i"
          % (executed.verdict, executed.report,
             len(executed.provision.records)))
    print("         over loaded -> verdict %s, report %s, records %i"
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




def test_terminated():
    """THE TERMINAL TOKEN (R-70): the nominal decides participation.
    A participating subject that ends without '<hwut-end>' draws
    'terminated-without-hwut-end' -- its own name, never a wall of
    line differences; trailing blank lines after the token are
    forgiven; a NON-participating nominal sees a token-bearing subject
    as ordinary content."""
    async def judged(nominal_text, subject_text):
        directory = tempfile.mkdtemp(prefix="vut_eq_")
        try:
            store = Store(Bookkeeper(directory))
            store.write_candidate("demo", None, "stdout", subject_text)
            result = await EquivalenceCheck(EquivalenceCheckConfig(
                name       = "demo",
                groundwork = _Provided(loaded(store, "demo",
                                       subject_name_list=("stdout",))),
                subjects   = {"stdout": BytesNominal(nominal_text)},
            )).run()
            return result
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    participating = "alpha\nbeta\n<hwut-end>\n"

    cut      = asyncio.run(judged(participating, "alpha\nbeta\n"))
    complete = asyncio.run(judged(participating,
                                  "alpha\nbeta\n<hwut-end>\n"))
    padded   = asyncio.run(judged(participating,
                                  "alpha\nbeta\n<hwut-end>\n\n\n"))
    old      = asyncio.run(judged("alpha\nbeta\n",
                                  "alpha\nbeta\n<hwut-end>\n"))

    print("INSPECT: cut      -> verdict %s, report %s"
          % (cut.verdict, cut.report))
    print("         complete -> verdict %s, report %s"
          % (complete.verdict, complete.report))
    print("         padded   -> verdict %s, report %s"
          % (padded.verdict, padded.report))
    print("         old nominal, marked subject -> verdict %s, "
          "report %s" % (old.verdict, old.report))
    ok = _check([
        (cut.report is E_TestRunResult.TERMINATED_WITHOUT_END,
         "the missing token has its OWN name, not a line difference"),
        (cut.verdict is False,
         "and the test FAILED"),
        (complete.verdict is True,
         "with the token, the same content passes"),
        (padded.verdict is True,
         "trailing blank lines after the token are forgiven"),
        (old.verdict is False
         and old.report is E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL,
         "a non-participating nominal sees the token as ordinary "
         "content: one trailing difference"),
    ])
    _verdict(ok, "the nominal decides; absence is named, never "
                 "diffed.")


class _Provided:
    """A groundwork over an already-made Subjects delivery."""
    def __init__(self, subjects):
        self.subjects      = subjects
        self.last_provided = subjects
    async def provide(self, stop_event=None):
        return self.subjects




def test_unexpected_stderr():
    """A FORBIDDEN STDERR (S-1): the book's note says a word on that
    stream is an ERROR -- reported BY NAME, never a line difference
    against a nominal that does not exist. An unnoted choice reads
    'forbidden'. A silent run is untouched by the law, and whitespace
    is silence."""
    async def judged(stderr_text):
        directory = tempfile.mkdtemp(prefix="vut_eq_")
        try:
            store = Store(Bookkeeper(directory))
            store.write_candidate("demo", None, "stdout", "the behaviour\n")
            store.write_candidate("demo", None, "stderr", stderr_text)
            return await EquivalenceCheck(EquivalenceCheckConfig(
                name            = "demo",
                groundwork      = _Provided(loaded(store, "demo")),
                subjects        = {"stdout":
                                   BytesNominal("the behaviour\n")},
                stderr_forbidden_f = True)).run()
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    silent = asyncio.run(judged(""))
    blank  = asyncio.run(judged("\n  \n"))
    noisy  = asyncio.run(judged("a warning nobody blessed\n"))

    print("INSPECT: silent stderr    -> verdict %s, report %s"
          % (silent.verdict, silent.report))
    print("         blank lines only -> verdict %s, report %s"
          % (blank.verdict, blank.report))
    print("         a word on stderr -> verdict %s, report %s"
          % (noisy.verdict, noisy.report))
    ok = _check([
        (silent.verdict is True,
         "silence is what a FORBIDDEN stderr expects"),
        (blank.verdict is True,
         "and whitespace is silence"),
        (noisy.report is E_TestRunResult.UNEXPECTED_STDERR,
         "a WORD there is reported by name"),
        (noisy.verdict is False,
         "and the test failed"),
    ])
    _verdict(ok, "a forbidden stderr is expected to say nothing.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "EquivalenceCheck: read -> verdict",
        choice_map = {
            "unexpected_stderr": test_unexpected_stderr,
            "terminated":       test_terminated,
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
