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
                      reproducible configurations, the divergence
                      verdicts.
    stream_store.py   The candidate/nominal streams beneath the naming.

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

A rename keeps the id -- that is what the register is for. An id may
be persisted anywhere: it decodes later to the same test, or to 'no
longer registered', never to another test.

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
