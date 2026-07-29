#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE STORE: RECORDS, FOOTPRINTS, AND THE DIRECTORY LOCK.

    UNIT     'Store' + 'DirectoryLock' + the Nominal kinds -- every
             artifact of a test, behind one interface.

    CAUSAL CONTRACT
             a key names a record; acceptance PROMOTES a candidate to a
             nominal; a footprint is OVERWRITTEN, never appended; the
             lock admits one live holder and breaks for a dead one.

    CONSISTENCY CONTRACT
             the two key spaces have one writer each; a footprint write
             leaves every other entry untouched; a lock whose holder is
             ALIVE is never broken, however long it is held.

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

from   vut.engine.test_run.nominal import (BytesNominal,         # noqa E402
                                           StreamNominal,
                                           NominalNotAvailable)
from   vut.engine.test_run.store   import (Store,                # noqa E402
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
    """RETURN: (Store, str), a store over a fresh temporary directory."""
    directory = tempfile.mkdtemp(prefix="vut_store_")
    return Store(directory), directory


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
        (with_choice.name == "parse--basic.stdout",
         "the choice is part of the key, so choices never collide"),
        (no_choice.name == "parse.stdout",
         "a test without choices carries no choice part"),
        (with_choice.parent.name == "GOOD" and candidate.parent.name == "OUT",
         "nominals and candidates live in SEPARATE key spaces"),
    ])
    _verdict(ok, "one key per (test, choice, subject); two spaces.")


def test_promotion():
    """Acceptance is the only way a nominal comes to exist: it PROMOTES a
    candidate. Before it, reading the nominal reports absence."""
    store, _ = _store()
    nominal  = store.nominal("parse", "basic", "stdout")
    before   = nominal.exists()
    store.write_candidate("parse", "basic", "stdout", "one\ntwo\n")
    still    = nominal.exists()
    store.accept("parse", "basic", "stdout", "one\ntwo\n")
    after    = nominal.exists()

    print("INSPECT: nominal before anything      = %s" % before)
    print("         after a CANDIDATE is written = %s" % still)
    print("         after ACCEPT                 = %s" % after)
    print("         content = %r" % nominal.open().read())
    ok = _check([
        (before is False,
         "an unaccepted key has no nominal"),
        (still is False,
         "writing a candidate does NOT create a nominal"),
        (after is True,
         "acceptance promotes it"),
    ])
    _verdict(ok, "acceptance is the only writer of a nominal.")


def test_footprint_overwrites():
    """A footprint is the state NOW, not a history: one entry per (test,
    choice, operation), overwritten, every other entry untouched."""
    store, _ = _store()
    store.write_footprint("parse", "basic", "Run", verdict=True, report="ok")
    store.write_footprint("parse", "basic", "Accept")
    store.write_footprint("other", None, "Run", verdict=False,
                          report="build-failed")
    first = store.footprint("parse", "basic", "Run")["report"]
    store.write_footprint("parse", "basic", "Run", verdict=False,
                          report="not-equivalent-with-nominal")
    second = store.footprint("parse", "basic", "Run")

    content = store.footprints()
    print("INSPECT: tests recorded = %s" % sorted(content))
    print("         Run report was '%s', now '%s'" % (first, second["report"]))
    print("         entry keys = %s" % sorted(second))
    ok = _check([
        (second["report"] == "not-equivalent-with-nominal",
         "the second write REPLACED the first"),
        (len(content["parse"]["basic"]) == 2,
         "one entry per operation -- Run and Accept, not four"),
        (store.footprint("parse", "basic", "Accept") is not None,
         "a sibling operation is untouched"),
        (content["other"]["<none>"]["Run"]["report"] == "build-failed",
         "another test in the same file is untouched"),
        ("when" in second and "host" in second,
         "'when' and 'host' are added by the store, not by the caller"),
    ])
    _verdict(ok, "state now, never a log -- and no entry disturbs another.")


def test_footprint_survives_damage():
    """A footprint is a convenience. Its loss must never fail a run, so a
    damaged file reads as empty rather than raising."""
    store, _ = _store()
    store.write_footprint("parse", "basic", "Run", verdict=True)
    with open(store.footprint_path, "w") as fh:
        fh.write("{ this is not json")
    damaged = store.footprints()
    store.write_footprint("parse", "basic", "Run", verdict=False)
    after = store.footprint("parse", "basic", "Run")

    print("INSPECT: damaged file reads as %r" % damaged)
    print("         a later write recovers: verdict = %s" % after["verdict"])
    ok = _check([
        (damaged == {},
         "a damaged footprint file reads as empty, it does not raise"),
        (after is not None and after["verdict"] is False,
         "writing recovers the file"),
    ])
    _verdict(ok, "a lost footprint never fails a run.")


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
        title      = "The store: records, footprints, and the directory lock",
        choice_map = {
            "keys":              test_keys,
            "promotion":         test_promotion,
            "footprint_write":   test_footprint_overwrites,
            "footprint_damage":  test_footprint_survives_damage,
            "lock_live":         test_lock_live_holder,
            "lock_dead":         test_lock_dead_holder,
            "nominal_kinds":     test_nominal_kinds,
        },
        happy      = "SUCCESS.*",
    ).run()
