"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE TUI TIER -- a terminal driver for display and merge.

DESCRIPTION
       A DRIVER like any other (README 11.4): it implements the
       DisplayAdapter sequence for one tool -- the terminal -- and owns
       its connection mechanics, which here are an output stream, an
       input function, and the author's own '$EDITOR'.

       THE CLIENT STAYS THIN. This driver renders DOWN items and asks
       three questions; it aligns NOTHING and diffs NOTHING -- an edit is
       answered with a REALIGN, and the fresh association comes from
       compare, through the hub (README 11.6). It dispatches on the item
       kind's NAME, exactly as a remote client does, so it never depends
       on compare's classes.

       DON'T BUILD AN EDITOR. On 'e' the working nominal is handed to
       the author's own editor ('$VISUAL', '$EDITOR', else 'vi') -- the
       git-commit idiom. Every terminal author already has an editor
       they are fast in; an embedded one would be worse than all of
       them.

       THE UNCHANGED EDIT STAYS LOCAL. An author who opened the editor
       and saved nothing has not answered -- re-prompt HERE, and never
       send the hub a no-progress REALIGN it would (rightly) end the
       session over.

       RENDERED META. What DOWN carries, this tier shows: the compare
       setup (ConfigInst), section boundaries, per-cell verdicts, the
       analogy provenance ('established at S:x/N:y' -- and, on a
       mismatch, WHERE the conflicting binding was made), the KIND of a
       mismatch where the relation names one (a type difference, a
       transposition), and constraint bindings. Meta that DOWN does not
       carry yet (e.g. a numeric's measured deviation) is compare's to
       emit, not this tier's to compute.

       TWO WAYS TO MARK, one renderer. The VERDICT marking (the merge
       view) marks what DID differ, by relation. The READING marking
       ('reading_f', the interpretation view -- 'hwut.diff FILE')
       marks what CAN vary, by tolerance kind:

           {numeric}   ~analogy~   <pattern>   !binding!   |nothing|

       Same rows, same notes, same banner -- an author moves between
       'hwut.diff' and 'hwut.accept.interactive' without relearning
       the picture.

       TWO COLUMNS ('--side-by-side', '-y'; E-49). One row per aligned
       pair: SUBJECT LEFT, NOMINAL RIGHT -- the direction a merge goes,
       subject into nominal, left into right -- the gutter between them
       saying the relation:

           ' ' equivalent   '~' tolerated   '|' differing
           '>' subject line, no nominal partner
           '<' nominal line, no subject partner

       The marks inside a cell are the stacked view's. A line wider
       than its column wraps onto continuation rows with blank numbers;
       a mark is closed at the wrap and reopened after it. The width is
       '--width', else the terminal's ('COLUMNS', else 80); each column
       is half of what remains after the numbers and the gutter, never
       below 20. Colour reaches a Windows console too: virtual-terminal
       processing is switched on for stdout where the console allows.
______________________________________________________________________________
"""
import io
import os
import re
import sys

from vut.services.lib import preferences
from vut.engine.display.colour      import ELEMENT_ROLE_DB
import shutil
import asyncio
import tempfile
from   contextlib import suppress

from   vut.engine.operations.interaction.port import (DisplayAdapter,
                                                      Resolution, E_Intent)


def annotate_for_editor(nominal_text, pair_list):
    """
    RETURN: (str, [str]), the nominal annotated for the author's editor,
            and THE ANNOTATION LINES THEMSELVES -- remembered, so
            'strip_annotations' removes exactly what was written.

    Before each nominal line the subject's paired line rides as a
    comment:

        ##ACTUAL:<line-n>: "....."          <line-n>: subject line number

    A subject line WITHOUT a nominal partner (an insertion) is annotated
    in sequence, before the next nominal line; a nominal line WITHOUT a
    subject partner (a deletion) is annotated '##ACTUAL:-: ""'. Lines
    the comparison never saw (blank, '##' comments) pass through
    unannotated -- they have no ACTUAL to name.
    """
    #  annotations keyed by the nominal line they precede; key 0 gathers
    #  what follows the last nominal line (trailing insertions)
    ann_db  = {}
    pending = []
    for line_n_s, line_n_n, subject_text in pair_list:
        if line_n_s == -1:
            line = '##ACTUAL:-: ""'
        else:
            line = '##ACTUAL:%i: "%s"' % (line_n_s, subject_text)
        pending.append(line)
        if line_n_n != -1:
            ann_db[line_n_n] = pending
            pending          = []
    trailing = pending

    annotation_list = []
    line_list       = []
    for n, line in enumerate(nominal_text.splitlines(), start=1):
        for annotation in ann_db.get(n, ()):
            line_list.append(annotation)
            annotation_list.append(annotation)
        line_list.append(line)
    for annotation in trailing:
        line_list.append(annotation)
        annotation_list.append(annotation)
    return "\n".join(line_list) + ("\n" if nominal_text.endswith("\n")
                                    or annotation_list else ""), \
           annotation_list


def strip_annotations(text, annotation_list):
    """
    RETURN: str, 'text' with the REMEMBERED annotation lines removed --
            each written line removed once, wherever it stands.

    Only what 'annotate_for_editor' wrote is removed: an author's own
    '##' comment stays, and so does an annotation line the author
    CHANGED -- a changed line is the author's text now ('##' lines are
    comments; the comparison never reads them either way). Membership
    is by MULTISET, not by order: one changed annotation must not
    shield the annotations after it.
    """
    from collections import Counter
    remaining = Counter(annotation_list)
    line_list = []
    for line in text.splitlines():
        if remaining[line] > 0:
            remaining[line] -= 1
            continue
        line_list.append(line)
    return "\n".join(line_list) + ("\n" if text.endswith("\n") else "")


def _ansi_enabled():
    """RETURN: True,  the console renders ANSI colour sequences -- on
                      Windows after enabling virtual-terminal processing
                      on the standard output handle, which the console
                      does not do by itself.
              False, it could not be enabled.
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
    except (AttributeError, OSError):
        return False


class TuiDisplay(DisplayAdapter):
    """THE TERMINAL DRIVER: renders each DOWN generation as text, and
    answers 'resolve' by asking the author -- edit, commit, or cancel.

        out          the stream the rendering goes to  (default: stdout)
        input_f      called for one answer; a test injects a script here
                     (default: builtins 'input'; EOF answers CANCEL)
        editor_argv  the editor command as a list; the nominal's file
                     path is appended (default: $VISUAL, $EDITOR, 'vi')
        color_f      ANSI colors; None = only when 'out' is a tty
        merge_f      False = display only; 'resolve' answers None and
                     the session is one round
        reading_f    True = mark by TOLERANCE KIND (the interpretation
                     view); False = mark by VERDICT (the merge view)
        side_by_side_f
                     True = TWO COLUMNS, subject LEFT, nominal RIGHT --
                     the direction a merge goes, subject into nominal;
                     False = the stacked S/N rows
        width        the rendering's width in columns for the two-column
                     view; None = the terminal's ('COLUMNS', else 80)

    In PLAIN rendering (no color) the marks are characters; with color
    they are painted instead. VERDICT view: bad '[..]', tolerated
    '~..~'. READING view: '{numeric}' '~analogy~' '<pattern>'
    '!binding!' '|nothing|' -- the legend line under the banner says so.
    """

    #  THE VERDICT MARKS -- what DID differ, by relation category.
    #  (bad is colored per side: subject red, nominal blue.)
    #  Each entry: (colour ROLE, plain mark begin, plain mark end). The
    #  colour itself is the person's preference ('bin/.hwut.conf',
    #  '~/.hwut.conf'; services E-78).
    VERDICT_MARK_DB = {
        "tolerated":           ("verdict.tolerated", "~", "~"),
    }
    #  THE READING MARKS -- what CAN vary, by tolerance kind.
    READING_MARK_DB = {
        "NUMERIC":             ("element.numeric", "{", "}"),
        "ANALOGY":             ("element.analogy", "~", "~"),
        "EQUIVALENCE_PATTERN": ("element.pattern", "<", ">"),
        "CONSTRAINT_BINDING":  ("element.binding", "!", "!"),
        "VISIBLE_NOTHING":     ("element.nothing", "|", "|"),
    }
    #  EVERY OTHER CELL wears its ELEMENT's colour on a terminal -- the
    #  category 'el:<KIND>' -- and no mark at all in plain rendering,
    #  where it is 'plain'.

    def __init__(self, out=None, input_f=None, editor_argv=None,
                 color_f=None, merge_f=True, reading_f=False,
                 side_by_side_f=False, width=None):
        self.out          = out if out is not None else sys.stdout
        self.input_f      = input_f if input_f is not None else input
        self.editor_argv  = editor_argv
        if color_f is None:
            color_f = getattr(self.out, "isatty", lambda: False)()
        if color_f: color_f = _ansi_enabled()
        self.color_f      = color_f
        self.side_by_side_f = side_by_side_f
        self.width        = width
        self.merge_f      = merge_f
        self.reading_f    = reading_f
        self.subject_name = None
        self.generation_n = 0        # DOWN generations rendered (= rounds)
        self.bad_pair_n   = 0        # differing pairs, current generation
        self.pair_list    = []       # (line_n_s, line_n_n, subject_text)
                                     # of the current generation -- the
                                     # editor's '##ACTUAL:' annotations
                                     # are written from this

    # -- the DisplayAdapter sequence -------------------------------------

    async def open(self, subject_name):
        """RETURN: None. The session for one subject begins; the round
        count starts afresh -- one driver may carry several subjects
        in turn ('hwut.diff', 'hwut.accept.interactive')."""
        self.subject_name = subject_name
        self.generation_n = 0

    async def present(self, item):
        """RETURN: None. Renders one DOWN item.

        Dispatch is on the KIND'S NAME, never on a class from compare --
        the same law a remote client obeys. A kind this tier does not
        know is SKIPPED, not an error: the protocol may grow, and an
        older renderer stays a correct renderer of what it knows.
        """
        method = getattr(self, "_render_" + type(item).__name__, None)
        if method is not None: method(item)

    async def resolve(self, subject_name, subject_text, nominal_text):
        """RETURN: Resolution, what the author decided -- REALIGN with an
                   edited nominal, COMMIT with the working one, COMMIT
                   with the subject taken whole ('t'), or CANCEL.
                   None, when this driver displays only ('merge_f' False).

        The no-change edit never leaves this method: an author who saved
        the nominal untouched is re-prompted HERE. The hub's no-progress
        guard is for a broken DRIVER; an undecided AUTHOR is not one.
        """
        if not self.merge_f: return None
        working = nominal_text
        while True:
            self._write("\n-- round %i: %i differing pair(s) --\n"
                        % (self.generation_n, self.bad_pair_n))
            self._write("[t]ake the subject whole   [e]dit the nominal   "
                        "[c]ommit the nominal as it stands   "
                        "[q]uit (cancel) ? ")
            try:
                answer = self.input_f("").strip().lower()
            except EOFError:
                answer = "q"

            if   answer == "c":
                return Resolution(intent=E_Intent.COMMIT,
                                  nominal_text=working)
            elif answer == "t":
                #  THE SUBJECT WHOLE, left into right: what the run
                #  printed becomes the nominal, unedited -- the
                #  interactive accept's plain 'yes' (E-51).
                return Resolution(intent=E_Intent.COMMIT,
                                  nominal_text=subject_text)
            elif answer == "q":
                return Resolution(intent=E_Intent.CANCEL)
            elif answer == "e":
                edited = await self._edit(working)
                if edited == working:
                    self._write("(no change -- nothing to realign)\n")
                    continue
                return Resolution(intent=E_Intent.REALIGN,
                                  nominal_text=edited)
            #  anything else: ask again

    async def close(self):
        """RETURN: None. The session ends, however it ended."""

    # -- the author's editor ---------------------------------------------

    async def _edit(self, working):
        """RETURN: str, the nominal as the author's editor left it, the
                   '##ACTUAL:' annotations REMOVED; 'working' unchanged
                   when the editor failed.

        WHAT THE AUTHOR EDITS IS ANNOTATED: before each nominal line the
        subject's paired line rides as a comment --

            ##ACTUAL:<line-n>: "....."

        '##' lines are comments and never considered for comparison, so
        even a stray survivor cannot tilt a verdict -- but the WRITTEN
        annotations are remembered and removed from the answer, so the
        nominal that leaves here is the author's text alone.
        """
        annotated, annotation_list = annotate_for_editor(working,
                                                         self.pair_list)
        answer = await self._run_editor(annotated)
        if answer is None: return working
        return strip_annotations(answer, annotation_list)

    async def _run_editor(self, text):
        """RETURN: str, the file as the author's editor left it;
                   None, when the editor failed.

        The text is written to a temporary file, the editor runs ON
        THE TTY (inherited stdio -- this driver's 'out' may be stderr,
        the editor's screen is its own affair), and whatever the file
        holds afterwards is the answer.
        """
        argv = self.editor_argv
        if argv is None:
            editor = os.environ.get("VISUAL") \
                     or os.environ.get("EDITOR") or "vi"
            argv = [editor]

        descriptor, path = tempfile.mkstemp(suffix=".nominal", text=True)
        try:
            with io.open(descriptor, "w", encoding="utf-8") as file_handle:
                file_handle.write(text)
            process = await asyncio.create_subprocess_exec(*argv, path)
            code    = await process.wait()
            if code != 0:
                self._write("(editor exited with %i -- nominal unchanged)\n"
                            % code)
                return None
            with io.open(path, "r", encoding="utf-8") as file_handle:
                return file_handle.read()
        finally:
            with suppress(OSError):
                os.unlink(path)

    # -- rendering, one method per DOWN kind -----------------------------

    def _render_ProtocolHeader(self, item):
        """RETURN: None. A generation begins: banner, counters reset.
        The leading newline separates rounds -- and detaches the banner
        from a prompt line in a captured (non-tty) rendering."""
        self.generation_n += 1
        self.bad_pair_n    = 0
        self.pair_list     = []
        title = self.subject_name if self.subject_name is not None else ""
        self._write("\n=[ %s ]=%s round %i\n"
                    % (title, "=" * max(1, 46 - len(title)),
                       self.generation_n))

    def _render_ConfigInst(self, item):
        """RETURN: None. The compare SETUP, one line -- an author judging
        a difference must see the rules it was judged under. In the
        READING view a legend follows: the marks say what CAN vary, so
        the legend is part of the rules."""
        if item.numeric_tolerance_ratio:
            numeric = "numeric=+/-%g" % item.numeric_tolerance_ratio
        else:
            numeric = "numeric=exact"
        self._write("setup | %s | analogy=%s '%s..%s' | whitespace=%s | "
                    "ignored '%s..%s'\n"
                    % (numeric,
                       "on" if item.analogy_f else "off",
                       item.analogy_begin_marker, item.analogy_end_marker,
                       "tolerant" if item.whitespace_f else "strict",
                       item.ignored_line_begin_marker,
                       item.ignored_line_end_marker))
        if self.reading_f:
            self._write("reading | {numeric} ~analogy~ <pattern> "
                        "!binding! |nothing|\n")

    def _render_SectionBeginInst(self, item):
        """RETURN: None. A chunk boundary, as compare drew it."""
        self._write("--[ %s ]--\n" % item.title)

    def _render_LinePairInst(self, item):
        """RETURN: None. One aligned pair -- ONE row when equivalent,
        an S row and an N row when the sides differ, and a note row per
        piece of provenance the cells carry."""
        self.pair_list.append(
            (item.line_n_s, item.line_n_n,
             "".join(cell.subject or "" for cell in item.cells_s)))

        s_n = "" if item.line_n_s == -1 else str(item.line_n_s)
        n_n = "" if item.line_n_n == -1 else str(item.line_n_n)

        if self.side_by_side_f:
            self._render_two_columns(item, s_n, n_n)
            return
        if self._is_good(item):
            text = self._side_text(item.cells_s, "subject") \
                   if s_n else self._side_text(item.cells_n, "nominal")
            #  THE READING HAS ONE STREAM, SO ONE NUMBER (E-56): it is
            #  the stream fed against ITSELF, so two columns would
            #  print the same number twice and invite the reader to
            #  look for a difference between them.
            if self.reading_f and s_n == n_n:
                self._write("  %4s | %s\n" % (s_n, text))
            else:
                self._write("  %4s %4s | %s\n" % (s_n, n_n, text))
        else:
            self.bad_pair_n += 1
            if s_n:
                self._write("S %4s %4s | %s\n"
                            % (s_n, "", self._side_text(item.cells_s,
                                                        "subject")))
            if n_n:
                self._write("N %4s %4s | %s\n"
                            % ("", n_n, self._side_text(item.cells_n,
                                                        "nominal")))
        for note in self._note_list(item):
            #  ONE STREAM, ONE PLACE (E-56): 'S:2/N:2' is the same
            #  line said twice where the reading fed a stream against
            #  itself.
            note = re.sub(r"S:(\d+)/N:\1", r"line \1", note) \
                   if self.reading_f else note
            if self.reading_f and s_n == n_n:
                self._write("  %4s | ^ %s\n" % ("", note))
            else:
                self._write("  %4s %4s | ^ %s\n" % ("", "", note))

    def _render_two_columns(self, item, s_n, n_n):
        """RETURN: None. One aligned pair as ONE row of two columns --
        subject left, nominal right, the gutter between them saying
        how they relate: ' ' equivalent, '~' tolerated, '|' differing,
        '>' a subject line with no nominal partner, '<' a nominal line
        with no subject partner. A line wider than its column wraps
        onto continuation rows with blank numbers; a note row rides
        below, spanning both columns."""
        good_f = self._is_good(item)
        if not good_f: self.bad_pair_n += 1
        if   not n_n: gutter = ">"
        elif not s_n: gutter = "<"
        elif good_f:
            gutter = "~" if any(self._category(c) == "tolerated"
                                for c in tuple(item.cells_s)
                                        + tuple(item.cells_n)) else " "
        else:         gutter = "|"
        column = self._column_width()
        left   = self._side_rows(item.cells_s, "subject", column) \
                 if s_n else [" " * column]
        right  = self._side_rows(item.cells_n, "nominal", column) \
                 if n_n else [" " * column]
        for k in range(max(len(left), len(right))):
            l = left[k]  if k < len(left)  else " " * column
            r = right[k] if k < len(right) else " " * column
            self._write(("%4s %s %s %4s %s"
                         % (s_n if k == 0 else "", l,
                            gutter if k == 0 else " ",
                            n_n if k == 0 else "", r)).rstrip() + "\n")
        for note in self._note_list(item):
            self._write("%4s ^ %s\n" % ("", note))

    def _column_width(self):
        """RETURN: int, one column's width: the rendering width minus
        the two number fields and the gutter, halved; never below 20."""
        width = self.width
        if width is None:
            width = shutil.get_terminal_size((80, 24)).columns
        return max(20, (width - 4 - 1 - 1 - 1 - 4 - 1) // 2)

    def _side_rows(self, cell_list, value_name, column):
        """RETURN: list[str], one side's line as rows of exactly 'column'
        visible characters -- wrapped where it is wider, padded where
        it is narrower -- each run of same-category cells marked once,
        as '_side_text' marks it, but with the mark closed and reopened
        at a wrap so that no colour or bracket spans a row break. In
        plain rendering the bracket marks take two columns of their
        own; the wrap counts them."""
        span_list = []
        for cell in cell_list:
            text     = getattr(cell, value_name) or ""
            category = self._category(cell)
            if span_list and span_list[-1][0] == category:
                span_list[-1][1] += text
            else:
                span_list.append([category, text])
        row_list, row, used = [], [], 0
        for category, text in span_list:
            if not text and category != "plain": continue
            cost = 0 if (self.color_f or category == "plain") else 2
            while text:
                room = column - used - cost
                if room <= 0:
                    row_list.append(self._joined(row, column, value_name))
                    row, used = [], 0
                    room = column - cost
                piece, text = text[:room], text[room:]
                row.append((category, piece)); used += len(piece) + cost
        row_list.append(self._joined(row, column, value_name))
        return row_list

    def _joined(self, row, column, value_name):
        """RETURN: str, one row's pieces marked and joined, padded to
        'column' visible characters."""
        piece_list, visible = [], 0
        for category, text in row:
            visible += len(text)
            if   category == "plain":
                piece_list.append(text)
            elif category == "bad":
                piece_list.append(self._paint(text, "verdict." + value_name,
                                              "[", "]"))
                visible += 0 if self.color_f else 2
            elif category.startswith("el:"):
                piece_list.append(self._paint(text, ELEMENT_ROLE_DB.get(
                                              category[3:], ""), "", ""))
            else:
                mark_db = self.READING_MARK_DB if self.reading_f \
                          else self.VERDICT_MARK_DB
                color, begin, end = mark_db[category]
                piece_list.append(self._paint(text, color, begin, end))
                visible += 0 if self.color_f else 2
        return "".join(piece_list) + " " * max(0, column - visible)

    def _render_EndOfStreamInst(self, item):
        """RETURN: None. The generation's end -- a closing rule."""
        self._write("%s\n" % ("=" * 60))

    # -- the small helpers -----------------------------------------------

    @staticmethod
    def _is_good(item):
        """RETURN: True, every cell's relation preserves equivalence
                   (its name says 'OK_...'); False, else.

        The name convention IS the interface here, as it is for any
        client: OK_* tolerates, everything else differs."""
        return all(c.relation_id.name.startswith("OK_")
                   for c in tuple(item.cells_s) + tuple(item.cells_n))

    def _category(self, cell):
        """RETURN: str, the cell's marking category under the active
                   view -- a READING_MARK_DB key or 'plain' when
                   reading; 'bad', 'tolerated' or 'plain' when judging.

        A VISIBLE-NOTHING relation is a TOLERANCE -- something visibly
        present was read as nothing -- so the verdict view marks it as
        one, not as plain equality."""
        if self.reading_f:
            name = cell.tolerance_id.name
            if name in self.READING_MARK_DB: return name
            return self._element_category(cell)
        name = cell.relation_id.name
        if not name.startswith("OK_"):
            return "bad"
        if name == "OK_TOLERATED" or "VISIBLE_NOTHING" in name:
            return "tolerated"
        return self._element_category(cell)

    def _element_category(self, cell):
        """RETURN: str, 'el:<KIND>' -- the cell's element kind, whose
                   colour it wears -- where colours are drawn.
                   'plain', where they are not: a plain rendering marks
                   no element."""
        if not self.color_f: return "plain"
        return "el:" + cell.tolerance_id.name

    def _side_text(self, cell_list, value_name):
        """RETURN: str, one side's line rebuilt from its cells, each RUN
                   of same-category cells marked once, by the active
                   view's mark table.

        ADJACENT CELLS OF ONE CATEGORY ARE ONE SPAN: '[appended by
        editor]' and never '[appended][ ][by][ ][editor]' -- the marks
        say WHERE a category holds, not how compare tokenised."""
        span_list = []                        # (category, text) runs
        for cell in cell_list:
            text     = getattr(cell, value_name) or ""
            category = self._category(cell)
            if span_list and span_list[-1][0] == category:
                span_list[-1][1] += text
            else:
                span_list.append([category, text])

        piece_list = []
        for category, text in span_list:
            if not text and category != "plain":
                #  A ZERO-WIDTH span (the empty counterpart of an
                #  insertion) would render as a bare mark pair; the
                #  OTHER side carries the visible mark.
                continue
            if   category == "plain":
                piece_list.append(text)
            elif category == "bad":
                piece_list.append(self._paint(text, "verdict." + value_name,
                                              "[", "]"))
            elif category.startswith("el:"):
                piece_list.append(self._paint(text, ELEMENT_ROLE_DB.get(
                                              category[3:], ""), "", ""))
            else:
                mark_db = self.READING_MARK_DB if self.reading_f \
                          else self.VERDICT_MARK_DB
                color, begin, end = mark_db[category]
                piece_list.append(self._paint(text, color, begin, end))
        return "".join(piece_list)

    def _paint(self, text, role, mark_begin, mark_end):
        """RETURN: str, 'text' in the colour the preferences give 'role'
                   when colours are on, wrapped in the plain marks
                   otherwise -- so a piped rendering carries the verdicts
                   too. The preferences are read only here, where a
                   colour is drawn: a pipe never reads them."""
        if self.color_f:
            return preferences.paint(text, preferences.load().color(role))
        return "%s%s%s" % (mark_begin, text, mark_end)

    @staticmethod
    def _note_list(item):
        """RETURN: [str], one note per piece of meta the pair's cells
                   carry: where an analogy binding was FIRST established
                   (and, on a mismatch, that the binding CONFLICTS with
                   that origin); a mismatch whose KIND the relation
                   names (a type difference, a transposition); and a
                   constraint binding entering the constraint space."""
        note_list = []
        seen      = set()

        #  THE KIND OF A MISMATCH, where the relation names one. Once
        #  per pair -- the mark already says WHERE.
        name_set = set(c.relation_id.name
                       for c in tuple(item.cells_s) + tuple(item.cells_n))
        if any(name.endswith("TYPE_DIFFERS") for name in name_set):
            note_list.append("type differs -- one side is a number, "
                             "the other is not")
        if "BAD_TRANSPOSE" in name_set:
            note_list.append("transposed -- present on both sides, "
                             "out of order")

        #  THE MEASUREMENT, where DOWN carries it: a numeric's measured
        #  deviation against the limit it stood against -- the number
        #  that decides widen-the-limit vs fix-the-code -- and the
        #  equivalence pattern that tolerated a text. (getattr: an older
        #  feeder without these fields still renders, minus the notes.)
        for meta in getattr(item, "numeric_list", ()):
            if meta.deviation == 0: continue
            if meta.deviation <= meta.limit:
                note_list.append("numeric: off by %g, within the limit "
                                 "of %g" % (meta.deviation, meta.limit))
            else:
                over = "%.1fx over" % (meta.deviation / meta.limit) \
                       if meta.limit else "the limit is zero"
                note_list.append("numeric: off by %g against a limit of "
                                 "%g (%s)"
                                 % (meta.deviation, meta.limit, over))
        for meta in getattr(item, "pattern_list", ()):
            key = ("pattern", meta.pattern)
            if key in seen: continue
            seen.add(key)
            note_list.append("pattern: matches '%s'" % meta.pattern)

        #  A CONSTRAINT BINDING is an event, not a difference: the value
        #  enters the constraint space (its verdict is compare's).
        for cell in tuple(item.cells_s) + tuple(item.cells_n):
            if cell.tolerance_id.name != "CONSTRAINT_BINDING": continue
            text = getattr(cell, "subject", None) \
                   or getattr(cell, "nominal", None) or ""
            key  = ("binding", text)
            if key in seen: continue
            seen.add(key)
            note_list.append("constraint binding %s -- the value enters "
                             "the constraint space" % text)

        def note(cell, own_value, partner_value):
            """RETURN: None. Appends 'cell's provenance note, once."""
            origin = cell.analogy_origin_line_number_pair
            if origin is None:                              return
            key = (own_value, partner_value,
                   origin.line_n_in_subject, origin.line_n_in_nominal)
            if key in seen:                                 return
            seen.add(key)
            place = "S:%s/N:%s" % (origin.line_n_in_subject,
                                   origin.line_n_in_nominal)
            if cell.relation_id.name.startswith("OK_"):
                note_list.append("analogy '%s' ~ '%s' -- established at %s"
                                 % (own_value, partner_value, place))
            else:
                note_list.append("CONFLICT: '%s' vs '%s' -- binding "
                                 "established at %s"
                                 % (own_value, partner_value, place))

        for cell in item.cells_s:
            partner = None
            if 0 <= cell.nominal_ref_i < len(item.cells_n):
                partner = item.cells_n[cell.nominal_ref_i].nominal
            note(cell, cell.subject, partner)
        for cell in item.cells_n:
            partner = None
            if 0 <= cell.subject_ref_i < len(item.cells_s):
                partner = item.cells_s[cell.subject_ref_i].subject
            note(cell, partner, cell.nominal)
        return note_list

    def _write(self, text):
        """RETURN: None. Everything rendered goes through here."""
        self.out.write(text)
