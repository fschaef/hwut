"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FAILURES, ONE TABLE (display D-31, D-34). Every reason a
         case can fail -- one member of 'E_Failure' per wire token the
         run or the report writes -- with its category, the word that
         stands before '[FAIL]', its phrase, and the explanation
         'hwut.help' gives.

'_brief_failure_db' comes first and holds what a reader looks up most:
the category and the word before '[FAIL]', one line per failure.
'failure_db' builds each 'Failure' from it through '_failure()', and is
frozen. A token the wire grows later and this table does not carry is
read as 'failed' by 'word.reason_word()', never swallowed.

A DEVIATION is a plain difference from GOOD: the ordinary business of
a test (ruled 2026-09-29). It carries no word before '[FAIL]' and needs
no help.
______________________________________________________________________________
"""
from dataclasses import dataclass
from enum        import Enum
from types       import MappingProxyType
from typing      import Optional


class E_Failure(Enum):
    """One member per reason a case fails; the value is the wire token
    the run writes into the book's 'report' column."""
    ACQUISITION_FAILED          = "acquisition-failed"
    BUILD_CONTAINED             = "build-contained"
    BUILD_FAILED                = "build-failed"
    BUILD_TOOL_NOT_FOUND        = "build-tool-not-found"
    CONSTRAINT                  = "constraint"
    DISPLAY_TARGET_UNREACHABLE  = "display-target-unreachable"
    FRAME_FAILED                = "frame-failed"
    INTERPRETER_NOT_FOUND       = "interpreter-not-found"
    LAUNCH_FAILED               = "launch-failed"
    MISDEP                      = "misdep"
    NO_GOOD_FILE                = "no-good-file"
    NOT_IN_BOOK                 = "not-in-book"
    NOMINAL_FILE_NOT_FOUND      = "nominal-file-not-found"
    NOMINAL_WITHOUT_END         = "nominal-without-hwut-end"
    NOT_EQUIVALENT_DIVERGED     = "not-equivalent-diverged"
    NOT_EQUIVALENT_GREW         = "not-equivalent-grew"
    NOT_EQUIVALENT_SHRANK       = "not-equivalent-shrank"
    NOT_EQUIVALENT_WITH_NOMINAL = "not-equivalent-with-nominal"
    OUTPUT_FILE_NOT_FOUND       = "output-file-not-found"
    PYPE_CONTAINED              = "pype-contained"
    PYPE_FAILED                 = "pype-failed"
    PYPE_FILE_NOT_FOUND         = "pype-file-not-found"
    PYPE_FILE_SYNTAX_ERROR      = "pype-file-syntax-error"
    PYPE_INTERPRETER_NOT_FOUND  = "pype-interpreter-not-found"
    RECORDING_MISSING           = "recording-missing"
    REGION_SYNTAX_ERROR         = "region-syntax-error"
    SOURCE_NOT_FOUND            = "source-not-found"
    SPEC_BROKEN                 = "spec-broken"
    STDERR_UNDECIDED            = "stderr-undecided"
    TARGET_NOT_BUILT            = "target-not-built"
    TERMINATED_WITHOUT_END      = "terminated-without-hwut-end"
    TEST_APP_CONTAINED          = "test-app-contained"
    TEST_APP_CPU_TIME_EXCEEDED  = "test-app-cpu-time-exceeded"
    TEST_APP_DISK_EXCEEDED      = "test-app-disk-exceeded"
    TEST_APP_FILE_SIZE_EXCEEDED = "test-app-file-size-exceeded"
    TEST_APP_LAUNCH_FAILED      = "test-app-launch-failed"
    TEST_APP_MEMORY_EXCEEDED    = "test-app-memory-exceeded"
    TEST_APP_NO_OUTPUT          = "test-app-no-output"
    TEST_APP_PIDS_EXCEEDED      = "test-app-pids-exceeded"
    TEST_APP_SESSION_GONE       = "test-app-session-gone"
    TEST_APP_STALLED            = "test-app-stalled"
    TEST_APP_WALL_CLOCK_EXCEEDED = "test-app-wall-clock-exceeded"
    TEST_CHOICE_VANISHED        = "test-choice-vanished"
    TEST_FAILED                 = "test-failed"
    TEST_VANISHED               = "test-vanished"
    UNACCEPTED                  = "unaccepted"
    UNEXPECTED_STDERR           = "unexpected-stderr"
    UNSTABLE                    = "unstable"
    UNSUPPORTED                 = "unsupported"


class E_FailureCategory(Enum):
    """WHAT WENT WRONG, by where the fault lies (display D-34):

        NOMINAL      the GOOD file is wrong -- missing, unfinished,
                     without its terminal token, broken in its framing,
                     contradicting its own constraints
        BUILD        the application cannot be made or started
        DEVIATION    the subject and the nominal differ -- the ordinary
                     business of a test; no word before '[FAIL]'
        BOOK         the book disagrees with the tree, or stains a case
        EXECUTION    the application ran and misbehaved: killed, cut
                     short, silent, stalled, speaking on stderr, its
                     pype failing
        ENVIRONMENT  what the test stands on: a dependency, the frame,
                     a case it relies on, a display target
    """
    NOMINAL     = "nominal"
    BUILD       = "build"
    DEVIATION   = "deviation"
    BOOK        = "book"
    EXECUTION   = "execution"
    ENVIRONMENT = "environment"


#  THE HEADING A CATEGORY STANDS UNDER (D-35), in HINTS and in
#  'hwut.help': the name, and the state in telegraphic words -- never a
#  sentence (RULED 2026-10-02).
CATEGORY_HEADING_DB = {
    E_FailureCategory.NOMINAL:     "NOMINAL -- error in GOOD file",
    E_FailureCategory.BUILD:       "BUILD -- build or launch error",
    E_FailureCategory.DEVIATION:   "DEVIATION -- output differs from GOOD",
    E_FailureCategory.BOOK:        "BOOK -- book and tree disagree",
    E_FailureCategory.EXECUTION:   "EXECUTION -- application invocation error",
    E_FailureCategory.ENVIRONMENT: "ENVIRONMENT -- error around the test",
}


def category_of(token):
    """
    RETURN: E_FailureCategory, the category of the failure the token
            names; ENVIRONMENT for a token the table does not carry --
            nobody taught it, and it is not the test's own doing.
    """
    failure = failure_of(token)
    return E_FailureCategory.ENVIRONMENT if failure is None \
           else failure.category


#  THE FIXED OPENING OF THE HEALING PARAGRAPH in 'hwut.help' (D-36): one
#  spelling for every failure, so a page that reads it reads one string.
HEAL_OPENER_STR = "In order to heal, "


@dataclass(frozen=True)
class Failure:
    """
    ONE REASON A CASE FAILS, everything said about it in one place.

        failure_id              the member of 'E_Failure'
        category                the member of 'E_FailureCategory'
        comment_before_FAIL_str the word standing before '[FAIL]' in
                                the run and the report; None for a
                                DEVIATION, which carries no word
        description             the phrase the HINTS block speaks
        what                    what the failure means -- 'hwut.help'
        heal                    how a person resolves it -- 'hwut.help',
                                printed after 'HEAL_OPENER_STR'
        sanitize                how 'hwut.sanitize' heals it: the
                                aspect and the verb; None where no
                                sanitize command does
    """
    failure_id:              E_Failure
    category:                E_FailureCategory
    comment_before_FAIL_str: Optional[str]
    description:             str
    what:                    str
    heal:                    str
    sanitize:                Optional[str] = None

    def is_deviation(self):
        """RETURN: bool, whether this is a plain difference from GOOD --
                   no word before '[FAIL]', no help needed."""
        return self.category is E_FailureCategory.DEVIATION

    def paragraph_list(self):
        """
        RETURN: list of str, the paragraphs 'hwut.help' prints for this
                failure, each a fixed string of the table: what it
                means; how it is healed, opening 'In order to heal, ';
                and how 'hwut.sanitize' heals it, where a command does.
        """
        result = [self.what,
                  HEAL_OPENER_STR + self.heal[0].lower() + self.heal[1:]]
        if self.sanitize is not None: result.append(self.sanitize)
        return result


_C = E_FailureCategory
_F = E_Failure

#  THE BRIEF: failure -> (category, the word before '[FAIL]'). The one
#  screen a reviewer reads to know what the run will say.
_brief_failure_db = {
    #  NOMINAL
    _F.NOMINAL_WITHOUT_END:         (_C.NOMINAL,    "no <hwut-end> marker"),
    _F.CONSTRAINT:                  (_C.NOMINAL,    "constraint"),
    _F.UNACCEPTED:                  (_C.NOMINAL,    "unaccepted"),
    _F.REGION_SYNTAX_ERROR:         (_C.NOMINAL,    "region"),
    _F.NO_GOOD_FILE:                (_C.NOMINAL,    "no GOOD file"),
    _F.NOMINAL_FILE_NOT_FOUND:      (_C.NOMINAL,    "no GOOD file"),
    _F.NOT_IN_BOOK:                 (_C.NOMINAL,    "not in book"),
    #  BUILD
    _F.LAUNCH_FAILED:               (_C.BUILD,      "no-launch"),
    _F.TEST_APP_LAUNCH_FAILED:      (_C.BUILD,      "no-launch"),
    _F.SOURCE_NOT_FOUND:            (_C.BUILD,      "no-launch"),
    _F.INTERPRETER_NOT_FOUND:       (_C.BUILD,      "no-launch"),
    _F.SPEC_BROKEN:                 (_C.BUILD,      "spec"),
    _F.BUILD_FAILED:                (_C.BUILD,      "no-build"),
    _F.TARGET_NOT_BUILT:            (_C.BUILD,      "no-build"),
    _F.BUILD_TOOL_NOT_FOUND:        (_C.BUILD,      "no-build"),
    _F.BUILD_CONTAINED:             (_C.BUILD,      "no-build"),
    #  DEVIATION
    _F.NOT_EQUIVALENT_WITH_NOMINAL: (_C.DEVIATION,  None),
    _F.NOT_EQUIVALENT_GREW:         (_C.DEVIATION,  None),
    _F.NOT_EQUIVALENT_SHRANK:       (_C.DEVIATION,  None),
    _F.NOT_EQUIVALENT_DIVERGED:     (_C.DEVIATION,  None),
    _F.TEST_FAILED:                 (_C.DEVIATION,  None),
    #  BOOK
    _F.TEST_VANISHED:               (_C.BOOK,       "no-app"),
    _F.TEST_CHOICE_VANISHED:        (_C.BOOK,       "no-choice"),
    _F.UNSTABLE:                    (_C.BOOK,       "unstable"),
    #  EXECUTION
    _F.UNEXPECTED_STDERR:           (_C.EXECUTION,  "stderr"),
    _F.STDERR_UNDECIDED:            (_C.EXECUTION,  "stderr"),
    _F.TERMINATED_WITHOUT_END:      (_C.EXECUTION,  "cut-short"),
    _F.TEST_APP_NO_OUTPUT:          (_C.EXECUTION,  "no-output"),
    _F.TEST_APP_STALLED:            (_C.EXECUTION,  "no-output"),
    _F.RECORDING_MISSING:           (_C.EXECUTION,  "no-output"),
    _F.OUTPUT_FILE_NOT_FOUND:       (_C.EXECUTION,  "no-output"),
    _F.TEST_APP_CONTAINED:          (_C.EXECUTION,  "killed"),
    _F.TEST_APP_WALL_CLOCK_EXCEEDED: (_C.EXECUTION,  "killed"),
    _F.TEST_APP_CPU_TIME_EXCEEDED:  (_C.EXECUTION,  "killed"),
    _F.TEST_APP_MEMORY_EXCEEDED:    (_C.EXECUTION,  "killed"),
    _F.TEST_APP_FILE_SIZE_EXCEEDED: (_C.EXECUTION,  "killed"),
    _F.TEST_APP_PIDS_EXCEEDED:      (_C.EXECUTION,  "killed"),
    _F.TEST_APP_DISK_EXCEEDED:      (_C.EXECUTION,  "killed"),
    _F.TEST_APP_SESSION_GONE:       (_C.EXECUTION,  "no-session"),
    _F.PYPE_INTERPRETER_NOT_FOUND:  (_C.EXECUTION,  "pype"),
    _F.PYPE_FILE_NOT_FOUND:         (_C.EXECUTION,  "pype"),
    _F.PYPE_FILE_SYNTAX_ERROR:      (_C.EXECUTION,  "pype"),
    _F.PYPE_CONTAINED:              (_C.EXECUTION,  "pype"),
    _F.PYPE_FAILED:                 (_C.EXECUTION,  "pype"),
    #  ENVIRONMENT
    _F.MISDEP:                      (_C.ENVIRONMENT, "no-dep"),
    _F.ACQUISITION_FAILED:          (_C.ENVIRONMENT, "no-dep"),
    _F.FRAME_FAILED:                (_C.ENVIRONMENT, "frame"),
    _F.DISPLAY_TARGET_UNREACHABLE:  (_C.ENVIRONMENT, "no-display"),
    _F.UNSUPPORTED:                 (_C.ENVIRONMENT, "failed"),
}


def _failure(failure_id, description, what, heal, sanitize=None):
    """
    RETURN: Failure, 'failure_id' with its category and word from
            '_brief_failure_db', and the texts as given.
    """
    category, comment = _brief_failure_db[failure_id]
    return Failure(failure_id, category, comment, description, what, heal,
                   sanitize)


_DEVIATION_WHAT = "The output differs from GOOD -- the ordinary business of a test."
_DEVIATION_HEAL = ("Read 'hwut.run.diff <test> [<choice>]'; mend the code, or "
                   "accept the new output with 'hwut.accept'.")
_CAP_RAISE = ("raise the cap in the header's 'caps { %s = ... }' only for a "
              "test that needs it by nature.")
_CAP_HEAL  = "Look for the cause first; " + _CAP_RAISE

#  THE FAILURES, each once: the phrase HINTS speaks, what it means, how
#  it is healed, and how 'hwut.sanitize' heals it where it can.
failure_db = MappingProxyType({f.failure_id: f for f in (
    #  NOMINAL
    _failure(_F.NO_GOOD_FILE, "no GOOD file; not accepted, not run",
             "Nothing was ever accepted for this case, so it is not run: "
             "a verdict needs a nominal to compare against (E-41).",
             "Look at its output with 'hwut.run.play <test> [<choice>]', "
             "then accept it: 'hwut.accept <test> [<choice>]'."),
    _failure(_F.NOT_IN_BOOK, "GOOD file stands; case not in GOOD/book.csv",
             "A GOOD file stands for this case, and 'GOOD/book.csv' has no "
             "row for it: it was accepted outside the book -- by a commit, "
             "a copy, another machine -- and has not been run here since "
             "(E-41).",
             "Run it: 'hwut.run <test> [<choice>]' enters the case and "
             "judges it.",
             "'hwut.sanitize.propose --books' proposes 'book <test> "
             "[<choice>]', which enters the standing GOOD file as accepted; "
             "nothing runs, nothing in GOOD/ moves."),
    _failure(_F.NOMINAL_FILE_NOT_FOUND, "GOOD missing",
             "The GOOD file named for a subject cannot be read.",
             "Restore it from git, or accept anew with 'hwut.accept'."),
    _failure(_F.NOMINAL_WITHOUT_END,
             "GOOD file does not end in <hwut-end>",
             "Every stdout GOOD ends in '<hwut-end>' (R-70); this one does "
             "not, so it cannot say what a complete stream is.",
             "Let the test print '<hwut-end>' as its last line (HwutRunner "
             "does so itself; a pype script prints it from '<eof>'), run "
             "it, and accept the new output with 'hwut.accept'."),
    _failure(_F.UNACCEPTED, "GOOD file carries unaccepted lines",
             "GOOD holds a '##! unaccepted' region: an acceptance that was "
             "begun and not finished (an ASPIRANT, B-14).",
             "Finish it: 'hwut.accept.interactive <test> [<choice>]'; or "
             "take the output whole, 'hwut.accept --force'."),
    _failure(_F.REGION_SYNTAX_ERROR, "broken region framing",
             "A '##!' region in GOOD or in the output cannot be read: an "
             "unknown handler, a bad parameter, an unclosed region. The "
             "HINTS line names the line.",
             "Mend the framing in the file the line names; where it is "
             "GOOD, accept anew."),
    _failure(_F.CONSTRAINT, "constraint violated",
             "A constraint of the choice is broken, in the output or in "
             "GOOD, or names a variable the text never binds (E-123). The "
             "finding is written where it was found, in a "
             "'##! constraint-violation' region.",
             "Mend the behaviour, or the constraint in the header, and "
             "accept anew with 'hwut.accept'.",
             "'hwut.sanitize.propose --constraints' proposes "
             "'remark <test> [<choice>]' for every GOOD that breaks its "
             "own constraints: the finding is written into the GOOD and "
             "'GOOD/book.csv' is stained 'constraint'; nothing is removed."),

    #  BUILD
    _failure(_F.BUILD_FAILED, "build failed",
             "The test's build command failed.",
             "Run the build by hand in the test directory and read the "
             "compiler."),
    _failure(_F.TARGET_NOT_BUILT, "target not built",
             "The build ran and the target it should make is not there.",
             "Compare the target name in the header's 'build { }' with "
             "what the build makes."),
    _failure(_F.BUILD_TOOL_NOT_FOUND, "build tool missing",
             "The build tool the header names is not installed or not on "
             "PATH.",
             "Install it, or name the right one in 'build { framework }'."),
    _failure(_F.BUILD_CONTAINED, "build killed by supervisor",
             "The supervisor killed the build: a cap was hit.",
             _CAP_HEAL % "..."),
    _failure(_F.SOURCE_NOT_FOUND, "source file missing",
             "The test's source file is not where the configuration says.",
             "Restore it; or, if the test is gone on purpose, "
             "'hwut.remove <test>'.",
             "'hwut.sanitize.propose --orphans' names the records of an "
             "application that no longer stands, healed by 'forget'."),
    _failure(_F.INTERPRETER_NOT_FOUND, "interpreter missing",
             "The interpreter the test's first line or 'hwut.conf' names "
             "is not installed or not on PATH.",
             "Install it, or name another in 'language-setup { }'."),
    _failure(_F.LAUNCH_FAILED, "launch failed",
             "The test could not be started.",
             "Check that the file is executable and its first line names "
             "an interpreter that exists."),
    _failure(_F.TEST_APP_LAUNCH_FAILED, "application launch failed",
             "The application process could not be started.",
             "Check that the file is executable and its first line names "
             "an interpreter that exists."),
    _failure(_F.SPEC_BROKEN, "@hwut header does not parse",
             "The '@hwut { ... }' block in the test's own header does not "
             "parse, so the test is not a test. The HINTS line names the "
             "fault.",
             "Mend the block ('hwut.config.show <test>' reads it back)."),

    #  DEVIATION
    _failure(_F.NOT_EQUIVALENT_WITH_NOMINAL, "differs from GOOD",
             _DEVIATION_WHAT, _DEVIATION_HEAL),
    _failure(_F.NOT_EQUIVALENT_GREW, "extra lines; GOOD intact",
             _DEVIATION_WHAT, _DEVIATION_HEAL),
    _failure(_F.NOT_EQUIVALENT_SHRANK, "lines missing; rest intact",
             _DEVIATION_WHAT, _DEVIATION_HEAL),
    _failure(_F.NOT_EQUIVALENT_DIVERGED, "differs from GOOD",
             _DEVIATION_WHAT, _DEVIATION_HEAL),
    _failure(_F.TEST_FAILED, "test failed",
             _DEVIATION_WHAT, _DEVIATION_HEAL),

    #  BOOK
    _failure(_F.TEST_VANISHED, "in book, no such test",
             "'GOOD/book.csv' records a test that no longer stands in its "
             "directory; the file and the tree disagree, and only a "
             "person can say which is wrong.",
             "If it moved: 'hwut.rename <old> <new>' or 'hwut.move' "
             "carries its history. If it is gone on purpose: "
             "'hwut.remove <test>'.",
             "'hwut.sanitize.propose --orphans' proposes 'move <test> "
             "<new-dir>' where the application stands in one other "
             "directory with nothing recorded of it there -- its records "
             "are carried after it -- and 'forget <test>' else, which "
             "drops every record of it: nominals, candidates, its row in "
             "'GOOD/book.csv', register id."),
    _failure(_F.TEST_CHOICE_VANISHED,
             "in book, no such choice",
             "'GOOD/book.csv' records a choice the test no longer offers.",
             "If it was renamed: 'hwut.rename'. If it is gone on purpose: "
             "'hwut.remove <test> <choice>'.",
             "'hwut.sanitize.propose --orphans' proposes "
             "'forget <test> <choice>', which drops every record of the "
             "choice."),
    _failure(_F.UNSTABLE, "UNSTABLE -- not run",
             "'hwut.run.stability' saw the case answer differently over "
             "repeats and stained it (B-2): it is not run until proven "
             "steady.",
             "Find the nondeterminism -- time, order, a race, a counter in "
             "a file -- then prove it: 'hwut.run.stability <test> "
             "[<choice>] --repeat=N' with N at least the stain's count. "
             "In an urgent case 'hwut.remove <test> [<choice>]' and "
             "accept afresh."),

    #  EXECUTION
    _failure(_F.UNEXPECTED_STDERR, "unexpected stderr",
             "The application wrote to stderr, and the choice does not "
             "tolerate it (E-5).",
             "Stop the writing; or declare it in the header: "
             "'tolerance { stderr_ignored = true }'."),
    _failure(_F.STDERR_UNDECIDED, "stderr undecided",
             "The application wrote to stderr and nobody has decided what "
             "that means for this choice.",
             "A result of an earlier hwut: run the case again. Where "
             "it writes on purpose, declare it in the header: "
             "'tolerance { stderr_ignored = true }'."),
    _failure(_F.TERMINATED_WITHOUT_END, "output cut short; no <hwut-end>",
             "GOOD ends in '<hwut-end>' and the output does not: the "
             "application stopped before its end -- a crash, an early "
             "exit, a lost line (R-70).",
             "Find why it stopped; 'hwut.run.diff' shows the output as "
             "far as it got."),
    _failure(_F.TEST_APP_NO_OUTPUT, "no output",
             "The application ran and printed nothing.",
             "Check that the choice is handled, and that output is not "
             "buffered away by an early exit."),
    _failure(_F.TEST_APP_STALLED, "stalled; no output",
             "The application stopped producing output and did not end.",
             "Look for a read on stdin, a lock, or a loop; "
             "'hwut.run.play' shows it live."),
    _failure(_F.RECORDING_MISSING, "no recording to replay",
             "A replay was asked for and no recording stands.",
             "Run the case once with 'hwut.run' to record it."),
    _failure(_F.OUTPUT_FILE_NOT_FOUND, "output file missing",
             "The header names an output file the run never wrote (R-71).",
             "Write it, or remove it from 'output = [...]'."),
    _failure(_F.TEST_APP_CONTAINED, "killed by supervisor",
             "The supervisor killed the application: a cap was hit; the "
             "HINTS line names which.",
             _CAP_HEAL % "..."),
    _failure(_F.TEST_APP_WALL_CLOCK_EXCEEDED,
             "killed; wall-clock cap exceeded",
             "The application ran longer than its wall-clock cap.",
             "Look for a hang or a wait first; "
             + _CAP_RAISE % "timeout_sec"),
    _failure(_F.TEST_APP_CPU_TIME_EXCEEDED, "killed; cpu-time cap exceeded",
             "The application used more cpu time than its cap.",
             "Look for a busy loop first; "
             + _CAP_RAISE % "cpu_sec"),
    _failure(_F.TEST_APP_MEMORY_EXCEEDED, "killed; memory cap exceeded",
             "The application used more memory than its cap.",
             "Look for a leak or an unbounded collection first; "
             + _CAP_RAISE % "memory_mb"),
    _failure(_F.TEST_APP_FILE_SIZE_EXCEEDED,
             "killed; file-size cap exceeded",
             "The application wrote a file larger than its cap.",
             "Look for a runaway log first; "
             + _CAP_RAISE % "file_size_mb"),
    _failure(_F.TEST_APP_PIDS_EXCEEDED, "killed; process cap exceeded",
             "The application started more processes than its cap.",
             "Look for a fork loop first; "
             + _CAP_RAISE % "child_process_max_n"),
    _failure(_F.TEST_APP_DISK_EXCEEDED, "killed; disk cap exceeded",
             "The application wrote more to disk than its cap.",
             "Let it clean up as it goes, or write less."),
    _failure(_F.TEST_APP_SESSION_GONE, "not run; process already dead",
             "An interactive application serves several choices; it died "
             "on an earlier one, so this one never ran (O-21).",
             "Mend the choice that carries the cap or the crash; this one "
             "follows."),
    _failure(_F.PYPE_INTERPRETER_NOT_FOUND, "pype interpreter missing",
             "The interpreter the pype names is not installed or not on "
             "PATH.",
             "Install it, or name the right one in 'pype = \"...\"'."),
    _failure(_F.PYPE_FILE_NOT_FOUND, "pype script missing",
             "The pype script the header names is not there.",
             "Restore it, or mend the name in 'pype = \"...\"'."),
    _failure(_F.PYPE_FILE_SYNTAX_ERROR, "pype script syntax error",
             "The pype script does not parse; the HINTS line names the "
             "place.",
             "Mend the script (hwut_pype MANUAL, 'hwut.pype' runs it by "
             "hand)."),
    _failure(_F.PYPE_CONTAINED, "pype killed by supervisor",
             "The supervisor killed the pype filter: a cap was hit.",
             "Look for a loop in the script."),
    _failure(_F.PYPE_FAILED, "pype failed",
             "The pype filter ended with an error.",
             "Run it by hand on the raw output: 'hwut.pype <script> < "
             "OUT/<raw>'."),

    #  ENVIRONMENT
    _failure(_F.MISDEP, "missing dependency",
             "A file or test this case depends on is not there, so the "
             "case was never dispatched (P-6).",
             "Provide it, or mend 'dependency { ... }' in 'hwut.conf'."),
    _failure(_F.ACQUISITION_FAILED, "dependency not acquired",
             "A dependency's acquisition command failed.",
             "Run the command by hand to see why."),
    _failure(_F.FRAME_FAILED, "frame failed",
             "The directory's 'on_entry' or 'on_exit' command failed, so "
             "its tests did not run on solid ground.",
             "Run the command by hand in the directory."),
    _failure(_F.UNSUPPORTED, "supporter failed; not run",
             "A case this one depends on ended badly, so this one was not "
             "run (P-5).",
             "Mend that one first; this one follows."),
    _failure(_F.DISPLAY_TARGET_UNREACHABLE, "display target unreachable",
             "The display target the case names cannot be reached.",
             "Check the target named in the header."),
)})


#  THE POINTER TO 'hwut.help' (D-34): written once at the end of a run
#  or a report where any case failed for a reason that is not a plain
#  deviation from GOOD.
HELP_HINT_STR = "HINT: use 'hwut.help' for explanation of subtle issues."


def subtle_f(token):
    """
    RETURN: bool, whether the token names a failure that is NOT a plain
            deviation -- one 'hwut.help' explains. A token the table
            does not carry counts as subtle: nobody taught it.
    """
    if not token or token == "ok": return False
    failure = failure_of(token)
    return failure is None or not failure.is_deviation()


def failure_of(token):
    """
    RETURN: Failure, the failure the wire token names.
            None, where the token names none -- success, absence, or a
            token this table does not carry.
    """
    try:
        return failure_db[E_Failure(token)]
    except (ValueError, KeyError):
        return None
