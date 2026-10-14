==============================================================================
hwut_vterm -- A TERMINAL'S SCREEN, READ BY A TEST
==============================================================================

A program that draws a screen -- a menu, an editor, a merge view -- writes
escape sequences. What a person SEES is what a terminal makes of them. A
test that compares the bytes pins the sequences, not the picture: two
programs that draw the same screen by different sequences differ, and a
screen that is wrong in a way no single line shows passes.

'hwut_vterm' is that terminal, for a test. Bytes go in; the grid of cells
comes back as plain values that print. With 'Screen' the test feeds the
bytes itself; with 'Terminal' (section 2) an application runs in it:

    from hwut_vterm import Screen

    with Screen(row_n=24, column_n=80) as screen:
        screen.feed(b"\x1b[1mbold\x1b[0m plain")
        print(screen.line(0))               # bold plain
        print(screen.cell(0, 0).bold_f)     # True
        print(screen.cursor())              # (0, 10)

The terminal is 'libvterm' -- the library neovim's terminal was built on --
reached through Python's 'ctypes'. Nothing is compiled and nothing but
the library is required.


1  WHAT A TEST CAN ASK OF THE SCREEN
______________________________________________________________________________

    Screen(row_n, column_n)     a blank terminal of that size. Use it in a
                                'with', or call 'close()'.
    screen.feed(data)           what the program wrote: bytes, or a str
                                (sent as UTF-8). Returns the bytes taken.
    screen.line(row)            the row's characters, trailing blanks
                                dropped.
    screen.line_list()          every row, top first.
    screen.cursor()             (row, column), counted from 0.
    screen.cell(row, column)    one cell:

        text            what stands in it; '' where nothing was written
                        and in the right half of a wide character
        width           1, or 2 for a wide character
        bold_f italic_f underline_f blink_f reverse_f conceal_f strike_f
        foreground      (red, green, blue), or None for the terminal's
        background      default colour
        attribute_text()    the set attributes by name: 'bold reverse'

A cell prints the same on every machine: an attribute is a name, a colour
is three numbers, and an indexed colour (SGR 31, 38;5;196) is resolved to
the three numbers before it is handed out.


2  AN APPLICATION RUN IN IT, OBSERVED BY CALLBACKS
______________________________________________________________________________

'Terminal' is a Screen an application runs in. The order is: set up,
declare what to observe, then run.

    from hwut_vterm import Terminal

    with Terminal(row_n=24, column_n=80) as terminal:
        terminal.region("foot", row=-1)
        terminal.on_change(lambda name, line_list: print(name, line_list))
        terminal.run(["my-app", "--some-option"])
        terminal.press("down")
        terminal.send("q")
        print(terminal.wait())              # the exit status

THE APPLICATION CANNOT TELL. It is one child process on a
pseudo-terminal; libvterm stays inside the test's own process, as the
parser of what the child writes. From the application's side:

    stdin, stdout, stderr     are a terminal ('isatty()' is True)
    the controlling terminal  is that terminal ('/dev/tty' opens)
    the size                  is the Terminal's rows and columns; LINES
                              and COLUMNS are taken out of its
                              environment, since they would overrule it
    TERM                      is 'xterm-256color'
    a question to the terminal ("where is the cursor?", '<esc>[6n')
                              is answered by libvterm, and the answer is
                              written back to the application
    the alternate screen      works: a full-screen program's picture does
                              not mix with the lines printed before it

KEYS go in as a keyboard sends them -- libvterm encodes them:

    terminal.send("text")           typed, character by character
    terminal.press("up")            a named key: enter tab backspace
                                    escape up down left right insert
                                    delete home end pageup pagedown
                                    f1 .. f12
    terminal.press("c", "ctrl")     with modifiers: shift, alt, ctrl

OBSERVATION HAS TWO LAYERS, and both are public:

    on_change(callback)     REGIONS. A region is a named rectangle:

                                terminal.region("foot", row=-1)
                                terminal.region("body", row=2, row_n=5)

                            (a negative row counts from the bottom).
                            'callback(name, line_list)' is called when
                            the region's TEXT has changed and the
                            application has gone quiet -- once per
                            changed region and pause, in the order the
                            regions were declared. A redraw that changes
                            nothing is not told; three redraws typed at
                            once are told once. This is the layer to
                            record in a GOOD.

    on_event(callback)      RAW. Every 'Event' libvterm reports, as it
                            happens: 'damage' (rows and columns, ends
                            excluded), 'cursor', 'property'
                            (cursor-visible, alternate-screen, ...),
                            'bell'. How many damages one redraw makes
                            depends on how the application's writes were
                            cut into reads: record them only for bytes
                            the test feeds itself.

"QUIET" is 'settle_s' (0.1 s by default) without a byte from the
application. Every call that lets the application act -- 'run', 'send',
'press', 'pump' -- reads until quiet and then reports the regions.

    terminal.expect("text")     wait until the text stands on the screen;
                                'TimeoutError', carrying the screen, where
                                it never does. Use it where 'quiet' is not
                                enough -- a slow start, a computation.
    terminal.wait()             until the application ended: its exit
                                status. It is killed, and 'TimeoutError'
                                raised, where it does not end.
    terminal.region_text(name)  a region's rows, asked directly
    terminal.answer()           what the terminal said while nothing ran
                                (a test of the terminal itself)

NOT HERE: scrollback, the mouse, a window title's text, a resize while
the application runs. None was needed yet.


3  THE ONE THING DONE DIFFERENTLY: THE CELL IS MEASURED
______________________________________________________________________________

A ctypes binding normally copies the C structure from the header. For
libvterm that is a trap: the cell's layout CHANGED between versions, and
a structure copied from one header reads another version's cells wrongly
without any error.

    MEASURED on libvterm 0.1.3, 0.2 and 0.3.3, built from source:

        attribute     0.1.3        0.2, 0.3.3
        strike        bit 0x40     bit 0x80
        conceal       (unknown)    bit 0x40

So this module copies nothing. The first time a cell is read, it feeds a
scratch terminal one attribute at a time -- '<esc>[1mX', '<esc>[9mX',
'<esc>[38;2;1;2;3mX' -- and compares the raw cell with a plain one. The
bit that changed is where that attribute stands; the bytes 1, 2, 3 are
where that colour stands. The answer is kept for the life of the process.

    An attribute the library does not know moves nothing: it reads False
    for ever, and nothing fails. ('conceal' on libvterm 0.1.)

    Underline is a number of two bits (single, double, curly): any of
    them reads 'underline_f'.

The page 'TEST/test-hwut_vterm.py' prints the same on all three versions.
The first user is 'services/lib/viewers/keyed/TEST/test-screen.py': the
keyed merge screen of 'hwut.accept.interactive', as drawn.


4  THE LIBRARY: FOUND, NOT SHIPPED -- AND SAID WHEN MISSING
______________________________________________________________________________

The library is looked for in this order:

    1. the file the environment variable HWUT_LIBVTERM names
    2. 'libvterm' as the system's own search finds it

Where neither stands, 'Screen()' raises 'LibraryMissing', and the text of
the exception is the detection message:

    libvterm is not installed, and 'HWUT_LIBVTERM' names no file
    HINT: install the library, or name its file:
        Debian, Ubuntu   apt install libvterm0
        Fedora           dnf install libvterm
        Arch             pacman -S libvterm
        macOS            brew install libvterm
        elsewhere        export HWUT_LIBVTERM=<path>/libvterm.so
        or work inside   hwut.dev.podman.enter   (the image holds it)

To ask by hand whether the library is there:

    python3 hwut_vterm.py       'libvterm found: <name>', exit 0;
                                the message above, exit 1

A TEST THAT USES THIS MODULE catches 'LibraryMissing', prints it and
probes nothing -- its output then differs from its GOOD, and the reason
stands in the difference:

    try:
        with Screen(24, 80) as screen: ...
    except LibraryMissing as error:
        print("NOT PROBED: %s" % error)

The development container ('adm/container/Containerfile') holds the
library, so a census run inside it never meets this message.


5  WHY libvterm
______________________________________________________________________________

Ruled 2026-10-09 (review-r10, r-11d): "use libvterm ... do not use pyte."
No Python module binding the library was found on the package index
('pyvterm' drives a Vectrex display, 'vterm' is a tkinter game terminal),
so the binding is written here, on the test side: no part of hwut that a
user runs depends on it.
