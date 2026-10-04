"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_cobertura' -- the output directory of a
         coverage run as ONE Cobertura XML report (coverage RATIONALE
         D-44), the format the CI dashboards read (Jenkins, GitLab,
         Azure, Codecov).

    hwut.cov.conv.to_cobertura [DIRECTORY] [-o FILE]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named); the report goes to FILE, or to
                                stdout.
    hwut.cov.conv.to_cobertura --help
                                this text

THE MAPPING, against the Cobertura DTD (coverage-04.dtd):

    <coverage>      line-rate, branch-rate, lines-valid, lines-covered,
                    branches-valid, branches-covered over the run;
                    'timestamp' is 0 and 'version' names hwut: nothing
                    of the day stands in the report (O-30)
    <source>        the run's root
    <package>       the directory of the source ('.' at the root);
                    <class> the source file, 'filename' its path from
                    the root
    <method>        one per function point: 'name', its line with
                    hits 1 or 0; 'signature' empty, which the DTD
                    allows and the readers accept
    <line>          every executable line, hits 1 or 0 -- hwut carries
                    no hit counts; a line with decisions carries
                    branch="true", condition-coverage="P% (taken/arms)"
                    and one <condition> per decision, type "jump"
    TG CP MC        not rendered: Cobertura has no toggle, cover point
                    or condition-independence; an XML comment names
                    them so a reader sees the gap

'complexity' is 0 everywhere: hwut does not measure it and will not
guess. WHO ran a line is not Cobertura's to say.

The exit status (E-1): OK with the report written, FAULT where the
directory cannot be read, REFUSED where the command line cannot be.
______________________________________________________________________________
"""
import sys
from   xml.sax.saxutils import quoteattr

from   vut.services.lib.cov.conv._face import help_of, one_file_main
from   vut.services.lib.cov.visitor    import I_OutputVisitor, walk

NAME  = "hwut.cov.conv.to_cobertura"
USAGE = "usage: %s [DIRECTORY] [-o FILE] | --help" % NAME
HELP  = help_of(__doc__)


def _rate(covered, total):
    """RETURN: str, Cobertura's rate: a fraction to four places, '0.0'
    where there is nothing to cover (the DTD knows no 'n/a')."""
    return "%.4f" % (covered / total) if total else "0.0"


class CoberturaVisitor(I_OutputVisitor):
    """The report (module header)."""

    def __init__(self):
        I_OutputVisitor.__init__(self)
        self.root        = None
        self.package_db  = {}          # package name -> [class xml]
        self.totals      = [0, 0, 0, 0]  # lines c, t; branches c, t
        self.pkg_totals  = {}          # package -> [lc, lt, bc, bt]
        self.summary     = None
        self.covered_set = set()
        self.line_db     = {}          # line -> (hits, [(taken, total)])
        self.method_list = []

    def header(self, root, summary_list):
        """RETURN: None. The root, for '<source>'."""
        self.root = root

    def source_open(self, summary):
        """RETURN: None. A class begins."""
        self.summary     = summary
        self.line_db     = {}
        self.method_list = []

    def lines(self, executable, covered, uncovered):
        """RETURN: None. Every executable line, hits 1 or 0."""
        self.covered_set = {n for b, e in covered for n in range(b, e)}
        for begin, end in executable:
            for line in range(begin, end):
                self.line_db[line] = (1 if line in self.covered_set else 0, [])

    def measure(self, measure, entry):
        """RETURN: None. Functions become methods, decisions become
        conditions; anything else is declared unrendered."""
        if measure.name == "function":
            for line, name, entered, _ in entry:
                self.method_list.append((name, line, entered))
        elif measure.name == "branch":
            for line, mask, total in entry:
                hits, condition_list = self.line_db.setdefault(line, (0, []))
                condition_list.append((bin(mask).count("1"), total))
        else:
            self.unrendered(measure)

    def who_ran(self, by_reference):
        """RETURN: None. NOTHING IS EMITTED: Cobertura has no place for
        the runs behind a line."""

    def source_close(self, summary):
        """RETURN: None. The class, with its methods and lines."""
        directory, _, base = summary.source.rpartition("/")
        package = directory or "."
        lc = sum(h for h, _ in self.line_db.values())
        lt = len(self.line_db)
        bc = sum(c for _, cl in self.line_db.values() for c, _ in cl)
        bt = sum(t for _, cl in self.line_db.values() for _, t in cl)
        out = ["      <class name=%s filename=%s line-rate=\"%s\" "
               "branch-rate=\"%s\" complexity=\"0\">"
               % (quoteattr(base), quoteattr(summary.source), _rate(lc, lt),
                  _rate(bc, bt)),
               "        <methods>"]
        for name, line, entered in self.method_list:
            out += ["          <method name=%s signature=\"\" line-rate=\"%s\" "
                    "branch-rate=\"0.0\" complexity=\"0\">"
                    % (quoteattr(name), _rate(entered, 1)),
                    "            <lines><line number=\"%i\" hits=\"%i\"/></lines>"
                    % (line, entered),
                    "          </method>"]
        out.append("        </methods>")
        out.append("        <lines>")
        for line in sorted(self.line_db):
            hits, condition_list = self.line_db[line]
            if not condition_list:
                out.append("          <line number=\"%i\" hits=\"%i\"/>" % (line, hits))
                continue
            c = sum(c for c, _ in condition_list)
            t = sum(t for _, t in condition_list)
            out.append("          <line number=\"%i\" hits=\"%i\" branch=\"true\" "
                       "condition-coverage=\"%i%% (%i/%i)\">"
                       % (line, hits, 100 * c // t if t else 0, c, t))
            out.append("            <conditions>")
            for number, (cc, ct) in enumerate(condition_list):
                out.append("              <condition number=\"%i\" type=\"jump\" "
                           "coverage=\"%i%%\"/>" % (number, 100 * cc // ct if ct else 0))
            out.append("            </conditions>")
            out.append("          </line>")
        out.append("        </lines>")
        out.append("      </class>")
        self.package_db.setdefault(package, []).append("\n".join(out))
        pt = self.pkg_totals.setdefault(package, [0, 0, 0, 0])
        for i, v in enumerate((lc, lt, bc, bt)):
            pt[i] += v; self.totals[i] += v

    def done(self):
        """RETURN: str, the report, LF terminated, with an XML comment
        naming the measures not rendered."""
        lc, lt, bc, bt = self.totals
        out = ["<?xml version=\"1.0\" ?>",
               "<!DOCTYPE coverage SYSTEM "
               "\"http://cobertura.sourceforge.net/xml/coverage-04.dtd\">"]
        if self.unrendered_set:
            out.append("<!-- not rendered by %s: %s -->"
                       % (NAME, ", ".join(sorted(self.unrendered_set))))
        out.append("<coverage line-rate=\"%s\" branch-rate=\"%s\" "
                   "lines-covered=\"%i\" lines-valid=\"%i\" "
                   "branches-covered=\"%i\" branches-valid=\"%i\" "
                   "complexity=\"0\" version=\"hwut\" timestamp=\"0\">"
                   % (_rate(lc, lt), _rate(bc, bt), lc, lt, bc, bt))
        out.append("  <sources>")
        out.append("    <source>%s</source>"
                   % (self.root if self.root is not None else "."))
        out.append("  </sources>")
        out.append("  <packages>")
        for package in sorted(self.package_db):
            plc, plt, pbc, pbt = self.pkg_totals[package]
            out.append("    <package name=%s line-rate=\"%s\" branch-rate=\"%s\" "
                       "complexity=\"0\">" % (quoteattr(package), _rate(plc, plt),
                                              _rate(pbc, pbt)))
            out.append("      <classes>")
            out += self.package_db[package]
            out.append("      </classes>")
            out.append("    </package>")
        out.append("  </packages>")
        out.append("</coverage>")
        return "\n".join(out) + "\n"


def main(argv=None, write=None, write_bytes=None):
    """RETURN: E_ExitCode (E-1), as '_face.one_file_main'."""
    return one_file_main(
        NAME, USAGE, HELP,
        lambda root, summary_list, found, target:
            walk(root, summary_list, CoberturaVisitor()).encode("utf-8"),
        argv, write, write_bytes)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
