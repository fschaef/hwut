"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report' COMMAND LINE -- what the RESULT DATABASES
         hold, rendered for somebody else.

    hwut.report [<wish>] [--format=<name>] [--out=<file>]
                [--width=<n>] [--directory=<path>]

IT READS THE BOOKS, NOT A RUN. A report may be asked of a run that
happened yesterday, and only 'GOOD/result_db.json' remembers it. So
this face explores the tree for its SHAPE -- which applications, which
choices, what they are called -- and asks each directory's book for the
VERDICT. A case the book has never seen is reported as never run,
which is a finding and not a fault.

FORMATS ('--format'):

    traditional  THE HWUT PAGE, and the default: a block per
                 directory, dot leaders to a right-aligned verdict,
                 then a summary whose directory column is
                 prefix-elided, then the failures listed once more.
    junit        the XML every CI ingests.
    tap          Test Anything Protocol, version 13.
    json         for whoever builds their own.

THE WIDTH IS THE TERMINAL'S. '--width' states it; otherwise COLUMNS,
otherwise the terminal's own, otherwise 80. Nothing here assumes a
constant: the page fills what it is given.

'[OK]' AND '[FAIL]' ARE RIGHT-ALIGNED TO ONE COLUMN, so the dot leader
runs two shorter for a failure and the verdicts stand in a line.

THE STAIN HAS NO JUnit WORD. JUnit knows failure, error and skipped; a
stained choice is none of them -- it was not run, and it did not fail.
'skipped' is the closest and is a lie of exactly the kind the stain
exists to forbid (E-11). So a stain is emitted as a FAILURE whose
message names it: CI goes red, which is true, and the message says why.

EXIT STATUS (E-1, services/_exit.py):
    0  the report was written; every case the wish selected stood
    1  a case the wish selected did not stand
    2  the command line cannot be read
    3  the command line reads, and selects nothing
______________________________________________________________________________
"""
import json
import os
import shutil
import sys
import xml.sax.saxutils as saxutils

from   vut.engine.bookkeeper.bookkeeper              import (NO_CHOICE_KEY)
from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.exploration          import selection
from   vut.services.labels                           import view_at
from   vut.services.labels._file                     import LabelFileError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                     import (RootConfMissing)
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish,
                                                             with_targets)
from   ._core                                        import usage_line
from   ._exit                                        import E_ExitCode

FORMAT_TUPLE   = ("traditional", "junit", "tap", "json")
WIDTH_DEFAULT  = 80
WIDTH_MINIMUM  = 40

USAGE = usage_line("hwut.report",
                   ("[<wish>]", "[<file-glob> [choice-glob]...]",
                    "[--format=<name>]", "[--out=<file>]",
                    "[--width=<n>]", "[--directory=<path>]"))

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


class CRow:
    """ONE CASE, as the databases remember it.

    'verdict' is True, False, or None where the book never saw it.
    'report'  is the E_TestRunResult word, '' where none stands.
    'stain'   is the stain dict, None where the choice is clean.
    """
    __slots__ = ("directory", "source_file", "choice", "verdict",
                 "report", "when", "stain", "title")

    def __init__(self, directory, source_file, choice, verdict, report,
                 when, stain, title=""):
        self.title       = title or ""
        self.directory   = directory
        self.source_file = source_file
        self.choice      = choice
        self.verdict     = verdict
        self.report      = report
        self.when        = when
        self.stain       = stain

    @property
    def name(self):
        """RETURN: str, the case as an author names it -- the target
        form: the file, or the file and the choice."""
        return self.source_file if self.choice is None \
               else "%s %s" % (self.source_file, self.choice)

    @property
    def good_f(self):
        """RETURN: bool, True where the book says it stood."""
        return self.verdict is True

    @property
    def word(self):
        """RETURN: str, the reason it did not stand: the stain first,
        then the recorded report, then the plain absence."""
        if self.stain is not None:   return "unstable"
        if self.verdict is None:     return "never run"
        return self.report or "failed"


def width_of(stated):
    """
    RETURN: int, the page width: what was stated, else COLUMNS, else
            the terminal's own, else 80 -- and never below 40, at
            which point the dot leader has nothing left to give.
    """
    if stated is not None: return max(stated, WIDTH_MINIMUM)
    text = os.environ.get("COLUMNS", "")
    if text.isdigit() and int(text) > 0:
        return max(int(text), WIDTH_MINIMUM)
    try:    got = shutil.get_terminal_size((WIDTH_DEFAULT, 24)).columns
    except Exception: got = WIDTH_DEFAULT
    return max(got or WIDTH_DEFAULT, WIDTH_MINIMUM)


def directory_title(directory):
    """
    RETURN: str, the directory's own title -- the FIRST line of its
            'hwut-info.dat'.
            '', where the file is absent or says nothing.

    The file's second line underlines the first; everything below is
    the directory's own business and is not a title.
    """
    try:
        with open(os.path.join(directory, "hwut-info.dat"), "r",
                  encoding="utf-8") as file_handle:
            for line in file_handle:
                if line.strip(): return line.strip()
    except OSError:
        pass
    return ""


def row_list_of(root, wish):
    """
    RETURN: list[(str, str, list[CRow])] -- per directory, in walk
            order: its relative path, its title, and one CRow per case
            the wish selected.

    A directory the wish empties is kept with an EMPTY row list: a
    report on a tree half of which was never asked for should still
    say which halves those are.
    """
    entry_list = []
    #  ONE ACTION, ONE PLACE ('exploration/selection.py'). The
    #  Bookkeeper this face reads the book from is the one THE
    #  SELECTION MADE -- two over one directory would be two answers
    #  to one question.
    found  = selection.of_tree(root, wish, view_at(root), base_f=True)
    by_dir = {}
    for entry in found.case_list:
        by_dir.setdefault(entry.directory, []).append(entry.case)
    for directory, result in found.result_db.items():
        whole      = os.path.join(root, directory)
        bookkeeper = found.bookkeeper_db[directory]
        book       = bookkeeper.book()
        app_db     = {app.source_file: app for app in result.app_set}
        row_list   = []
        for case in by_dir.get(directory, ()):
            test   = case.source_file
            key    = NO_CHOICE_KEY if case.choice is None else case.choice
            entry  = book.get(test, {}).get("choices", {}).get(key, {})
            run    = entry.get("operations", {}).get("Run", {})
            row_list.append(CRow(
                directory   = directory,
                source_file = case.source_file,
                choice      = case.choice,
                verdict     = run.get("verdict"),
                report      = run.get("report", ""),
                when        = run.get("when", ""),
                stain       = entry.get("stain"),
                title       = getattr(app_db.get(case.source_file),
                                      "title", "") or ""))
        entry_list.append((directory, directory_title(whole), row_list))
    return entry_list


#  ---------------------------------------------------------------------
#  THE TRADITIONAL PAGE
#  ---------------------------------------------------------------------
def elided(previous, current):
    """
    RETURN: str, 'current' with the leading path it SHARES with
            'previous' replaced by dots of that same length --
            'engine/bookkeeper/TEST' then '....../compare/TEST', the
            six dots being 'engine'.

    The shared part ends at a path separator: two directories sharing
    'engi' share nothing, and eliding four characters would say they
    did.
    """
    if not previous: return current
    a, b  = previous.split("/"), current.split("/")
    same  = 0
    while same < len(a) and same < len(b) and a[same] == b[same]:
        same += 1
    if same == 0: return current
    prefix = "/".join(a[:same])
    return "." * len(prefix) + current[len(prefix):]


def leader_line(left, verdict_text, width, indent):
    """
    RETURN: str, 'left', dots, and 'verdict_text' ENDING AT 'width'.

    The verdict is right-aligned to one column, so '[FAIL]' takes two
    dots more than '[OK]' and the verdicts stand in a line. Where the
    left side would leave no room, one blank separates them and the
    line simply runs long: truncating a test's name to keep a rule is
    the wrong trade.
    """
    head = " " * indent + left
    room = width - len(head) - len(verdict_text)
    if room < 1: return "%s %s" % (head, verdict_text)
    return "%s%s%s" % (head, "." * room, verdict_text)


def traditional_line_tuple(entry_list, width):
    """
    YIELD: [0] str  one line of the HWUT page: a block per directory,
                    then the summary, then the failures once more.
    """
    rule_equals = "=" * width
    rule_dashes = "-" * width
    for directory, title, row_list in entry_list:
        yield rule_equals
        yield ""
        if title:
            yield title.center(width).rstrip()
            yield ""
        stamp = _stamp_of(row_list)
        yield "%s%s%s" % (directory,
                          " " * max(1, width - len(directory)
                                       - len(stamp)),
                          stamp)
        yield rule_dashes
        yield ""
        previous_file = None
        for row in row_list:
            if row.source_file != previous_file:
                if previous_file is not None: yield ""
                yield " * %s:" % _title_of(row)
                yield ""
                previous_file = row.source_file
                shown         = row.source_file
            else:
                shown = " " * len(row.source_file)
            #  ONE BLANK before the leader: the dots never touch the
            #  name, whether a choice stands or not.
            left = (shown if row.choice is None
                    else "%s %s" % (shown, row.choice)) + " "
            yield leader_line(left,
                              "[OK]" if row.good_f else "[FAIL]",
                              width, 8)
        if not row_list:
            yield "    (no case selected here)"
        yield ""

    yield rule_equals
    yield ""
    yield "SUMMARY:"
    yield ""
    yield "    Fails: N: Verdict:          Directory:"
    yield ""
    previous = ""
    for directory, _, row_list in entry_list:
        fail_n = sum(1 for row in row_list if not row.good_f)
        yield "    %6s %-4d %-8s %s" \
              % (fail_n if fail_n else "", len(row_list),
                 "[OK]" if not fail_n else "[FAIL]",
                 elided(previous, directory))
        previous = directory
    yield ""

    failure_list = [row for _, _, row_list in entry_list
                    for row in row_list if not row.good_f]
    if failure_list:
        yield rule_dashes
        yield ""
        yield "FAILURES:"
        yield ""
        for row in failure_list:
            yield "    %s: %s -- %s" % (row.directory, row.name,
                                        row.word)
        yield ""
    yield rule_dashes
    total_n = sum(len(row_list) for _, _, row_list in entry_list)
    tail    = "(%d test%s)" % (total_n, "" if total_n == 1 else "s")
    yield tail.rjust(width)
    yield ""
    yield rule_equals


def _title_of(row):
    """RETURN: str, the application's own title, as the author wrote
    it in the test header; the FILE NAME where none stands, so the
    block always has a heading."""
    return row.title or row.source_file


def _stamp_of(row_list):
    """
    RETURN: str, the most recent instant any row of the directory
            carries, as the page writes it ('2026y08m26d 17h16').
            '<no date>', where no row was ever run -- ABSENCE IS DATA,
            never a fabricated now.
    """
    when_list = [row.when for row in row_list if row.when]
    if not when_list: return "<no date>"
    newest = max(when_list)
    try:
        date, _, clock = newest.partition("T")
        year, month, day = date.split("-")
        hour, minute     = clock.split(":")[:2]
        return "%sy%sm%sd %sh%s" % (year, month, day, hour, minute)
    except ValueError:
        return newest


#  ---------------------------------------------------------------------
#  THE MACHINE FORMATS
#  ---------------------------------------------------------------------
def junit_line_tuple(entry_list):
    """
    YIELD: [0] str  one line of a JUnit XML document: '<testsuite>'
                    per directory, '<testcase>' per case.

    A STAIN IS A FAILURE, not a 'skipped': it was not run and it did
    not fail, and JUnit has no third word. Skipping it would tell CI
    the run was fine, which is the false testimony the stain exists to
    punish.
    """
    total_n = sum(len(row_list) for _, _, row_list in entry_list)
    fail_n  = sum(1 for _, _, row_list in entry_list
                  for row in row_list if not row.good_f)
    yield '<?xml version="1.0" encoding="UTF-8"?>'
    yield '<testsuites tests="%d" failures="%d">' % (total_n, fail_n)
    for directory, title, row_list in entry_list:
        here_fail = sum(1 for row in row_list if not row.good_f)
        yield '  <testsuite name=%s tests="%d" failures="%d">' \
              % (saxutils.quoteattr(directory), len(row_list), here_fail)
        for row in row_list:
            attribute = 'classname=%s name=%s' \
                        % (saxutils.quoteattr(directory),
                           saxutils.quoteattr(row.name))
            if row.good_f:
                yield '    <testcase %s/>' % attribute
                continue
            yield '    <testcase %s>' % attribute
            yield '      <failure type=%s message=%s/>' \
                  % (saxutils.quoteattr(row.word),
                     saxutils.quoteattr(_message_of(row)))
            yield '    </testcase>'
        yield '  </testsuite>'
    yield '</testsuites>'


def _message_of(row):
    """RETURN: str, why the case did not stand, in one sentence."""
    if row.stain is not None:
        return ("the choice bears a STAIN: it switched results over %d "
                "repeat(s) and is not run until proven steady"
                % row.stain.get("repeat_n", 0))
    if row.verdict is None:
        return "the result database holds no run of this case"
    return "the run reported '%s'" % (row.report or "failure")


def tap_line_tuple(entry_list):
    """
    YIELD: [0] str  one line of a TAP version 13 stream: the plan
                    first, one 'ok'/'not ok' per case, the reason as a
                    YAML block where there is one.
    """
    row_list = [row for _, _, rows in entry_list for row in rows]
    yield "TAP version 13"
    yield "1..%d" % len(row_list)
    for index, row in enumerate(row_list, start=1):
        name = "%s: %s" % (row.directory, row.name)
        if row.good_f:
            yield "ok %d - %s" % (index, name)
            continue
        yield "not ok %d - %s" % (index, name)
        yield "  ---"
        yield "  reason: %s" % row.word
        yield "  message: %s" % _message_of(row)
        yield "  ..."


def json_text_of(entry_list):
    """
    RETURN: str, the whole report as one JSON document -- directories,
            their cases, and each case's verdict, reason and instant.

    'verdict' is 'true', 'false' or 'null'; NULL IS NEVER RUN, and
    never a stand-in for a failure.
    """
    document = {"directory_list": []}
    for directory, title, row_list in entry_list:
        document["directory_list"].append({
            "directory": directory,
            "title":     title,
            "case_list": [{"name":    row.name,
                           "file":    row.source_file,
                           "choice":  row.choice,
                           "verdict": row.verdict,
                           "reason":  None if row.good_f else row.word,
                           "stained": row.stain is not None,
                           "when":    row.when or None}
                          for row in row_list]})
    document["test_n"] = sum(len(r) for _, _, r in entry_list)
    document["fail_n"] = sum(1 for _, _, r in entry_list
                             for row in r if not row.good_f)
    return json.dumps(document, indent=2, sort_keys=True)


def line_tuple_of(entry_list, format_name, width):
    """
    YIELD: [0] str  one line of the report in the named format.
    """
    if   format_name == "traditional":
        yield from traditional_line_tuple(entry_list, width)
    elif format_name == "junit": yield from junit_line_tuple(entry_list)
    elif format_name == "tap":   yield from tap_line_tuple(entry_list)
    else:                        yield from json_text_of(
                                             entry_list).splitlines()


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where every selected
            case stood, FAULT where one did not, REFUSED where the
            command line cannot be read, EMPTY where it selects
            nothing.

    '--out' writes the report to a file INSTEAD of stdout, so a CI
    step may ask for XML and still read the face's own faults on the
    stream it watches.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED

    directory   = "."
    format_name = "traditional"
    out_name    = None
    width       = None
    unknown     = []
    word_list = []
    for argument in rest_list:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument.startswith("--out="):
            out_name = argument[len("--out="):]
        elif argument.startswith("--format="):
            format_name = argument[len("--format="):]
            if format_name not in FORMAT_TUPLE:
                write("REFUSED: '--format' takes one of %s, not '%s'"
                      % (", ".join(FORMAT_TUPLE), format_name))
                write(USAGE)
                return E_ExitCode.REFUSED
        elif argument.startswith("--width="):
            text = argument[len("--width="):]
            if not text.isdigit() or int(text) < 1:
                write("REFUSED: '--width' takes a positive integer, "
                      "not '%s'" % text)
                write(USAGE)
                return E_ExitCode.REFUSED
            width = int(text)
        else:
            if argument.startswith("-"): unknown.append(argument)
            else:                        word_list.append(argument)
    if unknown:
        write("REFUSED: 'hwut.report' does not take: %s"
              % ", ".join(sorted(unknown)))
        write(USAGE)
        return E_ExitCode.REFUSED
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    wish = with_targets(wish, word_list)
    try:
        entry_list = row_list_of(os.path.abspath(directory), wish)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT

    if not any(row_list for _, _, row_list in entry_list):
        write("EMPTY: the wish selects no case in '%s'" % directory)
        return E_ExitCode.EMPTY

    line_list = list(line_tuple_of(entry_list, format_name,
                                   width_of(width)))
    if out_name is None:
        for line in line_list: write(line)
    else:
        try:
            with open(out_name, "w", encoding="utf-8") as file_handle:
                file_handle.write("\n".join(line_list) + "\n")
        except OSError as error:
            write("FAULT: '%s' cannot be written -- %s"
                  % (out_name, error))
            return E_ExitCode.FAULT
        write("written: %s (%s, %d line(s))"
              % (out_name, format_name, len(line_list)))

    fail_n = sum(1 for _, _, row_list in entry_list
                 for row in row_list if not row.good_f)
    return E_ExitCode.FAULT if fail_n else E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
