"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR 'coverage' (coverage.py) -- python.

DESCRIPTION
       THREE CALLS, AS THE ROLE ASKS.

           wrap          'coverage run --data-file=<artifact>/.coverage
                          [--include] [--omit] -- <argv>'
           report_argv   'coverage json --data-file=... -o <artifact>/
                          coverage.json'  -- the SECOND supervised call:
                          what the run leaves is a DATABASE, and turning
                          it into text is a process like any other
           harvest       that json -> the homogeneous record

       WHY THE JSON AND NOT THE LCOV. coverage.py can emit both, and the
       json says exactly what this format wants:

           executed_lines   the lines that RAN            -> CV
           missing_lines    executable, never reached
           excluded_lines   not executable at all

       so EX is 'executed + missing' and CV is 'executed', with no
       inference. The lcov form would say the same thing through 'DA'
       lines with counts of zero -- and coverage.py's counts are always
       0 or 1, so nothing is gained and one conversion is added. (The
       lcov reader exists anyway, for the tools that ONLY speak it.)

       NO HIT COUNTS. coverage.py records line HITS, not their number,
       unless contexts are switched on -- so this reader never claims
       counts, and the header says 'counts: no'. Claiming a count of 1
       for every covered line would be a fabricated measurement.

       THE GATHER SET goes to the tool ('--include' / '--omit'): it is a
       gathering knob, and the cheapest place to gather less is the
       gatherer.

       PATHS. coverage.py reports paths relative to the directory it ran
       in, which is the TEST DIRECTORY -- so they are already in the one
       form a record holds. They are relativised again anyway: a
       configuration that made them absolute must not reach the record.
______________________________________________________________________________
"""
import io
import json
import os

from ..reader import (CCoverageFramework, CCoverageFormat,
                      register, artifact_directory_of,
                      relative_path, wanted, record_of)


DATA_FILE = ".coverage"
JSON_FILE = "coverage.json"


def _data_path(work_dir):
    """RETURN: str, where the run leaves its database."""
    return os.path.join(artifact_directory_of(work_dir), DATA_FILE)


def _json_path(work_dir):
    """RETURN: str, where the second call leaves the report."""
    return os.path.join(artifact_directory_of(work_dir), JSON_FILE)


class PythonCoverageFormat(CCoverageFormat):
    """coverage.py's json report."""
    name = "coverage.py-json"

    def read(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of the json report.
                None, where no report stands -- ABSENT, which is not an
                empty measurement and must not be reported as one.
        """
        path = _json_path(work_dir)
        if not os.path.isfile(path): return None
        with io.open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        return record_of(self, "python",
                         _entry_iterable(document, source_root, config))


def _entry_iterable(document, source_root, config):
    """
    YIELD: (path, executable_lines, covered_lines, None) per source
           file inside the gather set.

    EX is 'executed + missing': what COULD be hit. 'excluded_lines'
    are not executable and enter neither.
    """
    for raw_path, entry in sorted(document.get("files", {}).items()):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        executed = entry.get("executed_lines", [])
        missing  = entry.get("missing_lines", [])
        yield path, list(executed) + list(missing), executed, None


class PythonCoverageFramework(CCoverageFramework):
    """coverage.py: 'coverage run' around the call, 'coverage json'
    after it; reads PythonCoverageFormat."""
    name   = "coverage"
    format = PythonCoverageFormat()

    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], 'argv' run under 'coverage run'.

        '--' separates the tool's words from the application's, so an
        application flag that coverage.py also knows ('--include', say)
        stays the application's.
        """
        head = ["coverage", "run", "--data-file=%s" % _data_path(work_dir)]
        if config is not None:
            if config.include:
                head.append("--include=%s" % ",".join(config.include))
            if config.omit:
                head.append("--omit=%s" % ",".join(config.omit))
        return head + ["--"] + list(argv)

    def report_argv(self, config, work_dir):
        """
        RETURN: list[str], 'coverage json' -- the second supervised call.
                What the run left is a database; this makes it readable.
        """
        return ["coverage", "json",
                "--data-file=%s" % _data_path(work_dir),
                "-o", _json_path(work_dir), "-q"]


register(PythonCoverageFramework())
