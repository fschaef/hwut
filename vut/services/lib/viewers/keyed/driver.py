"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE KEYED DRIVER -- the DisplayAdapter that puts the merge on a
         screen and reads keys off it.

DESCRIPTION
       THIS IS THE GLUE, AND ONLY THE GLUE. 'prompt_toolkit' owns the
       Windows and the key loop; every ruling lives in 'reduce', and
       this module's judgement is which style a cell's kind gets and
       where the two viewports stand.

       ONE VIEWPORT FOR TWO PANES. Each Window scrolls to keep its own
       control's cursor visible. Letting each report its own cursor was
       MEASURED to pull the panes apart: two screens down, the subject
       showed lines 20..41 against the nominal's 1..22, and a person was
       reading one line against another that never stood beside it. Both
       controls therefore report the SAME row -- the ACTIVE pane's --
       so the two viewports cannot drift. The other pane's cursor is
       still seen: it is painted, not scrolled to.

       THE COLUMN OFFSET IS THE DRIVER'S, NOT THE STATE'S. 'state.py'
       holds no viewport offset and must not: a second copy of a LINE
       offset is the classic bug of this shape. A COLUMN offset is not
       that -- 'prompt_toolkit' scrolls sideways by the cursor's column,
       and our controls hold their cursor at column 0, so nothing in the
       layout can ever move sideways by itself. 'h'/'l' were measured
       DEAD for exactly this reason. The offset is painting and lives
       where painting lives.

       THE KEYMAP YIELDS TO THE SEARCH LINE. The table is bound at
       Application level, so every bound letter was swallowed before the
       search buffer could see it: typing 'line 30' reached 'e', which
       is EDIT, and the session died in '$EDITOR'. The bindings are now
       conditional on the search line being closed, and the search line
       is only there while a search is being typed.

       THE APPLICATION IS BUILT IN 'open' AND TORN DOWN IN 'close',
       both OUTSIDE the hub's round loop (port.py kept them there on
       purpose). A REALIGN therefore refills the rows and runs the same
       Application again; the screen is not rebuilt.

       WHERE 'prompt_toolkit' WILL NOT IMPORT, 'driver_for' never
       reaches this module: it hands back the TUI tier and today's
       line-based session runs. A merge is never hard-failed for lack
       of an import.

       A TEST NEEDS NO TERMINAL. 'act_script' is a list of acts (or
       (act, argument) pairs) applied in order instead of reading keys;
       the session then resolves exactly as a person's keystrokes would
       have made it, and the driver's own logic is measured without a
       tty.
______________________________________________________________________________
"""
from vut.engine.operations.interaction.port import (DisplayAdapter,
                                                    Resolution, E_Intent)
from vut.services.lib.viewers.keyed.act     import E_Act, E_Pane
from vut.services.lib.viewers.keyed.state   import MergeState
from vut.services.lib.viewers.keyed.reduce  import reduce
from vut.services.lib.viewers.keyed.project import (project,
                                                    row_of_cursor, E_Kind,
                                                    pane_title)
from vut.services.lib.viewers.keyed         import keymap
from vut.services.lib.viewers.keyed         import element
from vut.services.lib.viewers.keyed         import report

from vut.services.lib                      import preferences
from vut.engine.display.colour             import ELEMENT_ROLE_DB

import asyncio
import io
import os
import tempfile

#  prompt_toolkit's style class -> the colour role of the preferences
#  (services E-78). The plain table below is not a preference: without
#  colour, attributes alone must keep the screen readable.
STYLE_ROLE_DB = {
    "lineno":               "keyed.lineno",
    "title.output":         "keyed.title-output",
    "title.output.active":  "keyed.title-output-active",
    "title.good":           "keyed.title-good",
    "title.good.active":    "keyed.title-good-active",
    "separator":      "keyed.separator",
    "status":         "keyed.status",
    "status.on":      "keyed.status-on",
    "status.off":     "keyed.status-off",
    "el.cursor":      "keyed.element-cursor",
    "el.bad.subject":     "keyed.mismatch",
    "el.bad.nominal":     "verdict.nominal",
    "el.line-diff.subject": "keyed.line-diff",
    "el.line-diff.nominal": "verdict.nominal",
    "help":           "keyed.help",
    "search":         "keyed.search",
    "cursor.active":  "keyed.cursor-active",
    "cursor.other":   "keyed.cursor-other",
    "marked":         "keyed.marked",
    "target.virgin":  "keyed.target-virgin",
    "target.latched": "keyed.target-latched",
    "marker":         "keyed.marker",
    "filler":         "keyed.filler",
    "token":          "keyed.token",
    "copied":         "keyed.spent",
}

COLUMN_STEP_N = 8       # how far one 'h' or 'l' moves the view sideways


#  A TAB IS DRAWN AS BLANKS to the next stop (E-87). MEASURED: a raw tab
#  reached the screen as 'prompt_toolkit''s blue '^I'.
TAB_N = 8


def _expanded(text, column):
    """RETURN: str, 'text' with its tabs expanded to TAB_N stops, as if
               it started at 'column'."""
    if "\t" not in text: return text
    return ("\0" * column + text).expandtabs(TAB_N)[column:]


class KeyedDisplay(DisplayAdapter):
    """The keyed merge session, as the hub's DisplayAdapter."""

    def __init__(self, out=None, editor_argv=None, act_script=None,
                 width=None, color_f=None, view_only_f=False,
                 pt_input=None, pt_output=None, **_ignored):
        """RETURN: None.

        'out' and the rest of '**_ignored' are accepted so that
        'driver_for' may pass the TUI tier's argument set unchanged;
        this driver draws on the terminal and needs none of them.
        'color_f' IS read: '--plain' was measured to leave this tier
        fully coloured, because the argument was swallowed here.
        'pt_input'/'pt_output' are 'prompt_toolkit''s own input and
        output, for a suite that types real keys without a terminal;
        None: the terminal's.
        """
        self.editor_argv = editor_argv
        self.act_script  = list(act_script) if act_script is not None else None
        self.width       = width
        self.plain_f     = (color_f is False)
        #  VIEW ONLY ('hwut.run.diff'): the same screen, the viewing keymap,
        #  and no act that changes the nominal.
        self.view_only_f = view_only_f
        self.keymap      = keymap.VIEW_KEYMAP if view_only_f else keymap.KEYMAP
        self.bad_pair_n  = 0

        self.subject_name = None
        self.aspirant_f   = False
        self.pair_list    = []          # (line_n_s, line_n_n), 1-based, -1 absent
        self.element_db   = {}          # (side, stripped text) -> [Piece]
        self.numeric_ratio = 0          # compare's, from its ConfigInst
        self.element_i    = None        # the element cursor, or None
        self.stderr_spoke_f   = False
        self.stderr_ignored_f = False
        self.pair_db      = []          # report.Pair per delivered pair (E-91)
        self.reporting_f  = False       # the 't' window is up
        self.report_row   = None        # the scroll cursor in that window; None: nothing to rest on
        self.count_text   = ""          # the '<number>' typed before 'g'
        self.element_at   = None        # (pane, line) it belongs to
        self.state        = MergeState()
        self.leaving_act  = None
        self.asking       = None        # the act a 'y' lets run: DONE | CANCEL
        self.search_term  = None
        self.column_i     = 0
        self.help_f       = False

        #  THE EDITING PANES (intend 21): GOOD typed into ('e'), or the
        #  tolerance in memory (<F5>). None: the panes are the merge's.
        self.editing       = None       # None | "good" | "tolerance"
        self.edit_text     = ""         # the pane's text where no screen runs
        self.edit_fault    = None       # why the tolerance text was not read
        #  THE TOLERANCE IN MEMORY: what the next round aligns under.
        #  'page_options' is the choice's own, to tell a change by.
        self.page_options      = None
        self.tolerance_options = None
        self.tried_options     = None   # tried by the pane, for the hub

        self.pt_input      = pt_input
        self.pt_output     = pt_output
        self.application   = None
        self.search_buffer = None
        self.edit_buffer   = None
        self.subject_ctl   = None

    #  ---------------------------------------------------- the hub's calls

    def note_stderr(self, spoke_f, ignored_f=False):
        """RETURN: None. What the foot says of the case's stderr (E-136):
        'spoke_f' -- its last run wrote there; 'ignored_f' -- the test's
        block declares 'tolerance { stderr_ignored = true }'. MEASURED:
        the engine called this and no viewer defined it, so the foot's
        warning never showed."""
        self.stderr_spoke_f   = bool(spoke_f)
        self.stderr_ignored_f = bool(ignored_f)

    def note_standing(self, aspirant_f):
        """RETURN: None. The choice's STANDING (B-14), told by the face
                   that measured it: no nominal stood when this session
                   opened, so a commit here is a FIRST BLESSING and the
                   banner says 'aspirant'.
        """
        self.aspirant_f = bool(aspirant_f)

    def note_tolerance(self, options):
        """RETURN: None. The choice's own compare configuration, told by
                   the merge door before the first round: the tolerance
                   pane opens on it, and a change is measured against it.
        """
        self.page_options      = options
        self.tolerance_options = options
        self.tried_options     = None

    def tolerance_changed_f(self):
        """RETURN: bool, True where the tolerance in memory reads
                   otherwise than the choice's own -- what the leaving
                   question asks about (intend 21, 2.7)."""
        if self.page_options is None or self.tolerance_options is None:
            return False
        from vut.engine.orchestrator.run.tolerance_text import leaf_db_of
        return leaf_db_of(self.page_options) != leaf_db_of(self.tolerance_options)

    async def open(self, subject_name):
        """RETURN: None. The session for one subject begins; the
                   Application is built once, here, and survives every
                   round until 'close'.
        """
        self.subject_name = subject_name
        self.pair_list    = []
        self.pair_db      = []
        self.bad_pair_n   = 0
        self.column_i     = 0
        self.help_f       = False
        if self.act_script is None:
            self.application = self._build_application()

    async def present(self, item):
        """RETURN: None. One DOWN item; a line pair is kept for the
                   pairing, everything else is compare's rendering and
                   is not this driver's business.
        """
        ratio = getattr(item, "numeric_tolerance_ratio", None)
        if ratio is not None and not hasattr(item, "line_n_s"):
            self.numeric_ratio = ratio       # compare's ConfigInst (E-87)
            #  A ROUND BEGINS HERE: compare's configuration is the first
            #  item of every delivery. MEASURED: without this, the pairs
            #  of every round were kept, and after one 'z' the report of
            #  a three-line text held six pairs.
            self.pair_db    = []
            self.bad_pair_n = 0
            return
        line_n_s = getattr(item, "line_n_s", None)
        line_n_n = getattr(item, "line_n_n", None)
        if line_n_s is None or line_n_n is None: return
        self.pair_list.append((line_n_s, line_n_n))
        cell_list = tuple(getattr(item, "cells_s", ())) \
                    + tuple(getattr(item, "cells_n", ()))
        if not all(c.relation_id.name.startswith("OK_") for c in cell_list):
            self.bad_pair_n += 1
        cells_s = tuple(getattr(item, "cells_s", ()))
        cells_n = tuple(getattr(item, "cells_n", ()))
        self.pair_db.append(report.Pair(line_n_s, line_n_n, cells_s, cells_n))
        self._elements_of(cells_s, "subject", cells_n)
        self._elements_of(cells_n, "nominal", cells_s)

    def _elements_of(self, cell_list, side, other_list):
        """RETURN: None. One side's line entered into 'element_db' under
                   (side, its STRIPPED text), as 'element.Piece's.

        BY TEXT, NOT BY INDEX: a take copies a subject line into the
        nominal and re-indexes the pairing, but the copy reads as its
        original does -- so a taken line wears its elements at once,
        before any REALIGN. STRIPPED, because compare's cells carry no
        leading blank (E-87).
        """
        piece_list = element.pieces_of_cells(cell_list, side, other_list)
        text = "".join(piece.text for piece in piece_list)
        if text.strip():
            self.element_db[(side, element.key_of(text))] = piece_list

    async def resolve(self, subject_name, subject_text, nominal_text):
        """RETURN: Resolution, what the author decided -- COMMIT with the
                   nominal as it stands, CANCEL, or REALIGN with the
                   nominal after his takes (or after '$EDITOR').
        """
        self.state = self._opening_state(subject_text, nominal_text)
        while True:
            self.leaving_act = None
            self.asking      = None
            if self.act_script is not None:
                #  CONSUMED, not replayed: a script spans rounds the way a
                #  person's keystrokes do, so what is left after a REALIGN
                #  is what the next round reads.
                while self.act_script and self.leaving_act is None:
                    each = self.act_script.pop(0)
                    act, argument = each if isinstance(each, tuple) else (each, None)
                    self._apply(act, argument)
            else:
                await self.application.run_async()

            resolution = await self._resolution_of(self.leaving_act)
            #  NOTHING CHANGED, NOTHING TO ALIGN: BACK TO THE SCREEN
            #  (intend 21, 5.2). A REALIGN carrying the nominal the round
            #  opened on is refused by the hub as NO PROGRESS, and the
            #  refusal is a CANCEL -- MEASURED: '$EDITOR' left without a
            #  change, a failing editor, and 'z' before any take each
            #  ended the whole merge, and a following 'q' never ran.
            if resolution.intent is E_Intent.REALIGN \
               and resolution.tolerance is None \
               and resolution.nominal_text.splitlines() == nominal_text.splitlines():
                if self.act_script is not None and not self.act_script:
                    return Resolution(E_Intent.CANCEL)
                continue
            return resolution

    async def close(self):
        """RETURN: None. The session ends; the Application goes with it.

        A VIEW keeps what it was shown: the delivery closes before
        'view' opens the screen on it.
        """
        if self.view_only_f: return
        self.application  = None
        self.pair_list    = []

    async def view(self, subject_name, subject_text, nominal_text):
        """RETURN: None. The screen, opened on the pairs delivered since
                   'open', for looking only; it ends on 'q', unasked.

        'act_script' stands in for the keys here as in 'resolve'.
        """
        self.subject_name = subject_name
        self.state        = self._opening_state(subject_text, nominal_text)
        self.leaving_act  = None
        if self.act_script is not None:
            while self.act_script and self.leaving_act is None:
                each = self.act_script.pop(0)
                act, argument = each if isinstance(each, tuple) else (each, None)
                self._apply(act, argument)
        else:
            if self.application is None:
                self.application = self._build_application()
            await self.application.run_async()
        self.application = None
        self.element_db  = {}

    #  ---------------------------------------------------------- the state

    def _opening_state(self, subject_text, nominal_text):
        """RETURN: MergeState, the state a round opens on -- both texts as
                   line lists, the pairing compare just delivered, the
                   cursors at the top, nothing marked, target virgin.

        WHAT IS SPENT SURVIVES A ROUND. The subject text does not change
        within a session, so the subject lines already copied are still
        copied after a REALIGN and are carried over (L-13).
        """
        pairing = {}
        for line_n_s, line_n_n in self.pair_list:
            if line_n_s == -1: continue
            pairing[line_n_s - 1] = None if line_n_n == -1 else line_n_n - 1
        self.pair_list = []

        return MergeState(subject_line_list = tuple(subject_text.splitlines()),
                          nominal_line_list = tuple(nominal_text.splitlines()),
                          pairing           = pairing,
                          copied_s          = self.state.copied_s,
                          aspirant_f        = self.aspirant_f)

    def _apply(self, act, argument=None):
        """RETURN: None. One act reaches the reducer; an act that ends
                   the turn is remembered for 'resolve' to answer, and
                   the two acts that are PAINTING ONLY -- the sideways
                   scroll and the help screen -- are answered here,
                   since no ruling of the merge depends on them.
        """
        #  A QUESTION AT THE FOOT TAKES THE NEXT KEY (r-11c): 'y' lets the
        #  asked act run, every other key drops the question and does
        #  nothing else -- a key pressed at a question is an answer.
        if self.asking is not None:
            asked, self.asking = self.asking, None
            if act is not E_Act.YES:
                self._redraw()
                return
            act = asked
        elif act in (E_Act.YES, E_Act.NO):
            return
        if act is E_Act.HELP:
            self.help_f = not self.help_f
            self._redraw()
            return
        if act in (E_Act.SCROLL_LEFT, E_Act.SCROLL_RIGHT):
            step_n = -COLUMN_STEP_N if act is E_Act.SCROLL_LEFT else COLUMN_STEP_N
            self.column_i = max(0, self.column_i + step_n)
            return
        #  A WINDOW OVER THE PANES TAKES THE KEYS (E-93): while help is
        #  up only F1 acts; while the report is up the movement keys
        #  scroll it, <enter> jumps to the line its row names, t and
        #  Ctrl-C leave -- and no accept, remove, undo or edit fires.
        if self.help_f:
            return
        #  AN EDITING PANE TAKES THE KEYS (intend 21): the text's own
        #  undo and redo, $EDITOR, <F5> -- nothing of the merge.
        if self.editing is not None:
            self._apply_editing(act, argument)
            return
        if act in (E_Act.EDIT_HERE, E_Act.TOLERANCE) and not self.view_only_f:
            self.reporting_f = False            # <F5> from the report, too
            self._open_edit("good" if act is E_Act.EDIT_HERE else "tolerance")
            return
        if act is E_Act.REPORT:
            self.reporting_f = not self.reporting_f
            self.report_row  = self._report_first_row() if self.reporting_f else None
            self._redraw()
            return
        if self.reporting_f:
            line_list = report.lines_of(self.pair_db)
            if act in (E_Act.MOVE_DOWN, E_Act.MOVE_UP,
                       E_Act.PAGE_DOWN, E_Act.PAGE_UP):
                #  THE MARKER MOVES OVER ELEMENT ROWS ONLY (E-94): never a
                #  heading, a blank or '(none)'.
                row_list = [i for i in range(len(line_list))
                            if report.line_pair_at(line_list, i) is not None]
                if row_list:
                    step = {E_Act.MOVE_DOWN: 1, E_Act.MOVE_UP: -1,
                            E_Act.PAGE_DOWN: 10, E_Act.PAGE_UP: -10}[act]
                    here = row_list.index(self.report_row) \
                           if self.report_row in row_list else -1
                    if here < 0: here = 0 if step > 0 else 0
                    self.report_row = row_list[max(0, min(here + step,
                                                          len(row_list) - 1))]
            elif act is E_Act.TAKE_RANGE:
                pair = report.line_pair_at(line_list, self.report_row)
                if pair is not None:
                    self.reporting_f = False
                    self.state = self.state.with_(pane=E_Pane.SUBJECT)
                    self._goto(pair[0])
            elif act is E_Act.CANCEL:
                self.reporting_f = False
            self._redraw()
            return
        if act is E_Act.GOTO:
            self._goto(argument)
            return
        if act in (E_Act.ELEMENT_NEXT, E_Act.ELEMENT_PREV):
            self._step_element(+1 if act is E_Act.ELEMENT_NEXT else -1)
            return
        if self.view_only_f and act not in keymap.VIEW_ACT_SET:
            return
        if act in (E_Act.ASK_SAVE, E_Act.ASK_QUIT):
            #  A VIEW HAS NOTHING TO SAVE, so nothing to ask about.
            if self.view_only_f:
                act = E_Act.CANCEL
            else:
                self.asking = E_Act.DONE if act is E_Act.ASK_SAVE \
                              else E_Act.CANCEL
                self._redraw()
                return
        if act.leaves_session_f():
            self.leaving_act = act
            if self.application is not None: self.application.exit()
            return
        self.state = reduce(self.state, act, argument)

    #  ------------------------------------------------ the editing panes

    def _open_edit(self, kind):
        """RETURN: None. The GOOD side becomes an editable text -- GOOD
                   itself ('good'), or the tolerance in memory with the
                   proposals below it ('tolerance'); the keymap yields
                   to it until <F5>.
        """
        if kind == "good":
            text = "\n".join(self.state.nominal_line_list) + "\n"
        else:
            text = self._tolerance_pane_text()
        self.editing    = kind
        self.edit_fault = None
        self._set_edit_text(text, fresh_f=True)
        if self.application is not None and self.edit_buffer is not None:
            if kind == "good":
                #  THE EDIT BEGINS WHERE THE CURSOR STOOD, not at the top.
                document = self.edit_buffer.document
                row = max(0, min(self.state.cursor_n, document.line_count - 1))
                self.edit_buffer.cursor_position = \
                    document.translate_row_col_to_index(row, 0)
            self.application.layout.focus(self.edit_buffer)
        self._redraw()

    def _tolerance_pane_text(self):
        """RETURN: str, the tolerance pane: the tolerance in memory, every
                   key, and the proposals this round's differences give
                   (intend 21, section 4)."""
        from vut.engine.compare.api                    import Configuration
        from vut.engine.orchestrator.run.tolerance_text import text_of
        from vut.services.lib.viewers.keyed.proposal    import proposal_db
        options = self.tolerance_options if self.tolerance_options is not None \
                  else Configuration()
        finder  = options.pattern_finder
        proposal = proposal_db(
                       self.pair_db,
                       numeric_ratio = finder.numeric_tolerance_ratio,
                       pattern_list  = tuple(finder.equivalent_pattern_list),
                       nothing_list  = tuple(finder.visible_nothing_pattern_list),
                       whitespace_f  = finder.whitespace_f)
        return text_of(options, proposal)

    def _apply_editing(self, act, argument):
        """RETURN: None. One act while a pane is edited: <F5> closes it,
                   <Esc> closes it discarding what was typed, 'c-z'/'c-y'
                   are the TEXT's undo and redo (a stack apart from the
                   merge's), <F6> ('c-e') hands the text to $EDITOR.
                   Everything else means nothing here.
        """
        if act is E_Act.CLOSE_EDIT:
            self._close_edit()
        elif act is E_Act.DISCARD:
            #  <Esc>: THE PANE CLOSES AS IF NEVER OPENED -- no round, the
            #  memory as it was (ruled: "<Esc> drop and done").
            self._end_edit()
        elif act is E_Act.TYPE:
            self._set_edit_text(argument or "")
        elif act in (E_Act.UNDO, E_Act.REDO) and self.edit_buffer is not None:
            if act is E_Act.UNDO: self.edit_buffer.undo()
            else:                 self.edit_buffer.redo()
        elif act is E_Act.EDIT:
            self._leave(E_Act.EDIT)
        self._redraw()

    def _close_edit(self):
        """RETURN: None. The editing pane closes -- <F5> (intend 21).

        GOOD: a changed text becomes the nominal, and the round ends as
        a REALIGN; an unchanged one closes and nothing else happens.
        THE TOLERANCE: the text is read by the header's own reader onto
        the tolerance in memory. A text that cannot be read keeps the
        pane OPEN, its fault in the status bar -- there is nothing to
        align under. A text that reads as the tolerance already held
        closes without a round; any other becomes the tolerance in
        memory and the round ends as a REALIGN under it: TRY.
        """
        text = self._edit_text()
        if self.editing == "good":
            line_tuple = tuple(text.splitlines())
            self._end_edit()
            if line_tuple != self.state.nominal_line_list:
                self.state = self.state.with_(nominal_line_list=line_tuple)
                self._leave(E_Act.REALIGN)
            return

        from vut.engine.compare.api                    import Configuration
        from vut.engine.orchestrator.run.tolerance_text import (configuration_of,
                                                               leaf_db_of)
        base = self.tolerance_options if self.tolerance_options is not None \
               else Configuration()
        options, fault = configuration_of(text, base)
        if fault is not None:
            self.edit_fault = fault
            return
        self._end_edit()
        if leaf_db_of(options) == leaf_db_of(base): return
        self.tolerance_options = options
        self.tried_options     = options
        self._leave(E_Act.REALIGN)

    def _end_edit(self):
        """RETURN: None. The panes are the merge's again."""
        self.editing    = None
        self.edit_fault = None
        if self.application is not None and self.subject_ctl is not None:
            self.application.layout.focus(self.subject_ctl)

    def _leave(self, act):
        """RETURN: None. The round ends with 'act'."""
        self.leaving_act = act
        #  AFTER $EDITOR THE SCREEN IS NOT RUNNING: nothing to exit then.
        if self.application is not None and self.application.is_running:
            self.application.exit()

    def _edit_text(self):
        """RETURN: str, the editing pane's text -- the buffer's where the
                   screen runs."""
        if self.edit_buffer is not None: return self.edit_buffer.text
        return self.edit_text

    def _set_edit_text(self, text, fresh_f=False):
        """RETURN: None. The editing pane holds 'text'; 'fresh_f' starts
                   the text's undo history anew (a pane just opened)."""
        self.edit_text = text
        if self.edit_buffer is None: return
        from prompt_toolkit.document import Document
        if fresh_f:
            self.edit_buffer.reset(Document(text, 0))
        else:
            self.edit_buffer.text = text

    async def _resolution_of(self, act):
        """RETURN: Resolution, the hub's UP message for the act that ended
                   the turn. CANCEL where none did -- a session that ended
                   without deciding decided nothing.
        """
        pane_editor_f = (act is E_Act.EDIT and self.editing is not None)
        if pane_editor_f:
            #  $EDITOR ON AN EDITING PANE: its exit ends the edit as <F5>
            #  would -- a fault keeps the pane open, with the text as the
            #  editor left it.
            edited = await self._run_editor(self._edit_text(),
                                            ".conf" if self.editing == "tolerance"
                                            else ".nominal")
            if edited is not None: self._set_edit_text(edited)
            self.leaving_act = None
            self._close_edit()
            act = self.leaving_act
        nominal_text = "\n".join(self.state.nominal_line_list) + "\n"
        if act is E_Act.DONE:    return Resolution(E_Intent.COMMIT, nominal_text)
        if act is E_Act.REALIGN:
            tried, self.tried_options = self.tried_options, None
            return Resolution(E_Intent.REALIGN, nominal_text, tolerance=tried)
        if act is None and pane_editor_f:
            #  THE EDITOR CHANGED NOTHING THE ROUND DEPENDS ON, or its text
            #  was refused and the pane stays open: the same round, the
            #  screen again -- MEASURED: this ended the merge as CANCEL.
            return Resolution(E_Intent.REALIGN, nominal_text)
        if act is E_Act.EDIT:
            edited = await self._run_editor(nominal_text)
            if edited is None: return Resolution(E_Intent.REALIGN, nominal_text)
            return Resolution(E_Intent.REALIGN, edited)
        return Resolution(E_Intent.CANCEL)

    async def _run_editor(self, text, suffix=".nominal"):
        """RETURN: str, the file as the author's editor left it.

                   None, where the editor failed OR COULD NOT BE RUN AT
                   ALL: the nominal stands as it was.

        A MISSING EDITOR IS A FAILURE, NOT A CRASH. 'vi' absent was
        measured to raise FileNotFoundError out of the key loop and take
        the whole session with it, traceback over the screen.
        """
        argv = self.editor_argv
        if argv is None:
            argv = [os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"]

        descriptor, path = tempfile.mkstemp(suffix=suffix, text=True)
        try:
            with io.open(descriptor, "w", encoding="utf-8") as file_handle:
                file_handle.write(text)
            try:
                process = await asyncio.create_subprocess_exec(*argv, path)
            except (OSError, ValueError):
                return None
            if await process.wait() != 0: return None
            with io.open(path, "r", encoding="utf-8") as file_handle:
                return file_handle.read()
        finally:
            try: os.unlink(path)
            except OSError: pass

    #  ------------------------------------------------- the prompt_toolkit

    def _build_application(self):
        """RETURN: Application, prompt_toolkit's, laid out as banner over
                   two panes over a search line that is there only while
                   a search is being typed -- every control reading its
                   text from 'project(self.state)' at repaint time.
        """
        from prompt_toolkit             import Application
        from prompt_toolkit.buffer      import Buffer
        from prompt_toolkit.layout      import (Layout, HSplit, VSplit,
                                                Window, FormattedTextControl,
                                                BufferControl,
                                                ConditionalContainer)
        from prompt_toolkit.styles      import Style
        from prompt_toolkit.filters     import Condition
        from prompt_toolkit.key_binding import (KeyBindings,
                                                ConditionalKeyBindings,
                                                merge_key_bindings)

        self.subject_ctl = FormattedTextControl(
            text=lambda: self._fragments(E_Pane.SUBJECT),
            get_cursor_position=lambda: self._cursor_position(),
            focusable=True)
        nominal_ctl = FormattedTextControl(
            text=lambda: self._fragments(E_Pane.NOMINAL),
            get_cursor_position=lambda: self._cursor_position(),
            focusable=False)

        #  MULTILINE IS FALSE so that Enter ACCEPTS. A multiline buffer
        #  inserts a newline and never calls the accept handler, so the
        #  term could never be applied.
        self.search_buffer = Buffer(accept_handler=self._on_search_accepted,
                                    multiline=False)
        searching = Condition(lambda: self.search_term is not None)
        helping   = Condition(lambda: self.help_f)
        reporting = Condition(lambda: self.reporting_f)

        #  EACH PANE IS A COLUMN: its title over its lines, the two
        #  columns of EQUAL weight (E-87). MEASURED: titles in a row of
        #  their own split by THEIR text's width and the panes by
        #  THEIRS, so 'GOOD' stood nowhere near the nominal.
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.data_structures import Point
        half = Dimension(weight=1)
        def column(pane, control):
            """RETURN: HSplit, one pane: its title, then its lines."""
            return HSplit([
                Window(FormattedTextControl(text=lambda: self._title(pane)),
                       height=1,
                       style=lambda: "class:title.%s%s" % (
                           "output" if pane is E_Pane.SUBJECT else "good",
                           ".active" if self.state.pane is pane else "")),
                Window(control, wrap_lines=False)], width=half)
        #  THE EDITING PANE COVERS GOOD'S LINES (intend 21): the same
        #  column, its title saying what is edited.
        editing = Condition(lambda: self.editing is not None)
        self.edit_buffer = Buffer(multiline=True)
        def column_of(pane):
            """RETURN: HSplit, one pane: its title, then its lines -- for
                       GOOD, the editing pane instead while one is open."""
            if pane is E_Pane.SUBJECT: return column(pane, self.subject_ctl)
            return HSplit([
                Window(FormattedTextControl(text=lambda: self._title(pane)),
                       height=1,
                       style=lambda: "class:title.good%s" % (
                           ".active" if self.state.pane is pane
                                        or self.editing is not None else "")),
                ConditionalContainer(Window(nominal_ctl, wrap_lines=False),
                                     filter=~editing),
                ConditionalContainer(Window(BufferControl(self.edit_buffer),
                                            wrap_lines=False),
                                     filter=editing)], width=half)
        body = VSplit([column_of(E_Pane.SUBJECT),
                       Window(width=1, char="|", style="class:separator"),
                       column_of(E_Pane.NOMINAL)])
        #  NO HEADER LINE (E-90): the test's name stands in the OUTPUT
        #  title, the keys in the bottom bar.
        root = HSplit([
            #  HELP REPLACES THE PANES, it does not share the screen
            #  with them: the table is twenty lines and was measured
            #  clipped at row eleven on an ordinary 24-row terminal.
            ConditionalContainer(body, filter=~helping & ~reporting),
            ConditionalContainer(
                Window(FormattedTextControl(
                           text=lambda: self._report_text(),
                           get_cursor_position=lambda: Point(
                               x=0, y=self.report_row or 0)),
                       style="class:help", always_hide_cursor=True),
                filter=reporting),
            ConditionalContainer(
                Window(FormattedTextControl(text=lambda: self._help_text()),
                       style="class:help"),
                filter=helping),
            ConditionalContainer(
                Window(BufferControl(self.search_buffer), height=1,
                       style="class:search", dont_extend_height=True),
                filter=searching),
            #  THE STATUS BAR (E-87): what the element cursor stands on,
            #  or what the cursor's line holds.
            ConditionalContainer(
                Window(FormattedTextControl(text=lambda: self._status()),
                       height=1, style="class:status"),
                filter=~searching),
        ])

        #  THE TABLE YIELDS WHILE THE SEARCH LINE IS OPEN, or every
        #  bound letter is eaten before the buffer sees it.
        table_bindings = ConditionalKeyBindings(
                             keymap.key_bindings(self._on_act, self.keymap),
                             ~searching & ~editing)
        #  THE EDITING PANE'S KEYS: 'prompt_toolkit''s basic editing --
        #  letters, Enter, Backspace, the arrows -- and the editing
        #  table AFTER it, since the last binding matching a key wins and
        #  the basic set binds <F5>, 'c-z', 'c-y', 'c-e' to nothing.
        from prompt_toolkit.key_binding.bindings.basic import load_basic_bindings
        edit_bindings = ConditionalKeyBindings(
                            merge_key_bindings([
                                load_basic_bindings(),
                                keymap.key_bindings(self._on_act,
                                                    keymap.EDIT_KEYMAP)]),
                            editing)
        search_bindings = KeyBindings()

        @search_bindings.add("escape", filter=searching)
        def _(event):
            self.search_term = None
            event.app.layout.focus(self.subject_ctl)

        @search_bindings.add("c-c", filter=searching)
        def _(event):
            self.search_term = None
            self._apply(E_Act.CANCEL)

        digit_bindings = KeyBindings()
        for digit in "0123456789":
            digit_bindings.add(digit, filter=~searching & ~editing)(
                lambda event, d=digit: self._on_digit(d))
        digit_bindings.add("g", filter=~searching & ~editing)(
            lambda event: self._on_goto())
        bindings = merge_key_bindings([table_bindings, search_bindings,
                                       digit_bindings, edit_bindings])

        style = self._style(Style)
        layout = Layout(root, focused_element=self.subject_ctl)
        return Application(layout=layout, key_bindings=bindings,
                           style=style, full_screen=True, mouse_support=False,
                           input=self.pt_input, output=self.pt_output)

    def _style(self, Style):
        """RETURN: Style, prompt_toolkit's, colourful on a terminal and
                   attribute-only under '--plain' -- reverse, bold and
                   underline still carry the cursor and the banner,
                   because a plain screen is not an unreadable one.
        """
        if self.plain_f:
            return Style.from_dict({
                "lineno":               "",
                "title.output":         "",
                "title.output.active":  "bold",
                "title.good":           "",
                "title.good.active":    "bold",
                "separator":      "",
                "status":         "reverse",
                "status.on":      "reverse bold",
                "status.off":     "reverse",
                "el.cursor":      "underline",
                "el.bad.subject":       "bold",
                "el.bad.nominal":       "bold",
                "el.line-diff.subject": "bold",
                "el.line-diff.nominal": "bold",
                "help":           "reverse",
                "search":         "reverse",
                "cursor.active":  "reverse bold",
                "cursor.other":   "underline",
                "marked":         "bold",
                "target.virgin":  "underline",
                "target.latched": "underline bold",
                "marker":         "italic",
                "filler":         "",
                "token":          "bold",
                "copied":         "italic",
                "absent":         "",
            })
        prefs    = preferences.load()
        style_db = {name: preferences.toolkit_style(prefs.color(role))
                    for name, role in STYLE_ROLE_DB.items()}
        style_db["absent"] = ""
        for kind, role in ELEMENT_ROLE_DB.items():
            style_db["el." + kind.lower()] = preferences.toolkit_style(prefs.color(role))
        return Style.from_dict(style_db)

    def _screen_width(self):
        """RETURN: int, the terminal's columns while the screen runs.
                   None, where no screen runs (a scripted session)."""
        if self.application is None: return None
        try:    return self.application.output.get_size().columns
        except Exception: return None                          # noqa: BLE001

    def _title(self, pane):
        """RETURN: list[(style, text)], one pane's heading, the driven
                   pane's in the banner's style."""
        style = "class:title.%s%s" % (
            "output" if pane is E_Pane.SUBJECT else "good",
            ".active" if self.state.pane is pane else "")
        if pane is E_Pane.NOMINAL and self.editing is not None:
            return [("class:title.good.active",
                     " GOOD -- editing" if self.editing == "good" else
                     " TOLERANCE -- in memory")]
        return [(style, pane_title(self.state, pane,
                                   self._channel_name(),
                                   self._differ_n()))]

    def _channel_name(self):
        """RETURN: str, the test's name for the OUTPUT title -- the
                   channel named, not its extension: 'test.sh .stderr'
                   becomes 'test.sh stderr', and '.stdout' is dropped
                   (E-92), it being the default one."""
        name = self.subject_name or ""
        for channel in (".stdout", ".stderr"):
            if name.endswith(channel):
                base = name[:-len(channel)].rstrip()
                return base if channel == ".stdout" else "%s %s" % (base,
                                                                    channel[1:])
        return name

    def _report_first_row(self):
        """RETURN: int, the first element row of the report; 0 where it
                   has none."""
        line_list = report.lines_of(self.pair_db)
        return next((i for i in range(len(line_list))
                     if report.line_pair_at(line_list, i) is not None), None)

    def _redraw(self):
        """RETURN: None. The screen -- foot included -- drawn again now
                   (E-94): a window that opened or closed changes what
                   the foot must say."""
        if self.application is not None: self.application.invalidate()

    def _report_text(self):
        """RETURN: list[(style, str)], the tolerance report (E-91), the
                   scroll row marked so 'prompt_toolkit' keeps it in view
                   -- the window scrolls with j/k, Ctrl-D/U (E-92)."""
        line_list = report.lines_of(self.pair_db)
        result = []
        for i, line in enumerate(line_list):
            #  NO CURSOR LINE WHERE NOTHING IS REPORTED (E-95).
            style = "class:title.good.active" \
                    if self.report_row is not None and i == self.report_row else ""
            result.append((style, line + "\n"))
        return result

    def _help_text(self):
        """RETURN: str, the keymap TABLE, which is what help is here --
                   a loop over 'KEYMAP', never prose that goes stale.
        """
        return "\n".join(("  " + line)
                         for line in keymap.help_line_list(self.keymap))

    def _on_act(self, act):
        """RETURN: None. A key meant 'act'; search acts open the search
                   line, everything else reaches '_apply' at once.
        """
        if act in (E_Act.SEARCH_DOWN, E_Act.SEARCH_UP):
            self.search_term = act
            self.search_buffer.text = ""
            self.application.layout.focus(self.search_buffer)
            return
        self.count_text = ""
        self._apply(act)

    def _on_digit(self, digit):
        """RETURN: None. One digit of a '<number>' prefix (E-91)."""
        self.count_text += digit

    def _on_goto(self):
        """RETURN: None. 'g' after digits goes to that line; a bare 'g'
                   does nothing (realign is 'z')."""
        count, self.count_text = self.count_text, ""
        if count: self._apply(E_Act.GOTO, count)

    def _on_search_accepted(self, buffer):
        """RETURN: bool, False -- the buffer is not to clear itself; the
                   term is applied and the panes take the focus back.
        """
        act, self.search_term = self.search_term, None
        self._apply(act, buffer.text)
        self.application.layout.focus(self.subject_ctl)
        return False

    def _fragments(self, pane):
        """RETURN: list[(style, text)], one pane's rows as prompt_toolkit
                   fragments, one line per row, styled by kind and flags
                   and cut at the column offset 'h'/'l' set.
        """
        result = []
        for row in project(self.state):
            cell = row.subject if pane is E_Pane.SUBJECT else row.nominal
            if pane is E_Pane.SUBJECT:
                #  LINE NUMBERS ON OUTPUT'S SIDE ONLY (E-91): the panes are
                #  aligned, so one gutter tells where both stand.
                result.append(("class:lineno", "%4s " % (cell.index + 1)
                                               if cell.index >= 0 else "     "))
            result.extend(self._cut(self._pieces_of(cell, pane)))
            result.append(("", "\n"))
        return result

    def _placed_of(self, text, pane):
        """RETURN: list[Piece], the elements of 'text' as compare read it
                   on 'pane''s side, placed onto the text -- the other
                   side's reading where this side has none (a taken
                   line), its verdicts then dropped: they were the
                   other side's.
                   None, where compare never read the text."""
        side  = "subject" if pane is E_Pane.SUBJECT else "nominal"
        other = "nominal" if side == "subject" else "subject"
        key   = element.key_of(text)
        piece_list = self.element_db.get((side, key))
        if piece_list is None:
            piece_list = self.element_db.get((other, key))
            if piece_list is None: return None
            piece_list = [p._replace(differs_f=False) for p in piece_list]
        return element.placed(text, piece_list)

    def _pieces_of(self, cell, pane):
        """RETURN: list[(style, text)], one cell as fragments -- a PLAIN
                   line split into its elements, each in its element's
                   colour, or in the VERDICT's where compare found it
                   differing (subject red, nominal blue, as the text
                   display draws them); the element cursor underlined.
                   Every other line, and every line under '--plain', one
                   fragment in the cell's style.

        A spent, marker, filler or token line keeps its kind's colour
        whole: that colour is the thing to see there.
        """
        style = self._style_of(cell, pane)
        if self.plain_f or cell.kind is not E_Kind.PLAIN:
            return [(style, cell.text.expandtabs(TAB_N))]
        piece_list = self._placed_of(cell.text, pane)
        if piece_list is None: return [(style, cell.text.expandtabs(TAB_N))]
        side    = "subject" if pane is E_Pane.SUBJECT else "nominal"
        chosen  = self._chosen_piece_i(cell, pane)
        prefix  = (style + " ") if style else ""
        #  WHEN IS A MISMATCH THE WHOLE LINE? Where every element that
        #  carries text differs -- compare gave one line-spanning cell,
        #  or the partner is a filler. A RED GROUND on a sub-token says
        #  'this token is wrong'; on a whole line it just floods, and on
        #  a line that FITS a nominal it lies (E-92). So a whole-line
        #  mismatch is a light BLUE PEN, no ground; only a token wrong
        #  amid right ones keeps the red.
        texted    = [p for p in piece_list if p.text.strip()]
        whole_f   = bool(texted) and all(p.differs_f for p in texted)
        #  AGAINST A FILLER THERE IS NOTHING TO DIFFER FROM (E-93): on a
        #  first accept compare pairs every OUTPUT line with '--?--' and
        #  says 'differs' -- MEASURED: the whole subject went blue. A
        #  line whose partner is a filler, or that has no partner, wears
        #  its normal colours; blue is for a line that differs from a
        #  REAL GOOD line.
        if whole_f and pane is E_Pane.SUBJECT:
            partner_n = self.state.pairing.get(cell.index)
            partner   = self.state.nominal_line_list[partner_n] \
                        if partner_n is not None \
                           and partner_n < len(self.state.nominal_line_list) \
                        else None
            if partner is None or partner.strip() == "--?--":
                whole_f = False
                piece_list = [p._replace(differs_f=False) for p in piece_list]
        result  = []
        column  = 0
        for i, piece in enumerate(piece_list):
            if not piece.text: continue
            if not piece.differs_f:
                klass = "class:el." + piece.kind.lower()
            elif whole_f:
                klass = "class:el.line-diff.%s" % side
            elif side == "subject":
                #  A TOKEN WRONG AMONG RIGHT ONES: the red ground (E-90).
                klass = "class:el.%s class:el.bad.subject" % piece.kind.lower()
            else:
                klass = "class:el.bad.nominal"
            if i == chosen: klass += " class:el.cursor"
            text    = _expanded(piece.text, column)
            column += len(text)
            result.append((prefix + klass, text))
        return result

    def _goto(self, line_n):
        """RETURN: None. The active pane's cursor to line 'line_n'
                   (1-based, as the gutter shows it; E-91), clamped to
                   the pane; a spent subject line sends it on to the
                   next reachable one."""
        try:    n = int(line_n) - 1
        except (TypeError, ValueError): return
        if self.state.pane is E_Pane.SUBJECT:
            n = max(0, min(n, len(self.state.subject_line_list) - 1))
            self.state = self.state.with_(cursor_s=self.state.reachable_s(n, +1))
        else:
            n = max(0, min(n, len(self.state.nominal_line_list) - 1))
            self.state = self.state.with_(cursor_n=n)

    def _differ_n(self):
        """RETURN: int, how many OUTPUT lines still stand against GOOD
                   (E-91): unpaired, or paired to a line that differs --
                   spent lines not counted, since their copy stands."""
        n = 0
        for i_s, text in enumerate(self.state.subject_line_list):
            if i_s in self.state.copied_s: continue
            if self.state.token_i_s() == i_s: continue
            if self.state.pairing.get(i_s) is None: n += 1; continue
            piece_list = self._placed_of(text, E_Pane.SUBJECT) or ()
            if any(p.differs_f for p in piece_list): n += 1
        return n

    def _cursor_line(self, pane=None):
        """RETURN: str, the text of the cursor's line in 'pane' (the
                   active one by default); '' where there is none."""
        pane = pane or self.state.pane
        line_list = self.state.subject_line_list if pane is E_Pane.SUBJECT \
                    else self.state.nominal_line_list
        i = self.state.cursor_s if pane is E_Pane.SUBJECT \
            else self.state.cursor_n
        return line_list[i] if 0 <= i < len(line_list) else ""

    def _here(self):
        """RETURN: tuple, where the element cursor would belong now."""
        return (self.state.pane, self.state.cursor_s, self.state.cursor_n,
                self.state.nominal_line_list)

    def _step_element(self, direction):
        """RETURN: None. The element cursor to the next (+1) or previous
                   (-1) element of the cursor's line that can vary or
                   differs; past the last, it leaves the line's elements
                   (the status bar then speaks of the line)."""
        piece_list = self._placed_of(self._cursor_line(), self.state.pane)
        index_list = element.meta_index_list(piece_list or ())
        if self.element_at != self._here(): self.element_i = None
        self.element_at = self._here()
        if not index_list:
            self.element_i = None
            return
        if self.element_i is None:
            self.element_i = index_list[0] if direction > 0 else index_list[-1]
            return
        later = [i for i in index_list if (i - self.element_i) * direction > 0]
        self.element_i = (min(later) if direction > 0 else max(later)) \
                         if later else None

    def _chosen_piece_i(self, cell, pane):
        """RETURN: int, the piece the element cursor stands on, where
                   'cell' is the cursor's line in the active pane.
                   None, elsewhere."""
        if pane is not self.state.pane or not cell.cursor_f: return None
        if self.element_at != self._here(): return None
        return self.element_i

    def _status(self):
        """RETURN: list[(style, text)], the bottom bar (E-93): the keys
                   that apply to what is ON SCREEN -- the help window
                   offers only its close, the report its jump and its
                   close, the panes the merge keys; an element the
                   cursor stands on is described instead.

        LEFT-ALIGNED, THE FUNCTION KEYS FIRST (intend 21, ruled: "have all
        function key shortcuts be displayed on the status bar on the left,
        left aligned"). Whole hints are dropped from the right where the
        width does not hold them. UNDO AND REDO SAY WHETHER THEY CAN
        ("highlight u=undo as soon as something can be undone; turn it
        back gray if nothing more can be undone"): lit where the stack
        holds something, grey where it is empty -- the merge's stacks in
        the panes, the text's own in an editing pane.
        """
        width = self._screen_width()
        if self.asking is not None:
            return [("class:status",
                     " %s   y=yes  any other key=no"
                     % ("SAVE GOOD AS IT STANDS AND LEAVE?"
                        if self.asking is E_Act.DONE
                        else "LEAVE WITHOUT SAVING?"))]
        if self.editing is not None and self.edit_fault is not None:
            return [("class:status",
                     " NOT READ -- %s   <F5>=try again  <Esc>=discard"
                     % self.edit_fault)]
        if self.editing is None and not self.help_f and not self.reporting_f:
            pane       = self.state.pane
            side       = "subject" if pane is E_Pane.SUBJECT else "nominal"
            piece_list = self._placed_of(self._cursor_line(), pane)
            if self.element_at == self._here() and self.element_i is not None \
               and piece_list is not None and self.element_i < len(piece_list):
                return [("class:status", " " + element.status_of(
                             piece_list[self.element_i], side,
                             self.numeric_ratio))]
        item_list = self._foot_item_list()
        #  THE STAIN IS MENTIONED (E-136), in the view as in the merge:
        #  stderr spoke and the block does not tolerate it. Tolerated
        #  stderr is no stain and takes no room here. The refusal is
        #  named only where an 's' could meet it.
        if self.editing is None and not self.stderr_ignored_f:
            if self.stderr_spoke_f and not self.view_only_f:
                item_list = [("STDERR SPOKE: 's' will be refused -- "
                              "declare 'stderr_ignored = true' ", None)] \
                            + item_list
            elif self.stderr_spoke_f:
                item_list = [("STDERR SPOKE, untolerated ", None)] \
                            + item_list
        return self._fragments_of(item_list, width)

    def _foot_item_list(self):
        """RETURN: list[(str, E_Act | None)], the hints of what is on
                   screen, function keys first."""
        if self.editing is not None:
            item_list = [("<F5>=done" if self.editing == "good"
                          else "<F5>=try+close", None),
                         ("<Esc>=discard", None),
                         ("<F6>=$EDITOR", None),
                         ("<c-z>=undo", E_Act.UNDO),
                         ("<c-y>=redo", E_Act.REDO)]
            if self.editing == "tolerance":
                item_list.append(("the lower line stands", None))
            return item_list
        if self.help_f:
            return [("<F1>=close", None)]
        if self.reporting_f:
            head = [] if self.view_only_f else [("<F5>=tolerance", None)]
            return head + [("t=close", None), ("<enter>=go there", None)]
        if self.view_only_f:
            return keymap.item_list_of(keymap.VIEW_FUNCTION_TUPLE, self.keymap) \
                   + keymap.item_list_of(keymap.VIEW_BASIC_TUPLE, self.keymap)
        #  WHAT MUST NOT FALL OFF THE RIGHT EDGE COMES FIRST: undo and
        #  redo (lit or grey), and done -- MEASURED at 110 columns: in the
        #  header's order they were the hints dropped.
        first = (E_Act.UNDO, E_Act.REDO, E_Act.ASK_SAVE, E_Act.ASK_QUIT)
        basic = keymap.item_list_of(keymap.BASIC_TUPLE, self.keymap)
        return keymap.item_list_of(keymap.FUNCTION_TUPLE, self.keymap) \
               + [item for act in first for item in basic if item[1] is act] \
               + [item for item in basic if item[1] not in first]

    def _can_f(self, act):
        """RETURN: bool, True where 'act' (UNDO or REDO) would do
                   something now -- on the text's own stack while a pane
                   is edited, on the merge's otherwise."""
        if self.editing is not None:
            if self.edit_buffer is None: return False
            stack = getattr(self.edit_buffer, "_undo_stack" if act is E_Act.UNDO
                                              else "_redo_stack", None)
            return bool(stack)
        stack = self.state.undo_stack if act is E_Act.UNDO else self.state.redo_stack
        return bool(stack)

    def _fragments_of(self, item_list, width):
        """RETURN: list[(style, text)], the hints left-aligned, two blanks
                   apart, as many whole ones as 'width' holds; undo and
                   redo lit or grey."""
        room = None if width is None else width - 2
        result, used = [("class:status", " ")], 1
        for text, act in item_list:
            gap = "  " if used > 1 else ""
            if room is not None and used + len(gap) + len(text) > room: break
            style = "class:status"
            if act in (E_Act.UNDO, E_Act.REDO):
                style += " class:status.on" if self._can_f(act) \
                         else " class:status.off"
            if gap: result.append(("class:status", gap))
            result.append((style, text))
            used += len(gap) + len(text)
        return result

    def _hints(self):
        """RETURN: str, the foot's key hints for the panes, as text."""
        return "".join(text for _, text in
                       self._fragments_of(self._foot_item_list(),
                                          self._screen_width()))[1:]

    def _cut(self, piece_list):
        """RETURN: list[(style, text)], the line as the sideways view
                   shows it -- from the column offset on, with a '<' in
                   the first column where something was scrolled off, so
                   that a cut line never reads as a short one.
        """
        if not self.column_i: return piece_list
        style      = piece_list[0][0] if piece_list else ""
        skip_n     = self.column_i
        result     = [(style, "<")]
        for piece_style, text in piece_list:
            if skip_n >= len(text):
                skip_n -= len(text)
                continue
            result.append((piece_style, text[skip_n:]))
            skip_n = 0
        return result

    def _style_of(self, cell, pane):
        """RETURN: str, the style class for this cell -- the flags in
                   order of what an author most needs to see.
        """
        active_f = (pane is self.state.pane)
        if cell.kind is E_Kind.ABSENT:  return "class:absent"
        if cell.cursor_f:
            return "class:cursor.active" if active_f else "class:cursor.other"
        if cell.kind is E_Kind.COPIED:  return "class:copied"
        if cell.target_f and pane is E_Pane.NOMINAL:
            return "class:target.virgin" if cell.virgin_f else "class:target.latched"
        if cell.marked_f:               return "class:marked"
        if cell.kind is E_Kind.MARKER:  return "class:marker"
        if cell.kind is E_Kind.FILLER:  return "class:filler"
        if cell.kind is E_Kind.TOKEN:   return "class:token"
        return ""

    def _cursor_position(self):
        """RETURN: Point, the row BOTH panes keep visible -- the row of
                   the ACTIVE pane's cursor.

        ONE ROW FOR TWO WINDOWS. Each reporting its own cursor was
        measured to let the viewports drift apart until a person read
        subject line 20 against nominal line 1.
        """
        from prompt_toolkit.data_structures import Point
        row_list = project(self.state)
        if self.editing == "good" and self.edit_buffer is not None:
            #  WHILE GOOD IS TYPED INTO, OUTPUT follows the edit cursor: the
            #  row of the GOOD line it stands in, as the last round aligned
            #  it -- a line typed since has no row yet, and OUTPUT stays.
            line_i = self.edit_buffer.document.cursor_position_row
            for y, row in enumerate(row_list):
                if row.nominal.index == line_i: return Point(x=0, y=y)
        return Point(x=0, y=row_of_cursor(row_list, self.state.pane))
