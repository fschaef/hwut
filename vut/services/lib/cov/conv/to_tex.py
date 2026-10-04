"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_tex' -- the output directory of a coverage
         run as a LaTeX document (coverage RATIONALE D-44): the index
         over the sources, then every source listed with its lines
         coloured, its points and the test runs that executed them --
         for a report, an appendix, a print-out.

    hwut.cov.conv.to_tex [DIRECTORY] [-o FILE] [--style FILE]
                         [--body-only]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named); the document goes to FILE, or
                                to stdout. With '-o FILE' the package
                                'hwut-coverage.sty' is written beside it
                                where none stands yet, so the document
                                compiles where it lands.
        --style FILE            a style of the reader's: the document
                                loads '\\usepackage{FILE}' AFTER
                                'hwut-coverage', so every macro of the
                                package may be redefined there -- the
                                colours, the index table, the shape of
                                a listed line, or '\\covline' whole
        --body-only             the body alone, for '\\input' into a
                                document that owns the preamble and
                                loads 'hwut-coverage' itself
    hwut.cov.conv.to_tex --help
                                this text

THE BODY USES THE PACKAGE'S MACROS AND NOTHING ELSE ('hwut-coverage.sty'
beside this module names them): no colour, no font and no table shape
is written into the document, so a style decides every one of them.
Code is written escaped in '\\texttt', spaces as '~', so a line reads
as it stands in the file.

EVERY REGISTERED MEASURE IS RENDERED in the index and beside the lines
as 'to_html' renders it; a measure of another shape is declared and
named by '\\covnote' (D-29). A source the root no longer holds is listed
without its text, and the note says so. Nothing of the machine or the
day stands in the document (O-30).

The exit status (E-1): OK with the document written, FAULT where the
directory cannot be read or the files not written, REFUSED where the
command line cannot be.
______________________________________________________________________________
"""
import os
import shutil
import sys

from   vut.services.lib.cov.conv._face import help_of, one_file_main
from   vut.services.lib.cov.summary    import (line_count, measure_summary,
                                               percent)
from   vut.services.lib.cov.visitor    import I_OutputVisitor, walk

NAME  = "hwut.cov.conv.to_tex"
USAGE = ("usage: %s [DIRECTORY] [-o FILE] [--style FILE] [--body-only] | "
         "--help" % NAME)
HELP  = help_of(__doc__)

STYLE_NAME = "hwut-coverage"
STYLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          STYLE_NAME + ".sty")

HEAD_DB = {"branch": "branch arms", "function": "functions",
           "mcdc": "mc/dc conditions", "toggle": "toggle bits",
           "cover": "cover points"}


def escaped(text):
    """RETURN: str, 'text' with TeX's active characters made literal.
    A source path carrying '_' is the common case and would otherwise be
    a subscript."""
    out = []
    for ch in str(text):
        if   ch == "\\":       out.append("\\textbackslash{}")
        elif ch in "&%$#_{}":  out.append("\\" + ch)
        elif ch == "~":        out.append("\\textasciitilde{}")
        elif ch == "^":        out.append("\\textasciicircum{}")
        else:                  out.append(ch)
    return "".join(out)


def code(text):
    """RETURN: str, a line of code as TeX prints it: escaped, every
    space a '~' so the indentation stands, tabs as four."""
    return escaped(text.replace("\t", "    ")).replace(" ", "~")


class TexVisitor(I_OutputVisitor):
    """The document's body (module header). 'done' answers the body
    text; the preamble is the module's."""

    def __init__(self):
        I_OutputVisitor.__init__(self)
        self.root        = None
        self.name_list   = []
        self.row_list    = []
        self.total_db    = {}
        self.section_list = []
        self.cell_db     = {}
        self.point_db    = {}
        self.run_db      = {}
        self.covered_set = self.executable_set = frozenset()
        self.note_list   = []

    def header(self, root, summary_list):
        """RETURN: None. The root and the index's measure columns."""
        self.root      = root
        self.name_list = sorted({name for summary in summary_list
                                 for name in summary.measure_db})
        self.total_db  = {name: [0, 0] for name in ["lines"] + self.name_list}

    def source_open(self, summary):
        """RETURN: None. A source begins."""
        self.cell_db, self.point_db, self.run_db = {}, {}, {}

    def lines(self, executable, covered, uncovered):
        """RETURN: None. The sets the listing colours by."""
        self.executable_set = {n for b, e in executable for n in range(b, e)}
        self.covered_set    = {n for b, e in covered    for n in range(b, e)}

    def measure(self, measure, entry):
        """RETURN: None. As 'to_html': 'TAG taken/total' per decision,
        'TAG name' per named point; another shape is declared."""
        self.cell_db[measure.name] = measure_summary(measure.name, entry)
        for point in entry:
            if len(point) == 3 and not measure.named_f:
                line, mask, total = point
                text = "%s %i/%i" % (measure.tag, bin(mask).count("1"), total)
            elif len(point) == 4 and measure.named_f:
                line, name, covered, _ = point
                text = "%s %s%s" % (measure.tag, escaped(name),
                                    "" if covered else " (not)")
            else:
                del self.cell_db[measure.name]
                return self.unrendered(measure)
            self.point_db.setdefault(line, []).append(text)

    def who_ran(self, by_reference):
        """RETURN: None. Per covered line, the runs."""
        for name_tuple, span_tuple in by_reference:
            for begin, end in span_tuple:
                for line in range(begin, end):
                    self.run_db[line] = name_tuple

    def source_close(self, summary):
        """RETURN: None. The index row and the source's section."""
        covered_n = line_count(summary.covered)
        total_n   = line_count(summary.executable)
        self.total_db["lines"][0] += covered_n
        self.total_db["lines"][1] += total_n
        cell_list = ["\\texttt{%s}" % escaped(summary.source),
                     "%i/%i" % (covered_n, total_n),
                     escaped(percent(covered_n, total_n))]
        head = "lines %i/%i (%s)" % (covered_n, total_n,
                                     escaped(percent(covered_n, total_n)))
        for name in self.name_list:
            pair = self.cell_db.get(name)
            if pair is None:
                cell_list += ["--", "--"]
                continue
            c, t = pair
            self.total_db[name][0] += c; self.total_db[name][1] += t
            cell_list += ["%i/%i" % (c, t), escaped(percent(c, t))]
            head += "; %s %i/%i (%s)" % (HEAD_DB.get(name, name), c, t,
                                         escaped(percent(c, t)))
        self.row_list.append("  \\covindexrow{%s}" % " & ".join(cell_list))

        text_list, note = None, None
        if self.root is not None:
            path = os.path.join(self.root, *summary.source.split("/"))
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text_list = handle.read().split("\n")
                if text_list and text_list[-1] == "": text_list.pop()
            except OSError:
                note = ("the source file was not found under the root; the "
                        "lines stand without their text")
        else:
            note = "the output names no root; the lines stand without their text"
        last = max([len(text_list or ()), max(self.executable_set, default=0),
                    max(self.point_db, default=0)])
        section = ["\\covsource{%s}{%s}" % (escaped(summary.source), head)]
        if note: section.append("\\covnote{%s}" % note)
        section.append("\\begin{covlisting}")
        for number in range(1, last + 1):
            if number in self.covered_set:      state = "cov"
            elif number in self.executable_set: state = "unc"
            else:                               state = "non"
            text = text_list[number - 1] if text_list is not None \
                   and number <= len(text_list) else ""
            section.append("  \\covline{%s}{%i}{%s}{%s}{%s}"
                           % (state, number, code(text),
                              ", ".join(self.point_db.get(number, ())),
                              escaped(", ".join(self.run_db.get(number, ())))))
        section.append("\\end{covlisting}")
        self.section_list.append("\n".join(section))

    def done(self):
        """RETURN: str, the body: title, root, notes, index, sections."""
        out = ["\\covtitle{Coverage}"]
        if self.root is not None:
            out.append("\\covroot{%s}" % escaped(self.root))
        if self.unrendered_set:
            out.append("\\covnote{not rendered by %s: %s}"
                       % (escaped(NAME),
                          escaped(", ".join(sorted(self.unrendered_set)))))
        head = ["source", "lines", "\\%"]
        for name in self.name_list: head += [HEAD_DB.get(name, name), "\\%"]
        out.append("\\begin{covindex}{%i}" % len(self.name_list))
        out.append("  \\covindexhead{%s}" % " & ".join(head))
        out += self.row_list
        foot = ["all"]
        for name in ["lines"] + self.name_list:
            pair = self.total_db[name]
            foot += ["%i/%i" % tuple(pair), escaped(percent(*pair))]
        out.append("  \\covindextotal{%s}" % " & ".join(foot))
        out.append("\\end{covindex}")
        out += self.section_list
        return "\n".join(out) + "\n"


def document(body, style=None):
    """RETURN: str, the whole document around 'body': article class,
    the package, the reader's style after it where one is named."""
    head = ["\\documentclass{article}",
            "\\usepackage[margin=2cm]{geometry}",
            "\\usepackage{%s}" % STYLE_NAME]
    if style: head.append("\\usepackage{%s}" % style)
    return "\n".join(head + ["\\begin{document}", body.rstrip("\n"),
                             "\\end{document}"]) + "\n"


def tex_of(root, summary_list, style=None, body_only=False):
    """RETURN: str, the document, or the body alone."""
    body = walk(root, summary_list, TexVisitor())
    return body if body_only else document(body, style)


def place_style(directory):
    """RETURN: str, the path of 'hwut-coverage.sty' in 'directory',
    copied there where none stands yet. Raises OSError."""
    target = os.path.join(directory, STYLE_NAME + ".sty")
    if not os.path.isfile(target): shutil.copyfile(STYLE_PATH, target)
    return target


def _build(root, summary_list, found, target):
    """RETURN: bytes, the document; the package placed beside '-o'."""
    style = found["--style"]
    if style is not None and style.endswith(".sty"): style = style[:-4]
    if target is not None and not found["--body-only"]:
        place_style(os.path.dirname(os.path.abspath(target)))
    return tex_of(root, summary_list, style, found["--body-only"]).encode("utf-8")


def main(argv=None, write=None, write_bytes=None):
    """RETURN: E_ExitCode (E-1), as '_face.one_file_main'."""
    return one_file_main(NAME, USAGE, HELP, _build, argv, write, write_bytes,
                         option_db={"--style": "FILE"},
                         flag_set=("--body-only",))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
