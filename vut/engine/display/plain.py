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
import os

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
#  WIDE ENOUGH FOR THE WIDEST TAG, so every '[...]' ends in ONE
#  column: '[OK]', '[FAIL]', '[NO GOOD]', '[REFUSED]'. The flow's
#  tags right-align by construction (the dotted fill is measured to
#  'width'); this is the closing block's padding, which is not.
TAG_WIDTH   = 9
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

#  TWO MODES, AND THE BADGE SAYS WHICH ONE YOU ARE IN (D-15).
#
#      NORMAL   every launch writes 'START', every termination writes
#               'END  '. Two lines per run, and the pair brackets the
#               time the run stood.
#      --brief  no launch is announced. One line per run, at its
#               termination, 'DONE '.
#
#  A HELD START IS GONE. The delay decided BY TIMING whether a run got
#  a pair or a single line, so whether a LINE EXISTED depended on the
#  speed of the machine -- the one thing a GOOD file may never hold,
#  and every suite that recorded a flow had to pin the delay to 0 to
#  escape it. The MODE decides it now, which is a thing the caller
#  states rather than a thing the morning decides.

#  THE COUNT BADGE (E-97): a START line -- a run that is slow -- ends
#  in 'running |n|', the runs standing at that instant, this one included,
#  whenever n is two or more. One run alone says nothing; the badge
#  appears exactly where parallelism does. The DONE line carries the
#  tag and nothing more. Lanes drawn at the right edge were built and
#  replaced by this: a person saw none, since they needed a wide,
#  inked console and overlapping slow runs at once.

#  THE BADGES OF THE FLOW, which come in runs and therefore elide, and
#  the mark that stands under a repeat: PLAIN WHITESPACE, as wide as a
#  badge, so the body column does not move and a repeated badge says
#  nothing the position does not already say.
#  END CLOSES A START; DONE STANDS ALONE. A run fast enough that its
#  START was never released is reported 'DONE '; one slow enough to
#  have been announced is closed with 'END  ', so the eye can pair
#  the two and a reader never hunts for a START that was never
#  written.
FLOW_BADGE_TUPLE = ("START", "DONE ", "END  ", "SKIP ")
#  THE BADGES THAT CLOSE A RUN: their '||n' excludes the line's own
#  run, so it says what stands open after it (D-18).
CLOSING_BADGE_TUPLE = ("DONE ", "END  ")
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
                 brief_f=False, write_log=None, write_wallflowers=None,
                 root=None):
        """
        RETURN: CPlainFlow writing flow lines through 'write', faults
                and notes through 'write_log', and -- in the SILENT
                tier -- faults through 'write_error'.

        'width'  the line width the dotted fill aims at -- a
                 CONSTRUCTOR argument, never sniffed from a terminal,
                 so a suite pins it.
        'ink'    the CInk of word.py; a transparent one where None.
        'write_log'
                 where the flow goes A SECOND TIME, plain ('--log
                 <file>', O-24): START, DONE, ERROR, NOTE, the
                 run-time markers, in order, without ink. None means
                 no log stands, and nothing is written anywhere but
                 the flow. A FAULT and a NOTE stand IN THE FLOW at
                 the moment they happen (O-24); they are not
                 marginalia and go to 'write_error' only under
                 SILENT, which has no flow.

        THE COLUMNS ARE ASKED FOR, never assumed. 'timing_f' puts a
        seconds column before the line, 'jobs_f' a '|<n>|' one; absent
        both, the flow carries the badge and the name alone -- what a
        person reads is what ran, not when it ran or how many stood
        beside it. 'detail_f' shows the SESSION and BUILD nodes,
        which are otherwise silent unless they FAIL. 'failure_summary_f'
        keeps the closing HINTS block, which stands by default.

        'brief_f' IS NOT A TIER. A tier says HOW MUCH is shown --
        details, provision nodes, faults. 'brief_f' says HOW A RUN IS
        ANNOUNCED: one line at its end instead of a pair bracketing
        it. The two are orthogonal and a VERBOSE brief run is a
        meaningful thing to ask for.

        'write_wallflowers'
                 where the SILENT files' paths go (X-SILENT): called
                 once, with the sorted list, and RETURNS the name the
                 list now stands under -- or None where it could not
                 be written. The note then names that file instead of
                 every path. None means no such sink stands, and the
                 note lists the paths itself.
        'root'   the directory the run was asked of, as the CALLER
                 spelt it; the stream's directories are relative to it.
                 None means the call directory itself.
        """
        self.write       = write
        self.write_error = write_error if write_error is not None \
                           else write
        self.write_log   = write_log
        self.write_wallflowers = write_wallflowers
        self.root        = root
        self.width       = width
        self.ink         = ink if ink is not None else CInk(False)
        self.tier        = tier
        self.timing_f    = timing_f
        self.jobs_f      = jobs_f
        self.detail_f    = detail_f
        self.failure_summary_f = failure_summary_f
        self.brief_f     = brief_f
        self.last_key    = None      # (directory, file) of the last
                                     # flow line that named a run
        self.choice_column = 0       # where the CURRENT application's
                                     # choices stand; reset by each
                                     # new application (_run_body)

        self.t0          = None      # first parseable 'when'
        self.when_first  = None      # first 'when', raw
        self.when_last   = None      # last 'when', raw
        self.parallel_n  = 0         # PROCESSES alive: ++ at birth,
                                     # -- at death. The '|n|' column's
                                     # number, and nothing else's.
        self.screen_n    = 0         # ANNOUNCEMENTS OPEN ON THIS
                                     # SCREEN: ++ when a START is
                                     # written, -- when its END closes
                                     # it. The '||n' tail's number in
                                     # NORMAL mode.
        self.began_set   = set()     # (directory, node) with run-begun
        self.announced_set = set()   # (directory, node) whose START
                                     # was actually WRITTEN, and which
                                     # therefore has an 'END  ' owed
                                     # to it. Empty for ever under
                                     # '--brief'.

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
        self.silent_db   = {}        # directory -> [node, ...]
        self.meta_n      = 0         # cases the standard label hid
        self.skip_n      = 0         # cases the wish did not want
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

        ':' STANDS ONLY WHERE A CHOICE IDENTIFIES THE LINE. A
        CHOICELESS run elided to ':' names NOTHING AT ALL -- the mark
        says 'the same application', and with no choice beside it
        nothing tells one line from the next. The digest filter
        'test-run.pype' has stated this law since it was written; the
        display did not, and D-15 made the gap universal: every END
        follows its own START, so in a suite of choiceless runs EVERY
        verdict line read ':'. MEASURED, it broke a reader --
        'services test-base-questions.py' collects what a wish
        selected by looking for a name beside a verdict, and found
        none.
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
        shown         = ":" if (repeat_f and choice) else file
        if not choice: return shown, shown
        body = "%-*s%s" % (self.choice_column, shown, choice)
        return body, body

    def _line(self, when, badge, badge_ink, body, body_ink,
              right="", right_ink="", tail=""):
        """
        RETURN: None. One flow line written: prefix, badge, body,
                then -- where a right part stands -- a dotted fill
                aiming at 'width', the right part, and 'tail' WITHIN
                that width (D-20): the line the terminal is asked for
                is the line that is drawn.

        A BADGE THAT REPEATS BECOMES AN ARROW (E-33). The first of a
        run of 'START's says 'START'; those under it say '---->', so
        the eye reads one block and the word marks where the block
        begins. Only the flow badges elide -- 'DIR', 'TREE' and the
        rest announce something and are never a run.
        """
        own_badge = badge
        if badge in FLOW_BADGE_TUPLE:
            if badge == self.last_badge:
                badge, badge_ink = BADGE_REPEAT, self.ink.dim(BADGE_REPEAT)
            else:
                self.last_badge = badge
        else:
            self.last_badge = None
        prefix, prefix_ink = self._prefix(when)
        #  THE PARALLELISM RIDES ALONG (E-97): after the verdict column
        #  on every flow line -- and INSIDE the width (D-20), so a line
        #  drawn on an 80-column terminal is 80 columns, not 85.
        if badge in FLOW_BADGE_TUPLE or badge == BADGE_REPEAT:
            tail += self._count_tail(own_badge)
        if not right:
            #  THE COUNT STANDS IN ONE COLUMN (E-97): a line with a
            #  verdict ends at 'width', so a line without one is padded
            #  to it before the count -- otherwise a START's '||n' sat
            #  where its name happened to end.
            head, head_ink = "%s%s %s" % (prefix, badge, body), \
                             "%s%s %s" % (prefix_ink, badge_ink, body_ink)
            if tail:
                pad   = " " * max(self.width - len(head) - len(tail), 0)
                head += pad
                head_ink += pad
            self._flow(head + tail, head_ink + tail)
            return
        fill = self.width - len(prefix) - len(badge) - 1 - len(body) \
               - len(right) - 2 - len(tail)
        dots = "." * max(fill, 1)
        self._flow("%s%s %s %s %s%s"
                   % (prefix, badge, body, dots, right, tail),
                   "%s%s %s %s %s%s"
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
        """
        RETURN: None. A 'START' line, written AT THE LAUNCH -- in
                NORMAL mode, where the tier speaks at all, and where
                the node is not a silent provision one.
                None and NO LINE under '--brief', which announces no
                launch at all; and none where the tier is QUIET or
                SILENT, which have no flow.

        THE LAUNCHER'S COUNT RISES EITHER WAY. 'parallel_n' is the
        process table's number and is kept whether or not anything is
        printed, because '--brief' has no screen count to fall back
        on and reports this one.
        """
        self.parallel_n += 1
        self.began_set.add((directory, node))
        if self.brief_f:                               return
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        self._band(when, directory)
        if self._provision_hidden_f(node_kind):        return
        body, body_ink = self._run_body(directory, node)
        #  THE SCREEN GAINS AN ANNOUNCEMENT, and the line that opens it
        #  counts itself. AN 'END  ' IS NOW OWED to this run, and
        #  'announced_set' is the record of that debt -- the badge of
        #  its closing line is decided by nothing else.
        self.screen_n += 1
        self.announced_set.add((directory, node))
        self._line(when, "START", self.ink.start("START"), body, body_ink)

    def _count_tail(self, badge="START"):
        """
        RETURN: str, '  ||3' -- HOW MANY ANNOUNCEMENTS STAND OPEN ON
                THIS SCREEN at the moment this line is written, THIS
                LINE'S OWN INCLUDED, after the verdict column and
                beyond the width math.
                '', only where the line announces no run at all -- a
                band, a fault, a frame; those never reach here.

        THE COUNT IS TAKEN UPON PRINT (E-97, superseded). It used to
        be taken at the EVENT, from 'parallel_n', which counts
        PROCESSES: a run living less than START_DELAY_SECONDS is born,
        counted and dies having never appeared as a START, so 'peak 9'
        stood against a screen showing two open STARTs. The number
        described 'ps'; the reader is looking at a screen.

        SO: ++ when a START is actually WRITTEN, -- when its END closes
        it, and a DONE -- which opens and closes on its own line --
        counts itself for the length of that line and no longer. The
        tail is therefore DERIVABLE FROM THE PRINTED TRACE ALONE: the
        reader can count the open STARTs above and get this number.
        '||1' is meaningful, '||0' impossible, and START, END and '||n'
        stand on ONE clock.

        NOTHING IS SUPPRESSED. The old '< 2 -> ""' is why the last two
        lines of every directory printed no tail at all.

        UNDER '--brief' THE NUMBER COMES FROM THE LAUNCHER, because
        there is no screen count to take: nothing is announced, so
        counting announcements would say '1' on every line. The
        process table is then the only witness, and it stands in the
        same column at the end of the same line (D-15).

        A CLOSING LINE DOES NOT COUNT ITSELF (ruled, D-18). 'END' and
        'DONE' say what stands open AFTER this run closed, so the
        number the reader sees beside a closing line is the work that
        outlives it: '||0' on the last line of a serial run, and never
        below zero. START still counts itself -- it has just opened.
        The elision to ':' is decided after this, so a closed line
        that lost its badge to the line above is still counted as the
        closing line it is.
        """
        count = self.parallel_n if self.brief_f else self.screen_n
        if badge in CLOSING_BADGE_TUPLE: count = max(count - 1, 0)
        return "  ||%d" % count

    def on_tick(self, when):
        """
        RETURN: None, and NOTHING WRITTEN. Nothing is held any more,
                so a tick has nothing to release (D-15).

        THE METHOD STAYS because it is the receiver protocol's, and a
        consumer calls it when no event arrived. It was the release
        of held STARTs; holding is gone with the delay that measured
        it, and a launch is announced at the launch.
        """
        return

    def on_run_ended(self, when, directory, node, node_kind, good,
                     verdict, cause=None, report=None, detail=None):
        """
        RETURN: None. ONE LINE, and its badge is decided by ONE
                QUESTION -- is a 'START' owed a closing?

                    'END  '  an announced run: its START stands above
                    'DONE '  a run that was never announced, which
                             under '--brief' is every run, and under
                             NORMAL only a provision node that failed
                             where its kind is otherwise silent
                    'SKIP '  a node that never ran at all

        THE FLOW SAYS [OK] OR [FAIL] AND NO MORE. A reason belongs to
        the reader who has stopped to ask why, and that reader is
        reading HINTS; carrying it here spends the width of every
        failing line on a phrase the eye is not scanning for while a
        run is still going.

        THE LAUNCHER'S COUNT FALLS LAST, after the line is written,
        so that a '--brief' 'DONE ' counts its own run -- the run was
        still working when its line was made. NORMAL's screen count
        falls by the same rule and in the same place.
        """
        key      = (directory, node)
        began_f  = key in self.began_set
        try:
            self._run_ended_line(when, directory, node, node_kind,
                                 good, verdict, cause, report, detail,
                                 began_f, key)
        finally:
            if began_f:
                self.began_set.discard(key)
                self.parallel_n = max(self.parallel_n - 1, 0)
            if key in self.announced_set:
                self.announced_set.discard(key)
                self.screen_n = max(self.screen_n - 1, 0)

    def _run_ended_line(self, when, directory, node, node_kind, good,
                        verdict, cause, report, detail, began_f, key):
        """
        RETURN: None. The one line 'on_run_ended' owes, written -- or
                nothing, where the tier has no flow or the node is a
                silent provision one that did not fail.

        SPLIT OUT SO THE COUNTS FALL EXACTLY ONCE. Every early return
        here is a path on which no line is written, and the caller's
        'finally' still lowers what the launch raised.
        """
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
        #  'announced_set' ANSWERS WHETHER A START STANDS ABOVE. It is
        #  the only question the badge asks, and under '--brief' the
        #  answer is always no.
        announced_f = key in self.announced_set
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
        #  'END  ' CLOSES THE 'START' THIS NODE OPENED; a node whose
        #  START was never released is 'DONE ' -- it finished before
        #  it was worth announcing.
        badge = "END  " if announced_f else "DONE "
        #  '||n' UPON PRINT. An 'END  ' closes an announcement that is
        #  still open while its own line is written, so it prints the
        #  count and falls afterwards (the caller's 'finally'). A
        #  'DONE ' opened none, so it opens one for the length of its
        #  own line -- except under '--brief', where the tail reads
        #  the launcher's count and the screen count is never used.
        if not announced_f and not self.brief_f:
            self.screen_n += 1
            self.announced_set.add(key)
        if good:
            self._line(when, badge, badge, body, body_ink,
                       "[OK]", self.ink.tag_ok("[OK]"))
        elif verdict == "unaccepted":
            #  NOT A RUN AT ALL (O-25, amended): the nominal carries
            #  lines nobody accepted, so nothing could be judged. The
            #  tag says WHAT IS WRONG WITH THE GOOD, not what the run
            #  found -- there was no run. HINTS says what to do.
            self._line(when, badge, badge, body, body_ink,
                       "[NO GOOD]", self.ink.tag_undecided("[NO GOOD]"))
        else:
            self._line(when, badge, badge, body, body_ink,
                       "[FAIL]", self.ink.tag_fail("[FAIL]"))

    def on_fault(self, when, directory, text):
        """
        RETURN: None. A fault stands IN THE FLOW, where START and DONE
                stand (O-24): 'ERROR' as a block on red, then the text,
                at the moment it happens. The directory is the band's
                to say, not the line's (see '_band').

        IT IS NOT HELD. A message kept for the end is lost to a
        signal and read out of sequence; one written in place
        survives a kill and reads beside the node it belongs to.
        QUIET keeps it for the tail's FAULTS block as well; SILENT
        has no flow, so it goes to 'write_error'.
        """
        #  THE BAND FIRST, and NO DIRECTORY COLUMN: a line whose
        #  directory the last band did not name is unattributable, and
        #  the band is the one place a directory is ever said ('_band').
        self._band(when, directory)
        prefix, prefix_ink = self._prefix(when)
        plain = "%sERROR %s" % (prefix, text)
        line  = "%s%s %s" % (prefix_ink, self.ink.block_error("ERROR"), text)
        self.fault_list.append((directory, plain))
        if self.tier is E_Tier.SILENT: self.write_error(line)
        else:                          self._flow(plain, line)

    def _flow(self, plain_line, ink_line):
        """RETURN: None. One line into the flow -- inked for the
        terminal -- and the SAME line, plain, into the log where one
        stands ('--log <file>', O-24). The log is the flow without
        the colour: START, DONE, ERROR, the run-time markers, in
        order, as they happened."""
        self.write(ink_line)
        if self.write_log is not None: self.write_log(plain_line)

    def on_report(self, when, directory, text):
        """RETURN: None. Determination's note, e.g. an empty selection
        -- a NOTE line in the flow, beside the run it concerns
        (O-24)."""
        if self.tier in (E_Tier.QUIET, E_Tier.SILENT): return
        self._band(when, directory)
        prefix, prefix_ink = self._prefix(when)
        self._flow("%sNOTE  %s" % (prefix, text),
                   "%sNOTE  %s" % (prefix_ink, text))

    def on_warning(self, when, text):
        """RETURN: None. A finding about the WISH that decides nothing
        -- a glob that met only silenced runs -- verbatim, in every
        tier but SILENT, before any run: it stands where it always
        stood on the page, ahead of the flow (O-26). The text carries
        its own 'WARNING:' -- determination's word, the same line
        'hwut.wishlist' prints -- and this renderer adds nothing."""
        if self.tier is E_Tier.SILENT: return
        self._flow(text, text)

    def on_refused(self, when, directory, node, text):
        """RETURN: None. Not run, by name and reason: a line IN THE FLOW
        where it happened, and the closing REFUSED block which names
        the reason. Both stand in every tier but SILENT -- a refusal is
        never marginalia, and a flow that showed nothing where a case
        was passed over read as though the case had never been asked
        for (B-17).

        The tag says WHICH refusal: an ASPIRANT carries '[ ?! ]' -- an
        acceptance stands and is incomplete -- where a case nothing was
        ever accepted for carries '[REFUSED]'."""
        self.refused_db.setdefault(directory, []).append((node, text))
        if self.tier is E_Tier.SILENT: return
        aspirant_f = "nobody has accepted" in text
        tag        = "[ ?! ]" if aspirant_f else "[REFUSED]"
        ink_tag    = (self.ink.tag_undecided(tag) if aspirant_f
                      else self.ink.tag_fail(tag))
        body, body_ink = self._run_body(directory, node)
        self._line(when, "DONE ", "DONE ", body, body_ink, tag, ink_tag)

    def on_silent(self, when, directory, node):
        """RETURN: None. A candidate no carrier speaks for: held for the
        closing SILENT note (X-SILENT). Not a refusal, not a fault --
        one note, at the end, in every tier but SILENT."""
        self.silent_db.setdefault(directory, []).append(node)

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

    def on_tree_done(self, when, good, fail_n, meta_n=0, skip_n=0):
        """RETURN: None. The stream's own closing word, held for the
        tail; a line in the VERBOSE tier alone. 'skip_n' is what the
        wish did not want; 'meta_n' what the standard label hid --
        both said once, at the end."""
        self.good_f = good
        self.fail_n = fail_n
        #  An absent optional arrives as None (receiver.py); zero is
        #  what it means.
        self.meta_n = meta_n or 0
        self.skip_n = skip_n or 0
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
        self._band(when, directory)
        line = "%s%s %s" % (prefix_ink, self.ink.block_error("ERROR"), text)
        plain = "%sERROR %s" % (prefix, text)
        self.fault_list.append((directory, plain))
        if self.tier is E_Tier.SILENT: self.write_error(line)
        else:                          self._flow(plain, line)

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
            self._write_silent(write, w)
            write("=" * w)
            self._write_final_bar(write, w)
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
        self._write_silent(write, w)
        write("=" * w)
        self._write_final_bar(write, w)

    def _write_final_bar(self, write, w):
        """
        RETURN: None. THE LAST TWO LINES OF A RUN: one line of numbers
                under the prefix 'RESULTS:', then one bordered bar of
                width 'w' whose green, yellow and red regions are the
                ok, skipped and failed counts IN PROPORTION -- the
                shape of the run, read before its numbers are. Nothing
                where nothing was counted.

            RESULTS: <ok> ok, <fail> fail, [<skip> skip,]
                     [<refused> refused,] [<meta> meta,] <s.ss> [sec]
            |    ok    |skip|   fail   |

        SIX NUMBERS, NONE DERIVABLE FROM ANOTHER. 'run' (ok + fail)
        and 'total' (run + skip) were dropped: a reader recomputes
        them faster than he reads them, and 'total' did not count the
        refused, so the word did not mean what it said. Each of skip,
        refused and meta appears only where it is not zero.

        THE PREFIX IS THE ANCHOR. A test whose subject is the run's
        FLOW and not its arithmetic tolerates this line with one
        eq-pattern, 'RESULTS: .*'; a test whose subject IS the line
        must not.

        Each region opens with '|' and carries its word CENTRED -- or
        its first letter where the word does not fit, or nothing where
        only the border fits. A NON-EMPTY REGION IS NEVER NARROWER
        THAN ITS BORDER: one failure among a thousand passes still
        shows, which proportion alone would round away.

        SKIPPED is what the wish did not want. REFUSED is what could
        not run for want of a nominal -- stated, and listed by name in
        the REFUSED block above. META is what the standard label hid.
        Neither refused nor meta is drawn: neither was ever selected.
        """
        ink = self.ink
        ok_n   = sum(1 for node_db in self.verdict_db.values()
                     for verdict in node_db.values() if verdict == "ok")
        run_n  = sum(len(node_db) for node_db in self.verdict_db.values())
        #  UNACCEPTED IS COUNTED APART (O-25): a nominal with lines
        #  nobody decided is not a failure of the software, and a
        #  count that folds it into 'fail' sends the eye after a
        #  regression that is not there.
        undecided_n = sum(1 for node_db in self.verdict_db.values()
                          for verdict in node_db.values()
                          if verdict == "unaccepted")
        fail_n = run_n - ok_n - undecided_n
        skip_n = self.skip_n
        refused_n = sum(len(pl) for pl in self.refused_db.values())
        if run_n == 0 and skip_n == 0 and refused_n == 0: return

        part_list = ["%d ok" % ok_n, "%d fail" % fail_n]
        if undecided_n: part_list.append("%d unaccepted" % undecided_n)
        if skip_n:      part_list.append("%d skip" % skip_n)
        if refused_n:   part_list.append("%d refused" % refused_n)
        if self.meta_n: part_list.append("%d meta" % self.meta_n)
        part_list.append("%s [sec]" % self._elapsed_seconds())
        write("")
        write("RESULTS: %s" % ", ".join(part_list))

        total = run_n + skip_n
        if total == 0: return
        span_db  = {"ok": ok_n, "skip": skip_n, "fail": fail_n + undecided_n}
        #  A NON-EMPTY REGION IS AT LEAST ITS BORDER. Reserve one
        #  column each, share the rest by proportion, and give the
        #  remainder to the largest. ONE COLUMN IS HELD BACK for the
        #  CLOSING MARKER: the bar is bounded on both sides, so its
        #  right edge is as plain as its left and a region that runs
        #  to the end does not look cut off.
        floor_db = {k: (1 if n else 0) for k, n in span_db.items()}
        free     = w - 1 - sum(floor_db.values())
        width_db = {k: floor_db[k] + (n * free) // total
                    for k, n in span_db.items()}
        rest     = w - 1 - sum(width_db.values())
        width_db[max(span_db, key=lambda k: span_db[k])] += rest

        def region(word, width):
            """RETURN: str, '|' then 'word' centred in what is left;
            the first letter where the word does not fit; the border
            alone where nothing else does; nothing where the region is
            empty."""
            if width <= 0: return ""
            room = width - 1
            text = word if len(word) + 2 <= room \
                   else word[0] if room >= 1 else ""
            left = (room - len(text)) // 2
            return "|" + " " * left + text + " " * (room - left - len(text))

        #  THE CLOSING MARKER wears the ground of the LAST non-empty
        #  region, so the bar's colour runs to its own edge.
        last = "fail" if fail_n else "skip" if skip_n else "ok"
        paint_db = {"ok": ink.ground_ok, "skip": ink.ground_skip,
                    "fail": ink.ground_fail}
        write(ink.ground_ok  (region("ok",   width_db["ok"]))
              + ink.ground_skip(region("skip", width_db["skip"]))
              + ink.ground_fail(region("fail", width_db["fail"]))
              + paint_db[last]("|"))

    def _elapsed_seconds(self):
        """
        RETURN: str, the whole stream's span in seconds, two decimals
                ('58.23'); '-' where no event arrived or a 'when' does
                not parse.
        """
        if self.when_last is None: return "-"
        try:
            t0 = datetime.fromisoformat(str(self.when_first))
            t1 = datetime.fromisoformat(str(self.when_last))
            return "%.2f" % (t1 - t0).total_seconds()
        except (TypeError, ValueError):
            return "-"

    def _write_silent(self, write, w):
        """
        RETURN: None. ONE NOTE at the end on every file no carrier
                speaks for, each by its path RELATIVE TO THE DIRECTORY
                THE RUN WAS CALLED IN, and the two lines that settle
                them: ignore them, or name one under 'apps'. The paths
                go to 'write_wallflowers' where it stands and takes
                them, and the note names that file; else the note
                lists them. Nothing where nothing was silent.
        """
        if not self.silent_db: return
        path_list = sorted(
            os.path.relpath(os.path.join(self.root or "", directory, node))
            for directory, node_list in self.silent_db.items()
            for node in node_list)
        list_name = self.write_wallflowers(path_list) \
                    if self.write_wallflowers is not None else None
        write("")
        for line in wallflower_note_list(path_list, list_name):
            write(line)

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


def wallflower_note_list(path_list, list_name):
    """
    RETURN: list[str], the NOTE on the files no carrier speaks for
            (X-SILENT): their count, where they are listed, and the two
            ways to settle them -- naming 'list_name' where the paths
            stand in that file, else naming every path of 'path_list'.
            Spoken alike by every face that finds them.
    """
    head = "NOTE  %d file(s) carry no 'hwut { }' and stand under no " \
           "'apps'" % len(path_list)
    if list_name is not None:
        line_list = ["%s -- listed in %s" % (head, list_name),
                     "      helpers?  hwut.config.ignore $(cat %s)"
                     % list_name]
    else:
        line_list = [head + ":"] \
                    + ["          %s" % path for path in path_list] \
                    + ["      helpers?  hwut.config.ignore %s"
                       % " ".join(path_list)]
    return line_list + ["      a test?   name it under 'apps' in its "
                        "directory's hwut.conf"]


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
