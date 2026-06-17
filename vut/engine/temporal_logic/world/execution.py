"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RUNNER  --  the world's EXECUTION contract.

The third of the world's three outward faces (span, emission, EXECUTION). A
Runner takes a generated program and runs it over a trace, returning the
program's output for HWUT comparison. For the Luau world this wraps the 'luau'
interpreter as a subprocess; another world wraps its own runtime.

STATUS: CONTRACT ONLY, and THIN. Execution today is a bare subprocess call
living in the test harness, not yet a component method. This file forward-
declares the face so the world's interface is whole and the multi-target design
is visible; the contract is expected to GROW when a second world arrives and
the run/trace/output shape must be made language-neutral in earnest. One
implementation (the Luau runner, unbuilt -- todo-4) does not yet exercise it.
______________________________________________________________________________
"""
from abc import ABC, abstractmethod


class ExecutionError(Exception):
    """INFRASTRUCTURE failure while running a generated program.

    Raised when the runtime cannot run the program for a reason outside the
    rule file (interpreter missing, runtime crash, timeout). Distinct from a
    REPORT mismatch, which is HWUT's concern, not the runner's: the runner
    returns output; judging it is the harness's job.
    """
    pass


class Runner(ABC):
    """Abstract boundary the harness uses to run a generated program.

    A concrete runner executes the emitted program over a trace and returns its
    output. Keeping this abstract is what lets a second world run its target on
    its own runtime with no change above the world. The counterpart of the
    Emitter: emission produces the program, execution runs it.
    """

    @abstractmethod
    def run(self, program_text, trace):
        """RETURN: str, the program's stdout over the given trace.

        Raises ExecutionError on infrastructure failure.

        'program_text' is the emitted program (an Emitter.emit result); 'trace'
        is the input time line the program processes. The returned text is the
        REPORT block the harness compares against a nominal recording; the
        runner judges nothing.
        """
        raise NotImplementedError
