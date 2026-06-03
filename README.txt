================================================================================
                            VUT  --  Versatile Unit Test
                          (the road to HWUT 2.0)
================================================================================

EARLY STAGE -- WORK IN PROGRESS
--------------------------------------------------------------------------------
VUT is the second generation of HWUT. The first was written by the same author
roughly twenty years ago and has been in service ever since. This version is a
ground-up rewrite: twenty more years of the author's experience, and twenty
years of newer technology, put into one goal -- the best unit test tool there
is.

"VUT" (Versatile Unit Test) is the working name while the project matures. Once
it is production ready, it takes the name it is built to deserve: HWUT 2.0.

The project is in an early stage. Interfaces, file formats, and command names
may still change. What is stable is the idea; the surface around it is being
built.


WHAT HWUT IS
--------------------------------------------------------------------------------
A unit test in HWUT is not a list of assertions. It is a program that runs,
prints its behaviour, and terminates. HWUT compares that behaviour against a
recorded "known-good" description -- the GOOD file. If they match, the test
passes; if they differ, the difference itself tells you what changed.

Two consequences follow, and they are the heart of the tool:

  - The expectation lives OUTSIDE the test, in the GOOD file. The test only
    exercises the unit and shows what it does. You do not predict the answer
    and assert it -- you run the unit, read what it does, and freeze it once it
    is right.

  - A test is the WHOLE arc: it runs, and it terminates. A crash, a hang, a
    segmentation fault -- these are observable behaviour, not interrupted
    tests. HWUT watches from OUTSIDE the process, so it sees them. This is how
    HWUT checks that a unit not only answers correctly but stays consistent --
    something assertion-based tools, which die together with the unit, cannot.

Because the only thing HWUT requires is a program it can RUN on a command line,
HWUT is usable from ANY programming language. If your code can emit characters
and terminate, it is a first-class HWUT citizen.

A fuller account of the ideas -- units as causal systems, scenarios, tolerance,
and coverage -- is in PRINCIPALS.txt. [[ TODO: confirm filename / location once
written ]]


THE GOOD FILE
--------------------------------------------------------------------------------
The GOOD file holds the NOMINAL behaviour of a test. You do not write it by
hand from scratch -- you run the test, confirm the behaviour is right, and let
HWUT record it:

    hwut accept   <test-app-name> <choice>

GOOD files live under GOOD/ :

    GOOD/<application-name-without-suffix>.nom            (single-scenario app)
    GOOD/<application-name-without-suffix>/<choice>.nom   (app with choices)

A "choice" is a scenario -- a circumstance the unit is placed in, for which a
certain behaviour is appropriate. One application can expose several choices
(e.g. 'write-database', 'read-database'), each with its own GOOD file.


TOLERANCE
--------------------------------------------------------------------------------
Exact byte-for-byte comparison would be brittle: some output varies for reasons
that do not matter. HWUT lets you express what MUST hold and permit what MAY
vary:

  - numerical        -- numeric closeness rather than identity
  - analogies        -- ((term)) may differ between runs, as long as it differs
                        CONSISTENTLY
  - happy pattern    -- terms matching the same expression are equivalent
  - potpourri        -- a region where lines may appear in any order, each still
                        required to have its counterpart
  - reactive engine  -- sequence-independent checks
  - constraints      -- e.g. x < 1000 instead of a fixed value
                        <<not-yet-implemented>>

Tolerance is not only about robustness. It keeps the GOOD files REVIEWABLE: a
field that changes for an irrelevant reason on every commit trains the reviewer
to stop looking, and that is exactly how a real regression slips through on a
reflexive "accept". Tolerance silences the noise so that a diff, when it
appears, carries signal.



--------------------------------------------------------------------------------
License: MIT.
================================================================================
