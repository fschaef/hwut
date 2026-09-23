"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE BRIEF REPORT of a run: 'ok', or the reason of failure --
       one token, printable, greppable.

DESCRIPTION
       'E_TestRunResult' condenses a supervised run into one
       classification. The detailed evidence stays available (the
       attribution records, the per-subject verdicts, the stderr
       tails); this enum is the HEADLINE.

       The enum is meant to be EXPANDED as further run kinds join --
       the BUILD_* / TARGET_* members (sandbox_build.py) are the
       first such growth beyond the judged test application run.
       Values are dashed report tokens; 'str(result)' prints them.
______________________________________________________________________________
"""
from enum import Enum


class E_TestRunResult(Enum):
    OK                          = "ok"

    # THE SOURCE: nothing could even be attempted.
    SOURCE_NOT_FOUND            = "source-not-found"
    INTERPRETER_NOT_FOUND       = "interpreter-not-found"

    # THE JUDGEMENT: everything ran; the subject does not match. The
    # THREE SHAPES OF A DIFFERENCE say WHERE TO LOOK, never who is
    # wrong: all three are FAIL, and which side is at fault -- a GOOD
    # blessed under an older framework, a filter that stopped
    # filtering, a change in the code -- is the reader's to decide.
    #   GREW      every recorded line still stands, in order; lines
    #             stand between or around them
    #   SHRANK    every line that stands was recorded, in order; lines
    #             the GOOD holds are gone
    #   DIVERGED  neither: a recorded line changed or moved
    #  THE NOMINAL CARRIES LINES NOBODY DECIDED ('##! unaccepted', compare
    #  C-9): the comparison cannot pass, and it is not a regression.
    UNACCEPTED                  = "unaccepted"
    NOT_EQUIVALENT_WITH_NOMINAL = "not-equivalent-with-nominal"
    NOT_EQUIVALENT_GREW         = "not-equivalent-grew"
    NOT_EQUIVALENT_SHRANK       = "not-equivalent-shrank"
    NOT_EQUIVALENT_DIVERGED     = "not-equivalent-diverged"

    # THE TESTIMONY: nothing ran, and nothing will, until it is cleared.
    # A choice that came out 'ok' in one repeat and not in another bore
    # FALSE WITNESS about the unit beneath it. It is not asked again --
    # there is nothing to learn from asking a liar -- until
    # 'hwut.run.stability' repeats at least as often as convicted it and
    # finds every verdict alike, or the test is removed and re-accepted.
    UNSTABLE                    = "unstable"

    # THE TEST APPLICATION:
    TEST_APP_LAUNCH_FAILED      = "test-app-launch-failed"
    TEST_APP_CONTAINED          = "test-app-contained"
    #  THE MULTI ROAD (O-21): the one process serving every choice
    #  died -- of a cap, named on the choice that was running -- and
    #  THIS choice was never served. Not killed: never begun.
    TEST_APP_SESSION_GONE       = "test-app-session-gone"
    #  ONE TOKEN PER CAP (O-19): which cap was hit is the verdict's word.
    TEST_APP_WALL_CLOCK_EXCEEDED = "test-app-wall-clock-exceeded"
    TEST_APP_CPU_TIME_EXCEEDED   = "test-app-cpu-time-exceeded"
    TEST_APP_MEMORY_EXCEEDED     = "test-app-memory-exceeded"
    TEST_APP_FILE_SIZE_EXCEEDED  = "test-app-file-size-exceeded"
    TEST_APP_PIDS_EXCEEDED       = "test-app-pids-exceeded"
    TEST_APP_DISK_EXCEEDED       = "test-app-disk-exceeded"
    TEST_APP_NO_OUTPUT          = "test-app-no-output"
    TEST_APP_STALLED            = "test-app-stalled"

    # REPLAY: no usable recording to provision from.
    RECORDING_MISSING           = "recording-missing"

    # THE SUBJECTS AND NOMINALS:
    OUTPUT_FILE_NOT_FOUND       = "output-file-not-found"
    NOMINAL_FILE_NOT_FOUND      = "nominal-file-not-found"
    TERMINATED_WITHOUT_END      = "terminated-without-hwut-end"
    UNEXPECTED_STDERR           = "unexpected-stderr"
    #  The REGION FRAMING of a compared text is broken -- an unknown
    #  handler, a bad parameter, a nested or unclosed region. The text
    #  arrived; it cannot be READ. That is a verdict with a reason,
    #  not an exception: raised through, it dies in the scheduler as
    #  'Task exception was never retrieved' and the run loses the one
    #  thing it is for.
    REGION_SYNTAX_ERROR         = "region-syntax-error"
    STDERR_UNDECIDED            = "stderr-undecided"

    # THE PYPE STAGE (deterministicalization):
    PYPE_INTERPRETER_NOT_FOUND  = "pype-interpreter-not-found"
    PYPE_FILE_NOT_FOUND         = "pype-file-not-found"
    PYPE_FILE_SYNTAX_ERROR      = "pype-file-syntax-error"
    PYPE_CONTAINED              = "pype-contained"
    PYPE_FAILED                 = "pype-failed"

    # THE BUILD (sandbox_build.py):
    BUILD_TOOL_NOT_FOUND        = "build-tool-not-found"
    BUILD_CONTAINED             = "build-contained"
    BUILD_FAILED                = "build-failed"
    TARGET_NOT_BUILT            = "target-not-built"

    # THE ACQUISITION: a dependency the world outside would not deliver.
    ACQUISITION_FAILED          = "acquisition-failed"

    # THE DISPLAY -- which cannot make a test wrong:
    DISPLAY_TARGET_UNREACHABLE  = "display-target-unreachable"

    def __str__(self):
        """
        RETURN: str, the brief report token (e.g. 'ok',
                     'pype-file-syntax-error', 'target-not-built').
        """
        return self.value
