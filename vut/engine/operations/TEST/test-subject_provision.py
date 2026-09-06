#! /usr/bin/env python3
#
# @hwut {
#     title      = "Subject provision: the one channel"
#     choices    = ["bare", "executes", "loads", "production_false",
#                   "records", "stale"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE ONE CHANNEL -- 'subject_provision' decides, wires and records
(operations disc-2, settled 2026-09-02; services E-40).

    CAUSAL CONTRACT
             nothing recorded -> the provider EXECUTES; a current
             recording -> the provider LOADS; a recording older than
             its source -> EXECUTES again; 'production=False' never
             executes and says STALE or ABSENT beside the Loaded it
             hands back; a caller with no configuration gets a Loaded
             and never an executor.

    CONSISTENCY CONTRACT
             both providers answer 'provide()' with 'Subjects' and
             remember 'last_provided'; 'record()' writes what an
             executing provider produced and NOTHING for a Loaded one.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile
import time

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.procsitter.api              import ProcsitterConfig  # noqa E402
from   vut.engine.operations.configuration    import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   E_SourceKind)
from   vut.engine.operations.session          import store_of      # noqa E402
from   vut.engine.operations                  import subject_provision  # noqa E402
from   vut.engine.operations.subject_provision import (E_Decision,  # noqa E402
                                                       Loaded)
from   vut.engine.operations.run.core         import Provision     # noqa E402
from   vut.engine.bookkeeper.api              import (Bookkeeper,  # noqa E402
                                                      StoreConfig)


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


def _step(decision):
    """RETURN: str, the ruled step that decided, without the file it
    named -- a temporary path is no GOOD's business."""
    return decision.because.split("'")[0].strip()


def _place(body="print('one')\n"):
    """RETURN: (TestConfiguration, Store, str), a ready interpreted
    test in a fresh directory."""
    directory = tempfile.mkdtemp(prefix="vut_channel_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(body)
    configuration = TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        store          = StoreConfig(directory=directory),
        choice_db      = {None: TestChoiceConfiguration()})
    return (configuration,
            store_of(configuration, Bookkeeper(directory)),
            directory)


def _execute_and_record(configuration, store):
    """RETURN: dict, what was recorded after one execution through
    the channel."""
    provider, decision = subject_provision.provider_of(configuration,
                                                       store)
    asyncio.run(provider.provide())
    return subject_provision.record(store, configuration, None,
                                    provider), decision


def test_executes():
    """Nothing recorded: the channel hands back an executing Provision
    and (0) says why."""
    configuration, store, directory = _place()
    provider, decision = subject_provision.provider_of(configuration,
                                                       store)
    print("  decision: %s   %s" % (decision.what.value, _step(decision)))
    subjects = asyncio.run(provider.provide())
    ok = _check([
        (isinstance(provider, Provision), "an executing Provision"),
        (decision.what is E_Decision.PROVIDE, "the word is PROVIDE"),
        (decision.because.startswith("(0)"), "step (0) decided"),
        (subjects is not None and "stdout" in subjects,
         "provide() answered Subjects with stdout"),
        (provider.last_provided is subjects, "last_provided remembers"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "nothing recorded: the channel executes.")


def test_records():
    """record() writes an executing provider's product as the
    candidates, and nothing for a Loaded one."""
    configuration, store, directory = _place()
    recorded_db, _ = _execute_and_record(configuration, store)
    candidate = store.candidate_path("demo.py", None, "stdout")
    print("  recorded: %s" % sorted(recorded_db or {}))

    loaded, _ = subject_provision.provider_of(configuration, store,
                                              production=False)
    asyncio.run(loaded.provide())
    again = subject_provision.record(store, configuration, None, loaded)
    ok = _check([
        (recorded_db is not None and "stdout" in recorded_db,
         "stdout was recorded"),
        (candidate.exists(), "the candidate stands in the store"),
        (candidate.read_text().strip() == "one",
         "the candidate holds what the application printed"),
        (isinstance(loaded, Loaded), "the second provider LOADS"),
        (again is None, "a Loaded provider records nothing"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "record() writes an execution, never a read-back.")


def test_loads():
    """A current recording: a READER (production=False) gets a Loaded
    and what it provides is what was recorded; a PRODUCER, over the
    same current recording, RUNS -- the recording is what it will
    replace (ruled 2026-09-05)."""
    configuration, store, directory = _place()
    _execute_and_record(configuration, store)
    provider, decision = subject_provision.provider_of(configuration,
                                                       store,
                                                       production=False)
    print("  reader:   %s   %s" % (decision.what.value, _step(decision)))
    subjects = asyncio.run(provider.provide())
    with subjects["stdout"].open() as reader: text = reader.read()
    runner, run_decision = subject_provision.provider_of(configuration,
                                                         store)
    print("  producer: %s   %s" % (run_decision.what.value,
                                   _step(run_decision)))
    ok = _check([
        (isinstance(provider, Loaded), "a reader gets a Loaded provider"),
        (decision.what is E_Decision.RECORDED, "and the word is RECORDED"),
        (decision.because.startswith("(A.2)"), "step (A.2) decided"),
        (text.strip() == "one", "the recording is what is provided"),
        (provider.last_provided is subjects, "last_provided remembers"),
        (not isinstance(runner, Loaded),
         "a PRODUCER over the same recording does not load"),
        (run_decision.what is E_Decision.PROVIDE,
         "it RUNS: the recording is what it will replace"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a current recording is read back by a reader; a run runs.")


def test_stale():
    """The source younger than the recording: the channel executes
    again, and 'force_run' does the same over a current one."""
    configuration, store, directory = _place()
    _execute_and_record(configuration, store)
    source = os.path.join(directory, "demo.py")
    time.sleep(0.05)
    with open(source, "w") as fh: fh.write("print('two')\n")
    os.utime(source, None)
    younger, d_young = subject_provision.provider_of(configuration, store)
    print("  younger: %s   %s" % (d_young.what.value, _step(d_young)))
    asyncio.run(younger.provide())
    subject_provision.record(store, configuration, None, younger)
    forced, d_force = subject_provision.provider_of(configuration, store,
                                                    force_run=True)
    print("  forced:  %s   %s" % (d_force.what.value, _step(d_force)))
    ok = _check([
        (isinstance(younger, Provision), "a younger source executes"),
        (d_young.because.startswith("(A.1)"), "step (A.1) decided"),
        (store.candidate_path("demo.py", None, "stdout")
              .read_text().strip() == "two",
         "the new recording is the new text's"),
        (isinstance(forced, Provision), "force_run executes regardless"),
        ("forced" in d_force.because, "and says it was forced"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a changed text re-runs; a forced run runs.")


def test_production_false():
    """'production=False' never executes: ABSENT where nothing is
    recorded, STALE where the recording is old -- and a Loaded
    beside either word."""
    configuration, store, directory = _place()
    absent, d_absent = subject_provision.provider_of(configuration, store,
                                                     production=False)
    print("  absent: %s   %s" % (d_absent.what.value, _step(d_absent)))
    _execute_and_record(configuration, store)
    time.sleep(0.05)
    os.utime(os.path.join(directory, "demo.py"), None)
    stale, d_stale = subject_provision.provider_of(configuration, store,
                                                   production=False)
    print("  stale:  %s   %s" % (d_stale.what.value, _step(d_stale)))
    subjects = asyncio.run(stale.provide())
    with subjects["stdout"].open() as reader: text = reader.read()
    ok = _check([
        (isinstance(absent, Loaded) and d_absent.what is E_Decision.ABSENT,
         "nothing recorded: a Loaded, and the word ABSENT"),
        (isinstance(stale, Loaded) and d_stale.what is E_Decision.STALE,
         "old recording: a Loaded, and the word STALE"),
        (text.strip() == "one",
         "the stale recording is still delivered"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a face that only reads is never made to run.")


def test_bare():
    """No configuration in hand: 'bare_provider_of' reads, and never
    executes -- ABSENT before a recording, RECORDED after."""
    configuration, store, directory = _place()
    before, d_before = subject_provision.bare_provider_of(
                           store, "demo.py", subject_name_list=("stdout",))
    print("  before: %s   %s" % (d_before.what.value, _step(d_before)))
    _execute_and_record(configuration, store)
    after, d_after = subject_provision.bare_provider_of(
                         store, "demo.py", subject_name_list=("stdout",))
    print("  after:  %s   %s" % (d_after.what.value, _step(d_after)))
    subjects = asyncio.run(after.provide())
    with subjects["stdout"].open() as reader: text = reader.read()
    ok = _check([
        (isinstance(before, Loaded) and d_before.what is E_Decision.ABSENT,
         "before: a Loaded, and ABSENT"),
        (isinstance(after, Loaded) and d_after.what is E_Decision.RECORDED,
         "after: a Loaded, and RECORDED"),
        (text.strip() == "one", "the recording is read back"),
        (subject_provision.record(store, configuration, None, after)
         is None, "and it records nothing"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "without a configuration the channel reads, never runs.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Subject provision: the one channel",
        choice_map = {
            "bare":             test_bare,
            "executes":         test_executes,
            "loads":            test_loads,
            "production_false": test_production_false,
            "records":          test_records,
            "stale":            test_stale,
        }).run()
