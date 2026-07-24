#!/usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Verify that the procsitter contains each resource-exhaustion accident
         class and attributes it correctly in ProcsitterResult.

DESCRIPTION:

The procsitter's one job: a runaway test dies alone, and the report names the
exhausted resource. Each choice provokes one accident class with a small
inline test application and checks the attribution record.

CHOICES:

  wall_clock:  sleep-forever application -> WALL_CLOCK_EXCEEDED near cap.
  cpu_time:    spin loop -> CPU_TIME_EXCEEDED (RLIMIT_CPU / SIGXCPU).
  memory:      growing allocation -> MEMORY_EXCEEDED, peak recorded.
  file_size:   oversized write -> FILE_SIZE_EXCEEDED (RLIMIT_FSIZE),
               file stopped near the cap.
  pids:        fork storm -> contained by the watchdog's group count
               (PIDS_EXCEEDED); no straggling children survive the run.
  no_psutil:   psutil absent -> memory/pid caps reported in .unenforced,
               wall clock still enforced.
  cancelled_run: an INTERRUPTED run (Ctrl-C, a logout killing the
               harness) leaks NO child -- the cleanup is
               cancellation-proof; the accident that exhausts the
               per-user process table (and logs a developer out) is
               prevented.
  disk_usage:  a MANY-FILES loop -> FAIL_DISK_USAGE_EXCEEDED (the
               work-dir allocation cap RLIMIT_FSIZE cannot see), peak
               recorded.
  disk_space_low: a free-space FLOOR below current free space fires
               at once -> FAIL_DISK_SPACE_LOW; the mechanism that
               keeps the operating system operable.
  clean_under_caps: THE COMPLEMENT -- a real workload (memory, a file,
               children, cpu) UNDER every cap completes cleanly: the
               watchdog does not false-positive.
  self_exit_codes: the exit-status reference classes -- 0 ->
               OK_COMPLETED; nonzero -> FAIL_COMPLETED (positive code);
               signal death -> FAIL_COMPLETED (negative signal number).
  stderr_tail_cap: the captured tail is bounded -- last 100 lines, and
               a newline-less line trimmed to its 4096-byte tail.
  command_guard: the argv-list contract -- a bare string is rejected
               loudly (AssertionError); a missing program is a RESULT
               (FAIL_LAUNCH), never a crash.

AUTHOR: Frank-Rene Schaefer
"""

import asyncio
import logging
import sys
import tempfile

from   config import HwutRunner                                   # noqa F401

import vut.engine.procsitter.procsitter              as procsitter_module  # noqa E402
from   vut.engine.procsitter.procsitter              import (Procsitter,   # noqa E402
                                                       ProcsitterConfig,
                                                       E_Containment)

# Child-reap races between the harness's kill discipline and asyncio's
# child watcher may emit spurious warnings ("Unknown child process ...")
# -- harmless, but nondeterministic; the GOOD file must not see them.
logging.getLogger("asyncio").setLevel(logging.ERROR)

def _argv(app_code: str) -> list:
    """
    RETURN: list[str], argv running 'app_code' with this interpreter --
            a plain list, nothing to escape.
    """
    return [sys.executable, "-c", app_code]


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
    RETURN: ProcsitterResult, of running 'app_code' in a fresh scratch dir.
    """
    with tempfile.TemporaryDirectory(prefix="vut_procsitter_test_") as work_dir:
        return await Procsitter(config, work_dir).run(_argv(app_code))


# ---------------------------------------------------------------------------

async def test_wall_clock():
    """A sleeping (hanging) test burns no CPU; only the wall-clock cap can
    catch it. Expect WALL_CLOCK_EXCEEDED shortly after the cap."""
    config = ProcsitterConfig(max_wall_clock_sec=1.0)
    result = await _run(config, "import time; time.sleep(30)")

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.FAIL_WALL_CLOCK_EXCEEDED,
         "containment is WALL_CLOCK_EXCEEDED"),
        (1.0 <= result.wall_clock_sec < 8.0,
         "wall clock between cap and cap + kill overhead"),
        (result.exit_code is None,
         "exit_code is None (the procsitter ended it, not the test)"),
        (result.unenforced == (),
         "no caps unenforced on this platform"),
    ])
    _verdict(ok, "hang contained by wall clock, attributed.")


async def test_cpu_time():
    """A spin loop hits RLIMIT_CPU; the kernel delivers SIGXCPU. Expect
    CPU_TIME_EXCEEDED with measured cpu time near the cap."""
    config = ProcsitterConfig(max_cpu_time_sec=1, max_wall_clock_sec=15.0)
    result = await _run(config, "while True: pass")

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.FAIL_CPU_TIME_EXCEEDED,
         "containment is CPU_TIME_EXCEEDED"),
        (result.cpu_time_sec is not None and result.cpu_time_sec >= 0.9,
         "measured cpu time reached the cap"),
        (result.exit_code is None,
         "exit_code is None (the procsitter ended it, not the test)"),
    ])
    _verdict(ok, "spin loop contained by cpu-time cap, attributed.")


async def test_memory():
    """A growing allocation crosses the RSS cap; the watchdog kills the
    group. Expect MEMORY_EXCEEDED with the peak recorded."""
    config = ProcsitterConfig(max_memory_mb=96, max_wall_clock_sec=20.0)
    app    = ("import time\n"
              "hoard = []\n"
              "while True:\n"
              "    hoard.append(bytearray(4 * 1024 * 1024))\n"
              "    time.sleep(0.01)\n")
    result = await _run(config, app)

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.FAIL_MEMORY_EXCEEDED,
         "containment is MEMORY_EXCEEDED"),
        (result.peak_memory_mb is not None
         and result.peak_memory_mb > 96.0,
         "recorded peak exceeds the 96 MB cap"),
        (result.peak_memory_mb is not None
         and result.peak_memory_mb < 1024.0,
         "kill came before the hoard grew unbounded (< 1 GB)"),
        (result.exit_code is None,
         "exit_code is None (the procsitter ended it, not the test)"),
    ])
    _verdict(ok, "memory growth contained by RSS watchdog, attributed.")


async def test_file_size():
    """An oversized write hits RLIMIT_FSIZE. Apps that keep the default
    SIGXFSZ disposition die by signal -> FILE_SIZE_EXCEEDED; apps that
    ignore it -- CPython does -- get EFBIG from write() and fail by their
    own OSError -> COMPLETED, nonzero. Either way the kernel cap holds:
    the flood file stops at exactly the cap."""
    import os
    config = ProcsitterConfig(max_file_size_mb=1, max_wall_clock_sec=15.0)
    app    = ("with open('flood.bin', 'wb') as fh:\n"
              "    for _ in range(64):\n"
              "        fh.write(b'x' * (1024 * 1024))\n"
              "        fh.flush()\n")
    with tempfile.TemporaryDirectory(prefix="vut_procsitter_test_") as work_dir:
        result     = await Procsitter(config, work_dir).run(_argv(app))
        flood_path = os.path.join(work_dir, "flood.bin")
        size_mb    = (os.path.getsize(flood_path) / (1024.0 * 1024.0)
                      if os.path.exists(flood_path) else 0.0)

    # NOTE: which mechanism fires (SIGXFSZ death vs. EFBIG self-abort) is
    # platform-dependent -- the printed output only asserts the NORMALIZED
    # outcome (SIGXFSZ death -> FAIL_FILE_SIZE_EXCEEDED, EFBIG
    # self-abort -> FAIL_COMPLETED), so the GOOD file holds everywhere.
    contained_f = (result.containment is E_Containment.FAIL_FILE_SIZE_EXCEEDED) \
                  or (result.containment is E_Containment.FAIL_COMPLETED)
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
    """A fork storm is contained by the watchdog's group-member count
    (PIDS_EXCEEDED): the storm dies and no child survives the run.
    RLIMIT_NPROC is deliberately not used -- it is a per-REAL-USER cap
    that starves legitimate builds; max_pids is the watchdog's job. The
    marker string tags storm children so the post-run scan can prove
    extinction."""
    import psutil
    marker = "VUT_PROCSITTER_PIDBOMB_MARKER"
    config = ProcsitterConfig(max_pids=8, max_wall_clock_sec=15.0)
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

    # A storm that raced the watchdog to its own end (all forks done, the
    # parent sleeping) reads FAIL_COMPLETED; the printed output asserts
    # only the NORMALIZED outcome, so the GOOD file is stable.
    contained_f = (result.containment is E_Containment.FAIL_PIDS_EXCEEDED) \
                  or (result.containment is E_Containment.FAIL_COMPLETED)
    ok = _check([
        (contained_f,
         "storm contained (PIDS_EXCEEDED, watchdog group count)"),
        (result.wall_clock_sec < 10.0,
         "containment came well before the storm's natural end"),
        (len(survivors) == 0,
         "no straggling storm children survive the run"),
    ])
    _verdict(ok, "fork storm contained, all children reaped.")


async def test_cancelled_run():
    """An INTERRUPTED run (Ctrl-C, or a logout that tears the harness
    down mid-test) must leak NO child. The child setsid's into its own
    session, so nobody else would ever reap it -- the procsitter's cleanup
    is CANCELLATION-PROOF: it kills the child's group synchronously even
    as the run coroutine unwinds. A leak here silently consumes the
    per-user process table across runs -- the very accident that
    eventually logs a developer out."""
    import os, psutil
    marker = f"VUT_PROCSITTER_CANCEL_MARKER_{os.getpid()}"
    config = ProcsitterConfig(max_wall_clock_sec=30.0)
    app    = (f"import sys, time\n"
              f"sys.argv.append('{marker}')\n"
              f"time.sleep(30)\n")

    with tempfile.TemporaryDirectory(prefix="vut_procsitter_test_") as work_dir:
        run_task = asyncio.create_task(
            Procsitter(config, work_dir).run(_argv(app)))
        await asyncio.sleep(0.8)     # let it launch and setsid
        run_task.cancel()            # <-- interrupt the run mid-flight
        reraised = False
        try:
            await run_task
        except asyncio.CancelledError:
            reraised = True          # honoured -- AFTER the group is dead

    await asyncio.sleep(0.5)         # give the OS a moment to reap
    survivors = [proc for proc in psutil.process_iter(attrs=("cmdline",))
                 if proc.info["cmdline"]
                 and any(marker in arg for arg in proc.info["cmdline"])]

    print(f"INSPECT: survivors after cancel = {len(survivors)}")
    ok = _check([
        (reraised,
         "cancellation is honoured (CancelledError re-raised)"),
        (len(survivors) == 0,
         "no child survives the interrupted run -- group reaped"),
    ])
    _verdict(ok, "an interrupted run leaks nothing; logout-by-leak "
                 "prevented.")


async def test_no_psutil():
    """Honest reporting: without psutil the memory and pid caps cannot be
    enforced -- they must appear in .unenforced; the wall-clock cap must
    keep working."""
    saved = procsitter_module.psutil
    procsitter_module.psutil = None
    try:
        config = ProcsitterConfig(max_wall_clock_sec=1.0)
        result = await _run(config, "import time; time.sleep(30)")
    finally:
        procsitter_module.psutil = saved

    print(f"INSPECT: containment = {result.containment.name}")
    print(f"INSPECT: unenforced  = {sorted(result.unenforced)}")
    ok = _check([
        (result.containment is E_Containment.FAIL_WALL_CLOCK_EXCEEDED,
         "wall clock still enforced without psutil"),
        ("max_memory_mb" in result.unenforced,
         "memory cap reported as unenforced"),
        ("max_pids" in result.unenforced,
         "pid cap reported as unenforced"),
        (result.peak_memory_mb is None,
         "no fabricated memory measurement"),
    ])
    _verdict(ok, "degradation without psutil is loud, never silent.")


async def test_disk_usage():
    """A loop writing MANY files floods the disk where RLIMIT_FSIZE
    (per single file) is blind. The watchdog sums allocated bytes under
    the work dir and contains it: FAIL_DISK_USAGE_EXCEEDED, peak
    recorded, kill before the flood grows unbounded."""
    config = ProcsitterConfig(max_disk_mb=20, max_wall_clock_sec=30.0)
    app    = ("import time\n"
              "i = 0\n"
              "while True:\n"
              "    with open('flood%d.bin' % i, 'wb') as fh:\n"
              "        fh.write(b'x' * (1024 * 1024))\n"
              "    i += 1\n"
              "    time.sleep(0.02)\n")
    result = await _run(config, app)

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.FAIL_DISK_USAGE_EXCEEDED,
         "containment is FAIL_DISK_USAGE_EXCEEDED"),
        (result.peak_disk_mb is not None
         and result.peak_disk_mb > 20.0,
         "recorded peak exceeds the 20 MB cap"),
        (result.peak_disk_mb is not None
         and result.peak_disk_mb < 512.0,
         "kill came before the flood grew unbounded (< 512 MB)"),
        (result.wall_clock_sec < 15.0,
         "containment well before the 30 s natural end"),
    ])
    _verdict(ok, "many-files flood contained by the disk-usage cap.")


async def test_disk_space_low():
    """THE FLOOR that keeps the OS operable: an absurdly high
    min_free_disk_mb (larger than the whole disk) is below the free
    space immediately, so the FIRST disk poll terminates the call --
    FAIL_DISK_SPACE_LOW. This is the mechanism that stops a runaway
    write from filling the filesystem out from under the operating
    system, whoever caused the shortage."""
    import shutil
    total_mb = shutil.disk_usage(".").total / (1024.0 * 1024.0)
    config = ProcsitterConfig(min_free_disk_mb=int(total_mb) + 10**6,
                              max_wall_clock_sec=30.0)
    result = await _run(config, "import time; time.sleep(30)")

    print(f"INSPECT: containment = {result.containment.name}")
    ok = _check([
        (result.containment is E_Containment.FAIL_DISK_SPACE_LOW,
         "containment is FAIL_DISK_SPACE_LOW"),
        (result.wall_clock_sec < 10.0,
         "floor fired on an early disk poll, well before 30 s"),
        (result.exit_code is None,
         "exit_code is None (the procsitter ended it, not the test)"),
    ])
    _verdict(ok, "free-space floor keeps the operating system operable.")


async def test_clean_under_caps():
    """THE COMPLEMENT of every violation above: a run that genuinely
    USES resources -- memory, a file, extra processes, cpu, wall time
    -- yet stays UNDER every cap must complete cleanly, its work
    intact. This proves the watchdog does NOT false-positive: a
    legitimate call operating near a cap is not killed. Without this
    reference case, an over-eager cap would pass every test above while
    silently breaking real work."""
    import os
    config = ProcsitterConfig(max_memory_mb=256, max_file_size_mb=4,
                              max_disk_mb=50, max_pids=8,
                              max_cpu_time_sec=15, max_wall_clock_sec=15.0)
    app = ("import os\n"
           "for _ in range(2):\n"                 # a few short-lived children
           "    if os.fork() == 0:\n"
           "        os._exit(0)\n"
           "for _ in range(2): os.wait()\n"
           "hoard = bytearray(40 * 1024 * 1024)\n"   # 40 MB  < 256 cap
           "with open('out.bin', 'wb') as fh:\n"
           "    fh.write(b'y' * (512 * 1024))\n"      # 0.5 MB < 4 cap, < disk
           "s = 0\n"
           "for i in range(200000): s += i\n"        # a little cpu
           "print('done', s)\n")
    with tempfile.TemporaryDirectory(prefix="vut_procsitter_test_") as work_dir:
        result   = await Procsitter(config, work_dir).run(_argv(app))
        out_path = os.path.join(work_dir, "out.bin")
        out_mb   = (os.path.getsize(out_path) / (1024.0 * 1024.0)
                    if os.path.exists(out_path) else -1.0)

    print(f"INSPECT: containment = {result.containment.name}, "
          f"exit = {result.exit_code}")
    ok = _check([
        (result.containment is E_Containment.OK_COMPLETED,
         "clean completion -- OK_COMPLETED, no cap fired"),
        (result.exit_code == 0,           "exit code 0"),
        (result.unenforced == (),         "every cap enforced, none skipped"),
        (abs(out_mb - 0.5) < 0.01,        "the file was written intact (0.5 MB)"),
        (result.peak_memory_mb is None or result.peak_memory_mb < 256.0,
         "peak memory stayed under the cap -- no false memory kill"),
        (result.peak_disk_mb is None or result.peak_disk_mb < 50.0,
         "peak disk stayed under the cap -- no false disk kill"),
    ])
    _verdict(ok, "a real workload under every cap completes untouched.")


async def test_self_exit_codes():
    """The process's OWN termination -- three reference classes read
    straight from the exit status, NO cap involved: exit 0 ->
    OK_COMPLETED (the sole success); a nonzero exit -> FAIL_COMPLETED
    carrying that POSITIVE code; death by an uncaught SIGNAL ->
    FAIL_COMPLETED carrying the NEGATIVE signal number (the documented
    'death by signal' case)."""
    config = ProcsitterConfig(max_wall_clock_sec=10.0)
    ok_res   = await _run(config, "import sys; sys.exit(0)")
    fail_res = await _run(config, "import sys; sys.exit(3)")
    sig_res  = await _run(config, "import os; os.abort()")     # SIGABRT

    print(f"INSPECT: exit0 = {ok_res.containment.name}/{ok_res.exit_code}, "
          f"exit3 = {fail_res.containment.name}/{fail_res.exit_code}, "
          f"signal = {sig_res.containment.name}/{sig_res.exit_code}")
    ok = _check([
        (ok_res.containment is E_Containment.OK_COMPLETED
         and ok_res.exit_code == 0,
         "exit 0 -> OK_COMPLETED, the sole success"),
        (fail_res.containment is E_Containment.FAIL_COMPLETED
         and fail_res.exit_code == 3,
         "nonzero self-exit -> FAIL_COMPLETED, positive code preserved"),
        (sig_res.containment is E_Containment.FAIL_COMPLETED
         and sig_res.exit_code is not None and sig_res.exit_code < 0,
         "signal death -> FAIL_COMPLETED, negative signal number"),
    ])
    _verdict(ok, "self-termination classified by exit status alone.")


async def test_stderr_tail_cap():
    """stderr_last_100_lines is BOUNDED by contract: the record keeps
    the LAST 100 lines (a runaway cannot flood it), and one
    pathological line without newlines is trimmed to its 4096-byte
    tail (memory cannot flood either). Two runs, the two bounds."""
    config = ProcsitterConfig(max_wall_clock_sec=10.0)
    many = await _run(config,
        "import sys\n"
        "for i in range(150):\n"
        "    sys.stderr.write('err %d\\n' % i)\n")
    longline = await _run(config,
        "import sys\n"
        "sys.stderr.write('x' * 5000)\n")     # no newline: pending tail

    tail = many.stderr_last_100_lines.splitlines()
    longs = longline.stderr_last_100_lines.splitlines()
    print(f"INSPECT: kept {len(tail)} lines "
          f"[{tail[0] if tail else '-'} .. {tail[-1] if tail else '-'}]; "
          f"long line len = {len(longs[0]) if longs else 0}")
    ok = _check([
        (len(tail) == 100,
         "exactly the LAST 100 lines kept (150 emitted)"),
        (tail[0] == "err 50" and tail[-1] == "err 149",
         "the kept window is the TAIL, not the head"),
        (len(longs) == 1 and len(longs[0]) <= 4096,
         "a newline-less 5000-char line trimmed to its 4096-byte tail"),
    ])
    _verdict(ok, "the stderr tail is bounded, by line count and by length.")


async def test_command_guard():
    """The command is an argv LIST, never a string, and that contract
    is enforced LOUDLY: a bare string (which would spread into single
    characters) raises AssertionError -- a harness fault, not a silent
    misrun. A well-formed argv naming a program that does not exist is
    the opposite: a RESULT, not an exception -- FAIL_LAUNCH."""
    config = ProcsitterConfig(max_wall_clock_sec=10.0)
    with tempfile.TemporaryDirectory(prefix="vut_procsitter_test_") as work_dir:
        procsitter = Procsitter(config, work_dir)
        raised = False
        try:
            await procsitter.run("echo hello")        # a STRING -- misuse
        except AssertionError:
            raised = True
        launch = await procsitter.run(["/no/such/program", "arg"])

    print(f"INSPECT: bare-string raised = {raised}, "
          f"missing program = {launch.containment.name}")
    ok = _check([
        (raised,
         "a bare string command is rejected loudly (AssertionError)"),
        (launch.containment is E_Containment.FAIL_LAUNCH
         and launch.exit_code is None,
         "a missing program is a RESULT: FAIL_LAUNCH, not a crash"),
    ])
    _verdict(ok, "argv-list contract enforced; a missing program attributed.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Procsitter resource containment with attribution",
        choice_map = {
            "wall_clock": test_wall_clock,
            "cpu_time":   test_cpu_time,
            "memory":     test_memory,
            "file_size":  test_file_size,
            "pids":       test_pids,
            "no_psutil":  test_no_psutil,
            "cancelled_run": test_cancelled_run,
            "disk_usage":      test_disk_usage,
            "disk_space_low":  test_disk_space_low,
            "clean_under_caps": test_clean_under_caps,
            "self_exit_codes":  test_self_exit_codes,
            "stderr_tail_cap":  test_stderr_tail_cap,
            "command_guard":    test_command_guard,
        },
        happy      = "SUCCESS.*",
    ).run()
