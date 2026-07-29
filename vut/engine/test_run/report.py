"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE PRODUCTS of a test, and the ONE result derived from them.

DESCRIPTION
       Each sub-process returns its OWN product; none is merged into
       another (README 8):

           Provision    what was provided -- attribution records, and
                        whether provision succeeded
           Comparison   what was compared -- per subject verdicts.
                        ABSENT when provision never delivered.

       So "no comparison happened" is an ABSENCE, not a null field in a
       half-filled type, and a field's origin is readable from its type
       rather than by convention.

       'TestResult' is neither: it is DERIVED. The verdict is folded over
       whatever products exist, and the report is the FIRST reason by
       PRECEDENCE -- source and build reasons outrank run reasons, and
       run reasons outrank subject and nominal reasons.

       A FAILED BUILD IS A FAILED TEST. Not "the test could not run":
       failing to build is a shortcoming of the code under test, so the
       verdict is false and the report names the build. The comparison is
       absent, and the test still has its result.
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   typing      import Mapping, Optional, Sequence

from   vut.auxiliary.test_run_result import E_TestRunResult


#  Reason precedence: the earlier a reason stands, the louder it speaks.
#  A run that failed to build says so; it does not report that its output
#  file was missing, though that is also true.
_PRECEDENCE = (
    # -- the source and the build: nothing could even be attempted
    E_TestRunResult.SOURCE_NOT_FOUND,
    E_TestRunResult.INTERPRETER_NOT_FOUND,
    E_TestRunResult.BUILD_TOOL_NOT_FOUND,
    E_TestRunResult.BUILD_CONTAINED,
    E_TestRunResult.BUILD_FAILED,
    E_TestRunResult.TARGET_NOT_BUILT,
    # -- the run itself
    E_TestRunResult.TEST_APP_LAUNCH_FAILED,
    E_TestRunResult.TEST_APP_CONTAINED,
    E_TestRunResult.TEST_APP_STALLED,
    E_TestRunResult.TEST_APP_NO_OUTPUT,
    E_TestRunResult.RECORDING_MISSING,
    # -- the canonicaliser
    E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND,
    E_TestRunResult.PYPE_FILE_NOT_FOUND,
    E_TestRunResult.PYPE_FILE_SYNTAX_ERROR,
    E_TestRunResult.PYPE_CONTAINED,
    E_TestRunResult.PYPE_FAILED,
    # -- the subjects and nominals
    E_TestRunResult.OUTPUT_FILE_NOT_FOUND,
    E_TestRunResult.NOMINAL_FILE_NOT_FOUND,
    # -- the judgement: everything ran, the subject does not match
    E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL,
    # -- the display, which cannot make a test wrong
    E_TestRunResult.DISPLAY_TARGET_UNREACHABLE,
)

_RANK = {reason: i for i, reason in enumerate(_PRECEDENCE)}


def first_by_precedence(reason_list):
    """
    RETURN: E_TestRunResult, the reason that SPEAKS -- the first by
            precedence among those given.
            E_TestRunResult.OK, when none of them is a failure.

    Raises KeyError on a reason absent from the precedence table: a new
    token must be PLACED, never silently ranked last.
    """
    failure_list = [r for r in reason_list
                    if r is not None and r is not E_TestRunResult.OK]
    if not failure_list: return E_TestRunResult.OK
    return min(failure_list, key=lambda r: _RANK[r])


@dataclass(frozen=True)
class Provision:
    """WHAT WAS PROVIDED. One per attempt, always."""
    report:  E_TestRunResult      = E_TestRunResult.OK
    records: Sequence[object]     = field(default_factory=tuple)
    #  'records' is empty when provision was by stored data: nothing ran,
    #  so nothing was contained, and there is no attribution to make.

    @property
    def delivered(self):
        """
        RETURN: True,  subjects exist and a comparison may proceed.
                False, provision failed; there is nothing to compare.
        """
        return self.report is E_TestRunResult.OK


@dataclass(frozen=True)
class Comparison:
    """WHAT WAS COMPARED. Absent altogether when provision failed."""
    subject_verdict_db: Mapping[str, bool] = field(default_factory=dict)
    report:             E_TestRunResult    = E_TestRunResult.OK

    @property
    def verdict(self):
        """
        RETURN: True,  every compared subject matched its nominal.
                False, at least one did not, or comparison itself failed.

        An EMPTY comparison is False: nothing was held against anything,
        and reporting that as success would be a green light nobody
        earned.
        """
        if self.report is not E_TestRunResult.OK:     return False
        if not self.subject_verdict_db:               return False
        return all(self.subject_verdict_db.values())


@dataclass(frozen=True)
class TestResult:
    """THE TEST'S RESULT -- derived, never returned by a sub-process."""
    name:       str
    provision:  Provision
    comparison: Optional[Comparison] = None

    @property
    def verdict(self):
        """
        RETURN: True,  the test passed.
                False, it did not -- including when it never got as far
                       as comparing.
        """
        if not self.provision.delivered:  return False
        if self.comparison is None:       return False
        return self.comparison.verdict

    @property
    def report(self):
        """
        RETURN: E_TestRunResult, the ONE reason that speaks: the first by
                precedence among the products' reasons; OK when the test
                passed; NOT_EQUIVALENT_WITH_NOMINAL when everything ran
                and a subject simply did not match.
        """
        reason_list = [self.provision.report]
        if self.comparison is not None:
            reason_list.append(self.comparison.report)
        reason = first_by_precedence(reason_list)
        if reason is not E_TestRunResult.OK:  return reason
        if self.verdict:                      return E_TestRunResult.OK
        return E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL

    def footprint_facts(self):
        """
        RETURN: dict, what a footprint records of this result -- the
                verdict and the report token. 'when' and 'host' are the
                store's to add.
        """
        return {"verdict": self.verdict, "report": str(self.report)}
