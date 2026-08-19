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

    # THE JUDGEMENT: everything ran; the subject does not match.
    NOT_EQUIVALENT_WITH_NOMINAL = "not-equivalent-with-nominal"

    # THE TEST APPLICATION:
    TEST_APP_LAUNCH_FAILED      = "test-app-launch-failed"
    TEST_APP_CONTAINED          = "test-app-contained"
    TEST_APP_NO_OUTPUT          = "test-app-no-output"
    TEST_APP_STALLED            = "test-app-stalled"

    # REPLAY: no usable recording to provision from.
    RECORDING_MISSING           = "recording-missing"

    # THE SUBJECTS AND NOMINALS:
    OUTPUT_FILE_NOT_FOUND       = "output-file-not-found"
    NOMINAL_FILE_NOT_FOUND      = "nominal-file-not-found"
    TERMINATED_WITHOUT_END      = "terminated-without-hwut-end"
    UNEXPECTED_STDERR           = "unexpected-stderr"
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
