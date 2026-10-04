"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_jacoco' -- the output directory of a coverage
         run as ONE JaCoCo XML report (coverage RATIONALE D-44), for the
         tools that read JaCoCo (SonarQube, Jenkins' JaCoCo plugin).

    hwut.cov.conv.to_jacoco [DIRECTORY] [-o FILE]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named); the report goes to FILE, or to
                                stdout.
    hwut.cov.conv.to_jacoco --help
                                this text

THE MAPPING, against JaCoCo's report.dtd:

    <report>        name "hwut"; no <sessioninfo>: nothing of the day
                    stands in the report (O-30)
    <package>       the directory of the source ('.' at the root)
    <class>         one per source file, 'name' the path without its
                    extension (JaCoCo's class names are paths),
                    'sourcefilename' the base name; one <method> per
                    function point with 'name', 'desc' "()", 'line',
                    and a METHOD counter 0/1
    <sourcefile>    the source file, 'name' its base name; one <line>
                    per executable line with mi/ci (missed/covered
                    instructions: 1/0 or 0/1 -- hwut counts lines, so
                    a line is one instruction) and mb/cb (missed and
                    covered branch arms of the line's decisions)
    <counter>       INSTRUCTION, LINE, BRANCH, METHOD per class,
                    sourcefile, package and report
    TG CP MC        not rendered: JaCoCo has none; an XML comment names
                    them so a reader sees the gap

WHO ran a line is not JaCoCo's to say.

The exit status (E-1): OK with the report written, FAULT where the
directory cannot be read, REFUSED where the command line cannot be.
______________________________________________________________________________
"""
import sys
from   xml.sax.saxutils import quoteattr

from   vut.services.lib.cov.conv._face import help_of, one_file_main
from   vut.services.lib.cov.visitor    import I_OutputVisitor, walk

NAME  = "hwut.cov.conv.to_jacoco"
USAGE = "usage: %s [DIRECTORY] [-o FILE] | --help" % NAME
HELP  = help_of(__doc__)

COUNTER_TUPLE = ("INSTRUCTION", "LINE", "BRANCH", "METHOD")


def _counters(indent, count_db):
    """RETURN: list of str, one <counter> per type, missed and covered."""
    return ["%s<counter type=\"%s\" missed=\"%i\" covered=\"%i\"/>"
            % (indent, kind, count_db[kind][0], count_db[kind][1])
            for kind in COUNTER_TUPLE]


def _add(into, count_db):
    """RETURN: None. 'count_db' added into 'into', per type."""
    for kind in COUNTER_TUPLE:
        into[kind][0] += count_db[kind][0]
        into[kind][1] += count_db[kind][1]


def _fresh():
    """RETURN: dict, type -> [missed, covered], all zero."""
    return {kind: [0, 0] for kind in COUNTER_TUPLE}


class JacocoVisitor(I_OutputVisitor):
    """The report (module header)."""

    def __init__(self):
        I_OutputVisitor.__init__(self)
        self.package_db  = {}          # package -> [sourcefile xml]
        self.pkg_count   = {}          # package -> count_db
        self.all_count   = _fresh()
        self.line_db     = {}          # line -> [ci, mb, cb]
        self.method_n    = [0, 0]      # missed, covered
        self.method_list = []          # (name, line, entered)

    def header(self, root, summary_list):
        """RETURN: None. NOTHING IS EMITTED: JaCoCo names no root."""

    def source_open(self, summary):
        """RETURN: None. A sourcefile begins."""
        self.line_db  = {}
        self.method_n = [0, 0]
        self.method_list = []

    def lines(self, executable, covered, uncovered):
        """RETURN: None. Every executable line, one instruction."""
        covered_set = {n for b, e in covered for n in range(b, e)}
        for begin, end in executable:
            for line in range(begin, end):
                self.line_db[line] = [1 if line in covered_set else 0, 0, 0]

    def measure(self, measure, entry):
        """RETURN: None. Functions count as methods, decisions as
        branches; anything else is declared unrendered."""
        if measure.name == "function":
            for line, name, entered, _ in entry:
                self.method_n[1 if entered else 0] += 1
                self.method_list.append((name, line, entered))
        elif measure.name == "branch":
            for line, mask, total in entry:
                cell = self.line_db.setdefault(line, [0, 0, 0])
                taken = bin(mask).count("1")
                cell[1] += total - taken
                cell[2] += taken
        else:
            self.unrendered(measure)

    def who_ran(self, by_reference):
        """RETURN: None. NOTHING IS EMITTED: JaCoCo has no place for
        the runs behind a line."""

    def source_close(self, summary):
        """RETURN: None. The sourcefile with its lines and counters."""
        directory, _, base = summary.source.rpartition("/")
        package  = directory or "."
        count_db = _fresh()
        stem = summary.source.rsplit(".", 1)[0] if "." in base else summary.source
        out = ["    <class name=%s sourcefilename=%s>"
               % (quoteattr(stem), quoteattr(base))]
        for name, line, entered in self.method_list:
            out.append("      <method name=%s desc=\"()\" line=\"%i\">"
                       % (quoteattr(name), line))
            out.append("        <counter type=\"METHOD\" missed=\"%i\" "
                       "covered=\"%i\"/>" % (1 - entered, entered))
            out.append("      </method>")
        out.append("    </class>")
        out.append("    <sourcefile name=%s>" % quoteattr(base))
        for line in sorted(self.line_db):
            ci, mb, cb = self.line_db[line]
            out.append("      <line nr=\"%i\" mi=\"%i\" ci=\"%i\" mb=\"%i\" cb=\"%i\"/>"
                       % (line, 1 - ci, ci, mb, cb))
            count_db["INSTRUCTION"][ci] += 1
            count_db["LINE"][ci] += 1
            count_db["BRANCH"][0] += mb
            count_db["BRANCH"][1] += cb
        count_db["METHOD"] = list(self.method_n)
        out += _counters("      ", count_db)
        out.append("    </sourcefile>")
        self.package_db.setdefault(package, []).append("\n".join(out))
        _add(self.pkg_count.setdefault(package, _fresh()), count_db)
        _add(self.all_count, count_db)

    def done(self):
        """RETURN: str, the report, LF terminated, with an XML comment
        naming the measures not rendered."""
        out = ["<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
               "<!DOCTYPE report PUBLIC \"-//JACOCO//DTD Report 1.1//EN\" "
               "\"report.dtd\">"]
        if self.unrendered_set:
            out.append("<!-- not rendered by %s: %s -->"
                       % (NAME, ", ".join(sorted(self.unrendered_set))))
        out.append("<report name=\"hwut\">")
        for package in sorted(self.package_db):
            out.append("  <package name=%s>" % quoteattr(package))
            out += self.package_db[package]
            out += _counters("    ", self.pkg_count[package])
            out.append("  </package>")
        out += _counters("  ", self.all_count)
        out.append("</report>")
        return "\n".join(out) + "\n"


def main(argv=None, write=None, write_bytes=None):
    """RETURN: E_ExitCode (E-1), as '_face.one_file_main'."""
    return one_file_main(
        NAME, USAGE, HELP,
        lambda root, summary_list, found, target:
            walk(root, summary_list, JacocoVisitor()).encode("utf-8"),
        argv, write, write_bytes)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
