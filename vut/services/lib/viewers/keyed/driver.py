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
from vut.services.lib.viewers.keyed.project import (project, banner,
                                                    row_of_cursor, E_Kind)
from vut.services.lib.viewers.keyed         import keymap

import asyncio
import io
import os
import tempfile

COLUMN_STEP_N = 8       # how far one 'h' or 'l' moves the view sideways


class KeyedDisplay(DisplayAdapter):
    """The keyed merge session, as the hub's DisplayAdapter."""

    def __init__(self, out=None, editor_argv=None, act_script=None,
                 width=None, color_f=None, **_ignored):
        """RETURN: None.

        'out' and the rest of '**_ignored' are accepted so that
        'driver_for' may pass the TUI tier's argument set unchanged;
        this driver draws on the terminal and needs none of them.
        'color_f' IS read: '--plain' was measured to leave this tier
        fully coloured, because the argument was swallowed here.
        """
        self.editor_argv = editor_argv
        self.act_script  = list(act_script) if act_script is not None else None
        self.width       = width
        self.plain_f     = (color_f is False)

        self.subject_name = None
        self.aspirant_f   = False
        self.pair_list    = []          # (line_n_s, line_n_n), 1-based, -1 absent
        self.state        = MergeState()
        self.leaving_act  = None
        self.search_term  = None
        self.column_i     = 0
        self.help_f       = False

        self.application   = None
        self.search_buffer = None
        self.subject_ctl   = None

    #  ---------------------------------------------------- the hub's calls

    def note_standing(self, aspirant_f):
        """RETURN: None. The choice's STANDING (B-14), told by the face
                   that measured it: no nominal stood when this session
                   opened, so a commit here is a FIRST BLESSING and the
                   banner says 'aspirant'.
        """
        self.aspirant_f = bool(aspirant_f)

    async def open(self, subject_name):
        """RETURN: None. The session for one subject begins; the
                   Application is built once, here, and survives every
                   round until 'close'.
        """
        self.subject_name = subject_name
        self.pair_list    = []
        self.column_i     = 0
        self.help_f       = False
        if self.act_script is None:
            self.application = self._build_application()

    async def present(self, item):
        """RETURN: None. One DOWN item; a line pair is kept for the
                   pairing, everything else is compare's rendering and
                   is not this driver's business.
        """
        line_n_s = getattr(item, "line_n_s", None)
        line_n_n = getattr(item, "line_n_n", None)
        if line_n_s is None or line_n_n is None: return
        self.pair_list.append((line_n_s, line_n_n))

    async def resolve(self, subject_name, subject_text, nominal_text):
        """RETURN: Resolution, what the author decided -- COMMIT with the
                   nominal as it stands, CANCEL, or REALIGN with the
                   nominal after his takes (or after '$EDITOR').
        """
        self.state = self._opening_state(subject_text, nominal_text)
        self.leaving_act = None

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

        return await self._resolution_of(self.leaving_act)

    async def close(self):
        """RETURN: None. The session ends; the Application goes with it."""
        self.application  = None
        self.pair_list    = []

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
        if act is E_Act.HELP:
            self.help_f = not self.help_f
            return
        if act in (E_Act.SCROLL_LEFT, E_Act.SCROLL_RIGHT):
            step_n = -COLUMN_STEP_N if act is E_Act.SCROLL_LEFT else COLUMN_STEP_N
            self.column_i = max(0, self.column_i + step_n)
            return
        if act.leaves_session_f():
            self.leaving_act = act
            if self.application is not None: self.application.exit()
            return
        self.state = reduce(self.state, act, argument)

    async def _resolution_of(self, act):
        """RETURN: Resolution, the hub's UP message for the act that ended
                   the turn. CANCEL where none did -- a session that ended
                   without deciding decided nothing.
        """
        nominal_text = "\n".join(self.state.nominal_line_list) + "\n"
        if act is E_Act.COMMIT:  return Resolution(E_Intent.COMMIT, nominal_text)
        if act is E_Act.REALIGN: return Resolution(E_Intent.REALIGN, nominal_text)
        if act is E_Act.EDIT:
            edited = await self._run_editor(nominal_text)
            if edited is None: return Resolution(E_Intent.REALIGN, nominal_text)
            return Resolution(E_Intent.REALIGN, edited)
        return Resolution(E_Intent.CANCEL)

    async def _run_editor(self, text):
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

        descriptor, path = tempfile.mkstemp(suffix=".nominal", text=True)
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

        body = VSplit([Window(self.subject_ctl, wrap_lines=False),
                       Window(width=1, char="|"),
                       Window(nominal_ctl, wrap_lines=False)])
        root = HSplit([
            Window(FormattedTextControl(
                       text=lambda: banner(self.state, self.subject_name or "")),
                   height=1, style="class:banner"),
            #  HELP REPLACES THE PANES, it does not share the screen
            #  with them: the table is twenty lines and was measured
            #  clipped at row eleven on an ordinary 24-row terminal.
            ConditionalContainer(body, filter=~helping),
            ConditionalContainer(
                Window(FormattedTextControl(text=lambda: self._help_text()),
                       style="class:help"),
                filter=helping),
            ConditionalContainer(
                Window(BufferControl(self.search_buffer), height=1,
                       style="class:search", dont_extend_height=True),
                filter=searching),
        ])

        #  THE TABLE YIELDS WHILE THE SEARCH LINE IS OPEN, or every
        #  bound letter is eaten before the buffer sees it.
        table_bindings = ConditionalKeyBindings(
                             keymap.key_bindings(self._on_act), ~searching)
        search_bindings = KeyBindings()

        @search_bindings.add("escape", filter=searching)
        def _(event):
            self.search_term = None
            event.app.layout.focus(self.subject_ctl)

        @search_bindings.add("c-c")
        def _(event):
            self.search_term = None
            self._apply(E_Act.CANCEL)

        bindings = merge_key_bindings([table_bindings, search_bindings])

        style = self._style(Style)
        layout = Layout(root, focused_element=self.subject_ctl)
        return Application(layout=layout, key_bindings=bindings,
                           style=style, full_screen=True, mouse_support=False)

    def _style(self, Style):
        """RETURN: Style, prompt_toolkit's, colourful on a terminal and
                   attribute-only under '--plain' -- reverse, bold and
                   underline still carry the cursor and the banner,
                   because a plain screen is not an unreadable one.
        """
        if self.plain_f:
            return Style.from_dict({
                "banner":         "reverse",
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
        return Style.from_dict({
            "banner":         "reverse",
            "help":           "bg:#222222 #dddddd",
            "search":         "bg:#333333 #ffffff",
            "cursor.active":  "reverse bold",
            "cursor.other":   "underline",
            "marked":         "bg:#444466",
            "target.virgin":  "bg:#333355",
            "target.latched": "bg:#553333 bold",
            "marker":         "#ffaa00 bold",
            "filler":         "#666666",
            "token":          "#00aa00 bold",
            "copied":         "#555555 italic",
            "absent":         "",
        })

    def _help_text(self):
        """RETURN: str, the keymap TABLE, which is what help is here --
                   a loop over 'KEYMAP', never prose that goes stale.
        """
        return "\n".join(("  " + line) for line in keymap.help_line_list()) \
               + "\n  (F1 closes this)"

    def _on_act(self, act):
        """RETURN: None. A key meant 'act'; search acts open the search
                   line, everything else reaches '_apply' at once.
        """
        if act in (E_Act.SEARCH_DOWN, E_Act.SEARCH_UP):
            self.search_term = act
            self.search_buffer.text = ""
            self.application.layout.focus(self.search_buffer)
            return
        self._apply(act)

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
            result.append((self._style_of(cell, pane), self._cut(cell.text)))
            result.append(("", "\n"))
        return result

    def _cut(self, text):
        """RETURN: str, the line as the sideways view shows it -- from
                   the column offset on, with a '<' in the first column
                   where something was scrolled off, so that a cut line
                   never reads as a short one.
        """
        if not self.column_i:            return text
        if len(text) <= self.column_i:   return "<"
        return "<" + text[self.column_i:]

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
        return Point(x=0, y=row_of_cursor(project(self.state), self.state.pane))
