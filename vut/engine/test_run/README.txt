============================================================================
VUT-TESTRUN: SPECIFICATION (draft -- for review)
============================================================================

Status:  PROPOSED (not yet implemented); paper design under review.
Layer:   ORCHESTRATION (per test) -- above the applications
         (procsitter_test_app, procsitter_build) and the compare engine.
         Running MANY tests is a HIGHER layer, out of scope (section 15).
Decided: discussion Frank-Rene / Claude, 2026-07.

Reading order: PART I is the whole thing in brief (with the master
diagram); PARTS II-IV are the detail, grouped by concern; PART V is
reference and settled decisions.


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
                 TRANSLATION   -- builds the component configs
                    |             (procsitter / build / compare)
                    v
        +---------- PROVISION -- a reader per subject ------------+
        |  Run :  build -> execute -> determinize                 |
        |         (build)  (procsitter)  (pype)                   |
        |  Replay: read the stored records                        |
        +--------------------------+------------------------------+
                                   | subject readers
                                   |   (stdout / stderr / files)
                                   v
                 NOMINAL  ---->  COMPARE  (aligns two readers)
                (accepted        |
                 record)         |
              +------------------+-------------------+
              v                  v                   v
        EquivalenceCheck   DifferenceDisplay      Accept
         -> VERDICT         -> feed a TARGET      -> write NOMINAL
              |                  |                    |
           OBSERVER          DISPLAY ADAPTER        STORE
         (watch run)        (IDE / mergetool)   (GOOD by default)

2.2  LAYERING. The orchestration owns no heavy machinery; it TRANSLATES
the description into the lower components' configs and WIRES them.

    OPERATIONS    EquivalenceCheck | DifferenceDisplay | Accept
                  (each its own class + config)
        +----------------------------------------------------------+
    GROUNDWORK    Run (execute + contain + record) | Replay (stored)
                  -> the SUBJECTS: stdout / stderr / file readers
        +----------------------------------------------------------+
    TRANSLATION   declarative description -> component configs
                  *** procsitter / build / compare TYPES never appear
                      above this line ***
        +----------------------------------------------------------+
    COMPONENTS    procsitter | procsitter_build | compare  (existing)

2.3  ONE ARTIFACT, THREE ROLES. There is a single kind of artifact -- a
DETERMINIZED SUBJECT STREAM (bytes, stored or produced live) -- wearing
three hats:

              a DETERMINIZED SUBJECT STREAM
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

They share a per-subject core (name, groundwork, subjects); each adds
only what it needs (DifferenceDisplay a display target; Accept its own
per-subject step).

2.6  THE PRINCIPLE: translate and wire; delegate the work. Containment is
procsitter's, building is procsitter_build's, aligning/judging/feeding is
compare's. The user writes PLAIN data -- source file, source kind, limits
as numbers, nominals as readers -- and never constructs a Procsitter, a
build config, or a compare Comparator; the translation layer builds those.


############################################################################
PART II -- PROVISION  (how the subjects come to exist)
############################################################################

----------------------------------------------------------------------------
3  RUN -- provision by execution
----------------------------------------------------------------------------

A source becomes a command by its KIND; the command runs contained; its
raw output is determinized per subject; taps record it for later Replay:

    source_file
        |  COMPILED: build ---------\
        |  INTERPRETED: [interp, source] >-- argv --> procsitter.run
        |  EXECUTABLE: [source] ----/                (caps enforced)
        |                                                |
        |                                     raw stdout/stderr, files
        |                                                |
        |                              determinize (pype, per subject)
        |                                                |
        |                                      DETERMINIZED subject --> compare
        |                                        |            |
        |                                    (tap raw)   (tap determinized
        |                                        |         + timing)
        |                                        v            v
        +--------------------------------------> R E C O R D  (section 4)

  @dataclass Run:
      source_file:      str
      source_kind:      E_SourceKind        # EXECUTABLE|INTERPRETED|COMPILED
      interpreter:      Sequence[str]|None  # argv prefix, INTERPRETED
                                            #   (['lua'], ['python3','-u'])
      build_system:     E_BuildSystem|None  # COMPILED: WHICH tool
      build_targets:    Sequence[str]       # COMPILED
      build_arguments:  Sequence[str]       # COMPILED
      application_arguments: Sequence[str]  # args to the test app
      test_directory:   str                 # runs here; outputs -> OUT/
      # resource limits -- PLAIN NUMBERS, translated to a ProcsitterConfig:
      max_wall_clock_sec: float
      max_cpu_time_sec:   int
      max_memory_mb:      int
      max_pids:           int
      max_file_size_mb:   int
      max_disk_mb:        int
      min_free_disk_mb:   int
      # DETERMINIZATION -- part of provision, per subject (pype argv):
      determinizers:    dict        # subject name -> pype argv; a subject
                                    # absent is compared RAW (raw ==
                                    # determinized for it)
      # RECORDING (section 4):
      record_directory: str|None    # None: do not record
      record_raw:       bool        # also keep the raw pre-pype stream?
      record_timing:    bool        # also keep per-line delta times?
      line_stall_cap_sec: float|None  # stall watchdog (section 4)

  E_SourceKind: EXECUTABLE | INTERPRETED | COMPILED

DETERMINIZATION is provision, not comparison: a pype stage is HOW a raw
stream becomes the comparable stream. It lives here (per subject), never
in the compare-side map (section 7) and never in Replay (already applied).


----------------------------------------------------------------------------
4  RECORDING -- capturing a Run for a later Replay
----------------------------------------------------------------------------

DETERMINIZED (essential). The determinized stream per subject is exactly
what compare reads, so it is stored whenever 'record_directory' is set
(the 'stdout_log_after_pype' tap in procsitter_test_app). A subject with
no determinizer has raw == determinized and is stored once.

RAW (optional; 'record_raw', default off). The pre-pype stream: it may
OVERFLOW the log, and for a determinized subject is never compared or
displayed, so it serves only forensic inspection ('stdout_log_before_pype').

TIMING (optional; 'record_timing', default off). The per-line DELTA time
of the RAW cadence -- TINY (one number per line), so captured even when
the raw CONTENT is too big to keep (orthogonal to 'record_raw'). Two uses
of the one measurement: (1) an analyst aid, timing beside the diff; (2) a
HOST COMPUTE-SPEED reference -- a recording from host X vs current host Y
is a speed ratio that normalizes expectations. FORMAT: a SIDECAR (a
parallel per-line stream), never interleaved into the determinized record
(which must stay byte-exact); raw deltas + a host tag are kept, the ratio
is derived on demand (it is pairwise).

STALL WATCHDOG (optional). No output for an absolute (minute-range) gap,
or a line far exceeding the recent cadence, trips a stop (attributed
TEST_APP_STALLED). It is a PROCSITTER CAP: procsitter already pumps the
stream, so it enforces the gap alongside wall-clock and the rest, and
protects builds too. The Run's stall setting translates to it. (A
proposed procsitter extension -- new cap + containment reason.)

THE STORE. A candidate RECORDING holds, per subject: the determinized
stream, optional raw/timing SIDECARS, and a small MANIFEST (subjects, the
determinizer used, host + timestamp, verdict). Replay reads a candidate;
Accept PROMOTES one to the nominal. Both live behind the STORE abstraction
(section 6); where and how it keeps them is a backend detail.


----------------------------------------------------------------------------
5  REPLAY -- provision by stored data
----------------------------------------------------------------------------

No execution: the stored DETERMINIZED readers of a previous Run are read
straight into compare. NO source, NO caps, NO pype, NO procsitter --
provision is already done. The procsitter/pype configuration is
EXCLUSIVELY a Run concern.

  @dataclass Replay:
      record_directory: str        # where a prior Run recorded
      test_directory:   str|None   # context for output-file subjects


----------------------------------------------------------------------------
6  THE NOMINAL -- the accepted subject record
----------------------------------------------------------------------------

A subject is compared against a NOMINAL: the determinized subject stream
of a run whose behavior was ACCEPTED and written to storage. Available AT
ANY TIME by reading storage ALONE -- no execution, build, interpreter, or
procsitter. It is the "accepted" role of the one artifact (2.3).

  A Nominal is a reader over a stored subject record:

      class Nominal:                     # a reader over a subject record
          def open(self) -> reader       # opened lazily, closed by the op
      RecordNominal(path)     the accepted record on storage -- the
                              everyday case (the "GOOD")
      StreamNominal(reader)   an existing reader / pipe (tests)
      BytesNominal(data)      in-memory (tests)

Handing the user a Nominal (not compare's Comparator) keeps component
types out of the config and unifies nominal with subject. A comparison
always reads the CURRENTLY accepted record -- no 'record-time vs current'
ambiguity, nothing to embed. Acceptance (section 10) is what WRITES a
nominal.

THE STORE. All record access -- read a nominal, read/write a candidate,
write on Accept -- goes through a STORE keyed by (test name, subject).

      Accept  --write-->  +---------+  <--read--  EquivalenceCheck /
                          |  STORE  |             DifferenceDisplay / Replay
                          +---------+
                          default backend: the HWUT GOOD filesystem
                          (another -- a DB, an object store -- fits behind
                           the SAME interface)

The DEFAULT backend is HWUT's GOOD filesystem: a test's stdout nominal IS
the 'TEST/GOOD/<name>.txt' file HWUT already diffs against, and Accept
writing it is HWUT's 'make GOOD'. So testrun's Run -> EquivalenceCheck ->
Accept GENERALIZES HWUT's run -> diff -> promote loop to many subjects,
languages, replay, and display. The storage modality (names, persistence)
is the backend's business, not the design's.


############################################################################
PART III -- COMPARISON & THE OPERATIONS
############################################################################

----------------------------------------------------------------------------
7  THE SUBJECTS-TO-NOMINALS MAP  (compare-side; used by the two READERS)
----------------------------------------------------------------------------

PURE COMPARE concern: for each subject, WHAT it is held against and HOW.
Determinization is NOT here (it is provision, section 3). Identical
whether the subjects come from a Run or a Replay.

  @dataclass SubjectCheck:
      nominal:         Nominal      # the reference production (section 6)
      compare_options: object       # compare's tuning (declarative)

  subjects: dict   # subject name -> SubjectCheck
                   #   "stdout" | "stderr" | "<OUT/ file name>"
                   # a subject absent from the map is not judged.

Compare aligns the DETERMINIZED subject against the nominal; the raw
stream never enters comparison. This map is shared by EquivalenceCheck
and DifferenceDisplay; Accept has its own per-subject step (section 10).


----------------------------------------------------------------------------
8  EquivalenceCheck -- read -> verdict
----------------------------------------------------------------------------

Investigates CORRECTNESS, fast and fast-fail. Nothing about display.

  @dataclass EquivalenceCheckConfig:
      name:       str
      groundwork: Run | Replay
      subjects:   dict                 # subject name -> SubjectCheck

  class EquivalenceCheck:
      async def run(self, observer=None) -> EquivalenceResult

  @dataclass EquivalenceResult:
      name:        str
      report:      E_TestRunResult      # OK or the one reason token
      verdict:     bool
      subject_verdict_db: dict          # subject name -> bool
      records:     tuple                 # attribution records (Run only)

  Internally: Run -> (build? ->) run_test_app(consumer=None);
  Replay -> compare.is_equivalent over the recorded readers.


----------------------------------------------------------------------------
9  DifferenceDisplay -- read -> feed the aligned comparison
----------------------------------------------------------------------------

Aligns NOTHING and renders NOTHING. It drives the DOWN half of the feed
(section 11): compare produces the aligned comparison, DifferenceDisplay
routes it to a display TARGET, the target's driver renders. Only the
DETERMINIZED subject is shown, side by side with the nominal; a recorded
timing channel MAY annotate each line with its delta (analyst aid, never
part of a verdict).

  @dataclass DifferenceDisplayConfig:
      name:       str
      groundwork: Run | Replay
      subjects:   dict                 # subject name -> SubjectCheck
      target:     E_DisplayTarget      # selects the DRIVER (a DisplayAdapter
                                       # implementation, section 11); the
                                       # driver owns its own connection

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
replaced WHOLESALE, per subject, in the determinized domain. (The dump is
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
      name:     str
      subjects: dict                      # subject name -> AcceptStep
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
EndOfStreamInst. 'feeder/html_feeder.py' is ONE consumer (side-by-side
HTML) -- an example, not the interface.

  THE SIGNATURE in ProtocolHeader versions the PROTOCOL STRUCTURE (the
  message grammar) ONLY -- not the run, content, or process. A hub checks
  it before parsing so it never reads a message with the WRONG PARSER; on
  mismatch it REFUSES rather than mis-read.

11.3  UP IS THE ARTIFACT, NOT THE VIEW. DOWN is a rich PROJECTION for
human eyes; UP is the plain determinized NOMINAL STREAM plus a
status -- deliberately ASYMMETRIC. We NEVER reconstruct the nominal from
the feed: compare tokenizes and may normalize (whitespace, transparent
tokens, tolerance classes), so unparsing a view back to authoritative
bytes is lossy-risk, and a wrong nominal poisons every future comparison.
Instead, at INITIATE we hand the tool its MATERIAL -- the feed (to
display) AND the plain subject + plain nominal streams (to merge FROM) --
and it returns the plain merged stream. So Accept stays thin and
byte-exact. Only the UP envelope is new; sign/version it like DOWN.

11.4  THE HUBS AND THE DISPLAY ADAPTER. Our hub drives the session (emit
DOWN, consume UP, reduce to the nominal stream). It reaches any target
through ONE interface -- a DisplayAdapter stating a required SEQUENCE:

    open  ->  present each DOWN item  ->  (merge: yield an UP)  ->  close

A DRIVER implements that sequence for ONE tool; its connection mechanics
(a socket, a pipe, mergetool files) are the driver's OWN concern -- there
is NO shared 'connection' type. 'E_DisplayTarget' selects the driver.

11.5  DISPLAY TARGETS -- TWO TIERS. No semantic diff/merge protocol exists
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

11.7  DIFFERENTIAL RE-ASSOCIATION (optimization). The subject is fixed, so
an edit perturbs the alignment only LOCALLY -- re-align just a WINDOW:

    old association: [ head ......... | edited region | ......... tail ]
                                      ^START           ^END
                                      |<--- WINDOW --->|   (re-sync RUN of
                                                            stable pairs)
    result:          head  +  new window  +  tail (renumbered by the shift)

    START = first affected line pair (nominal side reaches the edit;
            backed to a stable anchor).
    END   = first pair beyond the change where the new alignment
            re-synchronizes with the old (same subject line, same nominal
            content, modulo the line-count shift), confirmed by a RUN of
            stable pairs, not one.

Caveat: compare's GLOBAL features break locality -- ANALOGIES (a
bidirectional subject<->nominal binding) and multi-line regions
(potpourri/verbatim/ignore/table) straddling the window; there, WIDEN or
fall back to full. Because the safe window needs compare's own semantics,
this lives IN compare -- an incremental 'reassociate(prior, changed_span)'
beside feed(). Purely an optimization: COMMIT always does a FULL re-align,
so a miss costs at most a briefly imperfect DISPLAY, never a wrong nominal.


----------------------------------------------------------------------------
12  THE OBSERVER  (progress seam -- all operations)
----------------------------------------------------------------------------

Orthogonal to the display TARGET: the observer WATCHES a run unfold (a
console log, a database of record); the target RECEIVES the comparison.
Duck-typed, all methods optional; fan-out to several is a composite
(observers ADD).

    class Observer:
        def started(self, name, groundwork_kind): ...
        def built(self, build_report): ...        # COMPILED Run only
        def verdict(self, subject_name, ok): ...
        def finished(self, result): ...

  Shipped: ConsoleObserver, NullObserver (default). Web / db observers are
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
14  NAMING  (confirm or adjust)
----------------------------------------------------------------------------

  module            test_run.py  (or a small package: run.py, replay.py,
                    nominal.py, equivalence_check.py, difference_display.py,
                    accept.py, feed.py)
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


----------------------------------------------------------------------------
15  DECISIONS & RESIDUALS  (the seven questions -- all settled)
----------------------------------------------------------------------------

  Q1 FEED / UP HALF (11): UP carries PLAIN nominal bytes (never a view to
     unparse) with an intent REALIGN|COMMIT|CANCEL; merge is an ITERATIVE
     alignment loop (11.6).
  Q2 RECORD STORE (4,6): all access behind a STORE keyed by (test name,
     subject); modality is a backend detail; default = HWUT GOOD (Accept =
     make-GOOD).
  Q3 TIMING FORMAT (4): a SIDECAR, never interleaved; store raw deltas +
     host tag, derive the pairwise ratio on demand.
  Q4 STALL PLACEMENT (4): a PROCSITTER cap (new output-gap cap +
     containment reason); the Run's stall setting translates to it.
  Q5 DISPLAY TARGETS (11.5): TWO TIERS -- RICH = our feed protocol, thin
     per-IDE clients (nvim first, in compare/feeder); BASIC = git
     mergetool/difftool (MERGED -> TAKE_DUMP).
  Q6 CONNECTION TYPE (11.4): none -- the abstraction is a DisplayAdapter
     (a required-sequence interface); a Driver owns its own connection.
  Q7 CORPUS / MANY TESTS: OUT -- a higher orchestration layer over many
     run_test calls.

  CROSS-COMPONENT extensions implied (tracked for implementation): compare
  gains 'reassociate' (11.7); procsitter gains an output-gap/stall cap (4).
  Both small, both optional to the core flow.

  RESIDUALS (detail, not architecture): the exact UP envelope framing; and
  which RICH display client is written first (nvim proposed).
============================================================================
