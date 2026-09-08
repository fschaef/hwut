THE BOOKKEEPER -- what a test run IS, and what it HAS DONE
==============================================================================

Status:  A COMPONENT of its own since 2026-08-25 (RATIONALE B-1). It
         was a sub-package of the orchestrator; 'operations' and
         'coverage' both had to reach upward into the orchestrator to
         name a test run, which is what moved it.

1  WHAT IT HOLDS
------------------------------------------------------------------------------

    test_run_id.py    THE SHAPE OF A RUN: 'TestRunId(app_id,
                      choice_id)', spelled '47' / '47.66'. Carries no
                      name.
    test_id_db.py     THE REGISTER of one directory: which names those
                      numbers stand for, in 'GOOD/test_ids.dat'.
    group_table.py    THE GROUP TABLE of one directory: a SET of runs
                      as one number, in 'GOOD/group_ids.dat'.
    bookkeeper.py     THE BOOK of one directory: the naming of every
                      file that carries a record, the entries, the
                      divergence verdicts. (Configuration: none --
                      B-6.)
    stream_store.py   The candidate/nominal streams beneath the naming.

1a WHAT GOES WHERE
------------------------------------------------------------------------------

TWO DATABASES under one directory, sorted by ONE question -- does the
thing depend on WHEN and WHERE it was made? (E-36, in services/RATIONALE)

    GOOD/book.csv               THE BOOK. What was DECIDED about the
                                software. Versioned with the tests.
    TMP/store/observations.bin  THE LOCAL DATABASE. What THIS machine
                                SAW: when, where, how long, host, pids.
                                Transient.

Beside them, not in them:

    GOOD/<test>[--<choice>].txt the NOMINALS (the oracles)
    GOOD/test_ids.dat           the REGISTER of run ids (B-2)
    TMP/store/<test>....stdout  the CANDIDATES (the recorded streams)
    the header, hwut.conf       the CONFIGURATION -- git's, beside the
                                book; never copied into it (B-6)

THE BOOK IS A TABLE (B-7): 'GOOD/book.csv', ONE ROW PER (TEST,
CHOICE), separator ';', no quoting -- a name containing ';' is
refused at the specification's door.

    test;choice;verdict;report;last_accept;coverage;stderr;stain_repeat_n;stain_when

    test            the application's file name; EMPTY means "the
                    same as the row above" -- an empty name means
                    nothing else, so it needs no mark (B-8)
    choice          the choice; empty where the test has none
    verdict         true / false -- of the last run
    report          the run's report token (word.py phrases it)
    last_accept     the instant the STANDING nominal was blessed;
                    empty until one is
    coverage        the coverage step's token; empty where not asked
    stderr          the stderr note ('ignored', 'forbidden'); empty
                    where none
    stain_repeat_n  the repeats a proof must make to clear the stain
    stain_when      the instant of the conviction
                    -- both empty where the choice is clean

An empty cell is ABSENCE. No row carries a configuration, an
operation name, a host, a duration or an attribution: the first is
git's, the last three the local database's, and an operation is not
a dimension of a decision.

READ THROUGH THE DOOR: 'tests()', 'choices()', 'result()', 'stain()',
'stderr_note()', 'divergence()'. The model these answer from is
private; the file's shape may change under a face without it
noticing (E-37).

HEALED THROUGH THE DOOR: 'rename_test()', 'rename_choice()' re-key an
entry in place; 'remove_test()', 'remove_choice()' give an entry up
and return it; 'adopt(test, entry)' takes a whole entry in under a
name that does not stand -- the entry 'remove_test()' returned in one
directory is what 'adopt()' writes in another. A name that already
stands is refused ('KeyError'); nothing is merged.

THE REGISTER IS WRITTEN IN THE SAME ACT (B-9): 'note_accept()' issues
the id, the removals retire it, the renames re-key it, 'adopt()'
issues the target's. It is read through the door too: 'run_id_of()',
'name_of()', 'roster()', 'app_iterable()', 'vanished()',
'register_generation()', 'register_text()'.

EVERY ACT RUNS UNDER THE DIRECTORY'S LOCK ('DirectoryLock', taken by
the bookkeeper for the act's duration). A holder above takes it once,
'with bookkeeper.held():', for a whole session; an act inside asks the
mutex, meets 'DirectoryDeadlock' -- which says 'this process already
holds it' -- and runs inside that holding. A lock held by ANOTHER live
process is 'DirectoryBusy' and refuses.

THE BOOK IS 'GOOD/book.csv' (B-10). A book under a name the tree has
retired -- 'result_db.csv', 'result_db.json' -- is read where it does
not stand, and the first write lays down 'book.csv' and removes the
old file. One book, never two.

BESIDE THE TESTS, NOT UNDER 'GOOD/': 'hwut-traces.csv' (B-11), what a
run COST per machine class -- one row per '(system, test, choice,
operation)', replaced where the key stands, committed, and deletable
without loss. The rows are SORTED, and an empty 'system' or 'test'
cell means the one above (B-12); an empty 'choice' means a test that
has none. 'TMP/store/observations.bin' keeps what does NOT travel.

2  THE ONE SENTENCE
------------------------------------------------------------------------------

A TEST RUN IS A GENERALITY. The runner performs one, the base records
one, a report names one, a coverage record attributes work to one. The
shape therefore stands with the runs' ADMINISTRATOR, and every other
component refers DOWNWARD to it.

3  WHO REFERS TO IT
------------------------------------------------------------------------------

    orchestrator      makes a Bookkeeper per directory and hands it
                      down; the services heal through it
    operations        the naming, the stream store, the stderr note
    coverage          the run id and the group table -- it owns
                      'Gathered', the qualification of a run id across
                      directories, and numbers no test itself

The component refers to none of them.

4  THE IDS
------------------------------------------------------------------------------

An id is born at the first 'hwut.accept'. THREE SCOPES, orthogonal,
each counting from 0: app ids among the apps, choice ids within their
app, group ids among the groups. A scope issues one above the highest
id it ever issued; the file carries that mark. Removal DELETES the
name and RETIRES the number. The ceiling of every scope is 2**32
('ID_LIMIT'); the id at the ceiling is refused by name.

A rename WITHIN the directory keeps the id -- that is what the
register is for. An id may be persisted anywhere: it decodes later to
the same test, or to 'no longer registered', never to another test.
Ids are the DIRECTORY'S (D-14): a test carried into ANOTHER directory
is retired here ('remove_app()') and issued afresh there
('run_id_of(..., allocate_f=True)'); a coverage record that travels
with it is re-seated under the fresh id by the face that carries it
(services E-46).

The register knows two things the book cannot: which application files
are REGISTERED ('roster()'), and which registered application has no
file any more ('vanished()').

5  THE TESTS
------------------------------------------------------------------------------

    test-bookkeeper.py    naming, record, overwrite, protection,
                          damage, reproduce, divergence, setup_delta
    test-stream_store.py  keys, lock_live, lock_dead, nominal_kinds,
                          promotion
    test-test_id_db.py    allocation, healing, retire, tables, faults,
                          vanished, face
    test-group_table.py   groups, tables, persisted, faults
