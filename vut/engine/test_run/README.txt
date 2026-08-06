============================================================================
VUT-TESTRUN
============================================================================

Status:  IMPLEMENTED, except where DISCUSSIONS.txt says otherwise.
         The design is settled; what is not built is named there,
         and nowhere else.
Layer:   ORCHESTRATION of ONE test -- above procsitter, the supervised
         build, and the compare engine.
Bounds:  ONE test. Selecting, ordering and scheduling MANY tests is a
         HIGHER layer and is not this component's business.

This is the component's ONE design document: it states the mechanics and
the design together. Questions still under discussion live in
DISCUSSIONS.txt and are not repeated here.

Reading order: PART I is the whole thing in brief, with the master
diagram; PARTS II-IV are the detail, grouped by concern; PART V is
reference.

############################################################################
PART I -- THE GENERAL PICTURE
############################################################################

----------------------------------------------------------------------------
1  THE TASK
----------------------------------------------------------------------------

Run a test and report what happened -- whatever the test is made of,
however its output is obtained, and (for display) wherever the result is
shown. A test is a SOURCE FILE that may be an EXECUTABLE, be INTERPRETED
(lua, python, ...), or be COMPILED into an application first. Its
SUBJECTS -- stdout, stderr, output files -- are obtained either by
RUNNING it or by REPLAYING a previous run, then held against a NOMINAL
(the accepted reference) to yield either a verdict or a displayed
comparison.


----------------------------------------------------------------------------
2  THE DESIGN
----------------------------------------------------------------------------

2.1  AT A GLANCE. One declarative description flows down into the
existing components and fans out into three operations:

                        DECLARATIVE DESCRIPTION
               (source, kind, caps, nominals, subjects, ...)
                                   |
                                   |
                                   v
        .----- PROVISION of behavior description output ----------.
        |                                                         |
        |  Run :  build --> execute ----> canonicalise            |
        |         (build)   (procsitter)  (pype/procsitter)       |
        |                                                         |
        |  Replay: read the stored records                        |
        |                                                         |
        '--------------------------.------------------------------'
                                   | subject readers
                                   | (stdout / stderr / files)
                                   |
                                   v
       NOMINAL  ------------->  COMPARE  (aligns two readers)
       (accepted record)           |
                                   |
                .------------------+-------------------.
                v                  v                   v
          EquivalenceCheck   DifferenceDisplay      Accept
           -> VERDICT         -> feed a TARGET      -> write NOMINAL
                |                  |                    |
             OBSERVER          DISPLAY ADAPTER        STORE
           (watch run)        (IDE / mergetool)   (GOOD by default)

2.2  LAYERING.

    OPERATIONS    EquivalenceCheck | DifferenceDisplay | Accept
                  (each its own class + config)
        ------------------------------------------------------------
    GROUNDWORK    Run (execute + contain + record) | Replay (stored)
                  -> the SUBJECTS: stdout / stderr / file readers
        ------------------------------------------------------------
    TRANSLATION   declarative description -> component configs
                  *** procsitter / build / compare TYPES never appear
                      above this line ***
        ------------------------------------------------------------
    COMPONENTS    procsitter | compare        (their own components)

2.3  ONE ARTIFACT, THREE ROLES: The behavior description

The output of the test app is considered a description under the tolerance
of given procedures is considered to be a precise description of the behavior
of the unit under test.

This textual output is an artifact that appears in three roles:


              A CANONICALISED SUBJECT STREAM
             /            |                 \
      Run candidate  Replay candidate     NOMINAL
      (just made)    (read from store)  (a candidate, ACCEPTED & kept)

Subject and nominal are thus the SAME KIND of thing; every comparison
merely aligns two readers.

2.4  THREE CONCERNS, kept strictly apart. Compare sits BETWEEN two
reader-sources and is blind to how either was produced:

    PROVISION ---(subject reader)---> COMPARE <---(nominal reader)--- NOMINAL
    Run | Replay                    aligns two                    the accepted
    (execution & pype               readers                       record, read
     live ONLY here)                                              from storage

2.5  THREE OPERATIONS -- two READERS and one WRITER, on one groundwork
and one store:

      EquivalenceCheck   read  -> a VERDICT (OK / FAIL_*)
      DifferenceDisplay  read  -> the aligned comparison, fed to a target
      Accept             write -> the NOMINAL (from a complete dump)

All three read the ONE configuration of the test application (2.7) and
name the CHOICE they act on. What each asks for beyond that differs:
the two readers need the subjects-to-nominals map (section 7);
DifferenceDisplay needs a display target; Accept needs its per-subject
step. Those are what an operation is ASKED for, not what the test IS.

  HOW AN OPERATION WORKS INSIDE. An operation is a CLASS -- three doors,
  each named for what is asked. Inside, the work is done by SUB-PROCESSES
  that activate UPON NEED: a sub-process runs when its product is wanted
  and not yet there, and reads the configuration keys it declares (2.7).

      Accept, finding no current subject stored, activates provision.
      That is not a special case inside Accept; it is an unmet
      precondition like any other.

      Provision by EXECUTION and provision by STORED DATA (5) produce the
      same thing from disjoint keys, so no operation ever branches on
      which one it got -- which is what keeps compare blind to provenance
      (2.4).

2.5b  THE HEART OF THE OPERATION, and who owns each part of it:

    Equivalence( D(b_pole), D(b), T )

    Equivalence  its STRUCTURE   THE FRAMEWORK -- compare. The same for
                                 every test; no test changes how
                                 equivalence works, only what it is given.
    D            the DESCRIPTION THE TEST APPLICATION: what it prints,
                                 and the CANONICALISER that rewrites that
                                 into canonical form. Both are D.
    T            the TOLERANCE   THE TESTER, as declared parameters --
                                 compare's own struct, held verbatim.
    b_pole       the REFERENCE   THE STORE: written by Accept, read by
                                 every comparison after (6).

  THIS IS WHY BOTH KNOBS SIT IN ONE PLACE. 'TestChoiceConfiguration' (3)
  holds the canonicalisers AND the compare setup, because D and T are one
  decision about one scenario taken twice -- understanding first,
  tolerance only over what understanding cannot reach (PHILOSOPHY 6).
  Filing them apart would make "what does this test absorb?" a question
  with two answers in two places.

2.6  TWO LAWS THAT KEPT RE-DERIVING THEMSELVES. Both were reached
  independently in a dozen places before either was written down, so
  both are stated once here rather than a dozen times below.

  REFUSE RATHER THAN GUESS. Where a component cannot know, it says so; it
  does not choose.

      an owned keyword in a chain stage  |
      a configuration serving no goal    |  each has a TEMPTING
      a build system with no tool        |  DEFAULT, and every
      a display target with no driver    |  default fails SILENTLY,
      an UP intent nobody defined        |  in the GREEN direction
      a foreign protocol signature       |
                                         v
                                    REFUSED, named, at the door

  ABSENT AND EMPTY NEVER COLLAPSE.

      an absent recording   is not  an empty subject
      an unreadable nominal is not  nothing to compare against
      an empty comparison   is not  a pass
      a COMMIT with no text is not  a commit
      a clean exit          is not  a built target
      'record nothing'      is not  'recorded, and it was empty'

      absent  ---.                    "which was it?" -- a RECORD
                  +--> one value       question, and no type answers it
      empty   ---'                     (the law of the port, procsitter
                                        3.1, applied to VALUES)

  Every collapse yields a FALSE GREEN, the one failure that cannot report
  itself.


2.7  THE CONFIGURATION. THREE WORLDS, kept apart.

    THE CONFIGURATION       THE STORE            IN FLIGHT
    the test's DESIGN       the ARTIFACTS        the PRODUCTS
    ....................    ..................   ..................
    what the test IS        subject candidates   readers, verdicts,
    command, build, caps,   nominals             aligned pairs,
    canonicalisers,         timing series        attribution records
    recording, choices      keyed (test,         passed step to step
    written by the AUTHOR   subject)             never persisted,
    read by the STEPS       written by RECORD    never posted
    never mutated by a run  and by ACCEPT

  ONE WRITER, MANY READERS. The configuration is written once and only
  read thereafter; products never travel through it. So every product
  keeps a port that names its producer, and 'which step made this' stays
  answerable. In the Store the same law holds by key space: RECORD writes
  candidates, ACCEPT writes nominals, and no key has two writers.

  AGGREGATION, NOT RESTATEMENT. The complete configuration AGGREGATES the
  raw configuration structs of the sub-components, VERBATIM. Procsitter's
  caps are a 'ProcsitterConfig' held as a member -- not ten numbers copied
  out and translated back. A field is declared by the component that
  enforces it, once.

  HANDED IN COMPLETE. This component does not read a configuration file
  and does not resolve shorthand. It is HANDED one aggregate, already flat
  and complete, and only reads it. Whatever produces it -- a configuration
  file and its reader, a caller in Python -- is OUTSIDE, and the
  translation happens THERE, once: not a thousand times through a thousand
  layers. What this component owes in return is that the shape it requires
  is stated exactly, which is what section 3 does.

  THE UNIT IS THE TEST APPLICATION, identified by its SOURCE FILE. There
  is NOT a configuration per run, nor one per choice. One configuration
  serves every run of that application, and the CHOICE DATABASE lives
  inside it: a choice is an entry, not a configuration of its own.


2.8  THE FRONT DOOR. One callable assembles everything below, so nothing
  above needs to know that procsitter, compare or a build exist:

      run_test(configuration, request) -> Outcome

  TWO THINGS: what the test IS, and what is asked OF it. A configuration
  does not change between runs; a REQUEST changes every time, and keeping
  them apart is why neither grows fields belonging to the other.

  WHERE THE ARTIFACTS LIVE IS SAID ONCE, by the configuration: the
  store's own struct names a directory when it wants one elsewhere, and
  the test's own directory serves otherwise ('store_of'). A store passed
  BESIDE a configuration that already declares one would be a second
  source of truth, and the two could disagree.

      @dataclass Request:
          goal:     E_Goal          # VERDICT | DISPLAY | NOMINAL
          choice:   str|None        # which scenario
          subjects: tuple           # which subjects are judged
          replay:   bool            # provision from stored data
          display:  Display         # WHERE a comparison is shown
          observer: object|None     # the progress seam (12)
          record:   bool|None       # None: follow the store config
          stop_event: object|None   # how the caller stops it

      @dataclass Display:
          target:      E_DisplayTarget|None   # names a driver (11.4)
          adapter:     DisplayAdapter|None    # given, it WINS
          argument_db: dict                   # the driver's own arguments

  A caller asks for an OUTCOME, and the goal selects the operation.

  THE CEREMONY. Each step is here and NOT in an operation, because each
  belongs to a different thing: the lock to a DIRECTORY, the footprint to
  a finished OPERATION, the recording to a delivering RUN.

                    configuration            request
                          |                     |
                          v                     v
              .-----------------------------------------.
     verify   | an unservable configuration is refused   |
              | HERE, before anything runs               |
              '-----------------------------------------'
                          |
     lock     .-----------+-------------------------.
              | the directory admits ONE live       |  busy -> DirectoryBusy
              | holder (6)                          |          (never queued)
              '-----------+-------------------------'
                          |
     operate  .-----------+-------------------------.
              | the goal's operation; sub-processes |
              | activate upon need (2.5)            |
              '-----------+-------------------------'
                          |
     record   .-----------+-------------------------.
              | a Run's subjects -> candidates, so  |  the SAME product
              | Replay has something to read        |  that was judged
              '-----------+-------------------------'
                          |
     footprint.-----------+-------------------------.
              | what happened, overwriting that     |
              | one entry (6)                       |
              '-----------+-------------------------'
                          |
     unlock            however it ended
                          |
                          v
                       Outcome


############################################################################
PART II -- PROVISION  (how the subjects come to exist)
############################################################################

THE STAGES. Provision is ONE type holding its stages as MEMBERS -- a
member that is None is a stage this provision does not have; absence is
DATA, never a null object pretending something ran:

    stage_acquire       the world   -> the DEPENDENCIES  (when declared)
    stage_build         sources     -> the APPLICATION  (COMPILED only)
    stage_execute       application -> raw streams, fanned out
    stage_canonicalise  raw         -> the SUBJECT
    stage_load          store       -> the SUBJECT

EXACTLY ONE PATH: 'stage_execute' and 'stage_load' exclude each other;
acquire, build and canonicalise stand only beside execute -- a loaded
subject is ALREADY canonical, which is why a canonicaliser change
demands a re-run, and REPLAY IS OFFLINE: a replayed test touches no
network, by construction. The invariants are checked at construction,
where the wiring is written.

EVERY STAGE IS A SUPPLIER, AND EVERY SUPPLIER ANSWERS IN ONE SHAPE:

    Supply(product, report, record_list)

The product is the stage's own kind of thing; product None ENDS
provision with the report token; the records are the attribution --
kept even in failure. A failure token may ride BESIDE a product (a
stalled run still delivers its partial streams; they are compared, and
the token speaks). No stage raises, so provision failure is test
failure and the suite runs on (2.6). Which reason SPEAKS among stages
is the ORCHESTRATOR'S merge -- a stage never knows its upstream. And
one shape keeps the door open: 'supply()' is already a future, so a
stage may later become a REQUEST to a scheduling component (a build
queue that orders its work) without any caller learning of it.

A stage that must not repeat its work REMEMBERS it: 'StageBuild' and
'StageAcquire' memoize, so wiring the SAME instance into every
Provision concerned is 'build if necessary' -- and 'ask the world
once' -- at suite scale. Sharing is the planner's deliberate act.

ACQUISITION IS A SUPERVISED CALL, LEFT OPEN. An 'AcquireItem' is a
name, a SATISFACTION CHECK, and a command: satisfied is SKIPPED (the
make semantics -- a suite runs twice without re-fetching the world),
absent runs the command under its own procsitter (the wall clock
contains a hung mirror, the disk cap a runaway download), and a command
that 'succeeded' while the check still says absent has FAILED. The
stage does not interpret what a command does -- curl, git, an
installer: the caller's affair. Discipline: acquire INTO the test's own
directory; pin what you fetch (a commit, a checksum, an exact version)
or the test is not reproducible.

'Run' (3) and 'Replay' (5) are PLANNERS -- functions that wire the one
Provision type; 'provision_of' chooses between them from the request.
Nothing downstream can tell a subject's provenance by type (2.4); the
'.kind' attribute exists for OBSERVATION only.

----------------------------------------------------------------------------
3  RUN -- provision by execution
----------------------------------------------------------------------------

A source becomes a command by its KIND; the command runs contained; its
raw output is canonicalised per subject; taps record it for later Replay:

    source_file
        |  COMPILED: build ---------\
        |  INTERPRETED: [interp, source] >-- argv --> procsitter.run
        |  EXECUTABLE: [source] ----/                (caps enforced)
        |                                                |
        |                                     raw stdout/stderr, files
        |                                                |
        |                              canonicalise (pype, per subject)
        |                                                |
        |                                      CANONICALISED subject --> compare
        |                                        |            |
        |                                    (tap raw)   (tap canonicalised
        |                                        |         + timing)
        |                                        v            v
        +--------------------------------------> R E C O R D  (section 4)

The configuration of all this is PER TEST APPLICATION (2.7), and it
AGGREGATES its sub-components' own structs rather than restating them:

  @dataclass TestConfiguration:
      source_file:      str              # THE IDENTITY. Its STEM keys the
                                         #   build directory -- stems must
                                         #   be unique across tests (below)
      source_kind:      E_SourceKind     # EXECUTABLE|INTERPRETED|COMPILED
      interpreter:      Sequence[str]|None  # argv prefix, INTERPRETED
                                            #   (['lua'], ['python3','-u'])
      test_directory:   str              # the PLACE; see below

      caps:             ProcsitterConfig    # procsitter's OWN struct, held
                                            # VERBATIM -- never copied out
      build:            BuildConfig|None    # the build's OWN struct; None
                                            # unless COMPILED
      store:            StoreConfig|None    # the Store's OWN struct:
                                            # directory, raw, timing
                                            # (section 4); None: no record

      choice_db:        dict     # choice name | None ->
                                 #   TestChoiceConfiguration

  @dataclass TestChoiceConfiguration:
      canonicalisers:   dict     # subject name -> pype argv; a subject
                                 # absent is compared RAW (raw ==
                                 # canonicalised for it)
      compare:          Configuration   # compare's OWN struct, held
                                        # VERBATIM (2.7). ONE per choice:
                                        # the compare SETUP for this
                                        # scenario

  E_SourceKind: EXECUTABLE | INTERPRETED | COMPILED

A CHOICE is a SCENARIO of this one application -- an entry in the map, not
a configuration of its own. The choice name is the command line argument
that selects it.

THE 'None' CHOICE. A test that mentions no choices has the single key
'None': the application is called ONCE, with NO choice argument. So the
map is EITHER '{None: ...}' or a map of named choices with no 'None' in
it; the two never mix, and 'has this test choices' is answered by looking
for that one key.

FLAT, NOT INHERITED. Every entry is COMPLETE as handed in (2.7): an
author who states one canonicaliser for the whole test states it once, and
whatever builds the configuration puts it into every entry. No step here
resolves a default, and no value's origin has to be traced.

THE PLACE. Three roles, three directories, never one:

    test_directory/                 the application RUNS here
        BUILD/<source-file-stem>/   the build of THIS test runs here
        OUT/                        the application's output files

The build has its own sub directory, and one PER TEST, keyed by the source
file's stem: 'parse.c' builds in 'BUILD/parse'. So a build writes no
object file where the application writes its output, and two tests of one
source tree never share a build directory -- which is what makes running
them CONCURRENTLY safe without a lock.

ONE RUN OF A TEST AT A TIME. NEVER two runs of the same test in parallel.
This covers its CHOICES: 'BUILD/<stem>' is per test, not per choice, so two
choices running at once would share one build directory. Different tests may
run concurrently -- that is what the per-test build directory buys -- and the
same test never overlaps itself.

  So 'OUT/', 'BUILD/<stem>' and the test's footprint entry (section 6) each
  have exactly ONE writer at any moment, and none of the three needs a lock.

  NOTE, AND A REQUIREMENT ON WHOEVER BUILDS CONFIGURATIONS: two source
  files with the SAME STEM would build in the same directory -- 'parse.c'
  and 'parse.lua' both in 'BUILD/parse'. COLLIDING stems must therefore
  be REFUSED where the configurations are made. This component holds ONE
  TestConfiguration at a time and cannot see its siblings, so it cannot
  check this; it only states the requirement (see also DISCUSSIONS.txt,
  the configuration file).

CANONICALISATION is provision, not comparison: a pype stage is HOW a raw
stream becomes the comparable stream. It lives here (per subject), never
in the compare-side map (section 7) and never in Replay (already applied).


----------------------------------------------------------------------------
4  RECORDING -- capturing a Run for a later Replay
----------------------------------------------------------------------------

CANONICALISED (essential). The canonicalised stream per subject is exactly
what compare reads, so it is stored whenever 'record_directory' is set
(a listener tee'd onto the chain edge, procsitter 7.4). A subject with
no canonicaliser has raw == canonicalised and is stored once.

RAW (optional; 'record_raw', default off). The pre-pype stream: it may
OVERFLOW the log, and for a canonicalised subject is never compared or
displayed, so it serves only forensic inspection ('stdout_log_before_pype').

TIMING (optional; 'record_timing', default off). The per-line DELTA time
of the RAW cadence -- TINY (one number per line), so captured even when
the raw CONTENT is too big to keep (orthogonal to 'record_raw'). Two uses
of the one measurement: (1) an analyst aid, timing beside the diff; (2) a
HOST COMPUTE-SPEED reference -- a recording from host X vs current host Y
is a speed ratio that normalises expectations. Raw deltas and a host tag
are kept; the ratio is derived on demand, being pairwise.

  STORED SEPARATELY, never interleaved into the canonicalised record --
  which stays byte-exact, and whose pipe into compare is therefore
  untouched. Separateness is a TECHNICALITY of storage, not a second
  artifact the caller handles: the timing series sits inside the subject's
  stored record behind the STORE (section 6), and the Store reports
  whether a subject carries one. Nothing above the Store sees a file.

  ONE LIMIT, from the ORDER. The cadence is a property of the RAW stream;
  the stored record is the CANONICALISED one, and a canonicaliser may
  REORDER. So use (2), a whole-run speed reference, always holds; use (1),
  a delta beside each displayed line, holds only where raw order IS
  canonicalised order -- a subject with no canonicaliser. Elsewhere the
  series describes the run, not the record's lines.

THE SILENCE CAP (optional). No output on either production port for an
absolute gap ends the call, attributed FAIL_STALLED. It is a PROCSITTER
CAP -- 'max_output_gap_sec', held in the 'ProcsitterConfig' of the
configuration (2.7), so it needs no setting here and protects builds
exactly as it protects runs. A wall clock bounds a call that is WORKING;
this one bounds a call that is WAITING. The brief report renders it as
TEST_APP_STALLED (section 13).

  A gap measured against the RECENT CADENCE rather than an absolute
  number was considered and is not built: cadence varies legitimately
  between phases of one run, so it would fail in the dangerous direction
  -- ending a healthy call that has merely slowed.

THE STORE. A candidate RECORDING holds, per subject, the canonicalised
stream and its optional raw and timing sidecars -- nothing else. Replay
reads a candidate; Accept PROMOTES one to the nominal. Both live behind the
STORE abstraction (section 6); where and how it keeps them is a backend
detail. What HAPPENED during the run is not kept with the streams; it is a
FOOTPRINT (section 6).


----------------------------------------------------------------------------
5  REPLAY -- provision by stored data
----------------------------------------------------------------------------

No execution: the stored CANONICALISED readers of a previous Run are read
straight into compare. NO source, NO caps, NO pype, NO procsitter --
provision is already done. The procsitter/pype configuration is
EXCLUSIVELY a Run concern.

  @dataclass Replay:
      record_directory: str        # where a prior Run recorded
      test_directory:   str|None   # context for output-file subjects


----------------------------------------------------------------------------
6  THE NOMINAL -- the accepted subject record
----------------------------------------------------------------------------

A subject is compared against a NOMINAL: the canonicalised subject stream
of a run whose behaviour was ACCEPTED and written to storage. Available AT
ANY TIME by reading storage ALONE -- no execution, build, interpreter, or
procsitter. It is the "accepted" role of the one artifact (2.3).

  A Nominal is a reader over a stored subject record:

      class Nominal:                     # a reader over a subject record
          def open(self) -> reader       # opened lazily, closed by the op
      RecordNominal(path)     the accepted record on storage -- the
                              everyday case (the "GOOD")
      StreamNominal(reader)   an existing reader / pipe (tests)
      BytesNominal(data)      in-memory (tests)

Handing the user a Nominal (not compare's own types) keeps component
types out of the config and unifies nominal with subject. A comparison
always reads the CURRENTLY accepted record -- no 'record-time vs current'
ambiguity, nothing to embed. Acceptance (section 10) is what WRITES a
nominal.

THE STORE. All record access -- read a nominal, read/write a candidate,
write on Accept -- goes through a STORE keyed by (test, choice, subject).

      Accept  --write-->  +---------+  <--read--  EquivalenceCheck /
                          |  STORE  |             DifferenceDisplay / Replay
                          +---------+
                          default backend: the HWUT GOOD filesystem
                          (another -- a DB, an object store -- fits behind
                           the SAME interface)

The Store's own struct, held verbatim by the configuration (2.7):

  @dataclass StoreConfig:
      directory:     str    # WHERE artifacts live; absent, the test's
                            #   own directory serves
      record_raw:    bool   # also keep the PRE-canonicalisation stream
      record_timing: bool   # also keep the per-line cadence (4)

THE FOOTPRINTS. Beside the records the Store keeps what HAPPENED, most
recently -- the RECENT FOOTPRINTS OF EXECUTION. This is what a recursive
listing over results reads ('hwut info' in HWUT today).

JSON. One entry per test and choice, one sub-entry per OPERATION:

    { "parse": {
        "basic": {
          "Run":     { "when": "2026-07-26T09:14:03Z",
                       "host": "linux-x86_64/ws-07",
                       "verdict": true,
                       "report": "OK",
                       "canonicaliser": { "stdout": ["python3",
                                          "hwut_pype.py", "clean.pype"] },
                       "compare": { "numeric_tolerance_ratio": 0.01 } },
          "Accept":  { "when": "2026-07-20T11:02:55Z",
                       "host": "linux-x86_64/ws-07" },
          "Display": { "when": "2026-07-26T09:15:40Z",
                       "host": "linux-x86_64/ws-07" } } } }

ONE FOOTPRINT FILE PER TEST DIRECTORY, holding every test in it. A
recursive listing walks directories and reads one file from each. Entering
and leaving a directory is a CEREMONY in any case; reading and writing that
file is part of it.

THE DIRECTORY IS THE LOCK -- 'DirectoryLock', taken with 'with', raising
'DirectoryBusy' when a live process holds it. Consistency is kept at
directory level, not per file -- one lock guards the directory's footprint
file and its tests' output alike, and it is what keeps two runs of a hwut
application out of each other's way.

    acquire   'mkdir' of a lock sub directory. 'mkdir' either creates or
              fails; it cannot half-succeed, so the winner is decided
              without a second mechanism.
    holder    the lock names its holder: (PROCESS ID, WHEN IT STARTED).
              The PAIR is what identifies -- a process id alone does not,
              since the system reuses them.
    steal     LIVENESS IS ASKED, NOT INFERRED. If no process of that id
              started at that time exists, the holder is gone: remove the
              lock and retry. No expiry, no heart beat, no clock skew, and
              a crashed run never leaves a lock behind it.
    release   the lock directory is removed on exit.

  A loser of the steal race simply fails its next 'mkdir' and waits, so
  removal needs no agreement between the removers.

  WHERE THE PAIR CANNOT BE HAD, DO NOT LOCK. An operating system that
  cannot report when a process started cannot support concurrent hwut
  sessions, and a user on such a system knows it. This is the same
  degradation shape procsitter already applies to its platform-dependent
  caps: report the reduced capability, do not pretend to it.

'report' is the brief report token (section 13), so a failure names itself:
BUILD_FAILED, TARGET_NOT_BUILT, TEST_APP_STALLED, and the rest.

NOT A HISTORY. Exactly ONE entry per (test, choice, operation), OVERWRITTEN
each time, by the single writer that section 3 guarantees. What was done
BEFORE is the concern of the software configuration
management system -- git and its kin -- and never of this component. A
footprint answers "what is the state of this test now", not "what has been
done to it". No append, no rotation, no log.

THE VERDICT SITS HERE, not in the record. A verdict belongs to an EXECUTION
EVENT; the stored streams are artifacts of provision. Re-comparing one
record against an edited nominal must be free to yield a different verdict,
which it cannot be if the verdict is welded to the stream.

BOTH HALVES OF FREEING ARE RECORDED, and for the same reason: a record is
history, and the configuration may have moved since.

    'canonicaliser'  changed the RECORD    -- a Replay whose subject was
                     frozen under one and whose nominal was accepted
                     under another compares two DIFFERENT freeings, and
                     the law of the arms breaks with nothing able to
                     say so.

    'compare'        changed the VERDICT   -- 'verdict: true' means one
                     thing under a strict setup and another under a
                     loose one. Recording only what DIFFERS from
                     compare's default: a default setup adds nothing,
                     and a footprint does not grow whenever compare
                     gains an option.

Neither names a tolerance or a pype flag: both walk whatever the lower
component declares, so an option invented later is recorded the day it is
first used.

The DEFAULT backend is HWUT's GOOD filesystem: a test's stdout nominal IS
the 'TEST/GOOD/<name>.txt' file HWUT already diffs against, and Accept
writing it is HWUT's 'make GOOD'. So testrun's Run -> EquivalenceCheck ->
Accept GENERALISES HWUT's run -> diff -> promote loop to many subjects,
languages, replay, and display. The storage modality (names, persistence)
is the backend's business, not the design's.


############################################################################
PART III -- COMPARISON & THE OPERATIONS
############################################################################

----------------------------------------------------------------------------
7  THE SUBJECTS-TO-NOMINALS MAP  (compare-side; used by the two READERS)
----------------------------------------------------------------------------

PURE COMPARE concern: for each subject, WHAT it is held against.
Canonicalisation is NOT here (it is provision, section 3). Identical
whether the subjects come from a Run or a Replay.

  subjects: dict   # subject name -> Nominal (section 6)
                   #   "stdout" | "stderr" | "<OUT/ file name>"
                   # a subject absent from the map is not judged.

HOW is not here. Compare's tuning is the compare SETUP of the scenario and
lives in 'TestChoiceConfiguration' (section 3), one per choice, as compare's
own struct held verbatim. This map says only WHAT each subject is held
against.

Compare aligns the CANONICALISED subject against the nominal; the raw
stream never enters comparison. This map is shared by EquivalenceCheck
and DifferenceDisplay; Accept has its own per-subject step (section 10).


----------------------------------------------------------------------------
8  EquivalenceCheck -- read -> verdict
----------------------------------------------------------------------------

Investigates CORRECTNESS, fast and fast-fail. Nothing about display.

  @dataclass EquivalenceCheckConfig:
      name:       str
      groundwork: Run | Replay
      subjects:   dict                 # subject name -> Nominal
      compare:    Configuration|None   # the choice's compare setup (3)
      fast_fail:  bool = True          # stop at the first differing
                                       #   subject. Subjects are compared
                                       #   in NAME ORDER, so the same
                                       #   difference is reported on
                                       #   every run.

  class EquivalenceCheck:
      async def run(self, observer=None) -> TestResult

EACH SUB-PROCESS RETURNS ITS OWN RESULT; none is merged into another.

  @dataclass Provision:              # WHAT WAS PROVIDED (3, 5)
      records:     tuple                 # attribution records; empty when
                                         #   provision was by stored data
      report:      E_TestRunResult       # OK, or why provision failed

  @dataclass Comparison:             # WHAT WAS COMPARED -- ABSENT when
      subject_verdict_db: dict           #   provision never delivered
      report:      E_TestRunResult

A noun names the thing provided, not a wrapper around it: 'Provision' and
'Comparison' are PRODUCTS. 'TestResult' keeps its suffix because it is not
a product -- it is DERIVED, folded from whichever products exist.

So "no comparison happened" is an ABSENCE, not a null field in a
half-filled type; and a field's origin is readable from its type rather
than by convention.

THE TEST'S VERDICT IS DERIVED, and belongs to neither of them:

  @dataclass TestResult:
      name:        str
      verdict:     bool                  # folded over what was produced
      report:      E_TestRunResult        # the FIRST reason by precedence
      provision:   Provision
      comparison:  Comparison|None

A FAILED BUILD IS A FAILED TEST. Not "the test could not run": failing to
build is a SHORTCOMING OF THE CODE under test, so the verdict is false and
the report is BUILD_FAILED. The comparison is absent, and the test still
has its result. The precedence of section 13 decides which reason speaks
when more than one could.


----------------------------------------------------------------------------
9  DifferenceDisplay -- read -> feed the aligned comparison
----------------------------------------------------------------------------

Aligns NOTHING and renders NOTHING. It drives the DOWN half of the feed
(section 11): compare produces the aligned comparison, DifferenceDisplay
routes it to a display TARGET, the target's driver renders. Only the
CANONICALISED subject is shown, side by side with the nominal; a recorded
timing channel MAY annotate each line with its delta (analyst aid, never
part of a verdict).

  @dataclass DifferenceDisplayConfig:
      name:           str
      groundwork:     Run | Replay
      subjects:       dict            # subject name -> Nominal
      compare:        Configuration|None
      adapter:        DisplayAdapter|None   # given, it WINS over target
      only_differing: bool = True     # a MATCHING subject is not carried
                                      #   out at all

  class DifferenceDisplay:
      async def run(self, observer=None) -> DifferenceDisplayResult

  @dataclass DifferenceDisplayResult:
      name:        str
      report:      E_TestRunResult
      subject_verdict_db: dict          # the reduction, per subject
      records:     tuple


----------------------------------------------------------------------------
10  Accept -- write the nominal (THIN; the intelligence is EXTERNAL)
----------------------------------------------------------------------------

Acceptance's CONTENT PRODUCTION -- authoring, merging, editing -- is
BEYOND scope: an external tool / IDE / human does it. Our side is thin:
the nominal is WRITTEN FROM A COMPLETE DUMP we did not construct --
replaced WHOLESALE, per subject, in the canonicalised domain. (The dump is
the same KIND of thing as the nominal: a subject record.)

    TAKE_DUMP   a complete dump is HANDED to us (the current output, or a
                dump some external tool produced) -> store it.
    INITIATE    LAUNCH the full-duplex feed (section 11) with an external
                merge/accept session -> EAT its final PLAIN nominal
                stream -> store it.

The external copy / write / merge / manual-merge are distinctions THERE;
from HERE there are only these two.

  @dataclass AcceptStep:
      mode:        E_AcceptMode           # TAKE_DUMP | INITIATE
      dump:        Nominal|None           # TAKE_DUMP: the complete dump
      interaction: object|None            # INITIATE: how to launch + collect
  @dataclass AcceptConfig:
      name:       str
      subjects:   dict                    # subject name -> AcceptStep
      choice:     str|None                # which scenario is accepted
      groundwork: Run|Replay|None         # what Accept PULLS when a step
                                          #   names no dump
      compare:    Configuration|None      # the setup an INITIATE session
                                          #   presents its DOWN under
  class Accept:
      async def run(self, observer=None) -> AcceptResult

  E_AcceptMode: TAKE_DUMP | INITIATE


############################################################################
PART IV -- THE SEAMS
############################################################################

----------------------------------------------------------------------------
11  THE FEED -- protocol, hubs, targets, and the merge loop
----------------------------------------------------------------------------

11.1  THE SESSION -- two hubs, two halves. Feeding a consumer is a session
across a channel; DOWN carries the comparison out, UP carries a human's
resolution back:

    OUR HUB                       channel                  CONSUMER HUB
    (DifferenceDisplay/Accept)  (stdio/socket)             (IDE client)
       |                                                        |
       |==== DOWN: the ASSOCIATION (compare DisplayInst) =======>|  present
       |                                                        |
       |<=== UP: the RESOLUTION (plain nominal + intent) ========|  (merge only)

We DEFINE the protocol and ship OUR hub; each IDE brings its own CONSUMER
hub. DISPLAY uses DOWN only (half-duplex); MERGE uses DOWN then UP
(full-duplex).

11.2  DOWN IS COMPARE'S -- reuse it, do not invent one. compare/feeder/ui.py:

    async feed(config, subject_stream, nominal_stream) -> AsyncIterable[DisplayInst]

runs the association INSIDE and yields immutable DisplayInst items:
ProtocolHeader, ConfigInst (how comparison was set), SectionBeginInst,
LinePairInst (the aligned row: subject cells, nominal cells, cost),
EndOfStreamInst.

  SectionBeginInst carries the BLOCK ID by which an UP addresses that
  block (11.7). It sits THERE and not on every LinePairInst: a client
  folds the stream into a buffer and is stateful whatever we do, so one
  local variable is cheaper than a field on every row, forever. 'feeder/html_feeder.py' is ONE consumer (side-by-side
HTML) -- an example, not the interface.

  THE SIGNATURE in ProtocolHeader versions the PROTOCOL STRUCTURE (the
  message grammar) ONLY -- not the run, content, or process. A hub checks
  it before parsing so it never reads a message with the WRONG PARSER; on
  mismatch it REFUSES rather than mis-read.

11.3  UP IS THE ARTIFACT, NOT THE VIEW. DOWN is a rich PROJECTION for
human eyes; UP is the plain canonicalised NOMINAL STREAM plus a
status -- deliberately ASYMMETRIC. We NEVER reconstruct the nominal from
the feed: compare tokenises and may normalise (whitespace, transparent
tokens, tolerance classes), so unparsing a view back to authoritative
bytes is lossy-risk, and a wrong nominal poisons every future comparison.
Instead, at INITIATE we hand the tool its MATERIAL -- the feed (to
display) AND the plain subject + plain nominal streams (to merge FROM) --
and it returns the plain merged stream. So Accept stays thin and
byte-exact. Only the UP envelope is new; sign/version it like DOWN.

  CONCRETELY:

    @dataclass Resolution:
        intent:       E_Intent      # REALIGN | COMMIT | CANCEL
        nominal_text: str|None      # the PLAIN artifact, never a view
        block_id:     int|None      # REALIGN: the block the edit fell
                                    # into, as NAMED by the last DOWN
                                    # (11.7). None -> realign in full.
        signature:    str           # checked BEFORE the message is read

    E_Intent: REALIGN | COMMIT | CANCEL

  A COMMIT carrying NO artifact is downgraded to CANCEL: committing an
  absent stream would store emptiness as the accepted behaviour. A driver
  with no 'resolve' cancels too -- half-duplex is a driver's choice, not
  a fault.

11.4  THE HUBS AND THE DISPLAY ADAPTER. Our hub drives the session (emit
DOWN, consume UP, reduce to the nominal stream). It reaches any target
through ONE interface -- a DisplayAdapter stating a required SEQUENCE:

    open  ->  present each DOWN item  ->  (merge: yield an UP)  ->  close

A DRIVER implements that sequence for ONE tool; its connection mechanics
(a socket, a pipe, mergetool files) are the driver's OWN concern -- there
is NO shared 'connection' type. 'E_DisplayTarget' selects the driver
through 'driver_for()' -- the ONE place a target becomes a driver, so
adding a tier touches one function. 'resolve' happens INSIDE the open
session: open -> present -> resolve -> close, since a driver whose
connection IS the session has nothing to answer on once it is closed.

11.5  DISPLAY TARGETS. The shipped interactive tier is the TERMINAL:

    TUI    the always-available interactive tier (interaction/tui.py): renders each
           DOWN generation as text -- setup banner, section boundaries,
           verdict-marked spans, analogy provenance -- and answers
           'resolve' by asking the author: [e]dit hands the nominal to
           '$EDITOR' (the git-commit idiom; the TUI builds no editor),
           [c]ommit, [q]uit. An edit that changed NOTHING is re-prompted
           locally -- the hub's no-progress guard (11.6a) is for broken
           drivers, not for hesitation. Meta this tier shows is meta
           DOWN carries; what DOWN lacks is compare's to emit, never
           the client's to compute.

           The renderer has TWO MARKING VIEWS, same rows, notes and
           banner: the VERDICT view marks what DID differ (bad '[..]',
           tolerated '~..~'); the READING view marks what CAN vary, by
           tolerance kind -- '{numeric}' '~analogy~' '<pattern>'
           '!binding!' '|nothing|' -- with a legend line under the
           banner. The reading of ONE stream is that stream fed against
           ITSELF: every pair equivalent by construction, so only the
           INTERPRETATION shows. One renderer, no second feeder.

           TWO SERVICE FACES share one argument language (services/core.py:
           '-' is stdin; --numeric/--pattern/--nothing name the setup):

           'hwut merge' (services/merge.py): any subject stream/file against any
           nominal -- UI on stderr, the artifact on '-o PATH' or
           stdout, written ONLY on commit (exit 0; a CANCEL exits 1 and
           writes nothing). Knows nothing of GOOD/ -- storing stays
           Accept's (10).

           'hwut compare' (services/compare.py): display only, never writes --
           the rendering IS the product, so it goes to STDOUT; exit is
           the diff convention (0 equivalent, 1 differing). With ONE
           argument it displays the READING of that stream.

Beyond the terminal -- TWO TIERS. No semantic diff/merge protocol exists
to adopt (verified: LSP/DAP prove the "one protocol, many editors"
pattern, but for language/debug, not comparison). So:

    RICH   OUR feed IS the protocol (the LSP move). Any IDE
    tier   ---- speaks ----> DisplayInst (DOWN) + our UP envelope
           A thin client per IDE, signature-versioned, transport-neutral;
           carries compare's SEMANTICS and the merge loop. Clients live in
           compare/feeder/ beside html_feeder. First client e.g. nvim.

    BASIC  the GIT MERGETOOL / DIFFTOOL convention -- what editors ALREADY
    tier   speak. Any editor
           ---- via ----> files: BASE / LOCAL / REMOTE / MERGED
           Universal (vimdiff, vscode, ...), zero per-editor code, but
           DUMB (naive line diff, no tolerances/analogies). Its MERGED
           file IS the plain dump Accept eats -> drops into TAKE_DUMP.

RICH where a client exists, BASIC everywhere else. The reason to write a
rich client is exactly what mergetool CANNOT do: semantic equivalence and
guided merge.

11.6  THE MERGE LOOP -- who keeps display and content coherent. Editing
the nominal can change the ALIGNMENT, which is COMPARE'S; so during a
merge WE are the alignment service and the IDE stays thin (it owns
EDITING and RENDERING). The SUBJECT is FIXED throughout -- only the
nominal evolves:

    human edit
        |
        v
    IDE --UP: REALIGN (working nominal, plain bytes)-->  OUR HUB
                                                            |
                                         compare.feed(subject, working)
                                                            |
    IDE  <--------- DOWN: fresh association -----------------+
     |  re-render, human edits on ...   (repeat)
     |
     +--UP: COMMIT (final nominal)-->  Accept stores it (section 10)
        (or CANCEL -> nominal unchanged)

Each round keeps the DISPLAY (alignment) and the CONTENT (nominal) in
lockstep, without the IDE embedding compare and without us unparsing a
view. UP thus carries an INTENT with its plain bytes:

    REALIGN  a working nominal -> a fresh DOWN
    COMMIT   the final nominal  -> stored
    CANCEL   abandon; the nominal is unchanged

11.6a  THE TWO GUARDS -- ending a session that would not end on its own.
'merge_session()' (interaction/feed.py) is the HUB that drives the loop above; the
sequence in full, one ROUND at a time:

    HUB (merge_session)                          DRIVER (adapter)
     |                                              |
     |------------ open(subject_name) ------------->|         ONCE
     |                                               |
     |  .--------------- ROUND ---------------------.
     |  |                                            |
     |  |  compare.feed(subject, working)             |
     |  |  yields DOWN items ...                      |
     |  |----------- present(item) * ----------------->|   * once per item
     |  |                                              |
     |  |----------- resolve(subject, working) -------->|
     |  |<---------- Resolution(intent, text) ----------|
     |  |                                              |
     |  |  intent is COMMIT or CANCEL?  ---------------------> break, keep intent
     |  |  text is None or == working?  -> NO-PROGRESS GUARD -> CANCEL, break
     |  |  round_n >= max_round_n?      -> THE CAP          -> CANCEL, break
     |  |  else: working = text, round_n += 1               -> another ROUND
     |  '--------------------------------------------.
     |                                                |
     |------------ close() -------------------------->|         ONCE
     |
    returns (working or None, intent) to the CALLER

'open' and 'close' happen ONCE, outside the loop -- a driver whose
connection IS the session (a pipe, a socket) has nothing to answer on
once it is closed. Each ROUND is an independent, exact
'compare.feed(subject, working nominal)': nothing carries over between
rounds, and nothing needs to, since the streams are held as plain text.

Two guards end the loop as a CANCEL -- the nominal is left exactly as it
was -- so a broken or adversarial driver can never hang the session:

    NO-PROGRESS GUARD   a REALIGN with no artifact, or one byte-identical
                        to the round before it, cannot align to anything
                        new. Refused AT ONCE -- no extra round is
                        computed. This catches the ordinary bug (a
                        driver echoing its input back unchanged) on the
                        very next round, and it never touches an author,
                        since every real edit progresses.

    THE CAP              'max_round_n' rounds (default MERGE_ROUND_MAX =
                        1000), then the session ends anyway. The
                        backstop for a driver that OSCILLATES -- always
                        answering with a DIFFERENT nominal, so it never
                        trips the no-progress guard, yet never commits
                        or cancels either. The default is deliberately
                        far above any human merge.

A COMMIT that carries no text is also downgraded to CANCEL (11.3):
storing emptiness would record it as accepted behaviour.

11.7  RE-ASSOCIATION IS BLOCK-SCOPED, AND THE BLOCK IS NAMED BY COMPARE.
A realignment re-folds the BLOCK the edit fell into, not a window computed
from the edit. A block is a CHUNK: a region is one, and a run of outer
lines is one. Compare made the chunks, so compare NAMES them; the IDE only
repeats the name it was given -- alignment never leaves compare.

    DOWN   SectionBeginInst(block_id=7, ...)     compare names the block
             LinePairInst  ...
           SectionBeginInst(block_id=8, ...)
             LinePairInst  ...          <-- the author edits here
    UP     REALIGN(block_id=8, working nominal)  the IDE quotes it back
    DOWN   a fresh association, block 8 re-folded

WHY A BLOCK AND NOT A WINDOW. A window has to be DERIVED -- a start backed
to an anchor, an end confirmed by a run of stable pairs, a widen where a
region straddles it. A block needs no derivation: it is a boundary compare
already drew, and an edit lies inside exactly one. The block also cannot
be straddled -- a region is atomic, since its analogy frame starts EMPTY
and is dropped (compare, D-13), so there is no mid-region state to resume
from.

THE COST IS PAID IN LATENCY, DELIBERATELY. Realignment is triggered by the
author or by a slow timer, never per keystroke. The delay fits the moment
it serves -- "let us see how that change develops" -- and buys the thing a
window was never able to give: the rest of the view does not move. Block
scope is therefore about DISPLAY STABILITY, not about speed.

TWO LAWS THE IDs OBEY:

    PER GENERATION.  Each DOWN issues its ids afresh. An UP quoting an id
                     from an older generation is REFUSED, not guessed at
                     -- the same discipline the protocol signature obeys
                     (11.2).
    FRAMING VOIDS.   An edit that adds or removes a '##!' or '####'
                     changes the block structure itself, so no id denotes
                     what it denoted: every id is void and the realignment
                     is a FULL re-fold. Detected by re-scanning the
                     working nominal's framing, before any id is honoured.

WHAT COMPARE OWES: one MODE of the association it already has -- start the
fold at a named block instead of at the beginning, using the state that
'ChunkPair' already carries. Not a second algorithm beside 'feed()'.

CORRECTNESS NEEDS NO JUDGEMENT: re-folding from block B must equal
'feed(subject, working nominal)' -- an exact oracle, not a sample. And
COMMIT always does a FULL re-align regardless, so a scoping mistake costs
at most a briefly imperfect DISPLAY, never a wrong nominal.


----------------------------------------------------------------------------
12  THE OBSERVER  (progress seam -- all operations)
----------------------------------------------------------------------------

Orthogonal to the display TARGET: the observer WATCHES a run unfold (a
console log, a database of record); the target RECEIVES the comparison.
Duck-typed, all methods optional; fan-out to several is a composite
(observers ADD).

    an observer implements what it cares about; there is NO base class
    to inherit, and a method it lacks is not a fault:

        def started(self, name, groundwork_kind): ...
        def built(self, build_report): ...        # COMPILED Run only
        def verdict(self, subject_name, ok): ...
        def finished(self, result): ...

    Operations call through 'notify(observer, method, *args)', which is
    silent for a missing method AND for one that RAISES: an observer
    watches, and nothing it does may reach a verdict. So a new call site
    never breaks an existing observer.

  Shipped: ConsoleObserver, NullObserver (default), ObserverGroup (they
  ADD, as consumers do in 'tee()'). Web / db observers are
  the caller's, against this protocol.


----------------------------------------------------------------------------
13  THE BRIEF REPORT  (verdict vocabulary -- reused, lightly extended)
----------------------------------------------------------------------------

E_TestRunResult (vut.auxiliary.test_run_result) already carries OK,
NOT_EQUIVALENT_WITH_NOMINAL, TEST_APP_*, OUTPUT_FILE_NOT_FOUND,
NOMINAL_FILE_NOT_FOUND, and the PYPE_* / BUILD_* / TARGET_NOT_BUILT
families -- REUSED. ADDITIONS: SOURCE_NOT_FOUND, INTERPRETER_NOT_FOUND,
RECORDING_MISSING (Replay, no usable recording), TEST_APP_STALLED,
DISPLAY_TARGET_UNREACHABLE. Precedence: source/build reasons outrank run
reasons outrank subject/nominal reasons.


############################################################################
PART V -- REFERENCE
############################################################################

----------------------------------------------------------------------------
14  NAMES
----------------------------------------------------------------------------

  package           a PACKAGE, not one module, one module per concern:
                      configuration.py    TestConfiguration,
                                          TestChoiceConfiguration (3)
                      provision/          the stage package (3, 5):
                        core.py             Supply, Subjects, Provision,
                                            Run, Replay, provision_of
                        stage_<name>.py     ONE module per stage, named
                                            like the member that holds
                                            it: acquire, build, execute,
                                            canonicalise, load -- class
                                            'Stage<Name>' inside
                        build.py            BuildConfig, the build TOOL
                                            under stage_build (3)
                      store.py            Store, StoreConfig (4, 6)
                      nominal.py          Nominal and its kinds (6)
                      operations/         the three operations (2.5):
                        equivalence_check.py   EquivalenceCheck (8)
                        difference_display.py  DifferenceDisplay (9)
                        accept.py              Accept (10)
                      interaction/        where a human meets a session:
                        feed.py             the feed session -- protocol,
                                            hubs, drivers (11)
                        tui.py              TuiDisplay -- the terminal
                                            tier, two marking views (11.5)
                        nvim/               the nvim client (11.5)
                      services/           the service faces (11.5):
                        merge.py            'hwut merge'
                        compare.py          'hwut compare'
                        core.py             what the faces share:
                                            streams and setup flags
                      observer.py         the progress seam (12)
                      report.py           TestResult, Provision,
                                          Comparison, the reason
                                          PRECEDENCE (8, 13)
                      session.py          run_test(), E_Goal -- THE FRONT
                                          DOOR and its ceremony (2.8)
  groundwork        Run | Replay
  operations        EquivalenceCheck | DifferenceDisplay | Accept
  configs           EquivalenceCheckConfig | DifferenceDisplayConfig |
                    AcceptConfig
  enums             E_SourceKind | E_DisplayTarget | E_AcceptMode
                    (+ reused E_BuildSystem, E_TestRunResult)
  reference         Nominal (RecordNominal | StreamNominal | BytesNominal)
  storage           Store (keyed by test name + subject; default backend =
                    the HWUT GOOD filesystem)
  display           DisplayAdapter (required-sequence interface); a Driver
                    implements it per tool (nvim, html, mergetool)
  directory fields  test_directory, record_directory; OUT/ (output subdir)
  file field        source_file
  args fields       application_arguments, build_arguments
  caps              max_wall_clock_sec, max_memory_mb, ...  (plain numbers)
============================================================================
