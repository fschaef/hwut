"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE EXECUTE STAGE -- raw behavior comes to exist.

DESCRIPTION
       One stage of provision (see provision/core.py): launch the test
       application supervised, collect the channels, the output files,
       and the cadence when asked for.
______________________________________________________________________________
"""
import asyncio
from pathlib import Path
from   dataclasses import replace

from   ..result                   import E_TestRunResult
from   ...procsitter.api   import Procsitter, E_Containment
from   ...procsitter.api import Link, chain
from   .core                      import (Supply, scratch_dir_of,
                                          STDOUT, STDERR,
                                          application_argv,
                                          read_all,
                                          read_all_timed)
from   .provider                  import I_ExecuteProvider
from   ..configuration            import caps_of
from   .containment               import token_of, detail_of


class StageExecute(I_ExecuteProvider):
    """RAW BEHAVIOR comes to exist: launch, contain, collect -- the
    channels, the output files, and the cadence when asked for.

    Reads the source, place and caps keys of the configuration.
    """

    def __init__(self, configuration, choice_name=None, keep_timing=False):
        self.configuration = configuration
        self.choice_name   = choice_name
        self.keep_timing   = keep_timing

    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = (raw_db, timing_db): the raw texts by
                subject name, and the cadence (empty unless asked for).
                Product None when the launch failed -- there is nothing
                to canonicalise and nothing to deliver. A STALLED or
                CONTAINED run DELIVERS: its partial streams are real
                behavior, and the token speaks beside them.
        """
        configuration = self.configuration
        #  THE TERMINAL TOKEN (R-70, t-6): where a pype owns this
        #  choice's stdout, the APPLICATION must not emit '<hwut-end>'
        #  -- the framework says so through the environment, and the
        #  reference runner listens.
        choice = configuration.choice_db.get(self.choice_name)
        pype_owned_f = (choice is not None
                        and "stdout" in choice.canonicalisers)
        #  THE CASE'S CAPS, not the application's (O-20): a choice may
        #  state its own, and this stage knows which choice it is.
        caps = caps_of(configuration, self.choice_name)
        if pype_owned_f:
            caps = replace(caps, env={**(caps.env or {}),
                                      "HWUT_NO_TERMINAL": "1"})
        caps = replace(caps, scratch_dir=scratch_dir_of(configuration,
                                                         self.choice_name))
        #  THE ERROR WITNESS IS CLEARED BEFORE THE RUN, never after:
        #  what stands in 'OUT/' when this returns is THIS run's.
        self._clear_error_witness()
        procsitter = Procsitter(caps,
                                work_dir=str(configuration.test_directory))
        error_link = Link()
        c = chain([(procsitter,
                    application_argv(configuration, self.choice_name),
                    {"stderr_handler": error_link.feed})])
        #  The cadence is measured AT ARRIVAL, or not at all: a dict
        #  where this provider measured, None where it did not --
        #  absence is data, never an empty measurement.
        timing_db = {} if self.keep_timing else None
        try:
            if self.keep_timing:
                stdout_text, delta_tuple = await read_all_timed(c.tail.reader)
                timing_db[STDOUT] = delta_tuple
            else:
                stdout_text = await read_all(c.tail.reader)
            record = (await asyncio.gather(*c.task_tuple))[0]
        finally:
            error_link.close()                 # not an edge: ours to close
        stderr_text = await read_all(error_link.reader)
        record_list = (record,)

        if record.containment is E_Containment.FAIL_LAUNCH:
            return Supply(product     = None,
                          report      = E_TestRunResult
                                        .TEST_APP_LAUNCH_FAILED,
                          record_list = record_list)

        raw_db = {STDOUT: stdout_text, STDERR: stderr_text}
        self._witness_error(stderr_text)
        missing_report = self._output_files(raw_db)

        report    = E_TestRunResult.OK
        if record.containment is E_Containment.FAIL_STALLED:
            report = E_TestRunResult.TEST_APP_STALLED
        elif record.containment is not E_Containment.OK_COMPLETED \
             and record.containment is not E_Containment.FAIL_COMPLETED:
            #  A KILL NAMES ITS CAP (O-19): the token says which, the
            #  detail says the cap and the peak.
            report      = token_of(record.containment)
            self.detail = detail_of(record, caps)
        elif missing_report is not None:
            #  Containment speaks first: a contained run explains a
            #  missing file better than the file's absence does.
            report = missing_report

        return Supply(product     = (raw_db, timing_db),
                      report      = report,
                      record_list = record_list,
                      detail      = getattr(self, "detail", None))

    def _error_witness_path(self):
        """
        RETURN: Path, 'OUT/<key>--<choice>.err' -- where the last run's
                stderr stands, if it stood at all.
        """
        from ...bookkeeper.api import error_witness_name
        configuration = self.configuration
        return configuration.output_directory \
               / error_witness_name(configuration.key_name, self.choice_name)

    def _clear_error_witness(self):
        """
        RETURN: None. Removes the standing '.err' BEFORE the run, so
                that what is found afterwards is THIS run's and never
                the one before it.

        Cleared on every execution and written only on occurrence, so
        the presence of the file IS the statement that this run wrote
        to stderr. 'OUT/' witnesses the LAST RUN; a '.err' left from an
        earlier one would witness the wrong one.
        """
        try:    self._error_witness_path().unlink()
        except OSError: pass

    def _witness_error(self, stderr_text):
        """
        RETURN: None. Writes 'OUT/<key>.err' where the run wrote to
                stderr, and nothing where it did not.

        NEVER A SUBJECT (E-5): not compared, not a nominal, not
        pype-d, and not named in 'output'. It is what a reader of a
        failed run asks for first, kept where the rest of the run's
        product is kept.
        """
        if not stderr_text: return
        path = self._error_witness_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stderr_text, encoding="utf-8")
        except OSError:
            pass                        # a witness that cannot be kept
                                        # is not a verdict about the run

    def _output_files(self, raw_db):
        """
        RETURN: E_TestRunResult.OUTPUT_FILE_NOT_FOUND where a declared
                file subject is absent; None else. The single-run
                road's door to 'read_declared_files'.
        """
        return read_declared_files(self.configuration, self.choice_name,
                                   raw_db)


def read_declared_files(configuration, choice_name, raw_db):
    """
    RETURN: E_TestRunResult.OUTPUT_FILE_NOT_FOUND where a DECLARED
            file subject is absent after the run; None where every
            declared file was read into 'raw_db'.

    ONE implementation, every road: the single run reads after the
    process ended; the SESSION reads after the CHOICE'S token/'done'
    (todo-1-judgement-timing) -- the process does not end between
    choices, and a file develops with REVISIONS, so only its state
    at the token is the subject.

    SUBJECTS ARE DECLARED, NEVER DISCOVERED ('output', R-71): the
    choice's 'output' names them; a name that is not 'stdout' is a
    FILE in the test directory. A declared file the run did not leave
    is a verdict, not a silence: discovery could never tell
    'produced' from 'forgot'.

    READ AND REMOVED -- the transport leaves no residue (the sink law
    of multi_execute._read_sinks), PER CHOICE on the session road:
    choice B must never read choice A's leftover; a lingering file
    would be explored as a candidate test application by the next
    walk; and a STALE file from run N would green run N+1 even where
    the application stopped producing it.
    """
    choice = configuration.choice_db.get(choice_name)
    output = getattr(choice, "output", None) if choice else None
    if output is None: return None
    directory = Path(configuration.test_directory)
    missing_f = False
    for name in output:
        if name == STDOUT: continue
        path = directory / name
        try:
            raw_db[name] = path.read_text(encoding="utf-8",
                                          errors="replace")
        except OSError:
            missing_f = True
            continue
        try:
            path.unlink()
        except OSError:
            pass
    if missing_f: return E_TestRunResult.OUTPUT_FILE_NOT_FOUND
    return None
