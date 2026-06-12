#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test - the spawner end-to-end (spawner.py).

Exercises the four spawn_* entry points against real execution
contexts: an asyncio Task, a worker thread, and a child process. Each
choice spawns a child, drives it to a terminal state, and prints the
E_ChildState progression.

CHOICES
    async_complete    spawn_async: child finishes on its own -> TERM_OK.
    async_terminate   spawn_async: cooperative child + .terminate()
                      -> TERM_OK.
    async_kill        spawn_async: stubborn child + .terminate() with a
                      numeric deadline -> TERM_FAILURE.
    thread_complete   spawn_thread: child finishes on its own -> TERM_OK.
    thread_refusal    spawn_thread: .terminate() with a numeric deadline
                      is REFUSED (DISCUSSION.txt D9) - returns False.
    process_complete  spawn_process: child process finishes -> TERM_OK.
    process_kill      spawn_process: child process killed externally,
                      watchdog resolves -> TERM_FAILURE.

DETERMINISM
    Most output is deterministic (E_ChildState names, bool returns). The
    process choices print the child PID, which varies every run - those
    lines have the fixed prefix 'child pid:' and are matched by a HAPPY
    pattern (see the 'happy' argument of HwutRunner below), so HWUT
    accepts the varying number without a GOOD-file mismatch.

THE __main__ GUARD
    spawn_process uses the multiprocessing 'spawn' start method, which
    re-imports this module in the child interpreter. The HwutRunner call
    is under 'if __name__ == "__main__":', so the child import does NOT
    re-run the test - without that guard the child would recurse.
________________________________________________________________________________
"""
import sys
import asyncio

from config import HwutRunner

from vut.engine.spawner        import (spawn_async, spawn_thread,
                                       spawn_process, E_ChildState)


# ----------------------------------------------------------------------
# Child callables
#   Defined at module level so the 'spawn' start method can pickle /
#   re-import them in the child process.
# ----------------------------------------------------------------------

async def child_complete(term, *args):
    """RETURN: str, a fixed marker.  An async child that finishes at once."""
    return "completed"


async def child_cooperative(term, *args):
    """RETURN: str, a fixed marker.

    An async child that waits for a termination request, then winds
    down cleanly. set_termination_callback() releases the wait when
    EventChildTerminationReq arrives.
    """
    done = asyncio.Event()
    term.set_termination_callback(lambda ev: done.set())
    await done.wait()
    return "wound-down"


async def child_stubborn(term, *args):
    """RETURN: never returns within the test window.

    An async child that ignores termination entirely - it never checks
    for a request. Used to force the deadline-kill path.
    """
    await asyncio.sleep(30)
    return "unreachable"


def child_process_complete(term, *args):
    """RETURN: str, a fixed marker.  A process child that finishes at once."""
    return "process-completed"


def child_process_long(term, *args):
    """RETURN: never returns within the test window.

    A process child that sleeps far longer than the test - used so the
    test can kill it externally and observe the watchdog verdict.
    """
    import time
    time.sleep(30)
    return "unreachable"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

async def _settle_to_terminal(parent, timeout_s=5.0):
    """RETURN: E_ChildState, the terminal state the child reached,
                           or the last live state if 'timeout_s' elapsed.

    Polls the child state until it is terminal or the timeout expires.
    Keeps the tests robust without printing any timing.
    """
    waited = 0.0
    step   = 0.05
    while waited < timeout_s:
        if parent.child_state().is_terminal():
            break
        await asyncio.sleep(step)
        waited += step
    return parent.child_state()


async def _teardown(parent):
    """RETURN: None.

    Releases everything a spawn_* call created, so the test process can
    exit promptly. Three steps:

      1. stop the parent terminal (closes the channel),
      2. for a process child, join the OS process to reap it,
      3. for a process child, abandon the multiprocessing.Queue feeder
         threads.

    Step 3 matters after an EXTERNAL kill. A multiprocessing.Queue runs
    a background QueueFeederThread; when the consumer process is killed,
    that thread blocks forever trying to flush, and - being non-daemon -
    holds the interpreter open at exit even after asyncio.run() returns.
    cancel_join_thread() on each queue releases it. Without this the
    test can hang at shutdown.
    """
    try:
        await asyncio.wait_for(parent.stop(), timeout=3.0)
    except asyncio.TimeoutError:
        print("  (teardown: parent.stop() timed out)")
    except Exception:
        pass

    spawner = getattr(parent, "_spawner", None)
    handle  = getattr(spawner, "_handle", None) if spawner else None
    proc    = getattr(handle, "_process", None) if handle else None
    if proc is not None:
        try:
            proc.join(timeout=3.0)
        except Exception:
            pass

    # Abandon the process channel's queue feeder threads, if any. The
    # ECP params carry the multiprocessing.Queue objects.
    ecp = getattr(parent, "_ecp", None)
    if ecp is not None and getattr(ecp, "params", None):
        for key in ("in_q", "out_q"):
            q = ecp.params.get(key)
            cancel = getattr(q, "cancel_join_thread", None)
            if cancel is not None:
                try:
                    cancel()
                except Exception:
                    pass


# ----------------------------------------------------------------------
# Choices - async
# ----------------------------------------------------------------------

async def run_async_complete():
    """RETURN: None.

    spawn_async with a child that returns immediately. The spawn yields
    a parent terminal; the child confirms its own completion and the
    FSM settles in TERM_OK.
    """
    print("--- spawn_async: self-completing child ---")
    parent = await spawn_async(child_complete, ())
    print("  spawn returned a terminal: %s" % (parent is not None))
    assert parent is not None
    state = await _settle_to_terminal(parent)
    print("  terminal state: %s" % state)
    assert state is E_ChildState.TERM_OK
    await _teardown(parent)


async def run_async_terminate():
    """RETURN: None.

    spawn_async with a cooperative child, terminated via
    .terminate(None). The child observes the request, winds down, and
    confirms -> TERM_OK.
    """
    print("--- spawn_async: cooperative child + terminate(None) ---")
    parent = await spawn_async(child_cooperative, ())
    assert parent is not None
    print("  state before terminate: %s" % parent.child_state())

    ok = await parent.terminate(wait_to_kill_ms=None)
    print("  terminate(None) returned: %s" % ok)
    assert ok is True

    state = await _settle_to_terminal(parent)
    print("  terminal state: %s" % state)
    assert state is E_ChildState.TERM_OK
    await _teardown(parent)


async def run_async_kill():
    """RETURN: None.

    spawn_async with a stubborn child that never confirms.
    .terminate(100) gives a 100ms grace; the deadline elapses, the Task
    is cancelled, and the FSM lands in TERM_FAILURE (DISCUSSION.txt D7:
    freed without confirmation).
    """
    print("--- spawn_async: stubborn child + terminate(100) ---")
    parent = await spawn_async(child_stubborn, ())
    assert parent is not None
    print("  state before terminate: %s" % parent.child_state())

    ok = await parent.terminate(wait_to_kill_ms=100)
    print("  terminate(100) returned: %s" % ok)
    assert ok is True

    state = await _settle_to_terminal(parent)
    print("  terminal state: %s" % state)
    assert state is E_ChildState.TERM_FAILURE
    await _teardown(parent)


# ----------------------------------------------------------------------
# Choices - thread
# ----------------------------------------------------------------------

async def run_thread_complete():
    """RETURN: None.

    spawn_thread with a self-completing child. The child runs on a
    worker thread, finishes, confirms, and the FSM settles in TERM_OK.
    """
    print("--- spawn_thread: self-completing child ---")
    parent = await spawn_thread(child_complete, ())
    print("  spawn returned a terminal: %s" % (parent is not None))
    assert parent is not None
    state = await _settle_to_terminal(parent)
    print("  terminal state: %s" % state)
    assert state is E_ChildState.TERM_OK
    await _teardown(parent)


async def run_thread_refusal():
    """RETURN: None.

    spawn_thread, then .terminate() with a NUMERIC deadline. A thread
    has no force-kill path, so a numeric wait_to_kill_ms is refused -
    .terminate() returns False (DISCUSSION.txt D9). A None deadline is
    accepted.
    """
    print("--- spawn_thread: numeric deadline is refused (D9) ---")
    parent = await spawn_thread(child_cooperative, ())
    assert parent is not None

    refused = await parent.terminate(wait_to_kill_ms=500)
    print("  terminate(500) returned: %s   (expect False)" % refused)
    assert refused is False

    accepted = await parent.terminate(wait_to_kill_ms=None)
    print("  terminate(None) returned: %s   (expect True)" % accepted)
    assert accepted is True

    state = await _settle_to_terminal(parent)
    print("  terminal state: %s" % state)
    assert state is E_ChildState.TERM_OK
    await _teardown(parent)


# ----------------------------------------------------------------------
# Choices - process
# ----------------------------------------------------------------------

async def run_process_complete():
    """RETURN: None.

    spawn_process with a self-completing child process. The 'spawn'
    start method is used (ProcessConfig default); the child process
    runs the trampoline, the callable returns, and the FSM settles in
    TERM_OK.
    """
    print("--- spawn_process: self-completing child process ---")
    parent = await spawn_process(child_process_complete, ())
    print("  spawn returned a terminal: %s" % (parent is not None))
    assert parent is not None
    # PID varies every run - matched by the HAPPY pattern.
    pid = parent._spawner._handle._process.pid
    print("  child pid: %s" % pid)
    state = await _settle_to_terminal(parent, timeout_s=8.0)
    print("  terminal state: %s" % state)
    assert state is E_ChildState.TERM_OK
    await _teardown(parent)


async def run_process_kill():
    """RETURN: None.

    spawn_process, then kill the child process EXTERNALLY (bypassing
    .terminate()). The Spawner's watchdog polls the process handle,
    finds it DEAD with no confirmation, and resolves the FSM to
    TERM_FAILURE (DISCUSSION.txt D7/D8).
    """
    print("--- spawn_process: external kill -> TERM_FAILURE ---")
    parent = await spawn_process(child_process_long, ())
    assert parent is not None
    proc = parent._spawner._handle._process
    # PID varies every run - matched by the HAPPY pattern.
    print("  child pid: %s" % proc.pid)
    print("  state before kill: %s" % parent.child_state())

    # Kill the OS process directly - no EventChildTermination is sent.
    proc.kill()
    print("  child process killed externally")

    state = await _settle_to_terminal(parent, timeout_s=8.0)
    print("  terminal state: %s" % state)
    assert state is E_ChildState.TERM_FAILURE
    await _teardown(parent)


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Spawner end-to-end",
        choice_map = {
            "async_complete":   run_async_complete,
            "async_terminate":  run_async_terminate,
            "async_kill":       run_async_kill,
            "thread_complete":  run_thread_complete,
            "thread_refusal":   run_thread_refusal,
            "process_complete": run_process_complete,
            "process_kill":     run_process_kill,
        },
        # The 'child pid:' lines carry a run-varying number; this HAPPY
        # pattern tells HWUT such lines may differ from the GOOD file.
        happy      = r"child pid: [0-9]+",
    ).run()
