#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify that the sandbox contains each resource-exhaustion accident
         class and attributes it correctly in SandboxResult.

DESCRIPTION:

The sandbox's one job: a runaway test dies alone, and the report names the
exhausted resource. Each choice provokes one accident class with a small
inline test application and checks the attribution record.

CHOICES:

  wall_clock:  sleep-forever application -> WALL_CLOCK_EXCEEDED near cap.
  cpu_time:    spin loop -> CPU_TIME_EXCEEDED (RLIMIT_CPU / SIGXCPU).
  memory:      growing allocation -> MEMORY_EXCEEDED, peak recorded.
  file_size:   oversized write -> FILE_SIZE_EXCEEDED (RLIMIT_FSIZE),
               file stopped near the cap.
  pids:        fork storm -> contained (PIDS_EXCEEDED or NPROC-failure
               self-abort); no straggling children survive the run.
  no_psutil:   psutil absent -> memory/pid caps reported in .unenforced,
               wall clock still enforced.

AUTHOR: Frank-Rene Schaefer
"""

import asyncio
import logging
import shlex
import sys
import tempfile

from   config import HwutRunner                                   # noqa F401

import vut.engine.sandbox.sandbox              as sandbox_module  # noqa E402
from   vut.engine.sandbox.sandbox              import (Sandbox,   # noqa E402
                                                       SandboxConfig,
                                                       E_Containment)

# Child-reap races between the harness's kill discipline and asyncio's
# child watcher may emit spurious warnings ("Unknown child process ...")
# -- harmless, but nondeterministic; the GOOD file must not see them.
logging.getLogger("asyncio").setLevel(logging.ERROR)

PY = shlex.quote(sys.executable)


def _cmd(app_code: str) -> str:
    """
    RETURN: str, a command line running 'app_code' with this interpreter.
    """
    return f"{PY} -c {shlex.quote(app_code)}"


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


async def _run(config, app_code):
    """
    RETURN: SandboxResult, of running 'app_code' in a fresh scratch dir.
    """
    with tempfile.TemporaryDirectory(prefix="vut_sandbox_test_") as work_dir:
        return await Sandbox(config, work_dir).run(_cmd(app_code))


# ---------------------------------------------------------------------------

async def test_wall_clock():
    """A sleeping (hanging) test burns no CPU; only the wall-clock cap can
    catch it. Expect WALL_CLOCK_EXCEEDED shortly after the cap."""
    config = SandboxConfig(max_wall_clock_sec=1.0)
    result = await _run(config, "import time; time.sleep(30)")

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.WALL_CLOCK_EXCEEDED,
         "containment is WALL_CLOCK_EXCEEDED"),
        (1.0 <= result.wall_clock_sec < 8.0,
         "wall clock between cap and cap + kill overhead"),
        (result.exit_code is None,
         "exit_code is None (the sandbox ended it, not the test)"),
        (result.unenforced == (),
         "no caps unenforced on this platform"),
    ])
    _verdict(ok, "hang contained by wall clock, attributed.")


async def test_cpu_time():
    """A spin loop hits RLIMIT_CPU; the kernel delivers SIGXCPU. Expect
    CPU_TIME_EXCEEDED with measured cpu time near the cap."""
    config = SandboxConfig(max_cpu_time_sec=1, max_wall_clock_sec=15.0)
    result = await _run(config, "while True: pass")

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.CPU_TIME_EXCEEDED,
         "containment is CPU_TIME_EXCEEDED"),
        (result.cpu_time_sec is not None and result.cpu_time_sec >= 0.9,
         "measured cpu time reached the cap"),
        (result.exit_code is None,
         "exit_code is None (the sandbox ended it, not the test)"),
    ])
    _verdict(ok, "spin loop contained by cpu-time cap, attributed.")


async def test_memory():
    """A growing allocation crosses the RSS cap; the watchdog kills the
    group. Expect MEMORY_EXCEEDED with the peak recorded."""
    config = SandboxConfig(max_memory_mb=96, max_wall_clock_sec=20.0)
    app    = ("import time\n"
              "hoard = []\n"
              "while True:\n"
              "    hoard.append(bytearray(4 * 1024 * 1024))\n"
              "    time.sleep(0.01)\n")
    result = await _run(config, app)

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.MEMORY_EXCEEDED,
         "containment is MEMORY_EXCEEDED"),
        (result.peak_memory_mb is not None
         and result.peak_memory_mb > 96.0,
         "recorded peak exceeds the 96 MB cap"),
        (result.peak_memory_mb is not None
         and result.peak_memory_mb < 1024.0,
         "kill came before the hoard grew unbounded (< 1 GB)"),
        (result.exit_code is None,
         "exit_code is None (the sandbox ended it, not the test)"),
    ])
    _verdict(ok, "memory growth contained by RSS watchdog, attributed.")


async def test_file_size():
    """An oversized write hits RLIMIT_FSIZE. Apps that keep the default
    SIGXFSZ disposition die by signal -> FILE_SIZE_EXCEEDED; apps that
    ignore it -- CPython does -- get EFBIG from write() and fail by their
    own OSError -> COMPLETED, nonzero. Either way the kernel cap holds:
    the flood file stops at exactly the cap."""
    import os
    config = SandboxConfig(max_file_size_mb=1, max_wall_clock_sec=15.0)
    app    = ("with open('flood.bin', 'wb') as fh:\n"
              "    for _ in range(64):\n"
              "        fh.write(b'x' * (1024 * 1024))\n"
              "        fh.flush()\n")
    with tempfile.TemporaryDirectory(prefix="vut_sandbox_test_") as work_dir:
        result     = await Sandbox(config, work_dir).run(_cmd(app))
        flood_path = os.path.join(work_dir, "flood.bin")
        size_mb    = (os.path.getsize(flood_path) / (1024.0 * 1024.0)
                      if os.path.exists(flood_path) else 0.0)

    # NOTE: which mechanism fires (SIGXFSZ death vs. EFBIG self-abort) is
    # platform-dependent -- the printed output only asserts the NORMALIZED
    # outcome, so the GOOD file holds on every platform.
    contained_f = (result.containment is E_Containment.FILE_SIZE_EXCEEDED) \
                  or (result.containment is E_Containment.COMPLETED
                      and result.exit_code != 0)
    ok = _check([
        (contained_f,
         "flood contained (SIGXFSZ death or EFBIG self-abort)"),
        (size_mb <= 1.0 + 1e-6,
         "flood file stopped at the 1 MB cap"),
        (result.wall_clock_sec < 10.0,
         "containment came well before the flood's natural end"),
    ])
    _verdict(ok, "disk flooding contained by file-size cap.")


async def test_pids():
    """A fork storm is contained by NPROC (fork fails inside the test) or
    by the watchdog's group count -- either way the storm dies and no
    child survives the run. The marker string tags storm children so the
    post-run scan can prove extinction."""
    import psutil
    marker = "VUT_SANDBOX_PIDBOMB_MARKER"
    config = SandboxConfig(max_pids=8, max_wall_clock_sec=15.0)
    app    = ("import os, sys, time\n"
              "for i in range(64):\n"
              "    pid = os.fork()\n"
              "    if pid == 0:\n"
              f"        sys.argv.append('{marker}')\n"
              "        time.sleep(30)\n"
              "        os._exit(0)\n"
              "time.sleep(30)\n")
    result = await _run(config, app)

    await asyncio.sleep(0.5)    # give the OS a moment to reap
    survivors = [proc for proc in psutil.process_iter(attrs=("cmdline",))
                 if proc.info["cmdline"]
                 and any(marker in arg for arg in proc.info["cmdline"])]

    # NOTE: whether the NPROC rlimit (fork fails inside the test) or the
    # watchdog's group count fires first is a race -- the printed output
    # only asserts the NORMALIZED outcome, so the GOOD file is stable.
    contained_f = (result.containment is E_Containment.PIDS_EXCEEDED) \
                  or (result.containment is E_Containment.COMPLETED
                      and result.exit_code != 0)
    ok = _check([
        (contained_f,
         "storm contained (PIDS_EXCEEDED or NPROC-failure self-abort)"),
        (result.wall_clock_sec < 10.0,
         "containment came well before the storm's natural end"),
        (len(survivors) == 0,
         "no straggling storm children survive the run"),
    ])
    _verdict(ok, "fork storm contained, all children reaped.")


async def test_no_psutil():
    """Honest reporting: without psutil the memory and pid caps cannot be
    enforced -- they must appear in .unenforced; the wall-clock cap must
    keep working."""
    saved = sandbox_module.psutil
    sandbox_module.psutil = None
    try:
        config = SandboxConfig(max_wall_clock_sec=1.0)
        result = await _run(config, "import time; time.sleep(30)")
    finally:
        sandbox_module.psutil = saved

    print(f"INSPECT: containment = {result.containment.name}")
    print(f"INSPECT: unenforced  = {sorted(result.unenforced)}")
    ok = _check([
        (result.containment is E_Containment.WALL_CLOCK_EXCEEDED,
         "wall clock still enforced without psutil"),
        ("max_memory_mb" in result.unenforced,
         "memory cap reported as unenforced"),
        ("max_pids" in result.unenforced,
         "pid cap reported as unenforced"),
        (result.peak_memory_mb is None,
         "no fabricated memory measurement"),
    ])
    _verdict(ok, "degradation without psutil is loud, never silent.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Sandbox resource containment with attribution",
        choice_map = {
            "wall_clock": test_wall_clock,
            "cpu_time":   test_cpu_time,
            "memory":     test_memory,
            "file_size":  test_file_size,
            "pids":       test_pids,
            "no_psutil":  test_no_psutil,
        },
        happy      = "SUCCESS.*",
    ).run()
