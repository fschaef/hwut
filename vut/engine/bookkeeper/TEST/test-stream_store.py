#! /usr/bin/env python3
#
# @hwut {
#     title      = "The store: records and the directory lock"
#     choices    = ["keys", "lock_dead", "lock_live", "nominal_kinds",
#                   "promotion"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE STORE: RECORDS AND THE DIRECTORY LOCK.

    UNIT     'Store' + 'DirectoryLock' + the Nominal kinds -- every
             artifact of a test, behind one interface. The naming is the
             Bookkeeper's; the Store asks it for every path.

    CAUSAL CONTRACT
             a key names a record; acceptance PROMOTES a candidate to a
             nominal; the lock admits one live holder and breaks for a
             dead one.

    CONSISTENCY CONTRACT
             the two key spaces have one writer each; a lock whose
             holder is ALIVE is never broken, however long it is held.

    Each choice prints the whole picture, so wrongness is visible.
______________________________________________________________________________
"""
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.nominal import (BytesNominal,         # noqa E402
                                           StreamNominal,
                                           NominalNotAvailable)
from   vut.engine.bookkeeper.bookkeeper import (    # noqa E402
                                           Bookkeeper)
from   vut.engine.bookkeeper.stream_store   import (Store,                # noqa E402
                                           DirectoryLock,
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


def _store():
    """RETURN: (Store, str), a store over a fresh temporary directory --
    OVER a Bookkeeper, which owns the naming."""
    directory = tempfile.mkdtemp(prefix="vut_store_")
    return Store(Bookkeeper(directory)), directory


def test_keys():
    """A key is (test, choice, subject). A test without choices keys by
    'None' and its records simply carry no choice part."""
    store, directory = _store()
    with_choice = store.nominal_path("parse", "basic", "stdout")
    no_choice   = store.nominal_path("parse", None, "stdout")
    candidate   = store.candidate_path("parse", "basic", "stdout")

    print("INSPECT: with choice = %s" % os.path.relpath(with_choice, directory))
    print("         no choice   = %s" % os.path.relpath(no_choice, directory))
    print("         candidate   = %s" % os.path.relpath(candidate, directory))
    ok = _check([
        (with_choice.name == "parse--basic.txt",
         "the choice is part of the key, so choices never collide"),
        (no_choice.name == "parse.txt",
         "a test without choices carries no choice part"),
        (with_choice.parent.name == "GOOD"
         and candidate.parent.name == "TMP/store",
         "nominals and candidates live in SEPARATE key spaces"),
    ])
    _verdict(ok, "one key per (test, choice, subject); two spaces.")


def test_promotion():
    """Acceptance is the only way a nominal comes to exist: it PROMOTES a
    candidate. Before it, reading the nominal reports absence."""
    store, _ = _store()
    path     = store.nominal_path("parse", "basic", "stdout")
    before   = path.exists()
    store.write_candidate("parse", "basic", "stdout", "one\ntwo\n")
    still    = path.exists()
    store.accept("parse", "basic", "stdout", "one\ntwo\n")
    after    = path.exists()

    print("INSPECT: nominal before anything      = %s" % before)
    print("         after a CANDIDATE is written = %s" % still)
    print("         after ACCEPT                 = %s" % after)
    print("         content = %r" % open(path).read())
    ok = _check([
        (before is False,
         "an unaccepted key has no nominal"),
        (still is False,
         "writing a candidate does NOT create a nominal"),
        (after is True,
         "acceptance promotes it"),
    ])
    _verdict(ok, "acceptance is the only writer of a nominal.")


def test_lock_live_holder():
    """A lock whose holder is ALIVE is never broken, however long it is
    held. Liveness is asked, not inferred from elapsed time."""
    store, directory = _store()
    if not liveness_can_be_asked():
        print("INSPECT: this platform cannot report process start times")
        _verdict(True, "no lock taken where liveness cannot be asked.")
        return

    child = subprocess.Popen([sys.executable, "-c",
                              "import sys, time, json, os\n"
                              "d = sys.argv[1]\n"
                              "os.makedirs(d)\n"
                              "import psutil\n"
                              "json.dump({'pid': os.getpid(),\n"
                              "           'started': psutil.Process().create_time()},\n"
                              "          open(os.path.join(d,'holder.json'),'w'))\n"
                              "sys.stdout.write('ready\\n'); sys.stdout.flush()\n"
                              "time.sleep(30)\n",
                              os.path.join(directory, LOCK_DIRECTORY_NAME)],
                             stdout=subprocess.PIPE, text=True)
    try:
        child.stdout.readline()                 # the lock now exists
        time.sleep(0.2)
        refused = DirectoryLock(directory).acquire()
        print("INSPECT: a live process holds the lock")
        print("         acquire() -> %s" % refused)
        ok = _check([
            (refused is False,
             "the lock is NOT taken while its holder lives"),
            (os.path.isdir(os.path.join(directory, LOCK_DIRECTORY_NAME)),
             "and it is not broken either"),
        ])
    finally:
        child.kill(); child.wait()
    _verdict(ok, "a live holder is never robbed of its lock.")


def test_lock_dead_holder():
    """A lock whose holder is GONE is broken and re-taken. A crashed run
    leaves no lock behind it -- there is no expiry to wait out."""
    store, directory = _store()
    if not liveness_can_be_asked():
        print("INSPECT: this platform cannot report process start times")
        _verdict(True, "no lock taken where liveness cannot be asked.")
        return

    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()                                # dead, and its pid known
    lock_path = os.path.join(directory, LOCK_DIRECTORY_NAME)
    os.makedirs(lock_path)
    with open(os.path.join(lock_path, "holder.json"), "w") as fh:
        json.dump({"pid": child.pid, "started": time.time()}, fh)

    lock  = DirectoryLock(directory)
    taken = lock.acquire()
    print("INSPECT: the recorded holder has exited")
    print("         acquire() -> %s, taken = %s" % (taken, lock.taken))
    ok = _check([
        (taken is True,
         "a lock whose holder is gone is broken and re-taken"),
        (lock.taken is True,
         "and this process now holds it"),
    ])
    lock.release()
    ok = ok and _check([
        (not os.path.isdir(lock_path),
         "release removes it"),
    ])
    _verdict(ok, "a crashed run leaves no lock behind it.")


def test_nominal_kinds():
    """Three kinds, one interface. They differ only in where the bytes
    come from -- and a stream, having one pass, refuses a second open
    rather than handing back an exhausted reader."""
    in_memory = BytesNominal("alpha\nbeta\n", name="<memo>")
    twice     = (in_memory.open().read(), in_memory.open().read())

    import io
    stream = StreamNominal(io.StringIO("gamma\n"), name="<pipe>")
    first  = stream.open().read()
    second = None
    try:
        stream.open()
    except NominalNotAvailable as error:
        second = str(error)

    print("INSPECT: BytesNominal read twice -> %r, %r" % twice)
    print("         StreamNominal first     -> %r" % first)
    print("         StreamNominal again     -> %s" % second)
    ok = _check([
        (twice[0] == twice[1] == "alpha\nbeta\n",
         "an in-memory nominal is re-openable"),
        (first == "gamma\n",
         "a stream nominal reads once"),
        (second is not None,
         "and REFUSES a second open, rather than comparing against nothing"),
    ])
    _verdict(ok, "one interface; a spent stream says so.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The store: records and the directory lock",
        choice_map = {
            "keys":              test_keys,
            "promotion":         test_promotion,
            "lock_live":         test_lock_live_holder,
            "lock_dead":         test_lock_dead_holder,
            "nominal_kinds":     test_nominal_kinds,
        },
        happy      = "SUCCESS.*",
    ).run()
