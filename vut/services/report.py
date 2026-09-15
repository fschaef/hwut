"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report' COMMAND LINE -- what the RESULT DATABASES
         hold, rendered for somebody else.

IT READS THE BOOKS, NOT A RUN. A report may be asked of a run that
happened yesterday, and only 'GOOD/book.csv' remembers it. So
this face explores the tree for its SHAPE -- which applications, which
choices, what they are called -- and asks each directory's book for the
VERDICT. A case the book has never seen is reported as never run,
which is a finding and not a fault.

FORMATS ('--format'):

    traditional  THE HWUT PAGE, and the default: a block per
                 directory, dot leaders to a right-aligned verdict,
                 then a summary whose directory column is
                 prefix-elided. A failure is said ONCE, where it
                 happened (E-70).
    junit        the XML every CI ingests.
    tap          Test Anything Protocol, version 13.
    json         for whoever builds their own.

THE WIDTH IS THE TERMINAL'S. '--width' states it; otherwise COLUMNS,
otherwise the terminal's own, otherwise 80. Nothing here assumes a
constant: the page fills what it is given.

'[OK]' AND '[FAIL]' ARE RIGHT-ALIGNED TO ONE COLUMN, so the dot leader
runs two shorter for a failure and the verdicts stand in a line. That
column stops VERDICT_MARGIN short of the rule: a label butted against
the border reads as if it had been cut off.

IT COLOURS, on a terminal: the title block on orange, '[OK]' on green,
'[FAIL]' on red -- the HWUT page as it always looked. ONLY the
traditional format, and only to a tty: '--plain' says no, '--color'
says yes outright, '--out' implies no, and a machine format never
carries an escape. The escapes
are laid on AFTER the layout is measured, so a coloured page and a
plain one break their lines in exactly the same columns.

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
import itertools
import shutil
import sys
import xml.sax.saxutils as saxutils

from   vut.engine.bookkeeper.api                     import E_TestVerdict
from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.exploration          import selection
from   vut.services.lib.labels                           import view_at
from   vut.services.lib.labels._file                     import LabelFileError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                     import (RootConfMissing)
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish,
                                                             with_targets)
from   ._core                                        import usage_line
from   ._exit                                        import E_ExitCode
from   ._target                                      import entered
from   vut.services.lib.cmdline import did_you_mean, option_tuple

FORMAT_TUPLE   = ("traditional", "junit", "tap", "json")
WIDTH_DEFAULT  = 80
WIDTH_MINIMUM  = 40

USAGE = usage_line("usage: hwut.report",
                   ("[<wish>]", "[<file-glob> [choice-glob]...]",
                    "[--format=<name>]", "[--out=<file>]",
                    "[--width=<n>]", "[--plain|--color]",
                    "[--directory=<path>]"))

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


class CRow:
    """ONE CASE, as the databases remember it.

    'verdict' is an E_TestVerdict, or None where the book never saw it.
    'report'  is the E_TestRunResult word, '' where none stands --
              refined to a SHAPE ('grew', 'shrank', 'diverged') where
              this face could read both whole files (E-31).
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
        return self.verdict is not None and self.verdict.passed_f

    @property
    def word(self):
        """RETURN: str, the reason it did not stand: the stain first,
        then the recorded report, then the plain absence."""
        if self.stain is not None:   return "unstable"
        if self.verdict is None:     return "never run"
        if self.verdict is E_TestVerdict.ASPIRANT: return "aspirant"
        return self.report or "failed"


def _json_verdict(verdict):
    """
    RETURN: bool, True for PASS and False for FAIL -- what the JSON
                  format has always carried.
            str, "aspirant" for a choice the book knows and nobody
                 has accepted (B-14).
            None, where the book never saw the case.
    """
    if verdict is None:                     return None
    if verdict is E_TestVerdict.ASPIRANT:   return str(verdict)
    return verdict.passed_f


#  THE PAGE'S COLOURS, as the HWUT page wore them. Backgrounds, not
#  foregrounds: a verdict is a BADGE, and a badge is read at a glance
#  across a screenful of dots.
ANSI_RESET   = "\033[0m"
ANSI_TITLE   = "\033[30;48;5;208m"      # black on orange
ANSI_OK      = "\033[30;48;5;40m"       # black on green
ANSI_FAIL    = "\033[97;48;5;160m"      # white on red

#  How far short of the rule the verdict column stops.
VERDICT_MARGIN = 2

HEIGHT_DEFAULT = 24
HEIGHT_MINIMUM = 8


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


def painted(text, code, color_f):
    """
    RETURN: str, 'text' wrapped in the ANSI sequence 'code' and closed
            again, where 'color_f'; 'text' untouched otherwise.

            NEVER called before a line's width has been measured: the
            escapes are invisible to a terminal and four characters
            wide to 'len', so a layout computed over them would break
            in the wrong column.
    """
    if not color_f: return text
    return "%s%s%s" % (code, text, ANSI_RESET)


def color_wanted_f(plain_f, out_name, stream, color_said_f=False):
    """
    RETURN: bool, True where the page should carry ANSI colour: not
            '--plain', not going to a file ('--out'), the stream is a
            terminal, and the console will render the escapes.
            '--color' says it outright, for a pipe that will be looked
            at anyway -- and for the suite, which drives every face
            through a pipe and could otherwise never see this page.

            False otherwise -- a report read by a machine, redirected
            into a file, or piped, is plain.
    """
    if plain_f:        return False
    if color_said_f:   return True
    if out_name is not None: return False
    if not getattr(stream, "isatty", lambda: False)(): return False
    return _ansi_enabled()


def _ansi_enabled():
    """
    RETURN: True,  the console renders ANSI escapes -- on Windows only
                   after virtual-terminal processing is switched on for
                   the standard output handle, which the console does
                   not do by itself.
            False, it could not be switched on.
    """
    if sys.platform != "win32": return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle   = kernel32.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
        mode     = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def height_of(stated=None):
    """
    RETURN: int, the page height in LINES: what was stated, else LINES,
            else the terminal's own, else 24 -- and never below 8, at
            which point a paged list has no room left for its content.

            Asked exactly as 'width_of' asks, so a face never reads the
            terminal two different ways.
    """
    if stated is not None: return max(stated, HEIGHT_MINIMUM)
    text = os.environ.get("LINES", "")
    if text.isdigit() and int(text) > 0:
        return max(int(text), HEIGHT_MINIMUM)
    try:    got = shutil.get_terminal_size((WIDTH_DEFAULT, HEIGHT_DEFAULT)).lines
    except Exception: got = HEIGHT_DEFAULT
    return max(got or HEIGHT_DEFAULT, HEIGHT_MINIMUM)


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


def _observed_instant(bookkeeper, case):
    """
    RETURN: str, WHEN THIS MACHINE LAST SAW that case run, as the page
            writes an instant ('2026-08-26T17:16:04Z'); '' where this
            machine has not observed it.

    THE INSTANT IS AN OBSERVATION (E-22): the book holds decisions, and
    a report read on another machine, or after 'TMP/' was cleared,
    dates nothing -- which is the truth about what THIS machine knows,
    not a gap.
    """
    from datetime import datetime, timezone
    from vut.engine.bookkeeper.api import (ObservationDb,
                                                   ObservationFault)
    try:
        observed = ObservationDb(bookkeeper.directory).get(
                       case.source_file, case.choice, "Run")
    except (ObservationFault, OSError):
        return ""
    if observed is None or observed.when is None: return ""
    return datetime.fromtimestamp(int(observed.when), tz=timezone.utc) \
                   .strftime("%Y-%m-%dT%H:%M:%SZ")


def row_list_of(root, wish):
    """
    RETURN: list[(str, str, list[CRow])] -- per directory, in walk
            order: its relative path, its title, and one CRow per case
            the wish selected.

    THE SNAPSHOT FORM of 'entry_stream_of', for the machine formats,
    which count and total before they can write their first line.
    """
    return list(entry_stream_of(root, wish))


def _tallied(entry_stream, fail_box):
    """
    YIELD: [0..2] one entry of 'entry_stream', unchanged.

    'fail_box[0]' rises by the failing rows of every entry that passes,
    so the caller has the count once the stream is spent. A streamed
    page is read once; walking it again to count would mean holding it
    all, which is the thing streaming exists to avoid.
    """
    for entry in entry_stream:
        fail_box[0] += sum(1 for row in entry[2] if not row.good_f)
        yield entry


def entry_stream_of(root, wish):
    """
    YIELD: [0] str            one directory, relative to 'root', walk
                              order.
           [1] str            its title.
           [2] list[CRow]     one row per case the wish selected there.

    ONE DIRECTORY AT A TIME, the moment it is known. Exploring a
    directory interviews its applications -- subprocesses -- so on a
    large tree the eager form leaves the screen empty for minutes and
    then fills it at once; this one puts each block up as it is
    finished.

    A directory the wish empties is yielded with an EMPTY row list: a
    report on a tree half of which was never asked for should still
    say which halves those are.
    """
    #  ONE ACTION, ONE PLACE ('exploration/selection.py'). The
    #  Bookkeeper this face reads the book from is the one THE
    #  SELECTION MADE -- two over one directory would be two answers
    #  to one question.
    for directory, result, bookkeeper, selected_list in \
            selection.of_tree_stream(root, wish, view_at(root),
                                     base_f=True):
        whole      = os.path.join(root, directory)
        app_db     = {app.source_file: app for app in result.app_set}
        row_list   = []
        for case in (entry.case for entry in selected_list):
            test   = case.source_file
            #  THROUGH THE DOOR, SHAPE-BLIND: 'result()' and 'stain()'
            #  answer the two questions a row asks; how the book files
            #  them is the bookkeeper's, and may change under this face
            #  without it noticing.
            run    = bookkeeper.result(test, case.choice) or {}
            report = run.get("report", "")
            #  THE SHAPE, HERE AND NOT IN THE RUN (E-31): this face
            #  reads whole files, with no producer to starve and no
            #  early-abort economy to keep. Asked only of a difference
            #  the run already found, and only of 'stdout' -- the one
            #  subject every test has.
            if report == "not-equivalent-with-nominal":
                report = bookkeeper.shape_of(test, case.choice, "stdout")
            row_list.append(CRow(
                directory   = directory,
                source_file = case.source_file,
                choice      = case.choice,
                verdict     = run.get("verdict"),
                report      = report,
                when        = _observed_instant(bookkeeper, case),
                stain       = bookkeeper.stain(test, case.choice),
                title       = getattr(app_db.get(case.source_file),
                                      "title", "") or ""))
        yield (directory, directory_title(whole), row_list)


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


def leader_line(left, verdict_text, width, indent=4, shown=None):
    """
    RETURN: str, 'left', dots, and 'verdict_text' ending VERDICT_MARGIN
            columns short of 'width'.

    The verdict is right-aligned to one column, so '[FAIL]' takes two
    dots more than '[OK]' and the verdicts stand in a line. That column
    stops short of the rule: a label butted against the border reads as
    if it had been cut off. Where the left side would leave no room,
    one blank separates them and the line simply runs long: truncating
    a test's name to keep a rule is the wrong trade.

    'shown' is what is PRINTED where the verdict stands -- the same
    text wearing its colour. The layout is measured on 'verdict_text',
    never on 'shown', because escapes have width to 'len' and none on
    a screen.
    """
    head = " " * indent + left
    room = width - len(head) - len(verdict_text) - VERDICT_MARGIN
    if shown is None: shown = verdict_text
    if room < 1: return "%s %s" % (head, shown)
    return "%s%s%s" % (head, "." * room, shown)


def traditional_line_tuple(entry_list, width, color_f=False):
    """
    YIELD: [0] str  one line of the HWUT page: a block per directory,
                    then the summary. A failure is said ONCE, in its
                    own block (E-70).

    IT STREAMS. 'entry_list' may be a GENERATOR, and a directory's
    block is yielded before the next directory has been explored, so a
    face writing as it reads puts each block on the screen the moment
    it is known. Only the SUMMARY needs the whole tree, and the
    summary is at the foot where it always was; each entry is kept, as
    it passes, for that one purpose.

    'color_f' lays the page's colours on -- the title block on orange,
    '[OK]' on green, '[FAIL]' on red. The three title lines are padded
    to the full width first, or the background would stop where the
    text does and the block would read as a ragged stripe.
    """
    def verdict_of(good_f):
        """RETURN: (str, str), the verdict's PLAIN text (what the
                   layout measures) and what is printed for it.
        """
        text = "[OK]" if good_f else "[FAIL]"
        return text, painted(text, ANSI_OK if good_f else ANSI_FAIL,
                             color_f)

    rule_equals = "=" * width
    rule_dashes = "-" * width
    seen_list   = []
    for entry in entry_list:
        seen_list.append(entry)
        directory, title, row_list = entry
        yield rule_equals
        if title:
            #  EMPTY, TITLE, EMPTY -- three lines of one stripe.
            yield painted(" " * width, ANSI_TITLE, color_f)
            yield painted(title.center(width), ANSI_TITLE, color_f)
            yield painted(" " * width, ANSI_TITLE, color_f)
        else:
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
            text, shown = verdict_of(row.good_f)
            yield leader_line(left, text, width, 8, shown=shown)
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
    for directory, _, row_list in seen_list:
        fail_n = sum(1 for row in row_list if not row.good_f)
        text, shown = verdict_of(not fail_n)
        #  PADDED BY HAND, not by '%-8s': the width belongs to the
        #  plain text, and 'shown' may carry escapes that '%-8s' would
        #  count as columns.
        yield "    %6s %-4d %s%s %s" \
              % (fail_n if fail_n else "", len(row_list),
                 shown, " " * (8 - len(text)),
                 elided(previous, directory))
        previous = directory
    yield ""

    #  NO CLOSING 'FAILURES:' LIST (E-70). Every failure already stands
    #  in its own block, badged red, beside the test that produced it,
    #  and the summary counts them per directory. Saying them a third
    #  time at the foot made the page longer without making it say
    #  anything the reader had not already been shown -- and on a long
    #  run it pushed the summary off the screen, which is the one part
    #  a person scrolls back for.
    yield rule_dashes
    total_n = sum(len(row_list) for _, _, row_list in seen_list)
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
    #  THE SHAPES ARE THIS FACE'S WORD, not the run's (E-31): the run
    #  said 'differs', and the files read afterwards said how.
    if row.report in ("not-equivalent-grew", "not-equivalent-shrank",
                      "not-equivalent-diverged"):
        return ("the run reported a difference from GOOD; the stored "
                "candidate and the nominal, read whole, are '%s'"
                % row.report)
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
                           #  JSON KEEPS ITS BOOLEANS for pass and
                           #  fail -- consumers exist -- and says
                           #  "aspirant" only where neither is true
                           #  (B-14).
                           "verdict": _json_verdict(row.verdict),
                           "reason":  None if row.good_f else row.word,
                           "stained": row.stain is not None,
                           "when":    row.when or None}
                          for row in row_list]})
    document["test_n"] = sum(len(r) for _, _, r in entry_list)
    document["fail_n"] = sum(1 for _, _, r in entry_list
                             for row in r if not row.good_f)
    return json.dumps(document, indent=2, sort_keys=True)


def line_tuple_of(entry_list, format_name, width, color_f=False):
    """
    YIELD: [0] str  one line of the report in the named format.

    'color_f' reaches the TRADITIONAL page only. A machine format never
    carries an escape: JUnit, TAP and JSON are parsed, not looked at.

    'entry_list' may be a GENERATOR. The traditional page streams it;
    every machine format counts or totals before its first line, so
    those take the list -- which is not a loss, because nobody WATCHES
    JUnit.
    """
    if   format_name == "traditional":
        yield from traditional_line_tuple(entry_list, width, color_f)
    elif not isinstance(entry_list, (list, tuple)):
        yield from line_tuple_of(list(entry_list), format_name, width,
                                 color_f)
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
    plain_f     = False
    color_said_f = False
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
                write("REFUSED: '--format' takes one of %s, not '%s'%s"
                      % (", ".join(FORMAT_TUPLE), format_name,
                         did_you_mean(format_name, FORMAT_TUPLE,
                                      among_listed_f=True)))
                write(USAGE)
                return E_ExitCode.REFUSED
        elif argument == "--plain":   plain_f = True
        elif argument == "--color":   color_said_f = True
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
              % ", ".join(sorted(unknown))
              + did_you_mean(unknown[0], option_tuple(USAGE)))
        write(USAGE)
        return E_ExitCode.REFUSED
    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    wish = with_targets(wish, word_list)
    #  HELD ONLY UNTIL THE FIRST CASE. 'EMPTY' is a fact about the
    #  WHOLE selection, and a stream cannot know it before the end --
    #  but it CAN know the moment the answer stops being 'empty'. So
    #  the walk is held just long enough to see one selected case, and
    #  from there the page is written directory by directory as the
    #  tree is explored.
    try:
        entry_stream = entry_stream_of(os.path.abspath(directory), wish)
        held_list    = []
        for entry in entry_stream:
            held_list.append(entry)
            if entry[2]: break
        else:
            write("EMPTY: the wish selects no case in '%s'" % directory)
            return E_ExitCode.EMPTY
        #  TALLIED AS IT PASSES: the exit code needs the failure count
        #  and the stream is consumed once, so it is counted on the way
        #  through rather than walked a second time.
        fail_box = [0]
        entry_list = _tallied(itertools.chain(held_list, entry_stream),
                              fail_box)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT

    color_f   = color_wanted_f(plain_f, out_name, sys.stdout, color_said_f)
    line_tuple = line_tuple_of(entry_list, format_name,
                               width_of(width), color_f)
    if out_name is None:
        #  WRITTEN AS IT COMES. The page is not built and then shown;
        #  a directory's block reaches the screen while the next
        #  directory is still being interviewed.
        for line in line_tuple: write(line)
        line_list = ()
    else:
        line_list = list(line_tuple)
        try:
            with open(out_name, "w", encoding="utf-8") as file_handle:
                file_handle.write("\n".join(line_list) + "\n")
        except OSError as error:
            write("FAULT: '%s' cannot be written -- %s"
                  % (out_name, error))
            return E_ExitCode.FAULT
        write("written: %s (%s, %d line(s))"
              % (out_name, format_name, len(line_list)))

    return E_ExitCode.FAULT if fail_box[0] else E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.report", main))
