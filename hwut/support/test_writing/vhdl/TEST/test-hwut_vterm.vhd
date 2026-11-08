-- @hwut {
--     title      = "A terminal's screen read by a test: libvterm through dlopen."
--     build      { framework = "make", target = "%.exe" }
--     choices {
--         attributes { features = ["vhdl-vterm"] }
--         colours    { features = ["vhdl-vterm"] }
--         events     { features = ["vhdl-vterm"] }
--         keys       { features = ["vhdl-vterm"] }
--         missing    { features = ["vhdl-vterm"] }
--         regions    { features = ["vhdl-vterm"] }
--         screen     { features = ["vhdl-vterm"] }
--         text       { features = ["vhdl-vterm"] }
--         unnoticed  { features = ["vhdl-vterm"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The VHDL port of 'python/TEST/test-hwut_vterm.py', choice for
--          choice, held against its GOOD files by '.link'. WANTS libvterm --
--          found at run time, no header needed to build. The two APPLICATIONS
--          a Terminal runs here are the Python test's, unchanged: they are the
--          system under test, and what they print is in the shared GOOD files.
--          ONE Terminal package serves every choice: its callbacks say what
--          the choice running wants said ('told').
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_runner.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.hwut_vterm.all;

entity test_hwut_vterm is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
end entity;

architecture test of test_hwut_vterm is
    --  WHAT THE CALLBACKS SAY, as the choice running wants it
    constant SAY_NOTHING : natural := 0;
    constant SAY_READ    : natural := 1;        -- 'keys':    the key pressed, the row it shows on
    constant SAY_CHANGE  : natural := 2;        -- 'regions': the region and its lines
    constant SAY_EVENT   : natural := 3;        -- 'events':  the event

    type TellingState is protected
        procedure set(mode : natural; pressed_text_now : string := "");
        impure function mode_of return natural;
        impure function pressed return string;
    end protected;

    type TellingState is protected body
        variable mode_now     : natural := SAY_NOTHING;
        variable pressed_text : line    := new string'("");
        procedure set(mode : natural; pressed_text_now : string := "") is
        begin mode_now := mode; pressed_text := new string'(pressed_text_now); end procedure;
        impure function mode_of return natural is begin return mode_now; end function;
        impure function pressed return string is begin return pressed_text.all; end function;
    end protected body;

    shared variable told : TellingState;

    procedure said_event(event : VtermEvent) is
    begin
        if told.mode_of = SAY_EVENT then print("    " & to_string(event)); end if;
    end procedure;

    procedure said_change(name : string; lines : str_list) is
    begin
        case told.mode_of is
            when SAY_READ   => print("    " & ljust(told.pressed, 22) & " " & item(lines, 0));   -- characters, not bytes
            when SAY_CHANGE => print("    changed  " & ljust(name, 5) & " " & list_repr(lines));
            when others     => null;
        end case;
    end procedure;

    package term is new work.hwut_vterm_terminal generic map (on_event => said_event, on_change => said_change);
    use term.all;

    constant SEEING_APP : string :=
        "" & LF &
        "import os, sys, tty, termios" & LF &
        "print(""streams are terminals: %s %s %s""" & LF &
        "      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))" & LF &
        "try:    os.close(os.open(""/dev/tty"", os.O_RDWR)); print(""controlling terminal: yes"")" & LF &
        "except OSError: print(""controlling terminal: no"")" & LF &
        "print(""size: %d columns, %d rows"" % tuple(os.get_terminal_size()))" & LF &
        "print(""TERM=%s COLUMNS=%s"" % (os.environ.get(""TERM""), os.environ.get(""COLUMNS"")))" & LF &
        "old = termios.tcgetattr(0); tty.setraw(0)" & LF &
        "sys.stdout.write(""\x1b[6;9H\x1b[6n""); sys.stdout.flush()" & LF &
        "reply = b""""" & LF &
        "while not reply.endswith(b""R""): reply += os.read(0, 1)" & LF &
        "sys.stdout.write(""\r\x1b[7;1Hthe terminal answered: %r"" % reply); sys.stdout.flush()" & LF &
        "while True:" & LF &
        "    key = os.read(0, 32)" & LF &
        "    sys.stdout.write(""\x1b[9;1H\x1b[Kread: %r"" % key); sys.stdout.flush()" & LF &
        "    if key == b""q"": break" & LF &
        "termios.tcsetattr(0, termios.TCSADRAIN, old)" & LF &
        "print(""\r\nleaving""); sys.exit(3)" & LF &
        "";
    constant DRAWING_APP : string :=
        "" & LF &
        "import os, sys, tty, termios" & LF &
        "old = termios.tcgetattr(0); tty.setraw(0)" & LF &
        "count, foot = 0, ""q=quit""" & LF &
        "def draw():" & LF &
        "    out = ""\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m""" & LF &
        "    out += ""\x1b[3;1Hcount: %d\x1b[4;1H(press n)"" % count" & LF &
        "    out += ""\x1b[8;1H%s"" % foot" & LF &
        "    sys.stdout.write(out); sys.stdout.flush()" & LF &
        "draw()" & LF &
        "while True:" & LF &
        "    key = os.read(0, 1)" & LF &
        "    if   key == b""n"": count += 1" & LF &
        "    elif key == b""f"": foot = ""q=quit  f=pressed""" & LF &
        "    elif key == b""q"": break" & LF &
        "    draw()" & LF &
        "termios.tcsetattr(0, termios.TCSADRAIN, old)" & LF &
        "";

    procedure shown(variable s : inout Screen) is
        -- RETURN: nothing; every row that holds something, framed, then the cursor.
        constant place : integer_vector := s.cursor;
    begin
        for row in 0 to s.row_n - 1 loop
            if s.line(row) /= "" then print("    " & integer'image(row) & " |" & s.line(row) & "|"); end if;
        end loop;
        print("    cursor (" & integer'image(place(0)) & ", " & integer'image(place(1)) & ")");
    end procedure;

    procedure shown(variable t : inout Terminal; row_n : natural) is
        -- RETURN: nothing; as for a Screen, for the terminal's 'row_n' rows.
        constant place : integer_vector := t.cursor;
    begin
        for row in 0 to row_n - 1 loop
            if t.line(row) /= "" then print("    " & integer'image(row) & " |" & t.line(row) & "|"); end if;
        end loop;
        print("    cursor (" & integer'image(place(0)) & ", " & integer'image(place(1)) & ")");
    end procedure;

    impure function argv_of(app : string) return string is
        -- RETURN: string, 'python3 -c <app>' as words each ended by NUL.
    begin return "python3" & NUL & "-c" & NUL & app & NUL; end function;

    -- ------------------------------------------------------------------ Screen
    procedure run_text is
        variable s    : Screen;
        variable cell : VtermCell;
    begin
        if not s.create(4, 12) then print("NOT PROBED: " & s.error_message); return; end if;
        print("-- plain, then carriage return and line feed");
        s.feed("hello" & CR & LF & "world");
        shown(s); s.close;

        assert s.create(4, 12) severity failure;
        print("-- UTF-8: two bytes, one cell; a wide character, two");
        s.feed(character'val(16#c3#) & character'val(16#a4#) & character'val(16#e6#) & character'val(16#97#)
               & character'val(16#a5#) & "x");                                        -- 'ä日x'
        shown(s);
        for column in 0 to 3 loop
            cell := s.cell(0, column);
            print("    column " & integer'image(column) & ": " & ljust(str_repr(cell_text(cell)), 6)
                  & " width " & integer'image(cell.width));
        end loop;
        s.close;

        assert s.create(3, 5) severity failure;
        print("-- seven characters on five columns: the line wraps");
        s.feed("abcdefg");
        shown(s); s.close;

        assert s.create(2, 4) severity failure;
        print("-- a str is sent as UTF-8; the bytes taken are counted");
        print("    taken: " & integer'image(s.feed("a" & character'val(16#c3#) & character'val(16#a4#))));
        print("-- a place off the screen");
        cell := s.cell(2, 0);
        if s.failed then print("    " & s.error_kind & ": " & s.error_message); end if;
        s.close;
    end procedure;

    procedure run_screen is
        variable s : Screen;
    begin
        if not s.create(5, 20) then print("NOT PROBED: " & s.error_message); return; end if;
        print("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'");
        s.feed("first line" & CR & LF & "second line" & CR & LF & "third line");
        s.feed(ESC & "[2;4HX");
        shown(s);
        print("-- erase to the end of that line");
        s.feed(ESC & "[K");
        shown(s);
        print("-- clear the screen, home, one word");
        s.feed(ESC & "[2J" & ESC & "[Hclean");
        shown(s);
        s.close;
    end procedure;

    procedure run_attributes is
        variable s    : Screen;
        variable cell : VtermCell;
        variable said : line;
    begin
        if not s.create(3, 20) then print("NOT PROBED: " & s.error_message); return; end if;
        for i in 0 to 6 loop
            s.feed(ESC & "[" & item(VTERM_ATTRIBUTE_SGR, i) & "m" & item(VTERM_ATTRIBUTE_NAME, i)(1) & ESC & "[0m");
        end loop;
        print("-- one cell per attribute, set by its own code");
        for i in 0 to 6 loop
            cell := s.cell(0, i);
            --  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
            if attribute_text(cell) = "" then said := new string'("(none)");
            else                              said := new string'(attribute_text(cell));
            end if;
            if item(VTERM_ATTRIBUTE_NAME, i) = "conceal" then said := new string'("conceal, or (none) on libvterm 0.1"); end if;
            print("    " & str_repr(cell_text(cell)) & "  " & said.all);
        end loop;
        print("-- bold, underline and reverse at once; then reset");
        s.feed(CR & LF & ESC & "[1;4;7mA" & ESC & "[0mB");
        for i in 0 to 1 loop
            cell := s.cell(1, i);
            if attribute_text(cell) = "" then said := new string'("(none)");
            else                              said := new string'(attribute_text(cell));
            end if;
            print("    " & str_repr(cell_text(cell)) & "  " & said.all);
        end loop;
        print("-- double underline (SGR 21) is underlined");
        s.feed(ESC & "[21mD");
        cell := s.cell(1, 2);
        print("    'D'  " & attribute_text(cell));
        s.close;
    end procedure;

    function colour_text(set_f : boolean; rgb : integer_vector) return string is
        -- RETURN: string, '(r, g, b)' as Python prints the tuple, or 'None'.
    begin
        if not set_f then return "None"; end if;
        return "(" & integer'image(rgb(0)) & ", " & integer'image(rgb(1)) & ", " & integer'image(rgb(2)) & ")";
    end function;

    procedure run_colours is
        constant what : str_list := "default" & LF & "indexed 31" & LF & "palette 196" & LF & "direct 10;20;30" & LF
                                    & "background 1;2;3" & LF;
        variable s    : Screen;
        variable cell : VtermCell;
        variable said : line;
    begin
        if not s.create(2, 20) then print("NOT PROBED: " & s.error_message); return; end if;
        s.feed("d" & ESC & "[31mr" & ESC & "[0m" & ESC & "[38;5;196mp" & ESC & "[0m" & ESC & "[38;2;10;20;30mt" & ESC & "[0m");
        s.feed(ESC & "[48;2;1;2;3mb" & ESC & "[0m");
        for column in 0 to 4 loop
            cell := s.cell(0, column);
            --  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: mostly
            --  red is the claim, not its shade.
            if item(what, column) = "indexed 31" then
                said := new string'("fg mostly red: "
                                    & bool_repr(cell.foreground(0) > 2 * maximum(cell.foreground(1), cell.foreground(2))));
            else
                said := new string'("fg " & colour_text(cell.foreground_f, cell.foreground)
                                    & "  bg " & colour_text(cell.background_f, cell.background));
            end if;
            print("    " & ljust(item(what, column), 18) & " " & str_repr(cell_text(cell)) & "  " & said.all);
        end loop;
        s.close;
    end procedure;
begin
    main : process
        variable runner : HwutRunner;

        -- ------------------------------------------------------------ Terminal
        procedure run_unnoticed is
            variable t       : Terminal;
            variable running : boolean;
            variable status  : integer;
        begin
            setenv("COLUMNS", "300");
            if not t.create(10, 44, 0.1) then print("NOT PROBED: " & t.error_message); return; end if;
            running := t.run(argv_of(SEEING_APP), "", 10.0);
            print("-- still running after its first screen: " & bool_repr(running));
            shown(t, 10);
            t.send("q", 1.0);
            status := t.wait_exit(10.0);
            print("-- after 'q': exit status " & integer'image(status));
            shown(t, 10);
            t.free;
        end procedure;

        procedure run_keys is
            variable t      : Terminal;
            variable status : integer;
            procedure press(key : string; modifier : string; said : string) is
            begin told.set(SAY_READ, said); t.press(key, modifier, 1.0); end procedure;
        begin
            if not t.create(10, 44, 0.1) then print("NOT PROBED: " & t.error_message); return; end if;
            t.region("read", 8, 1, 0, -1);
            told.set(SAY_READ, "(start)");
            t.run(argv_of(SEEING_APP), "", 10.0);
            press("up", "", "up");          press("enter", "", "enter");    press("tab", "", "tab");
            press("escape", "", "escape");  press("f5", "", "f5");          press("delete", "", "delete");
            press("c", "ctrl", "ctrl c");   press("x", "alt", "alt x");     press("up", "shift", "shift up");
            told.set(SAY_READ, "send '" & character'val(16#c3#) & character'val(16#a4#) & "'");
            t.send(character'val(16#c3#) & character'val(16#a4#), 1.0);
            told.set(SAY_READ, "send 'q'");
            t.send("q", 1.0);
            status := t.wait_exit(10.0);
            told.set(SAY_NOTHING);
            t.free;
        end procedure;

        procedure run_regions is
            variable t      : Terminal;
            variable status : integer;
            procedure act(said : string; typed : string) is
            begin print("-- " & said); t.send(typed, 1.0); end procedure;
        begin
            --  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once
            --  must be ONE report on a loaded machine too.
            if not t.create(8, 30, 0.3) then print("NOT PROBED: " & t.error_message); return; end if;
            t.region("head", 0, 1, 0, -1);
            t.region("body", 2, 2, 0, -1);
            t.region("foot", -1, 1, 0, -1);
            told.set(SAY_CHANGE);
            print("-- run");
            t.run(argv_of(DRAWING_APP), "", 10.0);
            act("'n'", "n"); act("'n'", "n"); act("'r': a redraw, nothing new", "r"); act("'f'", "f");
            act("'nnn', typed at once", "nnn"); act("'q'", "q");
            status := t.wait_exit(10.0);
            print("-- exit status " & integer'image(status) & "; a region asked by name: " & list_repr(t.region_text("body")));
            if t.region_text("nosuch") = "" and t.failed then
                print("-- no such region: " & t.error_kind & " " & t.error_message);
            end if;
            told.set(SAY_NOTHING);
            t.free;
        end procedure;

        procedure run_events is
            variable t : Terminal;
            procedure fed(said : string; data : string) is
            begin print("-- fed: " & said); t.feed(data); end procedure;
        begin
            if not t.create(4, 20, 0.1) then print("NOT PROBED: " & t.error_message); return; end if;
            told.set(SAY_EVENT);
            fed("'ab'", "ab");
            fed("a line feed and 'c'", CR & LF & "c");
            fed("the cursor to row 4, hidden", ESC & "[4;1H" & ESC & "[?25l");
            fed("the alternate screen", ESC & "[?1049h");
            fed("the bell", "" & BEL);
            fed("nothing that draws: a reset of attributes", ESC & "[0m");
            print("-- asked where the cursor is, nobody running: the answer waits");
            t.feed(ESC & "[2;5H" & ESC & "[6n");
            print("    answer() = " & bytes_repr(t.answer));
            print("-- a key pressed with nobody running");
            t.press("f1", "", 0.0);
            print("    answer() = " & bytes_repr(t.answer));
            told.set(SAY_NOTHING);
            t.free;
        end procedure;

        procedure run_missing is
            variable s     : Screen;
            variable first : line;
            variable cut   : natural := 0;
        begin
            setenv(VTERM_LIBRARY_VARIABLE, "/nowhere/libvterm.so");
            reset_library;
            if s.create(24, 80) then
                print("a Screen stands on a library that is not there");
                s.close;
                return;
            end if;
            --  THE SYSTEM'S OWN WORDS for the failed load are left out; what
            --  this module says -- the line, and the way to install -- stands.
            first := new string'(item(s.error_message & LF, 0));
            for i in first'left to first'right - 3 loop
                if first(i to i + 3) = " -- " then cut := i; exit; end if;
            end loop;
            if cut /= 0 then print(s.error_kind & ": " & first(first'left to cut - 1));
            else             print(s.error_kind & ": " & first.all);
            end if;
            if after_line(s.error_message) /= "" or item_n(s.error_message & LF) > 1 then
                print(after_line(s.error_message));
            end if;
        end procedure;
    begin
        runner.init(HWUT_ARGC, HWUT_ARGV1, "A terminal's screen read by a test: libvterm through dlopen.");
        runner.add("text"); runner.add("screen"); runner.add("attributes"); runner.add("colours");
        runner.add("unnoticed"); runner.add("keys"); runner.add("regions"); runner.add("events");
        runner.add("missing");
        while runner.dispatch loop
            if    runner.choice = "text"       then run_text;
            elsif runner.choice = "screen"     then run_screen;
            elsif runner.choice = "attributes" then run_attributes;
            elsif runner.choice = "colours"    then run_colours;
            elsif runner.choice = "unnoticed"  then run_unnoticed;
            elsif runner.choice = "keys"       then run_keys;
            elsif runner.choice = "regions"    then run_regions;
            elsif runner.choice = "events"     then run_events;
            elsif runner.choice = "missing"    then run_missing;
            end if;
            runner.choice_done;
        end loop;
        wait;
    end process;
end architecture;
