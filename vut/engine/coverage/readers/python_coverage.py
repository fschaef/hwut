"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR 'coverage' (coverage.py) -- python.

DESCRIPTION
       THREE CALLS, AS THE ROLE ASKS.

           specify_command_line
                         'coverage run --branch --data-file=<artifact>/
                          .coverage [--include=] [--omit=] -- <script>
                          [<choice>]'
                         -- the tool runs the SCRIPT; no interpreter
                         stands before it (D-39)
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

       THE BRANCHES (RATIONALE D-43). The run is made with '--branch', and
       the json then carries, per file, the ARCS of the decisions:

           executed_branches   [[3, 4]]               arcs a run took
           missing_branches    [[3, 5], [5, 6]]       arcs it did not

       An arc is (the decision's line, the line it leads to; a negative
       number is the exit of a scope). The arms of a decision are the
       destinations of the arcs leaving its line, EXECUTED AND MISSING
       TOGETHER, in ascending order -- a set that is the same whichever
       arm a run took (MEASURED on coverage.py 7.16) -- and bit i of the
       'branch' mask is arm i. A json without the keys, from a tool run
       without '--branch', yields no branch point: absence stays
       absent.

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

from .reader import (CCoverageFramework, CCoverageFormat,
                      register, artifact_directory_of, ARTIFACT_DIRECTORY,
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
        yield path, list(executed) + list(missing), executed, None, \
              {"branch": _branch_point_tuple(entry)}


def _branch_point_tuple(entry):
    """
    RETURN: tuple of (line, mask, total), one per decision line the json
            entry names arcs for, in line order; the arms of a line in
            ascending order of their destination, bit i set where arm i
            was taken. Empty where the entry carries no arcs.
    """
    taken_set = {(begin, end) for begin, end
                 in entry.get("executed_branches", [])}
    arm_db = {}
    for begin, end in list(entry.get("executed_branches", [])) \
                      + list(entry.get("missing_branches", [])):
        arm_db.setdefault(begin, set()).add(end)
    return tuple(
        (line,
         sum(1 << i for i, end in enumerate(sorted(arm_db[line]))
             if (line, end) in taken_set),
         len(arm_db[line]))
        for line in sorted(arm_db))


class PythonCoverageFramework(CCoverageFramework):
    """coverage.py: 'coverage run' runs the test application, 'coverage
    json' after it; reads PythonCoverageFormat."""
    name   = "coverage"
    format = PythonCoverageFormat()

    #  THE TOOL RUNS THE SCRIPT ITSELF: 'coverage run' takes a program
    #  file, not a command, so no interpreter stands before '{test}'.
    #  '--' separates the tool's words from the application's, so an
    #  application flag that coverage.py also knows stays the
    #  application's. The data file is relative: the call's working
    #  directory is the test directory.
    call_scheme = ("coverage run --branch --data-file=%s/%s "
                   "--include={include} --omit={omit} -- {test} {choice}"
                   % (ARTIFACT_DIRECTORY, DATA_FILE))

    def report_argv(self, config, work_dir):
        """
        RETURN: list[str], 'coverage json' -- the second supervised call.
                What the run left is a database; this makes it readable.
        """
        return ["coverage", "json",
                "--data-file=%s" % _data_path(work_dir),
                "-o", _json_path(work_dir), "-q"]


register(PythonCoverageFramework())
