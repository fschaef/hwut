"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE BOOKKEEPER -- one test directory: what a test IS, what it
       HAS DONE, and THE NAMING of every file that carries it.

DESCRIPTION
       ONE BASE: 'GOOD/result_db.json'. It records properly; there is
       nothing to bless about it. The file is write-protected as every
       other file in GOOD -- a guard against careless hands. This
       adapter is the ONLY way in or out: it unprotects, writes
       atomically, re-protects.

       THE NAMING. A record's key is (test, choice, subject); the
       Bookkeeper turns it into the file that carries it -- nominal
       under 'GOOD/', candidate under '.hwut-store/', the raw and cadence
       sidecars beside the candidate. Whoever reads or writes those
       files asks here for the path; the reading and writing themselves
       are the caller's.

       THE ENTRIES. One entry per (test, choice, operation),
       OVERWRITTEN -- state now, never a log; what was done before is
       the concern of the software configuration management system. The
       Bookkeeper DERIVES an entry from the result, the configuration
       and the goal: verdict and report from the result, both halves of
       freeing (canonicaliser, compare setup) from the choice's
       configuration, 'when' and 'host' added here, and THE ATTRIBUTION
       -- the record of every process that produced the result -- made
       durable beside them.

       THE REPRODUCTION. Each write refreshes the test's and the
       choice's reproducible configuration in the base, so a query can
       answer what a test is configured to do from the base alone.

       THE DIVERGENCE is detected ON CALL. The caller hands in what is
       DECLARED; the Bookkeeper answers what is recorded but declared
       no longer: a test reads DELETED, a choice NON-RESPONSIVE. What
       either verdict means is the caller's -- under 'run all tests' it
       is an error, under 'run this test with that choice' it is not.
       Healing is a service (rename, rename-choice, remove,
       remove-choice), never a guess.

       A missing or damaged base reads as EMPTY: the base is a record,
       and its loss must never fail a run.
______________________________________________________________________________
"""
import json
import os
import platform
import stat
from   dataclasses import fields, is_dataclass
from   datetime    import datetime, timezone
from   enum        import Enum
from   pathlib     import Path
from .configuration import E_StderrNote, NamingConfig


RESULT_DB_FILE_NAME = "result_db.json"

NO_CHOICE_KEY       = "<none>"

_OPERATION_BY_GOAL  = {"VERDICT": "Run",
                       "DISPLAY": "Display",
                       "NOMINAL": "Accept"}

E_DIVERGENCE_DELETED        = "deleted"
E_DIVERGENCE_NON_RESPONSIVE = "non-responsive"


def this_host():
    """
    RETURN: str, a host tag for an entry, 'linux-x86_64/<node>'.

    Coarse on purpose: it exists to compare compute speed between hosts,
    not to identify a machine.
    """
    return "%s-%s/%s" % (platform.system().lower(), platform.machine(),
                         platform.node())


def _now():
    """RETURN: str, the current UTC instant, seconds resolution, ISO."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _plain(value):
    """
    RETURN: the value if JSON can carry it; an Enum's name; a
            dataclass's fields, each made plain; the repr otherwise.

    The base is read by anything, so nothing Python-shaped may reach it.
    """
    if isinstance(value, (str, int, float, bool, type(None))): return value
    if isinstance(value, Enum):           return value.name
    if isinstance(value, (list, tuple)):  return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name))
                for f in fields(value)}
    return repr(value)


def compare_setup_delta(options):
    """
    RETURN: dict, every compare setting that DIFFERS from the default.
            {},   the setup is compare's default throughout.

    ONLY THE DIFFERENCES. A default setup adds nothing to an entry,
    and recording the whole of compare's Configuration would make every
    entry grow whenever compare gained an option. What is worth
    keeping is what somebody CHOSE.

    Nothing here names a tolerance: the walk is over whatever compare
    DECLARES, so a tolerance compare has not invented yet is recorded the
    day it is used. The declaration is read through 'dataclasses.fields'
    -- the same source compare's own defaults stand in, so the delta and
    the defaults cannot disagree about what a member is.
    """
    if options is None: return {}
    from ..compare.configuration import Configuration
    default    = Configuration()
    difference = {}

    for field in fields(Configuration):
        name   = field.name
        chosen = getattr(options, name, None)
        plain  = getattr(default, name, None)
        if name == "pattern_finder":
            for inner in fields(plain):
                a = getattr(chosen, inner.name, None)
                b = getattr(plain,  inner.name, None)
                if a != b: difference[inner.name] = _plain(a)
            continue
        if chosen != plain:
            difference[name] = _plain(chosen)
    return difference


class Bookkeeper:
    """ONE test directory's book: the naming, the entries, the
    reproducible configurations, and the divergence verdicts.

    THE NAMING LAW lives in 'configuration.py' (NamingConfig):
    'same_nominal_f' drops the choice part from a NOMINAL's key, so
    every choice is held against one blessed file; candidates keep
    their own names, so a diff still names which choice diverged.

    Made ABOVE -- the orchestrator makes one from the test's directory
    and hands it down; a service that needs one makes it inside the
    service. Nothing below makes its own.
    """

    def __init__(self, directory, naming=None):
        """
        RETURN: Bookkeeper over 'directory'.

        'naming' is the NamingConfig in force; None takes the default
        (a nominal per choice). It reaches the NOMINAL's name only --
        candidates are always named per choice.
        """
        self.directory = Path(directory)
        self.naming    = naming if naming is not None else NamingConfig()

    # -- the naming ---------------------------------------------------
    def key(self, test, choice, subject):
        """
        RETURN: str, the file name of one record: 'test--choice.subject'
                for a test with choices, 'test.subject' without.
        """
        stem = test if choice is None else "%s--%s" % (test, choice)
        return "%s.%s" % (stem, subject)

    def nominal_path(self, test, choice, subject):
        """
        RETURN: Path, where the ACCEPTED record of that key lives.

        Under 'same_nominal_f' the CHOICE PART IS DROPPED: every choice
        of the test is held against one blessed file. Candidates keep
        their own names regardless, or the choices would overwrite one
        another (configuration.py, NamingConfig).
        """
        nominal_choice = None if self.naming.same_nominal_f else choice
        return self.directory / "GOOD" / self.key(test, nominal_choice,
                                                  subject)

    def candidate_path(self, test, choice, subject):
        """RETURN: Path, where the CANDIDATE record of that key lives.

        THE STORE'S OWN GROUND, apart from 'OUT/': 'OUT/' is the
        TEST'S product space -- execution reads every file there as a
        subject -- and the store's records must never become the next
        run's subjects. The dot-name also keeps the tree walk out."""
        return self.directory / ".hwut-store" \
                              / self.key(test, choice, subject)

    def coverage_path(self, test, choice):
        """RETURN: Path, where the COVERAGE RECORD of that run lives --
        '.hwut-store/<key>.cover', the store's own ground: a measurement
        of the last run of that choice, never a nominal, never a
        subject. The suffix is coverage's own ('affected.py')."""
        return self.directory / ".hwut-store" \
                              / self.key(test, choice, "cover")

    def raw_path(self, test, choice, subject):
        """RETURN: Path, where the PRE-canonicalisation stream lives."""
        path = self.candidate_path(test, choice, subject)
        return path.with_suffix(path.suffix + ".raw")

    def timing_path(self, test, choice, subject):
        """RETURN: Path, where the cadence sidecar of that key lives."""
        path = self.candidate_path(test, choice, subject)
        return path.with_suffix(path.suffix + ".times")

    # -- the base -----------------------------------------------------
    @property
    def result_db_path(self):
        """RETURN: Path, the ONE base of this directory."""
        return self.directory / "GOOD" / RESULT_DB_FILE_NAME

    def book(self):
        """
        RETURN: dict, the whole base -- test -> {'configuration',
                'choices'}. Empty when nothing was recorded.

        A missing or unreadable base reads as empty: the base is a
        record, and its loss must never fail a run.
        """
        try:
            with open(self.result_db_path, "r", encoding="utf-8") as fh:
                content = json.load(fh)
        except Exception:
            return {}
        return content if isinstance(content, dict) else {}

    def _write_book(self, content):
        """
        RETURN: None. The whole base, replaced atomically and left
                write-protected.

        Unprotect, write beside, replace, re-protect: a reader never
        meets a half-written base, and a careless hand never meets a
        writable one.
        """
        path = self.result_db_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR
                           | stat.S_IRGRP | stat.S_IROTH)
        temporary = path.with_suffix(".json.tmp")
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(content, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(temporary, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    # -- recording ----------------------------------------------------
    def record(self, result, configuration, goal, choice_name=None,
               coverage=None):
        """
        RETURN: dict, the entry as written -- 'when' and 'host' are
                added here, so no caller has to remember them.

        'coverage' is the coverage step's token ('E_CoverageResult'),
        written as 'coverage' on the entry; None where none was asked,
        and then the key is absent -- absence is data.

        DERIVED, not handed in: the verdict and the report token from
        the result; both halves of freeing from the choice's
        configuration (the canonicaliser changed the RECORD, the
        compare setup changed the VERDICT -- without them a later
        reader cannot tell what this entry meant); THE ATTRIBUTION from
        the result's provision -- the record of the process that
        produced a result is PART of that result, in every mode, and
        this is its durable home.

        OVERWRITES exactly one (test, choice, operation) entry and
        leaves every other untouched; refreshes the test's and the
        choice's reproducible configuration beside it.

        THE LEDGER READING of an ACCEPT (n-3): the book is a book of
        record, and an accept is an EVENT in it. The entry keeps
        'first_accept' -- the instant of the FIRST acceptance ever,
        carried forward untouched -- while 'when' is the LAST: a
        re-accept moves only the second.
        """
        operation = _OPERATION_BY_GOAL[goal.name]
        entry     = {"verdict": bool(result.verdict),
                     "report":  str(result.report),
                     "when":    _now(),
                     "host":    this_host()}
        choice_entry = configuration.choice_configuration(choice_name)
        if choice_entry.canonicalisers:
            entry["canonicaliser"] = {name: list(argv) for name, argv
                                      in choice_entry.canonicalisers.items()}
        setup = compare_setup_delta(choice_entry.compare)
        if setup:
            entry["compare"] = setup
        records = tuple(getattr(result.provision, "records", ()) or ())
        if records:
            entry["records"] = [_plain(r) for r in records]
        if coverage is not None:
            entry["coverage"] = str(coverage)

        content    = self.book()
        test_book  = content.setdefault(result.name, {})
        test_book["configuration"] = self._test_facts(configuration)
        choice_key = NO_CHOICE_KEY if choice_name is None else choice_name
        choice_db  = test_book.setdefault("choices", {})
        choice_book = choice_db.setdefault(choice_key, {})
        choice_book["configuration"] = self._choice_facts(choice_entry)
        operation_db = choice_book.setdefault("operations", {})
        if operation == "Accept":
            prior = operation_db.get("Accept")
            entry["first_accept"] = prior.get("first_accept",
                                              prior.get("when")) \
                                    if prior else entry["when"]
        operation_db[operation] = entry
        self._write_book(content)
        return entry

    @staticmethod
    def _test_facts(configuration):
        """
        RETURN: dict, the test application's reproducible facts:
                source file and kind, interpreter, interactive, caps.
        """
        facts = {"source_file": configuration.source_file,
                 "source_kind": str(configuration.source_kind),
                 "interactive": bool(configuration.interactive)}
        if configuration.interpreter is not None:
            facts["interpreter"] = list(configuration.interpreter)
        if configuration.caps is not None:
            facts["caps"] = _plain(configuration.caps)
        return facts

    @staticmethod
    def _choice_facts(choice_entry):
        """
        RETURN: dict, the choice's reproducible facts: the
                canonicalisers and the compare setup's differences.
                Empty facts are absent, not empty.
        """
        facts = {}
        if choice_entry.canonicalisers:
            facts["canonicaliser"] = {name: list(argv) for name, argv
                                      in choice_entry.canonicalisers.items()}
        setup = compare_setup_delta(choice_entry.compare)
        if setup:
            facts["compare"] = setup
        return facts

    # -- queries ------------------------------------------------------
    def tests(self):
        """RETURN: list, every recorded test's name, sorted."""
        return sorted(self.book())

    def choices(self, test):
        """
        RETURN: list, every recorded choice of that test, sorted; None
                stands where the test ran without a choice.
        """
        recorded = self.book().get(test, {}).get("choices", {})
        return sorted((None if key == NO_CHOICE_KEY else key
                       for key in recorded),
                      key=lambda name: (name is not None, name))

    def stderr_note(self, test, choice):
        """
        RETURN: E_StderrNote, what the book says about that choice's
                stderr:

                    IGNORED    whatever happens there, do not worry
                    FORBIDDEN  a word there is an ERROR

                An unnoted choice reads FORBIDDEN: a test that was
                never asked about stderr is one that has never spoken
                there, and the first word it says is news. A book
                written before E-5 may still hold 'nominal' -- unknown
                to this enum, so it reads FORBIDDEN too: the migration
                is silent, and a speaking choice is caught at its next
                run rather than trusted on old say-so.
        """
        key   = NO_CHOICE_KEY if choice is None else choice
        noted = self.book().get(test, {}).get("choices", {}) \
                           .get(key, {}).get("stderr")
        try:
            return E_StderrNote(noted)
        except ValueError:
            return E_StderrNote.FORBIDDEN

    def note_stderr(self, test, choice, note):
        """
        RETURN: E_StderrNote, what now stands in the book for that
                choice -- written verbatim, replacing any earlier note.

        THE NOTE IS THE DECISION, and acceptance is where it is taken.
        STDERR IS NEVER SUBJECT TO TESTING (E-5): noting IGNORED or
        FORBIDDEN removes any nominal stderr that lingers from before
        this ruling, since a stream cannot be both compared and
        disregarded.
        """
        note       = E_StderrNote(note)
        content    = self.book()
        test_book  = content.setdefault(test, {})
        choice_db  = test_book.setdefault("choices", {})
        key        = NO_CHOICE_KEY if choice is None else choice
        choice_db.setdefault(key, {})["stderr"] = note.value
        self._write_book(content)
        #  STDERR IS NEVER SUBJECT TO TESTING (E-5): every remaining
        #  note -- IGNORED or FORBIDDEN -- means no nominal stderr can
        #  stand, so any that lingers is removed, unconditionally.
        path = self.nominal_path(test, choice, "stderr")
        if path.exists(): path.unlink()
        return note

    def result(self, test, choice, operation):
        """
        RETURN: dict, the most recent entry of that operation.
                None, no such entry.
        """
        key = NO_CHOICE_KEY if choice is None else choice
        return self.book().get(test, {}).get("choices", {}) \
                          .get(key, {}).get("operations", {}).get(operation)

    def test_configuration(self, test):
        """
        RETURN: dict, the test's reproducible facts as last recorded.
                None, the test is not in the book.
        """
        return self.book().get(test, {}).get("configuration")

    def choice_configuration(self, test, choice):
        """
        RETURN: dict, the choice's reproducible facts as last recorded.
                None, the choice is not in the book.
        """
        key = NO_CHOICE_KEY if choice is None else choice
        return self.book().get(test, {}).get("choices", {}) \
                          .get(key, {}).get("configuration")

    # -- divergence, ON CALL -------------------------------------------
    def divergence(self, declared_db):
        """
        RETURN: dict, the verdicts on what is recorded but declared no
                longer:
                    'deleted'        -> [test, ...]
                    'non-responsive' -> {test: [choice, ...]}
                Both empty when book and declaration agree.

        'declared_db' maps each declared test's name to its declared
        choice names (None where the test runs without a choice). A
        recorded test absent from it reads DELETED; a recorded choice
        of a declared test absent from its declaration reads
        NON-RESPONSIVE. A declared name never yet recorded raises no
        complaint -- it is simply new.

        Healing is a service (rename, rename-choice, remove,
        remove-choice); this answer never edits the book.
        """
        deleted        = []
        non_responsive = {}
        for test, test_book in sorted(self.book().items()):
            if test not in declared_db:
                deleted.append(test)
                continue
            declared = {NO_CHOICE_KEY if c is None else c
                        for c in declared_db[test]}
            missing  = sorted(key for key in test_book.get("choices", {})
                              if key not in declared)
            if missing:
                non_responsive[test] = \
                    [None if key == NO_CHOICE_KEY else key
                     for key in missing]
        return {E_DIVERGENCE_DELETED:        deleted,
                E_DIVERGENCE_NON_RESPONSIVE: non_responsive}
