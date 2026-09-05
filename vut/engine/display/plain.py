"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: TIER 1, THE PLAIN CONSOLE REPORT (D-1) -- the flow as the
         body, the DIRECTORIES roll-call after it, FAILURES last.

One line per event as it arrives:

    hh:mm:ss | NNN | [EVENT] base [choice] ...

'hh:mm:ss' is the event's own 'when' relative to the stream's first --
the display NEVER reads a clock of its own; a 'when' that is not an
ISO instant prints verbatim, right-aligned. 'NNN' is the count of
parallel executions AFTER the event. NO ABBREVIATION IS GENERATED for
a directory: it is named IN FULL, once, on its own banner line ('DIR')
when the run enters it -- every line beneath speaks of what ran, not
of where, until the next banner says otherwise. '[SKIP ]' marks a
'run-ended' that never had a 'run-begun' -- a node that never ran must
not claim it did.

PENDING RATIONALE: this supersedes D-1's 'NICK:base' column, E-30's
repeat mark and E-33's badge-arrow and single-directory elision, on
Frank-Rene's direct instruction (2026-08-31); the RATIONALE entries
themselves are not yet rewritten -- see the component's DISCUSSIONS.

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


#  THE BLANK BETWEEN AN APPLICATION'S NAME AND ITS FIRST CHOICE. The
#  choice column itself is not fixed tree-wide: each application sets
#  its own from its own name, and the ':' lines beneath it hold that
#  width ('_run_body'). A new application opens a new column.
#
#  TWO BLANKS, NOT A FIELD. The choice belongs to the name beside it,
#  and a wide gap reads as two columns that have nothing to do with
#  each other.
CHOICE_GAP = 2

#  The blank before a HINTS briefing, which IS a column of its own and
#  wants to be seen as one.
BRIEF_GAP = 3

#  THE DIRECTORIES TREE. Indented off the left margin so the block
#  reads as a figure rather than as more lines of report; the tag
#  right-aligned in its own width, the count beyond it in its own.
TREE_INDENT = "   "
TAG_WIDTH   = 6
COUNT_WIDTH = 9


def _dot_space_fill(width):
    """
    RETURN: str, '. . . .' of exactly 'width' characters -- a rule
            light enough to stand beside the tree's own connectors
            without reading as another one of them.
    """
    return (". " * (width // 2 + 1))[:width]


def _tag_and_count(tag, counts, good, ink):
    """
    RETURN: [0] str, the right side UNPAINTED -- the tag and the count
                in their fixed columns. Its LENGTH is what the fill is
                measured against, so it must carry no escape.
            [1] str, the same right side PAINTED, the tag alone
                inked and the count left plain.

    THE TAG IS RIGHT-ALIGNED so '[OK]' and '[FAIL]' end in one column
    though they differ in width; the count hangs beyond it, itself
    right-aligned. MEASURED UNPAINTED, PAINTED AFTER: an escape
    sequence has length and no width, and a fill measured over one
    would pull every dot rule out of true.
    """
    tag_field   = "%*s" % (TAG_WIDTH, tag)
    count_field = "%*s" % (COUNT_WIDTH, counts)
    tag_ink     = ink.tag_ok(tag) if good else ink.tag_fail(tag)
    return ("%s%s" % (tag_field, count_field),
            "%s%s%s" % (" " * (TAG_WIDTH - len(tag)), tag_ink,
                        count_field))

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
#  the mark that stands under a repeat: PLAIN WHITESPACE, as wide as a
#  badge, so the body column does not move and a repeated badge says
#  nothing the position does not already say.
FLOW_BADGE_TUPLE = ("START", "DONE ", "SKIP ")
BADGE_REPEAT     = "     "

#  'DONE ' is now the per-RUN completion badge (was 'END  '). The
#  per-DIRECTORY roll-up line, VERBOSE tier only, is renamed 'ROLL '
#  so the two are never the same word about two different things.


class CPlainFlow(CRunReportReceiver):
    """The tier-1 renderer: derive of the receiver, one flow line per
    event, the closing blocks from its own accounting."""

    def __init__(self, write, write_error=None, width=78, ink=None,
                 tier=E_Tier.PLAIN, timing_f=False, jobs_f=False,
                 detail_f=False, failure_summary_f=True,
                 start_delay=START_DELAY_SECONDS, write_log=None):
        """
        RETURN: CPlainFlow writing flow lines through 'write', faults
                and notes through 'write_log', and -- in the SILENT
                tier -- faults through 'write_error'.

        'width'  the line width the dotted fill aims at -- a
                 CONSTRUCTOR argument, never sniffed from a terminal,
                 so a suite pins it.
        'ink'    the CInk of word.py; a transparent one where None.
        'write_log'
                 where a FAULT or a NOTE goes. These are the run's
                 MARGINALIA -- a configuration line that did not
                 parse, a wish that selected nothing -- true, worth
                 keeping, and not what a reader watching a run is
                 watching for. None means no log stands, and then
                 they go to 'write_error' rather than into the flow:
                 A FAULT IS NEVER SWALLOWED, and the absence of a log
                 is not permission to lose one.

        THE COLUMNS ARE ASKED FOR, never assumed. 'timing_f' puts a
        seconds column before the line, 'jobs_f' a '|<n>|' one; absent
        both, the flow carries the badge and the name alone -- what a
        person reads is what ran, not when it ran or how many stood
        beside it. 'detail_f' shows the SESSION and BUILD nodes,
        which are otherwise silent unless they FAIL. 'failure_summary_f'
        keeps the closing HINTS block, which stands by default.
        """
        self.write       = write
        self.write_error = write_error if write_error is not None \
                           else write
        self.write_log   = write_log
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
        self.choice_column = 0       # where the CURRENT application's
                                     # choices stand; reset by each
                                     # new application (_run_body)

        self.t0          = None      # first parseable 'when'
        self.when_first  = None      # first 'when', raw
        self.when_last   = None      # last 'when', raw
        self.parallel_n  = 0
        self.began_set   = set()     # (directory, node) with run-begun

        self.last_dir_shown = None   # the directory the last DIR band
                                     # named; a repeat prints nothing
        self.last_badge  = None      # the badge last written, for the
                                     # run of repeats beneath it
        self.dir_order   = []        # walk order ('tree-begun'), else
                                     # first-seen
        self.verdict_db  = {}        # directory -> { node -> verdict }
        self.report_db   = {}        # (directory, node) -> report word
        self.cause_db    = {}
        self.detail_db  = {}        # (directory, node) -> the report's numbers (O-19)        # (directory, node) -> cause node
        self.frame_bad_db = {}       # directory -> [role, ...]
        self.fault_list  = []        # (directory, rendered fault line),
        self.refused_db  = {}        # directory -> [(node, reason), ...]
                                     # (E-41): not run, said at the end
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

    def _ink_dir(self, directory):
        """RETURN: str, 'directory' (the full path, verbatim), in the
        directory's own colour."""
        return self.ink.directory(str(directory))

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
        RETURN: [0] str, the run's name column: the application's
                    file, or ':' where it repeats the line above it
                    (the same mark a sorted wishlist uses, disc-8) --
                    then its choice, where it carries one.
                [1] str, the same (no colour differs here; a run's
                    body carries none of its own).

        THE APPLICATION SETS ITS OWN CHOICE COLUMN. The choices of one
        application stand under one another, at the width THAT NAME
        asks for -- not at a width every application in the tree
        shares. A NEW APPLICATION IS A NEW COLUMN:

            test-x.py    one
            :            two
            test-longer-name.py    alpha
            :                      beta

        A single fixed column would be as wide as the longest name
        anywhere in the run, and every short name would trail a field
        of blanks to reach it.

        NO DIRECTORY COLUMN. The DIR band already named the directory
        once, in full, when the run entered it; a line here says only
        what ran. ':' compares '(directory, file)', so two directories
        sharing an application's name are never confused for a repeat.
        """
        name          = _display_name(node)
        file, _, rest = name.partition(" ")
        choice        = rest.strip()
        key           = (directory, file)
        repeat_f      = (self.last_key == key)
        if not repeat_f:
            #  THE COLUMN IS SET BY THE NAME THAT OPENS THE GROUP and
            #  held for every ':' beneath it.
            self.choice_column = len(file) + CHOICE_GAP
        self.last_key = key
        shown         = ":" if repeat_f else file
        if not choice: return shown, shown
        body = "%-*s%s" % (self.choice_column, shown, choice)
        return body, body

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
        """RETURN: None. The roll-call's order registered in walk
        order; a line in the VERBOSE tier alone."""
        for directory in directory_list:
            if directory not in self.dir_order:
                self.dir_order.append(directory)
        if self.tier is not E_Tier.VERBOSE: return
        self._line(when, "TREE ", self.ink.bold("TREE "),
                   "%d directory(ies)" % len(directory_list),
                   "%d directory(ies)" % len(directory_list))

    def _band(self, when, directory):
        """
        RETURN: None. THE DIR BAND, printed exactly where the directory
                the flow speaks of CHANGES -- a full-width band naming
                it in full, on an orange ground -- and nowhere else.

        THE RULING IS 'WHEN THE DIRECTORY CHANGES', NOT 'WHEN IT
        BEGINS'. With one directory at a time the two coincide. With
        directories running in parallel ('--jobs', 'successor',
        'parallel') their lines INTERLEAVE, and a band printed only at
        each beginning leaves every later line under whichever band
        came last -- unreadable for a person, unattributable for a
        digest. So every flow line asks: is this the directory the
        last band named? If not, the band comes first. A line carries
        no directory column of its own (the ruling), and so the band
        is the ONE place the directory is ever said.
        """
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        if directory == self.last_dir_shown: return
        self.last_dir_shown = directory
        self.last_badge     = None   # a band ends any badge run above it
        self.last_key       = None   # and any ':' elision: the application
                                     # above is another directory's
        prefix, _ = self._prefix(when)
        text = "%sDIR  %s" % (prefix, directory)
        pad  = " " * max(self.width - len(text), 0)
        self.write(self.ink.dir_band(text + pad))

    def on_dir_begun(self, when, directory, node_n):
        """RETURN: None. The directory registered for the roll-call;
        its band is printed by '_band' the moment its first line
        needs it, not here -- see '_band' for why."""
        if directory not in self.dir_order:
            self.dir_order.append(directory)

    def on_frame(self, when, directory, role, good):
        """RETURN: None. A failed frame is a failure of the directory
        and says so; a good one speaks in the VERBOSE tier alone."""
        if not good:
            self.frame_bad_db.setdefault(directory, []).append(role)
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        self._band(when, directory)
        if good and self.tier is not E_Tier.VERBOSE:   return
        body = "%s:%s" % (directory, role)
        body_ink = "%s:%s" % (self._ink_dir(directory), role)
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
        self._band(when, directory)
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
                     verdict, cause=None, report=None, detail=None):
        """RETURN: None. 'DONE ' where the node had begun, 'SKIP '
        else; the count falls only for what had risen.

        THE FLOW SAYS [OK] OR [FAIL] AND NO MORE. A reason belongs to
        the reader who has stopped to ask why, and that reader is
        reading HINTS; carrying it here spends the width of every
        failing line on a phrase the eye is not scanning for while a
        run is still going.
        """
        key      = (directory, node)
        began_f  = key in self.began_set
        if began_f:
            self.began_set.discard(key)
            self.parallel_n = max(self.parallel_n - 1, 0)
        self.verdict_db.setdefault(key[0], {})[key[1]] = verdict
        if report is not None: self.report_db[key] = report
        if cause  is not None: self.cause_db[key]  = cause
        if detail is not None: self.detail_db[key] = detail
        if directory not in self.dir_order:
            self.dir_order.append(directory)

        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        self._band(when, directory)
        #  A FAILING provision node speaks even where its kind is
        #  otherwise silent: a failed precondition is a test result.
        if good and self._provision_hidden_f(node_kind):  return
        self._release_held((directory, node))
        body, body_ink = self._run_body(directory, node)

        if not began_f:
            #  A NODE THAT NEVER RAN STILL CARRIES ITS VERDICT. An
            #  application that would not launch, would not parse or
            #  would not build never reaches a 'run-begun', and it is
            #  a FAILING TEST all the same -- reading '[FAIL]' like
            #  every other. 'SKIP ' says it never ran; the tag says
            #  how it came out; HINTS says which of the three it was.
            if good:
                self._line(when, "SKIP ", self.ink.warn("SKIP "),
                           body, body_ink,
                           "[OK]", self.ink.tag_ok("[OK]"))
            else:
                self._line(when, "SKIP ", self.ink.warn("SKIP "),
                           body, body_ink,
                           "[FAIL]", self.ink.tag_fail("[FAIL]"))
            return
        if good:
            self._line(when, "DONE ", "DONE ", body, body_ink,
                       "[OK]", self.ink.tag_ok("[OK]"))
        else:
            self._line(when, "DONE ", "DONE ", body, body_ink,
                       "[FAIL]", self.ink.tag_fail("[FAIL]"))

    def _marginal(self, plain_line, ink_line):
        """
        RETURN: None. One FAULT or NOTE line placed where marginalia
                belong: THE LOG, where one stands.

        THESE ARE NOT THE RUN REPORT. A configuration line that did
        not parse and a wish that selected nothing are true and worth
        keeping, and neither is what a reader watching a run is
        watching for; three of them bury the verdict they stand
        beside.

        WITH NO LOG they go to 'write_error' -- never into the flow,
        and never nowhere: A FAULT IS NEVER SWALLOWED, and '--no-log'
        asks for no file, not for silence.
        """
        if self.write_log is not None: self.write_log(plain_line)
        else:                          self.write_error(ink_line)

    def on_fault(self, when, directory, text):
        """RETURN: None. A fault is never swallowed: a line in the
        log (or, with none, on 'write_error'); QUIET additionally
        holds it for the tail's FAULTS block."""
        prefix, prefix_ink = self._prefix(when)
        line = "%sFAULT %s: %s" % (prefix_ink,
                                     self._ink_dir(directory), text)
        plain = "%sFAULT %s: %s" % (prefix, directory, text)
        self.fault_list.append((directory, plain))
        if self.tier is E_Tier.SILENT: self.write_error(line)
        else:                          self._marginal(plain, line)

    def on_report(self, when, directory, text):
        """RETURN: None. Determination's note, e.g. an empty
        selection -- marginalia, and so the log's (or, with none,
        'write_error')."""
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        prefix, prefix_ink = self._prefix(when)
        self._marginal("%sNOTE  %s: %s" % (prefix, directory, text),
                       "%sNOTE  %s: %s" % (prefix_ink,
                                           self._ink_dir(directory),
                                           text))

    def on_refused(self, when, directory, node, text):
        """RETURN: None. Not run, by name and reason: held for the
        closing REFUSED block, which stands in every tier but SILENT
        -- a refusal is never marginalia."""
        self.refused_db.setdefault(directory, []).append((node, text))

    def on_dir_done(self, when, directory, good, fail_db):
        """RETURN: None. Accounted for the roll-call; a line in the
        VERBOSE tier alone -- badge 'ROLL ', distinct from a single
        run's own 'DONE ' (they used to share the word)."""
        if directory not in self.dir_order:
            self.dir_order.append(directory)
        self.dir_good_db[directory] = good
        if self.tier is not E_Tier.VERBOSE: return
        ok_n, total_n = self._count(directory)
        tag    = "[OK]" if good else "[FAIL]"
        right  = "%d of %d ok  %s" % (ok_n, total_n, tag)
        right_ink = "%d of %d ok  %s" \
                    % (ok_n, total_n,
                       self.ink.tag_ok(tag) if good else self.ink.tag_fail(tag))
        self._line(when, "ROLL ", "ROLL ", directory,
                   self._ink_dir(directory), right, right_ink)

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
        fault, and so the log's; the stream walks on."""
        directory = fields.get("directory", ".")
        when      = fields.get("when", "")
        prefix, prefix_ink = self._prefix(when)
        text = "event of kind '%s' does not fit the vocabulary" % kind
        line = "%sFAULT %s: %s" % (prefix_ink,
                                     self._ink_dir(directory), text)
        plain = "%sFAULT %s: %s" % (prefix, directory, text)
        self.fault_list.append((directory, plain))
        if self.tier is E_Tier.SILENT: self.write_error(line)
        else:                          self._marginal(plain, line)

    # -- the closing blocks ------------------------------------------------
    def _verdict_of(self, key):
        """
        RETURN: str, the verdict recorded under the (directory, node)
                'key' -- the tuple form every other database here is
                keyed by, read out of the nested store.

        KeyError, where no run stands under that key.
        """
        return self.verdict_db[key[0]][key[1]]

    def _count(self, directory):
        """
        RETURN: [0] int, how many of the directory's runs ended 'ok'.
                [1] int, how many runs the directory saw at all.
        """
        node_db = self.verdict_db.get(directory, {})
        return (sum(1 for verdict in node_db.values() if verdict == "ok"),
                len(node_db))

    def _failure_key_list(self, directory):
        """
        RETURN: list, the (directory, node) keys of the directory's
                not-ok runs, node-sorted -- an unknown verdict reads
                not-ok.
        """
        return sorted((directory, node)
                      for node, verdict
                      in self.verdict_db.get(directory, {}).items()
                      if verdict != "ok")

    def _directory_tree(self):
        """
        RETURN: dict, the root of a tree built from every path in
                'self.dir_order', one node per '/'-separated segment.
                A node that is itself one of the run's directories
                carries 'directory' (the full path); a node that is
                only a path segment on the way to one does not.

        '.' (the walk's own root) becomes a single node named '.'; a
        path never splits into zero segments.
        """
        root = {"children": {}, "order": [], "directory": None}
        for directory in self.dir_order:
            part_list = [p for p in str(directory).split("/") if p] \
                        or ["."]
            node = root
            for part in part_list:
                if part not in node["children"]:
                    node["children"][part] = {"children": {}, "order": [],
                                              "directory": None}
                    node["order"].append(part)
                node = node["children"][part]
            node["directory"] = directory
        return root

    def _write_directory_tree(self, write, w):
        """
        RETURN: None. The tree written depth-first.

        THE CONNECTOR SAYS WHETHER ANYTHING FOLLOWS AT ITS OWN LEVEL:
        "+--- " where a sibling stands below it, "'--- " where none
        does -- so the last of a group closes it visibly.

        AND WHETHER THE NODE IS A PLACE OR A WAY TO ONE. A LEAF ends
        in one blank: "'--- suite/TEST". A JUNCTION -- no run of its
        own, sub-branches below it -- ends in a DOT: "'---. suite".
        The dot is a way, not a destination, and the eye can tell the
        two apart without reading the name.

        A JUNCTION IS SIX COLUMNS WIDE because the indent below it is
        four per level and must not step sideways; a leaf hangs
        nothing below it, so it may be five. A place that also
        branches keeps six.

        THE INK, where the ink is on: everything that is TREE -- the
        bars, the connectors, a junction's name -- is the directory's
        ORANGE, the one colour a directory has wherever it is named.
        A leaf's name is two things: the ROAD to it, green, with the
        '/' that ends the road; and the PLACE, the TEST directory
        itself, red.

        A NODE THAT ONLY LEADS SOMEWHERE IS NOT A LEVEL. A segment
        with exactly one child and no run of its own is joined to that
        child by '/' rather than given a line: 'adm/TEST' is one
        place, and drawing it as two says there was a choice at 'adm'
        that was never there. Where sub-branches DO exist the segment
        is named alone, because there the choice is real.

        The right side is '[OK]'/'[FAIL]' RIGHT-ALIGNED -- the two
        differ in width and their ends must still stand in one column
        -- with the '<ok>/<total>' count beyond it, right-aligned to
        'w'. The fill is DOT-SPACE: the tree already draws lines of
        its own, and a solid rule beside them reads as a second set
        of them.
        """
        def collapse(part, node):
            """
            RETURN: [0] str, the label -- the segment, joined by '/'
                        to each single onward child that carries no
                        run of its own.
                    [1] dict, the node the label ends at.
            """
            while node["directory"] is None and len(node["order"]) == 1:
                only = node["order"][0]
                part = "%s/%s" % (part, only)
                node = node["children"][only]
            return part, node

        def leaf_label(label):
            """
            RETURN: str, the leaf's name PAINTED: the way to it green,
                    the '/' included, and the last part -- the TEST
                    directory itself -- red. 'TEST' is the place; what
                    precedes it is the road, and the two are read
                    differently.
            """
            head, sep, tail = label.rpartition("/")
            return "%s%s" % (self.ink.ok(head + sep) if sep else "",
                             self.ink.fail(tail))

        def recurse(node, indent):
            child_n = len(node["order"])
            for i, part in enumerate(node["order"]):
                label, child = collapse(part, node["children"][part])
                last_f    = (i == child_n - 1)
                directory = child["directory"]
                branch_f  = bool(child["order"])
                #  THE CONNECTOR: a JUNCTION ends in a dot; a LEAF ends
                #  in one blank; a place that ALSO branches keeps two,
                #  so that the indent of what hangs below it -- four
                #  per level -- is unmoved. A leaf hangs nothing, so
                #  its width need not match.
                if directory is None:   end = ". "
                elif branch_f:          end = "  "
                else:                   end = " "
                connector = ("'---%s" if last_f else "+---%s") % end
                left      = "%s%s%s%s" % (TREE_INDENT, indent,
                                          connector, label)
                #  THE INK: everything that is TREE -- the indent's
                #  bars, the connector, a junction's name -- is the
                #  directory's orange; a leaf's name is road and
                #  place, green and red.
                tree_ink  = self.ink.directory("%s%s%s" % (TREE_INDENT,
                                                            indent,
                                                            connector))
                label_ink = leaf_label(label) if directory is not None \
                            else self.ink.directory(label)
                left_ink  = "%s%s" % (tree_ink, label_ink)
                if directory is not None:
                    good   = self.dir_good_db.get(directory)
                    tag    = "[OK]" if good else "[FAIL]"
                    counts = "%d/%d" % self._count(directory)
                    right, right_ink = _tag_and_count(tag, counts,
                                                      good, self.ink)
                    fill = max(w - len(left) - len(right) - 2, 1)
                    dots = _dot_space_fill(fill)
                    write("%s %s %s" % (left_ink, self.ink.dim(dots),
                                        right_ink))
                else:
                    write(left_ink)
                recurse(child, indent + ("    " if last_f else "|   "))
        #  ONE DIRECTORY IS NOT A TREE. A connector says "this branches
        #  from something"; with nothing to branch from, the name
        #  stands alone at the indent, and the right side as usual.
        if len(self.dir_order) == 1:
            directory = self.dir_order[0]
            good      = self.dir_good_db.get(directory)
            tag       = "[OK]" if good else "[FAIL]"
            counts    = "%d/%d" % self._count(directory)
            left      = "%s%s" % (TREE_INDENT, directory)
            right, right_ink = _tag_and_count(tag, counts, good, self.ink)
            fill = max(w - len(left) - len(right) - 2, 1)
            write("%s %s %s" % (left, self.ink.dim(_dot_space_fill(fill)),
                                right_ink))
            return
        recurse(self._directory_tree(), "")

    def _hint_key_list(self, directory):
        """
        RETURN: list, the directory's not-ok (directory, node) keys
                whose word is NOT 'differs from GOOD' -- a plain
                compare mismatch is the ordinary business a test suite
                exists to catch, not a hint. What earns a line here is
                why a test never got as far as a comparison at all:
                killed by the supervisor, a broken pipe, a missing
                pype script, an interpreter not found, and the like.
        """
        return [key for key in self._failure_key_list(directory)
                if phrase(self.report_db.get(key, self._verdict_of(key)))
                   != "differs from GOOD"]

    def tail(self):
        """
        RETURN: None. The DIRECTORIES roll-call, the FAULTS met (QUIET
        tier), and the HINTS block, last -- nothing in the SILENT
        tier.
        """
        if self.tier is E_Tier.SILENT: return
        write, ink, w = self.write, self.ink, self.width
        ok_total   = sum(1 for node_db in self.verdict_db.values()
                         for verdict in node_db.values()
                         if verdict == "ok")
        fail_total = sum(len(node_db)
                         for node_db in self.verdict_db.values()) - ok_total

        write("")
        write("=" * w)
        head_right = "%d ok, %d fail, %s" % (ok_total, fail_total,
                                             self._elapsed())
        write("DIRECTORIES%*s" % (w - len("DIRECTORIES"), head_right))
        write("-" * w)
        if not self.dir_order:
            write("    (no directory ran)")
        else:
            self._write_directory_tree(write, w)
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
                         if self._hint_key_list(d)
                         or self.frame_bad_db.get(d)]
        if not self.failure_summary_f: fail_dir_list = []
        if not fail_dir_list:
            self._write_refused(write, w)
            write("=" * w)
            return
        write("")
        write("=" * w)
        write("HINTS")
        write("-" * w)
        #  'HINTS' was 'FAILURES'. A plain 'differs from GOOD' is left
        #  out (see '_hint_key_list') and never carries a shape
        #  (GREW/SHRANK/DIVERGED, E-29): E-31 rules the RUN never
        #  takes one, since its compare aborts on the first mismatch
        #  and has read neither text whole. That stays 'hwut.report's
        #  question, unchanged.
        #
        #  EVERY PHRASE HERE COMES THROUGH 'word.phrase()' AND FROM
        #  NOWHERE ELSE -- one table to review, and one table to
        #  translate (D-6). A phrase written inline at a call site is
        #  a word no reviewer of the table would ever see.
        #
        #  THE COLUMNS READ AS THE FLOW'S DO: the application once,
        #  ':' beneath where it repeats, and THE APPLICATION'S OWN
        #  NAME setting where its choices stand. A new application is
        #  a new column, exactly as in the flow ('_run_body').
        #
        #  THE BRIEFING FOLLOWS THE WIDEST OF THEM, so the reasons
        #  stand in one column down the whole block: the reason is
        #  what this block exists to be read for, and a reason that
        #  moves is one the eye must hunt for on every line.
        brief_column = 0
        for directory in fail_dir_list:
            for role in self.frame_bad_db.get(directory, []):
                brief_column = max(brief_column,
                                   len("frame %s" % role) + BRIEF_GAP)
            for key in self._hint_key_list(directory):
                file, _, rest = _display_name(key[1]).partition(" ")
                choice        = rest.strip()
                width         = len(file)
                if choice: width += CHOICE_GAP + len(choice)
                brief_column  = max(brief_column, width + BRIEF_GAP)
        for directory in fail_dir_list:
            #  THE DIRECTORY, ONCE, and in the directory's colour.
            write(self._ink_dir(directory))
            last_file    = None
            choice_column = 0
            for role in self.frame_bad_db.get(directory, []):
                write("    %-*s%s"
                      % (brief_column, "frame %s" % role,
                         ink.fail(phrase("frame-failed"))))
            for key in self._hint_key_list(directory):
                name          = _display_name(key[1])
                file, _, rest = name.partition(" ")
                choice        = rest.strip()
                repeat_f      = (last_file == file)
                if not repeat_f: choice_column = len(file) + CHOICE_GAP
                last_file     = file
                shown         = ":" if repeat_f else file
                left          = "%-*s%s" % (choice_column, shown,
                                            choice) if choice else shown
                token = self.report_db.get(key, self._verdict_of(key))
                line  = "    %-*s%s" % (brief_column, left,
                                        ink.fail(phrase(token)))
                #  THE NUMBERS BESIDE THE WORD (O-19): which cap, the cap,
                #  the peak -- what a reader of a kill asks first.
                detail = self.detail_db.get(key)
                if detail is not None: line += "  (%s)" % detail
                cause = self.cause_db.get(key)
                if cause is not None: line += "  <- %s" % cause
                write(line)
        self._write_refused(write, w)
        write("=" * w)

    def _write_refused(self, write, w):
        """
        RETURN: None. The REFUSED block (E-41): everything not run, by
                directory, name and reason -- one block at the end,
                never a line in the flow. Nothing where nothing was
                refused.
        """
        if not self.refused_db: return
        write("")
        write("=" * w)
        write("REFUSED -- not run")
        write("-" * w)
        column = max(len(node) for pair_list in self.refused_db.values()
                     for node, _ in pair_list) + BRIEF_GAP
        for directory in self.dir_order:
            pair_list = self.refused_db.get(directory)
            if not pair_list: continue
            write(self._ink_dir(directory))
            for node, reason in pair_list:
                write("    %-*s%s" % (column, node, reason))


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
