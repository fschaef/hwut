"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: TIER 1, THE PLAIN CONSOLE REPORT (D-1) -- the flow as the
         body, the DIRECTORIES roll-call after it, FAILURES last.

One line per event as it arrives:

    hh:mm:ss | NNN | [EVENT] NICK:base [choice] ...

'hh:mm:ss' is the event's own 'when' relative to the stream's first --
the display NEVER reads a clock of its own; a 'when' that is not an
ISO instant prints verbatim, right-aligned. 'NNN' is the count of
parallel executions AFTER the event. 'NICK' is the directory's
deterministic nickname, expanded once at its 'DIR  ' line and again
in both closing blocks. '[SKIP ]' marks a 'run-ended' that never had a
'run-begun' -- a node that never ran must not claim it did.

Every token on a line is English through 'word.phrase()' -- one
vocabulary, one reading (D-6). An unknown event kind is ignored; an
unknown verdict reads not-ok (the stability promise).

THE TIERS (D-5), each a strict subset of the one above:

    VERBOSE   every event as it arrives, the swallowed ones included
    PLAIN     the flow, the roll-call, FAILURES
    QUIET     no flow; the roll-call, FAULTS met, FAILURES
    SILENT    nothing on stdout; faults go to 'write_error', prefixed
              and nicknamed exactly as in the flow

LAYERING LAW: this component imports the orchestrator's vocabulary,
receiver and summary; NOTHING imports display back. The queue is the
only door.
______________________________________________________________________________
"""
import re
from datetime import datetime
from enum     import Enum

from ..protocol.receiver import CRunReportReceiver
from ..protocol.summary  import fold
from .word                       import CInk, phrase


class E_Tier(Enum):
    VERBOSE = "verbose"
    PLAIN   = "plain"
    QUIET   = "quiet"
    SILENT  = "silent"


def derive_nickname(directory):
    """
    RETURN: str, the deterministic nickname of a directory path: the
            initials of its hyphen/underscore/dot-separated words, a
            trailing 'TEST' component dropped, upper-cased; the first
            four letters where only one word remains; 'ROOT' for '.'.
            Collisions are the registry's business, not this
            function's.
    """
    part_list = [part for part in str(directory).split("/")
                 if part and part != "."]
    if part_list and part_list[-1] == "TEST":
        part_list = part_list[:-1]
    word_list = []
    for part in part_list:
        word_list += [word for word in re.split(r"[-_.]+", part)
                      if word]
    if not word_list:         return "ROOT"
    if len(word_list) == 1:   return word_list[0][:4].upper()
    return "".join(word[0] for word in word_list).upper()


def _split_node(node):
    """
    RETURN: [0] str, the node's base name -- the file, or the whole
                'build[...]' / 'session[...]' spelling.
            [1] str, the choice, where the node carries one; None
                else.
    """
    if node.startswith(("build[", "session[")): return node, None
    base, _, choice = node.partition(" ")
    return base, (choice if choice else None)


def _instant(when):
    """
    RETURN: float, the instant as seconds since the epoch, where
            'when' parses as ISO-8601.
            None, where it does not -- a stream whose instants cannot
            be read holds nothing back, which is the safe way to be
            wrong about a clock.
    """
    try:
        return datetime.fromisoformat(str(when)).timestamp()
    except (ValueError, TypeError):
        return None


def _display_name(node):
    """
    RETURN: str, the node as the eye reads it: 'base choice' where a
            choice stands, the base alone else.

    NO BRACES ROUND THE CHOICE. The flow gives the choice a column of
    its own, and a column needs no bracket to say where it begins --
    the brackets were doing what alignment now does, and doing it
    with punctuation the eye must step over.
    """
    base, choice = _split_node(node)
    if choice is None: return base
    return "%s %s" % (base, choice)


#  The application-name column of the flow line. FIXED, so a column
#  never moves under a reader following it down the page.
APP_COLUMN = 20

#  HOW LONG A START IS HELD BACK. A test that finishes inside the
#  window never announces its beginning: the pair says nothing the
#  end line does not, and two lines per run buries the one that
#  carries a verdict. A test that outlives the window announces
#  itself, so a slow or hanging one is visible while it stands.
#
#  ZERO MEANS ANNOUNCE AT ONCE, and a suite that records the flow
#  states it: whether a line EXISTS would otherwise depend on the
#  speed of the machine, which is the one thing a GOOD file may
#  never hold. A digest that drops START lines is the other way
#  (--pype), and the run suite takes both roads.
START_DELAY_SECONDS = 2.0

#  THE BADGES OF THE FLOW, which come in runs and therefore elide, and
#  the mark that stands under a repeat. As wide as a badge, so the body
#  column does not move.
FLOW_BADGE_TUPLE = ("START", "END  ", "SKIP ")
BADGE_REPEAT     = "---->"


class CPlainFlow(CRunReportReceiver):
    """The tier-1 renderer: derive of the receiver, one flow line per
    event, the closing blocks from its own accounting."""

    def __init__(self, write, write_error=None, width=78, ink=None,
                 tier=E_Tier.PLAIN, timing_f=False, jobs_f=False,
                 detail_f=False, failure_summary_f=True,
                 start_delay=START_DELAY_SECONDS):
        """
        RETURN: CPlainFlow writing flow lines through 'write' and, in
                the SILENT tier, faults through 'write_error'.

        'width'  the line width the dotted fill aims at -- a
                 CONSTRUCTOR argument, never sniffed from a terminal,
                 so a suite pins it.
        'ink'    the CInk of word.py; a transparent one where None.

        THE COLUMNS ARE ASKED FOR, never assumed. 'timing_f' puts a
        seconds column before the line, 'jobs_f' a '|<n>|' one; absent
        both, the flow carries the badge and the name alone -- what a
        person reads is what ran, not when it ran or how many stood
        beside it. 'detail_f' shows the SESSION and BUILD nodes,
        which are otherwise silent unless they FAIL. 'failure_summary_f'
        keeps the closing FAILURES block, which stands by default.
        """
        self.write       = write
        self.write_error = write_error if write_error is not None \
                           else write
        self.width       = width
        self.ink         = ink if ink is not None else CInk(False)
        self.tier        = tier
        self.timing_f    = timing_f
        self.jobs_f      = jobs_f
        self.detail_f    = detail_f
        self.failure_summary_f = failure_summary_f
        self.start_delay = start_delay
        self.held_db     = {}        # (directory, node) -> what its
                                     # START line would have said
        self.last_key    = None      # (directory, file) of the last
                                     # flow line that named a run

        self.t0          = None      # first parseable 'when'
        self.when_first  = None      # first 'when', raw
        self.when_last   = None      # last 'when', raw
        self.parallel_n  = 0
        self.began_set   = set()     # (directory, node) with run-begun

        self.nick_db     = {}        # directory -> nickname
        self.solo_dir_f  = False     # ONE directory: the column goes
        self.last_badge  = None      # the badge last written, for the
                                     # run of repeats beneath it
        self.nick_index  = {}        # directory -> colour index
        self.dir_order   = []        # walk order ('tree-begun'), else
                                     # first-seen
        self.verdict_db  = {}        # (directory, node) -> verdict
        self.report_db   = {}        # (directory, node) -> report word
        self.cause_db    = {}        # (directory, node) -> cause node
        self.frame_bad_db = {}       # directory -> [role, ...]
        self.fault_list  = []        # (directory, rendered fault line),
                                     # in arrival order
        self.dir_good_db = {}        # directory -> dir-done's 'good'
        self.good_f      = None
        self.fail_n      = None
        self.event_f     = False

    # -- the mechanics ---------------------------------------------------
    def dispatch(self, item):
        """
        RETURN: None. One raw event through the receiver's validation
                and onto this renderer; the closing 'None' is a no-op.
        """
        if item is None: return
        self._dispatch(item)

    def _nick(self, directory):
        """
        RETURN: str, the nickname of 'directory' -- registered on
                first sight, collisions resolved by an appended 2, 3,
                ... in first-seen order.
        """
        known = self.nick_db.get(directory)
        if known is not None: return known
        nick  = derive_nickname(directory)
        if nick in self.nick_db.values():
            count = 2
            while "%s%d" % (nick, count) in self.nick_db.values():
                count += 1
            nick = "%s%d" % (nick, count)
        self.nick_db[directory]    = nick
        self.nick_index[directory] = len(self.nick_index)
        return nick

    def _ink_nick(self, directory):
        """RETURN: str, the nickname, painted in the directory's own
        cycling colour."""
        return self.ink.nick(self._nick(directory),
                             self.nick_index.get(directory, 0))

    def _clock(self, when):
        """
        RETURN: str, the flow line's timing column: SECONDS since the
                stream's first instant, one decimal, right-aligned;
                'when' verbatim, right-aligned, where it does not
                parse as ISO-8601.

        SECONDS, NOT 'hh:mm:ss': a test suite is read in seconds, and
        a column of zeroed hours says nothing anyone needed.
        """
        try:
            t = datetime.fromisoformat(str(when))
        except (ValueError, TypeError):
            return "%8s" % str(when)
        if self.t0 is None: self.t0 = t
        return "%7.1fs" % (t - self.t0).total_seconds()

    def _elapsed(self):
        """
        RETURN: str, the whole stream's span, first 'when' to last --
                'hh:mm:ss' where both parse; the last 'when' verbatim
                else; '-' where no event arrived.
        """
        if self.when_last is None: return "-"
        try:
            t0 = datetime.fromisoformat(str(self.when_first))
            t1 = datetime.fromisoformat(str(self.when_last))
        except (ValueError, TypeError):
            return str(self.when_last)
        seconds = int((t1 - t0).total_seconds())
        return "%02d:%02d:%02d" % (seconds // 3600,
                                   seconds // 60 % 60, seconds % 60)

    def _prefix(self, when):
        """
        RETURN: [0] str, the line prefix, plain: the seconds column
                where '--show-timing' asked for it, the '|<n>|' job
                column where '--show-jobs' did, and NOTHING where
                neither did -- which is the default.
                [1] str, the same, painted dim.

        The job column carries no blank inside its bars: '|3|' is one
        token and reads as one.
        """
        part_list = []
        if self.timing_f: part_list.append(self._clock(when))
        if self.jobs_f:   part_list.append("|%d|" % self.parallel_n)
        if not part_list: return "", ""
        text = " ".join(part_list) + " "
        return text, self.ink.dim(text)

    def _run_body(self, directory, node):
        """
        RETURN: [0] str, the run's name column, ELIDED against the
                    line before it and column-aligned:

                        A  test-app.sh  one
                        :/ test-solo.sh
                        A2 test-app.sh  one
                        :/ :            two

                    ':/' stands where the DIRECTORY repeats, ':/ :'
                    where the application does too -- the same one
                    mark, two positions, that a sorted wishlist uses
                    (disc-8). What repeats is not read again; what
                    changed stands out.
                [1] str, the same, the nickname painted.

        The columns are padded so applications of one directory sit
        under one another and the choices of one application do the
        same.
        """
        name          = _display_name(node)
        file, _, rest = name.partition(" ")
        choice        = rest.strip()
        nick          = self._nick(directory)
        key           = (directory, file)
        if self.solo_dir_f:
            #  NO DIRECTORY COLUMN, and so no ':/': what repeats is the
            #  application alone, and its ':' stands under its name.
            shown    = ":" if self.last_key == key else file
            self.last_key = key
            pad      = " " * max(APP_COLUMN - len(shown), 0)
            body     = "%s%s" % (shown, pad)
            if not choice: return body.rstrip(), body.rstrip()
            return "%s %s" % (body, choice), "%s %s" % (body, choice)
        #  THE COLUMNS ARE FIXED, not grown as names arrive: a width
        #  that widens mid-run moves every column under it, and a
        #  reader following one column down the page loses it. A name
        #  longer than the column overflows its own line alone.
        nick_width     = max([len(n) for n in self.nick_db.values()]
                             + [3])
        app_width      = APP_COLUMN

        if self.last_key == key:
            #  THE THIRD ':' STANDS IN THE APPLICATION'S COLUMN, under
            #  the first letter of the name it repeats -- a mark that
            #  says 'the same as above' belongs above what it repeats.
            mark, mark_ink, shown = ":/", self.ink.dim(":/"), ":"
        elif self.last_key is not None \
             and self.last_key[0] == directory:
            mark, mark_ink, shown = ":/", self.ink.dim(":/"), file
        else:
            mark, mark_ink, shown = nick, self._ink_nick(directory), \
                                    file
        self.last_key = key

        pad_mark = " " * max(nick_width - len(mark), 0)
        pad_app  = " " * max(app_width - len(shown), 0)
        body     = "%s%s %s%s" % (mark, pad_mark, shown, pad_app)
        body_ink = "%s%s %s%s" % (mark_ink, pad_mark, shown, pad_app)
        if not choice: return body.rstrip(), body_ink.rstrip()
        return "%s %s" % (body, choice), "%s %s" % (body_ink, choice)

    def _line(self, when, badge, badge_ink, body, body_ink,
              right="", right_ink="", tail=""):
        """
        RETURN: None. One flow line written: prefix, badge, body,
                then -- where a right part stands -- a dotted fill
                aiming at 'width', the right part, and 'tail' beyond
                the width math.

        A BADGE THAT REPEATS BECOMES AN ARROW (E-33). The first of a
        run of 'START's says 'START'; those under it say '---->', so
        the eye reads one block and the word marks where the block
        begins. Only the flow badges elide -- 'DIR', 'TREE' and the
        rest announce something and are never a run.
        """
        if badge in FLOW_BADGE_TUPLE:
            if badge == self.last_badge:
                badge, badge_ink = BADGE_REPEAT, self.ink.dim(BADGE_REPEAT)
            else:
                self.last_badge = badge
        else:
            self.last_badge = None
        prefix, prefix_ink = self._prefix(when)
        if not right:
            self.write("%s%s %s%s" % (prefix_ink, badge_ink, body_ink,
                                      tail))
            return
        fill = self.width - len(prefix) - len(badge) - 1 - len(body) \
               - len(right) - 2
        dots = "." * max(fill, 1)
        self.write("%s%s %s %s %s%s"
                   % (prefix_ink, badge_ink, body_ink,
                      self.ink.dim(dots), right_ink, tail))

    # -- the handlers ----------------------------------------------------
    def on_any(self, kind, **fields):
        """RETURN: None. Bookkeeping every event shares: the first and
        the last 'when'."""
        self.event_f = True
        when = fields.get("when")
        if when is None: return
        if self.when_first is None: self.when_first = when
        self.when_last = when

    def on_tree_begun(self, when, directory_list):
        """RETURN: None. Nicknames and the roll-call's order registered
        in walk order; a line in the VERBOSE tier alone.

        ONE DIRECTORY, NO DIRECTORY COLUMN: where the whole run happens
        in one place, a nickname repeated down the page names nothing
        the reader does not already know, and ':/' says 'the same as
        above' about a thing that was never in question (E-33)."""
        self.solo_dir_f = len(directory_list) == 1
        for directory in directory_list:
            self._nick(directory)
            if directory not in self.dir_order:
                self.dir_order.append(directory)
        if self.tier is not E_Tier.VERBOSE: return
        self._line(when, "TREE ", self.ink.bold("TREE "),
                   "%d directory(ies)" % len(directory_list),
                   "%d directory(ies)" % len(directory_list))

    def on_dir_begun(self, when, directory, node_n):
        """RETURN: None. The directory's nickname declared, once."""
        if directory not in self.dir_order:
            self.dir_order.append(directory)
        nick = self._nick(directory)
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        body = "%s = %s" % (nick, directory)
        self._line(when, "DIR  ", self.ink.warn("DIR  "),
                   body, "%s = %s" % (self._ink_nick(directory),
                                      directory))

    def on_frame(self, when, directory, role, good):
        """RETURN: None. A failed frame is a failure of the directory
        and says so; a good one speaks in the VERBOSE tier alone."""
        if not good:
            self.frame_bad_db.setdefault(directory, []).append(role)
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        if good and self.tier is not E_Tier.VERBOSE:   return
        nick = self._nick(directory)
        body = "%s:%s" % (nick, role)
        body_ink = "%s:%s" % (self._ink_nick(directory), role)
        if good:
            self._line(when, "FRAME", "FRAME", body, body_ink,
                       "[OK]", self.ink.tag_ok("[OK]"))
        else:
            right = "the frame failed  [FAIL]"
            right_ink = "%s  %s" % (self.ink.fail("the frame failed"),
                                    self.ink.tag_fail("[FAIL]"))
            self._line(when, "FRAME", "FRAME", body, body_ink,
                       right, right_ink)

    def _provision_hidden_f(self, node_kind):
        """
        RETURN: bool, True where a node of this kind does not speak:
                SESSION and BUILD are PROVISION, and only the tests
                and the directory's own lines make a flow worth
                reading. '--show-details' shows them; the VERBOSE
                tier shows everything.

        A FAILING provision node always speaks, wherever this is
        asked: a failed precondition is a test result, not a silence.
        """
        if self.detail_f:                    return False
        if self.tier is E_Tier.VERBOSE:      return False
        return node_kind in ("SESSION", "BUILD")

    def on_run_begun(self, when, directory, node, node_kind):
        """RETURN: None. The parallel count rises; a 'START' line --
        where the tier speaks at all, and where the node is not a
        silent provision one."""
        self.parallel_n += 1
        self.began_set.add((directory, node))
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        if self._provision_hidden_f(node_kind):        return
        if self.start_delay > 0:
            #  HELD, not dropped: the body is computed when the line
            #  is finally written, so the elision reads against the
            #  line that truly precedes it.
            self.held_db[(directory, node)] = when
            return
        body, body_ink = self._run_body(directory, node)
        self._line(when, "START", self.ink.start("START"),
                   body, body_ink)

    def on_tick(self, when):
        """
        RETURN: None. Releases every held START whose run has now
                outlived the delay -- oldest first, so the flow keeps
                the order the runs began in.

        Called by the consumer when no event arrived: a run that
        merely takes long emits nothing, and a START nobody released
        would never be seen.
        """
        if not self.held_db: return
        now = _instant(when)
        if now is None: return
        for key in sorted(self.held_db,
                          key=lambda k: str(self.held_db[k])):
            begun = _instant(self.held_db[key])
            if begun is None or now - begun < self.start_delay:
                continue
            directory, node = key
            began_when     = self.held_db.pop(key)
            body, body_ink = self._run_body(directory, node)
            self._line(began_when, "START",
                       self.ink.start("START"), body, body_ink)

    def _release_held(self, key):
        """
        RETURN: bool, True where a START was still held for this run
                -- and is now forgotten, unwritten: the run ended
                inside the window, and its end line says everything
                its beginning would have.
        """
        return self.held_db.pop(key, None) is not None

    def on_run_ended(self, when, directory, node, node_kind, good,
                     verdict, cause=None, report=None):
        """RETURN: None. 'END  ' where the node had begun, 'SKIP '
        else; the failing line carries its phrase inline; the count
        falls only for what had risen."""
        key      = (directory, node)
        began_f  = key in self.began_set
        if began_f:
            self.began_set.discard(key)
            self.parallel_n = max(self.parallel_n - 1, 0)
        self.verdict_db[key] = verdict
        if report is not None: self.report_db[key] = report
        if cause  is not None: self.cause_db[key]  = cause
        if directory not in self.dir_order:
            self.dir_order.append(directory)

        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        #  A FAILING provision node speaks even where its kind is
        #  otherwise silent: a failed precondition is a test result.
        if good and self._provision_hidden_f(node_kind):  return
        self._release_held((directory, node))
        body, body_ink = self._run_body(directory, node)
        word     = phrase(report if report is not None else verdict)
        tail     = "" if cause is None else "  <- %s" % cause

        if not began_f:
            self._line(when, "SKIP ", self.ink.warn("SKIP "),
                       "%s  %s" % (body, word),
                       "%s  %s" % (body_ink, self.ink.warn(word)),
                       tail=tail)
            return
        if good:
            self._line(when, "END  ", "END  ", body, body_ink,
                       "[OK]", self.ink.tag_ok("[OK]"))
        else:
            right     = "%s  [FAIL]" % word
            right_ink = "%s  %s" % (self.ink.fail(word),
                                    self.ink.tag_fail("[FAIL]"))
            self._line(when, "END  ", "END  ", body, body_ink,
                       right, right_ink, tail=tail)

    def on_fault(self, when, directory, text):
        """RETURN: None. A fault is never swallowed: a flow line, or
        -- SILENT -- the same line on 'write_error'; QUIET holds it
        for the tail's FAULTS block."""
        prefix, prefix_ink = self._prefix(when)
        line = "%sFAULT %s: %s" % (prefix_ink,
                                     self._ink_nick(directory), text)
        self.fault_list.append((directory, "%sFAULT %s: %s"
                                % (prefix, self._nick(directory), text)))
        if   self.tier is E_Tier.SILENT: self.write_error(line)
        elif self.tier is E_Tier.QUIET:  pass
        else:                            self.write(line)

    def on_report(self, when, directory, text):
        """RETURN: None. Determination's note, e.g. an empty
        selection."""
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        prefix, prefix_ink = self._prefix(when)
        self.write("%sNOTE  %s: %s" % (prefix_ink,
                                         self._ink_nick(directory),
                                         text))

    def on_dir_done(self, when, directory, good, fail_db):
        """RETURN: None. Accounted for the roll-call; a line in the
        VERBOSE tier alone."""
        if directory not in self.dir_order:
            self.dir_order.append(directory)
        self.dir_good_db[directory] = good
        if self.tier is not E_Tier.VERBOSE: return
        nick   = self._nick(directory)
        ok_n, total_n = self._count(directory)
        tag    = "[OK]" if good else "[FAIL]"
        right  = "%d of %d ok  %s" % (ok_n, total_n, tag)
        right_ink = "%d of %d ok  %s" \
                    % (ok_n, total_n,
                       self.ink.tag_ok(tag) if good else self.ink.tag_fail(tag))
        self._line(when, "DONE ", "DONE ", nick,
                   self._ink_nick(directory), right, right_ink)

    def _fault_lines(self):
        """
        RETURN: list[str], the held fault lines, GROUPED BY DIRECTORY
                in the roll-call's order -- faults of no listed
                directory (the walk's own, '.') first -- and in arrival
                order within one directory.
        """
        rank = {d: i for i, d in enumerate(self.dir_order)}
        return [line for _, (_, line)
                in sorted(enumerate(self.fault_list),
                          key=lambda p: (rank.get(p[1][0], -1), p[0]))]

    def on_tree_done(self, when, good, fail_n):
        """RETURN: None. The stream's own closing word, held for the
        tail; a line in the VERBOSE tier alone."""
        self.good_f = good
        self.fail_n = fail_n
        if self.tier is not E_Tier.VERBOSE: return
        self._line(when, "TREE ", self.ink.bold("TREE "),
                   "done, %d failure(s)" % fail_n,
                   "done, %d failure(s)" % fail_n)

    def on_misfit(self, kind, **fields):
        """RETURN: None. A known kind whose structure does not fit: a
        fault line, the stream walks on."""
        directory = fields.get("directory", ".")
        when      = fields.get("when", "")
        prefix, prefix_ink = self._prefix(when)
        text = "event of kind '%s' does not fit the vocabulary" % kind
        line = "%sFAULT %s: %s" % (prefix_ink,
                                     self._ink_nick(directory), text)
        self.fault_list.append((directory, "%sFAULT %s: %s"
                                % (prefix, self._nick(directory), text)))
        if   self.tier is E_Tier.SILENT: self.write_error(line)
        elif self.tier is E_Tier.QUIET:  pass
        else:                            self.write(line)

    # -- the closing blocks ------------------------------------------------
    def _count(self, directory):
        """
        RETURN: [0] int, how many of the directory's runs ended 'ok'.
                [1] int, how many runs the directory saw at all.
        """
        verdict_list = [verdict for (d, _n), verdict
                        in self.verdict_db.items() if d == directory]
        return (sum(1 for verdict in verdict_list if verdict == "ok"),
                len(verdict_list))

    def _failure_key_list(self, directory):
        """
        RETURN: list, the (directory, node) keys of the directory's
                not-ok runs, node-sorted -- an unknown verdict reads
                not-ok.
        """
        return sorted(key for key, verdict in self.verdict_db.items()
                      if key[0] == directory and verdict != "ok")

    def tail(self):
        """
        RETURN: None. The DIRECTORIES roll-call, the FAULTS met (QUIET
        tier), and the FAILURES block, last -- nothing in the SILENT
        tier.
        """
        if self.tier is E_Tier.SILENT: return
        write, ink, w = self.write, self.ink, self.width
        ok_total   = sum(1 for verdict in self.verdict_db.values()
                         if verdict == "ok")
        fail_total = len(self.verdict_db) - ok_total

        write("")
        write("=" * w)
        head_right = "%d ok, %d fail, %s" % (ok_total, fail_total,
                                             self._elapsed())
        write("DIRECTORIES%*s" % (w - len("DIRECTORIES"), head_right))
        write("-" * w)
        if not self.dir_order:
            write("    (no directory ran)")
        nick_width = max([len(self.nick_db[d])
                          for d in self.dir_order], default=0)
        for directory in self.dir_order:
            nick   = self.nick_db[directory]
            good   = self.dir_good_db.get(directory)
            ok_n, total_n = self._count(directory)
            tag    = "[OK]" if good else "[FAIL]"
            counts = "%3d of %3d ok" % (ok_n, total_n)
            plain_left  = "%-*s  %s" % (nick_width, nick, directory)
            plain_right = "%-6s %s" % (tag, counts)
            fill = max(w - len(plain_left) - len(plain_right) - 2, 1)
            tag_ink  = ink.tag_ok(tag) if good else ink.tag_fail(tag)
            ink_left = "%s%s  %s" % (ink.nick(nick,
                                       self.nick_index[directory]),
                                     " " * (nick_width - len(nick)),
                                     directory)
            write("%s %s %s%s %s"
                  % (ink_left, ink.dim("." * fill), tag_ink,
                     " " * (6 - len(tag)), counts))
        if self.event_f and self.good_f is None:
            write("    the stream ended without 'tree-done'")

        if self.tier is E_Tier.QUIET and self.fault_list:
            write("")
            write("=" * w)
            write("FAULTS")
            write("-" * w)
            for line in self._fault_lines():
                write(line)

        fail_dir_list = [d for d in self.dir_order
                         if self._failure_key_list(d)
                         or self.frame_bad_db.get(d)]
        if not self.failure_summary_f: fail_dir_list = []
        if not fail_dir_list:
            write("=" * w)
            return
        write("")
        write("=" * w)
        write("FAILURES")
        write("-" * w)
        name_width = 28
        for directory in fail_dir_list:
            for key in self._failure_key_list(directory):
                name_width = max(name_width,
                                 len(_display_name(key[1])) + 2)
        for directory in fail_dir_list:
            write("%s  %s" % (self._ink_nick(directory), directory))
            for role in self.frame_bad_db.get(directory, []):
                write("    %-*s %s"
                      % (name_width, "frame %s" % role,
                         ink.fail("the frame failed")))
            for key in self._failure_key_list(directory):
                token = self.report_db.get(key, self.verdict_db[key])
                line  = "    %-*s %s" % (name_width,
                                         _display_name(key[1]),
                                         ink.fail(phrase(token)))
                cause = self.cause_db.get(key)
                if cause is not None: line += "  <- %s" % cause
                write(line)
        write("=" * w)


def render(event_iterable, write, write_error=None, width=78,
           colour_f=False, tier=E_Tier.PLAIN):
    """
    RETURN: CRunSummary, the events folded -- after every event went
            through one CPlainFlow (flow lines, then the closing
            blocks) under the given width, ink and tier. The
            convenience for a suite or a caller holding the whole
            stream; a face wanting LIVE lines drives CPlainFlow
            itself.
    """
    flow = CPlainFlow(write, write_error, width=width,
                      ink=CInk(colour_f), tier=tier)
    event_list = []
    for item in event_iterable:
        if item is None: break
        event_list.append(item)
        flow.dispatch(item)
    flow.tail()
    return fold(event_list)
