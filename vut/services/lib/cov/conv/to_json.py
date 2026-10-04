"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_json' -- the output directory of a coverage
         run as ONE JSON document, LOSSLESS (coverage RATIONALE D-44):
         everything the directory says, for a script that wants it
         without reading the binary files.

    hwut.cov.conv.to_json [DIRECTORY] [-o FILE]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named); the document goes to FILE, or
                                to stdout.
    hwut.cov.conv.to_json --help
                                this text

THE DOCUMENT, keys sorted, two-space indent, LF terminated:

    {"format": "hwut-coverage-json", "version": 1,
     "root": "<the run's root>",
     "sources": [
       {"source": "src/a.c",
        "lines": {"executable": [[1, 10]], "covered": [[1, 6]],
                  "uncovered": [[6, 10]]},
        "measures": {"branch": [[3, 1, 2], ...],
                     "toggle": [[2, "clk", 1, 1], ...]},
        "who_ran": [{"runs": ["t0", "t1"], "ranges": [[1, 3]]}, ...]
       }, ...]}

Ranges are half-open [begin, end) as everywhere in this component. A
measure stands in its OWN SHAPE (database/measure.py): a decision point
'[line, mask, total]', a named point '[line, name, covered, total]'. So
EVERY REGISTERED MEASURE IS RENDERED by construction, as the record's
text spelling renders it, and none is declared unrendered -- the one
format beside the record's own that may say so (D-29).

The exit status (E-1): OK with the document written, FAULT where the
directory cannot be read, REFUSED where the command line cannot be.
______________________________________________________________________________
"""
import json
import sys

from   vut.services.lib.cov.conv._face import help_of, one_file_main
from   vut.services.lib.cov.visitor    import I_OutputVisitor, walk

NAME  = "hwut.cov.conv.to_json"
USAGE = "usage: %s [DIRECTORY] [-o FILE] | --help" % NAME
HELP  = help_of(__doc__)


class JsonVisitor(I_OutputVisitor):
    """The document (module header)."""

    def __init__(self):
        I_OutputVisitor.__init__(self)
        self.document    = {"format": "hwut-coverage-json", "version": 1,
                            "root": None, "sources": []}
        self.entry       = None

    def header(self, root, summary_list):
        """RETURN: None. The root."""
        self.document["root"] = root

    def source_open(self, summary):
        """RETURN: None. A source's object begins."""
        self.entry = {"source": summary.source, "lines": {},
                      "measures": {}, "who_ran": []}

    def lines(self, executable, covered, uncovered):
        """RETURN: None. The three range lists."""
        self.entry["lines"] = {"executable": [list(r) for r in executable],
                               "covered":    [list(r) for r in covered],
                               "uncovered":  [list(r) for r in uncovered]}

    def measure(self, measure, entry):
        """RETURN: None. The entry in the measure's own shape -- every
        measure, by construction."""
        self.entry["measures"][measure.name] = [list(p) for p in entry]

    def who_ran(self, by_reference):
        """RETURN: None. Per reference, the runs and the ranges."""
        self.entry["who_ran"] = [{"runs": list(name_tuple),
                                  "ranges": [list(r) for r in span_tuple]}
                                 for name_tuple, span_tuple in by_reference]

    def source_close(self, summary):
        """RETURN: None. The object joins the list."""
        self.document["sources"].append(self.entry)

    def done(self):
        """RETURN: str, the document, LF terminated."""
        return json.dumps(self.document, indent=2, sort_keys=True,
                          ensure_ascii=False) + "\n"


def main(argv=None, write=None, write_bytes=None):
    """RETURN: E_ExitCode (E-1), as '_face.one_file_main'."""
    return one_file_main(
        NAME, USAGE, HELP,
        lambda root, summary_list, found, target:
            walk(root, summary_list, JsonVisitor()).encode("utf-8"),
        argv, write, write_bytes)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
