"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_html' -- the output directory of a coverage
         run as HTML pages for people (coverage RATIONALE D-44): what
         was covered, what was not, and WHO ran what -- the one thing
         every other coverage format cannot say.

    hwut.cov.conv.to_html [DIRECTORY] [-o OUTDIR]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named). The pages go to OUTDIR,
                                'DIRECTORY/html' where none is named:

        index.html              one row per source file: lines covered
                                of executable and the percentage, then
                                one column per measure any source
                                carries (branch arms, functions, mc/dc,
                                toggle bits, cover points), covered of
                                total and the percentage; 'n/a' where
                                there is nothing to cover
        <source path>.html      the source, every executable line
                                coloured covered or not, the points of
                                the line beside it ('BR 1/2', 'FN main'),
                                and the TEST RUNS that executed the
                                line: 'directory/test choice', from
                                the output's own tables

    hwut.cov.conv.to_html --help
                                this text

THE PAGES ARE SELF-CONTAINED: one style block, no script, no file
fetched from anywhere, so they open from a disk and travel in a mail.
Nothing in them is the machine's or the day's: two runs over one tree
write the same pages (O-30).

EVERY REGISTERED MEASURE IS RENDERED: branch and mc/dc as the items
taken of the items there are, the named points by name. A measure that
registers later and is none of these is declared and NAMED on the index
page rather than guessed at (D-29).

A SOURCE THE ROOT NO LONGER HOLDS gets its page without the text: the
line numbers, the colour and the runs stand, and the page says the file
was not found. The browser is never opened; the path of 'index.html' is
written.

The exit status (E-1): OK with the pages written, FAULT where the
directory cannot be read or OUTDIR not written, REFUSED where the
command line cannot be read.
______________________________________________________________________________
"""
import html
import os
import sys

from   vut.services.lib.cov.conv._face import help_of, many_files_main
from   vut.services.lib.cov.summary    import (line_count, measure_summary,
                                               percent)
from   vut.services.lib.cov.visitor    import I_OutputVisitor, walk

NAME  = "hwut.cov.conv.to_html"
USAGE = "usage: %s [DIRECTORY] [-o OUTDIR] | --help" % NAME
HELP  = help_of(__doc__)

#  The column heads, by measure name; a measure registered later shows
#  under its name.
HEAD_DB = {"branch": "branch arms", "function": "functions",
           "mcdc": "mc/dc conditions", "toggle": "toggle bits",
           "cover": "cover points"}

STYLE = """\
    body { font-family: sans-serif; margin: 1.5em; color: #222; }
    table { border-collapse: collapse; }
    th, td { padding: 0.2em 0.7em; text-align: left;
             border-bottom: 1px solid #ddd; vertical-align: top; }
    th { background: #f0f0f0; }
    td.n { text-align: right; }
    .src td { padding: 0 0.6em; border: none; font-family: monospace;
              white-space: pre; }
    .src td.ln { color: #888; text-align: right; }
    .src td.runs, .src td.pts { font-family: sans-serif; font-size: 85%;
                                color: #555; white-space: normal; }
    tr.cov td.txt { background: #dff5dd; }
    tr.unc td.txt { background: #f8d7d7; }
    tr.cov td.pts { color: #2a6; }
    p.note { color: #a33; }
"""


def _e(text):
    """RETURN: str, 'text' with HTML's active characters as entities."""
    return html.escape(str(text), quote=True)


def _page(title, body):
    """RETURN: str, one complete HTML document."""
    return ("<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
            "<title>%s</title>\n<style>\n%s</style>\n</head>\n<body>\n"
            "%s</body>\n</html>\n" % (_e(title), STYLE, body))


def page_path(source):
    """RETURN: str, the page of 'source', relative to OUTDIR, with '/'
    between."""
    return source + ".html"


class HtmlVisitor(I_OutputVisitor):
    """The pages: 'index.html' and one per source (module header).
    'done' answers {relative path: text}."""

    def __init__(self):
        I_OutputVisitor.__init__(self)
        self.root       = None
        self.name_list  = []           # every measure any source carries
        self.row_list   = []           # index rows
        self.total_db   = {}           # measure name -> [covered, total]
        self.page_db    = {}           # relative path -> text
        self.summary    = None
        self.cell_db    = {}           # measure name -> (c, t) of the source
        self.point_db   = {}           # line -> [text]
        self.run_db     = {}           # line -> run names
        self.covered_set = self.executable_set = frozenset()

    def header(self, root, summary_list):
        """RETURN: None. The root, and the measure columns the index
        will have."""
        self.root      = root
        self.name_list = sorted({name for summary in summary_list
                                 for name in summary.measure_db})
        self.total_db  = {name: [0, 0] for name in ["lines"] + self.name_list}

    def source_open(self, summary):
        """RETURN: None. A source begins; its page collects."""
        self.summary  = summary
        self.cell_db  = {}
        self.point_db = {}
        self.run_db   = {}

    def lines(self, executable, covered, uncovered):
        """RETURN: None. The sets the page colours by."""
        self.executable_set = {n for b, e in executable for n in range(b, e)}
        self.covered_set    = {n for b, e in covered    for n in range(b, e)}

    def measure(self, measure, entry):
        """RETURN: None. A decision point reads 'TAG taken/total', a
        named point 'TAG name' ('(not)' where it was not covered); the
        source's summary cell is the measure's own. A measure of
        another shape is declared unrendered."""
        self.cell_db[measure.name] = measure_summary(measure.name, entry)
        for point in entry:
            if len(point) == 3 and not measure.named_f:
                line, mask, total = point
                text = "%s %i/%i" % (measure.tag, bin(mask).count("1"), total)
            elif len(point) == 4 and measure.named_f:
                line, name, covered, _ = point
                text = "%s %s%s" % (measure.tag, name, "" if covered else " (not)")
            else:
                del self.cell_db[measure.name]
                return self.unrendered(measure)
            self.point_db.setdefault(line, []).append(text)

    def who_ran(self, by_reference):
        """RETURN: None. Per covered line, the runs that executed it."""
        for name_tuple, span_tuple in by_reference:
            for begin, end in span_tuple:
                for line in range(begin, end):
                    self.run_db[line] = name_tuple

    def source_close(self, summary):
        """RETURN: None. The index row and the source's page."""
        covered_n = line_count(summary.covered)
        total_n   = line_count(summary.executable)
        self.total_db["lines"][0] += covered_n
        self.total_db["lines"][1] += total_n
        cell_list = ["<td><a href=\"%s\">%s</a></td>"
                     % (_e(page_path(summary.source)), _e(summary.source)),
                     "<td class=\"n\">%i/%i</td>" % (covered_n, total_n),
                     "<td class=\"n\">%s</td>" % percent(covered_n, total_n)]
        for name in self.name_list:
            pair = self.cell_db.get(name)
            if pair is None:
                cell_list += ["<td class=\"n\">-</td>", "<td class=\"n\">-</td>"]
                continue
            c, t = pair
            self.total_db[name][0] += c; self.total_db[name][1] += t
            cell_list += ["<td class=\"n\">%i/%i</td>" % (c, t),
                          "<td class=\"n\">%s</td>" % percent(c, t)]
        self.row_list.append("<tr>%s</tr>" % "".join(cell_list))
        self.page_db[page_path(summary.source)] = self._source_page(
            summary, covered_n, total_n)

    def _source_page(self, summary, covered_n, total_n):
        """RETURN: str, the page of one source."""
        text_list, note = None, ""
        if self.root is not None:
            path = os.path.join(self.root, *summary.source.split("/"))
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text_list = handle.read().split("\n")
                if text_list and text_list[-1] == "": text_list.pop()
            except OSError:
                note = ("<p class=\"note\">the source file was not found "
                        "under the root; the lines stand without their "
                        "text</p>")
        else:
            note = ("<p class=\"note\">the output names no root; the lines "
                    "stand without their text</p>")
        last = max([len(text_list or ()), max(self.executable_set, default=0),
                    max(self.point_db, default=0)])
        up   = "../" * summary.source.count("/")
        head = "lines %i/%i (%s)" % (covered_n, total_n, percent(covered_n, total_n))
        for name in sorted(self.cell_db):
            c, t = self.cell_db[name]
            head += "; %s %i/%i (%s)" % (HEAD_DB.get(name, name), c, t, percent(c, t))
        line_list = ["<p><a href=\"%sindex.html\">index</a></p>" % up,
                     "<h1>%s</h1>" % _e(summary.source),
                     "<p>%s</p>" % head]
        if note: line_list.append(note)
        line_list.append("<table class=\"src\">")
        for number in range(1, last + 1):
            if number in self.covered_set:      cls = "cov"
            elif number in self.executable_set: cls = "unc"
            else:                               cls = "non"
            text = text_list[number - 1] if text_list is not None \
                   and number <= len(text_list) else ""
            line_list.append(
                "<tr class=\"%s\"><td class=\"ln\">%i</td><td class=\"txt\">%s"
                "</td><td class=\"pts\">%s</td><td class=\"runs\">%s</td></tr>"
                % (cls, number, _e(text) or " ",
                   _e(", ".join(self.point_db.get(number, ()))),
                   _e(", ".join(self.run_db.get(number, ())))))
        line_list.append("</table>")
        return _page(summary.source, "\n".join(line_list) + "\n")

    def done(self):
        """RETURN: dict, relative path -> page text, 'index.html' among
        them -- with a paragraph naming any measure not rendered."""
        head = ["source", "lines", "%"]
        for name in self.name_list: head += [HEAD_DB.get(name, name), "%"]
        line_list = ["<h1>Coverage</h1>"]
        if self.root is not None:
            line_list.append("<p>root: <code>%s</code></p>" % _e(self.root))
        if self.unrendered_set:
            line_list.append("<p class=\"note\">not rendered by %s: %s</p>"
                             % (NAME, _e(", ".join(sorted(self.unrendered_set)))))
        line_list.append("<table>")
        line_list.append("<tr>%s</tr>" % "".join("<th>%s</th>" % _e(h) for h in head))
        line_list += self.row_list
        foot = ["<th>all</th>"]
        for name in ["lines"] + self.name_list:
            pair = self.total_db[name]
            foot += ["<th class=\"n\">%i/%i</th>" % tuple(pair),
                     "<th class=\"n\">%s</th>" % percent(*pair)]
        line_list.append("<tr>%s</tr>" % "".join(foot))
        line_list.append("</table>")
        self.page_db["index.html"] = _page("Coverage", "\n".join(line_list) + "\n")
        return self.page_db


def _build(root, summary_list, found, out_dir):
    """RETURN: str, the closing line: where 'index.html' stands."""
    page_db = walk(root, summary_list, HtmlVisitor())
    for relative, text in page_db.items():
        path = os.path.join(out_dir, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle: handle.write(text)
    return "COVERAGE PAGES: %s -- %i source file(s)" % (
        os.path.join(out_dir, "index.html"), len(summary_list))


def main(argv=None, write=None):
    """RETURN: E_ExitCode (E-1), as '_face.many_files_main'."""
    return many_files_main(NAME, USAGE, HELP, _build, "html", argv, write)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
