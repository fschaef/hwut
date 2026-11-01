! @hwut {
!     title      = "A terminal's screen read by a test: libvterm through ISO_C_BINDING."
!     build      { framework = "make", executable = "%.exe" }
!     choices {
!         attributes { features = ["fortran-vterm"] }
!         colours    { features = ["fortran-vterm"] }
!         events     { features = ["fortran-vterm"] }
!         keys       { features = ["fortran-vterm"] }
!         missing    { features = ["fortran-vterm"] }
!         regions    { features = ["fortran-vterm"] }
!         screen     { features = ["fortran-vterm"] }
!         text       { features = ["fortran-vterm"] }
!         unnoticed  { features = ["fortran-vterm"] }
!     }
!     interactive = true
! }
!
! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: The Fortran port of 'python/TEST/test-hwut_vterm.py', choice for
!          choice, held against its GOOD files by '.link'. WANTS libvterm --
!          found at run time, no header needed to build. The two APPLICATIONS
!          a Terminal runs here are the Python test's, unchanged, run by
!          'python3': they are the system under test, and what they print is
!          in the shared GOOD files.
! _____________________________________________________________________________
module vterm_said
    ! WHAT THE CALLBACKS SAY -- module procedures, and the one word they share
    ! with the test ('pressed'), as Python's lambdas share it by closure.
    use hwut_text
    use hwut_pytext
    use hwut_vterm
    implicit none
    character(:), allocatable :: pressed

contains

    function padded(text, width) result(line)
        ! RETURN: 'text' filled with blanks to 'width' CHARACTERS -- as
        !         Python's '%-6s' counts, not bytes.
        character(*), intent(in)  :: text
        integer, intent(in)       :: width
        character(:), allocatable :: line
        line = text // repeat(" ", max(0, width - char_count(text)))
    end function

    function lines_repr(line_list) result(text)
        ! RETURN: the lines as Python prints a list of str.
        type(string), intent(in)  :: line_list(:)
        character(:), allocatable :: text
        integer                   :: i
        text = "["
        do i = 1, size(line_list)
            if( i > 1 ) text = text // ", "
            text = text // repr(line_list(i)%s)
        end do
        text = text // "]"
    end function

    subroutine said_read(name, line_list)
        character(*), intent(in) :: name
        type(string), intent(in) :: line_list(:)
        call say("    " // padded(pressed, 22) // " " // line_list(1)%s)
    end subroutine

    subroutine said_change(name, line_list)
        character(*), intent(in) :: name
        type(string), intent(in) :: line_list(:)
        call say("    changed  " // padded(name, 5) // " " // lines_repr(line_list))
    end subroutine

    subroutine said_event(event)
        type(VtermEvent), intent(in) :: event
        call say("    " // event%str())
    end subroutine

end module vterm_said

module test_hwut_vterm_choices
    use, intrinsic :: iso_c_binding, only: c_double
    use hwut_text
    use hwut_pytext
    use hwut_posix, only: c_setenv
    use hwut_runner
    use hwut_vterm
    use vterm_said
    implicit none

    ! THE APPLICATIONS UNDER OBSERVATION -- the Python test's own, word for
    ! word: the system under test is the same, so the GOOD files can be.
    character(*), parameter :: SEEING_APP = NL &
        // 'import os, sys, tty, termios' // NL &
        // 'print("streams are terminals: %s %s %s"' // NL &
        // '      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))' // NL &
        // 'try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")' // NL &
        // 'except OSError: print("controlling terminal: no")' // NL &
        // 'print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))' // NL &
        // 'print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))' // NL &
        // 'old = termios.tcgetattr(0); tty.setraw(0)' // NL &
        // 'sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()' // NL &
        // 'reply = b""' // NL &
        // 'while not reply.endswith(b"R"): reply += os.read(0, 1)' // NL &
        // 'sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()' // NL &
        // 'while True:' // NL &
        // '    key = os.read(0, 32)' // NL &
        // '    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()' // NL &
        // '    if key == b"q": break' // NL &
        // 'termios.tcsetattr(0, termios.TCSADRAIN, old)' // NL &
        // 'print("\r\nleaving"); sys.exit(3)' // NL

    character(*), parameter :: DRAWING_APP = NL &
        // 'import os, sys, tty, termios' // NL &
        // 'old = termios.tcgetattr(0); tty.setraw(0)' // NL &
        // 'count, foot = 0, "q=quit"' // NL &
        // 'def draw():' // NL &
        // '    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"' // NL &
        // '    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count' // NL &
        // '    out += "\x1b[8;1H%s" % foot' // NL &
        // '    sys.stdout.write(out); sys.stdout.flush()' // NL &
        // 'draw()' // NL &
        // 'while True:' // NL &
        // '    key = os.read(0, 1)' // NL &
        // '    if   key == b"n": count += 1' // NL &
        // '    elif key == b"f": foot = "q=quit  f=pressed"' // NL &
        // '    elif key == b"q": break' // NL &
        // '    draw()' // NL &
        // 'termios.tcsetattr(0, termios.TCSADRAIN, old)' // NL

    type(VtermError) :: error
    integer          :: stat

contains

    logical function missing()
        ! RETURN: .true., and the one line said, where the library was not
        !         found by the last constructor; .false. else.
        missing = stat /= 0
        if( missing ) call say("NOT PROBED: " // error%message)
    end function

    subroutine shown(s)
        ! RETURN: nothing; every row that holds something, framed, then the
        !         cursor.
        class(Screen), intent(in) :: s
        type(string), allocatable :: line(:)
        integer                   :: row, at(2)
        line = s%line_list()
        do row = 1, size(line)
            if( len(line(row)%s) > 0 ) call say("    " // str(row - 1) // " |" // line(row)%s // "|")
        end do
        at = s%cursor()
        call say("    cursor (" // str(at(1)) // ", " // str(at(2)) // ")")
    end subroutine

    function python3(app) result(argv)
        ! RETURN: the command line that runs the Python text 'app'.
        character(*), intent(in) :: app
        type(string)             :: argv(3)
        argv(1)%s = "python3"
        argv(2)%s = "-c"
        argv(3)%s = app
    end function

    ! ---------------------------------------------------------------- Screen
    subroutine run_text()
        type(Screen) :: s
        type(Cell)   :: c
        integer      :: column, n
        s = Screen(4, 12, stat, error)
        if( missing() ) return
        call say("-- plain, then carriage return and line feed")
        n = s%feed("hello" // achar(13) // NL // "world")
        call shown(s); call s%close()

        s = Screen(4, 12)
        call say("-- UTF-8: two bytes, one cell; a wide character, two")
        n = s%feed("ä日x")
        call shown(s)
        do column = 0, 3
            c = s%cell(0, column)
            call say("    column " // str(column) // ": " // padded(repr(c%text), 6) // " width " // str(c%width))
        end do
        call s%close()

        s = Screen(3, 5)
        call say("-- seven characters on five columns: the line wraps")
        n = s%feed("abcdefg")
        call shown(s); call s%close()

        s = Screen(2, 4)
        call say("-- a str is sent as UTF-8; the bytes taken are counted")
        call say("    taken: " // str(s%feed("aä")))
        call say("-- a place off the screen")
        c = s%cell(2, 0, stat, error)
        if( stat /= 0 ) call say("    " // error%kind // ": " // error%message)
        call s%close()
    end subroutine

    subroutine run_screen()
        type(Screen) :: s
        integer      :: n
        s = Screen(5, 20, stat, error)
        if( missing() ) return
        call say("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'")
        n = s%feed("first line" // achar(13) // NL // "second line" // achar(13) // NL // "third line")
        n = s%feed(ESC // "[2;4H" // "X")
        call shown(s)
        call say("-- erase to the end of that line")
        n = s%feed(ESC // "[K")
        call shown(s)
        call say("-- clear the screen, home, one word")
        n = s%feed(ESC // "[2J" // ESC // "[H" // "clean")
        call shown(s)
        call s%close()
    end subroutine

    subroutine run_attributes()
        type(Screen)              :: s
        type(Cell)                :: c
        character(:), allocatable :: said
        integer                   :: i, n
        s = Screen(3, 20, stat, error)
        if( missing() ) return
        do i = 1, 7
            n = s%feed(ESC // "[" // ATTRIBUTE_SGR(i) // "m" // ATTRIBUTE_NAME(i)(1:1) // ESC // "[0m")
        end do
        call say("-- one cell per attribute, set by its own code")
        do i = 1, 7
            c    = s%cell(0, i - 1)
            ! 'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
            said = c%attribute_text()
            if( len(said) == 0 ) said = "(none)"
            if( trim(ATTRIBUTE_NAME(i)) == "conceal" ) said = "conceal, or (none) on libvterm 0.1"
            call say("    " // repr(c%text) // "  " // said)
        end do
        call say("-- bold, underline and reverse at once; then reset")
        n = s%feed(achar(13) // NL // ESC // "[1;4;7mA" // ESC // "[0mB")
        do i = 0, 1
            c    = s%cell(1, i)
            said = c%attribute_text()
            if( len(said) == 0 ) said = "(none)"
            call say("    " // repr(c%text) // "  " // said)
        end do
        call say("-- double underline (SGR 21) is underlined")
        n = s%feed(ESC // "[21mD")
        c = s%cell(1, 2)
        call say("    " // repr("D") // "  " // c%attribute_text())
        call s%close()
    end subroutine

    function colour_text(set_f, rgb) result(text)
        ! RETURN: '(r, g, b)' as Python prints the tuple, or 'None'.
        logical, intent(in)       :: set_f
        integer, intent(in)       :: rgb(3)
        character(:), allocatable :: text
        text = "None"
        if( set_f ) text = "(" // str(rgb(1)) // ", " // str(rgb(2)) // ", " // str(rgb(3)) // ")"
    end function

    subroutine run_colours()
        type(Screen)              :: s
        type(Cell)                :: c
        type(string)              :: what(5)
        character(:), allocatable :: said
        integer                   :: column, n
        what = [string("default         "), string("indexed 31      "), string("palette 196     "), &
                string("direct 10;20;30 "), string("background 1;2;3")]
        s = Screen(2, 20, stat, error)
        if( missing() ) return
        n = s%feed("d" // ESC // "[31mr" // ESC // "[0m" // ESC // "[38;5;196mp" // ESC // "[0m" &
                   // ESC // "[38;2;10;20;30mt" // ESC // "[0m")
        n = s%feed(ESC // "[48;2;1;2;3mb" // ESC // "[0m")
        do column = 0, 4
            c = s%cell(0, column)
            ! THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that one
            ! is a colour and mostly red is the claim, not its shade.
            if( trim(what(column + 1)%s) == "indexed 31" ) then
                said = "fg mostly red: " // repr(c%foreground(1) > 2 * max(c%foreground(2), c%foreground(3)))
            else
                said = "fg " // colour_text(c%foreground_f, c%foreground) // "  bg " &
                       // colour_text(c%background_f, c%background)
            end if
            call say("    " // padded(trim(what(column + 1)%s), 18) // " " // repr(c%text) // "  " // said)
        end do
        call s%close()
    end subroutine

    ! -------------------------------------------------------------- Terminal
    subroutine run_unnoticed()
        type(Terminal) :: t
        logical        :: running
        integer        :: status
        call c_setenv("COLUMNS", "300")
        t = Terminal(10, 44, stat = stat, error = error)
        if( missing() ) return
        running = t%run(python3(SEEING_APP))
        call say("-- still running after its first screen: " // repr(running))
        call shown(t)
        running = t%send("q")
        status  = t%wait()
        call say("-- after 'q': exit status " // str(status))
        call shown(t)
        call t%close()
    end subroutine

    subroutine run_keys()
        type(Terminal) :: t
        type(string)   :: key(9), modifier(9)
        logical        :: running
        integer        :: i, status
        key      = [string("up    "), string("enter "), string("tab   "), string("escape"), string("f5    "), &
                    string("delete"), string("c     "), string("x     "), string("up    ")]
        modifier = [string("     "), string("     "), string("     "), string("     "), string("     "), &
                    string("     "), string("ctrl "), string("alt  "), string("shift")]
        t = Terminal(10, 44, stat = stat, error = error)
        if( missing() ) return
        call t%region("read", row = 8)
        call t%on_change(said_read)
        pressed = "(start)"
        running = t%run(python3(SEEING_APP))
        do i = 1, 9
            if( len_trim(modifier(i)%s) > 0 ) then
                pressed = trim(modifier(i)%s) // " " // trim(key(i)%s)
                running = t%press(trim(key(i)%s), trim(modifier(i)%s))
            else
                pressed = trim(key(i)%s)
                running = t%press(trim(key(i)%s))
            end if
        end do
        pressed = "send 'ä'"
        running = t%send("ä")
        pressed = "send 'q'"
        running = t%send("q")
        status  = t%wait()
        call t%close()
    end subroutine

    subroutine run_regions()
        type(Terminal)            :: t
        type(string)              :: said(6), typed(6)
        type(string), allocatable :: body(:)
        logical                   :: running
        integer                   :: i, status
        said  = [string("'n'                       "), string("'n'                       "), &
                 string("'r': a redraw, nothing new"), string("'f'                       "), &
                 string("'nnn', typed at once      "), string("'q'                       ")]
        typed = [string("n  "), string("n  "), string("r  "), string("f  "), string("nnn"), string("q  ")]
        ! A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
        ! ONE report on a loaded machine too.
        t = Terminal(8, 30, settle_s = 0.3_c_double, stat = stat, error = error)
        if( missing() ) return
        call t%region("head", row = 0)
        call t%region("body", row = 2, row_n = 2)
        call t%region("foot", row = -1)
        call t%on_change(said_change)
        call say("-- run")
        running = t%run(python3(DRAWING_APP))
        do i = 1, 6
            call say("-- " // trim(said(i)%s))
            running = t%send(trim(typed(i)%s))
        end do
        status = t%wait()
        body   = t%region_text("body")
        call say("-- exit status " // str(status) // "; a region asked by name: " // lines_repr(body))
        body = t%region_text("nosuch", stat, error)
        if( stat /= 0 ) call say("-- no such region: " // error%kind // " " // error%message)
        call t%close()
    end subroutine

    subroutine run_events()
        type(Terminal) :: t
        type(string)   :: said(6), data(6)
        logical        :: running
        integer        :: i, n
        said = [string("'ab'"), string("a line feed and 'c'"), string("the cursor to row 4, hidden"), &
                string("the alternate screen"), string("the bell"), &
                string("nothing that draws: a reset of attributes")]
        data(1)%s = "ab"
        data(2)%s = achar(13) // NL // "c"
        data(3)%s = ESC // "[4;1H" // ESC // "[?25l"
        data(4)%s = ESC // "[?1049h"
        data(5)%s = achar(7)
        data(6)%s = ESC // "[0m"
        t = Terminal(4, 20, stat = stat, error = error)
        if( missing() ) return
        call t%on_event(said_event)
        do i = 1, 6
            call say("-- fed: " // said(i)%s)
            n = t%feed(data(i)%s)
        end do
        call say("-- asked where the cursor is, nobody running: the answer waits")
        n = t%feed(ESC // "[2;5H" // ESC // "[6n")
        call say("    answer() = " // bytes_repr(t%answer()))
        call say("-- a key pressed with nobody running")
        running = t%press("f1", react_s = 0.0_c_double)
        call say("    answer() = " // bytes_repr(t%answer()))
        call t%close()
    end subroutine

    subroutine run_missing()
        type(Screen)              :: s
        type(string), allocatable :: line(:)
        integer                   :: i, cut
        call c_setenv(LIBRARY_VARIABLE, "/nowhere/libvterm.so")
        call reset_library()
        s = Screen(stat = stat, error = error)
        if( stat == 0 ) then
            call say("a Screen stands on a library that is not there")
            call s%close()
            return
        end if
        ! THE SYSTEM'S OWN WORDS for the failed load are left out; what this
        ! module says -- the line, and the way to install -- stands.
        line = split_lines(error%message)
        cut  = index(line(1)%s, " -- ")
        if( cut == 0 ) cut = len(line(1)%s) + 1
        call say(error%kind // ": " // line(1)%s(:cut - 1))
        do i = 2, size(line)
            call say(line(i)%s)
        end do
    end subroutine

end module test_hwut_vterm_choices

program test_hwut_vterm
    ! THE CHOICES ARE MODULE PROCEDURES: a procedure pointer to an internal
    ! one would need a trampoline, and with it an executable stack.
    use hwut_runner
    use test_hwut_vterm_choices
    implicit none
    type(HwutRunner) :: runner
    runner = HwutRunner("A terminal's screen read by a test: libvterm through ISO_C_BINDING.", [ &
                 HwutChoice("text", run_text), HwutChoice("screen", run_screen), &
                 HwutChoice("attributes", run_attributes), HwutChoice("colours", run_colours), &
                 HwutChoice("unnoticed", run_unnoticed), HwutChoice("keys", run_keys), &
                 HwutChoice("regions", run_regions), HwutChoice("events", run_events), &
                 HwutChoice("missing", run_missing)])
    call runner%run()
end program test_hwut_vterm
