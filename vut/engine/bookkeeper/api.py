"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DOOR into 'engine/bookkeeper'. Everything outside the
         component reaches it through this module and through no other.

WHAT A CALLER IS TOLD TO BUILD -- the configurations, and they stand
here because A CONFIGURATION CONFIGURES A COMPONENT AND THEREFORE
BELONGS ON ITS DOOR:

    StoreConfig         what a store is told: where it writes and
                        under what naming
    NamingConfig        how a record is named from test and choice
    E_StderrNote        the note a choice's stderr carries: nominal,
                        ignored, forbidden
    CAPS_FIELD_DB       the author's caps vocabulary against the
                        procsitter's field names -- one list, read by
                        the adapter and by the book

WHAT A CALLER ASKS:

    Bookkeeper          the book of one directory: what was decided
    Store               the records of one directory: what was written
    DirectoryLock, DirectoryBusy
                        the store's access check, and its refusal
    TestIdDb, TestIdFault
                        the register: ids issued once, never reused
    TestRunId, run_id_of_text
                        the identity of one run
    ObservationDb, Observation, ObservationFault, observation_of
                        THIS MACHINE'S local observations -- the other
                        half of a record, and not the book (E-22)
    STORE_DIRECTORY_NAME, BOOK_FORBIDDEN_IN_NAME
    GOOD_OWNED_FILE_TUPLE
                        the bookkeeper's own files under GOOD/ (book,
                        legacy book, register): a walker of GOOD/ for
                        oracles skips these, asked here, never listed
                        what a test or choice name may not carry, so
                        the book's table survives it: the enforcer
                        asks, and adapts when this changes
                        the two names a caller must spell the same way
                        the component does
    GroupTable, GroupDb, parse_group_table, GroupFault
                        the group table a directory states, and the
                        fault where it does not hold
    source_digest_of    the digest that says whether a source moved
    LOCK_DIRECTORY_NAME the lock's place under 'TMP/'
    RunIdFault          a run id that does not read

TWO DATABASES, ONE DOOR. The book holds DECISIONS and the observation
database holds WHAT THIS MACHINE SAW (E-36); they are different files,
different lifetimes and different questions, but one component owns
both, and a caller that has one usually wants the other in the same
breath.

IT HOLDS NOTHING OF ITS OWN -- imports and '__all__'.

SUBSTITUTE AT THE DOOR. A re-export binds its names once, at import.
A test replacing a class must replace it here, since this is what the
product reads.

THE RULE IS EXECUTABLE: 'adm/LAYERING.txt' names this module in a
'DOOR' line. The component's own suites are inside the wall.
______________________________________________________________________________
"""
from .bookkeeper    import (Bookkeeper, BOOK_FORBIDDEN_IN_NAME,
                            GOOD_OWNED_FILE_TUPLE, NOMINAL_SUFFIX_DB,
                            STORE_DIRECTORY_NAME, SUBJECT_BY_SUFFIX_DB,
                            compare_setup_delta, error_witness_name,
                            nominal_stands_f)
from .configuration import (CAPS_FIELD_DB, E_StderrNote, NamingConfig,
                            StoreConfig)
from .group_table   import (EMPTY_GROUP, GroupDb, GroupFault,
                            GroupTable, parse_group_table)
from .observation   import (Observation, ObservationDb, ObservationFault,
                            observation_of)
from .stream_store  import (DirectoryBusy, DirectoryLock,
                            LOCK_DIRECTORY_NAME, Store,
                            source_digest_of)
from .test_id_db    import TestIdDb, TestIdFault
from .test_run_id   import RunIdFault, TestRunId, run_id_of_text

__all__ = ("Bookkeeper", "CAPS_FIELD_DB", "DirectoryBusy",
           "DirectoryLock", "E_StderrNote", "EMPTY_GROUP", "GroupDb", "GroupFault", "GroupTable", "BOOK_FORBIDDEN_IN_NAME", "GOOD_OWNED_FILE_TUPLE", "LOCK_DIRECTORY_NAME",
           "NOMINAL_SUFFIX_DB", "NamingConfig", "Observation",
           "ObservationDb", "ObservationFault", "RunIdFault",
           "STORE_DIRECTORY_NAME", "SUBJECT_BY_SUFFIX_DB",
           "Store", "StoreConfig", "TestIdDb", "TestIdFault",
           "TestRunId", "compare_setup_delta", "error_witness_name",
           "nominal_stands_f",
           "observation_of",
           "parse_group_table", "run_id_of_text", "source_digest_of")
