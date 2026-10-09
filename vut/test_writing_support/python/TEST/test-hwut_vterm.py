#! /usr/bin/env python3
#
# @hwut {
#     title      = "A terminal's screen read by a test: libvterm through ctypes."
#     choices    = ["attributes", "colours", "events", "keys", "missing",
#                   "regions", "screen", "text", "unnoticed"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut_vterm.Screen' fed escape sequences, its cells read back.

    WANTS 'libvterm' (Debian: 'libvterm0'; in the development container).
    Where it is not found every choice but 'missing' says so in one line
    and probes nothing -- and differs from its GOOD.

    text        plain bytes, UTF-8, a wide character (two columns, the
                right half empty), a line wrapping at the right edge
    screen      the sequences a full-screen program writes: the cursor
                addressed, a line erased, the screen cleared, the cursor
                read back
    attributes  each attribute by its SGR code, then all at once, then
                reset. THE BITS ARE MEASURED per library (the module's
                purpose): the names printed here are the same on every
                libvterm; 'conceal' reads False on 0.1, which knows none
    colours     the default (None), an indexed colour, a 256-palette
                colour and a direct one -- each read as red, green, blue
    -- 'Terminal': an application run in it --
    unnoticed   WHAT THE APPLICATION SEES: its three streams are a
                terminal, it has a controlling one, the size is the
                terminal's (COLUMNS=300 in the test's environment does
                not reach it), TERM is set, and its question 'where is
                the cursor?' is answered. Its exit status comes back.
    keys        named keys, function keys, a modifier, a non-ASCII
                character: what the application READS for each
    regions     three regions declared before the run; each key changes
                one of them, and ONLY that one is told -- once per pause,
                whatever the application wrote in between
    events      the RAW layer, on bytes the test feeds itself (so the
                count of events is the bytes', not a scheduler's):
                damage, cursor, a property, the bell; and the terminal's
                answer to a question, with no application to take it
    missing     HWUT_LIBVTERM naming no file: 'LibraryMissing', by name,
                with the hint how to install the library
______________________________________________________________________________
"""
import os
import sys

import config                                                    # noqa: F401
from   vut.test_writing_support.python.hwut_runner import HwutRunner
from   vut.test_writing_support.python             import hwut_vterm
from   vut.test_writing_support.python.hwut_vterm  import (Screen, Terminal,
                                                           LibraryMissing,
                                                           ATTRIBUTE_SGR_DB)

ESC = "\x1b"


def shown(screen):
    """RETURN: None. Every row that holds something, framed, then the
               cursor."""
    for row, line in enumerate(screen.line_list()):
        if line: print("    %d |%s|" % (row, line))
    print("    cursor %s" % (screen.cursor(),))


def probe(function):
    """RETURN: callable, 'function' run on a library that is there; one
               line where it is not."""
    def run():
        try:
            function()
        except LibraryMissing as error:
            print("NOT PROBED: %s" % error)
    return run


def run_text():
    with Screen(4, 12) as screen:
        print("-- plain, then carriage return and line feed")
        screen.feed(b"hello\r\nworld")
        shown(screen)
    with Screen(4, 12) as screen:
        print("-- UTF-8: two bytes, one cell; a wide character, two")
        screen.feed("ä日x".encode("utf-8"))
        shown(screen)
        for column in range(4):
            cell = screen.cell(0, column)
            print("    column %d: %-6r width %d" % (column, cell.text, cell.width))
    with Screen(3, 5) as screen:
        print("-- seven characters on five columns: the line wraps")
        screen.feed(b"abcdefg")
        shown(screen)
    with Screen(2, 4) as screen:
        print("-- a str is sent as UTF-8; the bytes taken are counted")
        print("    taken: %d" % screen.feed("aä"))
        print("-- a place off the screen")
        try:               screen.cell(2, 0)
        except IndexError as error: print("    IndexError: %s" % error)


def run_screen():
    with Screen(5, 20) as screen:
        print("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'")
        screen.feed(b"first line\r\nsecond line\r\nthird line")
        screen.feed((ESC + "[2;4H" + "X").encode())
        shown(screen)
        print("-- erase to the end of that line")
        screen.feed((ESC + "[K").encode())
        shown(screen)
        print("-- clear the screen, home, one word")
        screen.feed((ESC + "[2J" + ESC + "[H" + "clean").encode())
        shown(screen)


def run_attributes():
    with Screen(3, 20) as screen:
        for column, (name, code) in enumerate(ATTRIBUTE_SGR_DB.items()):
            screen.feed("%s[%sm%s%s[0m" % (ESC, code, name[0], ESC))
        print("-- one cell per attribute, set by its own code")
        for column, name in enumerate(ATTRIBUTE_SGR_DB):
            cell = screen.cell(0, column)
            #  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
            said = cell.attribute_text() or "(none)"
            if name == "conceal": said = "conceal, or (none) on libvterm 0.1"
            print("    %r  %s" % (cell.text, said))
        print("-- bold, underline and reverse at once; then reset")
        screen.feed("\r\n%s[1;4;7mA%s[0mB" % (ESC, ESC))
        for column in (0, 1):
            cell = screen.cell(1, column)
            print("    %r  %s" % (cell.text, cell.attribute_text() or "(none)"))
        print("-- double underline (SGR 21) is underlined")
        screen.feed("%s[21mD" % ESC)
        print("    %r  %s" % ("D", screen.cell(1, 2).attribute_text()))


def run_colours():
    with Screen(2, 20) as screen:
        screen.feed("d%s[31mr%s[0m%s[38;5;196mp%s[0m%s[38;2;10;20;30mt%s[0m"
                    % (ESC, ESC, ESC, ESC, ESC, ESC))
        screen.feed("%s[48;2;1;2;3mb%s[0m" % (ESC, ESC))
        for column, what in enumerate(("default", "indexed 31", "palette 196",
                                       "direct 10;20;30",
                                       "background 1;2;3")):
            cell = screen.cell(0, column)
            #  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that
            #  one is a colour and mostly red is the claim, not its shade.
            if what == "indexed 31":
                red, green, blue = cell.foreground
                said = "fg mostly red: %s" % (red > 2 * max(green, blue))
            else:
                said = "fg %s  bg %s" % (cell.foreground, cell.background)
            print("    %-18s %r  %s" % (what, cell.text, said))


#  THE APPLICATION UNDER OBSERVATION: it says what it sees, asks the
#  terminal where the cursor is, then names every key until 'q'.
SEEING_APP = r"""
import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
"""

#  AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body,
#  'f' rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
DRAWING_APP = r"""
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
"""


def run_unnoticed():
    os.environ["COLUMNS"] = "300"
    with Terminal(10, 44) as terminal:
        print("-- still running after its first screen: %s"
              % terminal.run([sys.executable, "-c", SEEING_APP]))
        shown(terminal)
        terminal.send("q")
        print("-- after 'q': exit status %s" % terminal.wait())
        shown(terminal)


def run_keys():
    with Terminal(10, 44) as terminal:
        terminal.region("read", row=8)
        terminal.on_change(lambda name, line_list:
                           print("    %-22s %s" % (pressed, line_list[0])))
        pressed = "(start)"
        terminal.run([sys.executable, "-c", SEEING_APP])
        for key, modifier_tuple in (("up", ()), ("enter", ()), ("tab", ()),
                                    ("escape", ()), ("f5", ()), ("delete", ()),
                                    ("c", ("ctrl",)), ("x", ("alt",)),
                                    ("up", ("shift",))):
            pressed = " ".join(modifier_tuple + (key,))
            terminal.press(key, *modifier_tuple)
        pressed = "send 'ä'"
        terminal.send("ä")
        pressed = "send 'q'"
        terminal.send("q")
        terminal.wait()


def run_regions():
    #  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must
    #  be ONE report on a loaded machine too.
    with Terminal(8, 30, settle_s=0.3) as terminal:
        terminal.region("head", row=0)
        terminal.region("body", row=2, row_n=2)
        terminal.region("foot", row=-1)
        terminal.on_change(lambda name, line_list:
                           print("    changed  %-5s %s" % (name, line_list)))
        for said, act in (("run",             lambda: terminal.run([sys.executable, "-c", DRAWING_APP])),
                          ("'n'",             lambda: terminal.send("n")),
                          ("'n'",             lambda: terminal.send("n")),
                          ("'r': a redraw, nothing new", lambda: terminal.send("r")),
                          ("'f'",             lambda: terminal.send("f")),
                          ("'nnn', typed at once", lambda: terminal.send("nnn")),
                          ("'q'",             lambda: terminal.send("q"))):
            print("-- %s" % said)
            act()
        print("-- exit status %s; a region asked by name: %s"
              % (terminal.wait(), terminal.region_text("body")))
        try:              terminal.region_text("nosuch")
        except KeyError as error: print("-- no such region: KeyError %s" % error)


def run_events():
    with Terminal(4, 20) as terminal:
        terminal.on_event(lambda event: print("    %s" % event))
        for said, data in (("'ab'",                         "ab"),
                           ("a line feed and 'c'",          "\r\nc"),
                           ("the cursor to row 4, hidden",  ESC + "[4;1H" + ESC + "[?25l"),
                           ("the alternate screen",         ESC + "[?1049h"),
                           ("the bell",                     "\x07"),
                           ("nothing that draws: a reset of attributes", ESC + "[0m")):
            print("-- fed: %s" % said)
            terminal.feed(data.encode().decode("unicode_escape"))
        print("-- asked where the cursor is, nobody running: the answer waits")
        terminal.feed(ESC + "[2;5H" + ESC + "[6n")
        print("    answer() = %r" % terminal.answer())
        print("-- a key pressed with nobody running")
        terminal.press("f1", react_s=0)
        print("    answer() = %r" % terminal.answer())


def run_missing():
    os.environ[hwut_vterm.LIBRARY_VARIABLE] = "/nowhere/libvterm.so"
    hwut_vterm._library = None
    try:
        Screen()
        print("a Screen stands on a library that is not there")
    except LibraryMissing as error:
        #  THE SYSTEM'S OWN WORDS for the failed load are left out; what
        #  this module says -- the line, and the way to install -- stands.
        line_list = str(error).split("\n")
        print("LibraryMissing: %s" % line_list[0].split(" -- ")[0])
        for line in line_list[1:]: print(line)


HwutRunner(
    argv       = sys.argv,
    title      = "A terminal's screen read by a test: libvterm through ctypes.",
    choice_map = {
        "text":       probe(run_text),
        "screen":     probe(run_screen),
        "attributes": probe(run_attributes),
        "colours":    probe(run_colours),
        "unnoticed":  probe(run_unnoticed),
        "keys":       probe(run_keys),
        "regions":    probe(run_regions),
        "events":     probe(run_events),
        "missing":    run_missing,
    },
).run()
