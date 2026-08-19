#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ACCEPT: WRITE THE NOMINAL.

    UNIT     'Accept' -- the last step of the run -> diff -> promote loop.
             Content production is external; this stores a complete dump.

    CAUSAL CONTRACT
             a handed dump is stored wholesale; a step naming no dump
             PULLS provision; what is stored becomes the nominal that
             later comparisons read.

    CONSISTENCY CONTRACT
             acceptance is ALL OR NOTHING -- a dump that cannot be read
             leaves NOTHING written, so a test is never half accepted;
             provision is pulled ONCE however many subjects need it.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile
from   types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.result       import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.procsitter    import ProcsitterConfig # noqa E402
from   vut.engine.operations.consume.accept import (Accept,       # noqa E402
                                                     AcceptConfig,
                                                     AcceptStep,
                                                     E_AcceptMode)
from   vut.engine.operations.configuration   import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   E_SourceKind)
from   vut.engine.operations.consume.equivalence_check import (            # noqa E402
                                                              EquivalenceCheck,
                                                              EquivalenceCheckConfig)
from   vut.engine.operations.nominal         import (BytesNominal, # noqa E402
                                                   RecordNominal)
from   vut.engine.operations.run.core  import Run            # noqa E402
from   vut.engine.orchestrator.bookkeeper.bookkeeper import (    # noqa E402
                                                   Bookkeeper)
from   vut.engine.orchestrator.bookkeeper.stream_store           import Store          # noqa E402
from   vut.engine.orchestrator.bookkeeper.configuration import (  # noqa E402
                                              E_StderrNote)


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


def _place(body):
    """RETURN: str, a fresh test directory holding 'demo.py'."""
    directory = tempfile.mkdtemp(prefix="vut_acc_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(body)
    return directory


def _configuration(directory):
    """RETURN: TestConfiguration, an INTERPRETED test in 'directory'."""
    return TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = {None: TestChoiceConfiguration()})


def test_take_dump():
    """A complete dump is stored WHOLESALE: the nominal becomes exactly
    what was handed over, not a merge of it with what was there."""
    directory = tempfile.mkdtemp(prefix="vut_acc_")
    store     = Store(Bookkeeper(directory))
    store.accept("demo", None, "stdout", "the OLD nominal\n")
    result = asyncio.run(Accept(AcceptConfig(
        "demo", {"stdout": AcceptStep(dump=BytesNominal("the NEW dump\n"))}),
        store).run())
    stored = open(store.nominal_path("demo", None, "stdout")).read()

    print("INSPECT: report = %s" % result.report)
    print("         stored = %r" % stored)
    ok = _check([
        (result.verdict is True,
         "acceptance succeeded"),
        (stored == "the NEW dump\n",
         "the nominal is REPLACED wholesale, not merged"),
        (result.accepted_db == {"stdout": "the NEW dump\n"},
         "and the result says exactly what was stored"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a dump replaces the nominal, wholesale.")


def test_pulls_provision():
    """A step naming no dump has an UNMET PRECONDITION, so provision
    activates -- and it activates ONCE, however many subjects need it."""
    directory = _place("import sys\n"
                       "print('to stdout')\n"
                       "sys.stderr.write('to stderr\\n')\n")
    store  = Store(Bookkeeper(directory))
    result = asyncio.run(Accept(AcceptConfig(
        "demo",
        {"stdout": AcceptStep(), "stderr": AcceptStep()},
        groundwork=Run(_configuration(directory))), store).run())

    print("INSPECT: report        = %s" % result.report)
    print("         accepted      = %s" % sorted(result.accepted_db))
    print("         stdout stored = %r"
          % open(store.nominal_path("demo", None, "stdout")).read())
    print("         provision run = %s (records: %i)"
          % (result.provision is not None,
             len(result.provision.records) if result.provision else 0))
    ok = _check([
        (result.verdict is True,
         "acceptance succeeded without any dump being handed over"),
        (sorted(result.accepted_db) == ["stderr", "stdout"],
         "both subjects were accepted"),
        (result.provision is not None
             and len(result.provision.records) == 1,
         "provision ran ONCE -- one attribution record for two subjects"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "an unmet precondition pulls provision, once.")


def test_all_or_nothing():
    """A dump that cannot be read leaves NOTHING written. A half-accepted
    test would hold new behaviour against old nominals on the subjects
    that were missed, and report the difference as a fault of the code."""
    directory = tempfile.mkdtemp(prefix="vut_acc_")
    store     = Store(Bookkeeper(directory))
    result = asyncio.run(Accept(AcceptConfig("demo", {
        "stdout": AcceptStep(dump=BytesNominal("this one is readable\n")),
        "stderr": AcceptStep(dump=RecordNominal("/nowhere/no-such-dump")),
    }), store).run())

    print("INSPECT: report            = %s" % result.report)
    print("         accepted          = %s" % result.accepted_db)
    print("         readable one kept = %s"
          % store.nominal_path("demo", None, "stdout").exists())
    ok = _check([
        (result.verdict is False,
         "acceptance failed"),
        (result.accepted_db == {},
         "nothing was stored"),
        (not store.nominal_path("demo", None, "stdout").exists(),
         "not even the subject whose dump WAS readable"),
        (result.report is E_TestRunResult.RECORDING_MISSING,
         "and the report names the missing dump"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "all or nothing -- never half a nominal.")


def test_the_loop_closes():
    """THE POINT OF ALL OF IT: run -> differ -> accept -> run -> pass.
    Acceptance is what turns a failing test into a passing one, and
    nothing else in the component may."""
    directory = _place("print('behaviour version one')\n")
    store     = Store(Bookkeeper(directory))

    def check():
        """RETURN: TestResult, of one EquivalenceCheck over a fresh Run."""
        return asyncio.run(EquivalenceCheck(EquivalenceCheckConfig(
            name       = "demo",
            groundwork = Run(_configuration(directory)),
            subjects   = {"stdout": RecordNominal(
                              store.nominal_path("demo", None,
                                                 "stdout"))}
        )).run())

    before = check()
    asyncio.run(Accept(AcceptConfig(
        "demo", {"stdout": AcceptStep()},
        groundwork=Run(_configuration(directory))), store).run())
    after = check()

    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write("print('behaviour version TWO')\n")
    changed = check()

    print("INSPECT: before acceptance -> verdict %-5s report %s"
          % (before.verdict, before.report))
    print("         after acceptance  -> verdict %-5s report %s"
          % (after.verdict, after.report))
    print("         behaviour changed -> verdict %-5s report %s"
          % (changed.verdict, changed.report))
    ok = _check([
        (before.verdict is False
             and before.report is E_TestRunResult.NOMINAL_FILE_NOT_FOUND,
         "with no nominal yet, the test fails and says why"),
        (after.verdict is True,
         "acceptance makes it pass"),
        (changed.verdict is False
             and changed.report is E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL,
         "and a change of behaviour makes it fail again"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "run -> differ -> accept -> pass -> change -> differ.")


def test_initiate_needs_its_session():
    """INITIATE takes its dump from an external session. Without one
    there is nothing to store, and that is reported rather than
    silently falling back to the current output."""
    directory = tempfile.mkdtemp(prefix="vut_acc_")
    store     = Store(Bookkeeper(directory))

    class Session:
        async def collect(self, subject_name):
            """RETURN: str, the final plain nominal stream of a session."""
            return "merged by an external session\n"

    with_session = asyncio.run(Accept(AcceptConfig(
        "demo", {"stdout": AcceptStep(mode=E_AcceptMode.INITIATE,
                                      interaction=Session())}), store).run())
    without = asyncio.run(Accept(AcceptConfig(
        "other", {"stdout": AcceptStep(mode=E_AcceptMode.INITIATE)}),
        store).run())

    print("INSPECT: with a session -> %s, stored %r"
          % (with_session.report,
             open(store.nominal_path("demo", None, "stdout")).read()))
    print("         without one   -> %s, stored anything: %s"
          % (without.report, store.nominal_path("other", None, "stdout").exists()))
    ok = _check([
        (with_session.verdict is True,
         "the session's final stream becomes the nominal"),
        (without.verdict is False,
         "without a session, acceptance fails"),
        (not store.nominal_path("other", None, "stdout").exists(),
         "and does NOT fall back to the current output"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "INITIATE stores its session's stream, or nothing.")




def test_ledger():
    """THE LEDGER READING (n-3): the book is a book of record, and an
    accept is an EVENT in it. 'first_accept' is the instant of the
    FIRST acceptance ever, carried forward untouched; 'when' is the
    LAST -- a re-accept moves only the second."""
    directory  = tempfile.mkdtemp(prefix="vut_acc_")
    bookkeeper = Bookkeeper(directory)

    def accept_entry(marker):
        """RETURN: dict, the book's Accept entry after one recorded
        acceptance carrying 'marker' as its instant."""
        result = SimpleNamespace(name="demo", verdict=True,
                                 report="accepted",
                                 provision=SimpleNamespace(records=()))
        configuration = _configuration(directory)
        entry = bookkeeper.record(result, configuration,
                                  SimpleNamespace(name="NOMINAL"),
                                  choice_name=None)
        return entry

    first  = accept_entry("one")
    second = accept_entry("two")

    print("INSPECT: after the FIRST accept")
    print("         first_accept == when : %s"
          % (first["first_accept"] == first["when"]))
    print("         after a RE-ACCEPT")
    print("         first_accept carried : %s"
          % (second["first_accept"] == first["first_accept"]))
    print("         'when' may move on   : %s"
          % (second["when"] >= first["when"]))
    ok = _check([
        (first["first_accept"] == first["when"],
         "the first accept IS both ends of the ledger"),
        (second["first_accept"] == first["first_accept"],
         "a re-accept leaves 'first_accept' untouched"),
        (second["when"] >= first["when"],
         "and moves only 'when' -- the LAST accept"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "first and last accept: the book keeps the history's "
                 "two ends.")




def test_stderr():
    """THE SECOND QUESTION (S-1). The book holds ONE NOTE about a
    choice's stderr, with three readings -- 'nominal' (recorded and
    compared), 'ignored' (whatever happens, do not worry), 'forbidden'
    (a word there is an error) -- and ACCEPTANCE is where it is
    written. A stream that appears with NO note ever taken stops the
    ceremony: 'stderr-undecided', nothing written at all, because only
    the author knows which of the three is meant.

    An UNNOTED choice reads 'forbidden': a test nobody was asked about
    has never spoken there, and its first word is news."""
    def accepted(note):
        """RETURN: (AcceptResult, note in the book, nominal exists)."""
        directory  = tempfile.mkdtemp(prefix="vut_acc_")
        bookkeeper = Bookkeeper(directory)
        store      = Store(bookkeeper)
        result     = asyncio.run(Accept(
            AcceptConfig(
                name       = "demo",
                subjects   = {"stdout": AcceptStep()},
                groundwork = _Provided({
                    "stdout": BytesNominal("the behaviour\n"),
                    "stderr": BytesNominal("a warning nobody blessed\n")}),
                stderr     = note),
            store).run())
        state = (result, bookkeeper.stderr_note("demo", None),
                 store.nominal_path("demo", None, "stderr").exists())
        shutil.rmtree(directory, ignore_errors=True)
        return state

    print("INSPECT: an unnoted choice reads %s"
          % Bookkeeper(tempfile.mkdtemp()).stderr_note("demo", None))
    print("         %-12s %-22s %-11s %s"
          % ("asked for", "report", "book note", "nominal file"))
    outcome_db = {}
    for note in (None, E_StderrNote.NOMINAL, E_StderrNote.IGNORED,
                 E_StderrNote.FORBIDDEN):
        result, written, nominal_f = accepted(note)
        outcome_db[note] = (result, written, nominal_f)
        print("         %-12s %-22s %-11s %s"
              % ("(nothing)" if note is None else note.value,
                 result.report.value, written.value, nominal_f))

    refused = outcome_db[None][0]
    ok = _check([
        (refused.report is E_TestRunResult.STDERR_UNDECIDED,
         "a stream with words and no note REFUSES the ceremony"),
        (not refused.accepted_db,
         "and nothing at all is written -- not even the stdout that "
         "was fine"),
        (outcome_db[E_StderrNote.NOMINAL][1] is E_StderrNote.NOMINAL
         and outcome_db[E_StderrNote.NOMINAL][2],
         "'nominal' notes the book AND records the stream"),
        (outcome_db[E_StderrNote.IGNORED][1] is E_StderrNote.IGNORED
         and not outcome_db[E_StderrNote.IGNORED][2],
         "'ignored' notes the book and records nothing"),
        (outcome_db[E_StderrNote.FORBIDDEN][1] is E_StderrNote.FORBIDDEN
         and not outcome_db[E_StderrNote.FORBIDDEN][2],
         "'forbidden' notes the book and records nothing"),
    ])
    _verdict(ok, "one note, three readings, and the author writes it.")


class _Provided:
    """A groundwork over a made delivery -- what a run would hand in."""
    def __init__(self, reader_db):
        from vut.engine.operations.run.core import Subjects
        from vut.engine.operations.report import Provision as ProvisionRecord
        self.subjects = Subjects(reader_db,
                                 ProvisionRecord(report=E_TestRunResult.OK))
    async def provide(self, stop_event=None):
        return self.subjects


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Accept: write the nominal",
        choice_map = {
            "stderr":         test_stderr,
            "ledger":         test_ledger,
            "take_dump":      test_take_dump,
            "pulls_run":      test_pulls_provision,
            "all_or_nothing": test_all_or_nothing,
            "the_loop":       test_the_loop_closes,
            "initiate":       test_initiate_needs_its_session,
        },
        happy      = "SUCCESS.*",
    ).run()
