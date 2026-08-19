============================================================================
VUT-ORCHESTRATOR
============================================================================

Status:  bookkeeper/ IMPLEMENTED. orchestrator.py, explorer/ and
         services/ are named in DISCUSSIONS.txt and nowhere else.
Layer:   ABOVE test_run. Selecting and driving MANY tests; the book of
         each test directory.
Bounds:  Running ONE test is test_run's business. This component asks
         and drives; it never enters a test's ceremony itself.

----------------------------------------------------------------------------
1  THE STRUCTURE
----------------------------------------------------------------------------

    orchestrator/
        orchestrator.py     the Orchestrator: explore, then per
                            directory ask the Bookkeeper, drive the run
        bookkeeper/
            configuration.py  StoreConfig (what is kept) and
                              NamingConfig (how a record is named)
            bookkeeper.py   the Bookkeeper: ONE test directory's book
        explorer/
            explorer.py     the Explorer: which directories hold tests
        services/           rename, rename-choice, remove,
                            remove-choice, report

    A file names the class it holds.

----------------------------------------------------------------------------
2  THE BOOKKEEPER
----------------------------------------------------------------------------

One Bookkeeper per test directory. It is made ABOVE: the Orchestrator
makes one from the test's directory and hands it down; a service that
needs one makes it inside the service. Nothing below makes its own.

It answers three kinds of question and performs one kind of write:

    THE NAMING          (test, choice, subject) -> the file's path
    WHAT A TEST IS      its reproducible configuration, from the base
    WHAT IT HAS DONE    the entries: verdict, report, when, host, the
                        attribution records
    RECORD              derive and write one entry

2.1  THE NAMING

A record's key is (test, choice, subject). The Bookkeeper turns it into
the file that carries it:

    GOOD/<test>--<choice>.<subject>          the nominal
    GOOD/<test>.<subject>                    ... of a test without choices
    OUT/<test>--<choice>.<subject>           the candidate
    OUT/<...>.<subject>.raw                  the pre-canonicalisation
                                             stream, beside the candidate
    OUT/<...>.<subject>.times                the cadence sidecar

The reading and writing of those files is the caller's; the Bookkeeper
names, it does not touch them.

2.2  THE BASE

ONE file: 'GOOD/result_db.json'. JSON. Write-protected (mode 0444) as
every other file in GOOD. The adapter is the only way in or out: it
unprotects, writes a temporary beside, replaces, re-protects. A missing
or damaged base reads as EMPTY and never raises; a later write recovers
it.

The shape, one entry per (test, choice, operation), OVERWRITTEN:

    { "<test>": {
        "configuration": { source_file, source_kind, interpreter,
                           interactive, caps },
        "choices": {
          "<choice>" | "<none>": {
            "configuration": { canonicaliser, compare },
            "operations": {
              "Run" | "Display" | "Accept": {
                verdict, report, when, host,
                canonicaliser,          -- if the choice names any
                compare,                -- the setup's differences only
                records                 -- the attribution
    } } } } } }

State now, never a log: what was done before is the concern of the
software configuration management system.

2.3  RECORDING

'record(result, configuration, goal, choice_name)' DERIVES the entry:

    verdict, report      from the result
    canonicaliser        from the choice's configuration
    compare              compare_setup_delta(): only what differs from
                         compare's default
    when, host           added here
    records              the result's provision records -- one
                         ProcsitterResult per supervised call, made
                         plain (Enum -> name, dataclass -> fields)

The same write refreshes the test's and the choice's reproducible
configuration, so a query answers from the base alone.

2.4  THE QUERIES

    book()                              the whole base
    tests(), choices(test)              what is recorded
    result(test, choice, operation)     the most recent entry
    test_configuration(test)            reproducible test facts
    choice_configuration(test, choice)  reproducible choice facts

An unknown name answers None.

2.5  THE DIVERGENCE

Detected ON CALL: 'divergence(declared_db)' takes what the caller
DECLARES -- test name -> its choice names (None where the test runs
without a choice) -- and answers what is recorded but declared no
longer:

    a recorded test absent from the declaration      -> 'deleted'
    a recorded choice absent from its test's         -> 'non-responsive'
        declaration

A declared name never yet recorded raises no complaint. The answer
never edits the book; healing is a service:

    hwut.rename        app.cpp  new-app.cpp
    hwut.rename-choice app.cpp  old  new
    hwut.remove        app.cpp
    hwut.remove-choice app.cpp  choice

What a verdict means is the caller's: under 'run all tests' a
non-responsive choice is an error; under 'run this test with that
choice' it is not.
