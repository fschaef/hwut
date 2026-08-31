#! /usr/bin/env python3
#
# @hwut {
#     title      = "The build step of provision"
#     choices    = ["argv", "contained", "reasons", "silent_failure",
#                   "success"]
#     eq-pattern = ["SUCCESS.*"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE BUILD STEP OF PROVISION.

    UNIT     'BuildConfig' + 'build()' -- one supervised call, an argv
             built from the enumerated vocabulary, and POST-EXIT target
             accounting against a declared contract.

    CAUSAL CONTRACT
             the argv follows from the build system; the build runs in
             'BUILD/<file>'; the report names what went wrong, tool
             reasons outranking target reasons.

    CONSISTENCY CONTRACT
             a tool that reports success and produced nothing is CAUGHT
             by the accounting; GENERATOR without a tool is refused
             rather than guessed at.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.result     import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.api  import ProcsitterConfig # noqa E402
from   vut.engine.operations.build_action import (BuildConfig,    # noqa E402
                                                   E_BuildSystem,
                                                   build,
                                                   make_argv)
from   vut.engine.operations.configuration import (               # noqa E402
                                                 TestConfiguration,
                                                 TestChoiceConfiguration,
                                                 E_SourceKind)


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


def _configuration(directory, build_configuration):
    """RETURN: TestConfiguration, a COMPILED test in 'directory'."""
    return TestConfiguration(source_file    = "demo.c",
                             source_kind    = E_SourceKind.COMPILED,
                             test_directory = directory,
                             caps           = ProcsitterConfig(
                                                  max_wall_clock_sec=20.0),
                             build          = build_configuration,
                             choice_db      = {None: TestChoiceConfiguration()})


def _with_makefile(body):
    """
    RETURN: (TestConfiguration factory input) str, a fresh test directory
            whose 'BUILD/demo.c' holds a Makefile with 'body'.
    """
    directory = tempfile.mkdtemp(prefix="vut_build_")
    build_dir = os.path.join(directory, "BUILD", "demo.c")
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, "Makefile"), "w") as fh:
        fh.write(body)
    return directory


def test_argv():
    """The argv is CONSTRUCTED from the enumerated vocabulary -- never
    assembled by the caller, so no quoting question arises."""
    row_list = [
        ("MAKE with an argument",
         BuildConfig(E_BuildSystem.MAKE, ["app"], ["-j2"])),
        ("NINJA",
         BuildConfig(E_BuildSystem.NINJA, ["app"])),
        ("CMAKE (targets need --target)",
         BuildConfig(E_BuildSystem.CMAKE, ["app"])),
        ("GENERATOR (targets are accounting only)",
         BuildConfig(E_BuildSystem.GENERATOR, ["out.c"], ["spec.y"],
                     tool="protoc")),
        ("MESON (subcommand 'compile')",
         BuildConfig(E_BuildSystem.MESON, ["app"])),
        ("BAZEL (subcommand 'build')",
         BuildConfig(E_BuildSystem.BAZEL, ["//app:all"])),
        ("SCONS (plain, like make)",
         BuildConfig(E_BuildSystem.SCONS, ["app"], ["-j2"])),
        ("MSBUILD (targets FOLDED into -t:)",
         BuildConfig(E_BuildSystem.MSBUILD, ["Build", "Test"])),
    ]
    for title, configuration in row_list:
        print("INSPECT: %-38s -> %s" % (title, make_argv(configuration)))

    refused = None
    try:
        make_argv(BuildConfig(E_BuildSystem.GENERATOR, ["out.c"]))
    except AssertionError as error:
        refused = str(error)
    print("         GENERATOR without a tool               -> %s"
          % (refused or "NOT REFUSED"))
    ok = _check([
        (make_argv(row_list[2][1])[:3] == ["cmake", "--build", "."],
         "CMAKE builds the current directory"),
        ("out.c" not in make_argv(row_list[3][1]),
         "a GENERATOR's targets stay OFF the command line"),
        (refused is not None,
         "GENERATOR without a tool is refused, not guessed at"),
        (make_argv(row_list[4][1])[:2] == ["meson", "compile"]
         and make_argv(row_list[5][1])[:2] == ["bazel", "build"],
         "MESON and BAZEL carry their subcommand"),
        (make_argv(row_list[7][1])[-1] == "-t:Build;Test",
         "MSBUILD folds its targets into ONE -t: option"),
    ])
    _verdict(ok, "one vocabulary, one argv, no quoting question.")


def test_success():
    """A build that runs and produces its target. It runs in BUILD/<file>,
    which is where the accounting then looks."""
    directory = _with_makefile("app:\n\techo built > app\n")
    configuration = _configuration(directory,
                                   BuildConfig(E_BuildSystem.MAKE, ["app"]))
    outcome = asyncio.run(build(configuration))
    where   = os.path.relpath(configuration.build_directory, directory)

    print("INSPECT: ran in    = %s" % where)
    print("         report    = %s" % outcome.report)
    print("         built     = %s" % list(outcome.built_target_list))
    print("         missing   = %s" % list(outcome.missing_target_list))
    ok = _check([
        (where == os.path.join("BUILD", "demo.c"),
         "the build ran in BUILD/<file>, not in the test directory"),
        (outcome.report is E_TestRunResult.OK,
         "the report is OK"),
        (outcome.built_target_list == ("app",),
         "the declared target is accounted present"),
        (outcome.succeeded is True,
         "and the outcome says it succeeded"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a build runs in its own directory and accounts its targets.")


def test_silent_failure_is_caught():
    """THE CASE THE ACCOUNTING EXISTS FOR: a tool that exits ZERO and
    produces nothing. Supervision sees a clean exit; only the post-exit
    walk of the declared contract catches it."""
    directory = _with_makefile("app:\n\t@echo 'pretending to build'\n")
    configuration = _configuration(directory,
                                   BuildConfig(E_BuildSystem.MAKE, ["app"]))
    outcome = asyncio.run(build(configuration))

    print("INSPECT: the tool exited cleanly: containment = %s"
          % outcome.record.containment.name)
    print("         report  = %s" % outcome.report)
    print("         missing = %s" % list(outcome.missing_target_list))
    ok = _check([
        (outcome.record.containment.name == "OK_COMPLETED",
         "supervision saw nothing wrong -- the tool exited zero"),
        (outcome.report is E_TestRunResult.TARGET_NOT_BUILT,
         "the ACCOUNTING caught it: the declared target is absent"),
        (outcome.succeeded is False,
         "so the build did not succeed, whatever the exit code said"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a clean exit is not proof that anything was built.")


def test_reasons():
    """Tool reasons outrank target reasons: a tool that never ran cannot
    be blamed for a target it never reached."""
    absent_tool = _with_makefile("app:\n\ttrue\n")
    failing     = _with_makefile("app:\n\tfalse\n")

    outcome_tool = asyncio.run(build(_configuration(
        absent_tool, BuildConfig(E_BuildSystem.MAKE, ["app"],
                                 tool="no-such-build-tool-anywhere"))))
    outcome_fail = asyncio.run(build(_configuration(
        failing, BuildConfig(E_BuildSystem.MAKE, ["app"]))))

    print("INSPECT: tool not on PATH -> %s" % outcome_tool.report)
    print("         tool exits non-zero -> %s" % outcome_fail.report)
    ok = _check([
        (outcome_tool.report is E_TestRunResult.BUILD_TOOL_NOT_FOUND,
         "an absent tool reports the TOOL, not the missing target"),
        (outcome_fail.report is E_TestRunResult.BUILD_FAILED,
         "a failing tool reports the FAILURE, not the missing target"),
        (outcome_tool.missing_target_list == ("app",),
         "the target is still accounted absent -- the evidence remains"),
    ])
    for d in (absent_tool, failing): shutil.rmtree(d, ignore_errors=True)
    _verdict(ok, "tool reasons outrank target reasons.")


def test_contained_build():
    """A build is a supervised call like any other: a cap ends it, and
    the report says the build was CONTAINED rather than that it failed.
    A tool the procsitter stopped did not decide anything."""
    directory = _with_makefile("app:\n\tsleep 30\n")
    configuration = _configuration(directory,
                                   BuildConfig(E_BuildSystem.MAKE, ["app"]))
    outcome = asyncio.run(build(configuration,
                                caps=ProcsitterConfig(max_wall_clock_sec=1.0)))

    print("INSPECT: containment = %s" % outcome.record.containment.name)
    print("         report      = %s" % outcome.report)
    ok = _check([
        (outcome.record.containment.name == "FAIL_WALL_CLOCK_EXCEEDED",
         "the procsitter ended the build"),
        (outcome.report is E_TestRunResult.BUILD_CONTAINED,
         "reported as CONTAINED -- not as a build that failed on merit"),
        (outcome.succeeded is False,
         "and it did not succeed"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a contained build is distinguished from a failed one.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The build step of provision",
        choice_map = {
            "argv":           test_argv,
            "success":        test_success,
            "silent_failure": test_silent_failure_is_caught,
            "reasons":        test_reasons,
            "contained":      test_contained_build,
        },
        happy      = "SUCCESS.*",
    ).run()
