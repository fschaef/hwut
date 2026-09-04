"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE: PRESENTERS -- a coverage record rendered for a reader, rather
         than for the store.
DESCRIPTION
       'record.walk(record, presenter)' is the ONE traversal; these are
       operations over it. 'record.TextPresenter' is the storage form
       and lives beside the walk because its bytes are an oracle; these
       two are for people.

           HtmlPresenter    a page: one table, a row per source file,
                            the uncovered ranges spelled out
           TexPresenter     a longtable for a report or an appendix

       EACH RENDERS THE AXES IT KNOWS AND ANNOUNCES THE REST. The
       visitor is written over a SETTLED set of coverage axes
       ('record.I_Presenter'), so a new axis costs both of these an
       edit -- and should. A presenter that met 'mcdc' and printed
       'mcdc 3/7' from a generic summary would look complete and be
       deficient: what makes MC/DC MC/DC is WHICH condition
       combinations ran, and a fraction has discarded it. So an axis
       neither presenter knows is NOT rendered; its name is collected
       and SAID in the output, and the gap stands where a reader sees
       it until somebody closes it.

       ESCAPING IS THE PRESENTER'S OWN BUSINESS. A source path may
       carry '&' or '_'; HTML and TeX disagree about what that means,
       and neither the record nor the measure should know.

       A RATIO IS DERIVED, NEVER STORED (record.py): 'entry.ratio' is
       None where a file has no executable line, and both presenters
       SAY so rather than printing 100% -- a lie told in the green
       direction is still a lie.
______________________________________________________________________________
"""
from .record import I_Presenter, line_n, walk


def _percent(ratio):
    """
    RETURN: str, the ratio as a percentage to one decimal.
            'n/a', where 'ratio' is None -- a file with no executable
            line has NO coverage ratio, and 100% would be a lie.
    """
    return "n/a" if ratio is None else "%.1f%%" % (100.0 * ratio)


def _range_text(range_tuple):
    """
    RETURN: str, half-open ranges as a reader reads them -- '12' for one
            line, '12-19' for several, comma separated. Empty string
            where there are none.

    THE STORED FORM IS DELTA CODED and the presenter does not show it:
    'd+L' is for the disk, where every byte counts, not for a person.
    """
    part_list = []
    for begin, end in range_tuple:
        part_list.append("%d" % begin if end - begin == 1
                         else "%d-%d" % (begin, end - 1))
    return ", ".join(part_list)


class HtmlPresenter(I_Presenter):
    """A record as one HTML page: the provenance, then a table with a
    row per source file -- lines covered of executable, the ratio, the
    uncovered ranges, and one cell per measure that file carries."""

    #  THE AXES THIS PRESENTER RENDERS. A count of points covered out
    #  of points present is an honest reading of BRANCH, TOGGLE and
    #  COVER: each is a set of independent points, and how many ran is
    #  what a table cell of a file summary is for. It is NOT an honest
    #  reading of every axis that could register, which is why the set
    #  is named rather than assumed.
    RENDERED_SET = frozenset(("branch", "toggle", "cover"))

    def __init__(self, title="Coverage"):
        I_Presenter.__init__(self)
        self.title     = title
        self.head_list = []
        self.row_list  = []
        self.cell_list = []
        self.path      = None
        self.entry     = None

    @staticmethod
    def escaped(text):
        """RETURN: str, with the three characters that end an HTML text
        node spelled as entities."""
        return (str(text).replace("&", "&amp;")
                         .replace("<", "&lt;")
                         .replace(">", "&gt;"))

    def header(self, record):
        """RETURN: None. The provenance, as a definition list."""
        for name, value in (("language", record.language),
                            ("tool",     record.tool or "(unstamped)"),
                            ("format",   record.source),
                            ("counts",   "yes" if record.counts_f else "no"),
                            ("runs",     len(record.run) or "(unseated)")):
            self.head_list.append("    <dt>%s</dt><dd>%s</dd>"
                                  % (name, self.escaped(value)))

    def file_open(self, path, entry):
        """RETURN: None. A row begins; its measure cells collect."""
        self.path      = path
        self.entry     = entry
        self.cell_list = []

    def lines(self, executable, covered, count_tuple):
        """RETURN: None. The line axis is the row's fixed left part."""

    def measure(self, measure, point_tuple):
        """RETURN: None. One cell for an axis this presenter renders;
        for any other, the base records the name as unrendered and
        'done' announces it."""
        if measure.name not in self.RENDERED_SET:
            return self.unrendered(measure)
        covered, total = measure.summary(point_tuple)
        self.cell_list.append("%s %d/%d" % (self.escaped(measure.name),
                                            covered, total))

    def file_close(self, path, entry):
        """RETURN: None. The row, complete."""
        self.row_list.append(
            "      <tr><td>%s</td><td>%d/%d</td><td>%s</td>"
            "<td>%s</td><td>%s</td></tr>"
            % (self.escaped(path),
               line_n(entry.covered), line_n(entry.executable),
               _percent(entry.ratio),
               self.escaped(_range_text(entry.uncovered)),
               self.escaped("; ".join(self.cell_list))))

    def done(self):
        """RETURN: str, the page -- with a NOTICE naming any axis this
        presenter does not render, so a gap is seen and not guessed
        at."""
        notice = ""
        if self.unrendered_set:
            notice = ("    <p><strong>not rendered by this presenter:</strong>"
                      " %s</p>\n"
                      % self.escaped(", ".join(sorted(self.unrendered_set))))
        return ("<!DOCTYPE html>\n<html>\n  <head><title>%s</title></head>\n"
                "  <body>\n    <h1>%s</h1>\n    <dl>\n%s\n    </dl>\n"
                "%s"
                "    <table>\n      <tr><th>file</th><th>covered</th>"
                "<th>ratio</th><th>uncovered lines</th>"
                "<th>other measures</th></tr>\n%s\n    </table>\n"
                "  </body>\n</html>\n"
                % (self.escaped(self.title), self.escaped(self.title),
                   "\n".join(self.head_list), notice,
                   "\n".join(self.row_list)))


class TexPresenter(I_Presenter):
    """A record as a LaTeX 'longtable' -- a report's appendix, one row
    per source file. Emits the table alone, for \\input into a document
    that owns the preamble."""

    RENDERED_SET = frozenset(("branch", "toggle", "cover"))

    def __init__(self, caption="Coverage"):
        I_Presenter.__init__(self)
        self.caption   = caption
        self.head_list = []
        self.row_list  = []
        self.cell_list = []

    @staticmethod
    def escaped(text):
        """RETURN: str, with TeX's active characters made literal. A
        source path carrying '_' is the common case and would
        otherwise be a subscript."""
        out = []
        for ch in str(text):
            if   ch == "\\":            out.append("\\textbackslash{}")
            elif ch in "&%$#_{}":       out.append("\\" + ch)
            elif ch == "~":             out.append("\\textasciitilde{}")
            elif ch == "^":             out.append("\\textasciicircum{}")
            else:                       out.append(ch)
        return "".join(out)

    def header(self, record):
        """RETURN: None. The provenance, as a leading remark."""
        self.head_list.append(
            "%% language: %s, tool: %s, format: %s, counts: %s"
            % (record.language, record.tool or "(unstamped)",
               record.source, "yes" if record.counts_f else "no"))

    def file_open(self, path, entry):
        """RETURN: None. A row begins."""
        self.cell_list = []

    def lines(self, executable, covered, count_tuple):
        """RETURN: None. NOTHING IS EMITTED HERE: the line axis is the
        row's fixed left part and is read off 'entry' in 'file_close',
        where the whole row is written at once."""

    def measure(self, measure, point_tuple):
        """RETURN: None. One cell for an axis this presenter renders;
        any other is declared unrendered and named by 'done'."""
        if measure.name not in self.RENDERED_SET:
            return self.unrendered(measure)
        covered, total = measure.summary(point_tuple)
        self.cell_list.append("%s %d/%d" % (self.escaped(measure.name),
                                            covered, total))

    def file_close(self, path, entry):
        """RETURN: None. The row, complete."""
        self.row_list.append(
            "  \\texttt{%s} & %d/%d & %s & %s & %s \\\\"
            % (self.escaped(path),
               line_n(entry.covered), line_n(entry.executable),
               self.escaped(_percent(entry.ratio)),
               self.escaped(_range_text(entry.uncovered)),
               self.escaped("; ".join(self.cell_list))))

    def done(self):
        """RETURN: str, the longtable -- preceded by a remark naming
        any axis this presenter does not render, so a gap is seen and
        not guessed at."""
        head_list = list(self.head_list)
        if self.unrendered_set:
            head_list.append(
                "%% not rendered by this presenter: %s"
                % self.escaped(", ".join(sorted(self.unrendered_set))))
        return ("%s\n\\begin{longtable}{lllll}\n"
                "  \\caption{%s}\\\\\n  \\hline\n"
                "  file & covered & ratio & uncovered & other \\\\\n"
                "  \\hline\n\\endhead\n%s\n  \\hline\n"
                "\\end{longtable}\n"
                % ("\n".join(head_list), self.escaped(self.caption),
                   "\n".join(self.row_list)))


def html_of(record, title="Coverage"):
    """RETURN: str, the record as an HTML page."""
    return walk(record, HtmlPresenter(title))


def tex_of(record, caption="Coverage"):
    """RETURN: str, the record as a LaTeX longtable."""
    return walk(record, TexPresenter(caption))
