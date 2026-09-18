==============================================================================
services -- THE COMMAND LINE FACES
==============================================================================

One file per face; each exports 'main(argv, write) -> int'. 'argv' is the
command line WITHOUT the program's own name; 'write' takes one line at a
time and is 'print' where none is given, so a test drives a face without a
process. Every face answers '--help' with its full documentation and takes
'--directory=<path>', reading the current directory else.

EXIT STATUS, common to every face -- ONE enum, 'E_ExitCode'
('_exit.py'); every face returns its members and nothing else:

    0  OK       nothing refused, nothing failed
    1  FAULT    a fault was met, or a test failed; the face still
                printed what stands
    2  REFUSED  the command line cannot be READ: an unknown option, a
                malformed wish, a directory that does not exist --
                refused at the door, by name, with the usage line
    3  EMPTY    the command line reads, and asks for NOTHING: a wish
                that selects no test, a tree holding no test directory
  141  SIGPIPE  the unix convention 128+13: the reader hung up; the
                face went quiet instead of crashing

The faces:

    hwut.config.show   (lib/config/show.py)
                 what the framework READ: the configuration as a tree,
                 syntax checked, defaults resolved. One file's, or the
                 whole directory's. '--no-default' drops what nobody
                 stated; '--provenance' names the place of every stated
                 value; '--gnu' names it as 'file:line:column'. The
                 printed form is the specification language itself and
                 can be read back (R-50).

    hwut.plan    (plan.py)
                 what the framework INTENDS: the test plan -- nodes,
                 links, exclusion sets (see orchestrator/plan). The
                 selection keywords state the wish: '--fail', '--pass',
                 '--since=<point>', '--until=<point>', '--glob
                 <target>' (several times, OR'ed among themselves;
                 kinds AND'ed). A point is a span ('2h') or an anchor
                 ('yesterday', 'last-week', 'monday', 'january'),
                 reckoned in UTC. The plan is printed, never read back:
                 to replay is to re-determine (plan/RATIONALE, P-4).
                 The Bookkeeper is made here and handed down, only
                 where the wish asks the base.

    hwut.run     (run.py)
                 what the framework RUNS: the live tree run. Explores
                 below the root, applies the same wish as 'hwut.plan',
                 dispatches through the real test-run dispatcher, and
                 renders the event stream live in the tier-1 console
                 form (display/plain.py). Four tiers ('--verbose',
                 '--plain', '--quiet', '--silent') and a colour
                 decision ('--colour', '--no-colour') govern the
                 rendering. '--no-store' suppresses recording; '--jobs'
                 bounds parallel work per directory.

    hwut.accept  (accept.py, accept_first.py, accept_adapt.py,
                  _accept_common.py)
                 ONE FACE (E-59), switching on whether this is a FIRST
                 acceptance -- no nominal stands -- or an ADAPTATION of
                 a standing GOOD. The author chooses no face and no
                 flag. 'accept_first' builds what a first acceptance
                 records; 'accept_adapt' reads what stands;
                 '_accept_common' holds what BOTH rely on --
                 classification, the closing-token rule, the reading of
                 a candidate -- because the atomic refusal spans the
                 whole SELECTION and neither half may own it.

                 ACCEPT IS PARTIAL BY DEFAULT (E-60). Without
                 '--force', a first acceptance records the candidate's
                 SHAPE with nothing decided: one '##! unaccepted'
                 region per subject chunk, one filler line per line of
                 it, the closing token outside every region. The report
                 says 'undecided', never 'blessed'. The next run reads
                 '[ ?! ]' (O-25) -- a decision still owed, not a
                 failure. '--force' is the old blessing: the candidate
                 whole.

                 A CHANGE IS MERGED HERE where stdin and stderr are
                 terminals, through the same engine
                 'hwut.accept.interactive' runs ('lib/accept/
                 engine.py'). Off a terminal -- a pipe, a script, a
                 suite -- it says so and '--force' still overwrites: a
                 face that cannot ask must not decide.

                 PROMOTION: a recorded candidate becomes the NOMINAL,
                 the pole every later run is judged against --
                 'Store.accept()' is the only way a nominal comes to
                 exist, and this face is the only thing that calls
                 it. Selection is the wish; a positional short form
                 desugars into '--glob'. A standing nominal is a
                 CHANGE and 'hwut.accept.interactive's business: detected, named,
                 left alone unless '--force' says otherwise.
                 STDERR IS NEVER SUBJECT TO TESTING: never promoted;
                 where it spoke, refused until '--stderr-tol' notes
                 it IGNORED. A stdout candidate whose last line is
                 not '<hwut-end>' is refused outright: an incomplete
                 stream is never promotable, and no flag bypasses.
                 THE UPDATE CHECK stands before every other: a
                 recording whose mtime is older than the test file's
                 is refused, by name, and the test is named to be
                 re-run. One file is consulted -- the application --
                 not what it reads.
                 A BARE 'hwut.accept' WALKS THE TREE, as 'hwut.run'
                 does; '--directory=<path>' reads one directory.
                 It RUNS ON NECESSITY: a case whose recording is
                 older than its source is run before it is judged;
                 '--force-run' runs every case regardless.
                 It does not read a file of targets: that is
                 'hwut.accept.apply'.

    hwut.accept.propose
                 (lib/accept/propose.py)
                 BLESSES NOTHING, RUNS NOTHING. Reads what stands and
                 writes the differing cases as a file to hand back to
                 'hwut.accept -f'. Its whole content is a list of
                 REPLACEMENTS:

                     # TEST RUN: <dir>/<test-app> <choice>
                     # -- [4711] OUT:  "<what the run produced>"
                     #    [4712] OUT:  "<and the next, if it differs>"
                     # => [4721] GOOD: "<what stands today>"
                     #    [4722] GOOD: "<and the next>"
                     <dir>/<test-app> <choice>

                 ACCEPT THIS AND THE 'OUT' LINE BECOMES THE NOMINAL,
                 in place of the line in brackets; nothing else in
                 the nominal moves. An empty 'OUT' is a nominal line
                 that GOES; an empty bracket a line that ARRIVES. A
                 line that agrees does not appear at all.

                     SUBJECT                 NOMINAL
                       Hans was a nice man.    Hans was a Nazi.
                       Berta was his bride.    Berta was his bride.
                       Frederik was a baker.   Frederik was a maker.

                     # TEST RUN: suite/TEST/story.sh
                     # -- [1] OUT:  "Hans was a nice man."
                     # => [1] GOOD: "Hans was a Nazi."
                     # -- [3] OUT:  "Frederik was a baker."
                     # => [3] GOOD: "Frederik was a maker."
                     suite/TEST/story.sh

                 Both sides are QUOTED and start at ONE column, so
                 space at either end is visible; the text shown is
                 THE FILE'S OWN LINE, not the engine's compared cell
                 -- what becomes the nominal is what you see. A case
                 over the bound gets ONE line and no target:

                     DIFF(suite/TEST/big.sh choice) > 5 lines

                 '-o <file>' IS REQUIRED and takes the proposal; what
                 CANNOT be proposed goes to STDOUT, one line each, so
                 the file holds nothing but what can be blessed and is
                 handed back unedited save for the targets refused.

                 THE WISH NARROWS, IT DOES NOT DECIDE. Every word
                 'hwut.accept' takes is taken here and means the same.
                 '--fail' is SUPERFLUOUS -- a proposal is by
                 construction about what differs -- and misleading: it
                 selects on the BOOK's last verdict, a memory, where
                 the proposal is a measurement taken now. Edit a
                 nominal by hand and the book still says the case
                 passed; '--fail' then hides a real difference.

                 THE PLACES ARE THE COMPARE ENGINE'S. Two lines are
                 one place where 'compare.associate' pairs them under
                 that choice's own tolerances; a difference the run
                 holds EQUIVALENT is never proposed. '<n>' bounds the
                 PAIRS, not the bytes: a case with more is named as a
                 comment alone, never as a target -- a difference
                 nobody read is not one to bless in bulk. ONLY A
                 DIVERGENCE IS PROPOSED -- the four 'not-equivalent-*'
                 verdicts; every other names a run that BROKE, and
                 what it left is wreckage, not a pole. Two further
                 cases are silent: no candidate (nothing ran, nothing
                 to judge) and no nominal (a first blessing is
                 deliberate, E-41).

    hwut.accept.apply
                 (lib/accept/apply.py)
                 blesses the targets a file names, one per line,
                 '<dir>/<test-app> <choice>'. A line's PATH is
                 separated from its NAME, so a target is matched in
                 ITS directory and nowhere else; '#' and blank lines
                 are skipped, which is how a reader vetoes, and which
                 makes 'hwut.accept.propose's output this face's
                 input unedited. The word is the tree's own:
                 'hwut.sanitize' reports and acts on '--apply'.
                 IT REPORTS TWO SECTIONS, 'EXECUTION:' and 'REPORT:',
                 in the style a run's report wears, closing on
                 'Accepted <n>/<m>'. Grouped by directory as a run
                 groups, a test application written once however many
                 of its choices stand below it; the verdict
                 RIGHT-ALIGNED and alone in carrying colour -- green
                 '[DONE]', red '[ERROR]' -- then one sentence per
                 failure, in the shape of a run's HINTS. Every
                 line of the file is answered, a target that matched
                 nothing included. The refresh is silent here.

                 IT ASKS NOTHING. '--force' and '--dont-ask' are both
                 implicit: the file cannot exist unless somebody read
                 the change -- propose writes no target it has not
                 shown, line by line -- and the reader deleted what he
                 refused. THE READING IS THE CONSENT, and the EDITING
                 is the answer to every per-key question, given in
                 advance and in writing.

    hwut.remove  (remove.py)
                 '<test>' forgets a test whole, '<test> <choice>' one
                 choice of it -- the words every face reads (E-53); a
                 path enters its directory ('_target.py'). Nominals,
                 candidates and every sidecar, the book entry with its
                 stain, the register id retired. NOT touched: the
                 application, its 'hwut.conf', 'OUT/'. Asks first
                 unless '--dont-ask'. A test not in the book is not an
                 error. SEVERAL AT ONCE is 'hwut.remove.propose' and
                 'hwut.remove.apply'.

    hwut.remove.propose
                 (lib/remove/propose.py)
                 REMOVES NOTHING. Walks the tree and writes, as a file
                 to read, every test run whose record has lost its
                 ground -- 'app absent', 'choice not offered',
                 'nominal absent, book entry stands' -- the reason in
                 a few words above each target; where the absent
                 application stands ELSEWHERE in the tree the reason
                 says 'possibly moved to <there>', so a directory
                 split is not mistaken for a death. The judgement is
                 'hwut.sanitize's ('orphans'), through its own
                 functions: an application that stands but cannot be
                 explored is UNREACHABLE, never proposed. WHERE A TEST
                 OF THAT NAME STANDS ELSEWHERE the note says
                 ', possibly moved to <dir>' -- the same base-name map
                 'adm/rescue_goods.py' uses for stranded nominals,
                 built here from exploration -- and the answer is
                 probably to carry the history across rather than
                 forget it. '-o <file>'
                 is required; a directory whose exploration faulted is
                 named on stdout and not judged.

    hwut.remove.apply
                 (lib/remove/apply.py)
                 forgets what such a file names, per directory, through
                 'hwut.remove', one target at a time. '--dont-ask' is
                 implicit -- the reading was the consent. Reports as
                 'hwut.accept.apply' does, closing on 'Forgotten n/m'.

    (adm/bundle.sh)
                 '--app <name>' bundles ONE FACE whole -- its module,
                 its launchers, its tests and their GOOD files, plus
                 everything it imports ('--deps', implied). The
                 documents of every directory touched come BY DEFAULT
                 ('--no-doc' to leave them): work that changes a
                 component maintains its documents, and a bundle that
                 omitted them would invite them to drift.

    hwut.rename  (rename.py)
                 '<app> -to <app'>' renames a test whole; '<app>
                 <choice> -to <choice'>' one choice of it; '<app> -to
                 <path>/<app'>' renames AND carries the test into
                 '<path>'; a fresh name that is an existing directory
                 means INTO it, the name unchanged. '-to' is a keyword;
                 the words before it, one or two, say app or choice. A
                 choice never crosses a directory. The app word may be
                 a path ('_target.py'); '--directory' names the
                 source. What follows: nominals, candidates, sidecars,
                 the error witness, the coverage record, the book
                 entry, the register entry, the labels ('_follow.py',
                 last). WITHIN a directory the register keeps the id.
                 ACROSS one the source register retires it, the
                 target issues a fresh one, the book entry is given up
                 by the source and adopted by the target
                 ('Bookkeeper.adopt'), and the coverage record is
                 re-seated under the fresh id through coverage's
                 'seated'. A fresh name standing in the target's book
                 OR register is refused before anything moves. NOT
                 TOUCHED, NOT EDITED: the application file, its
                 '@hwut' block, any 'hwut.conf' apps section -- READ
                 AND SAID instead, as NOTE lines before 'Proceed?':
                 the application under the old name (git mv it), a
                 block or section still declaring the old choice or
                 name (edit it), a file under neither name; a file
                 under BOTH names is refused. '--no-warning' drops
                 the notes, '--silent' everything but a refusal or a
                 fault. Asks first unless '--dont-ask'. Exit status per
                 E-1.

    hwut.move    (move.py)
                 '<app> <app'>' is 'hwut.rename <app> -to <app'>',
                 word for word; two words, no more.

    _target.py   A TEST NAMED BY PATH ENTERS ITS DIRECTORY. A bare
                 word 'a/TEST/keep.sh' whose directory part is literal
                 (no '*', '?', '[') means: enter 'a/TEST', perform
                 'keep.sh' there, one directory explored -- '..' and
                 absolute paths included -- on every face that takes
                 test words ('entered()': run, plan, wishlist, report,
                 accept, play, show, remove, rename,
                 move, stability; 'cov' by forwarding). A directory
                 part carrying a glob metacharacter is a wish glob
                 with a path member (E-15), over the tree below, and
                 so is every '--glob' argument. A relative path is
                 read against '--directory' where one was said; an
                 absolute path stands on its own and must lie within
                 it. Two words naming two directories are refused, as
                 is an absolute path outside '--directory'.

    hwut.diff    (diff.py)
                 'SUBJECT NOMINAL': how two files compare (the VERDICT
                 view). 'FILE' without an '@hwut' block: how compare
                 READS it. Otherwise THE STORE FORM: the wish, a test,
                 a test and a choice, a path word entering its
                 directory ('_target.py'), '--directory' for one
                 directory, the tree below the cwd else; every
                 selected case whose stdout candidate is not
                 equivalent to its nominal -- compare's engine, the
                 choice's own setup, judged NOW -- is shown, one
                 banner each; more than one: a CHECKLIST first
                 ('lib/checklist.py': a number works that case,
                 '<enter>' the first unhandled -- printed beside its
                 number -- 'n' the next page, 'q' quits; '[X]' says
                 HANDLED, and the menu is re-entered until nothing is
                 left); '--all' skips it.
                 '-y' two columns, subject LEFT, nominal RIGHT
                 ('viewers/tui.py'); '--width N'. Rendering on stdout;
                 exit 0 equivalent, 1 shown differing, 2 unusable, 3
                 no case selected. Display only; the merge is
                 'hwut.accept.interactive's.

    the merge engine   (lib/accept/engine.py)
                 THE SESSION LOOP, the three writes of an acceptance
                 (E-41) and every refusal, in ONE implementation. Both
                 doors call it, so a rule about promotion cannot hold
                 at one and not the other. 'adapter_for' picks the
                 tier; 'run_sessions' holds one session per key;
                 'refusal' asks 'hwut.accept's own questions; 'report'
                 prints the block both doors print.

    the keyed session   (lib/viewers/keyed/)
                 THE MERGE WITH KEYS (E-61), a viewer tier reached
                 where stderr is a terminal. Subject left, nominal
                 right; TWO CURSORS, and Tab decides which pane the
                 movement keys drive -- a MODE SWITCH FOR A SUBSET of
                 the keymap, since the takes, undo, realign and the
                 leaving acts mean the same in either pane.

                 THREE TAKES, each with its own scope, so no marked
                 range ever crosses a region border: Enter, the marked
                 subject range into the marked nominal range; 'a', this
                 region into its associated region; 'A', the complete
                 subject over the complete nominal. Copying is always
                 line-wise, left to right; 'e' remains the one way to
                 alter text. A take inside an 'unaccepted' region
                 SPLITS it and an emptied region is REMOVED, framing
                 and all; no region of any other kind is ever CUT, on
                 either side.

                 THE TARGET is derived from the alignment and TRACKS
                 the subject range while VIRGIN; entry never latches it,
                 modification does. 'g' asks compare again and the
                 banner counts takes since it did.

                 THE SEAM: 'prompt_toolkit' owns the Windows, the
                 scrolling and the search; VUT owns the merge state --
                 'state.py' and 'reduce(state, act) -> state', pure, no
                 terminal -- because the derived target, the latch, the
                 whole-range take and the split are RULINGS, and a
                 ruling belongs in a module that can state it. Key ->
                 act is ONE TABLE ('keymap.py') and the bindings are
                 generated from it. Where the import fails, 'driver_for'
                 hands back the TUI tier and the line-based session
                 runs: a merge is NEVER hard-failed for a missing
                 import.

    hwut.accept.interactive   (lib/accept/interactive.py)
                 the cases a wish selects whose stdout candidate is
                 not equivalent to its nominal (measured now, as
                 'hwut.diff'), the checklist, then ONE SESSION PER
                 CASE on stderr: the view ('-y' two columns), then
                 [t]ake the subject whole, [e]dit the nominal,
                 [c]ommit the nominal as it stands, [q]uit. COMMIT IS
                 THE ACCEPTANCE: 'store.accept', the register, the
                 book's acceptance note -- 'hwut.accept's three
                 writes. Refused at commit in 'hwut.accept's words: a
                 stained choice, a text without the closing token,
                 stderr that spoke ('--stderr-tol'). The candidate
                 STAYS as the run left it: a partial acceptance is
                 visible at the next run. E-51's NAME for the engine
                 above; 'hwut.accept' reaches the same loop. A case
                 with NO nominal is now this face's too (E-60): it
                 provisions the candidate itself, the way 'hwut.accept'
                 refreshes (E-40), and opens on the mirror.

    hwut.report.details   (lib/report/details.py)
                 the pack of a test -- metadata head, source, GOOD,
                 OUT with the cadence inside, coverage where a record
                 was harvested -- for handing to another pair of
                 eyes. The words are the wish's ('_cases.py'): every
                 selected case is packed in turn, one pack each, walk
                 order; '-r' verbatim; '--no-coverage'. Stdout; exit 3
                 where nothing is selected.

    _exit.py     THE EXIT STATUS LAW (E-1) and THE GUARD (E-55). One
                 enum every face relates to: OK, FAULT, REFUSED,
                 EMPTY, SIGPIPE 141, SIGINT 130, SIGTERM 143.
                 'guarded(name, main)' wraps every face's entry point:
                 a terminal signal leaves ONE line on stderr,
                 '<face> ended forcefully.', the shell's own 128+n
                 code, and no traceback -- the interpreter's teardown
                 noise silenced with it.

    _cases.py    THE STORE-READING BLOCK every such face runs between
                 its words and its work: entered path, the climb, the
                 wish with its targets, the labels view, the selection
                 (one directory under '--directory', the tree
                 otherwise), the cases grouped by directory;
                 'differing_keys' measures each case's stdout
                 candidate against its nominal with compare's
                 'is_equivalent' under the choice's setup. THE
                 CHECKLIST IS NOT HERE: 'lib/checklist.py' owns the
                 menu and the marks, shared by every face that offers
                 a list.

    hwut.pype    (pype.py)
                 the pype LINE-MATCHING FILTER, as a face. The language
                 -- parser, modes, trace, usage line -- lives in
                 'test_writing_support/hwut_pype' and is tested there;
                 this face owns the DOOR: '--help' on stdout, 0; no
                 argument naming an existing script, or a dangling
                 '--pype-dir', refused with the usage, 2; a script that
                 does not parse, 1; 'sys.exit(n)' inside a python block
                 leaves untouched. Every other option is handed to the
                 interpreter unread. A '#! /usr/bin/env hwut.pype'
                 she-bang line reaches it by PATH.

    hwut.target  (target.py)
                 one USER-DEFINED TARGET run over every directory that
                 binds targets (E-7):

                     hwut.target <option-list> <target> <passed-through>

                 A directory takes part where its 'hwut.conf' carries a
                 'target { }' binding; definition is membership.
                 Everything after the target name goes to each
                 directory's script, argv-style, untouched. TWO PHASES:
                 phase one settles the plan and a refusal there costs
                 zero executions; per directory, three reasons decide,
                 in order:

                     1  file present
                     2  file executable
                     3  shebang's interpreter executable
                        (where a shebang decides)

                 '-i, --ignore' turns any refusal of a directory into a
                 skip; '--default=<script>' fills absence; '+x' sets
                 a+x where the executable bit is missing, never done
                 without it; '-q, --quiet' drops the per-directory
                 output recording. Phase two executes, each directory
                 under its DirectoryLock, cwd the directory itself,
                 environment inherited unchanged. TARGETS ARE NOT
                 TESTS: exit codes are reported, never deciding -- the
                 face answers 0 iff phase one accepted and every
                 planned script was found and executed; 3 where no
                 directory binds any target.

A fault does not withhold the output: a directory with one broken header
prints the fault, then the tree or the plan of what stands, and answers 1.


THE CONSOLIDATION: every command line face lives HERE -- one door for
the tool, under ONE NAMING LAW:

    hwut.<name>  <=>  vut/services/<name>.py  ('-' <=> '_')
                      ('python3 -m vut.services.<name>')
    its launcher <=>  vut/bin/hwut.<name>
    its suite    <=>  TEST/test-<name>.py or TEST/test-<name>.sh

A DOTTED NAME IS A PACKAGE (disc-8): a family of faces on one subject
shares a package, the dot in the launcher naming the directory:

    hwut.<p>.<name>  <=>  vut/services/<p>/<name>.py
    its launcher     <=>  vut/bin/hwut.<p>.<name>
    its suite        <=>  vut/services/<p>/TEST/test-<name>.sh (or .py)

Every plain '<name>.py' in this directory IS a service; a module that
is NOT a service is underscore-prefixed ('_core.py', '_config.py' --
private helpers of the operations faces). 'lib/config/show.py' and
'plan.py' face the orchestrator; 'diff.py' and 'lib/report/details.py'
face
the operations component. 'stability.py' faces NO component: it runs
'run.py' repeatedly and reads what the Bookkeeper kept -- a face over
a face, which is where a question about SEVERAL runs belongs.
'wishlist.py' faces the exploration alone: it selects and prints, and
runs nothing. 'pype.py' faces 'test_writing_support/hwut_pype': the
interpreter is test-writing support, and the face is the tool's door to
it. 'play.py' runs ONE choice and renders the reading of
what it produced under that test's own setup; it judges nothing and
records nothing. The faces that take a wish also take its SHORT FORM --
'hwut.run test-app.sh one', bare words as targets. '_follow.py' is the one place a renamed or removed name
reaches the records at the tree's boundary; the rename and removal
faces call it last. 'labels/' is the first dotted family:
'hwut.labels.create', '.add', '.remove', '.list' and '.query' -- five
acts on 'hwut-root.labels', the file of the tree's SETS OF RUNS, which
stands beside 'hwut-root.conf' at the boundary. 'remove.py' (and its choice form) faces the Bookkeeper
and the register, and runs nothing either. A healing face on a stored subject reads
the Bookkeeper; its run-fallback re-enters the orchestrator -- a face
importing both sides sits above both, which is here.
