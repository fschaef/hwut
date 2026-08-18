#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify the supervised BUILD across the VARIANTS of
         E_BuildSystem: command-line construction for every member,
         real builds with ninja and cmake, and the GENERAL member --
         GENERATOR, a program called in a sandbox to generate the
         targets.

DESCRIPTION:

BASIC functionality (make only) lives in 'test-sandbox_build.py'.
This module walks the vocabulary. Real-tool choices GUARD their
environment actionably (the pype pattern): a missing 'ninja'/'cmake'
is an environment defect, reported with the fix -- never a silent
pass. The GENERATOR choices need only this python interpreter.

CHOICES:

  command_lines:  the CONSTRUCTED command line, pinned per
                  E_BuildSystem -- with targets, without, with tool
                  override, with argument_list; GENERATOR: targets
                  never on the command line. Deterministic, no
                  execution.
  ninja:          a real ninja build of two file targets ->
                  accounted in request order, report 'ok'; plus a
                  failing rule -> 'build-failed'.
  cmake:          a real cmake build: configure (itself a supervised
                  call) then 'cmake --build . --target app' of a C
                  executable; the target file accounted post-exit.
  generator:      THE GENERAL MEMBER: a python code generator writes
                  the requested target files ('argument_list' carries
                  the generator's arguments; 'target_list' is purely
                  the accounting contract) -> report 'ok'; a
                  generator that forgets one target ->
                  'target-not-built', NAMED.

AUTHOR: Frank-Rene Schaefer
"""

import asyncio      # noqa F401  (HwutRunner drives the coroutines)
import logging
import os
import shlex
import shutil
import sys
import tempfile

from   config import HwutRunner                                     # noqa F401

from   vut.engine.sandbox.sandbox       import (Sandbox,            # noqa E402
                                                SandboxConfig,
                                                E_Containment)      # noqa F401
from   vut.engine.sandbox.sandbox_build import (E_BuildSystem,      # noqa E402
                                                SandboxConfigBuild,
                                                run_build)
from   vut.auxiliary.test_run_result    import E_TestRunResult      # noqa E402

logging.getLogger("asyncio").setLevel(logging.ERROR)

PY = shlex.quote(sys.executable)


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


def _require_tool(name):
    """
    RETURN: True,  the tool is present on PATH.
            False, else -- with an ACTIONABLE report: this is an
                   environment defect, not a code defect.
    """
    if shutil.which(name) is not None:
        return True
    print(f"FAIL: build tool not found on PATH: '{name}'")
    print(f"      install '{name}' to run this choice.")
    return False


def _sandbox(work_dir, wall=60.0):
    """
    RETURN: Sandbox, a supervised call in 'work_dir' under a
            wall-clock cap.
    """
    return Sandbox(SandboxConfig(max_wall_clock_sec=wall), work_dir)


def _write(work_dir, name, text):
    """
    RETURN: None. Writes 'text' as file 'name' in 'work_dir'.
    """
    with open(os.path.join(work_dir, name), "w") as fh:
        fh.write(text)


# ---------------------------------------------------------------------------

async def test_command_lines():
    """The command line is CONSTRUCTED from the enumerated vocabulary
    -- the caller composes data, not plumbing. Pinned per build
    system; GENERATOR never receives the targets (accounting contract
    only). No execution."""
    from vut.engine.sandbox.sandbox_build import _make_command_line

    def line(build_system, target_list, tool=None, argument_list=()):
        """RETURN: str, the constructed command line (no run)."""
        return _make_command_line(SandboxConfigBuild(
            build_system  = build_system,
            target_list   = target_list,
            sandbox       = None,          # construction only
            tool          = tool,
            argument_list = list(argument_list)))

    case_list = [
        ("make, two targets",
         line(E_BuildSystem.MAKE,  ["all", "install"]),
         "make all install"),
        ("make, default target",
         line(E_BuildSystem.MAKE,  []),
         "make"),
        ("make, tool override",
         line(E_BuildSystem.MAKE,  ["all"], tool="gmake"),
         "gmake all"),
        ("make, argument_list",
         line(E_BuildSystem.MAKE,  ["app"], argument_list=["-j4"]),
         "make -j4 app"),
        ("make, target needing quotes",
         line(E_BuildSystem.MAKE,  ["dir with space/x.out"]),
         "make 'dir with space/x.out'"),
        ("ninja, two targets",
         line(E_BuildSystem.NINJA, ["lib.a", "app"]),
         "ninja lib.a app"),
        ("cmake, two targets",
         line(E_BuildSystem.CMAKE, ["lib", "app"]),
         "cmake --build . --target lib app"),
        ("cmake, default",
         line(E_BuildSystem.CMAKE, []),
         "cmake --build ."),
        ("cmake, argument_list",
         line(E_BuildSystem.CMAKE, ["app"],
              argument_list=["--config", "Release"]),
         "cmake --build . --config Release --target app"),
        ("generator: targets NOT passed",
         line(E_BuildSystem.GENERATOR, ["a.c", "b.c"],
              tool="python3", argument_list=["gen.py", "--fast"]),
         "python3 gen.py --fast"),
    ]
    ok = True
    for label, got, expected in case_list:
        good_f = (got == expected)
        print(f"  {'OK  ' if good_f else 'FAIL'}: {label:<30} -> {got}")
        ok = ok and good_f
    _verdict(ok, "command lines constructed from the enumerated "
                 "vocabulary.")


async def test_ninja():
    """A real ninja build: two file targets accounted in request
    order; then a failing rule -> 'build-failed' with the WHY in the
    record's stderr tail."""
    build_ninja = (
        "rule emit\n"
        "  command = echo made-$out > $out\n"
        "rule boom\n"
        "  command = sh -c 'echo ninja-rule-broken >&2; exit 1'\n"
        "build alpha.out: emit\n"
        "build beta.out: emit\n"
        "build broken.out: boom\n")

    if not _require_tool("ninja"): return
    with tempfile.TemporaryDirectory(prefix="vut_build_") as work_dir:
        _write(work_dir, "build.ninja", build_ninja)
        good = await run_build(SandboxConfigBuild(
            build_system = E_BuildSystem.NINJA,
            target_list  = ["beta.out", "alpha.out"],
            sandbox      = _sandbox(work_dir)))
        bad  = await run_build(SandboxConfigBuild(
            build_system = E_BuildSystem.NINJA,
            target_list  = ["broken.out"],
            sandbox      = _sandbox(work_dir)))

    print(f"INSPECT: good: built = {list(good.built_target_list)}, "
          f"report = {good.report}")
    print(f"INSPECT: bad:  exit = {bad.record.exit_code}, "
          f"report = {bad.report}")
    ok = _check([
        (good.built_target_list == ("beta.out", "alpha.out"),
         "ninja targets built -- accounted in request order"),
        (good.verdict is True and str(good.report) == "ok",
         "verdict True; brief report 'ok'"),
        (bad.report is E_TestRunResult.BUILD_FAILED,
         "failing rule -> 'build-failed'"),
        # ninja echoes the failing command's output on its own STDOUT;
        # the stderr tail is not asserted here (tool-specific habit).
        (bad.verdict is False,
         "no True verdict for the failing build"),
    ])
    _verdict(ok, "ninja variant: build and failure, both attributed.")


async def test_cmake():
    """A real cmake build. CONFIGURE is itself a supervised system
    call (the ground serves every step); then the door:
    'cmake --build . --target app'. The built executable is the
    accounted target file."""
    cmakelists = (
        "cmake_minimum_required(VERSION 3.10)\n"
        "project(vut_variant C)\n"
        "add_executable(app app.c)\n")
    app_c = ('#include <stdio.h>\n'
             'int main(void) { printf("app speaking\\n"); return 0; }\n')

    if not _require_tool("cmake"): return
    if not _require_tool("cc"):    return
    with tempfile.TemporaryDirectory(prefix="vut_build_") as work_dir:
        _write(work_dir, "CMakeLists.txt", cmakelists)
        _write(work_dir, "app.c",          app_c)

        # CONFIGURE: a plain supervised call -- the ground, reused.
        configure = await _sandbox(work_dir).run("cmake -S . -B .")

        result = await run_build(SandboxConfigBuild(
            build_system = E_BuildSystem.CMAKE,
            target_list  = ["app"],
            sandbox      = _sandbox(work_dir)))

    print(f"INSPECT: configure = {configure.containment.name}, "
          f"built = {list(result.built_target_list)}, "
          f"report = {result.report}")
    ok = _check([
        (configure.ok,
         "configure step: supervised call completed"),
        (result.built_target_list == ("app",),
         "the executable target is accounted post-exit"),
        (result.verdict is True and str(result.report) == "ok",
         "verdict True; brief report 'ok'"),
    ])
    _verdict(ok, "cmake variant: configure supervised, build through "
                 "the door.")


async def test_generator():
    """THE GENERAL MEMBER: any program called in a sandbox to
    generate targets. The generator's arguments travel in
    'argument_list'; 'target_list' is purely the ACCOUNTING CONTRACT
    -- never passed to the tool. A generator that forgets a target is
    caught post-exit, the target NAMED."""
    gen_py = ("import sys\n"
              "for name in sys.argv[1:]:\n"
              "    with open(name, 'w') as fh:\n"
              "        fh.write('/* generated: ' + name + ' */\\n')\n")

    with tempfile.TemporaryDirectory(prefix="vut_build_") as work_dir:
        _write(work_dir, "gen.py", gen_py)

        good = await run_build(SandboxConfigBuild(
            build_system  = E_BuildSystem.GENERATOR,
            target_list   = ["lexer.c", "parser.c"],   # the contract
            sandbox       = _sandbox(work_dir),
            tool          = sys.executable,
            argument_list = ["gen.py", "lexer.c", "parser.c"]))

        forgetful = await run_build(SandboxConfigBuild(
            build_system  = E_BuildSystem.GENERATOR,
            target_list   = ["lexer2.c", "parser2.c"], # the contract...
            sandbox       = _sandbox(work_dir),
            tool          = sys.executable,
            argument_list = ["gen.py", "lexer2.c"]))   # ...half kept

        lexer_txt = open(os.path.join(work_dir, "lexer.c")).read()

    print(f"INSPECT: good: built = {list(good.built_target_list)}, "
          f"report = {good.report}")
    print(f"INSPECT: forgetful: built = "
          f"{list(forgetful.built_target_list)}, "
          f"missing = {list(forgetful.missing_target_list)}, "
          f"report = {forgetful.report}")
    ok = _check([
        (good.built_target_list == ("lexer.c", "parser.c"),
         "generated targets accounted -- the contract is honored"),
        (lexer_txt == "/* generated: lexer.c */\n",
         "target content is the generator's"),
        (good.verdict is True and str(good.report) == "ok",
         "verdict True; brief report 'ok'"),
        (forgetful.record.ok,
         "forgetful generator exits 0 -- exit code alone looks fine"),
        (forgetful.built_target_list == ("lexer2.c",)
         and forgetful.missing_target_list == ("parser2.c",),
         "the forgotten target is NAMED"),
        (forgetful.report is E_TestRunResult.TARGET_NOT_BUILT,
         "brief report 'target-not-built'"),
    ])
    _verdict(ok, "the general generator: contract in, accounting out.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Supervised build variants: every E_BuildSystem "
                     "member, incl. the general generator",
        choice_map = {
            "command_lines": test_command_lines,
            "ninja":         test_ninja,
            "cmake":         test_cmake,
            "generator":     test_generator,
        },
        happy      = "SUCCESS.*",
    ).run()
