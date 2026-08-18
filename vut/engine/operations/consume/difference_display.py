"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       DIFFERENCE DISPLAY -- read, and SHOW what differs.

DESCRIPTION
       The second reader. It provides subjects exactly as EquivalenceCheck
       does, and then does the other thing with them: instead of reducing
       the comparison to a verdict it carries the whole ALIGNMENT out to a
       target.

       IT SHOWS EVERY NAMED SUBJECT. There is no fast-fail here: a person
       looking at a difference wants all of it, and stopping at the first
       would hide the rest of what changed.

       A DISPLAY CANNOT MAKE A TEST WRONG. The verdict is derived from the
       comparison exactly as it is for the fast reader; an unreachable
       target is reported as its own reason, which the precedence table
       ranks below every real fault.
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   typing      import Mapping, Optional

from   ..result                 import E_TestRunResult
from   ...compare.configuration import Configuration
from   ..interaction.feed       import (NullDisplay, feed_down,
                                        ProtocolMismatch)
from   ..nominal                import NominalNotAvailable
from   ..observer               import notify
from   ..report                 import Comparison, TestResult

from   ...compare               import main as compare_main


@dataclass(frozen=True)
class DifferenceDisplayConfig:
    """What this operation is ASKED for: which groundwork provides, what
    each subject is held against, and where to show it."""
    name:       str
    groundwork: object
    subjects:   Mapping[str, object]    = field(default_factory=dict)
    compare:    Optional[Configuration] = None
    adapter:    Optional[object]        = None
    only_differing: bool = True


class DifferenceDisplay:
    """READ -> FEED THE ALIGNED COMPARISON."""

    def __init__(self, config, observer=None):
        self.config   = config
        self.observer = observer

    async def run(self, stop_event=None):
        """
        RETURN: TestResult, derived exactly as the fast reader derives it.

        The display is a SIDE EFFECT of the same reading; it does not
        change what the comparison found.
        """
        config = self.config
        notify(self.observer, "started", config.name,
               getattr(config.groundwork, "kind", "?"))

        provided = await config.groundwork.provide(stop_event=stop_event)
        if not provided.provision.delivered:
            result = TestResult(config.name, provided.provision)
            notify(self.observer, "finished", result)
            return result

        comparison = await self._compare_and_show(provided)
        result     = TestResult(config.name, provided.provision, comparison)
        notify(self.observer, "finished", result)
        return result

    async def _compare_and_show(self, provided):
        """
        RETURN: Comparison, one verdict per named subject -- EVERY one of
                them, since a person wants all of what differs.
        """
        config     = self.config
        options    = config.compare if config.compare is not None \
                                    else Configuration()
        adapter    = config.adapter if config.adapter is not None \
                                    else NullDisplay()
        verdict_db = {}
        report     = E_TestRunResult.OK

        for name in sorted(config.subjects):
            outcome, reason = await self._one(name, provided, options,
                                              adapter)
            verdict_db[name] = outcome
            notify(self.observer, "verdict", name, outcome)
            if reason is not E_TestRunResult.OK and report is E_TestRunResult.OK:
                report = reason

        return Comparison(subject_verdict_db=verdict_db, report=report)

    async def _one(self, name, provided, options, adapter):
        """
        RETURN: (bool, E_TestRunResult), one subject's verdict and the
                reason if something beside a mismatch went wrong.

        The subject is read TWICE -- once to judge, once to show -- and
        both readings come from the same provided reader, which is
        re-openable precisely so that showing cannot consume what judging
        needs.
        """
        if name not in provided:
            return False, E_TestRunResult.OUTPUT_FILE_NOT_FOUND
        try:
            nominal_reader = self.config.subjects[name].open()
        except NominalNotAvailable:
            return False, E_TestRunResult.NOMINAL_FILE_NOT_FOUND

        subject_reader = provided[name].open()
        try:
            ok = bool(await compare_main.is_equivalent(options,
                                                       subject_reader,
                                                       nominal_reader))
        finally:
            for reader in (subject_reader, nominal_reader):
                close = getattr(reader, "close", None)
                if close is not None: close()

        if ok and self.config.only_differing:
            return True, E_TestRunResult.OK

        try:
            await feed_down(options,
                            provided[name].open(),
                            self.config.subjects[name].open(),
                            adapter, name)
        except ProtocolMismatch:
            return ok, E_TestRunResult.DISPLAY_TARGET_UNREACHABLE
        except NominalNotAvailable:
            return False, E_TestRunResult.NOMINAL_FILE_NOT_FOUND
        return ok, E_TestRunResult.OK
