"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE STORE -- every artifact of a test, behind one interface.

DESCRIPTION
       Three worlds are kept apart (README 2.7). This is the second: the
       ARTIFACTS. Records are keyed by (test, choice, subject); the
       default backend is the HWUT GOOD filesystem, and another -- a
       database, an object store -- fits behind the same interface.

       TWO KEY SPACES, ONE WRITER EACH. A candidate is written by
       recording; a nominal is written by acceptance. No key has two
       writers, so 'which step wrote this' never becomes a question a key
       cannot answer.

       BESIDE THE RECORDS, THE FOOTPRINTS: what happened, most recently,
       per test and choice. JSON, ONE FILE PER TEST DIRECTORY, one entry
       per test, one sub-entry per operation. NOT A HISTORY -- exactly one
       entry per (test, choice, operation), overwritten. What was done
       before is the concern of the software configuration management
       system, never of this one.

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
import platform
from   dataclasses import dataclass
from   datetime    import datetime, timezone
from   pathlib     import Path

from   .nominal import RecordNominal
#  The lock mechanism lives in the auxiliary; these names are part of
#  THIS component's face and are re-exported here.
from   ...auxiliary.directory_mutex import (MkdirMutex,        # noqa: F401
                                            DirectoryBusy,
                                            DirectoryDeadlock,
                                            liveness_can_be_asked,
                                            LOCK_DIRECTORY_NAME)


FOOTPRINT_FILE_NAME = "hwut-footprints.json"
LOCK_DIRECTORY_NAME = ".hwut-lock"
_HOLDER_FILE_NAME   = "holder.json"


@dataclass(frozen=True)
class StoreConfig:
    """WHERE and HOW MUCH is kept. Held verbatim by the test's
    configuration (README 2.7); None there means: do not record."""
    directory:     str
    record_raw:    bool = False   # keep the pre-canonicalisation stream
    record_timing: bool = False   # keep per-line delta times


def this_host():
    """
    RETURN: str, a host tag for a footprint, 'linux-x86_64/<node>'.

    Coarse on purpose: it exists to compare compute speed between hosts,
    not to identify a machine.
    """
    return "%s-%s/%s" % (platform.system().lower(), platform.machine(),
                         platform.node())


def _now():
    """RETURN: str, the current UTC instant, seconds resolution, ISO."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DirectoryLock(MkdirMutex):
    """The access check of ONE test directory: it guards the directory's
    footprint file and its tests' output alike.

    Use as a context manager. Where liveness cannot be asked, the lock is
    a no-op and '.taken' says so. The face of 'MkdirMutex'
    (vut/auxiliary/directory_mutex.py) in this component; mechanism,
    holder record and policies live there.
    """
    pass


class Store:
    """Records and footprints of the tests under ONE directory.

    Default backend: the HWUT GOOD filesystem. A record is a file under
    'GOOD/' named for its key; candidates live beside it under 'OUT/'.
    """

    def __init__(self, directory, config=None):
        self.directory = Path(directory)
        self.config    = config

    @property
    def records(self):
        """
        RETURN: True,  a run's subjects are to be kept as candidates.
                False, nothing is recorded.

        Answered by the presence of a StoreConfig: a configuration that
        names no store asks for no recording.
        """
        return self.config is not None

    # -- keys ---------------------------------------------------------
    def _key(self, test, choice, subject):
        """
        RETURN: str, the file name of one record: 'test--choice.subject'
                for a test with choices, 'test.subject' without.
        """
        stem = test if choice is None else "%s--%s" % (test, choice)
        return "%s.%s" % (stem, subject)

    def nominal_path(self, test, choice, subject):
        """RETURN: Path, where the ACCEPTED record of that key lives."""
        return self.directory / "GOOD" / self._key(test, choice, subject)

    def candidate_path(self, test, choice, subject):
        """RETURN: Path, where the CANDIDATE record of that key lives."""
        return self.directory / "OUT" / self._key(test, choice, subject)

    # -- records ------------------------------------------------------
    def nominal(self, test, choice, subject):
        """
        RETURN: Nominal, a reader over the accepted record of that key.

        Opened lazily, so a key with no record yet is named without fault
        and reported by whoever needed to read it.
        """
        return RecordNominal(self.nominal_path(test, choice, subject))

    def candidate(self, test, choice, subject):
        """RETURN: Nominal, a reader over the candidate record."""
        return RecordNominal(self.candidate_path(test, choice, subject))

    def write_candidate(self, test, choice, subject, text):
        """
        RETURN: Path, where the candidate was written.

        The candidate key space has ONE writer: recording.
        """
        path = self.candidate_path(test, choice, subject)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
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
        return self.candidate_path(test, choice, subject).with_suffix(
                   self.candidate_path(test, choice, subject).suffix + ".raw")

    def timing_path(self, test, choice, subject):
        """RETURN: Path, where the cadence sidecar of that key lives."""
        return self.candidate_path(test, choice, subject).with_suffix(
                   self.candidate_path(test, choice, subject).suffix + ".times")

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

    # -- footprints ---------------------------------------------------
    @property
    def footprint_path(self):
        """RETURN: Path, the ONE footprint file of this directory."""
        return self.directory / FOOTPRINT_FILE_NAME

    def footprints(self):
        """
        RETURN: dict, every footprint of this directory, test -> choice ->
                operation -> facts. Empty when none were written.

        A missing or unreadable file reads as empty: a footprint is a
        convenience, and its loss must never fail a run.
        """
        try:
            with open(self.footprint_path, "r", encoding="utf-8") as fh:
                content = json.load(fh)
        except Exception:
            return {}
        return content if isinstance(content, dict) else {}

    def footprint(self, test, choice, operation):
        """
        RETURN: dict, the most recent facts of that operation.
                None, no such footprint.
        """
        key = "<none>" if choice is None else choice
        return self.footprints().get(test, {}).get(key, {}).get(operation)

    def write_footprint(self, test, choice, operation, **fact_db):
        """
        RETURN: dict, the entry as written -- 'when' and 'host' are added
                here, so no caller has to remember them.

        OVERWRITES exactly one (test, choice, operation) entry and leaves
        every other untouched. NOT an append: what was there before is the
        concern of the configuration management system.

        The single writer is guaranteed above -- one run of a test at a
        time, one live holder of the directory lock.
        """
        key     = "<none>" if choice is None else choice
        content = self.footprints()
        entry   = dict(fact_db)
        entry["when"] = _now()
        entry["host"] = this_host()
        content.setdefault(test, {}).setdefault(key, {})[operation] = entry

        self.footprint_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.footprint_path.with_suffix(".json.tmp")
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(content, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(temporary, self.footprint_path)   # atomic: a reader sees
                                                    # the old file or the
                                                    # new one, never half
        return entry

    def lock(self):
        """RETURN: DirectoryLock, the access check of this directory."""
        return DirectoryLock(self.directory)
