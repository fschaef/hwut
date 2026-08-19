#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE FRONT DOOR AND ITS CEREMONY.

    UNIT     'run_test' -- verify, lock, operate, record, book,
             unlock. The one callable a caller needs.

    CAUSAL CONTRACT
             the GOAL selects the operation; a Run's subjects are stored
             as candidates so Replay has something to read; what happened
             is entered in the book.

    CONSISTENCY CONTRACT
             the lock is released however the run ended; an unservable
             configuration is refused BEFORE anything runs; a Replay
             records nothing; the recorded candidate is the SAME
             execution that was judged, never a second one.
______________________________________________________________________________
"""
import asyncio
import io
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.result       import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.procsitter    import ProcsitterConfig # noqa E402
from   vut.engine.operations.configuration   import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   ConfigurationError,
                                                   E_SourceKind)
from   vut.engine.operations.session         import (              # noqa E402
                                                   run_test as _front_door,
                                                   Display,
                                                   Request,
                                                   store_of,
                                                   E_Goal)
from   vut.engine.orchestrator.bookkeeper.bookkeeper import (    # noqa E402
                                                   Bookkeeper,
                                                   compare_setup_delta)
from   vut.engine.operations.interaction.feed import (            # noqa E402
                                                    E_DisplayTarget,
                                                    driver_for)
from   vut.engine.orchestrator.bookkeeper.stream_store           import (Store,        # noqa E402
                                                   DirectoryBusy,
                                                   StoreConfig,
                                                   LOCK_DIRECTORY_NAME)


def _bookkeeper_of(configuration):
    """RETURN: Bookkeeper, over the directory the configuration names.

    MADE ABOVE: the Bookkeeper is never made inside 'run_test' -- and in
    this file, 'above' is the test itself.
    """
    directory = configuration.store.directory \
                if configuration.store is not None \
                else configuration.test_directory
    return Bookkeeper(directory)


def run_test(configuration, request=None):
    """RETURN: Outcome, of the front door, handed a Bookkeeper made
    here."""
    return _front_door(configuration, request,
                       bookkeeper=_bookkeeper_of(configuration))


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


def _place(body, **kwargs):
    """RETURN: (TestConfiguration, Store, str), a ready test."""
    directory = tempfile.mkdtemp(prefix="vut_sess_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(body)
    argument_db = dict(source_file    = "demo.py",
                       source_kind    = E_SourceKind.INTERPRETED,
                       test_directory = directory,
                       caps           = ProcsitterConfig(
                                            max_wall_clock_sec=20.0),
                       interpreter    = ["python3", "-u"],
                       store          = StoreConfig(directory=directory),
                       choice_db      = {None: TestChoiceConfiguration()})
    argument_db.update(kwargs)
    configuration = TestConfiguration(**argument_db)
    return (configuration,
            store_of(configuration, _bookkeeper_of(configuration)),
            directory)


def test_the_arc():
    """The whole arc through one door: a test with no nominal fails and
    says why, acceptance makes it pass, a change makes it fail again."""
    configuration, store, directory = _place("print('behaviour one')\n")

    first  = asyncio.run(run_test(configuration))
    accept = asyncio.run(run_test(configuration, Request(goal=E_Goal.NOMINAL)))
    passed = asyncio.run(run_test(configuration))
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write("print('behaviour TWO')\n")
    changed = asyncio.run(run_test(configuration))

    for title, outcome in (("no nominal yet", first),
                           ("accept",         accept),
                           ("verdict",        passed),
                           ("behaviour changed", changed)):
        print("INSPECT: %-18s -> %-5s %s"
              % (title, outcome.verdict, outcome.report))
    ok = _check([
        (first.report is E_TestRunResult.NOMINAL_FILE_NOT_FOUND,
         "with no nominal the test fails and names the nominal"),
        (accept.verdict is True and passed.verdict is True,
         "acceptance makes it pass"),
        (changed.report is E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL,
         "a change of behaviour makes it fail again"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the whole arc, through one callable.")


def test_recording_feeds_replay():
    """A Run RECORDS its subjects as candidates, which is what gives
    Replay something to read. And the recorded candidate is the SAME
    execution that was judged -- not a second run of the application."""
    configuration, store, directory = _place(
        "import random\nprint('run id', random.randint(0, 10**9))\n")

    executed = asyncio.run(run_test(configuration))
    stored   = open(store.candidate_path("demo", None, "stdout")).read()
    replayed = asyncio.run(run_test(configuration, Request(replay=True)))

    print("INSPECT: recorded subjects = %s" % sorted(executed.recorded_db))
    print("         the judged run and the stored one match: %s"
          % (stored == executed.recorded_db["stdout"]))
    print("         replay recorded nothing: %s"
          % (replayed.recorded_db is None))
    ok = _check([
        (sorted(executed.recorded_db) == ["stderr", "stdout"],
         "a Run stores every subject it provided"),
        (stored == executed.recorded_db["stdout"],
         "and stores the SAME execution that was judged"),
        (replayed.recorded_db is None,
         "a Replay records nothing -- it would write back what it read"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "what was judged is what is recorded.")


def test_entry_is_booked():
    """What happened is entered in the book, one entry per operation,
    overwritten -- and the canonicaliser is recorded with it."""
    configuration, store, directory = _place(
        "print('x')\n",
        choice_db={None: TestChoiceConfiguration(
                             canonicalisers={"stdout": ["cat"]})})

    asyncio.run(run_test(configuration, Request(goal=E_Goal.NOMINAL)))
    outcome = asyncio.run(run_test(configuration))
    book    = store.bookkeeper.book()

    print("INSPECT: operations booked = %s"
          % {t: {c: sorted(v["choices"][c]["operations"])
                 for c in v["choices"]}
             for t, v in book.items()})
    print("         Run entry  = %s"
          % {k: v for k, v in outcome.entry.items()
             if k not in ("when", "host", "records")})
    ok = _check([
        (sorted(book["demo"]["choices"]["<none>"]["operations"])
             == ["Accept", "Run"],
         "one entry per operation, both kept"),
        ("canonicaliser" in outcome.entry,
         "the canonicaliser is recorded: a record is HISTORY, and a later "
         "Replay must be able to tell it was freed differently"),
        ("when" in outcome.entry and "host" in outcome.entry,
         "when and host are recorded for the speed reference"),
        ("records" in outcome.entry,
         "the attribution rides with it -- the record of the process "
         "that produced a result is PART of that result"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "what happened is booked, and never appended to.")


def test_lock_is_released():
    """The directory lock is taken for the ceremony and released however
    it ended -- including when the run raised."""
    configuration, store, directory = _place("print('x')\n")
    lock_path = os.path.join(directory, LOCK_DIRECTORY_NAME)

    asyncio.run(run_test(configuration))
    after_success = os.path.isdir(lock_path)

    broken = TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = {None: TestChoiceConfiguration()})
    raised = None
    try:
        asyncio.run(run_test(broken, Request(choice="no-such-choice")))
    except KeyError as error:
        raised = "KeyError %s" % error
    after_failure = os.path.isdir(lock_path)

    print("INSPECT: lock after a clean run  = %s" % after_success)
    print("         a bad choice raised     = %s" % raised)
    print("         lock after the failure  = %s" % after_failure)
    ok = _check([
        (after_success is False,
         "the lock is released after a clean run"),
        (raised is not None,
         "a choice that was never described is a FAULT, not a default"),
        (after_failure is False,
         "and the lock is released even then"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the lock is released however the ceremony ended.")


def test_refused_before_anything_runs():
    """An unservable configuration is refused at the door, before a
    process is launched or a directory is touched."""
    configuration, store, directory = _place("print('x')\n", choice_db={})
    refused = None
    try:
        asyncio.run(run_test(configuration))
    except ConfigurationError as error:
        refused = str(error).split(".")[0]

    print("INSPECT: empty choice_db -> %s" % (refused or "NOT REFUSED"))
    print("         lock left behind: %s"
          % os.path.isdir(os.path.join(directory, LOCK_DIRECTORY_NAME)))
    print("         entries booked: %s" % store.bookkeeper.book())
    ok = _check([
        (refused is not None,
         "the configuration is refused"),
        (not os.path.isdir(os.path.join(directory, LOCK_DIRECTORY_NAME)),
         "no lock was taken"),
        (store.bookkeeper.book() == {},
         "and nothing was booked"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "refused at the door, before anything happens.")


def test_goal_selects():
    """The GOAL names an outcome, and it selects the operation. A caller
    asks for what it wants, not for a class."""
    configuration, store, directory = _place("print('x')\n")
    asyncio.run(run_test(configuration, Request(goal=E_Goal.NOMINAL)))

    collected = []

    class Adapter:
        async def open(self, name):    collected.append("open")
        async def present(self, item): collected.append("item")
        async def close(self):         collected.append("close")

    verdict = asyncio.run(run_test(configuration))
    display = asyncio.run(run_test(
        configuration,
        Request(goal=E_Goal.DISPLAY, display=Display(adapter=Adapter()))))
    operation_list = sorted(store.bookkeeper.book()["demo"]["choices"]
                                                  ["<none>"]["operations"])

    print("INSPECT: VERDICT -> %s, %s" % (verdict.verdict, verdict.report))
    print("         DISPLAY -> %s, adapter saw %i items"
          % (display.verdict, collected.count("item")))
    print("         operations recorded = %s" % operation_list)
    ok = _check([
        (verdict.verdict is display.verdict is True,
         "both goals read the same test and agree"),
        (collected == [],
         "a MATCHING subject is not carried out to the display"),
        (operation_list == ["Accept", "Display", "Run"],
         "each goal booked its own entry"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a caller asks for an outcome, not for a class.")


def test_recording_sidecars():
    """'record_raw' and 'record_timing' keep the material of README 4.
    The CADENCE is stored SEPARATELY, so the pipe into compare is
    untouched by construction rather than by care."""
    directory = tempfile.mkdtemp(prefix="vut_sess_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write("import time\n"
                 "print('zebra'); time.sleep(0.05); print('apple')\n")
    with open(os.path.join(directory, "sort.pype"), "w") as fh:
        fh.write("on: <bof> => {\n    kept = []\n}\n"
                 "on: <else> => {\n    kept.append(pype.line())\n}\n"
                 "on: <eof> => {\n    for one in sorted(kept):\n"
                 "        print(one)\n}\n")
    pype = os.path.join(os.path.dirname(__file__), "..", "..",
                        "hwut_pype", "hwut_pype.py")
    configuration = TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        store          = StoreConfig(directory=directory, record_raw=True,
                                     record_timing=True),
        choice_db      = {None: TestChoiceConfiguration(
            canonicalisers={"stdout": ["python3", pype,
                                       os.path.join(directory,
                                                    "sort.pype")]})})
    store = Store(Bookkeeper(directory))
    asyncio.run(run_test(configuration))

    candidate = open(store.candidate_path("demo", None, "stdout")).read()
    raw       = store.raw_path("demo", None, "stdout").read_text()
    cadence   = store.timing("demo", None, "stdout")

    print("INSPECT: canonicalised record = %r" % candidate)
    print("         raw stream kept      = %r" % raw)
    print("         cadence entries      = %i, all non-negative: %s"
          % (len(cadence or ()), all(d >= 0 for d in (cadence or ()))))
    print("         cadence has none of the record's bytes: %s"
          % (store.timing_path("demo", None, "stdout")
             != store.candidate_path("demo", None, "stdout")))
    ok = _check([
        (candidate == "apple\nzebra\n",
         "the RECORD is the canonicalised stream"),
        (raw == "zebra\napple\n",
         "the RAW stream is kept beside it, in the order emitted"),
        (cadence is not None and len(cadence) == 2,
         "one cadence entry per RAW line"),
        (cadence[1] >= 0.04,
         "and it measured the real gap between them"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "record, raw and cadence -- three files, one untouched pipe.")


def test_target_selects_a_driver():
    """A target is the ONLY place a driver is chosen, so adding a tier
    touches one function. A target with no driver is refused rather than
    guessed at."""
    #  Each target is named with the arguments THAT outcome needs --
    #  a client's argv for RICH, a stream and no merge for a TUI probe.
    argument_db = {
        E_DisplayTarget.RICH: {"argv": ["python3", "-c", "pass"]},
        E_DisplayTarget.TUI:  {"out": io.StringIO(), "merge_f": False},
    }
    row_list = []
    for target in E_DisplayTarget:
        driver = driver_for(target, **argument_db.get(target, {}))
        row_list.append((str(target), type(driver).__name__))
        print("INSPECT: %-8s -> %s" % row_list[-1])
    refused = None
    try:
        driver_for(E_DisplayTarget.RICH)
    except ValueError as error:
        refused = str(error).split("--")[0].strip()
    print("         RICH without a client -> %s" % (refused or "NOT REFUSED"))
    ok = _check([
        (dict(row_list)["none"] == "NullDisplay",
         "NONE carries nothing"),
        (dict(row_list)["tui"] == "TuiDisplay",
         "TUI is the terminal, interactively"),
        (dict(row_list)["rich"] == "RemoteDisplay",
         "RICH is the client that speaks the protocol"),
        (refused is not None,
         "and RICH without a client is refused -- there is no default IDE"),
    ])
    _verdict(ok, "one place turns a target into a driver.")


def test_busy_directory_is_refused():
    """THE CONCURRENCY LAW, through the front door: a directory held by a
    LIVE process is refused, not waited out. Two runs of one test must
    never overlap."""
    configuration, store, directory = _place("print('x')\n")
    lock_path = os.path.join(directory, LOCK_DIRECTORY_NAME)

    child = subprocess.Popen([sys.executable, "-c",
        "import sys, os, json, time, psutil\n"
        "d = sys.argv[1]; os.makedirs(d)\n"
        "json.dump({'pid': os.getpid(),\n"
        "           'started': psutil.Process().create_time()},\n"
        "          open(os.path.join(d,'holder.json'),'w'))\n"
        "sys.stdout.write('held\\n'); sys.stdout.flush(); time.sleep(30)\n",
        lock_path], stdout=subprocess.PIPE, text=True)
    refused = None
    try:
        child.stdout.readline()
        try:
            asyncio.run(run_test(configuration))
        except DirectoryBusy as error:
            refused = str(error)
        still_held = os.path.isdir(lock_path)
    finally:
        child.kill(); child.wait()

    print("INSPECT: a live process holds the directory")
    print("         run_test -> %s"
          % ("refused: " + refused.split("'")[-1].strip()
             if refused else "NOT REFUSED"))
    print("         the holder's lock survives: %s" % still_held)
    ok = _check([
        (refused is not None,
         "the run is REFUSED, not queued and not forced"),
        (still_held is True,
         "and the live holder's lock is untouched"),
        (store.bookkeeper.book() == {},
         "nothing was booked on the way out"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "two runs of one test never overlap.")


def test_request_is_separate():
    """A CONFIGURATION says what the test IS and does not change between
    runs. A REQUEST says what is wanted OF it this time. Keeping them
    apart is why neither grows fields belonging to the other."""
    configuration, store, directory = _place("print('x')\n")
    asyncio.run(run_test(configuration, Request(goal=E_Goal.NOMINAL)))

    one_configuration = [
        asyncio.run(run_test(configuration, request))
        for request in (Request(),
                        Request(goal=E_Goal.DISPLAY),
                        Request(goal=E_Goal.VERDICT, replay=True))]

    import inspect
    parameter_list = list(
        inspect.signature(run_test).parameters)

    print("INSPECT: run_test takes %s" % parameter_list)
    print("         three requests over ONE configuration -> %s"
          % [outcome.report.name for outcome in one_configuration])
    print("         the configuration is unchanged: %s"
          % (configuration.source_file == "demo.py"))
    ok = _check([
        (parameter_list == ["configuration", "request"],
         "TWO parameters: what the test IS, and what is asked OF it"),
        (len({outcome.report for outcome in one_configuration}) == 1,
         "three different requests, one configuration, all agreeing"),
        (Request().goal is E_Goal.VERDICT,
         "a request with nothing said asks the commonest thing"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "what the test is, and what is asked of it, stay apart.")


def test_the_configuration_says_where():
    """WHERE the artifacts live follows from the configuration and is
    said ONCE. A store named beside it would be a second source of truth,
    and the two could disagree."""
    elsewhere = tempfile.mkdtemp(prefix="vut_store_")
    configuration, _, directory = _place("print('x')\n")
    moved = TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        store          = StoreConfig(directory=elsewhere),
        choice_db      = {None: TestChoiceConfiguration()})

    asyncio.run(run_test(moved, Request(goal=E_Goal.NOMINAL)))
    here     = store_of(moved, _bookkeeper_of(moved))
    storeless = TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = {None: TestChoiceConfiguration()})
    default   = store_of(storeless, _bookkeeper_of(storeless))
    landed    = here.nominal_path("demo", None, "stdout").exists()
    not_here  = not os.path.exists(os.path.join(directory, "GOOD"))

    print("INSPECT: the store's own directory was named -> artifacts land there")
    print("         nominal in the named directory : %s" % landed)
    print("         nothing under the test directory: %s" % not_here)
    print("         no store named -> defaults to the test directory: %s"
          % (str(default.directory) == directory))
    ok = _check([
        (landed is True,
         "a store that names a directory is OBEYED, not ignored"),
        (not_here is True,
         "and nothing is written where it did not ask"),
        (str(default.directory) == directory,
         "a configuration naming no store uses the test's own directory"),
        (here.records is True and default.records is False,
         "a store is asked whether it records; no StoreConfig, no record"),
    ])
    for d in (directory, elsewhere): shutil.rmtree(d, ignore_errors=True)
    _verdict(ok, "where artifacts live is said once, by the configuration.")


def test_the_compare_setup_is_recorded():
    """BOTH HALVES OF FREEING reach the entry. The canonicaliser
    changed the RECORD; the compare setup changed the VERDICT. An entry
    saying 'verdict: true' means something different under a loose setup
    than a strict one, and without this nothing said which was in force.

    TWO PROPERTIES, both shown over EVERY DECLARED MEMBER:

        COMPLETE  a member chosen away from its default SURFACES in
                  the entry -- nothing silently vanishes, which is what
                  would make a stored verdict uninterpretable. The
                  sweep reads compare's DECLARATION, so a member
                  compare gains later is swept the day it exists.
        MINIMAL   a default setup adds nothing at all.
    """
    import dataclasses
    import vut.engine.compare.configuration as compare_configuration

    loose = compare_configuration.Configuration()
    loose.pattern_finder.numeric_tolerance_ratio = 0.01

    directory = tempfile.mkdtemp(prefix="vut_sess_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write("print('value 100.4')\n")
    def configured(options):
        """RETURN: TestConfiguration, with that compare setup."""
        return TestConfiguration(
            source_file    = "demo.py",
            source_kind    = E_SourceKind.INTERPRETED,
            test_directory = directory,
            caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
            interpreter    = ["python3", "-u"],
            store          = StoreConfig(directory=directory),
            choice_db      = {None: TestChoiceConfiguration(compare=options)})

    store = Store(Bookkeeper(directory))
    store.accept("demo", None, "stdout", "value 100.0\n")
    strict_outcome = asyncio.run(run_test(configured(None)))
    loose_outcome  = asyncio.run(run_test(configured(loose)))

    print("INSPECT: default setup  -> verdict %-5s entry 'compare' %s"
          % (strict_outcome.verdict,
             "compare" in strict_outcome.entry))
    print("         loose setup    -> verdict %-5s entry 'compare' %s"
          % (loose_outcome.verdict, loose_outcome.entry.get("compare")))

    #  THE SWEEP: every declared member, perturbed by its type, and
    #  what the delta says about it.
    print()
    print("         THE SWEEP -- every declared member of compare's "
          "pattern finder")
    print("         %-30s %-14s %-14s %s"
          % ("member", "default", "chosen", "in entry"))
    unreached = []
    for member in dataclasses.fields(
                        compare_configuration.ConfigurationPatternFinder):
        options  = compare_configuration.Configuration()
        default  = getattr(options.pattern_finder, member.name)
        chosen   = _perturbed(default)
        setattr(options.pattern_finder, member.name, chosen)
        delta    = compare_setup_delta(options)
        present  = member.name in delta
        if not present: unreached.append(member.name)
        print("         %-30s %-14s %-14s %s"
              % (member.name, _short(default), _short(chosen),
                 "yes" if present else "NO -- UNREACHED"))

    ok = _check([
        (strict_outcome.verdict is False and loose_outcome.verdict is True,
         "the setup decided the verdict -- same subject, same nominal"),
        ("compare" not in strict_outcome.entry,
         "a DEFAULT setup adds nothing to the entry"),
        (loose_outcome.entry["compare"]
             == {"numeric_tolerance_ratio": 0.01},
         "a chosen one is recorded, and only what was chosen"),
        (not unreached,
         "EVERY declared member surfaces when chosen -- none is "
         "silently dropped"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "what the verdict meant is recorded beside the verdict.")


def _perturbed(value):
    """
    RETURN: a value of the same type as 'value', but DIFFERENT from it
            -- what a member looks like once somebody has chosen it.

    Raises AssertionError for a type the sweep has not met: a new kind
    of member must be PLACED here, never silently skipped.
    """
    match value:
        case bool():  return not value
        case int():   return value + 1
        case float(): return value + 0.5
        case str():   return value + "!"
        case list():  return list(value) + ["chosen"]
        case tuple(): return tuple(value) + ("chosen",)
        case _:
            assert False, "the sweep cannot perturb a %s" % type(value)


def _short(value):
    """RETURN: str, 'value' rendered short enough for the table."""
    text = repr(value)
    return text if len(text) <= 13 else text[:10] + "..."


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The front door and its ceremony",
        choice_map = {
            "the_arc":     test_the_arc,
            "recording":   test_recording_feeds_replay,
            "book":        test_entry_is_booked,
            "lock":        test_lock_is_released,
            "refused":     test_refused_before_anything_runs,
            "goal":        test_goal_selects,
            "sidecars":    test_recording_sidecars,
            "target":      test_target_selects_a_driver,
            "busy":        test_busy_directory_is_refused,
            "request":     test_request_is_separate,
            "where":       test_the_configuration_says_where,
            "setup":       test_the_compare_setup_is_recorded,
        },
        happy      = "SUCCESS.*",
    ).run()
