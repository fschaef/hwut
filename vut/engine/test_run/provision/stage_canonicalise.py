"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE CANONICALISE STAGE -- the subject comes to exist.

DESCRIPTION
       One stage of provision (see provision/core.py): each raw stream
       rewritten by its declared pype, comparable after. A stream with
       no canonicaliser declared is comparable raw -- raw IS canonical
       for it.
______________________________________________________________________________
"""
import asyncio

from   vut.engine.test_run.result          import E_TestRunResult
from   vut.engine.procsitter.procsitter     import Procsitter, E_Containment
from   vut.engine.procsitter.construction   import Link, chain
from   vut.engine.test_run.nominal          import BytesNominal
from   vut.engine.test_run.provision.core   import Supply, read_all


async def canonicalise(text, pype_argv, procsitter):
    """
    RETURN: (str, E_TestRunResult), the canonicalised text and the report.

    The canonicaliser is a supervised call like any other: its own caps,
    its own attribution. A canonicaliser that fails leaves the text
    UNCHANGED and says so -- it never silently returns half a stream,
    which would be compared and called a difference in the subject.
    """
    source = Link()
    await source.feed(text.encode("utf-8"))
    source.close()

    c      = chain([(procsitter, list(pype_argv))],
                   stdin_reader=source.reader)
    record = (await asyncio.gather(*c.task_tuple))[0]
    result = await read_all(c.tail.reader)

    if record.containment is E_Containment.FAIL_LAUNCH:
        return text, E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND
    if record.containment is E_Containment.FAIL_COMPLETED:
        return text, E_TestRunResult.PYPE_FAILED
    if record.containment is not E_Containment.OK_COMPLETED:
        return text, E_TestRunResult.PYPE_CONTAINED
    return result, E_TestRunResult.OK


class StageCanonicalise:
    """THE SUBJECT comes to exist: each raw stream rewritten by its
    declared pype, comparable after. A stream with no canonicaliser
    declared is comparable raw -- raw IS canonical for it.

    Reads the canonicaliser and caps keys of the configuration.
    """

    def __init__(self, configuration, choice_name=None):
        self.configuration = configuration
        self.choice_name   = choice_name

    async def supply(self, raw_db, stop_event=None):
        """
        RETURN: Supply, product = readers by subject name; report = the
                FIRST canonicaliser failure, or OK. This stage answers
                for ITSELF only -- which reason speaks among the
                stages' is the orchestrator's merge, not a stage's
                knowledge of its upstream.

        A failing canonicaliser leaves its text UNCHANGED and says so
        ('canonicalise'); the subject is delivered either way.
        """
        configuration = self.configuration
        procsitter = Procsitter(configuration.caps,
                                work_dir=str(configuration.test_directory))
        reader_db = {}
        report    = E_TestRunResult.OK
        entry     = configuration.choice_configuration(self.choice_name)
        for name, text in raw_db.items():
            pype_argv = entry.canonicalisers.get(name)
            if pype_argv is not None:
                text, pype_report = await canonicalise(text, pype_argv,
                                                       procsitter)
                if pype_report is not E_TestRunResult.OK \
                   and report is E_TestRunResult.OK:
                    report = pype_report
            reader_db[name] = BytesNominal(text, name=name)
        return Supply(product=reader_db, report=report)
