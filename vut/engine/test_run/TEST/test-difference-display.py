#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

DIFFERENCE DISPLAY AND THE FEED SESSION.

    UNIT     'DifferenceDisplay' + the feed session -- the second reader,
             which carries the whole ALIGNMENT out instead of reducing it.

    CAUSAL CONTRACT
             DOWN is compare's own item stream, carried not interpreted;
             a driver sees open -> items -> close, in that order; every
             named subject is shown, never only the first.

    CONSISTENCY CONTRACT
             a display cannot change a verdict; 'close' runs however the
             session ended; a signature this hub cannot parse is REFUSED
             before parsing, never guessed at.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.auxiliary.test_run_result       import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.procsitter    import ProcsitterConfig # noqa E402
from   vut.engine.test_run.configuration   import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   E_SourceKind)
from   vut.engine.test_run.difference_display import (           # noqa E402
                                                   DifferenceDisplay,
                                                   DifferenceDisplayConfig)
from   vut.engine.test_run.feed            import (              # noqa E402
                                                   CollectingDisplay,
                                                   NullDisplay,
                                                   ProtocolMismatch,
                                                   PROTOCOL_SIGNATURE,
                                                   check_signature)
from   vut.engine.test_run.nominal         import BytesNominal   # noqa E402
from   vut.engine.test_run.provision       import Run            # noqa E402


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
    directory = tempfile.mkdtemp(prefix="vut_disp_")
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


def _show(directory, subject_db, adapter, only_differing=True):
    """RETURN: TestResult, of one DifferenceDisplay over a fresh Run."""
    return asyncio.run(DifferenceDisplay(DifferenceDisplayConfig(
        name           = "demo",
        groundwork     = Run(_configuration(directory)),
        subjects       = subject_db,
        adapter        = adapter,
        only_differing = only_differing)).run())


def test_down_is_compares():
    """DOWN is compare's own item stream: a header, how the comparison was
    set, the section, the aligned rows, the end. This module CARRIES those
    items; it does not invent or interpret them."""
    directory = _place("print('alpha'); print('WRONG'); print('gamma')\n")
    adapter   = CollectingDisplay()
    result    = _show(directory,
                      {"stdout": BytesNominal("alpha\nbeta\ngamma\n")},
                      adapter)

    print("INSPECT: verdict = %s, report = %s" % (result.verdict, result.report))
    print("         opened  = %s, closed = %s"
          % (adapter.opened_list, adapter.closed))
    print("         DOWN    = %s"
          % [type(item).__name__ for item in adapter.item_list])
    ok = _check([
        (type(adapter.item_list[0]).__name__ == "ProtocolHeader",
         "the stream opens with a signature the receiver checks FIRST"),
        (type(adapter.item_list[-1]).__name__ == "EndOfStreamInst",
         "and ends with an explicit end -- never merely stopping"),
        (sum(1 for i in adapter.item_list
             if type(i).__name__ == "LinePairInst") == 3,
         "one aligned row per line pair of the comparison"),
        (result.verdict is False,
         "the verdict is what the comparison found"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "DOWN is compare's; this module carries it.")


def test_sequence_is_kept():
    """A driver sees the required SEQUENCE: open, the items, close -- and
    'close' runs however the session ended, so a driver that raised mid
    presentation still releases what it holds."""
    directory = _place("print('one')\n")

    class Recorder(NullDisplay):
        def __init__(self):  self.trace = []
        async def open(self, name):   self.trace.append("open:%s" % name)
        async def present(self, item):
            self.trace.append("item")
            if len([t for t in self.trace if t == "item"]) == 2:
                raise RuntimeError("this driver fails mid-presentation")
        async def close(self):        self.trace.append("close")

    recorder = Recorder()
    raised   = None
    try:
        _show(directory, {"stdout": BytesNominal("something else\n")},
              recorder)
    except RuntimeError as error:
        raised = str(error)

    print("INSPECT: trace = %s" % recorder.trace)
    print("         the driver's exception PROPAGATED: %s" % (raised is not None))
    ok = _check([
        (recorder.trace[0] == "open:stdout",
         "the session opens naming the subject"),
        (recorder.trace[-1] == "close",
         "and closes even though presentation raised"),
        (raised is not None,
         "the failure PROPAGATES: a display that failed is not reported "
         "as a display that happened"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "open, items, close -- close always.")


def test_every_subject_is_shown():
    """No fast-fail here. A person looking at a difference wants all of
    it; stopping at the first would hide the rest of what changed."""
    directory = _place("import sys\n"
                       "print('stdout is wrong')\n"
                       "sys.stderr.write('stderr is wrong too\\n')\n")
    adapter = CollectingDisplay()
    result  = _show(directory,
                    {"stdout": BytesNominal("expected out\n"),
                     "stderr": BytesNominal("expected err\n")},
                    adapter)

    print("INSPECT: judged = %s" % sorted(result.comparison.subject_verdict_db))
    print("         shown  = %s" % adapter.opened_list)
    ok = _check([
        (sorted(result.comparison.subject_verdict_db) == ["stderr", "stdout"],
         "BOTH subjects are judged, not just the first"),
        (sorted(adapter.opened_list) == ["stderr", "stdout"],
         "and both are shown"),
        (result.verdict is False,
         "the test still fails"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a difference is shown whole, never truncated.")


def test_matching_subject_is_not_shown():
    """By default only what DIFFERS is carried out. A matching subject
    costs nothing to display because it is not displayed."""
    directory = _place("print('the same')\n")
    quiet     = CollectingDisplay()
    verbose   = CollectingDisplay()
    same      = BytesNominal("the same\n")

    matched = _show(directory, {"stdout": same}, quiet)
    _show(directory, {"stdout": BytesNominal("the same\n")}, verbose,
          only_differing=False)

    print("INSPECT: matching, only_differing -> shown %s, items %i"
          % (quiet.opened_list, len(quiet.item_list)))
    print("         matching, always         -> shown %s, items %i"
          % (verbose.opened_list, len(verbose.item_list)))
    ok = _check([
        (quiet.opened_list == [],
         "a matching subject is not carried out at all"),
        (verbose.opened_list == ["stdout"],
         "unless the caller asked for everything"),
        (matched.verdict is True,
         "and either way the verdict is unchanged"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "only what differs is carried, unless asked otherwise.")


def test_signature_refuses():
    """A hub checks the signature BEFORE parsing, so it never reads a
    message with the wrong parser. On mismatch it REFUSES."""
    accepted = refused = None
    try:
        check_signature(PROTOCOL_SIGNATURE)
        accepted = "accepted"
    except ProtocolMismatch as error:
        accepted = str(error)
    try:
        check_signature("some-other-protocol/9")
    except ProtocolMismatch as error:
        refused = str(error)

    print("INSPECT: our own signature   -> %s" % accepted)
    print("         a foreign signature -> %s"
          % (refused.split("--")[0].strip() if refused else "NOT REFUSED"))
    ok = _check([
        (accepted == "accepted",
         "the signature this hub speaks is accepted"),
        (refused is not None,
         "a foreign one is REFUSED rather than guessed at"),
    ])
    _verdict(ok, "refuse rather than mis-read.")


def test_display_cannot_change_a_verdict():
    """A display is a side effect of the same reading. Whatever the target
    does, the verdict is what the comparison found."""
    directory = _place("print('alpha')\n")
    with_display = _show(directory, {"stdout": BytesNominal("alpha\n")},
                         CollectingDisplay())
    without      = _show(directory, {"stdout": BytesNominal("alpha\n")},
                         NullDisplay())
    differing    = _show(directory, {"stdout": BytesNominal("beta\n")},
                         CollectingDisplay())

    print("INSPECT: matching + a target -> %s / %s"
          % (with_display.verdict, with_display.report))
    print("         matching + none     -> %s / %s"
          % (without.verdict, without.report))
    print("         differing + target  -> %s / %s"
          % (differing.verdict, differing.report))
    ok = _check([
        (with_display.verdict == without.verdict is True,
         "the target does not change a passing verdict"),
        (with_display.report is without.report is E_TestRunResult.OK,
         "nor the report"),
        (differing.report is E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL,
         "a shown difference still reports the mismatch, not the display"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "showing a difference does not change it.")


def test_failed_provision_shows_nothing():
    """The display behaves EXACTLY as the fast reader when provision
    failed: the comparison is absent, the report names the build, and
    nothing is carried out to the target."""
    directory = tempfile.mkdtemp(prefix="vut_disp_")
    os.makedirs(os.path.join(directory, "BUILD", "broke"))
    with open(os.path.join(directory, "BUILD", "broke", "Makefile"), "w") as fh:
        fh.write("app:\n\tfalse\n")
    from vut.engine.test_run.build import BuildConfig, E_BuildSystem
    configuration = TestConfiguration(
        source_file    = "broke.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        build          = BuildConfig(E_BuildSystem.MAKE, ["app"]),
        choice_db      = {None: TestChoiceConfiguration()})
    adapter = CollectingDisplay()
    result  = asyncio.run(DifferenceDisplay(DifferenceDisplayConfig(
        name       = "broke",
        groundwork = Run(configuration),
        subjects   = {"stdout": BytesNominal("anything\n")},
        adapter    = adapter)).run())

    print("INSPECT: verdict    = %s" % result.verdict)
    print("         report     = %s" % result.report)
    print("         comparison = %s" % result.comparison)
    print("         target saw = %s items, opened %s"
          % (len(adapter.item_list), adapter.opened_list))
    ok = _check([
        (result.verdict is False
             and result.report is E_TestRunResult.BUILD_FAILED,
         "the display reports the build, exactly as the fast reader does"),
        (result.comparison is None,
         "the comparison is ABSENT"),
        (adapter.item_list == [] and adapter.opened_list == [],
         "and NOTHING was carried out -- there was nothing to show"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "no provision, no comparison, nothing shown.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "DifferenceDisplay and the feed session",
        choice_map = {
            "down_stream":   test_down_is_compares,
            "sequence":      test_sequence_is_kept,
            "every_subject": test_every_subject_is_shown,
            "only_differing": test_matching_subject_is_not_shown,
            "signature":     test_signature_refuses,
            "verdict_safe":  test_display_cannot_change_a_verdict,
            "no_provision":  test_failed_provision_shows_nothing,
        },
        happy      = "SUCCESS.*",
    ).run()
