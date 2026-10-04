==============================================================================
coverage -- THE MEASUREMENT OF WHAT A TEST REACHED
==============================================================================

Status:  The record and its algebra, the election, the index, the
         two internings, 'hwut.affected', ELEVEN READERS over eleven
         artifact formats, and the MEASURE registration (branch, mc/dc,
         toggle, cover) are BUILT and green. For the current table of
         tools, formats and what this build reads, ask the registry --
         'hwut.cov.formats' (RATIONALE D-13); it is not copied here.
         'julia' is owed, and DISCUSSIONS.txt names what is not built.
Layer:   BESIDE procsitter and compare -- a component the operations
         layer holds VERBATIM and translates for.
Bounds:  ONE test's measurement. Aggregating many is a HIGHER layer.

This file states MECHANICS. Why any of it is so lives in RATIONALE.txt;
what is still open lives in DISCUSSIONS.txt.


------------------------------------------------------------------------------
1  THE THREE THINGS THIS COMPONENT OWNS
------------------------------------------------------------------------------

    CONTRACT   CoverageConfig            what is gathered
    THE CALL   specify_command_line()    the tool's command line, from
                                         its call scheme (D-39)
    HARVEST    harvest(dir)              artifact -> homogeneous record

Nothing else. It renders nothing, judges nothing, and decides nothing
about whether coverage was wanted.


------------------------------------------------------------------------------
2  THE MODULES
------------------------------------------------------------------------------

    configuration.py  CoverageConfig, CoverageRefused
    record.py         the homogeneous record: intervals, delta coding,
                      format/parse, merge
    measure.py        the measurements BESIDE the line axis: branch,
                      mc/dc, toggle, cover, function, and the
                      registration for one more
    index.py          the other fold: who executed this line; and
                      'Gathered', a run id qualified by the directory
                      its record was found in
    affected.py       'hwut.affected': a change in, the runs out
    registry.py       language -> candidate tools -> the elected one
    reader.py         the two ROLES -- CCoverageFramework (the tool:
                      invocation) over CCoverageFormat (the artefact:
                      reading) -- and the tool -> framework registry
    readers/          one module per artifact FORMAT, holding the
                      format and the framework(s) that write it
                        python_coverage.py  coverage.py json
                        lcov.py             the lcov tracefile
                        gcov.py             gcov annotated source
                        cobertura.py        cobertura xml
                        go.py               go cover profile
                        luacov.py           luacov report
                        jacoco.py           jacoco xml
    FORMAT.txt        the record's syntax, both spellings
    binary.py         the binary spelling: the ONE form on disk


------------------------------------------------------------------------------
3  THE ROAD OF ONE MEASUREMENT
------------------------------------------------------------------------------

    CoverageConfig          language stated, or DERIVED from the
        |                   source file's extension
        v
    registry.elect()        the candidate list of that language, by
        |                   GLOB; the FIRST one this machine has
        v
    framework_of(tool)      one framework per tool, its format inside
        |
        v
    build coverage_target   the author's target, built and run in
        |                   place of the executable (section 5)
        v
    specify_command_line() -> the execute stage runs THIS call
        |
        |              the tool leaves its own artifact in
        |              <test_directory>/OUT/COVERAGE/
        v
    report_argv() ---> the second supervised call, where one stands
        |
        v
    harvest() --------> CoverageRecord --seated(run id)-->
                        (homogeneous)   TMP/store/<test>--<choice>.cover

Four seams outside this component: the adapter's target
('orchestrator/run/adapter.py'), the execute stage's argv
('operations/run/core.py'), the session's closing act
('operations/coverage_action.py'), the book entry and the record's path
('bookkeeper/bookkeeper.py').


------------------------------------------------------------------------------
4  THE RECORD
------------------------------------------------------------------------------

Per source file, two sorted HALF-OPEN interval lists:

    EX   the ranges that could be hit
    CV   the ranges that were

'uncovered = EX - CV' and the percentage are DERIVED, never stored.

DELTA CODED: 'd+L' per range, 'd' alone where the range is one line,
'd+L*C' where hit counts are recorded. 'd' is the gap from the previous
range's END, so every delta is positive and small.

    ##VUT-COVERAGE 4
    ##run:      0.1
    ##language: python
    ##tool:     coverage
    ##format:   coverage.py-json
    ##counts:   no
    SF:parser/core.py
    EX:3+12,5+5
    CV:3+12

THE HEADER NAMES THE RUN as a RUN ID the register issued -- '0.1' is
application 0, choice 1 -- beside the provenance ('language', 'tool',
'format'). In the store the key would do; away from it the record would
be anonymous, and the index (4b) could only guess.

'run' IS A SET, comma separated: a MERGED record names every run that
made it ('##run:      0.0,0.1,3'). A record fresh from a READER names
none and says so ('##run:      -'); 'record.seated' is the one seam that
gives it a run.

IDS, NOT NAMES (RATIONALE D-18): an id is issued once and never re-used
(bookkeeper B-2), so a record that travelled decodes to the same test or
to 'no longer registered' -- and a RENAME TOUCHES NO RECORD.

PATHS ARE RELATIVE TO THE TEST DIRECTORY. HIT COUNTS are off by default
and the header declares them. MERGE is the union of ranges: associative,
commutative, idempotent -- an aggregate does not depend on its walk
order. Provenance that agrees is carried; provenance that differs is
JOINED, so a mixed aggregate shows that it is one.

ABSENT AND EMPTY DO NOT COLLAPSE. A source file not measured has NO
block. One measured and found to have no executable line has a block
with an empty 'EX'. A file with no executable line has NO ratio -- not
1.0.


------------------------------------------------------------------------------
4b  THE INDEX -- WHO COVERED THIS LINE
------------------------------------------------------------------------------

'index.py' folds the SAME per-run records a second way. Where 'merge'
answers "what did the suite reach", the index answers "which runs reached
this line" -- and therefore, what to run when that line changes.

    index_of([(run key, CoverageRecord), ...], group_table=None)
                                              ->  TestIndex

        .of_line(path, line)        -> frozenset of run keys
        .of_ranges(path, ranges)    -> frozenset of run keys
        .of_change({path: ranges})  -> tuple of run keys, sorted
        .segment_iterable(path)     -> ((begin, end), origin_set) ...

A run key is a 'TestRunId' -- (app_id, choice_id|None), issued by the
bookkeeper's register, DIRECTORY-LOCAL, stable under any invocation
root, untouched when its directory moves (RATIONALE D-14). A walk
across directories ('record_iterable') qualifies as it goes: 'Gathered'
pairs the found-directory with the run id, is what a cross-directory
index decodes to, and is never stored -- the group table's 'format'
refuses it.

A SEGMENT CARRIES ONE INTEGER, not a set of names: the bookkeeper's
'GroupTable' interns a set of run keys as a GROUP ID (bookkeeper B-3).
Decoding happens at the EDGE, on the few segments a query touched.
Group 0 is the empty set, by construction, so no query needs a special
case for 'nobody'.

    an id is ISSUED ONCE -- app, choice and group ids each count from
        0 and are never re-issued (bookkeeper B-2), so an old record
        cannot be silently reattributed
    a RENAME KEEPS THE ID -- it touches one register entry and no
        record anywhere

'index_of' TAKES the group table, so a fold over one directory hands
in its persisted 'GroupDb' and keeps its group ids across builds. Given
none, a fresh table is made and the ids live as long as the index.

The line axis is cut where the origin SET changes and fused where it does
not, so a file one run reaches whole costs ONE segment. A stretch nobody
executed is CARRIED as a segment naming nobody -- not skipped. A query is
a bisect.

ON DISK THE FOLD IS THE COVERAGE RUN'S OUTPUT (D-42): per source file,
each covered range under the test run or group of test runs that
executed it. The per-run records are its input and are removed once
gathered.

THE LIMIT. The index names what CERTAINLY executed a line. It never
claims the rest is unaffected: a test may depend on code it never
executed -- a deleted branch, a data file, a dynamic dispatch, an
absence. It is a SUGGESTION, never a clearance, and every face over it
says so.


------------------------------------------------------------------------------
4c  'hwut.affected' -- THE FACE
------------------------------------------------------------------------------

    hwut.affected --records DIR [--diff FILE|-] [-p N] [-b|--bare]

    default   the framed answer: what was asked, what was indexed, the
              runs to perform, and the LIMIT under it
    --bare    names alone, one per line, for piping into a wish; the
              limit goes to stderr rather than away
    exit      0 a selection, 3 nothing executed the change, 2 refused

A diff's paths are relative to the ROOT; a record's are relative to ITS
TEST DIRECTORY. The face REBASES -- 'parser/TEST' + '../core.py' becomes
'parser/core.py' -- and that join is why the directory must come from the
aggregator rather than from the record.

An ADDED line is itself; a REMOVED line is recorded at the new-side
position where it stood, because saying nothing there would hide a
deletion entirely. A file removed wholesale contributes nothing: there is
no new-side line to ask about.

'record_iterable' WALKS for '*.cover'. That is a stand-in: the store's
naming is the BOOKKEEPER'S, and the real face asks it. It is the only
place that changes.


------------------------------------------------------------------------------
5  WHAT A COVERAGE RUN IS
------------------------------------------------------------------------------

THE DEMAND SHAPES THE RUN (RATIONALE D-19). 'hwut.cov.run <wishlist>'
generates the chain; nothing is discovered. IT IS NOT A TEST RUN
(D-38): nothing is compared with 'GOOD/', no verdict is determined,
'GOOD/book.csv' is not written. 'hwut.run' measures no coverage.

    build    'build { coverage_target = "cov-parse.exe" }' is built IN
             PLACE OF the executable and run in its place. The name is
             the whole communication with the author's build system.
             REQUIRED under coverage for a compiled test; absent, the
             case is answered 'no-coverage-target' and not run.
    run      the elected tool's 'specify_command_line' gives the call
             by which the TOOL runs the application (D-39); an
             instrumented binary measures itself and is called as it
             stands.
    report   'report_argv', the tool's second call, supervised.
    harvest  the run's closing act: the reader reads 'OUT/COVERAGE',
             the record is seated with the run id and written to
             'TMP/store/<test>--<choice>.cover' in its BINARY
             spelling (D-20; 'hwut.cov.conv.to_humans' shows it). Raw
             artefacts are run debris under 'OUT/'.
    gather   the RUN's closing act (D-42): every per-case record is
             folded into the output directory and removed.

THE OUTPUT DIRECTORY ('-o <directory>', D-42) is the one place coverage
data is kept:

    test_run_id_db.csv         directory;test;choice;test_run_id --
                               a cell equal to the one above is empty,
                               as in 'GOOD/book.csv'
    test_run_group_id_db.csv   test_run_group_id;test_run_ids
    <source path>.cover        one file per source file, record
                               version 3 ('database/FORMAT.txt' 9),
                               BINARY on disk (D-43): 'EX' once, the
                               universe of every measure once (branch
                               arms, mc/dc conditions, toggle bits,
                               cover points, functions), then per test
                               run or group that took something
                               'CV@<reference>:' its lines and
                               '<TAG>@<reference>:' its items.
                               'hwut.cov.conv.to_humans FILE' prints it as
                               text

An identifier is a base-64 number and stands in exactly one of the two
tables. 'coverage/output.py' writes and reads all three.

IT HOLDS EXACTLY ONE RUN: it is emptied when the run starts, and only
where it is empty or carries hwut's marker. Without '-o' the run asks
whether './hwut.coverage/' is to be used; '--dont-ask' takes it
unasked; where nobody can be asked the run is refused.

ONE BADGE PER CASE in the coverage run's output, which is rendered as
a test run's is (display D-40): '[REC]' where a record stands, else the
reason and '[NO REC]', and the reason in full under HINTS:

    no target       no-coverage-target  compiled, and no
                                        'coverage_target' declared
    no data         no-data-provided    the run left nothing to harvest
    incomplete      run-incomplete      the application did not
                                        testify; nothing read
    report failed   report-failed       the tool's second call did not
                                        end well
    not in book     not-registered      'GOOD/book.csv' names no such
                                        run

A DIRECTORY reads '[COMPLETE]', '[PARTIAL]' or '[OMITTED]' in the
roll-call: every case recorded, some, none.

THE RECORD IS THE WHOLE PRODUCT (D-38): a run that bore nothing writes
no record. What each case came to is left as a LOCAL TRACE,
'TMP/hwut-traces-coverage.csv' (D-41) -- ignored by git, read by
'hwut.help' alone, which explains every '[NO REC]' of the last
coverage run. Coverage
is measured for ACCEPTED tests: the run id is the register's, which
the coverage run reads and never writes.
Built: 'operations/coverage_action.py' (one run) and 'orchestrator/
run/coverage_dispatcher.py' (the plan's dispatcher), tested in
'operations/TEST/test-coverage_provision.py' and 'services/TEST/
test-cov_run.py'.


------------------------------------------------------------------------------
5a  WHAT A COVERAGE RUN IS NOT
------------------------------------------------------------------------------

    -- it is not a replay: a replay executed nothing and harvests
       nothing; the entry carries no 'coverage' key.
    -- it is not a run of a case with no nominal: such a case is not
       run at all (E-41); a case with a nominal is registered before
       it runs, so every coverage run has its id.
    -- it is not a harvest of a run that did not TESTIFY (D-21): a run
       that was killed, stalled, was contained, or ended without
       '<hwut-end>' is noted 'run-incomplete' and nothing is read.
    -- it is not concurrent with another run of ITS directory (D-22):
       one artefact directory, one run at a time; directories in
       parallel.
    -- it is not time-capped (D-19): wall clock and CPU are lifted;
       memory, file size, process and disk caps stand.


------------------------------------------------------------------------------
6  EVERY REFUSAL THIS COMPONENT MAKES
------------------------------------------------------------------------------

    no language stated and none derivable from the extension
    no tool configured for the language
    no configured candidate available on this machine
    the elected tool has no reader in this build
    a record that cannot be read whole            (RecordFault)
    a record line under a tag no measure claims   (RecordFault)
    a merge of records carrying hit counts        (CountsNotMergeable)
    a merge of records carrying a measure that
    cannot say which items it counted             (MeasureNotMergeable)
    a jacoco line with neither 'ci' nor 'mi'      (CoverageRefused)
    a point that spells no point                  (MeasureFault)
    a second measure of one name, or one tag      (MeasureFault)
    a run id or a group that names nothing        (RunIdFault,
                                                   GroupFault -- the
                                                   bookkeeper's)

Each names what it looked for. None of them is a silent absence of
coverage: a skipped measurement reads as an absent one, and absence and
emptiness do not collapse.


------------------------------------------------------------------------------
6b  THE READERS -- THREE CALLS EACH
------------------------------------------------------------------------------

    specify_command_line(included_paths, omitted_paths, test_app, choice)
                    the tool's command line, filled from the class's
                    'call_scheme'; None where the tool is not on the
                    command line. The fields: {include} {omit} {test}
                    {choice}; a word whose field is empty is dropped
                    whole. '{test}' is the application WITHOUT its
                    interpreter: the tool chooses how to run it.

                        coverage run --data-file=OUT/COVERAGE/.coverage
                            --include={include} --omit={omit}
                            -- {test} {choice}
    report_argv()   the SECOND supervised call, where the tool leaves
                    BINARY STATE rather than a report; None where it
                    needs none
    harvest(dir)    the artifact -> the homogeneous record

A READER NAMES ITS CALLS AND MAKES NONE. Every process HWUT runs goes
through the procsitter, so the execute stage makes what the reader names.

THE TABLE OF TOOLS, FORMATS AND ALIASES IS NOT WRITTEN HERE. It has one
author -- the registry -- and is printed by

    hwut.cov.formats

whose GOOD file stands in 'TEST/GOOD/'. It was copied into five
documents once, and three of the five were false within two days
(RATIONALE D-13). What this section states instead is the SHAPE of the
answer: every tool names a format; several tools share one; a tool
either names a second call or honestly names none.

    coverage            coverage.py json       coverage run  coverage json
    gcov                gcov annotated source  --            gcov -b -p ...
    lcov &c.            lcov tracefile         --            --

Those three are the only shapes there are.

WHAT THAT REACHES. 'gcov' serves every gcc front end -- C, C++,
Objective-C, FORTRAN, Ada, Modula-2, COBOL, Vala, and VHDL through GHDL.
The tracefile serves Rust, Swift, Zig, Crystal, Julia, Dart and VERILOG
(through 'verilator_coverage --write-info'). Four of those languages
need registry entries and no code at all.

AN ALIAS CLAIMS THE FORMAT, NOT THE TOOL: it says 'this leaves a
tracefile in OUT/COVERAGE', not 'this component knows how to drive it'.
A tool needing its own call scheme deserves a module.

A FORMAT, NOT A TOOL, IS WHAT A READER KNOWS: four tools speak the
tracefile, so one reader serves all four -- and each record still names
the TOOL that ran, because the tool and the format are different facts.

gcov's second call is named LATE, over the '.gcda' the run just wrote,
and is None where there are none: that says 'the build was not
instrumented' rather than running gcov over nothing.

WHAT EACH FORMAT SAYS, and what is deliberately ignored:

    coverage.py json   'executed' -> CV, 'executed + missing' -> EX,
                       'excluded' -> neither. No counts: it records
                       hits, not their number. Run with '--branch', its
                       arcs are the arms of a BRANCH point (executed
                       and missing together, ascending, a mask).
    lcov tracefile     every 'DA' -> EX, every non-zero 'DA' -> CV.
                       'LF'/'LH' are DERIVED and are not consulted;
                       'FN*' and 'BRDA' are other measurements.
    gcov annotated     '-' not executable, '#####' executable and never
                       run, '<n>*' is <n>. The 'branch' lines under a
                       line are its ARMS, in order: one BRANCH point,
                       a mask with bit i set where arm i was taken.
                       The path comes from 'Source:', never from the
                       file name.
    go coverprofile    a line is a BLOCK, with a start and an end --
                       which IS a range and arrives as one. Blocks
                       overlap on boundary lines (the COLUMNS divide what
                       the lines do not) and are unioned. The path is an
                       IMPORT path: the module name from 'go.mod' is
                       stripped, and where there is no 'go.mod' it is
                       LEFT as it stands.
    luacov report      a blank count field is NOT EXECUTABLE, '*0' is
                       executable and never run. The field width is the
                       file's own and is derived per section. The raw
                       'luacov.stats.out' is NOT read: it counts a blank
                       line and an unexecuted statement both 0, and a
                       reader over it would have to invent EX.
    jacoco xml         every '<line>' -> EX, 'ci > 0' -> CV (JaCoCo: "a
                       source line is considered executed when at least
                       one instruction assigned to it has been
                       executed"). 'cb'/'mb' are COUNTS of branches and
                       name no arm: no BRANCH point (D-43). The path is
                       BUILT from
                       '<package>' + '<sourcefile>'. A line with neither
                       'ci' nor 'mi' is REFUSED: it is well-formed and
                       cannot say whether the line ran.
    cobertura xml      every '<line>' -> EX, every non-zero 'hits' -> CV,
                       and 'condition-coverage' is a COUNT of arms taken:
                       no BRANCH point (D-43). 'line-rate' and its kin
                       are SUMMARIES and are not
                       consulted. A root that is not '<coverage>' with
                       '<packages>' is left alone.


------------------------------------------------------------------------------
6c  THE MEASUREMENTS BESIDE THE LINE AXIS
------------------------------------------------------------------------------

Line coverage lives in 'EX'/'CV'. Every OTHER measurement answers a
different question about the same source, and belongs to a DECISION
POINT rather than to a line:

    branch      of the arms leaving this decision, WHICH were taken
    condition   of the terms in it, how many took both values
    mcdc        of the conditions in it, WHICH had their INDEPENDENCE
                demonstrated -- that each alone can flip the outcome

A MEASURE IS REGISTERED ('measure.py'): it owns a NAME, a record TAG, its
encoding, and whether it merges. The record dispatches on the tag and
asks the measure; it knows what none of them mean.

    BR:2*1/2          branch: line 2, arm 0 of two taken
    BR:2*3/2          branch: line 2, both arms taken
    MC:4*3/3,0*7/3    mc/dc: line 4 carries TWO decisions

'<line delta>*<mask in hexadecimal>/<total>': bit i of the mask is set
where item i was taken, delta coded as the ranges are. A ZERO
delta is a SECOND DECISION ON ONE LINE -- MC/DC admits it ('if (a) if
(b)'), branch does not. A file with no such measurement writes NO such
line.

BOTH MERGE (D-43), because a mask says WHICH items were taken. Two runs
taking different arms of one decision report masks 1 and 2; the union is
the OR, 3. A tool that counts its arms without naming them (cobertura's
'condition-coverage', JaCoCo's 'cb'/'mb') contributes no such measure.
A measure that cannot say which items it counted still declares itself
unmergeable, and 'record.merge' refuses it by name.

MC/DC IS REGISTERED AND NOTHING PRODUCES IT YET. The encoding is ours and
is tested; reading GCC 14's '--conditions' output is owed, and will be
written against a real artifact like every other reader.

A MEASURE WITH NO LINE CANNOT LIVE HERE -- AND FEWER LACK ONE THAN WAS
BELIEVED. The witnessed artifacts seat toggle points at the signal's
DECLARATION line and cover points at their statement, so both live here
as NAMED points, and because a named point carries its identity, both
MERGE (RATIONALE D-12). What is truly line-less -- FSM states,
covergroup bins -- is line-less by the UCIS XSD itself, and stays out:
see DISCUSSIONS disc-9 and its amendment.


------------------------------------------------------------------------------
7  ADDING A LANGUAGE
------------------------------------------------------------------------------

    (1) an entry in 'registry.EXTENSION_DB' if the extension is new
        (it serves 'hwut.cov.conv.to_humans' and the record's header)
    (2) the language's 'coverage' list in the SHIPPED ROOT CONF
        ('services/_boundary.ROOT_CONF_TEXT', D-26): the candidate
        tools, in PREFERENCE order. A tree already placed carries its
        own copy in 'hwut-root.conf' and edits that.
    (3) a module under 'readers/' with 'call_scheme', 'report_argv' and
        'harvest', passed to 'reader.register', and imported by
        'readers/__init__.py'

A TOOL THAT SPEAKS A FORMAT ALREADY READ needs only (2) and one line in
'readers.ALIAS_DB'. Nothing else changes, and a configuration never
names a reader.

WRITE THE READER AGAINST A REAL ARTIFACT. Every fixture in
'TEST/test-readers.py' was emitted by the actual tool and pasted in
verbatim; a hand-written one proves only that the reader reads what its
author imagined.

THE THREE STEPS ABOVE ARE THE CODE ONLY. The witness, the fixture, the
choice, the GOOD file and the ledgers are steps too:
'HOW-TO-INTEGRATE-A-COVERAGE.txt' walks all of them in order.


------------------------------------------------------------------------------
8  THE TEST
------------------------------------------------------------------------------

    cd TEST
    PYTHONPATH="$TR" python3 test-record.py <choice>

    PYTHONPATH="$TR" python3 test-index.py  <choice>

test-record:   intervals, encoding, roundtrip, merge, faults, election.
test-readers:  python, cobertura, lcov, gcov, go, luacov, jacoco,
               witnessed, verilator, native, ghdl, psl, resultset,
               ucis, agreement, aliases, calls, absent, gather, branches.
test-measure:  registration, branch, mcdc, named, in_record, union,
               points, faults.
test-gathered: same, text, measures, faults.
test-output:   carry, rebased, refused.
test-presenter-visitor: text, vocabulary, walk.
services/TEST/test-cov: to_humans, lcov, html, cobertura, jacoco,
               json, tex, pdf, formats, refused, help -- the converters
               over the output directory (D-44, D-45); their visitor
               discipline in 'services/TEST/test-cov_visitor.py'.
test-index:    keys, segments, query, change, economy, lossy, honest.
               (the group table's own test stands with the bookkeeper:
               'bookkeeper/TEST/test-group_table.py')
test-affected: diff, answer, bare, empty, refused, help.
Correctness is the compare engine's judgement of that stdout against
'GOOD/test-record.py--<choice>.txt' ('adm/census.py').


------------------------------------------------------------------------------
9  SEE ALSO
------------------------------------------------------------------------------

    RATIONALE.txt     the settled decisions and WHY (D-1 .. D-11)
    DISCUSSIONS.txt   what is OPEN (disc-1 .. disc-9) and OWED (todo-1 ..)
    adm/PHILOSOPHY.txt        section 7: the asymmetry of error
    operations/README.txt     2.6: refuse rather than guess;
                              absent and empty never collapse
