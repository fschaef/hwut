#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify the supervised BUILD (procsitter_build.py): one door,
         input = configuration (ProcsitterConfigBuild), output = result
         (ProcsitterResultBuild) -- the targets ACTUALLY BUILT are
         accounted after the task finished.

DESCRIPTION:

The build is an ordinary supervised system call; this module's own
contribution is the VOCABULARY (E_BuildSystem, targets) and the
POST-EXIT ACCOUNTING of targets.

BASIC functionality with 'make' ONLY -- the one build tool present
everywhere the suite runs. The VARIANTS (every E_BuildSystem member,
command-line construction, the general code generator) live in
'test-procsitter_build-variants.py'.

CHOICES:

  make_targets:          two file targets via a real Makefile ->
                         both in '.built_target_list' (request
                         order), verdict True, report 'ok'.
  target_missing:        the tool exits 0, yet one requested target
                         is not a file post-exit (phony-style rule)
                         -> report 'target-not-built'; the missing
                         target is NAMED; the built one still
                         accounted.
  build_classification:  E_TestRunResult, THE BRIEF REPORT of a
                         build: build-tool-not-found,
                         build-contained (wall cap), build-failed
                         (nonzero exit; stderr tail captured as the
                         WHY).

AUTHOR: Frank-Rene Schaefer
"""

import asyncio      # noqa F401  (HwutRunner drives the coroutines)
import logging
import os
import sys
import tempfile

from   config import HwutRunner                                     # noqa F401

from   vut.engine.procsitter.procsitter       import (Procsitter,            # noqa E402
                                                ProcsitterConfig,
                                                E_Containment)
from   vut.engine.test_run.procsitter_build import (E_BuildSystem,      # noqa E402
                                                ProcsitterConfigBuild,
                                                ProcsitterResultBuild,  # noqa F401
                                                run_build)
from   vut.auxiliary.test_run_result    import E_TestRunResult      # noqa E402

logging.getLogger("asyncio").setLevel(logging.ERROR)


def _check(results):
    """
    RETURN: True,  all (bool, label) pairs in results are True;
                   prints OK/FAIL per line.
            False, else.
    """
    ok = True
    for result, label in results:
        print(f"  {'OK  ' if result else 'FAIL'}: {label}")
        ok = ok and result
    return ok


def _verdict(ok, subject):
    """
    RETURN: None. Prints the final SUCCESS/FAIL line for the choice.
    """
    if ok: print(f"SUCCESS: {subject}")
    else:  print(f"FAIL: {subject} (see above)")


def _write_makefile(work_dir, text):
    """
    RETURN: None. Writes 'text' as the work dir's Makefile.
    """
    with open(os.path.join(work_dir, "Makefile"), "w") as fh:
        fh.write(text)


def _build_config(work_dir, target_list, wall=20.0, tool=None):
    """
    RETURN: ProcsitterConfigBuild, a make-driven build of 'target_list'
            in 'work_dir' under a wall-clock cap.
    """
    return ProcsitterConfigBuild(
        build_system = E_BuildSystem.MAKE,
        target_list  = target_list,
        procsitter      = Procsitter(ProcsitterConfig(max_wall_clock_sec=wall),
                               work_dir),
        tool         = tool)


def _print_build_diagnostics(label, result):
    """
    RETURN: None. On a failed build -- nonzero exit, containment, or a
            missing target -- prints exit code and the captured
            stderr tail: the WHY. (Failure paths only; the GOOD file
            never sees this.)
    """
    if result.record.containment is E_Containment.OK_COMPLETED and not result.missing_target_list:
        return
    print(f"DIAGNOSTIC: {label}: containment="
          f"{result.record.containment.name}, "
          f"exit_code={result.record.exit_code}, "
          f"missing={list(result.missing_target_list)}")
    for line in result.record.stderr_last_100_lines.splitlines():
        print(f"DIAGNOSTIC: {label} stderr| {line}")


# ---------------------------------------------------------------------------

async def test_make_targets():
    """The happy path: two file targets, really built by make; both
    accounted in request order after the task finished."""
    makefile = ("alpha.out:\n"
                "\techo 'alpha built' > alpha.out\n"
                "beta.out: alpha.out\n"
                "\tcat alpha.out > beta.out\n"
                "\techo 'beta built' >> beta.out\n")

    with tempfile.TemporaryDirectory(prefix="vut_build_") as work_dir:
        _write_makefile(work_dir, makefile)
        result = await run_build(
            _build_config(work_dir, ["beta.out", "alpha.out"]))
        # Guarded: a build gone wrong must be DIAGNOSED, never crash
        # this test on a bare, uninformative FileNotFoundError.
        beta_txt = (open(os.path.join(work_dir, "beta.out")).read()
                    if "beta.out" in result.built_target_list else "")

    print(f"INSPECT: containment = {result.record.containment.name}, "
          f"built = {list(result.built_target_list)}, "
          f"report = {result.report}")
    ok = _check([
        (result.record.containment is E_Containment.OK_COMPLETED,
         "build tool completed with exit 0"),
        (result.built_target_list == ("beta.out", "alpha.out"),
         "both targets built -- accounted in request order"),
        (result.missing_target_list == (),
         "nothing missing"),
        (beta_txt == "alpha built\nbeta built\n",
         "target content is the build's, not a stand-in"),
        (result.verdict is True and str(result.report) == "ok",
         "verdict True; brief report 'ok'"),
    ])
    _print_build_diagnostics("make_targets", result)
    _verdict(ok, "targets built and accounted after the task finished.")


async def test_target_missing():
    """The tool is content -- exit 0 -- but a requested target is not
    a file post-exit (a phony-style rule that builds nothing). The
    accounting catches what the exit code cannot; the missing target
    is NAMED."""
    makefile = ("real.out:\n"
                "\techo 'made' > real.out\n"
                "ghost.out:\n"
                "\ttrue\n")

    with tempfile.TemporaryDirectory(prefix="vut_build_") as work_dir:
        _write_makefile(work_dir, makefile)
        result = await run_build(
            _build_config(work_dir, ["real.out", "ghost.out"]))

    print(f"INSPECT: exit = {result.record.exit_code}, "
          f"built = {list(result.built_target_list)}, "
          f"missing = {list(result.missing_target_list)}")
    ok = _check([
        (result.record.containment is E_Containment.OK_COMPLETED,
         "tool exit 0 -- the exit code alone would look fine"),
        (result.built_target_list == ("real.out",),
         "the built target is accounted"),
        (result.missing_target_list == ("ghost.out",),
         "the unbuilt target is NAMED"),
        (result.verdict is False
         and result.report is E_TestRunResult.TARGET_NOT_BUILT,
         "verdict False; brief report 'target-not-built'"),
    ])
    _verdict(ok, "post-exit accounting catches the target the exit code "
                 "missed.")


async def test_build_classification():
    """E_TestRunResult grown to the build: one provoked reason per
    case. Tool reasons outrank target reasons; 'build-failed' carries
    the WHY in the record's captured stderr tail."""

    async def classify(makefile, target_list, wall=20.0, tool=None):
        """RETURN: ProcsitterResultBuild of one provoked build."""
        with tempfile.TemporaryDirectory(prefix="vut_build_") as work_dir:
            if makefile is not None:
                _write_makefile(work_dir, makefile)
            return await run_build(
                _build_config(work_dir, target_list, wall=wall, tool=tool))

    absent    = await classify("x.out:\n\ttouch x.out\n", ["x.out"],
                               tool="/no/such/make")
    contained = await classify("x.out:\n\tsleep 30\n", ["x.out"],
                               wall=1.0)
    failed    = await classify("x.out:\n\texit 1\n", ["x.out"])

    case_list = [
        ("tool not found",
         absent.report,    E_TestRunResult.BUILD_TOOL_NOT_FOUND),
        ("hanging rule (wall cap 1 s)",
         contained.report, E_TestRunResult.BUILD_CONTAINED),
        ("failing rule (exit 1)",
         failed.report,    E_TestRunResult.BUILD_FAILED),
    ]
    ok = True
    for label, got, expected in case_list:
        good_f = (got is expected)
        print(f"  {'OK  ' if good_f else 'FAIL'}: {label:<28} -> {got}")
        ok = ok and good_f
    ok = _check([
        (contained.record.containment
             is E_Containment.FAIL_WALL_CLOCK_EXCEEDED,
         "contained build: the record names the resource"),
        (failed.record.stderr_last_100_lines != "",
         "failing build: stderr tail captured -- the WHY survives"),
        (absent.verdict is False and contained.verdict is False
         and failed.verdict is False,
         "no failing case sneaks a True verdict"),
    ]) and ok
    _verdict(ok, "the brief report names the build failure, one token "
                 "each.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Supervised build: config in, result out, targets "
                     "accounted",
        choice_map = {
            "make_targets":         test_make_targets,
            "target_missing":       test_target_missing,
            "build_classification": test_build_classification,
        },
        happy      = "SUCCESS.*",
    ).run()
