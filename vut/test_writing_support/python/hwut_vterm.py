"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- 'libvterm' through 'ctypes'.

    A program that draws a screen writes escape sequences; what a person
    SEES is what a terminal makes of them. This module is that terminal:
    bytes go in, and the grid of cells -- characters, attributes,
    colours, the cursor -- is read back as plain values a test prints.

        from hwut_vterm import Screen

        with Screen(row_n=24, column_n=80) as screen:
            screen.feed(b"\\x1b[1mbold\\x1b[0m plain")
            print(screen.line(0))               # 'bold plain'
            print(screen.cell(0, 0).bold_f)     # True
            print(screen.cursor())              # (0, 10)

    RULED 2026-10-09 (r-11d): "use libvterm ... do not use pyte". No
    Python module binding the library was found on the package index;
    this is the binding, and it is the test side's.

THE LIBRARY IS FOUND, NOT SHIPPED: 'libvterm.so' as the system knows it
    (Debian: 'libvterm0'), or the file the environment variable
    HWUT_LIBVTERM names. Where neither stands, 'Screen()' raises
    'LibraryMissing', whose text says how to install it -- a test prints
    it and probes nothing. 'python3 hwut_vterm.py' asks the same by hand.

THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED. libvterm's 'VTermScreenCell'
    changed between its versions -- MEASURED on 0.1.3, 0.2 and 0.3.3:
    'strike' is bit 0x40 in 0.1 and 0x80 from 0.2 on, where 'conceal'
    took its place; 0.1 knows no 'conceal' at all. A binding that copied
    one header would read another version's cells wrongly AND SILENTLY.
    So, once per library, a scratch terminal is fed one attribute at a
    time -- '<esc>[1mX', '<esc>[9mX', '<esc>[38;2;1;2;3mX' -- and the bit
    or the bytes that changed are where that attribute stands. An
    attribute the library does not know moves nothing and reads False
    for ever.

TWO CLASSES:
    Screen      the grid alone: bytes in, cells out. No process.
    Terminal    a Screen an APPLICATION RUNS IN (ruled 2026-10-09): set
                up, declare what to observe, then 'run()' -- on a
                pseudo-terminal, so the application cannot tell. Keys go
                in as a keyboard sends them; observation is by callback,
                raw ('on_event') or by named region ('on_change').
______________________________________________________________________________
"""
import ctypes
import ctypes.util
import os
from   dataclasses import dataclass

#  THE ENVIRONMENT VARIABLE that names the library's file, where the
#  system's search does not find it.
LIBRARY_VARIABLE = "HWUT_LIBVTERM"

#  WHAT IS THE SAME IN EVERY VERSION: six code points of four bytes, then
#  the width; everything behind them is measured.
CHARS_PER_CELL_N = 6
CHARS_BYTE_N     = 4 * CHARS_PER_CELL_N
CELL_BYTE_N      = 128           # room beyond any version's cell

#  THE ATTRIBUTES A CELL IS ASKED FOR, each with the SGR code that sets it.
ATTRIBUTE_SGR_DB = {
    "bold":      "1",
    "italic":    "3",
    "underline": "4",
    "blink":     "5",
    "reverse":   "7",
    "conceal":   "8",
    "strike":    "9",
}


#  WHAT A PERSON IS TOLD where the library is not found: how to get it.
INSTALL_HINT = "\n".join((
    "HINT: install the library, or name its file:",
    "    Debian, Ubuntu   apt install libvterm0",
    "    Fedora           dnf install libvterm",
    "    Arch             pacman -S libvterm",
    "    macOS            brew install libvterm",
    "    elsewhere        export %s=<path>/libvterm.so" % LIBRARY_VARIABLE,
    "    or work inside   hwut.dev.podman.enter   (the image holds it)",
))


def detection_text():
    """RETURN: str, 'libvterm found: <name>', if the library loads
               the text of 'LibraryMissing' -- what is wrong and how to
               install it -- else

    'python3 hwut_vterm.py' prints it and exits 0 or 1 accordingly.
    """
    try:
        return "libvterm found: %s" % library()._name
    except LibraryMissing as error:
        return str(error)


class LibraryMissing(Exception):
    """'libvterm' was not found: neither by the system's search nor under
    the name HWUT_LIBVTERM gives."""


class _Position(ctypes.Structure):
    """'VTermPos', passed by value: a row and a column."""
    _fields_ = [("row", ctypes.c_int), ("col", ctypes.c_int)]


class _Rectangle(ctypes.Structure):
    """'VTermRect', passed by value: rows and columns, the ends EXCLUDED."""
    _fields_ = [("start_row", ctypes.c_int), ("end_row", ctypes.c_int),
                ("start_col", ctypes.c_int), ("end_col", ctypes.c_int)]


#  THE CALLBACKS' SHAPES, the same in every version measured (0.1.3, 0.2,
#  0.3.3). Later versions APPEND to 'VTermScreenCallbacks'; the structure
#  here ends in spare null slots, so a library that reads further than
#  this module wrote reads "no callback".
_OUTPUT_F     = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_char),
                                 ctypes.c_size_t, ctypes.c_void_p)
_DAMAGE_F     = ctypes.CFUNCTYPE(ctypes.c_int, _Rectangle, ctypes.c_void_p)
_MOVERECT_F   = ctypes.CFUNCTYPE(ctypes.c_int, _Rectangle, _Rectangle,
                                 ctypes.c_void_p)
_MOVECURSOR_F = ctypes.CFUNCTYPE(ctypes.c_int, _Position, _Position,
                                 ctypes.c_int, ctypes.c_void_p)
_PROPERTY_F   = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int,
                                 ctypes.POINTER(ctypes.c_int), ctypes.c_void_p)
_BELL_F       = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)


class _ScreenCallbacks(ctypes.Structure):
    """'VTermScreenCallbacks': the five this module answers, the three it
    leaves null, and spare slots for what later versions append."""
    _fields_ = [("damage",      _DAMAGE_F),
                ("moverect",    _MOVERECT_F),
                ("movecursor",  _MOVECURSOR_F),
                ("settermprop", _PROPERTY_F),
                ("bell",        _BELL_F),
                ("resize",      ctypes.c_void_p),
                ("sb_pushline", ctypes.c_void_p),
                ("sb_popline",  ctypes.c_void_p),
                ("spare",       ctypes.c_void_p * 8)]


#  'VTERM_DAMAGE_ROW': damage is told per row, once the terminal is
#  flushed -- not per cell as it happens.
DAMAGE_MERGE_ROW = 1

#  THE PROPERTIES A TERMINAL REPORTS, by libvterm's number; the ones
#  whose value is a flag or a number carry it, a title's text does not
#  (its C form differs by version).
PROPERTY_DB = {
    1: ("cursor-visible", True),
    2: ("cursor-blink",   True),
    3: ("alternate-screen", True),
    4: ("title",          False),
    5: ("icon-name",      False),
    6: ("reverse-video",  True),
    7: ("cursor-shape",   True),
    8: ("mouse",          True),
    9: ("focus-report",   True),
}

#  THE KEYS THAT ARE NOT A CHARACTER, by the name a test presses them
#  under ('VTermKey'; function keys stand at 256 + n).
KEY_DB = {
    "enter": 1, "tab": 2, "backspace": 3, "escape": 4,
    "up": 5, "down": 6, "left": 7, "right": 8,
    "insert": 9, "delete": 10, "home": 11, "end": 12,
    "pageup": 13, "pagedown": 14,
}
KEY_DB.update(("f%d" % n, 256 + n) for n in range(1, 13))
MODIFIER_DB = {"shift": 1, "alt": 2, "ctrl": 4}


@dataclass(frozen=True)
class Event:
    """ONE THING THE TERMINAL DID, as libvterm reports it (the RAW layer).

    kind        'damage'    rows 'row'..'row_end' and columns
                            'column'..'column_end' changed, ends EXCLUDED
                'cursor'    the cursor stands at ('row', 'column');
                            'value' says whether it is visible
                'property'  the property 'name' is now 'value' (None
                            where the value is a text)
                'bell'      the bell rang
    """
    kind:       str
    row:        int    = None
    column:     int    = None
    row_end:    int    = None
    column_end: int    = None
    name:       str    = None
    value:      object = None

    def __str__(self):
        """RETURN: str, the event on one line, as a test prints it."""
        if self.kind == "damage":
            return "damage    rows %d..%d  columns %d..%d" \
                   % (self.row, self.row_end, self.column, self.column_end)
        if self.kind == "cursor":
            return "cursor    (%d, %d)%s" % (self.row, self.column,
                                             "" if self.value else "  hidden")
        if self.kind == "property":
            return "property  %s = %s" % (self.name, self.value)
        return self.kind


@dataclass(frozen=True)
class Cell:
    """ONE CELL OF THE SCREEN, as plain values.

    'text' is what stands in it -- '' for a cell nothing was written to,
    and for the right half of a wide character. 'foreground' and
    'background' are (red, green, blue), or None where the cell wears the
    terminal's default -- also where a program asked by number for the
    very colour the default is."""
    text:        str   = ""
    width:       int   = 1
    bold_f:      bool  = False
    italic_f:    bool  = False
    underline_f: bool  = False
    blink_f:     bool  = False
    reverse_f:   bool  = False
    conceal_f:   bool  = False
    strike_f:    bool  = False
    foreground:  tuple = None
    background:  tuple = None

    def attribute_text(self):
        """RETURN: str, the attributes that are set, by name and in one
                        fixed order, separated by blanks -- 'bold reverse'
                   '', if none is set
        """
        return " ".join(name for name in ATTRIBUTE_SGR_DB
                        if getattr(self, name + "_f"))


@dataclass(frozen=True)
class _Layout:
    """WHERE A CELL'S FIELDS STAND in this library's 'VTermScreenCell'."""
    mask_db:           dict     # attribute name -> (byte offset, bit mask)
    foreground_i:      int      # offset of the foreground's red byte
    background_i:      int      # offset of the background's red byte
    convert_f:         bool     # colours pass 'convert_color_to_rgb' first
    default_fg:        tuple    # what an unwritten cell wears
    default_bg:        tuple


_library = None                  # the loaded library, once
_layout  = None                  # its measured layout, once


def library():
    """RETURN: ctypes.CDLL, 'libvterm', loaded once and its functions
                            declared
               raises LibraryMissing, if no such library is found
    """
    global _library
    if _library is not None: return _library
    name = os.environ.get(LIBRARY_VARIABLE) or ctypes.util.find_library("vterm")
    if not name:
        raise LibraryMissing("libvterm is not installed, and '%s' names no "
                             "file\n%s" % (LIBRARY_VARIABLE, INSTALL_HINT))
    try:
        lib = ctypes.CDLL(name)
    except OSError as error:
        raise LibraryMissing("libvterm cannot be loaded from '%s' -- %s\n%s"
                             % (name, error, INSTALL_HINT))
    pointer = ctypes.c_void_p
    for function, result, argument_list in (
        ("vterm_new",                 pointer, [ctypes.c_int, ctypes.c_int]),
        ("vterm_free",                None,    [pointer]),
        ("vterm_set_utf8",            None,    [pointer, ctypes.c_int]),
        ("vterm_input_write",         ctypes.c_size_t,
                                      [pointer, ctypes.c_char_p, ctypes.c_size_t]),
        ("vterm_obtain_screen",       pointer, [pointer]),
        ("vterm_obtain_state",        pointer, [pointer]),
        ("vterm_screen_reset",        None,    [pointer, ctypes.c_int]),
        ("vterm_screen_enable_altscreen", None, [pointer, ctypes.c_int]),
        ("vterm_screen_get_cell",     ctypes.c_int,
                                      [pointer, _Position, ctypes.c_char_p]),
        ("vterm_state_get_cursorpos", None,
                                      [pointer, ctypes.POINTER(_Position)]),
        ("vterm_output_set_callback", None,    [pointer, _OUTPUT_F, pointer]),
        ("vterm_keyboard_unichar",    None,
                                      [pointer, ctypes.c_uint32, ctypes.c_int]),
        ("vterm_keyboard_key",        None,
                                      [pointer, ctypes.c_int, ctypes.c_int]),
        ("vterm_screen_set_callbacks", None,   [pointer, pointer, pointer]),
        ("vterm_screen_set_damage_merge", None, [pointer, ctypes.c_int]),
        ("vterm_screen_flush_damage", None,    [pointer]),
    ):
        entry          = getattr(lib, function)
        entry.restype  = result
        entry.argtypes = argument_list
    #  ONLY 0.2 AND LATER hold an indexed colour that must be resolved.
    if hasattr(lib, "vterm_screen_convert_color_to_rgb"):
        lib.vterm_screen_convert_color_to_rgb.restype  = None
        lib.vterm_screen_convert_color_to_rgb.argtypes = [pointer, pointer]
    _library = lib
    return lib


class Screen:
    """A TERMINAL OF 'row_n' ROWS AND 'column_n' COLUMNS that draws what
    it is fed and lets its cells be read. Use it in a 'with', or call
    'close()': the terminal is the library's memory, not Python's."""

    def __init__(self, row_n=24, column_n=80):
        """RETURN: Screen, blank, the cursor at (0, 0)
                   raises LibraryMissing, if 'libvterm' is not found
        """
        self.row_n, self.column_n = row_n, column_n
        self._lib      = library()
        self._terminal = self._lib.vterm_new(row_n, column_n)
        self._lib.vterm_set_utf8(self._terminal, 1)
        self._screen   = self._lib.vterm_obtain_screen(self._terminal)
        self._state    = self._lib.vterm_obtain_state(self._terminal)
        #  THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR, and a
        #  full-screen application draws on it: without this its screen
        #  and the shell's lines before it would stand in one grid.
        self._lib.vterm_screen_enable_altscreen(self._screen, 1)
        self._lib.vterm_screen_reset(self._screen, 1)

    def __enter__(self):
        """RETURN: Screen, this one."""
        return self

    def __exit__(self, *_):
        """RETURN: None. The terminal is given back; an exception passes."""
        self.close()

    def close(self):
        """RETURN: None. The terminal's memory is freed; a second call
                   does nothing."""
        if self._terminal is not None:
            self._lib.vterm_free(self._terminal)
            self._terminal = self._screen = self._state = None

    def feed(self, data):
        """RETURN: int, the number of bytes the terminal took -- all of
                        them, where it works as documented

        'data' is what a program wrote: bytes, or a str sent as UTF-8.
        """
        if isinstance(data, str): data = data.encode("utf-8")
        return self._lib.vterm_input_write(self._terminal, data, len(data))

    def cursor(self):
        """RETURN: (int, int), the cursor's row and column, from 0."""
        position = _Position()
        self._lib.vterm_state_get_cursorpos(self._state,
                                            ctypes.byref(position))
        return (position.row, position.col)

    def _raw(self, row, column):
        """RETURN: ctypes buffer, the library's own cell at that place,
                   its colours resolved to red, green, blue where the
                   library keeps them otherwise."""
        buffer = ctypes.create_string_buffer(CELL_BYTE_N)
        self._lib.vterm_screen_get_cell(self._screen, _Position(row, column),
                                        buffer)
        if _layout is not None and _layout.convert_f:
            #  THE COLOUR'S STRUCTURE begins one byte before its red: the
            #  type byte the conversion reads and rewrites.
            for start in (_layout.foreground_i, _layout.background_i):
                self._lib.vterm_screen_convert_color_to_rgb(
                    self._screen, ctypes.byref(buffer, start - 1))
        return buffer

    def cell(self, row, column):
        """RETURN: Cell, what stands at that place
                   raises IndexError, if the place is not on the screen
        """
        if not (0 <= row < self.row_n and 0 <= column < self.column_n):
            raise IndexError("(%d, %d) is not on a screen of %d x %d"
                             % (row, column, self.row_n, self.column_n))
        layout = _measured()
        raw    = self._raw(row, column).raw
        text   = "".join(
            chr(code) for code in
            (int.from_bytes(raw[i:i + 4], "little")
             for i in range(0, CHARS_BYTE_N, 4))
            if code not in (0, 0xFFFFFFFF))
        colour = lambda i, default: (                           # noqa: E731
            None if tuple(raw[i:i + 3]) == default else tuple(raw[i:i + 3]))
        return Cell(
            text       = text,
            width      = raw[CHARS_BYTE_N] or 1,
            foreground = colour(layout.foreground_i, layout.default_fg),
            background = colour(layout.background_i, layout.default_bg),
            **{name + "_f": bool(raw[offset] & mask)
               for name, (offset, mask) in layout.mask_db.items()})

    def line(self, row):
        """RETURN: str, the row's characters, blanks at its end dropped;
                        a cell nothing was written to reads as a blank
        """
        text_list, column = [], 0
        while column < self.column_n:
            cell = self.cell(row, column)
            text_list.append(cell.text or " ")
            column += max(cell.width, 1)
        return "".join(text_list).rstrip()

    def line_list(self):
        """RETURN: list[str], every row as 'line()' gives it, top first."""
        return [self.line(row) for row in range(self.row_n)]


class Terminal(Screen):
    """A TERMINAL AN APPLICATION RUNS IN, OBSERVED BY CALLBACKS.

    Set up first, then run: the application is started on a
    pseudo-terminal of this size and cannot tell this from a terminal a
    person sits at -- its three streams are a terminal, the size and
    TERM answer, and what it ASKS the terminal (where is the cursor?) is
    answered by libvterm and handed back to it.

        with Terminal(24, 80) as terminal:
            terminal.region("foot", row=-1)
            terminal.on_change(lambda name, line_list: print(name, line_list))
            terminal.run(["my-app"])
            terminal.press("down")
            terminal.send("q")
            print(terminal.wait())

    TWO LAYERS OF OBSERVATION (ruled 2026-10-09: both):

        on_event    RAW: every 'Event' libvterm reports -- damage, cursor,
                    property, bell -- as it happens. How MANY damages one
                    redraw makes depends on how the application's writes
                    were cut into reads; print them only where the bytes
                    are fed by the test itself.
        on_change   REGIONS: a named rectangle's text, told once it has
                    CHANGED and the application has gone QUIET
                    ('settle_s' without a byte). One call per changed
                    region and pause, in the order the regions were
                    declared -- the same on every run.
    """

    def __init__(self, row_n=24, column_n=80, settle_s=0.1):
        """RETURN: Terminal, blank, nothing running in it
                   raises LibraryMissing, if 'libvterm' is not found

        'settle_s' is how long the application must write nothing before
        its screen is taken as drawn.
        """
        super().__init__(row_n, column_n)
        self.settle_s       = settle_s
        self._event_f_list  = []
        self._change_f_list = []
        self._region_db     = {}        # name -> (row, row_n, column, column_n)
        self._told_db       = {}        # name -> the lines last told
        self._answer        = bytearray()
        self._master        = None
        self._process       = None
        self._ended_f       = False
        #  THE CALLBACK OBJECTS LIVE AS LONG AS THE TERMINAL: libvterm
        #  keeps their addresses, Python must keep them.
        self._output_f  = _OUTPUT_F(self._on_output)
        self._callbacks = _ScreenCallbacks(
            damage      = _DAMAGE_F(self._on_damage),
            movecursor  = _MOVECURSOR_F(self._on_cursor),
            settermprop = _PROPERTY_F(self._on_property),
            bell        = _BELL_F(self._on_bell))
        self._lib.vterm_output_set_callback(self._terminal, self._output_f,
                                            None)
        self._lib.vterm_screen_set_callbacks(self._screen,
                                             ctypes.byref(self._callbacks),
                                             None)
        self._lib.vterm_screen_set_damage_merge(self._screen,
                                                DAMAGE_MERGE_ROW)

    #  ------------------------------------------------------- observation
    def on_event(self, callback):
        """RETURN: None. 'callback(event)' is called with every raw
                   'Event' from now on."""
        self._event_f_list.append(callback)

    def on_change(self, callback):
        """RETURN: None. 'callback(name, line_list)' is called for every
                   region whose text changed, once the screen is quiet."""
        self._change_f_list.append(callback)

    def region(self, name, row, row_n=1, column=0, column_n=None):
        """RETURN: None. The rectangle 'name' is observed from now on:
                   'row_n' rows from 'row', 'column_n' columns from
                   'column' (to the right edge where None).

        A NEGATIVE 'row' counts from the bottom: -1 is the last row.
        """
        if row < 0: row += self.row_n
        if column_n is None: column_n = self.column_n - column
        self._region_db[name] = (row, row_n, column, column_n)
        #  WHAT STANDS THERE NOW IS KNOWN, not news: only a change is told.
        self._told_db[name]   = self.region_text(name)

    def region_text(self, name):
        """RETURN: list[str], the region's rows as they stand now, blanks
                              at each row's end dropped
                   raises KeyError, if no such region was declared
        """
        row, row_n, column, column_n = self._region_db[name]
        result = []
        for each in range(row, row + row_n):
            text_list, at = [], column
            while at < column + column_n:
                cell = self.cell(each, at)
                text_list.append(cell.text or " ")
                at += max(cell.width, 1)
            result.append("".join(text_list).rstrip())
        return result

    def report(self):
        """RETURN: list[str], the names of the regions whose text differs
                   from what was last told -- each told to every
                   'on_change' callback, in the order of declaration."""
        changed_list = []
        for name in self._region_db:
            line_list = self.region_text(name)
            if self._told_db.get(name) == line_list: continue
            self._told_db[name] = line_list
            changed_list.append(name)
            for callback in self._change_f_list: callback(name, line_list)
        return changed_list

    def _emit(self, event):
        """RETURN: 1, libvterm's 'handled'. The event reaches every raw
                   callback."""
        for callback in self._event_f_list: callback(event)
        return 1

    def _on_damage(self, rectangle, _):
        return self._emit(Event("damage", rectangle.start_row,
                                rectangle.start_col, rectangle.end_row,
                                rectangle.end_col))

    def _on_cursor(self, position, _, visible, __):
        return self._emit(Event("cursor", position.row, position.col,
                                value=bool(visible)))

    def _on_property(self, number, value, _):
        name, plain_f = PROPERTY_DB.get(number, ("property-%d" % number, False))
        return self._emit(Event("property", name=name,
                                value=value[0] if plain_f else None))

    def _on_bell(self, _):
        return self._emit(Event("bell"))

    def _on_output(self, data, length, _):
        """RETURN: None. What the TERMINAL says -- a key's sequence, the
                   answer to a question -- is collected for the
                   application."""
        self._answer += ctypes.string_at(data, length)

    #  --------------------------------------------------- bytes in and out
    def feed(self, data):
        """RETURN: int, the number of bytes the terminal took.

        The raw events of what was fed fire before this returns; what the
        terminal answered goes to the application, where one runs.
        """
        taken_n = super().feed(data)
        self._lib.vterm_screen_flush_damage(self._screen)
        self._forward()
        return taken_n

    def answer(self):
        """RETURN: bytes, what the terminal said since the last call and
                   no application took -- the reply to a question fed by
                   hand, the sequence of a key pressed with nothing
                   running."""
        data, self._answer = bytes(self._answer), bytearray()
        return data

    def _forward(self):
        """RETURN: None. The terminal's words reach the application, if
                   one runs; they wait in 'answer()' otherwise."""
        if self._master is None or not self._answer: return
        try:
            os.write(self._master, bytes(self._answer))
        except OSError:
            self._ended_f = True
        self._answer = bytearray()

    def send(self, text, react_s=1.0):
        """RETURN: bool, True if the application still runs after it

        'text' is typed, character by character, as a keyboard sends it;
        then the screen is given 'react_s' to begin answering and is read
        until quiet.
        """
        for character in text:
            self._lib.vterm_keyboard_unichar(self._terminal, ord(character), 0)
        self._forward()
        return self.pump(react_s)

    def press(self, key, *modifier_tuple, react_s=1.0):
        """RETURN: bool, True if the application still runs after it
                   raises KeyError, if 'key' or a modifier has no name here

        'key' is a name of KEY_DB ('enter', 'up', 'f5', ...) or one
        character; the modifiers are 'shift', 'alt', 'ctrl' --
        'press("c", "ctrl")' is Ctrl-C.
        """
        modifier = 0
        for name in modifier_tuple: modifier |= MODIFIER_DB[name]
        if len(key) == 1:
            self._lib.vterm_keyboard_unichar(self._terminal, ord(key), modifier)
        else:
            self._lib.vterm_keyboard_key(self._terminal, KEY_DB[key], modifier)
        self._forward()
        return self.pump(react_s)

    #  ------------------------------------------------------ the application
    def run(self, argv, env=None, cwd=None, start_s=10.0):
        """RETURN: bool, True if the application still runs once its
                         first screen stands
                   raises RuntimeError, if one already runs here

        'argv' is started on a pseudo-terminal of this terminal's size:
        stdin, stdout and stderr are that terminal, and it is the
        application's controlling one. TERM is 'xterm-256color'; LINES
        and COLUMNS are taken OUT of the environment, since they would
        overrule the size the terminal answers.
        """
        import fcntl, struct, subprocess, termios      # noqa: E401
        if self._process is not None:
            raise RuntimeError("an application already runs in this terminal")
        self._master, slave = os.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ,
                    struct.pack("HHHH", self.row_n, self.column_n, 0, 0))
        environment = dict(os.environ if env is None else env)
        environment["TERM"] = "xterm-256color"
        for name in ("LINES", "COLUMNS"): environment.pop(name, None)

        def in_child():
            """RETURN: None. The child leads its own session and the
                       pseudo-terminal is its controlling terminal."""
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        self._process = subprocess.Popen(
            argv, stdin=slave, stdout=slave, stderr=slave, cwd=cwd,
            env=environment, preexec_fn=in_child, close_fds=True)
        os.close(slave)
        self._ended_f = False
        return self.pump(start_s)

    def pump(self, first_s=1.0):
        """RETURN: bool, True if the application still runs

        READ UNTIL QUIET: wait up to 'first_s' for the application to
        write at all, then go on reading until it has written nothing for
        'settle_s'. Then the changed regions are reported.
        """
        import select
        wait_s = first_s
        while self._master is not None and not self._ended_f:
            ready, _, _ = select.select([self._master], [], [], wait_s)
            if not ready: break
            try:
                data = os.read(self._master, 65536)
            except OSError:              # the last writer closed: it ended
                data = b""
            if not data:
                self._ended_f = True
                break
            self.feed(data)
            wait_s = self.settle_s
        self.report()
        return self._process is not None and self._process.poll() is None \
               and not self._ended_f

    def expect(self, text, timeout_s=10.0):
        """RETURN: (int, int), the row and column where 'text' stands on
                               the screen, once it does
                   raises TimeoutError, carrying the screen, if it does
                          not within 'timeout_s'
        """
        import time
        deadline = time.monotonic() + timeout_s
        while True:
            for row, line in enumerate(self.line_list()):
                if text in line: return (row, line.index(text))
            if time.monotonic() >= deadline or self._ended_f \
               or self._master is None:
                raise TimeoutError("'%s' did not appear; the screen:\n%s"
                                   % (text, "\n".join(self.line_list())))
            self.pump(self.settle_s)

    def wait(self, timeout_s=10.0):
        """RETURN: int, the application's exit status, once it has ended
                        and its last words are on the screen
                   None, if no application was run
                   raises TimeoutError, if it still runs after
                          'timeout_s' -- it is killed first
        """
        import subprocess, time                        # noqa: E401
        if self._process is None: return None
        deadline = time.monotonic() + timeout_s
        while self.pump(self.settle_s):
            if time.monotonic() >= deadline:
                self._process.kill()
                self._process.wait()
                raise TimeoutError("the application still ran after %.1f s"
                                   % timeout_s)
        try:
            return self._process.wait(max(deadline - time.monotonic(), 0.1))
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            raise TimeoutError("the application closed its terminal and "
                               "did not end")

    def close(self):
        """RETURN: None. An application still running is killed, the
                   pseudo-terminal closed, the terminal's memory freed."""
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
            self._process.wait()
        if self._master is not None:
            os.close(self._master)
            self._master = None
        super().close()


def _measured():
    """RETURN: _Layout, where this library's cell keeps each attribute and
               each colour -- measured once on a scratch terminal, then
               remembered."""
    global _layout
    if _layout is not None: return _layout

    def cell_after(sequence):
        """RETURN: bytes, the raw cell (0, 0) of a fresh terminal after
                   'sequence' and one 'X' -- unconverted."""
        with Screen(2, 4) as scratch:
            scratch.feed("\x1b[%sm" % sequence if sequence else "")
            scratch.feed("X")
            return scratch._raw(0, 0).raw

    def changed(raw):
        """RETURN: list[(int, int)], (offset, bits) of every byte behind
                   the width in which 'raw' differs from the plain cell."""
        return [(i, a ^ b) for i, (a, b)
                in enumerate(zip(plain[CHARS_BYTE_N + 1:],
                                 raw[CHARS_BYTE_N + 1:]), CHARS_BYTE_N + 1)
                if a != b]

    plain   = cell_after("")
    mask_db = {}
    for name, code in ATTRIBUTE_SGR_DB.items():
        found = changed(cell_after(code))
        #  NOTHING MOVED: this library does not know the attribute.
        mask_db[name] = found[0] if found else (CHARS_BYTE_N + 1, 0)
    #  UNDERLINE IS A NUMBER OF TWO BITS (single, double, curly): any of
    #  them is 'underlined', so the double's bit joins the mask.
    for offset, bits in changed(cell_after("21")):
        if offset == mask_db["underline"][0]:
            mask_db["underline"] = (offset, mask_db["underline"][1] | bits)

    def colour_at(code):
        """RETURN: int, the offset of the red byte of the colour
                   '<code>;2;1;2;3' sets."""
        raw = cell_after("%s;2;1;2;3" % code)
        return raw.index(b"\x01\x02\x03", CHARS_BYTE_N + 1)

    foreground_i = colour_at("38")
    background_i = colour_at("48")
    convert_f    = hasattr(library(), "vterm_screen_convert_color_to_rgb")
    #  THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell will be
    #  read from now on.
    _layout = _Layout(mask_db, foreground_i, background_i, convert_f,
                      (), ())
    with Screen(2, 4) as scratch:
        scratch.feed("X")
        raw = scratch._raw(0, 0).raw
    _layout = _Layout(mask_db, foreground_i, background_i, convert_f,
                      tuple(raw[foreground_i:foreground_i + 3]),
                      tuple(raw[background_i:background_i + 3]))
    return _layout


if __name__ == "__main__":
    #  THE DETECTION, asked by hand: is the library there?
    import sys
    print(detection_text())
    sys.exit(0 if _library is not None else 1)
