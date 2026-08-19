"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE STORE -- every artifact of a test, behind one interface.

DESCRIPTION
       Three worlds are kept apart (README 2.7). This is the second: the
       ARTIFACTS. Records are keyed by (test, choice, subject); the
       default backend is the HWUT GOOD filesystem, and another -- a
       database, an object store -- fits behind the same interface.

       THE NAMING IS THE BOOKKEEPER'S. A Store is constructed OVER a
       Bookkeeper (vut/engine/orchestrator/bookkeeper/) and asks it for
       every path it touches; the key scheme has ONE expression, there.
       The Store triggers the reading and the writing; the Bookkeeper
       answers where. Results and entries are the Bookkeeper's whole
       business -- nothing of them lives here.

       TWO KEY SPACES, ONE WRITER EACH. A candidate is written by
       recording; a nominal is written by acceptance. No key has two
       writers, so 'which step wrote this' never becomes a question a key
       cannot answer.

       THE DIRECTORY IS THE LOCK. 'mkdir' of a lock sub directory either
       creates or fails, so the winner is decided without a second
       mechanism. The lock names its holder as (PROCESS ID, WHEN IT
       STARTED) -- the PAIR identifies, a process id alone does not, since
       the system reuses them. Liveness is ASKED, not inferred from
       elapsed time: no expiry, no heart beat, no clock skew, and a
       crashed run leaves no lock behind it. The mechanism is
       'MkdirMutex' (vut/auxiliary/directory_mutex.py); 'DirectoryLock'
       is its face here, and non-recursive: the live holder locking
       again is refused by name ('DirectoryDeadlock').
______________________________________________________________________________
"""
import json
import os
from   dataclasses import dataclass
from   pathlib     import Path
from .configuration import StoreConfig   # noqa: F401

#  The lock mechanism lives in the auxiliary; these names are part of
#  THIS component's face and are re-exported here.
from   ....auxiliary.directory_mutex import (MkdirMutex,        # noqa: F401
                                            DirectoryBusy,
                                            DirectoryDeadlock,
                                            liveness_can_be_asked,
                                            LOCK_DIRECTORY_NAME)


LOCK_DIRECTORY_NAME = ".hwut-lock"


def _utc_now():
    """RETURN: str, the current UTC instant, seconds resolution,
    ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def source_digest_of(path):
    """
    RETURN: str, the sha256 hex digest of the file's CONTENT -- the
            source identity a freshness sidecar records. Content, not
            path or mtime: the identity survives a checkout and a
            touch alike.
    """
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()
_HOLDER_FILE_NAME   = "holder.json"


class DirectoryLock(MkdirMutex):
    """The access check of ONE test directory: it guards the directory's
    book and its tests' output alike.

    Use as a context manager. Where liveness cannot be asked, the lock is
    a no-op and '.taken' says so. The face of 'MkdirMutex'
    (vut/auxiliary/directory_mutex.py) in this component; mechanism,
    holder record and policies live there.
    """
    pass


class Store:
    """The artifacts of the tests under ONE directory.

    Default backend: the HWUT GOOD filesystem. A record is a file under
    'GOOD/' named for its key; candidates live beside it under 'OUT/'.
    Constructed OVER a Bookkeeper: the directory is the Bookkeeper's,
    and every path is asked of it.
    """

    def __init__(self, bookkeeper, config=None):
        self.bookkeeper = bookkeeper
        self.config     = config

    @property
    def directory(self):
        """RETURN: Path, the ONE directory -- the Bookkeeper's."""
        return Path(self.bookkeeper.directory)

    @property
    def records(self):
        """
        RETURN: True,  a run's subjects are to be kept as candidates.
                False, nothing is recorded.

        Answered by the presence of a StoreConfig: a configuration that
        names no store asks for no recording.
        """
        return self.config is not None

    # -- keys: THE NAMING IS THE BOOKKEEPER'S -------------------------
    def stderr_note(self, test, choice):
        """RETURN: E_StderrNote, what the book says about that choice's
        stderr; FORBIDDEN where nothing is noted."""
        return self.bookkeeper.stderr_note(test, choice)

    def note_stderr(self, test, choice, note):
        """RETURN: E_StderrNote, what now stands in the book."""
        return self.bookkeeper.note_stderr(test, choice, note)

    def nominal_path(self, test, choice, subject):
        """RETURN: Path, where the ACCEPTED record of that key lives."""
        return self.bookkeeper.nominal_path(test, choice, subject)

    def candidate_path(self, test, choice, subject):
        """RETURN: Path, where the CANDIDATE record of that key lives."""
        return self.bookkeeper.candidate_path(test, choice, subject)


    def write_candidate(self, test, choice, subject, text,
                        source_digest=None, instant=None):
        """
        RETURN: Path, where the candidate was written.

        The candidate key space has ONE writer: recording. Beside every
        candidate a FRESHNESS sidecar '<candidate>.when' records the
        instant and the SOURCE IDENTITY -- the digest of the test
        source's content -- so that a later staleness law can be ruled
        without re-recording history. A candidate must be COMPLETE: a
        partial subject of an aborted run is reported, never stored as
        if whole -- refused at the door by the CALLER, which is the only
        place completeness is known.

        'instant' is a parameter so that a test may state the clock.
        """
        path = self.candidate_path(test, choice, subject)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        freshness = {"instant": instant or _utc_now()}
        if source_digest is not None:
            freshness["source_digest"] = source_digest
        with open(str(path) + ".when", "w", encoding="utf-8") as fh:
            json.dump(freshness, fh, sort_keys=True)
        return path

    def accept(self, test, choice, subject, text):
        """
        RETURN: Path, where the nominal was written.

        PROMOTION: this is the only way a nominal comes to exist. The
        nominal key space has ONE writer: acceptance.
        """
        path = self.nominal_path(test, choice, subject)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    def raw_path(self, test, choice, subject):
        """RETURN: Path, where the PRE-canonicalisation stream lives."""
        return self.bookkeeper.raw_path(test, choice, subject)

    def timing_path(self, test, choice, subject):
        """RETURN: Path, where the cadence sidecar of that key lives."""
        return self.bookkeeper.timing_path(test, choice, subject)

    def write_raw(self, test, choice, subject, text):
        """
        RETURN: Path, where the raw stream was written.

        Kept BESIDE the canonicalised record, never instead of it: what
        is compared is the canonicalised one, and the raw is evidence.
        """
        path = self.raw_path(test, choice, subject)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    def write_timing(self, test, choice, subject, delta_list):
        """
        RETURN: Path, where the cadence was written -- one delta per RAW
                line, in raw order.

        SEPARATE FROM THE RECORD by construction, so the pipe into
        compare is untouched. Separateness is a technicality of storage:
        'has this subject a cadence' is answered by 'timing()', and
        nothing above the Store sees a file.
        """
        path = self.timing_path(test, choice, subject)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"unit": "second", "delta_list": list(delta_list)}, fh)
            fh.write("\n")
        return path

    def timing(self, test, choice, subject):
        """
        RETURN: tuple, the recorded per-line deltas of that key.
                None,  none was recorded.

        NOTE the order: the cadence belongs to the RAW stream while the
        record is the CANONICALISED one. Where a canonicaliser reorders,
        the deltas describe the RUN, not the record's lines.
        """
        try:
            with open(self.timing_path(test, choice, subject), "r",
                      encoding="utf-8") as fh:
                return tuple(json.load(fh)["delta_list"])
        except Exception:
            return None

    def lock(self):
        """RETURN: DirectoryLock, the access check of this directory."""
        return DirectoryLock(self.directory)
