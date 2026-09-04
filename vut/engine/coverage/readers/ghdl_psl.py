"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR GHDL'S PSL REPORT -- cover directives as named
         points.

DESCRIPTION
       WHAT IS READ, witnessed (TEST/REAL_PARSING_INPUT/PROVENANCE.txt): the json
       'ghdl -r ... --psl-report=FILE' writes -- a 'details' list, one
       entry per PSL directive:

           { "directive": "cover",
             "name": ".tb(sim).dut@blinker(rtl).cover_reach_done",
             "file": "blinker.vhdl", "line": 47,
             "finished-count": 5, ... }

       ONLY 'cover' DIRECTIVES BECOME COVERAGE. A cover names something
       the verification MEANT to see happen; 'finished-count' above zero
       is that thing seen -- a 'cover' point at the directive's own
       line, covered or not. An ASSERTION is a different question: it is
       a VERDICT (did the property ever fail), not a coverage to
       accumulate, and reading its counts as coverage would report a
       vacuously-passing assert as a green somebody earned. Asserts are
       left to the tool that judges them.

       THE POINT'S NAME is the directive's LABEL -- the last component
       of the report's instance-qualified name. The prefix is the
       INSTANCE; two instances of one entity carry one label at one
       line, and their points UNION (covered where either finished), the
       same per-declaration answer verilator gives.

       EX AND CV STAY EMPTY. This report says nothing about lines
       executing; inventing line coverage from directive positions would
       be the export's misfiling in the other direction. The record
       carries the 'cover' axis alone, and renders must say so.

       A JSON WITHOUT THE SHAPE IS LEFT ALONE: '.json' is anybody's
       suffix ('coverage.json' among them), and a document without a
       'details' list of directives is not this report.
______________________________________________________________________________
"""
import json
import os

from .reader import (CCoverageFramework, CCoverageFormat,
                      register, relative_path, wanted)
from ..database.record import FileCoverage


JSON_SUFFIX = (".json",)


class GhdlPslFormat(CCoverageFormat):
    """GHDL's '--psl-report' json."""
    name = "ghdl-psl-json"

    suffix = JSON_SUFFIX

    def absorb(self, accumulator, path):
        """RETURN: None. One PSL report folded in -- 'cover' points,
        keyed (source, line, label)."""
        _absorb(accumulator, path)

    def record_of(self, point_db, source_root, config, counts_f):
        """
        RETURN: CoverageRecord over the unioned reports -- 'cover'
                points per source file, EX/CV deliberately empty (see
                the module header), so 'counts_f' says nothing here.
        """
        file_db = {}
        for raw_path in sorted(set(source for source, _, _ in point_db)):
            path = relative_path(raw_path, source_root)
            if not wanted(path, config): continue
            point_tuple = tuple(sorted(
                (line, label, covered, 1)
                for (source, line, label), covered in point_db.items()
                if source == raw_path))
            file_db[path] = FileCoverage(path, (), (), None,
                                         {"cover": point_tuple})

        return self.record_from(file_db, False, _language_of(file_db))


class GhdlPslFramework(CCoverageFramework):
    """ghdl: invocation; reads GhdlPslFormat.

    NOTHING TO WRAP (the base's default): the report is asked for ON
    the run command line ('--psl-report=FILE'), and the PSL itself was
    compiled in with '-fpsl' -- both the build's and the test's own
    business; this reader reports their absence by finding no
    report.
    """
    name   = "ghdl"
    format = GhdlPslFormat()




def _absorb(point_db, path):
    """
    RETURN: None. Folds one report into 'point_db':
            (file, line, label) -> 0 or 1, UNIONED -- covered where any
            instance's directive finished.

    A json that is not this report is LEFT ALONE.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return
    if not isinstance(document, dict): return
    detail_list = document.get("details")
    if not isinstance(detail_list, list): return

    for detail in detail_list:
        if not isinstance(detail, dict):          continue
        if detail.get("directive") != "cover":    continue
        source = detail.get("file")
        line   = detail.get("line")
        if not source or not isinstance(line, int): continue
        label  = str(detail.get("name", "")).rsplit(".", 1)[-1]
        if not label: continue
        covered = 1 if detail.get("finished-count", 0) > 0 else 0
        key = (source, line, label)
        point_db[key] = max(point_db.get(key, 0), covered)


def _language_of(file_db):
    """
    RETURN: str, 'vhdl' where every file's extension says so; 'unknown'
            else. PSL rides in VHDL comments here; a report over
            something else should not borrow the name.
    """
    suffix_set = {os.path.splitext(path)[1].lower() for path in file_db}
    return ("vhdl" if suffix_set and suffix_set <= {".vhd", ".vhdl"}
            else "unknown")


register(GhdlPslFramework())
