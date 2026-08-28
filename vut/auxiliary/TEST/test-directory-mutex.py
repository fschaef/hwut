#! /usr/bin/env python3
#
# @hwut {
#     title      = "The directory mutex: one live holder, asked liveness, named refusals"
#     choices    = ["age", "dead", "foreign", "hold_timeout", "reentry",
#                   "taken", "waiting"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The auxiliary directory mutex -- mutual exclusion over one
         directory, between processes.

CHOICES: taken, reentry, foreign, dead, waiting, hold_timeout, age;

DESCRIPTION:

taken         acquisition of a free directory: 'mkdir' wins, the holder is
              recorded as this process, release removes every trace.

reentry       the mutex is NON-RECURSIVE: the live holder acquiring again
              is refused by name -- 'DirectoryDeadlock', a 'DirectoryBusy'.

foreign       a lock whose holder is a DIFFERENT live process stands:
              'acquire()' answers False, 'with' raises 'DirectoryBusy',
              and the holder's lock survives both.

dead          a lock whose recorded holder is GONE is broken and re-taken;
              liveness is asked, never inferred from elapsed time.

waiting       'wait_sec' polls a foreign live holder before reporting
              busy; the holder outliving the wait is still refused.

hold_timeout  'max_hold_sec' treats a LIVE holder held longer than
              allowed as gone; the same holder within its allowance, or
              under the default 'None', stands.

age           'holder_age_sec' answers how long the lock has been held;
              a holder record without an acquisition time answers None --
              absence is data, never zero.
______________________________________________________________________________
"""
import os
import sys
import json
import time
import tempfile
import subprocess
import config                                                       # noqa: F401

from   vut.language_support.python.hwut_runner import HwutRunner    # noqa: E402
from   vut.auxiliary.directory_mutex           import (             # noqa: E402
                                               MkdirMutex,
                                               DirectoryBusy,
                                               DirectoryDeadlock,
                                               liveness_can_be_asked,
                                               LOCK_DIRECTORY_NAME)


def _check(pair_list):
    """
    RETURN: True,  every claim held.
            False, at least one did not.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def _directory():
    """RETURN: str, a fresh temporary directory to guard."""
    return tempfile.mkdtemp(prefix="vut_mutex_")


def _liveness_or_bail():
    """
    RETURN: True,  process start times can be asked on this platform.
            False, they cannot -- the choice reported that and is done.
    """
    if liveness_can_be_asked(): return True
    print("INSPECT: this platform cannot report process start times")
    _verdict(True, "no lock taken where liveness cannot be asked.")
    return False


def _lock_path(directory):
    """RETURN: str, where the lock sub directory of 'directory' lives."""
    return os.path.join(directory, LOCK_DIRECTORY_NAME)


def _foreign_live_holder(directory, acquired=None):
    """
    RETURN: subprocess.Popen, a live child that holds the lock of
            'directory' and sleeps until killed.

    The child writes its own (pid, started) pair; 'acquired' overrides
    the recorded acquisition time when given.
    """
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, time, json, os\n"
         "import psutil\n"
         "d = sys.argv[1]\n"
         "os.makedirs(d)\n"
         "record = {'pid': os.getpid(),\n"
         "          'started': psutil.Process().create_time(),\n"
         "          'acquired': float(sys.argv[2])}\n"
         "json.dump(record, open(os.path.join(d, 'holder.json'), 'w'))\n"
         "sys.stdout.write('ready\\n'); sys.stdout.flush()\n"
         "time.sleep(30)\n",
         _lock_path(directory),
         str(acquired if acquired is not None else time.time())],
        stdout=subprocess.PIPE, text=True)
    child.stdout.readline()                     # the lock now exists
    return child


def _dead_holder(directory, record_extra=None):
    """
    RETURN: None. Writes a lock whose recorded holder has already
            exited; 'record_extra' entries join the holder record.
    """
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()                                # dead, and its pid known
    os.makedirs(_lock_path(directory))
    record = {"pid": child.pid, "started": time.time()}
    record.update(record_extra or {})
    with open(os.path.join(_lock_path(directory), "holder.json"), "w") as fh:
        json.dump(record, fh)


def test_taken():
    """Acquisition of a free directory, and a clean release."""
    if not _liveness_or_bail(): return
    directory = _directory()
    mutex = MkdirMutex(directory)
    taken = mutex.acquire()
    holder = mutex.holder()
    print("INSPECT: acquire() -> %s, taken = %s" % (taken, mutex.taken))
    print("         the recorded holder is this process: %s"
          % (holder is not None and holder.get("pid") == os.getpid()))
    ok = _check([
        (taken is True,               "a free directory is taken"),
        (mutex.taken is True,         "and the mutex says so"),
        (os.path.isdir(_lock_path(directory)),
                                      "the lock sub directory exists"),
        (holder.get("pid") == os.getpid(),
                                      "the holder file names this process"),
        ("acquired" in holder,        "and records when it acquired"),
    ])
    mutex.release()
    ok = ok and _check([
        (not os.path.isdir(_lock_path(directory)),
                                      "release removes every trace"),
        (mutex.taken is False,        "and the mutex says so"),
    ])
    _verdict(ok, "the mutex is taken and released without residue.")


def test_reentry():
    """The mutex is non-recursive: one lock site per holder. The live
    holder acquiring again is refused BY NAME, never waited out."""
    if not _liveness_or_bail(): return
    directory = _directory()
    mutex = MkdirMutex(directory)
    mutex.acquire()
    second = MkdirMutex(directory)
    try:
        second.acquire()
        raised = "nothing"
    except DirectoryDeadlock:
        raised = "DirectoryDeadlock"
    except DirectoryBusy:
        raised = "DirectoryBusy"
    print("INSPECT: the holder acquires its own directory again")
    print("         raised = %s" % raised)
    ok = _check([
        (raised == "DirectoryDeadlock",
         "re-acquisition by the live holder raises DirectoryDeadlock"),
        (issubclass(DirectoryDeadlock, DirectoryBusy),
         "which IS a DirectoryBusy, for a caller that does not distinguish"),
        (mutex.taken is True,
         "the first acquisition still stands"),
        (os.path.isdir(_lock_path(directory)),
         "and the lock is untouched"),
    ])
    mutex.release()
    _verdict(ok, "the mutex is non-recursive, and says so by name.")


def test_foreign():
    """A lock whose holder is a DIFFERENT live process stands, however
    the contender knocks."""
    if not _liveness_or_bail(): return
    directory = _directory()
    child = _foreign_live_holder(directory)
    try:
        refused = MkdirMutex(directory).acquire()
        try:
            with MkdirMutex(directory):
                entered = True
        except DirectoryBusy:
            entered = False
        print("INSPECT: a different live process holds the lock")
        print("         acquire() -> %s, 'with' entered -> %s"
              % (refused, entered))
        ok = _check([
            (refused is False,  "acquire() answers False, it does not raise"),
            (entered is False,  "'with' raises DirectoryBusy"),
            (os.path.isdir(_lock_path(directory)),
                                "the holder's lock survives both"),
        ])
    finally:
        child.kill(); child.wait()
    _verdict(ok, "a live holder is never robbed of its lock.")


def test_dead():
    """A lock whose recorded holder is GONE is broken and re-taken. A
    crashed holder leaves no lock behind it -- there is no expiry to
    wait out."""
    if not _liveness_or_bail(): return
    directory = _directory()
    _dead_holder(directory)
    mutex = MkdirMutex(directory)
    taken = mutex.acquire()
    print("INSPECT: the recorded holder has exited")
    print("         acquire() -> %s, taken = %s" % (taken, mutex.taken))
    ok = _check([
        (taken is True,       "a lock whose holder is gone is broken and re-taken"),
        (mutex.taken is True, "and this process now holds it"),
    ])
    mutex.release()
    ok = ok and _check([
        (not os.path.isdir(_lock_path(directory)), "release removes it"),
    ])
    _verdict(ok, "a crashed holder leaves no lock behind it.")


def test_waiting():
    """'wait_sec' polls before reporting busy. A holder that outlives
    the wait is still refused -- waiting buys patience, never the lock."""
    if not _liveness_or_bail(): return
    directory = _directory()
    child = _foreign_live_holder(directory)
    try:
        mutex  = MkdirMutex(directory, wait_sec=0.3, poll_sec=0.05)
        before = time.monotonic()
        taken  = mutex.acquire()
        waited = time.monotonic() - before
        print("INSPECT: a live holder outlives the contender's wait")
        print("         acquire() -> %s, waited the full period: %s"
              % (taken, waited >= 0.3))
        ok = _check([
            (taken is False,   "the holder outliving the wait is still refused"),
            (waited >= 0.3,    "and the contender did wait before saying so"),
        ])
    finally:
        child.kill(); child.wait()
    _verdict(ok, "waiting buys patience, never the lock.")


def test_hold_timeout():
    """'max_hold_sec' treats a LIVE holder held longer than allowed as
    gone. The default None keeps the law: liveness alone decides."""
    if not _liveness_or_bail(): return

    #  One live holder, acquired long ago -- three contenders knock.
    directory = _directory()
    child = _foreign_live_holder(directory, acquired=time.time() - 100.0)
    try:
        stands   = MkdirMutex(directory).acquire()
        stands_2 = MkdirMutex(directory, max_hold_sec=1000.0).acquire()
        overdue  = MkdirMutex(directory, max_hold_sec=1.0)
        taken    = overdue.acquire()
        print("INSPECT: a live holder, acquired 100 seconds ago")
        print("         default policy        -> acquire() %s" % stands)
        print("         max_hold_sec = 1000.0 -> acquire() %s" % stands_2)
        print("         max_hold_sec = 1.0    -> acquire() %s" % taken)
        ok = _check([
            (stands is False,   "under the default, liveness alone decides"),
            (stands_2 is False, "a live holder within its allowance stands"),
            (taken is True,     "a live holder past its allowance is treated as gone"),
        ])
        overdue.release()
    finally:
        child.kill(); child.wait()
    _verdict(ok, "the hold allowance is an opt-in, not the law.")


def test_age():
    """'holder_age_sec' answers how long the lock has been held; a record
    without an acquisition time answers None -- absence is data."""
    if not _liveness_or_bail(): return

    directory = _directory()
    mutex = MkdirMutex(directory)
    print("INSPECT: no holder recorded      -> age = %s"
          % mutex.holder_age_sec())
    mutex.acquire()
    age = mutex.holder_age_sec()
    print("         this process holds      -> age is a number >= 0: %s"
          % (age is not None and age >= 0.0))
    mutex.release()

    elder = _directory()
    _dead_holder(elder)                       # a record without 'acquired'
    age_absent = MkdirMutex(elder).holder_age_sec()
    print("         a record without 'acquired' -> age = %s" % age_absent)
    ok = _check([
        (age is not None and age >= 0.0,
         "a held lock answers its age"),
        (age_absent is None,
         "a record without an acquisition time answers None, never zero"),
    ])
    _verdict(ok, "holder time is answered where recorded, absent where not.")


HwutRunner(
    argv       = sys.argv,
    title      = "The directory mutex: one live holder, asked liveness, named refusals",
    choice_map = {
        "taken":        test_taken,
        "reentry":      test_reentry,
        "foreign":      test_foreign,
        "dead":         test_dead,
        "waiting":      test_waiting,
        "hold_timeout": test_hold_timeout,
        "age":          test_age,
    },
).run()
