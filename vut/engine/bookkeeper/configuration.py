"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BOOKKEEPER'S CONFIGURATION -- what is kept, where, and
         under what name.

Two configurations live here: 'StoreConfig', the storing knobs a test
carries verbatim, and 'NamingConfig', the law by which a record's file
name is formed. They are separate because one is about VOLUME and the
other about IDENTITY: a test may store more or less without changing
what its records are CALLED, and it may share one nominal across its
choices without changing how much is kept.
______________________________________________________________________________
"""
from dataclasses import dataclass
from enum        import Enum


class E_TestVerdict(Enum):
    """WHAT THE BOOK SAYS of a choice's STANDING -- the 'verdict' column.

    A row in the book says the choice is KNOWN; it does not say a
    nominal stands. Whether one stands is asked of 'GOOD/' by
    'nominal_stands_f', per case, and nothing remembers the answer
    (B-14). The column says what the last act found:

    PASS       ran and was equivalent to its nominal -- or was just
               accepted, which is the same statement (E-15).
    FAIL       ran and was not.
    ASPIRANT   in the book, never accepted: registered, an id issued,
               no nominal to be judged against. Played by 'hwut.run.play',
               refused by 'hwut.run' (NOT_ACCEPTED_REASON). Neither a
               pass nor a failure -- '--fail' iterates FAIL and nothing
               else, since what never ran cannot have failed.

    PARSED ONCE, AT THE ROW. The book's text becomes this the moment a
    row is read ('_model_of_rows') and becomes text again only where a
    row is written ('_rows_of_model'); between the two, every reader
    holds the enum. A bare bool would round-trip 'ASPIRANT' to 'true'
    on the next write, and an aspirant would quietly pass.
    """
    PASS     = "true"
    FAIL     = "false"
    ASPIRANT = "aspirant"

    def __str__(self):
        """RETURN: str, the verdict's token, as the book holds it."""
        return self.value

    @classmethod
    def of_bool(cls, flag):
        """RETURN: E_TestVerdict, PASS for a true flag, FAIL else."""
        return cls.PASS if flag else cls.FAIL

    @classmethod
    def of_text(cls, text):
        """
        RETURN: E_TestVerdict, of the book's token.
                None, of '' or any token the book never wrote --
                a legacy row with no verdict recorded.
        """
        for member in cls:
            if member.value == text: return member
        return None

    @property
    def passed_f(self):
        """RETURN: bool, True where this is PASS."""
        return self is E_TestVerdict.PASS

    @property
    def failed_f(self):
        """RETURN: bool, True where this is FAIL -- and only then."""
        return self is E_TestVerdict.FAIL


@dataclass
class StoreConfig:
    """WHERE and HOW MUCH is kept. Held verbatim by the test's
    configuration (README 2.7); 'None' there means: do not record.

    directory      the test directory whose book and records these are.
                   Nominals live under 'GOOD/', the store's own records
                   under 'TMP/store/' -- apart from the test's 'OUT/',
                   which is the test's product space and whose every
                   file execution reads as a subject.

    record_raw     keep the PRE-CANONICALISATION stream beside the
                   candidate. Off by default: it doubles the volume and
                   is wanted only where a canonicaliser is under
                   suspicion.

    record_timing  keep per-line delta times beside the candidate. Off
                   by default. Where a provider cannot measure, the
                   result is 'None' -- never an empty stand-in, never
                   a zero.
    """
    directory:     str
    record_raw:    bool = False
    record_timing: bool = False


@dataclass
class NamingConfig:
    """THE LAW BY WHICH A RECORD IS NAMED, for ONE TEST DIRECTORY.

    same_nominal_set  THE TESTS WHOSE CHOICES SHARE ONE NOMINAL: for
                    each, the choice part is dropped from the nominal's
                    key, so 'demo--a' and 'demo--b' are both held
                    against 'demo.txt'. Stated by the author as 'same'
                    in the header (root only); it saves one blessed
                    file per choice where every choice must produce the
                    same behaviour.

                    'same' IS ONE APPLICATION'S WORD, AND THE BOOK IS
                    THE DIRECTORY'S (B-30): the law names the tests, so
                    ONE bookkeeper answers for all of them. It is told
                    once, from the application set, by whoever makes
                    it.

                    CANDIDATES ARE UNAFFECTED: each choice's own run is
                    still recorded under its own name, or the choices
                    would overwrite one another and no diff could name
                    which choice diverged.
    """
    same_nominal_set: frozenset = frozenset()

    def shared_f(self, test):
        """RETURN: bool, True where every choice of 'test' is held
                   against ONE nominal."""
        return test in self.same_nominal_set


#  THE AUTHOR'S CAPS VOCABULARY -- what a test header may STATE --
#  against the procsitter's field names. ONE LIST, READ BY TWO: the
#  adapter turns a stated cap into a procsitter field, and the book
#  writes a cap back under the name the author knows (E-36). It stands
#  here, below both, because the bookkeeper may not reach up to the
#  orchestrator for it.
CAPS_FIELD_DB = {
    "timeout_sec":         "max_wall_clock_sec",
    "cpu_sec":             "max_cpu_time_sec",
    "memory_mb":           "max_memory_mb",
    "file_size_mb":        "max_file_size_mb",
    "child_process_max_n": "max_pids",
}
