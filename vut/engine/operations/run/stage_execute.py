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


#  Which cap a containment names (O-19).
_CONTAINMENT_TOKEN_DB = {
    E_Containment.FAIL_WALL_CLOCK_EXCEEDED: E_TestRunResult.TEST_APP_WALL_CLOCK_EXCEEDED,
    E_Containment.FAIL_CPU_TIME_EXCEEDED:   E_TestRunResult.TEST_APP_CPU_TIME_EXCEEDED,
    E_Containment.FAIL_MEMORY_EXCEEDED:     E_TestRunResult.TEST_APP_MEMORY_EXCEEDED,
    E_Containment.FAIL_FILE_SIZE_EXCEEDED:  E_TestRunResult.TEST_APP_FILE_SIZE_EXCEEDED,
    E_Containment.FAIL_PIDS_EXCEEDED:       E_TestRunResult.TEST_APP_PIDS_EXCEEDED,
    E_Containment.FAIL_DISK_USAGE_EXCEEDED: E_TestRunResult.TEST_APP_DISK_EXCEEDED,
}


def _detail_of(record, caps):
    """
    RETURN: str, the cap that was hit and how far the run went past it,
                 e.g. 'cap 512 MB, peak 1069 MB' -- from the record's
                 peaks and the caps in force
            None, where the containment names no cap this can measure.

    A PEAK IS WHAT THIS MACHINE SAW (E-36): the detail is spoken, in
    HINTS and the log, and never written to the book.
    """
    c = record.containment
    if c is E_Containment.FAIL_MEMORY_EXCEEDED:
        peak = record.peak_memory_mb
        return "cap %s MB, peak %s MB" % (caps.max_memory_mb,
                                          "?" if peak is None else "%.0f" % peak)
    if c is E_Containment.FAIL_WALL_CLOCK_EXCEEDED:
        return "cap %s s, ran %.1f s" % (caps.max_wall_clock_sec,
                                          record.wall_clock_sec)
    if c is E_Containment.FAIL_CPU_TIME_EXCEEDED:
        used = record.cpu_time_sec
        return "cap %s s cpu, used %s s" % (caps.max_cpu_time_sec,
                                            "?" if used is None else "%.1f" % used)
    if c is E_Containment.FAIL_FILE_SIZE_EXCEEDED:
        return "cap %s MB per file" % caps.max_file_size_mb
    if c is E_Containment.FAIL_PIDS_EXCEEDED:
        return "cap %s, peak %s" % (caps.max_pids,
                                   "?" if record.peak_pids is None else record.peak_pids)
    if c is E_Containment.FAIL_DISK_USAGE_EXCEEDED:
        peak = record.peak_disk_mb
        return "cap %s MB, peak %s MB" % (caps.max_disk_mb,
                                          "?" if peak is None else "%.0f" % peak)
    return None


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
        caps = configuration.caps
        if pype_owned_f:
            caps = replace(caps, env={**(caps.env or {}),
                                      "HWUT_NO_TERMINAL": "1"})
        caps = replace(caps, scratch_dir=scratch_dir_of(configuration,
                                                         self.choice_name))
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
        missing_report = self._output_files(raw_db)

        report    = E_TestRunResult.OK
        if record.containment is E_Containment.FAIL_STALLED:
            report = E_TestRunResult.TEST_APP_STALLED
        elif record.containment is not E_Containment.OK_COMPLETED \
             and record.containment is not E_Containment.FAIL_COMPLETED:
            #  A KILL NAMES ITS CAP (O-19): the token says which, the
            #  detail says the cap and the peak.
            report = _CONTAINMENT_TOKEN_DB.get(record.containment,
                                               E_TestRunResult.TEST_APP_CONTAINED)
            self.detail = _detail_of(record, caps)
        elif missing_report is not None:
            #  Containment speaks first: a contained run explains a
            #  missing file better than the file's absence does.
            report = missing_report

        return Supply(product     = (raw_db, timing_db),
                      report      = report,
                      record_list = record_list,
                      detail      = getattr(self, "detail", None))

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
