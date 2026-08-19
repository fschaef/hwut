"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       EQUIVALENCE CHECK -- read, and say whether the test passed.

DESCRIPTION
       The FAST reader: it investigates correctness and nothing else. No
       display, no alignment kept, no explanation -- for those there is
       DifferenceDisplay, which reads the same subjects the same way.

       AN OPERATION IS A CLASS; ITS SUB-PROCESSES ACTIVATE UPON NEED
       (README 2.5). Provision runs because subjects are wanted and are
       not there; comparison runs because a verdict is wanted and
       provision delivered. Nothing branches on WHICH provision it got.

       IT JUDGES; IT DOES NOT PROVIDE. Every reader it compares comes
       from provision, and comparison itself is compare's business. What
       this class owns is the ARRANGEMENT: which subject is held against
       which nominal, in what order, and when to stop.

       A SUBJECT WITH NO NOMINAL IS NOT JUDGED. Absence from the map is
       how a caller says "do not hold this one against anything" -- but a
       nominal that IS named and cannot be read is a FAULT, not a pass.
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   typing      import Mapping, Optional

from   ...compare               import main as compare_main
from   ..result                 import E_TestRunResult
from   ...compare.configuration import Configuration
from   ..nominal                import NominalNotAvailable
from   .terminal                import ends_in_terminal
from   ..observer               import notify
from   ..report                 import (Comparison, TestResult)


@dataclass(frozen=True)
class EquivalenceCheckConfig:
    """What this operation is ASKED for, beside the test's own
    configuration: which groundwork provides, and what each subject is
    held against."""
    name:       str
    groundwork: object                                  # Run | Loaded
    subjects:   Mapping[str, object] = field(default_factory=dict)
    compare:    Optional[Configuration] = None
    fast_fail:  bool = True
    stderr_forbidden_f: bool = False  # the book says FORBIDDEN: a word
                                      # on stderr is an error


class EquivalenceCheck:
    """READ -> VERDICT."""

    def __init__(self, config, observer=None):
        self.config   = config
        self.observer = observer

    async def run(self, stop_event=None):
        """
        RETURN: TestResult, the derived result -- its verdict folded over
                the products, its report the first reason by precedence.

        Provision that failed ends it: 'comparison' stays None, which is
        an ABSENCE and not a half-filled type. A failed build therefore
        yields a FAILED TEST that names the build.
        """
        config = self.config
        notify(self.observer, "started", config.name,
               getattr(config.groundwork, "kind", "?"))

        provided = await config.groundwork.provide(stop_event=stop_event)
        if not provided.provision.delivered:
            result = TestResult(config.name, provided.provision)
            notify(self.observer, "finished", result)
            return result

        comparison = await self._compare(provided)
        result     = TestResult(config.name, provided.provision, comparison)
        notify(self.observer, "finished", result)
        return result

    async def _compare(self, provided):
        """
        RETURN: Comparison, one verdict per NAMED subject.

        Subjects are compared in NAME ORDER, so the first difference a
        run reports is the same one the next run reports -- a fast-fail
        that stopped somewhere else each time would be a nondeterministic
        report of a deterministic fault.
        """
        options   = self.config.compare \
                    if self.config.compare is not None else Configuration()
        verdict_db = {}
        report     = E_TestRunResult.OK

        #  A FORBIDDEN STDERR (the book's note, S-1): a word on that
        #  stream is an ERROR, reported BY NAME -- never a line
        #  difference against a nominal that does not exist.
        if self.config.stderr_forbidden_f and "stderr" in provided:
            with provided["stderr"].open() as reader:
                noise = reader.read()
            if noise.strip():
                verdict_db["stderr"] = False
                report = E_TestRunResult.UNEXPECTED_STDERR
                notify(self.observer, "verdict", "stderr", False)

        for name in sorted(self.config.subjects):
            nominal = self.config.subjects[name]
            if name not in provided:
                verdict_db[name] = False
                if report is E_TestRunResult.OK:
                    report = E_TestRunResult.OUTPUT_FILE_NOT_FOUND
                notify(self.observer, "verdict", name, False)
                if self.config.fast_fail: break
                continue

            try:
                nominal_reader = nominal.open()
            except NominalNotAvailable:
                verdict_db[name] = False
                if report is E_TestRunResult.OK:
                    report = E_TestRunResult.NOMINAL_FILE_NOT_FOUND
                notify(self.observer, "verdict", name, False)
                if self.config.fast_fail: break
                continue

            #  THE TERMINAL TOKEN (R-70): the nominal decides
            #  participation. A participating subject that ends
            #  without '<hwut-end>' is INCOMPLETE -- its own name, not
            #  a wall of line differences ending in one missing line.
            #  Peeked on FRESH readers; the working pair stays
            #  untouched.
            if ends_in_terminal(nominal.open()) \
               and not ends_in_terminal(provided[name].open()):
                verdict_db[name] = False
                if report is E_TestRunResult.OK:
                    report = E_TestRunResult.TERMINATED_WITHOUT_END
                notify(self.observer, "verdict", name, False)
                close = getattr(nominal_reader, "close", None)
                if close is not None: close()
                if self.config.fast_fail: break
                continue

            subject_reader = provided[name].open()
            try:
                ok = await compare_main.is_equivalent(options,
                                                      subject_reader,
                                                      nominal_reader)
            finally:
                for reader in (subject_reader, nominal_reader):
                    close = getattr(reader, "close", None)
                    if close is not None: close()

            verdict_db[name] = bool(ok)
            notify(self.observer, "verdict", name, bool(ok))
            if not ok and self.config.fast_fail: break

        return Comparison(subject_verdict_db=verdict_db, report=report)
