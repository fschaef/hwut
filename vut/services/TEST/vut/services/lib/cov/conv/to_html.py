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

from   vut.engine.coverage.api      import (DEFAULT_DIRECTORY_NAME,
                                            OutputRefused, root_of)
from   vut.services._exit           import E_ExitCode
from   vut.services.lib.cov.summary import (line_count, measure_summary,
                                            percent, summaries_of)

NAME  = "hwut.cov.conv.to_html"
USAGE = "usage: %s [DIRECTORY] [-o OUTDIR] | --help" % NAME
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()

#  The column heads, by measure name; a measure registered later shows
#  under its name.
HEAD_DB = {"branch": "branch arms", "function": "functions",
           "mcdc": "mc/dc conditions", "toggle": "toggle bits",
           "cover": "cover points"}
TAG_DB  = {"branch": "BR", "function": "FN", "mcdc": "MC",
           "toggle": "TG", "cover": "CP"}

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


def _measure_names(summary_list):
    """RETURN: list of str, every measure name any source carries, in
    name order."""
    return sorted({name for summary in summary_list
                   for name in summary.measure_db})


def _source_page_path(source):
    """RETURN: str, the page of 'source', relative to OUTDIR, with '/'
    between."""
    return source + ".html"


def index_html(root, summary_list):
    """RETURN: str, 'index.html': the table over every source."""
    name_list = _measure_names(summary_list)
    line_list = ["<h1>Coverage</h1>"]
    if root is not None:
        line_list.append("<p>root: <code>%s</code></p>" % _e(root))
    line_list.append("<table>")
    head = ["source", "lines", "%"]
    for name in name_list: head += [HEAD_DB.get(name, name), "%"]
    line_list.append("<tr>%s</tr>"
                     % "".join("<th>%s</th>" % _e(h) for h in head))
    total_db = {"lines": [0, 0]}
    for summary in summary_list:
        covered_n = line_count(summary.covered)
        total_n   = line_count(summary.executable)
        total_db["lines"][0] += covered_n; total_db["lines"][1] += total_n
        cell_list = ["<td><a href=\"%s\">%s</a></td>"
                     % (_e(_source_page_path(summary.source)),
                        _e(summary.source)),
                     "<td class=\"n\">%i/%i</td>" % (covered_n, total_n),
                     "<td class=\"n\">%s</td>" % percent(covered_n, total_n)]
        for name in name_list:
            entry = summary.measure_db.get(name)
            if entry is None:
                cell_list += ["<td class=\"n\">-</td>", "<td class=\"n\">-</td>"]
                continue
            c, t = measure_summary(name, entry)
            pair = total_db.setdefault(name, [0, 0])
            pair[0] += c; pair[1] += t
            cell_list += ["<td class=\"n\">%i/%i</td>" % (c, t),
                          "<td class=\"n\">%s</td>" % percent(c, t)]
        line_list.append("<tr>%s</tr>" % "".join(cell_list))
    foot = ["<th>all</th>", "<th class=\"n\">%i/%i</th>" % tuple(total_db["lines"]),
            "<th class=\"n\">%s</th>" % percent(*total_db["lines"])]
    for name in name_list:
        pair = total_db.get(name, [0, 0])
        foot += ["<th class=\"n\">%i/%i</th>" % tuple(pair),
                 "<th class=\"n\">%s</th>" % percent(*pair)]
    line_list.append("<tr>%s</tr>" % "".join(foot))
    line_list.append("</table>")
    return _page("Coverage", "\n".join(line_list) + "\n")


def _points_of_line(summary):
    """RETURN: dict, line -> list of str, the points of each line as a
    reader reads them: 'BR 1/2', 'FN main', 'TG clk', 'MC 2/3'."""
    out = {}
    for name, entry in sorted(summary.measure_db.items()):
        tag = TAG_DB.get(name, name)
        for point in entry:
            if len(point) == 3:
                line, mask, total = point
                text = "%s %i/%i" % (tag, bin(mask).count("1"), total)
            else:
                line, point_name, covered, total = point
                text = "%s %s%s" % (tag, point_name,
                                    "" if covered else " (not)")
            out.setdefault(line, []).append(text)
    return out


def _runs_of_line(summary):
    """RETURN: dict, line -> tuple of str, the run names that executed
    each covered line."""
    out = {}
    for name_tuple, span_tuple in summary.by_reference:
        for begin, end in span_tuple:
            for line in range(begin, end):
                out[line] = name_tuple
    return out


def source_html(root, summary):
    """RETURN: str, the page of one source."""
    text_list, note = None, ""
    if root is not None:
        path = os.path.join(root, *summary.source.split("/"))
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text_list = handle.read().split("\n")
            if text_list and text_list[-1] == "": text_list.pop()
        except OSError:
            note = ("<p class=\"note\">the source file was not found under "
                    "the root; the lines stand without their text</p>")
    else:
        note = ("<p class=\"note\">the output names no root; the lines "
                "stand without their text</p>")
    executable_set = {line for begin, end in summary.executable
                      for line in range(begin, end)}
    covered_set    = {line for begin, end in summary.covered
                      for line in range(begin, end)}
    point_db = _points_of_line(summary)
    run_db   = _runs_of_line(summary)
    last = max([len(text_list or ()), max(executable_set, default=0),
                max(point_db, default=0)])
    depth = summary.source.count("/")
    up    = "../" * depth
    covered_n, total_n = line_count(summary.covered), line_count(summary.executable)
    line_list = ["<p><a href=\"%sindex.html\">index</a></p>" % up,
                 "<h1>%s</h1>" % _e(summary.source),
                 "<p>lines %i/%i (%s)%s</p>"
                 % (covered_n, total_n, percent(covered_n, total_n),
                    "".join("; %s %i/%i (%s)"
                            % (HEAD_DB.get(name, name), c, t, percent(c, t))
                            for name, entry in sorted(summary.measure_db.items())
                            for c, t in (measure_summary(name, entry),))),
                 "<table class=\"src\">"]
    if note: line_list.insert(3, note)
    for number in range(1, last + 1):
        if number in covered_set:      cls = "cov"
        elif number in executable_set: cls = "unc"
        else:                          cls = "non"
        text = text_list[number - 1] if text_list is not None \
               and number <= len(text_list) else ""
        line_list.append(
            "<tr class=\"%s\"><td class=\"ln\">%i</td><td class=\"txt\">%s</td>"
            "<td class=\"pts\">%s</td><td class=\"runs\">%s</td></tr>"
            % (cls, number, _e(text) or " ",
               _e(", ".join(point_db.get(number, ()))),
               _e(", ".join(run_db.get(number, ())))))
    line_list.append("</table>")
    return _page(summary.source, "\n".join(line_list) + "\n")


def write_pages(root, summary_list, out_dir):
    """
    RETURN: str, the path of 'index.html'.

    Raises OSError where a page cannot be written.
    """
    os.makedirs(out_dir, exist_ok=True)
    index = os.path.join(out_dir, "index.html")
    with open(index, "w", encoding="utf-8") as handle:
        handle.write(index_html(root, summary_list))
    for summary in summary_list:
        path = os.path.join(out_dir,
                            *_source_page_path(summary.source).split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source_html(root, summary))
    return index


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode (E-1): OK with the pages written, FAULT where the
            output directory cannot be read or OUTDIR not written,
            REFUSED where the command line cannot be read.

    'write' takes one line of text; 'print' where none is given.
    """
    if write is None: write = print
    if argv is None:  argv = sys.argv[1:]

    if "--help" in argv or "-h" in argv:
        write(HELP)
        return E_ExitCode.OK

    directory_list, target = [], None
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in ("-o", "--output"):
            if i + 1 >= len(argv) or target is not None:
                write("REFUSED: '%s' takes one OUTDIR, once" % word)
                write(USAGE)
                return E_ExitCode.REFUSED
            target = argv[i + 1]; i += 2
        elif word.startswith("-"):
            write("REFUSED: unknown option '%s'" % word); write(USAGE)
            return E_ExitCode.REFUSED
        else:
            directory_list.append(word); i += 1
    if len(directory_list) > 1:
        write("REFUSED: %s takes at most one DIRECTORY" % NAME)
        write(USAGE)
        return E_ExitCode.REFUSED
    directory = directory_list[0] if directory_list \
                else os.path.join(os.getcwd(), DEFAULT_DIRECTORY_NAME)
    if not os.path.isdir(directory):
        write("FAULT: '%s' is no directory" % directory)
        return E_ExitCode.FAULT
    if root_of(directory) is None:
        write("FAULT: '%s' carries no marker of a coverage run; name "
              "the '-o' directory of 'hwut.cov.run'" % directory)
        return E_ExitCode.FAULT
    if target is None: target = os.path.join(directory, "html")

    try:
        root, summary_list = summaries_of(directory)
        index = write_pages(root, summary_list, target)
    except OutputRefused as refusal:
        write("FAULT: %s" % refusal)
        return E_ExitCode.FAULT
    except OSError as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT
    write("COVERAGE PAGES: %s -- %i source file(s)" % (index, len(summary_list)))
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
