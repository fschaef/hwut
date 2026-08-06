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

from   vut.engine.test_run.result          import E_TestRunResult
from   vut.engine.procsitter.procsitter     import Procsitter, E_Containment
from   vut.engine.procsitter.construction   import Link, chain
from   vut.engine.test_run.provision.core   import (Supply,
                                                    STDOUT, STDERR,
                                                    application_argv,
                                                    read_all,
                                                    read_all_timed)


class StageExecute:
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
        procsitter = Procsitter(configuration.caps,
                                work_dir=str(configuration.test_directory))
        error_link = Link()
        c = chain([(procsitter,
                    application_argv(configuration, self.choice_name),
                    {"stderr_handler": error_link.feed})])
        timing_db = {}
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
        raw_db.update(self._output_files())

        report    = E_TestRunResult.OK
        if record.containment is E_Containment.FAIL_STALLED:
            report = E_TestRunResult.TEST_APP_STALLED
        elif record.containment is not E_Containment.OK_COMPLETED \
             and record.containment is not E_Containment.FAIL_COMPLETED:
            report = E_TestRunResult.TEST_APP_CONTAINED

        return Supply(product     = (raw_db, timing_db),
                      report      = report,
                      record_list = record_list)

    def _output_files(self):
        """
        RETURN: dict, subject name -> text, for every file the run left
                under 'OUT/'. A file subject is named by its file name.
        """
        directory = self.configuration.output_directory
        file_db   = {}
        if not directory.is_dir(): return file_db
        for path in sorted(directory.iterdir()):
            if not path.is_file(): continue
            try:
                file_db[path.name] = path.read_text(encoding="utf-8",
                                                    errors="replace")
            except OSError:
                pass
        return file_db
