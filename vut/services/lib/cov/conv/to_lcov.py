"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_lcov' -- the output directory of a coverage
         run as ONE lcov tracefile (coverage RATIONALE D-6, D-43, D-44),
         for 'genhtml' and every other tool that reads lcov.

    hwut.cov.conv.to_lcov [DIRECTORY] [-o FILE]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named); the tracefile goes to FILE, or
                                to stdout.
    hwut.cov.conv.to_lcov --help
                                this text

THE MAPPING IS LOSSY BY CONSTRUCTION, as D-43 states, and in exactly
these ways:

    SF    the source's path from the run's root, made absolute with the
          root the marker names
    DA    every executable line, count 1 where ANY test run executed it
          and 0 where none did -- hwut carries no hit counts
    FN    every function point, at its line; FNDA 1 or 0
    BRDA  every arm of every decision: the BLOCK is the decision's place
          among the decisions of its line, the BRANCH the arm's index;
          taken is 1 or 0, and '-' where the decision's line was never
          executed, as lcov spells a block never entered
    TG CP not rendered: lcov has no toggle and no cover point; the
          tracefile SAYS so in a '#' line before the record
    MC    not rendered, OWED: lcov 2.2 spells MC/DC, but no reader
          produces the measure yet and no tracefile carrying it was
          witnessed; writing the line from memory would be the
          invention every reader of this component refuses

WHO EXECUTED WHAT -- the test runs and the groups behind each range --
is what lcov cannot say and this component's own files do. The
tracefile is a presentation for the tools that want lcov; the output
directory stays the one place the data is kept.

The exit status (E-1): OK with the tracefile written, FAULT where the
directory cannot be read, REFUSED where the command line cannot be.
______________________________________________________________________________
"""
import os
import sys

from   vut.services.lib.cov.conv._face import help_of, one_file_main
from   vut.services.lib.cov.visitor    import I_OutputVisitor, walk

NAME  = "hwut.cov.conv.to_lcov"
USAGE = "usage: %s [DIRECTORY] [-o FILE] | --help" % NAME
HELP  = help_of(__doc__)


class LcovVisitor(I_OutputVisitor):
    """The tracefile, one record per source (module header)."""

    RENDERED_SET = frozenset(("branch", "function"))

    def __init__(self):
        I_OutputVisitor.__init__(self)
        self.root        = None
        self.line_list   = []
        self.covered_set = set()
        self.body        = []          # the current record's lines
        self.da_list     = []

    def header(self, root, summary_list):
        """RETURN: None. The root, for 'SF'."""
        self.root = root

    def source_open(self, summary):
        """RETURN: None. 'TN:' and 'SF:' open the record."""
        self.body = ["TN:",
                     "SF:%s" % (os.path.join(self.root, *summary.source.split("/"))
                                if self.root is not None else summary.source)]

    def lines(self, executable, covered, uncovered):
        """RETURN: None. The 'DA' lines are kept for the record's end,
        where lcov places them; the covered set serves 'BRDA'."""
        self.covered_set = {line for begin, end in covered
                            for line in range(begin, end)}
        self.da_list, hit_n = [], 0
        for begin, end in executable:
            for line in range(begin, end):
                hit = 1 if line in self.covered_set else 0
                self.da_list.append("DA:%i,%i" % (line, hit))
                hit_n += hit
        self.da_list += ["LF:%i" % sum(e - b for b, e in executable),
                         "LH:%i" % hit_n]

    def measure(self, measure, entry):
        """RETURN: None. 'FN'/'FNDA' for the functions, 'BRDA' for the
        arms; every other measure is declared unrendered."""
        if measure.name == "function":
            for line, name, _, _ in entry:
                self.body.append("FN:%i,%s" % (line, name))
            for _, name, entered, _ in entry:
                self.body.append("FNDA:%i,%s" % (entered, name))
            self.body.append("FNF:%i" % len(entry))
            self.body.append("FNH:%i" % sum(e for _, _, e, _ in entry))
        elif measure.name == "branch":
            found_n = taken_n = 0
            block_db = {}
            for line, mask, total in entry:
                block = block_db.get(line, 0)
                block_db[line] = block + 1
                for arm in range(total):
                    taken = (mask >> arm) & 1
                    self.body.append("BRDA:%i,%i,%i,%s" % (
                        line, block, arm,
                        "-" if line not in self.covered_set else str(taken)))
                    found_n += 1
                    taken_n += taken
            self.body.append("BRF:%i" % found_n)
            self.body.append("BRH:%i" % taken_n)
        else:
            self.unrendered(measure)

    def who_ran(self, by_reference):
        """RETURN: None. NOTHING IS EMITTED: lcov has no place for the
        runs behind a range; that is what the output directory is
        for."""

    def source_close(self, summary):
        """RETURN: None. The record, closed."""
        self.line_list += self.body + self.da_list + ["end_of_record"]

    def done(self):
        """RETURN: str, the tracefile, LF terminated; empty where there
        is no source. A '#' line names the measures not rendered, so a
        reader sees the gap."""
        head = []
        if self.unrendered_set:
            head.append("# not rendered by %s: %s"
                        % (NAME, ", ".join(sorted(self.unrendered_set))))
        line_list = head + self.line_list
        return "\n".join(line_list) + "\n" if line_list else ""


def main(argv=None, write=None, write_bytes=None):
    """RETURN: E_ExitCode (E-1), as '_face.one_file_main'."""
    return one_file_main(
        NAME, USAGE, HELP,
        lambda root, summary_list, found, target:
            walk(root, summary_list, LcovVisitor()).encode("utf-8"),
        argv, write, write_bytes)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
