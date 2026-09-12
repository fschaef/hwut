"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE KEYED DRIVER -- the DisplayAdapter that puts the merge on a
         screen and reads keys off it.

DESCRIPTION
       THIS IS THE GLUE, AND ONLY THE GLUE. 'prompt_toolkit' owns the
       Windows, the scrolling and the key loop; every ruling lives in
       'reduce', and this module's whole judgement is which style a
       cell's kind gets. The projection is pushed into the controls ONE
       WAY: they call back into 'project' on every repaint, and our
       state never reads a viewport offset back.

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


class KeyedDisplay(DisplayAdapter):
    """The keyed merge session, as the hub's DisplayAdapter."""

    def __init__(self, out=None, editor_argv=None, act_script=None,
                 width=None, **_ignored):
        """RETURN: None.

        'out' and the rest of '**_ignored' are accepted so that
        'driver_for' may pass the TUI tier's argument set unchanged;
        this driver draws on the terminal and needs none of them.
        """
        self.editor_argv = editor_argv
        self.act_script  = list(act_script) if act_script is not None else None
        self.width       = width

        self.subject_name = None
        self.pair_list    = []          # (line_n_s, line_n_n), 1-based, -1 absent
        self.state        = MergeState()
        self.leaving_act  = None
        self.search_term  = None

        self.application  = None
        self.search_buffer = None

    #  ---------------------------------------------------- the hub's calls

    async def open(self, subject_name):
        """RETURN: None. The session for one subject begins; the
                   Application is built once, here, and survives every
                   round until 'close'.
        """
        self.subject_name = subject_name
        self.pair_list    = []
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
        """
        pairing = {}
        for line_n_s, line_n_n in self.pair_list:
            if line_n_s == -1: continue
            pairing[line_n_s - 1] = None if line_n_n == -1 else line_n_n - 1
        self.pair_list = []

        return MergeState(subject_line_list = tuple(subject_text.splitlines()),
                          nominal_line_list = tuple(nominal_text.splitlines()),
                          pairing           = pairing)

    def _apply(self, act, argument=None):
        """RETURN: None. One act reaches the reducer; an act that ends
                   the turn is remembered for 'resolve' to answer.
        """
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

                   None, where the editor failed: the nominal stands as it
                   was.
        """
        argv = self.editor_argv
        if argv is None:
            argv = [os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"]

        descriptor, path = tempfile.mkstemp(suffix=".nominal", text=True)
        try:
            with io.open(descriptor, "w", encoding="utf-8") as file_handle:
                file_handle.write(text)
            process = await asyncio.create_subprocess_exec(*argv, path)
            if await process.wait() != 0: return None
            with io.open(path, "r", encoding="utf-8") as file_handle:
                return file_handle.read()
        finally:
            try: os.unlink(path)
            except OSError: pass

    #  ------------------------------------------------- the prompt_toolkit

    def _build_application(self):
        """RETURN: Application, prompt_toolkit's, laid out as banner over
                   two panes over a search line -- every control reading
                   its text from 'project(self.state)' at repaint time.
        """
        from prompt_toolkit             import Application
        from prompt_toolkit.buffer      import Buffer
        from prompt_toolkit.layout      import (Layout, HSplit, VSplit,
                                                Window, FormattedTextControl,
                                                BufferControl)
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.styles      import Style
        from prompt_toolkit.filters     import Condition
        from prompt_toolkit.key_binding import KeyBindings

        subject_ctl = FormattedTextControl(
            text=lambda: self._fragments(E_Pane.SUBJECT),
            get_cursor_position=lambda: self._cursor_position(E_Pane.SUBJECT),
            focusable=True)
        nominal_ctl = FormattedTextControl(
            text=lambda: self._fragments(E_Pane.NOMINAL),
            get_cursor_position=lambda: self._cursor_position(E_Pane.NOMINAL),
            focusable=False)

        self.search_buffer = Buffer(accept_handler=self._on_search_accepted)
        search_active      = Condition(lambda: self.search_term is not None)

        body = VSplit([Window(subject_ctl, wrap_lines=False),
                       Window(width=1, char="|"),
                       Window(nominal_ctl, wrap_lines=False)])
        root = HSplit([
            Window(FormattedTextControl(
                       text=lambda: banner(self.state, self.subject_name or "")),
                   height=1, style="class:banner"),
            body,
            Window(BufferControl(self.search_buffer), height=1,
                   style="class:search", dont_extend_height=True),
        ])

        bindings = keymap.key_bindings(self._on_act)
        search_bindings = KeyBindings()

        @search_bindings.add("escape")
        def _(event):
            self.search_term = None
            event.app.layout.focus(subject_ctl)

        style = Style.from_dict({
            "banner":         "reverse",
            "search":         "bg:#333333 #ffffff",
            "cursor.active":  "reverse bold",
            "cursor.other":   "underline",
            "marked":         "bg:#444466",
            "target.virgin":  "bg:#333355",
            "target.latched": "bg:#553333 bold",
            "marker":         "#888888 italic",
            "filler":         "#666666",
            "token":          "#00aa00 bold",
            "absent":         "",
        })
        layout = Layout(root, focused_element=subject_ctl)
        return Application(layout=layout, key_bindings=bindings,
                           style=style, full_screen=True, mouse_support=False)

    def _on_act(self, act):
        """RETURN: None. A key meant 'act'; search acts open the search
                   line, everything else reaches the reducer at once.
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
        self.application.layout.focus_previous()
        return False

    def _fragments(self, pane):
        """RETURN: list[(style, text)], one pane's rows as prompt_toolkit
                   fragments, one line per row, styled by kind and flags.
        """
        result = []
        for row in project(self.state):
            cell = row.subject if pane is E_Pane.SUBJECT else row.nominal
            result.append((self._style_of(cell, pane), cell.text))
            result.append(("", "\n"))
        return result

    def _style_of(self, cell, pane):
        """RETURN: str, the style class for this cell -- the flags in
                   order of what an author most needs to see.
        """
        active_f = (pane is self.state.pane)
        if cell.kind is E_Kind.ABSENT:  return "class:absent"
        if cell.cursor_f:
            return "class:cursor.active" if active_f else "class:cursor.other"
        if cell.target_f and pane is E_Pane.NOMINAL:
            return "class:target.virgin" if cell.virgin_f else "class:target.latched"
        if cell.marked_f:               return "class:marked"
        if cell.kind is E_Kind.MARKER:  return "class:marker"
        if cell.kind is E_Kind.FILLER:  return "class:filler"
        if cell.kind is E_Kind.TOKEN:   return "class:token"
        return ""

    def _cursor_position(self, pane):
        """RETURN: Point, where prompt_toolkit should keep visible -- the
                   row of this pane's cursor, so its own scrolling
                   follows the author without our holding an offset.
        """
        from prompt_toolkit.data_structures import Point
        return Point(x=0, y=row_of_cursor(project(self.state), pane))
