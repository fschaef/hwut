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
       under 'GOOD/', candidate under 'TMP/store/', the raw and cadence
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
       Healing is a service (rename, remove), never a guess.

       A missing or damaged base reads as EMPTY: the base is a record,
       and its loss must never fail a run.
______________________________________________________________________________
"""
import csv
import json
import os
import sys
import platform
import stat
from   dataclasses import fields, is_dataclass
from   datetime    import datetime, timezone
from   enum        import Enum
from   pathlib     import Path
from   contextlib  import contextmanager
from .configuration import E_StderrNote, E_TestVerdict, NamingConfig
from .test_id_db import FILE_NAME as _REGISTER_FILE_NAME
from .test_id_db import TestIdDb

#  THE STORE'S GROUND, under the transient root 'TMP/' (services E-24).
#  Re-exported by 'stream_store'.
STORE_DIRECTORY_NAME = "TMP/store"

#  THE BOOK IS A TABLE (B-6): one row per (test, choice, operation), and
#  one row per choice with 'operation' empty for the choice's own facts.
BOOK_FILE_NAME             = "book.csv"
#  Read once, then replaced: a book written before B-6.
#  THE NAMES THE BOOK HAS WORN, newest first: read where the current
#  one does not stand, and gone at the first write (B-10).
LEGACY_BOOK_FILE_TUPLE     = ("result_db.csv", "result_db.json")
#  THE TABLE (B-7, B-8): one row per (test, choice); ';' between cells,
#  never quoted -- a name carrying ';' is refused at the validator. AN
#  EMPTY 'test' CELL MEANS "the same as the row above": an empty name
#  means nothing else, so it needs no mark.
BOOK_SEPARATOR = ";"

#  WHAT A NAME MAY NOT CARRY, because the table would not survive it.
#  THE BOOK NAMES THESE, AND WHOEVER ENFORCES THEM ASKS -- the
#  specification's door refuses a name at the moment it is read
#  ('orchestrator/exploration/validator.py'), and does so from THIS
#  tuple, so a separator that changes here changes there without the
#  bookkeeper knowing who its clients are.
BOOK_FORBIDDEN_IN_NAME = (BOOK_SEPARATOR,)

#  WHAT THE BOOKKEEPER OWNS UNDER 'GOOD/', by name -- the book, the book
#  it replaced, the register. Everything else there is a NOMINAL, an
#  oracle. Whoever walks 'GOOD/' for oracles ('hwut.sanitize',
#  operations' hygiene suite) ASKS THIS, and never carries a list: a
#  file the bookkeeper adds is then skipped everywhere without the
#  bookkeeper knowing who walks.
GOOD_OWNED_FILE_TUPLE = (BOOK_FILE_NAME,) + LEGACY_BOOK_FILE_TUPLE \
                        + (_REGISTER_FILE_NAME,)
#  THE REGISTER'S TWO COLUMNS COME LAST, so that every column standing
#  before this entry keeps its place and an older book reads unchanged
#  (a row ends with its last fact, B-9).
_COLUMN_TUPLE  = ("test", "choice", "verdict", "report", "last_accept",
                  "coverage", "stderr", "stain_repeat_n", "stain_when",
                  "test_id", "choice_id")

NO_CHOICE_KEY       = "<none>"

#  Subject -> the suffix a NOMINAL carries. 'stdout' is spelt hwut
#  1.0's way, because the accepted files of an existing tree carry
#  that name and 1.0 still reads them. A subject absent here keeps
#  its own name.
NOMINAL_SUFFIX_DB   = {"stdout": "txt"}

#  THE SIDECARS a record may carry, by suffix -- the naming's own, so a
#  reader that strips them and a writer that adds them agree.
SIDECAR_SUFFIX_TUPLE = (".raw", ".times", ".when")


def key_parts_of(name):
    """
    RETURN: (test, choice, subject), read back out of a record's file
                name -- the inverse of 'Bookkeeper.key'. 'choice' is
                None for a test without choices. Sidecar suffixes are
                stripped first, so 'test-x.py--basic.txt.when' and
                'test-x.py--basic.txt' both answer
                ('test-x.py', 'basic', 'stdout'); a suffix in
                'SUBJECT_BY_SUFFIX_DB' is read back as its subject.
            None, where the name has no subject part at all.

    THE ONE PLACE THE KEY IS READ, as 'key' is the one place it is
    written. It says nothing about whether the TEST part is a source
    file -- that gate is the caller's, since only the caller knows
    which extensions the tree admits.
    """
    stem = name
    for suffix in SIDECAR_SUFFIX_TUPLE:
        if stem.endswith(suffix): stem = stem[:-len(suffix)]
    remainder, dot, suffix = stem.rpartition(".")
    if not dot: return None
    if "--" in remainder:
        test, _, choice = remainder.partition("--")
    else:
        test, choice = remainder, None
    return test, choice, SUBJECT_BY_SUFFIX_DB.get(suffix, suffix)


def error_witness_name(test, choice):
    """RETURN: str, '<test>--<choice>.err' ('<test>.err' without a
               choice) -- the file name of the error witness.

    The one spelling; 'Bookkeeper.error_witness_path' puts it under
    'OUT/'. Module-level so that a stage holding a configuration and
    no Bookkeeper spells it identically."""
    stem = test if choice is None else "%s--%s" % (test, choice)
    return "%s.err" % stem
#  THE WAY BACK: a reader that finds a file must name the SUBJECT it
#  belongs to, not the suffix it wears. One table, both directions.
SUBJECT_BY_SUFFIX_DB = {suffix: subject
                        for subject, suffix in NOMINAL_SUFFIX_DB.items()}

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



#  THE TABLE CODEC (B-6). The model the accessors answer from stays
#  what it was; only its life on disk is a table.

def _rows_of_model(content):
    """
    YIELD: [0] dict  one row per (test, choice), in that order -- the
                     file is stable under re-writing and a diff honest.
                     The 'test' cell is EMPTY where it repeats the
                     row above (B-9).
    """
    last_test = None
    for test in sorted(content):
        choice_db = content[test].get("choices", {})
        for key in sorted(choice_db, key=lambda k: (k != NO_CHOICE_KEY, k)):
            book  = choice_db[key]
            stain = book.get("stain") or {}
            yield {"test":   "" if test == last_test else test,
                   "choice": "" if key == NO_CHOICE_KEY else key,
                   "verdict":        _verdict_text(book.get("verdict")),
                   "report":         book.get("report") or "",
                   "last_accept":    book.get("last_accept") or "",
                   "coverage":       book.get("coverage") or "",
                   "stderr":         book.get("stderr") or "",
                   "stain_repeat_n": str(stain["repeat_n"])
                                     if "repeat_n" in stain else "",
                   "stain_when":     stain.get("when") or "",
                   #  THE REGISTER'S COLUMNS (B-13): the id of the
                   #  application and the id of the choice. The MARKS
                   #  are not here -- they bound a SCOPE, and a row can
                   #  be removed (B-2).
                   "test_id":        book.get("test_id") or "",
                   "choice_id":      book.get("choice_id") or ""}
            last_test = test


def _model_of_rows(row_iterable):
    """
    RETURN: dict, the model rebuilt from the table's rows -- the exact
            inverse of '_rows_of_model'. An EMPTY 'test' cell is the
            row above's (B-8; B-7's one-day ':' is read the same way);
            an unknown column is ignored and a missing one reads as
            absent. A table with an 'operation' column (the
            one-day shape of B-6) is folded: its 'Run' row is the
            choice's decision, its operation-less row the facts.
    """
    content   = {}
    last_test = None
    for row in row_iterable:
        test = row.get("test") or ""
        if test in ("", ":"): test = last_test or ""
        if not test: continue              # a first row with no name
        last_test = test
        key  = row.get("choice") or NO_CHOICE_KEY
        book = content.setdefault(test, {}).setdefault("choices", {}) \
                      .setdefault(key, {})
        operation = row.get("operation")
        if operation == "Accept":          # B-6's Accept row: its instant
            if row.get("last_accept"): book["last_accept"] = row["last_accept"]
            continue
        if operation is not None and operation not in ("", "Run"):
            continue                       # B-6's Display rows
        if row.get("verdict"):
            book["verdict"] = E_TestVerdict.of_text(row["verdict"])
            book["report"]  = row.get("report") or ""
        for name in ("last_accept", "coverage", "stderr",
                     "test_id", "choice_id"):
            if row.get(name): book[name] = row[name]
        if row.get("stain_repeat_n"):
            book["stain"] = {"repeat_n": int(row["stain_repeat_n"]),
                             "when":     row.get("stain_when") or ""}
        elif row.get("stain"):                          # B-6's one cell
            legacy = _stain_of_text(row["stain"])
            if legacy is not None:
                book["stain"] = {"repeat_n": legacy["repeat_n"],
                                 "when":     legacy["when"]}
    return content


def _model_of_legacy(content):
    """
    RETURN: dict, a pre-B-6 book ('result_db.json') as the model: the
            'Run' operation's verdict and report become the choice's,
            'Accept's instant its 'last_accept'; every configuration
            key is dropped, since it left the book.
    """
    model = {}
    for test, test_book in content.items():
        if not isinstance(test_book, dict): continue
        choice_db = test_book.get("choices", {})
        if not isinstance(choice_db, dict): continue
        for key, choice_book in choice_db.items():
            if not isinstance(choice_book, dict): continue
            out = model.setdefault(test, {}).setdefault("choices", {}) \
                       .setdefault(key, {})
            if "stderr" in choice_book: out["stderr"] = choice_book["stderr"]
            stain = choice_book.get("stain")
            if isinstance(stain, dict) and "repeat_n" in stain:
                out["stain"] = {"repeat_n": stain["repeat_n"],
                                "when":     stain.get("when", "")}
            operation_db = choice_book.get("operations", {})
            if not isinstance(operation_db, dict): continue
            run = operation_db.get("Run")
            if isinstance(run, dict) and "verdict" in run:
                out["verdict"] = _verdict_of_legacy(run["verdict"])
                out["report"]  = run.get("report", "")
                if "coverage" in run: out["coverage"] = run["coverage"]
            accept = operation_db.get("Accept")
            if isinstance(accept, dict) and accept.get("last_accept"):
                out["last_accept"] = accept["last_accept"]
    return model


def _without_register_columns(entry):
    """
    RETURN: dict, a copy of 'entry' whose choices bear no 'test_id' and
            no 'choice_id'; every other field as it stood.

    AN ID IS THE DIRECTORY'S, NEVER THE TEST'S (E-46). An entry handed
    from one directory's book to another still carries the ids the
    source issued, and they mean nothing under the new roof.
    """
    fresh = dict(entry)
    if "choices" not in entry: return fresh
    choice_db = {}
    for key, book in entry["choices"].items():
        book = dict(book)
        book.pop("test_id", None)
        book.pop("choice_id", None)
        choice_db[key] = book
    fresh["choices"] = choice_db
    return fresh


def _verdict_text(verdict):
    """
    RETURN: str, the book's token for 'verdict' -- an E_TestVerdict.
            '' for None: a row that carries no verdict.

    THE ONE PLACE the enum becomes text. A bool never reaches here:
    '_model_of_rows' and the legacy reader hand every verdict over as
    the enum, and 'of_bool' is where a run's bool became one.
    """
    if verdict is None: return ""
    assert isinstance(verdict, E_TestVerdict), repr(verdict)
    return verdict.value


def _verdict_of_legacy(value):
    """
    RETURN: E_TestVerdict, of what a legacy JSON book held under
            'verdict' -- a bool, or already a token.
            None, where it held neither.
    """
    if isinstance(value, E_TestVerdict): return value
    if isinstance(value, bool):          return E_TestVerdict.of_bool(value)
    if isinstance(value, str):           return E_TestVerdict.of_text(value)
    return None


def _bool_text(value):
    """RETURN: str, 'true'/'false' for a bool; '' for None."""
    if value is None: return ""
    return "true" if value else "false"


def _bool_of_text(text):
    """RETURN: bool, of 'true'/'false'; None for anything else."""
    if text == "true":  return True
    if text == "false": return False
    return None



def _stain_of_text(text):
    """RETURN: dict, a stain in B-6's one-cell form '<n>@<when>|...';
    None where malformed. Read only, for a table of that one day."""
    try:
        count, _, rest = text.partition("@")
        when, _, verdicts = rest.partition("|")
        return {"repeat_n":     int(count),
                "when":         when,
                "verdict_list": [v for v in verdicts.split(";") if v]}
    except (ValueError, AttributeError):
        return None

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
    from ..compare.api import Configuration
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


def _subsequence_f(small, large):
    """
    RETURN: bool, True where every line of 'small' stands in 'large' in
            the same order -- 'large' may hold lines between and around
            them, and holds no line of 'small' out of turn.
    """
    it = iter(large)
    return all(line in it for line in small)


def nominal_stands_f(directory, test, choice=None):
    """
    RETURN: True,  an ACCEPTED record of that (test, choice) stands in
                   the directory's GOOD/ -- any subject: 'test--choice.
                   txt', 'test--choice.stderr', ...; and, for any
                   choice, the choice-less form 'test.txt', which is the
                   nominal every choice shares under 'same'. Something
                   was accepted for this case.
            False, nothing does: never accepted, or the nominals were
                   removed.

    THE GATE 'hwut.run' ADMITS BY (E-41): a case with no nominal is not
    run, since a verdict needs something to compare against; a test
    with one accepted choice and one new one runs the first and refuses
    the second, by name. The look is by NAME ONLY and never by the
    book: the book records runs, GOOD/ records acceptance, and only
    the latter is the evidence asked for here.
    """
    good = Path(directory) / "GOOD"
    if not good.is_dir(): return False
    prefix_tuple = (test + ".",) if choice is None \
                   else (test + ".", "%s--%s." % (test, choice))
    for name in os.listdir(str(good)):
        if name in GOOD_OWNED_FILE_TUPLE: continue
        if name.startswith(prefix_tuple): return True
    return False


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

    # -- THE LOCK: the bookkeeper is the locking proxy (B-9) -----------
    @contextmanager
    def held(self):
        """
        RETURN: context manager yielding the DirectoryLock, HELD for the
                whole 'with' -- the way a run holds its directory for a
                session. Inside it every write of this bookkeeper runs
                without taking the lock again (the mutex is
                non-recursive: a second take by the holder raises
                'DirectoryDeadlock').

        Raises DirectoryBusy where ANOTHER LIVE PROCESS holds the
        directory. Where THIS process already holds it, the block runs
        inside that holding and 'None' is yielded: the mutex is the one
        authority on who holds what.
        """
        from .stream_store    import DirectoryLock
        from ...auxiliary.directory_mutex import DirectoryDeadlock
        try:
            lock = DirectoryLock(self.directory)
            lock.__enter__()
        except DirectoryDeadlock:
            #  A HOLDER ABOVE ALREADY HAS IT: this 'held()' is inside
            #  another, and the inner one holds nothing of its own.
            yield None
            return
        try:
            yield lock
        finally:
            lock.__exit__(None, None, None)

    @contextmanager
    def _act(self):
        """
        RETURN: context manager, the critical section of ONE act on the
                directory's records: the lock is taken for its
                duration, unless THIS PROCESS ALREADY HOLDS IT -- a
                holder above ('held()'), a run holding its directory
                for a session, any of them.

        THE MUTEX IS ASKED, NOT A TABLE. 'DirectoryDeadlock' means
        exactly 'you already hold this', which is the holder-above
        case; catching it is how the act learns, and no register of
        holders can drift out of step with the truth. A lock held by
        ANOTHER live process is 'DirectoryBusy' and still raises.
        """
        from .stream_store    import DirectoryLock
        from ...auxiliary.directory_mutex import DirectoryDeadlock
        try:
            lock = DirectoryLock(self.directory)
            lock.__enter__()
        except DirectoryDeadlock:
            yield                      # held above: the act runs inside it
            return
        try:
            yield
        finally:
            lock.__exit__(None, None, None)

    # -- THE REGISTER, read and written through this door only (B-9) --
    def _register(self):
        """
        RETURN: TestIdDb, the register read FRESH -- from the BOOK where
                the book carries the '# vut-register' block, and from
                'GOOD/test_ids.dat' where it does not.

        B-10's MIGRATION, exactly: the old file is read where the
        current place carries nothing, and it goes at the first write. A
        tree from before B-13 needs no migration step; the first write
        makes it.
        """
        content = self.book()
        header  = getattr(self, "_book_header_line_list", [])
        register = TestIdDb.register_of_book(header,
                                             _register_row_iterable(content),
                                             str(self.directory))
        #  THE HEADER DECIDES, NOT THE COUNT. A book that carries the
        #  '#' block IS the register, however many rows bear an id --
        #  none, after the last test was removed, is a legitimate
        #  state (B-14). Falling back on the count resurrected the
        #  removed test from the stale sidecar as an aspirant.
        if header or len(register): return register
        return TestIdDb(str(self.directory))

    def _standing_header_line_list(self):
        """
        RETURN: list[str], the '#' block the book on disk carries.

                An empty list, where it carries none -- a book from
                before B-13, which grows one at its first register write.
        """
        try:
            with open(self.book_path, "r", encoding="utf-8") as fh:
                return [each.rstrip("\n") for each in fh
                        if each.startswith("#")]
        except Exception:                                      # noqa: BLE001
            return []

    def _with_register_columns(self, content):
        """
        RETURN: dict, 'content' with every row's 'test_id' and
                'choice_id' restored from what stands on disk, where the
                row carries none of its own.

                'content' unchanged, where the book on disk carries no
                register at all.
        """
        try:
            standing = self.book()
        except Exception:                                      # noqa: BLE001
            return content
        for test, test_book in content.items():
            was = standing.get(test, {}).get("choices", {})
            for key, book in test_book.get("choices", {}).items():
                for column in ("test_id", "choice_id"):
                    if book.get(column): continue
                    if was.get(key, {}).get(column):
                        book[column] = was[key][column]
        return content

    def _register_bump(self):
        """
        RETURN: None. The register's generation raised by one, and the
                '#' block written.

        A RENAME OR A REMOVAL IS NOW THE ROW'S OWN. The id rides on the
        row, so renaming the book's row renames the register entry and
        removing it retires the id -- there is nothing left for the
        register to do but SAY that it moved. Coverage reads that
        generation to know whether a snapshot still stands (D-25), and
        no mutation may pass without it.
        """
        register = self._register()
        register.generation += 1
        self._register_write(register)

    def _register_write(self, register):
        """
        RETURN: None. The register laid into the book -- the '#' block
                and the two id columns -- and the book written.

        ONE FILE, ONE WRITE (B-9). What was two writes inside one act is
        now one, and the 'two lifetimes' question B-9 left open is
        answered by there being one file.
        """
        content = self.book()
        row_db  = register.book_row_db()
        #  CLEARED FIRST, THEN LAID IN. An id given back (B-4) or a
        #  choice removed is no longer the register's, and its columns
        #  must go with it -- otherwise the book would name an id the
        #  register does not hold, which is a book that cannot be
        #  trusted to bound the next one (B-2).
        for test_book in content.values():
            for book in test_book.get("choices", {}).values():
                for column in ("test_id", "choice_id"):
                    book.pop(column, None)
        for (test, choice), (app_id, choice_id) in row_db.items():
            #  CREATED AS AN ASPIRANT WHERE NO ROW STANDS (B-14). A
            #  row says the choice is KNOWN -- registered, an id
            #  issued -- and no more; whether a nominal stands is asked
            #  of GOOD/ by 'nominal_stands_f', per case. So an id with
            #  no row to sit on makes one, and the row's verdict says
            #  what is true of it: ASPIRANT, never accepted. B-13's
            #  "annotated, never created" is overturned by B-14; it
            #  rested on a row meaning a nominal stands, which it no
            #  longer does.
            choice_db = content.setdefault(test, {}).setdefault("choices", {})
            book = choice_db.get(choice or NO_CHOICE_KEY)
            if book is None:
                book = choice_db[choice or NO_CHOICE_KEY] = \
                       {"verdict": E_TestVerdict.ASPIRANT}
            book["test_id"] = str(app_id)
            book["choice_id"] = "" if choice_id is None else str(choice_id)
        self._write_book(content, register.book_header_line_list())

    def run_id_of(self, test, choice=None, allocate_f=False):
        """
        RETURN: TestRunId, the id of '(test, choice)' -- issued now
                where 'allocate_f' and none stands.
                None, where none stands and none is to be issued.

        The register's 'run_id_of', under the directory's lock where
        it may write.
        """
        if not allocate_f:
            return self._register().run_id_of(test, choice)
        with self._act():
            register = self._register()
            run_id   = register.run_id_of(test, choice, allocate_f=True)
            self._register_write(register)
            return run_id

    def name_of(self, run_id):
        """RETURN: (test, choice), what the id names; None where it
        names nothing (no longer registered, or never)."""
        return self._register().name_of(run_id)

    def roster(self):
        """RETURN: list[str], every registered application name."""
        return self._register().roster()

    def app_iterable(self):
        """RETURN: iterable of (app_id, name, choice tuple), the
        register's applications."""
        return self._register().app_iterable()

    def vanished(self):
        """RETURN: the register's 'vanished': applications registered
        whose source no longer stands."""
        return self._register().vanished()

    def register_generation(self):
        """RETURN: int, the register's generation, bumped per mutation
        (coverage D-25)."""
        return self._register().generation

    def register_text(self):
        """RETURN: str, the register in its own text format -- a
        snapshot for a gather to carry."""
        return self._register().format()

    def give_back(self, run_id):
        """RETURN: None. An id issued for an accept that aborted is handed
        back (B-4) -- the register's 'give_back', under the lock."""
        with self._act():
            register = self._register()
            register.give_back(run_id)
            self._register_write(register)

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

        THE STDOUT NOMINAL IS SPELT '.txt' -- hwut 1.0's name, and the
        name every accepted file of an existing tree already carries.
        A NOMINAL IS THE SHARED GROUND between the two frameworks: 1.0
        reads these files today and must keep reading them, so 2.0
        asks for them under the name they have.

        EVERY OTHER SUBJECT KEEPS ITS OWN ('.stderr', a declared
        output file's): 1.0 named ONE file per choice and has no word
        for the rest, so there is nothing to be compatible with, and
        two subjects under one name would collide.

        CANDIDATES ARE UNAFFECTED. The store is 2.0's own ground, no
        other framework reads it, and there the subject names itself.
        """
        nominal_choice = None if self.naming.same_nominal_f else choice
        return self.directory / "GOOD" \
               / self.key(test, nominal_choice, NOMINAL_SUFFIX_DB
                                                .get(subject, subject))

    def candidate_path(self, test, choice, subject):
        """RETURN: Path, where the CANDIDATE record of that key lives:
                   'OUT/<key>.txt' for stdout, 'OUT/<key>.<subject>'
                   for every other.

        'OUT/' WITNESSES THE LAST RUN. The candidate IS the run's
        product and belongs beside the rest of it, under the name the
        nominal carries -- 'OUT/x--c.txt' against 'GOOD/x--c.txt', one
        spelling, and a reader compares two files whose names agree.

        THE SIDECARS DO NOT FOLLOW IT. '.raw', '.times', '.when' and
        '.cover' stay on the store's ground: they were the CHANNEL,
        mattering while the stream was being taken, and they are not
        the product. They are machine-local observations (E-36) and
        nothing off this host reads them.

        SUPERSEDES O-8 IN PART. O-8 moved candidates off 'OUT/'
        because execution DISCOVERED every file there as a subject, so
        a run ingested the previous run's candidates. R-71 retired
        discovery -- subjects are DECLARED -- and the reason went with
        it. What O-8 keeps: the sidecars, and 'OUT/' being the test's
        space rather than the framework's scratch."""
        return self.directory / "OUT" \
                              / self.key(test, choice, NOMINAL_SUFFIX_DB
                                                       .get(subject, subject))

    def error_witness_path(self, test, choice):
        """RETURN: Path, 'OUT/<key>.err' -- where the LAST RUN's stderr
                   stands, if it stood at all.

        NOT A SUBJECT (E-5): never a nominal, never compared, never
        pype-d, never recorded through the store. The run clears it
        before it launches and writes it only where stderr spoke, so
        its PRESENCE is the statement. This is the ONE place its name
        is spelt; 'error_witness_name' is the same spelling for a
        caller that has no Bookkeeper in hand."""
        return self.directory / "OUT" / error_witness_name(test, choice)

    def _store_path(self, test, choice, subject):
        """RETURN: Path, the STORE'S ground for the sidecars of that
                   key -- 'TMP/store/<key>.<subject>', the stem the
                   '.raw', '.times' and '.when' suffixes hang from.

        Not a record and never read as one: it names no file of its
        own, only the stem its sidecars extend."""
        return self.directory / STORE_DIRECTORY_NAME \
                              / self.key(test, choice, subject)

    def coverage_path(self, test, choice):
        """RETURN: Path, where the COVERAGE RECORD of that run lives --
        'TMP/store/<key>.cover', the store's own ground: a measurement
        of the last run of that choice, never a nominal, never a
        subject. The suffix is coverage's own ('affected.py')."""
        return self.directory / STORE_DIRECTORY_NAME \
                              / self.key(test, choice, "cover")

    def raw_path(self, test, choice, subject):
        """RETURN: Path, where the PRE-canonicalisation stream lives --
                   on the STORE'S ground, not beside the candidate."""
        path = self._store_path(test, choice, subject)
        return path.with_suffix(path.suffix + ".raw")

    def timing_path(self, test, choice, subject):
        """RETURN: Path, where the cadence sidecar of that key lives --
                   on the STORE'S ground, not beside the candidate."""
        path = self._store_path(test, choice, subject)
        return path.with_suffix(path.suffix + ".times")

    def freshness_path(self, test, choice, subject):
        """RETURN: Path, where the freshness sidecar of that key lives
                   -- the instant and the source digest, on the
                   STORE'S ground."""
        path = self._store_path(test, choice, subject)
        return path.with_suffix(path.suffix + ".when")

    def outdated_f(self, test, choice, subject, source_path):
        """
        RETURN: True, where the recorded candidate is OLDER than the
                      test file that produced it -- the application
                      has been edited since the run that recorded it,
                      so what stands in the store describes a test
                      that no longer exists
                False, where the candidate is at least as new as its
                      source, and where EITHER file cannot be stat'ed
                      (an unreadable clock accuses nobody, and a
                      missing candidate is a different complaint with
                      its own words).

        MTIME, NOT CONTENT. A test whose text changed and whose output
        did not is still a test that must be RE-RUN before anything is
        blessed: the store's business is what THIS text produced, and
        only running it can say. Comparing content would answer a
        different question, and answer it too late.

        THE SOURCE IS ONE FILE, not a closure. What a test reads --
        its configuration, its pype script, the library under test --
        is not walked here: an mtime check that tried to be complete
        would be a build system, and being nearly complete is worse
        than being plainly one file, because a reader would trust it.
        """
        try:
            candidate = self.candidate_path(test, choice, subject)
            return os.stat(str(source_path)).st_mtime \
                   > os.stat(str(candidate)).st_mtime
        except OSError:
            return False

    def shape_of(self, test, choice, subject="stdout"):
        """
        RETURN: str, WHERE TO LOOK in a difference the RUN already
                found, read afterwards from the candidate and nominal
                WHOLE (B-5):
                'not-equivalent-grew'      every recorded line still
                                           stands, in order, and lines
                                           stand between or around them
                'not-equivalent-shrank'    every line that stands was
                                           recorded, in order, and lines
                                           the GOOD holds are gone
                'not-equivalent-diverged'  neither: a recorded line
                                           changed or moved
                'not-equivalent-with-nominal'
                                           the shape IS NOT CLAIMED: a
                                           file is missing or cannot be
                                           read, so the run's own word
                                           stands

        THIS IS THE REPORT'S TO SAY, NOT THE RUN'S (E-31). Comparison
        aborts at the first difference it can state and consumes no
        further input, so at verdict time neither text has been read
        whole. GREW and SHRANK are claims ABOUT THE WHOLE TEXT; only a
        reader that has both files entire may make them, and only
        where the stored candidate IS the whole output.

        ALL FOUR ARE FAIL. The shape says nothing about WHICH SIDE is
        wrong: a GOOD blessed under a framework that swallowed output
        grows, and so does a filter that stopped filtering. One is
        stale ground, the other is the defect a golden master exists
        to catch, and they wear the same shape. Only the reader
        decides.

        THIS METHOD, NOT A STANDALONE FUNCTION (B-5): its only two
        inputs, the candidate and the nominal, are paths this
        Bookkeeper already names; a caller elsewhere kept its own copy
        of the same two-file read, which is the one law this method
        removes a second place from.
        """
        candidate_path = self.candidate_path(test, choice, subject)
        nominal_path   = self.nominal_path(test, choice, subject)
        try:
            with open(candidate_path, encoding="utf-8",
                     errors="replace") as fh:
                new = fh.read().splitlines()
            with open(nominal_path, encoding="utf-8",
                     errors="replace") as fh:
                old = fh.read().splitlines()
        except OSError:
            return "not-equivalent-with-nominal"
        if len(new) > len(old) and _subsequence_f(old, new):
            return "not-equivalent-grew"
        if len(old) > len(new) and _subsequence_f(new, old):
            return "not-equivalent-shrank"
        return "not-equivalent-diverged"

    # -- the base -----------------------------------------------------
    @property
    def book_path(self):
        """RETURN: Path, the ONE book of this directory."""
        return self.directory / "GOOD" / BOOK_FILE_NAME

    def legacy_book_path(self):
        """RETURN: Path, a book under a name the tree has retired, the
                newest such name first; None where none stands.

        The book is read from it once and written to 'book.csv'; the
        old file is removed on that write (B-10)."""
        for name in LEGACY_BOOK_FILE_TUPLE:
            path = self.directory / "GOOD" / name
            if path.exists(): return path
        return None

    def book(self):
        """
        RETURN: dict, the whole base as the MODEL every accessor answers
                from: test -> {'choices': {key -> {'operations': {op ->
                {'verdict', 'report', ...}}, 'stderr'?, 'stain'?}}}.
                Empty when nothing was recorded.

        THE MODEL IS PRIVATE (B-6, E-37): its shape is answered
        through 'tests()', 'choices()', 'result()', 'stain()',
        'stderr_note()'; a reader that indexes it directly is reading
        past the door.

        A missing or unreadable base reads as empty: the base is a
        record, and its loss must never fail a run. A book written
        before B-6 ('result_db.json') is read where no '.csv' stands,
        its configuration dropped on the way in.
        """
        path = self.book_path
        if not path.exists():
            path = self.legacy_book_path()
            if path is None: return {}
        if path.suffix == ".json":
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    content = json.load(fh)
            except Exception:
                return {}
            return _model_of_legacy(content) if isinstance(content, dict) \
                   else {}
        try:
            with open(path, "r", encoding="utf-8", newline="") as fh:
                line_list = fh.read().splitlines()
        except Exception:
            return {}
        try:
            #  THE '#' BLOCK IS NOT A COMMENT. A gnuplot '#' line may be
            #  skipped; this one carries the register's scope-wide facts
            #  and is held aside for 'register_of_book' to read. It is
            #  kept OUT of the csv reader, which would otherwise take it
            #  for a row.
            self._book_header_line_list = [each for each in line_list
                                           if each.startswith("#")]
            body = [each for each in line_list if not each.startswith("#")]
            if not body: return {}
            #  B-6's one-day table was ','-separated with an
            #  'operation' column; told apart by its header,
            #  read once, rewritten as B-7 on the next write.
            delimiter = BOOK_SEPARATOR if BOOK_SEPARATOR in body[0] \
                        else ","
            return _model_of_rows(csv.DictReader(body, delimiter=delimiter))
        except Exception:
            return {}

    def _write_book(self, content, header_line_list=None):
        """
        RETURN: None. The whole base, replaced atomically and left
                write-protected.

        Unprotect, write beside, replace, re-protect: a reader never
        meets a half-written base, and a careless hand never meets a
        writable one.
        """
        #  THE REGISTER'S COLUMNS ARE CARRIED OVER (B-13). One file
        #  means a caller may have read the book, caused an id to be
        #  issued, and then written back the copy it read -- which knows
        #  nothing of that id. A row that carries no id here, and did on
        #  disk, KEEPS the one on disk: this write is about the caller's
        #  facts, never about forgetting the register's.
        content = self._with_register_columns(content)
        #  THE '#' BLOCK IS CARRIED OVER TOO, for the same reason: a
        #  caller writing its own facts must not drop the register's.
        #  Only a register write states one of its own.
        if header_line_list is None:
            header_line_list = self._standing_header_line_list()
        path = self.book_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR
                           | stat.S_IRGRP | stat.S_IROTH)
        temporary = path.with_suffix(".csv.tmp")
        with open(temporary, "w", encoding="utf-8", newline="") as fh:
            for line in header_line_list:
                fh.write(line + "\n")
            fh.write(BOOK_SEPARATOR.join(_COLUMN_TUPLE) + "\n")
            for row in _rows_of_model(content):
                #  A ROW ENDS WITH ITS LAST FACT (B-9): trailing empty
                #  cells are not written; a middle one keeps its place.
                cells = [str(row.get(name, "")) for name in _COLUMN_TUPLE]
                while cells and cells[-1] == "": cells.pop()
                fh.write(BOOK_SEPARATOR.join(cells) + "\n")
        os.replace(temporary, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        #  ONE BOOK, NEVER TWO (B-6, B-10): a book under a retired name
        #  ('result_db.csv', 'result_db.json'), once read and written
        #  here, is removed.
        while True:
            legacy = self.legacy_book_path()
            if legacy is None: break
            try:
                os.chmod(legacy, stat.S_IRUSR | stat.S_IWUSR)
                legacy.unlink()
            except OSError:
                break
        #  ONE REGISTER, NEVER TWO (B-13, B-14): once the book carries
        #  the '#' block, the legacy sidecar has been read for the last
        #  time, and goes -- B-10's rule, applied to the register.
        if header_line_list:
            sidecar = self.directory / "GOOD" / _REGISTER_FILE_NAME
            if sidecar.exists():
                try:
                    os.chmod(sidecar, stat.S_IRUSR | stat.S_IWUSR)
                    sidecar.unlink()
                except OSError:
                    pass

    # -- recording ----------------------------------------------------
    def record(self, result, configuration, goal, choice_name=None,
               coverage=None):
        """RETURN: what '_record_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            return self._record_unlocked(
                       result=result, configuration=configuration, goal=goal, choice_name=choice_name, coverage=coverage)

    def _record_unlocked(self, result, configuration, goal, choice_name=None,
               coverage=None):
        """
        RETURN: dict, the entry as written -- DECISIONS ONLY (E-20).
                What the run merely observed -- its duration, its
                telemetry, the host and the instant -- is written to
                the LOCAL observation database instead (E-22), which
                this method also does, so no caller has to remember
                either.

        'coverage' is the coverage step's token ('E_CoverageResult'),
        written as 'coverage' on the entry; None where none was asked,
        and then the key is absent -- absence is data.

        DERIVED, not handed in: the verdict and the report token from
        the result; both halves of freeing from the choice's
        configuration (the canonicaliser changed the RECORD, the
        compare setup changed the VERDICT -- without them a later
        reader cannot tell what this entry meant).

        THE ATTRIBUTION IS AN OBSERVATION and goes to the local
        database: the record of the process that produced a result is
        part of that result, and a run makes it again, identically.

        OVERWRITES exactly one (test, choice, operation) entry and
        leaves every other untouched. No configuration rides with it
        (B-6).

        AN ACCEPT KEEPS ITS INSTANT (E-36): 'last_accept' says when the
        NOMINAL NOW STANDING was blessed -- a fact about the oracle in
        front of the reader. A re-accept moves it, because a re-accept
        produced the nominal that now stands. Every EARLIER acceptance
        is history, and history is the configuration management
        system's: git holds each one, dated and attributed.
        """
        operation = _OPERATION_BY_GOAL[goal.name]
        #  THE BASE HOLDS DECISIONS (E-20). 'when', 'host' and the
        #  attribution 'records' were all things a run can MAKE AGAIN
        #  identically, and went to the local observation database
        #  (E-22); what stays is what a later reader cannot reproduce:
        #  the verdict, the report, the acceptance's instant, and the
        #  configuration that says what the entry meant.
        entry     = {"verdict": E_TestVerdict.of_bool(result.verdict),
                     "report":  str(result.report)}
        #  NO CONFIGURATION IN THE BOOK (B-6): what held is the same
        #  commit's header and 'hwut.conf', which git versions with
        #  this file. A copy here was read by nobody and churned with
        #  every moved default.
        records = tuple(getattr(result.provision, "records", ()) or ())
        #  WHAT THIS MACHINE MERELY OBSERVED goes to the local database
        #  (E-22), not here: a run can make it again. The book keeps the
        #  decisions.
        self._note_observation(result, operation, choice_name, records)
        if coverage is not None:
            entry["coverage"] = str(coverage)

        content    = self.book()
        test_book  = content.setdefault(result.name, {})
        choice_key = NO_CHOICE_KEY if choice_name is None else choice_name
        choice_db  = test_book.setdefault("choices", {})
        choice_book = choice_db.setdefault(choice_key, {})
        #  ONE ROW PER CHOICE (B-7): the verdict and report are THE
        #  choice's, of its last run; an operation is not a dimension
        #  of a decision.
        choice_book["verdict"] = entry["verdict"]
        choice_book["report"]  = entry["report"]
        if "coverage" in entry: choice_book["coverage"] = entry["coverage"]
        if operation == "Accept":
            #  'last_accept' IS THE ONLY INSTANT LEFT IN THE BASE, and
            #  belongs here because ACCEPTANCE IS A DECISION: it says
            #  WHEN THE STANDING NOMINAL WAS BLESSED, which is a fact
            #  about the oracle in front of the reader, not about any
            #  run. HISTORY IS THE CONFIGURATION MANAGEMENT SYSTEM'S:
            #  git holds every earlier acceptance of this file, dated,
            #  attributed and undoable, and the book need not keep a
            #  second, poorer copy (E-36).
            entry["last_accept"] = _now()
            choice_book["last_accept"] = entry["last_accept"]
        self._write_book(content)
        return entry

    def _note_observation(self, result, operation, choice_name, records):
        """
        RETURN: None. The run's telemetry written to the LOCAL
                observation database, under '(test, choice, operation)'
                -- state now, overwritten (E-22, E-23).

        A fault writing it is SWALLOWED: an observation nobody can
        store costs a re-run and nothing else, and must never make a
        recorded verdict fail.
        """
        from .observation import ObservationDb, observation_of
        from .traces      import TraceDb
        observation = observation_of(records[-1] if records else None,
                                     host=this_host(),
                                     compare_complete_f=getattr(
                                         result, "compare_complete_f",
                                         None))
        try:
            ObservationDb(self.directory).note(
                result.name, choice_name, operation, observation)
        except Exception as fault:                          # noqa: BLE001
            #  Said once on stderr, never raised: the verdict stands.
            print("NOTE: local observation not written -- %s" % fault,
                  file=sys.stderr)
        #  THE TRAVELLING HALF (B-11): what a run COST, per machine
        #  class, beside the tests. Silent on failure by construction.
        TraceDb(self.directory).note(
            result.name, choice_name, operation,
            duration_ms    = observation.duration_ms,
            cpu_time_ms    = observation.cpu_time_ms,
            peak_memory_mb = observation.peak_memory_mb)



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
        """RETURN: what '_note_stderr_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            return self._note_stderr_unlocked(
                       test=test, choice=choice, note=note)

    def _note_stderr_unlocked(self, test, choice, note):
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

    def note_accept(self, test, choice):
        """RETURN: what '_note_accept_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            result = self._note_accept_unlocked(
                         test=test, choice=choice)
            #  AN ID IS BORN AT THE FIRST ACCEPT (README 4): issued
            #  here, in the acceptance's own act (E-41).
            register = self._register()
            register.run_id_of(test, choice, allocate_f=True)
            self._register_write(register)
            return result

    def _note_accept_unlocked(self, test, choice):
        """
        RETURN: str, the instant now standing as 'last_accept' for that
                choice -- written into its row, which is created where
                none stood.

        ACCEPTANCE IS A DECISION AND THE BOOK HOLDS DECISIONS (E-20,
        E-36): whoever makes a nominal stand enters it here, or the
        book says "accepted outside the book" ('hwut.sanitize --books',
        E-41). 'hwut.accept' calls this beside 'Store.accept()'; the
        engine's NOMINAL goal reaches the same row through 'record()'.
        A fresh acceptance means the candidate IS the nominal, so the
        row's verdict reads true and its report 'ok'.
        """
        content   = self.book()
        test_book = content.setdefault(test, {})
        choice_db = test_book.setdefault("choices", {})
        key       = NO_CHOICE_KEY if choice is None else choice
        row       = choice_db.setdefault(key, {})
        row["verdict"]     = E_TestVerdict.PASS
        row["report"]      = "ok"
        row["last_accept"] = _now()
        self._write_book(content)
        return row["last_accept"]

    # -- THE STAIN: a test that switched results is disqualified ------
    def stain(self, test, choice):
        """
        RETURN: dict, the stain standing on that choice -- 'repeat_n',
                'when' and the 'verdict_list' that convicted it.
                None, the choice is clean.

        A STAIN IS A DISQUALIFICATION, not a failure. A test that came
        out 'ok' in one repeat and not in another has borne FALSE
        WITNESS about the unit beneath it, and bears it until it is
        proven steady over at least as many repeats as convicted it
        ('hwut.stability'). Until then the choice is not run at all:
        there is nothing to learn from asking a liar again.
        """
        key = NO_CHOICE_KEY if choice is None else choice
        return self.book().get(test, {}).get("choices", {}) \
                          .get(key, {}).get("stain")

    def note_stain(self, test, choice, repeat_n, verdict_list):
        """RETURN: what '_note_stain_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            return self._note_stain_unlocked(
                       test=test, choice=choice, repeat_n=repeat_n, verdict_list=verdict_list)

    def _note_stain_unlocked(self, test, choice, repeat_n, verdict_list):
        """
        RETURN: dict, the stain now standing -- replacing any earlier
                one, so a fresh conviction states the fresh count.

        'repeat_n' is what it takes to clear it: a later proof must
        repeat AT LEAST as often, or it has not answered the charge.
        """
        content   = self.book()
        test_book = content.setdefault(test, {})
        choice_db = test_book.setdefault("choices", {})
        key       = NO_CHOICE_KEY if choice is None else choice
        #  THE DECISION ALONE (B-7): the verdicts that convicted are
        #  what this machine saw, and are not the book's.
        stain     = {"repeat_n": int(repeat_n), "when": _now()}
        choice_db.setdefault(key, {})["stain"] = stain
        self._write_book(content)
        return stain

    def clear_stain(self, test, choice):
        """RETURN: what '_clear_stain_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            return self._clear_stain_unlocked(
                       test=test, choice=choice)

    def _clear_stain_unlocked(self, test, choice):
        """
        RETURN: dict, the stain that is gone.
                None, none stood.

        THE ONLY WAY OUT BESIDE REMOVAL. 'hwut.stability' clears it
        having repeated at least as often as the conviction and found
        every verdict alike; nothing else does -- not a run, not an
        acceptance, not the passage of time.
        """
        content   = self.book()
        choice_db = content.get(test, {}).get("choices", {})
        key       = NO_CHOICE_KEY if choice is None else choice
        gone      = choice_db.get(key, {}).pop("stain", None)
        if gone is not None: self._write_book(content)
        return gone

    # -- RENAME: the book re-keys; NO RECORD CONTENT IS TOUCHED -------
    def rename_test(self, test, fresh):
        """RETURN: what '_rename_test_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            result = self._rename_test_unlocked(
                         test=test, fresh=fresh)
            #  THE NAME FOLLOWS IN THE REGISTER; the id stands (B-2).
            self._register_bump()
            return result

    def _rename_test_unlocked(self, test, fresh):
        """
        RETURN: dict, the entry now standing under 'fresh'.
                None, the test was not in the book.

        Raises KeyError where 'fresh' already stands: a rename that
        would swallow another test's history is refused, never merged.

        THE ENTRY MOVES WHOLE -- its configuration, its choices, their
        operations, their stderr notes and any STAIN. A rename is not
        a fresh start: what the test did under its old name it did.
        """
        content = self.book()
        if test not in content:                    return None
        if fresh in content:
            raise KeyError("'%s' already stands in the book" % fresh)
        content[fresh] = content.pop(test)
        self._write_book(content)
        return content[fresh]

    def rename_choice(self, test, choice, fresh):
        """RETURN: what '_rename_choice_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            result = self._rename_choice_unlocked(
                         test=test, choice=choice, fresh=fresh)
            self._register_bump()
            return result

    def _rename_choice_unlocked(self, test, choice, fresh):
        """
        RETURN: dict, the choice entry now standing under 'fresh'.
                None, the choice was not in the book.

        Raises KeyError where 'fresh' already stands among that test's
        choices.
        """
        content   = self.book()
        choice_db = content.get(test, {}).get("choices", {})
        key       = NO_CHOICE_KEY if choice is None else choice
        new_key   = NO_CHOICE_KEY if fresh is None else fresh
        if key not in choice_db:                   return None
        if new_key in choice_db:
            raise KeyError("'%s' already stands among the choices of "
                           "'%s'" % (fresh, test))
        choice_db[new_key] = choice_db.pop(key)
        self._write_book(content)
        return choice_db[new_key]

    def adopt(self, test, entry):
        """RETURN: what '_adopt_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            result = self._adopt_unlocked(
                         test=test, entry=entry)
            #  THE TARGET ISSUES fresh ids for every choice adopted
            #  (E-46): ids are the directory's.
            register = self._register()
            for choice in self.choices(test) or [None]:
                register.run_id_of(test, choice, allocate_f=True)
            self._register_write(register)
            return result

    def _adopt_unlocked(self, test, entry):
        """
        RETURN: dict, the entry now standing under 'test' -- the entry
                given, minus the ids the source issued, written into
                this book whole.

        Raises KeyError where 'test' already stands: a history adopted
        onto a live name would swallow the one that stood.

        THE OTHER HALF OF 'remove_test' (E-46, services): the entry a
        source directory's book gave up is taken in by the target's,
        with its configuration, its choices, their operations, their
        stderr notes and any STAIN. What the test did under its old
        roof it did.

        THE IDS DO NOT COME WITH IT. An id is the DIRECTORY's, never
        the test's (E-46), and 'adopt' issues fresh ones the moment
        this returns. Carried in, they would be written onto rows of a
        book that bears no '# vut-register' block -- the one shape
        'TestIdDb.register_of_book' refuses, since a book naming ids it
        cannot bound would issue one twice (B-2). The refusal would
        land INSIDE the act, after the write, with the artefacts
        already moved.
        """
        content = self.book()
        if test in content:
            raise KeyError("'%s' already stands in the book" % test)
        content[test] = _without_register_columns(entry)
        self._write_book(content)
        return content[test]

    # -- REMOVAL: the book forgets, that a fresh record may be made ---
    def remove_test(self, test):
        """RETURN: what '_remove_test_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            result = self._remove_test_unlocked(
                         test=test)
            #  THE REGISTER IN THE SAME ACT (B-9): the id retired,
            #  never reissued (B-2).
            self._register_bump()
            return result

    def _remove_test_unlocked(self, test):
        """
        RETURN: dict, the test's whole book entry that is gone.
                None, the test was not in the book.

        THE BOOK ONLY. Nominals, candidates and the register are other
        people's ground; the face that removes a test walks them in
        its own order and this is one step of it.
        """
        content = self.book()
        gone    = content.pop(test, None)
        if gone is not None: self._write_book(content)
        return gone

    def remove_choice(self, test, choice):
        """RETURN: what '_remove_choice_unlocked' returns -- the same act, under
        the directory's lock (B-9).
        """
        with self._act():
            result = self._remove_choice_unlocked(
                         test=test, choice=choice)
            self._register_bump()
            return result

    def _remove_choice_unlocked(self, test, choice):
        """
        RETURN: dict, the choice's book entry that is gone.
                None, the choice was not in the book.

        The test's own entry stands, its other choices with it. A test
        whose LAST choice is removed keeps an empty 'choices' map: the
        configuration it recorded is still true, and 'remove_test' is
        the verb for wanting none of it.
        """
        content   = self.book()
        choice_db = content.get(test, {}).get("choices", {})
        key       = NO_CHOICE_KEY if choice is None else choice
        gone      = choice_db.pop(key, None)
        if gone is not None: self._write_book(content)
        return gone

    def result(self, test, choice):
        """
        RETURN: dict, the choice's decision as last recorded --
                'verdict', 'report', and 'last_accept' / 'coverage'
                where they stand.
                None, no such choice was ever recorded.
        """
        key   = NO_CHOICE_KEY if choice is None else choice
        book  = self.book().get(test, {}).get("choices", {}).get(key)
        if book is None or "verdict" not in book: return None
        return {name: book[name] for name in
                ("verdict", "report", "last_accept", "coverage")
                if name in book}



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

        Healing is a service (rename, remove); this answer never
        edits the book.
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


def _register_row_iterable(content):
    """
    RETURN: iterable of dict, one row per (test, choice) of the book's
            model, carrying the register's columns -- what
            'TestIdDb.register_of_book' reads.

    The model is nested; the register reads rows. This flattens it in
    the table's own order, which is what the marks-on-the-first-row rule
    depends on (B-8).
    """
    for test in sorted(content):
        for choice in sorted(content[test].get("choices", {})):
            book = content[test]["choices"][choice]
            yield {"test":        test,
                   "choice":      "" if choice == NO_CHOICE_KEY else choice,
                   "test_id":     book.get("test_id", ""),
                   "choice_id":   book.get("choice_id", ""),
                   }
