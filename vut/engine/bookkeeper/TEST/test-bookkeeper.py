#! /usr/bin/env python3
#
# @hwut {
#     title      = "The Bookkeeper: the naming, the base, the verdicts"
#     choices    = ["damage", "divergence", "naming", "overwrite",
#                   "protection", "record", "reproduce", "setup_delta",
#                   "one_act"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE BOOKKEEPER: THE NAMING, THE BASE, AND THE DIVERGENCE VERDICTS.

    UNIT     'Bookkeeper' -- one test directory's book, behind one
             adapter.

    CAUSAL CONTRACT
             a key names a record's file; an entry is DERIVED from the
             result, the configuration and the goal; one entry per
             (test, choice, operation), overwritten; the attribution
             record becomes durable; divergence is answered ON CALL and
             never edits the book.

    CONSISTENCY CONTRACT
             the base is write-protected after every write; a damaged
             base reads as empty and a later write recovers it; a
             declared name never recorded raises no complaint.

    Each choice prints the whole picture, so wrongness is visible.
______________________________________________________________________________
"""
import asyncio
import json
import os
import shutil
import stat
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.bookkeeper.observation import ObservationDb   # noqa E402
from   vut.engine.bookkeeper.bookkeeper import (    # noqa E402
                                           Bookkeeper,
                                           compare_setup_delta,
                                           BOOK_FILE_NAME)
from   vut.engine.operations.configuration import (TestConfiguration,  # noqa E402
                                           TestChoiceConfiguration,
                                           E_SourceKind)
from   vut.engine.operations.report        import (TestResult,     # noqa E402
                                           Comparison)
from   vut.engine.operations.result        import E_TestRunResult  # noqa F401,E402
from   vut.engine.operations.run.core import Run             # noqa E402
from   vut.engine.operations.session       import E_Goal           # noqa E402
from   vut.engine.procsitter.api  import ProcsitterConfig # noqa E402


def _check(pair_list):
    """
    RETURN: True,  every claim held.
            False, at least one did not.

    Prints one line per claim, so the reader sees which.
    """
    all_f = True
    for verdict, claim in pair_list:
        print("  %s: %s" % ("OK  " if verdict else "FAIL", claim))
        all_f = all_f and verdict
    return all_f


def _verdict(ok, message):
    """RETURN: None. The choice's last line: SUCCESS, or the failure."""
    print(("SUCCESS: %s" if ok else "FAILURE: %s") % message)


def _place(content):
    """
    RETURN: str, a test directory holding 'demo.py' with 'content'.
    """
    directory = tempfile.mkdtemp(prefix="vut_book_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(content)
    return directory


def _configured(directory, choice_db=None):
    """
    RETURN: TestConfiguration, INTERPRETED 'demo.py' in 'directory'.
    """
    return TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = choice_db
                         or {None: TestChoiceConfiguration()})


def _ran(configuration, choice_name=None):
    """
    RETURN: TestResult, of one REAL run of the configuration -- real
            provision, real attribution record, a verdict of True with
            report OK stated by a matching comparison.
    """
    provided = asyncio.run(Run(configuration, choice_name).provide())
    return TestResult(name       = configuration.stem,
                      provision  = provided.provision,
                      comparison = Comparison({"stdout": True}))


def test_naming():
    """The naming turns (test, choice, subject) into the file that
    carries it: nominal under GOOD/, candidate under 'TMP/store/'
    (the store's OWN ground, apart from the test's 'OUT/'), the raw and
    cadence sidecars beside the candidate."""
    book = Bookkeeper("/place")
    with_choice = book.nominal_path("parse", "basic", "stdout")
    without     = book.nominal_path("parse", None, "stdout")
    candidate   = book.candidate_path("parse", "basic", "stdout")
    raw         = book.raw_path("parse", "basic", "stdout")
    cadence     = book.timing_path("parse", "basic", "stdout")

    print("INSPECT: with choice = %s" % os.path.relpath(with_choice, "/place"))
    print("         no choice   = %s" % os.path.relpath(without, "/place"))
    print("         candidate   = %s" % os.path.relpath(candidate, "/place"))
    print("         raw         = %s" % os.path.relpath(raw, "/place"))
    print("         cadence     = %s" % os.path.relpath(cadence, "/place"))
    ok = _check([
        (str(with_choice).endswith("GOOD/parse--basic.txt"),
         "the choice is part of the key, so choices never collide"),
        (str(without).endswith("GOOD/parse.txt"),
         "a test without choices carries no choice part"),
        (str(candidate).endswith("OUT/parse--basic.txt"),
         "nominals and candidates live in SEPARATE key spaces: "
         "'GOOD/' and 'OUT/', one name, two grounds"),
        (str(raw).endswith(".stdout.raw")
         and str(cadence).endswith(".stdout.times"),
         "the sidecars ride beside the candidate, named after it"),
    ])
    _verdict(ok, "one key per (test, choice, subject); the Bookkeeper "
                 "names its file.")


def test_record_derives():
    """An entry is DERIVED from the result, the configuration and the
    goal -- and the ATTRIBUTION becomes durable: a fresh Bookkeeper over
    the same directory reads the record of the process that produced
    the result."""
    directory = _place("print('to stdout')\n")
    entry_cfg = TestChoiceConfiguration(
                    canonicalisers={"stdout": ["cat"]})
    configuration = _configured(directory,
                                choice_db={"basic": entry_cfg})
    book  = Bookkeeper(directory)
    entry = book.record(_ran(configuration, "basic"), configuration,
                        E_Goal.VERDICT, "basic")

    fresh    = Bookkeeper(directory)
    read     = fresh.result("demo", "basic")
    observed = ObservationDb(directory).get("demo", "basic", "Run")

    print("INSPECT: entry keys = %s" % sorted(entry))
    print("         verdict %s, report %s"
          % (read["verdict"], read["report"]))
    print("         observed: host %s, duration %s"
          % (observed.host is not None,
             observed.duration_ms is not None))
    ok = _check([
        (sorted(entry) == ["report", "verdict"],
         "THE BASE HOLDS DECISIONS: the verdict and the report -- "
         "nothing a run can make again, and NO CONFIGURATION (B-6)"),
        (read["verdict"] is True and read["report"] == "ok",
         "the verdict and the report come from the result"),
        ("canonicaliser" not in read and "compare" not in read,
         "the canonicaliser and the compare setup are the header's "
         "and hwut.conf's, versioned by git beside the book (B-6)"),
        ("records" not in entry and "when" not in entry
         and "host" not in entry,
         "the attribution, the instant and the host are OBSERVATIONS "
         "and are not in the book"),
        (observed is not None and observed.host is not None,
         "they are in the LOCAL database instead, under (test, "
         "choice, operation) -- added here, not by the caller"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "an entry is derived; decisions to the book, "
                 "observations to the local database.")


def test_overwrite():
    """One entry per (test, choice, operation), OVERWRITTEN -- state
    now, never a log; every other entry untouched."""
    directory     = _place("print('x')\n")
    configuration = _configured(directory)
    book          = Bookkeeper(directory)
    result        = _ran(configuration)

    book.record(result, configuration, E_Goal.VERDICT)
    book.record(result, configuration, E_Goal.NOMINAL)
    first    = book.result("demo", None)["report"]
    accepted = book.result("demo", None).get("last_accept")

    failed = TestResult(name       = "demo",
                        provision  = result.provision,
                        comparison = Comparison({"stdout": False}))
    book.record(failed, configuration, E_Goal.VERDICT)
    second = book.result("demo", None)

    with open(book.book_path, encoding="utf-8") as fh:
        row_n = len(fh.read().splitlines()) - 1
    print("INSPECT: report was '%s', now '%s'" % (first, second["report"]))
    print("         rows for the choice = %d" % row_n)
    ok = _check([
        (second["report"] == "not-equivalent-with-nominal",
         "the second write REPLACED the first"),
        (row_n == 1,
         "ONE ROW PER CHOICE (B-7): an operation is not a dimension"),
        (accepted is not None and second.get("last_accept") == accepted,
         "the acceptance's instant stands on the same row, and a later "
         "run leaves it where it is"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "state now, never a log -- and no entry disturbs "
                 "another.")


def test_protection():
    """The base is WRITE-PROTECTED after every write -- a guard against
    careless hands, as every other file in GOOD. The adapter unprotects,
    writes beside, replaces, re-protects; no temporary remains."""
    directory     = _place("print('x')\n")
    configuration = _configured(directory)
    book          = Bookkeeper(directory)
    result        = _ran(configuration)

    book.record(result, configuration, E_Goal.VERDICT)
    mode_first = stat.S_IMODE(os.stat(book.book_path).st_mode)
    book.record(result, configuration, E_Goal.NOMINAL)
    mode_again = stat.S_IMODE(os.stat(book.book_path).st_mode)
    leftovers  = [name for name in os.listdir(book.book_path.parent)
                  if name.endswith(".tmp")]

    print("INSPECT: %s" % BOOK_FILE_NAME)
    print("         mode after first write  = %s" % oct(mode_first))
    print("         mode after second write = %s" % oct(mode_again))
    print("         temporaries left behind = %s" % leftovers)
    ok = _check([
        (mode_first == 0o444,
         "the base is left read-only"),
        (mode_again == 0o444,
         "a second write meets the protection and restores it"),
        (leftovers == [],
         "the write is by replacement; no temporary remains"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "protected against careless hands, writable only "
                 "through the adapter.")


def test_damage():
    """The base is a record. A damaged base reads as EMPTY, it does not
    raise; a later write recovers it."""
    directory     = _place("print('x')\n")
    configuration = _configured(directory)
    book          = Bookkeeper(directory)
    result        = _ran(configuration)

    book.record(result, configuration, E_Goal.VERDICT)
    os.chmod(book.book_path, 0o644)
    with open(book.book_path, "w") as fh:
        fh.write("{ this is not json")
    damaged = book.book()
    book.record(result, configuration, E_Goal.VERDICT)
    after   = book.result("demo", None)

    print("INSPECT: damaged base reads as %r" % damaged)
    print("         a later write recovers: verdict = %s"
          % after["verdict"])
    ok = _check([
        (damaged == {},
         "a damaged base reads as empty, it does not raise"),
        (after is not None and after["verdict"] is True,
         "writing recovers the base"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a lost base never fails a run.")


def test_reproduce():
    """THE BOOK HOLDS NO CONFIGURATION (B-6). What a test was configured
    to do is the same commit's header and 'hwut.conf', which git
    versions beside the book; a copy here was read by nobody and
    churned with every moved default. The table carries the decision
    and nothing else."""
    import vut.engine.compare.configuration as compare_configuration
    loose = compare_configuration.Configuration()
    loose.pattern_finder.numeric_tolerance_ratio = 0.01

    directory = _place("print('value 100.4')\n")
    entry_cfg = TestChoiceConfiguration(
                    canonicalisers={"stdout": ["cat"]},
                    compare=loose)
    configuration = _configured(directory,
                                choice_db={"basic": entry_cfg})
    Bookkeeper(directory).record(_ran(configuration, "basic"),
                                 configuration, E_Goal.VERDICT, "basic")

    fresh = Bookkeeper(directory)
    read  = fresh.result("demo", "basic")
    with open(fresh.book_path, encoding="utf-8") as fh:
        table = fh.read()

    print("INSPECT: entry           = %s" % read)
    print("         table header    = %s" % table.splitlines()[0])
    print("         rows            = %d" % (len(table.splitlines()) - 1))
    print("         any 'caps' word = %s" % ("caps" in table))
    ok = _check([
        (sorted(read) == ["report", "verdict"],
         "the entry is the decision and nothing else"),
        (table.splitlines()[0]
         == "test;choice;verdict;report;last_accept;coverage;"
            "stderr;stain_repeat_n;stain_when;test_id;choice_id",
         "THE BOOK IS A TABLE (B-7): one row per choice, ';' between, "
         "every column a decision -- and since B-13 the REGISTER'S two "
         "id columns, last so that every older column keeps its place. "
         "The MARKS are not columns: a row can be removed, and a mark "
         "that went with it would let the scope reissue an id (B-2)"),
        ("caps" not in table and "canonicaliser" not in table
         and "numeric" not in table,
         "no configuration word reaches the oracle directory"),
        (not hasattr(fresh, "test_configuration")
         and not hasattr(fresh, "choice_configuration"),
         "the accessors that read the copy back are gone with it"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the book holds what was DECIDED; what was CONFIGURED "
                 "is git's, beside it.")


def test_divergence():
    """Divergence is answered ON CALL: the caller hands in what is
    DECLARED; the book answers what is recorded but declared no longer.
    A declared name never recorded raises no complaint -- it is new."""
    directory     = _place("print('x')\n")
    choice_db     = {"basic": TestChoiceConfiguration(),
                     "old":   TestChoiceConfiguration()}
    configuration = _configured(directory, choice_db=choice_db)
    book          = Bookkeeper(directory)
    book.record(_ran(configuration, "basic"), configuration,
                E_Goal.VERDICT, "basic")
    book.record(_ran(configuration, "old"), configuration,
                E_Goal.VERDICT, "old")

    agreeing = book.divergence({"demo": ["basic", "old"]})
    renamed  = book.divergence({"demo": ["basic", "fancy"]})
    dropped  = book.divergence({"other": [None]})
    before   = json.dumps(book.book(), sort_keys=True)
    after    = json.dumps(Bookkeeper(directory).book(), sort_keys=True)

    print("INSPECT: declared as recorded    -> %s" % agreeing)
    print("         'old' renamed to 'fancy'-> %s" % renamed)
    print("         'demo' not declared     -> %s" % dropped)
    ok = _check([
        (agreeing == {"deleted": [], "non-responsive": {}},
         "book and declaration agreeing raise nothing"),
        (renamed == {"deleted": [],
                     "non-responsive": {"demo": ["old"]}},
         "a recorded choice no longer declared is NON-RESPONSIVE"),
        (renamed["non-responsive"]["demo"] == ["old"]
         and "fancy" not in str(renamed),
         "the never-recorded 'fancy' raises no complaint -- it is new"),
        (dropped["deleted"] == ["demo"],
         "a recorded test no longer declared is DELETED"),
        (before == after,
         "the answer never edits the book"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the caller declares; the book answers; healing is a "
                 "service.")


def test_setup_delta():
    """ONLY the differences reach the book: a default compare setup adds
    nothing, and an option compare has not invented yet is recorded the
    day it is used."""
    import dataclasses
    import vut.engine.compare.configuration as compare_configuration

    plain = compare_setup_delta(compare_configuration.Configuration())
    loose = compare_configuration.Configuration()
    loose.pattern_finder.numeric_tolerance_ratio = 0.01
    chosen = compare_setup_delta(loose)

    #  AN OPTION COMPARE HAS NOT INVENTED YET. Compare invents one by
    #  DECLARING it, and the walk is over whatever it declares at the
    #  moment of the call -- so the option is recorded the day it exists,
    #  with nothing here naming it. The declaration is stood in for and
    #  put back; a test that leaves a component changed is a trap for the
    #  next one.
    original_finder = compare_configuration.ConfigurationPatternFinder
    original_config = compare_configuration.Configuration

    field_list = [(f.name, f.type, f)
                  for f in dataclasses.fields(original_finder)]
    FutureFinder = dataclasses.make_dataclass(
        "ConfigurationPatternFinder",
        [(name, type_, field) for name, type_, field in field_list]
        + [("rounding_digits", int, dataclasses.field(default=0))],
        slots=True)

    FutureConfiguration = dataclasses.make_dataclass(
        "Configuration",
        [(f.name,
          FutureFinder if f.name == "pattern_finder" else f.type,
          dataclasses.field(default_factory=FutureFinder)
          if f.name == "pattern_finder" else f)
         for f in dataclasses.fields(original_config)],
        slots=True)

    #  THE DOOR IS WHAT THE BOOK READS (E-37), so the future compare
    #  must stand behind the door as well: patching the module the
    #  door imports FROM would leave the door holding yesterday's
    #  class, and this test would prove nothing.
    from vut.engine.compare import api as compare_api
    original_api_config = compare_api.Configuration
    compare_configuration.ConfigurationPatternFinder = FutureFinder
    compare_configuration.Configuration              = FutureConfiguration
    compare_api.Configuration                        = FutureConfiguration
    try:
        future = FutureConfiguration()
        future.pattern_finder.rounding_digits = 3
        invented = compare_setup_delta(future)
    finally:
        compare_configuration.ConfigurationPatternFinder = original_finder
        compare_configuration.Configuration              = original_config
        compare_api.Configuration                        = original_api_config

    #  AND AN OPTION THAT DOES NOT EXIST cannot be set at all: the
    #  configuration is slotted, so a misspelt tolerance is refused where
    #  it is written instead of being carried silently into the book.
    try:
        compare_configuration.Configuration().pattern_finder \
                            .numeric_tolerence_ratio = 0.01
        refused = ""
    except AttributeError as error:
        refused = str(error)

    print("INSPECT: default setup -> %s" % plain)
    print("         chosen setup  -> %s" % chosen)
    print("         an option compare has not invented yet -> %s"
          % invented)
    print("         a misspelt one -> %s" % refused)
    ok = _check([
        (plain == {},
         "a DEFAULT setup adds nothing"),
        (chosen == {"numeric_tolerance_ratio": 0.01},
         "a chosen one is recorded, and only what was chosen"),
        (invented == {"rounding_digits": 3},
         "a tolerance compare invents later is recorded the day it "
         "is used"),
        (bool(refused),
         "a tolerance that does not exist is refused where it is "
         "written"),
    ])
    _verdict(ok, "what somebody CHOSE is what the book keeps.")


def test_one_act():
    """THE BOOKKEEPER IS THE LOCKING PROXY (B-9): the register is written
    in the book's own act -- an accept issues an id, a removal retires
    it, a rename re-keys it -- and every act runs under the directory's
    lock, which a holder above takes once through 'held()' and the
    acts inside see as held."""
    from vut.engine.bookkeeper.api import DirectoryLock, DirectoryBusy
    from vut.auxiliary.directory_mutex import DirectoryDeadlock
    directory = _place("print('x')\n")
    book      = Bookkeeper(directory)
    sibling   = Bookkeeper(directory)          # a run builds one per app

    book.note_accept("app.py", "one")
    issued   = book.run_id_of("app.py", "one")
    book.rename_choice("app.py", "one", "first")
    renamed  = book.run_id_of("app.py", "first")
    book.rename_test("app.py", "fresh.py")
    rekeyed  = book.run_id_of("fresh.py", "first")
    gone     = book.remove_test("fresh.py")
    retired  = book.run_id_of("fresh.py", "first")
    book.note_accept("later.py", None)
    later    = book.run_id_of("later.py")

    #  INSIDE 'held()' every act goes through without a second take --
    #  through the sibling too, since what is held is the DIRECTORY --
    #  while a stranger's lock on the directory is refused.
    inside_ok = stranger = nested_ok = None
    with book.held():
        sibling.note_accept("held.py", None)
        inside_ok = sibling.run_id_of("held.py") is not None
        #  A HELD() INSIDE A HELD() holds nothing of its own and runs
        #  inside the one above -- the mutex says so, and the act
        #  believes it rather than a table of its own.
        with sibling.held() as inner:
            nested_ok = inner is None
        try:
            with DirectoryLock(directory): stranger = "taken"
        except (DirectoryBusy, DirectoryDeadlock) as error:
            stranger = type(error).__name__
    after = sibling.run_id_of("held.py")

    print("INSPECT: issued %s, renamed %s, re-keyed %s, retired -> %s, "
          "later %s" % (issued, renamed, rekeyed, retired, later))
    print("         inside held(): sibling wrote %s; a second lock: %s; "
          "after: %s" % (inside_ok, stranger, after))
    ok = _check([
        (issued is not None and str(issued) == "0.0",
         "an accept issues the id in its own act"),
        (renamed == issued and rekeyed == issued,
         "a rename re-keys the register; the id stands"),
        (gone is not None and retired is None,
         "a removal retires the id in the book's act"),
        (later is not None and str(later) == "1",
         "a retired id is never reissued (B-2)"),
        (inside_ok and after is not None,
         "under held(), a sibling bookkeeper writes without deadlock"),
        (stranger == "DirectoryDeadlock",
         "a bare second lock on the held directory is refused by name"),
        (nested_ok,
         "a nested held() yields None: it holds nothing of its own"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    return ok


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The Bookkeeper: the naming, the base, the verdicts",
        choice_map = {
            "naming":      test_naming,
            "record":      test_record_derives,
            "overwrite":   test_overwrite,
            "protection":  test_protection,
            "damage":      test_damage,
            "reproduce":   test_reproduce,
            "divergence":  test_divergence,
            "setup_delta": test_setup_delta,
            "one_act":     test_one_act,
        },
        happy      = "SUCCESS.*",
    ).run()
