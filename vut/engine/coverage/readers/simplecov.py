"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR SIMPLECOV'S RESULTSET -- ruby's own record of a
         run.

DESCRIPTION
       WHAT IS READ, witnessed (WITNESS-hdl-artifacts.txt session,
       simplecov + simplecov-cobertura vendored): 'coverage/
       .resultset.json' --

           { "<suite>": {
               "coverage": { "<abs path>": { "lines":
                   [null, 1, 3, 0, null, ...] } },
               "timestamp": ... } }

       THE ARRAY IS THE FILE: index i speaks of line i+1. 'null' is NOT
       EXECUTABLE; an integer is a hit count -- EX where an integer
       stands, CV where it is above zero, no inference. Older simplecov
       wrote the array directly, without the '"lines"' wrapper; both
       shapes are read, because both are simplecov's own.

       SUITES UNION. A resultset holds one entry per test suite; a file
       named by two suites has its counts ADDED, which is what two runs
       of one file mean. 'null' yields to an integer: a line one suite
       could not see executed is not thereby non-executable.

       THE PATH IS ABSOLUTE -- simplecov names the machine it ran on --
       and is made relative against the source root, after which no
       record names it.

       WHY SECOND ON THE ROAD: the registry road for ruby says cobertura
       first ('simplecov-cobertura'), which the shared reader serves.
       This reader is for the resultset that is ALREADY THERE when no
       formatter was configured -- simplecov writes it unconditionally.

       A JSON WITHOUT THE SHAPE IS LEFT ALONE.
______________________________________________________________________________
"""
import io
import json
import os

from ..reader import (CCoverageFramework, CCoverageFormat,
                      register, artifact_directory_of,
                      relative_path, wanted)
from ..record import ranges_of, FileCoverage, CoverageRecord


RESULTSET_SUFFIX = (".resultset.json",)


class SimplecovFormat(CCoverageFormat):
    """SimpleCov's .resultset.json."""
    name = "simplecov-resultset"

    def read(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of every resultset under the artifact
                directory, suites and files unioned.
                None, where none stands -- ABSENT.
        """
        line_db_by_file = {}
        directory = artifact_directory_of(work_dir)
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if not name.endswith(RESULTSET_SUFFIX): continue
                _absorb(line_db_by_file, os.path.join(directory, name))
        if not line_db_by_file: return None

        counts_f = bool(config is not None and config.counts)
        file_db  = {}
        for raw_path in sorted(line_db_by_file):
            path = relative_path(raw_path, source_root)
            if not wanted(path, config): continue
            line_db    = line_db_by_file[raw_path]
            executable = sorted(line_db)
            covered    = [n for n in executable if line_db[n] > 0]
            count_list = None
            if counts_f and covered:
                count_list = tuple(max(line_db[n]
                                       for n in range(begin, end)
                                       if n in line_db)
                                   for begin, end in ranges_of(covered))
            file_db[path] = FileCoverage(path, ranges_of(executable),
                                         ranges_of(covered), count_list)

        return CoverageRecord(language = "ruby",
                              tool     = "",
                              source   = self.name,
                              counts_f = counts_f,
                              file_db  = file_db)


class SimplecovFramework(CCoverageFramework):
    """simplecov: invocation; reads SimplecovFormat."""
    name   = "simplecov"
    format = SimplecovFormat()

    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], 'argv' unchanged.

        SimpleCov starts INSIDE the ruby process ('SimpleCov.start'
        before the code under test loads) -- the test's own first lines,
        not a wrapper around them. This reader reports its absence by
        finding no resultset.
        """
        return list(argv)

    def report_argv(self, config, work_dir):
        """RETURN: None. The process writes the resultset at exit."""
        return None


def _absorb(line_db_by_file, path):
    """
    RETURN: None. Folds one resultset into 'line_db_by_file':
            path -> {line: count}, suites unioned by ADDING counts,
            'null' yielding to any integer.

    A json that is not a resultset is LEFT ALONE.
    """
    try:
        with io.open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return
    if not isinstance(document, dict): return

    for suite in document.values():
        if not isinstance(suite, dict): continue
        coverage_db = suite.get("coverage")
        if not isinstance(coverage_db, dict): continue
        for source, entry in coverage_db.items():
            array = (entry.get("lines")
                     if isinstance(entry, dict) else entry)
            if not isinstance(array, list): continue
            standing = line_db_by_file.setdefault(source, {})
            for index, value in enumerate(array):
                if not isinstance(value, int): continue     # null, or noise
                number = index + 1
                standing[number] = standing.get(number, 0) + value


register(SimplecovFramework())
