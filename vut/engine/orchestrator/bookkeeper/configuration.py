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


class E_StderrNote(Enum):
    """WHAT THE BOOK SAYS about a choice's stderr -- one note, three
    readings, and acceptance is where it is written.

    NOMINAL    a stderr stream was RECORDED: it is compared like any
               other subject, and a difference is a difference.
    IGNORED    whatever happens on stderr, DO NOT WORRY: it is never
               read, never compared, never reported.
    FORBIDDEN  a word there is an ERROR ('unexpected-stderr'). An
               UNNOTED choice reads FORBIDDEN: a test nobody was asked
               about has never spoken there, and its first word is
               news.
    """
    NOMINAL   = "nominal"
    IGNORED   = "ignored"
    FORBIDDEN = "forbidden"

    def __str__(self):
        """RETURN: str, the note's token, as the book holds it."""
        return self.value


@dataclass
class StoreConfig:
    """WHERE and HOW MUCH is kept. Held verbatim by the test's
    configuration (README 2.7); 'None' there means: do not record.

    directory      the test directory whose book and records these are.
                   Nominals live under 'GOOD/', the store's own records
                   under '.hwut-store/' -- apart from the test's 'OUT/',
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
    """THE LAW BY WHICH A RECORD IS NAMED.

    same_nominal_f  ALL CHOICES SHARE ONE NOMINAL: the choice part is
                    dropped from the nominal's key, so 'demo--a.stdout'
                    and 'demo--b.stdout' are both held against
                    'demo.stdout'. Stated by the author as 'same' in
                    the header (exploration's TestParameters, root
                    only), it saves one blessed file per choice where
                    every choice must produce the same behaviour.

                    CANDIDATES ARE UNAFFECTED: each choice's own run is
                    still recorded under its own name, or the choices
                    would overwrite one another and no diff could name
                    which choice diverged.
    """
    same_nominal_f: bool = False
