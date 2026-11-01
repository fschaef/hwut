// @hwut {
//     title      = "A terminal's screen read by a test: libvterm through DPI-C."
//     build      { framework = "make", executable = "%.exe"
//                  caps { memory_mb = 2048 } }
//     choices {
//         attributes { features = ["sv-vterm"] }
//         colours    { features = ["sv-vterm"] }
//         events     { features = ["sv-vterm"] }
//         keys       { features = ["sv-vterm"] }
//         missing    { features = ["sv-vterm"] }
//         regions    { features = ["sv-vterm"] }
//         screen     { features = ["sv-vterm"] }
//         text       { features = ["sv-vterm"] }
//         unnoticed  { features = ["sv-vterm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The SystemVerilog port of 'python/TEST/test-hwut_vterm.py', choice
//          for choice, held against its GOOD files by '.link'. WANTS libvterm
//          -- found at run time, no header needed to build. The two
//          APPLICATIONS a Terminal runs here are the Python test's, unchanged
//          (run by 'python3 -c'): they are the system under test, and what
//          they print is in the shared GOOD files.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import hwut_vterm::*;

class SaidRead extends ChangeCallback;
    // Says, beside the key just pressed, what the application read.
    string pressed = "(start)";

    virtual function void on_change(string name, string line_list[$]);
        // RETURN: nothing; the key and the region's line are printed.
        $display("    %s %s", padded(pressed, 22), line_list[0]);   // 'ä': characters, not bytes
    endfunction
endclass

class SaidChange extends ChangeCallback;
    // Says which region changed, and into what.
    virtual function void on_change(string name, string line_list[$]);
        // RETURN: nothing; the region's name and lines are printed.
        $display("    changed  %s %s", padded(name, 5), list_repr(line_list));
    endfunction
endclass

class SaidEvent extends EventCallback;
    // Says every event.
    virtual function void on_event(Event event_);
        // RETURN: nothing; the event is printed.
        $display("    %s", event_.to_string());
    endfunction
endclass

class Test extends HwutRunner;
    localparam string ESC = "\x1b";

    //  THE APPLICATIONS UNDER OBSERVATION -- the Python test's own, word for
    //  word: the system under test is the same, so the GOOD files can be.
    //  SEEING_APP says what it sees, asks the terminal where the cursor is,
    //  then names every key until 'q'.
    localparam string SEEING_APP = {
        "\n",
        "import os, sys, tty, termios\n",
        "print(\"streams are terminals: %s %s %s\"\n",
        "      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))\n",
        "try:    os.close(os.open(\"/dev/tty\", os.O_RDWR)); print(\"controlling terminal: yes\")\n",
        "except OSError: print(\"controlling terminal: no\")\n",
        "print(\"size: %d columns, %d rows\" % tuple(os.get_terminal_size()))\n",
        "print(\"TERM=%s COLUMNS=%s\" % (os.environ.get(\"TERM\"), os.environ.get(\"COLUMNS\")))\n",
        "old = termios.tcgetattr(0); tty.setraw(0)\n",
        "sys.stdout.write(\"\\x1b[6;9H\\x1b[6n\"); sys.stdout.flush()\n",
        "reply = b\"\"\n",
        "while not reply.endswith(b\"R\"): reply += os.read(0, 1)\n",
        "sys.stdout.write(\"\\r\\x1b[7;1Hthe terminal answered: %r\" % reply); sys.stdout.flush()\n",
        "while True:\n",
        "    key = os.read(0, 32)\n",
        "    sys.stdout.write(\"\\x1b[9;1H\\x1b[Kread: %r\" % key); sys.stdout.flush()\n",
        "    if key == b\"q\": break\n",
        "termios.tcsetattr(0, termios.TCSADRAIN, old)\n",
        "print(\"\\r\\nleaving\"); sys.exit(3)\n"};

    //  DRAWING_APP has a head, a body and a foot: 'n' counts in the body, 'f'
    //  rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
    localparam string DRAWING_APP = {
        "\n",
        "import os, sys, tty, termios\n",
        "old = termios.tcgetattr(0); tty.setraw(0)\n",
        "count, foot = 0, \"q=quit\"\n",
        "def draw():\n",
        "    out = \"\\x1b[2J\\x1b[1;1H\\x1b[7m the head \\x1b[0m\"\n",
        "    out += \"\\x1b[3;1Hcount: %d\\x1b[4;1H(press n)\" % count\n",
        "    out += \"\\x1b[8;1H%s\" % foot\n",
        "    sys.stdout.write(out); sys.stdout.flush()\n",
        "draw()\n",
        "while True:\n",
        "    key = os.read(0, 1)\n",
        "    if   key == b\"n\": count += 1\n",
        "    elif key == b\"f\": foot = \"q=quit  f=pressed\"\n",
        "    elif key == b\"q\": break\n",
        "    draw()\n",
        "termios.tcsetattr(0, termios.TCSADRAIN, old)\n"};

    function new();
        // RETURN: the runner of this test.
        super.new("A terminal's screen read by a test: libvterm through ctypes.",
                  '{"text", "screen", "attributes", "colours", "unnoticed", "keys", "regions", "events", "missing"});
    endfunction

    function void shown(Screen screen);
        // RETURN: nothing; every row that holds something, framed, then the
        //         cursor.
        for (int row = 0; row < screen.row_n; row++) begin
            string line = screen.line(row);
            if (line.len()) $display("    %0d |%s|", row, line);
        end
        $display("    cursor %s", screen.cursor_repr());
    endfunction

    function bit missing(Screen screen);
        // RETURN: 1, and the one line said, where the library was not found;
        //         0 else.
        if (screen != null) return 0;
        $display("NOT PROBED: %s", last_error.message);
        return 1;
    endfunction

    // ----------------------------------------------------------------- Screen
    function void run_text();
        // RETURN: nothing; plain bytes, UTF-8, a wide character, a wrapping line.
        Screen s;
        Cell   cell_value;
        s = Screen::create(4, 12);
        if (missing(s)) return;
        $display("-- plain, then carriage return and line feed");
        void'(s.feed("hello\r\nworld"));
        shown(s); s.close();
        s = Screen::create(4, 12);
        $display("-- UTF-8: two bytes, one cell; a wide character, two");
        void'(s.feed("\xc3\xa4\xe6\x97\xa5x"));                          // 'ä日x'
        shown(s);
        for (int column = 0; column < 4; column++) begin
            cell_value = s.cell_(0, column);
            $display("    column %0d: %s width %0d", column, padded(str_repr(cell_value.text), 6), cell_value.width);
        end
        s.close();
        s = Screen::create(3, 5);
        $display("-- seven characters on five columns: the line wraps");
        void'(s.feed("abcdefg"));
        shown(s); s.close();
        s = Screen::create(2, 4);
        $display("-- a str is sent as UTF-8; the bytes taken are counted");
        $display("    taken: %0d", s.feed("a\xc3\xa4"));
        $display("-- a place off the screen");
        if (s.cell_(2, 0) == null) $display("    %s: %s", s.error.kind, s.error.message);
        s.close();
    endfunction

    function void run_screen();
        // RETURN: nothing; the sequences a full-screen program writes.
        Screen s;
        s = Screen::create(5, 20);
        if (missing(s)) return;
        $display("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'");
        void'(s.feed("first line\r\nsecond line\r\nthird line"));
        void'(s.feed({ESC, "[2;4HX"}));
        shown(s);
        $display("-- erase to the end of that line");
        void'(s.feed({ESC, "[K"}));
        shown(s);
        $display("-- clear the screen, home, one word");
        void'(s.feed({ESC, "[2J", ESC, "[Hclean"}));
        shown(s);
        s.close();
    endfunction

    function void run_attributes();
        // RETURN: nothing; each attribute by its SGR code, then all at once,
        //         then reset.
        Screen s;
        Cell   cell_value;
        string said;
        s = Screen::create(3, 20);
        if (missing(s)) return;
        for (int i = 0; i < 7; i++)
            void'(s.feed({ESC, "[", ATTRIBUTE_SGR[i], "m", ATTRIBUTE_NAME[i].substr(0, 0), ESC, "[0m"}));
        $display("-- one cell per attribute, set by its own code");
        for (int i = 0; i < 7; i++) begin
            cell_value = s.cell_(0, i);
            //  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
            said = cell_value.attribute_text();
            if (said.len() == 0) said = "(none)";
            if (ATTRIBUTE_NAME[i] == "conceal") said = "conceal, or (none) on libvterm 0.1";
            $display("    %s  %s", str_repr(cell_value.text), said);
        end
        $display("-- bold, underline and reverse at once; then reset");
        void'(s.feed({"\r\n", ESC, "[1;4;7mA", ESC, "[0mB"}));
        for (int i = 0; i < 2; i++) begin
            cell_value = s.cell_(1, i);
            said = cell_value.attribute_text();
            if (said.len() == 0) said = "(none)";
            $display("    %s  %s", str_repr(cell_value.text), said);
        end
        $display("-- double underline (SGR 21) is underlined");
        void'(s.feed({ESC, "[21mD"}));
        $display("    %s  %s", str_repr("D"), s.cell_(1, 2).attribute_text());
        s.close();
    endfunction

    function void run_colours();
        // RETURN: nothing; the default, an indexed, a palette and a direct
        //         colour, each read as red, green, blue.
        string what[5] = '{"default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3"};
        Screen s;
        Cell   cell_value;
        string said;
        s = Screen::create(2, 20);
        if (missing(s)) return;
        void'(s.feed({"d", ESC, "[31mr", ESC, "[0m", ESC, "[38;5;196mp", ESC, "[0m", ESC, "[38;2;10;20;30mt", ESC, "[0m"}));
        void'(s.feed({ESC, "[48;2;1;2;3mb", ESC, "[0m"}));
        for (int column = 0; column < 5; column++) begin
            cell_value = s.cell_(0, column);
            //  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: mostly
            //  red is the claim, not its shade.
            if (what[column] == "indexed 31") begin
                int most = cell_value.foreground[1] > cell_value.foreground[2] ? cell_value.foreground[1] : cell_value.foreground[2];
                said = {"fg mostly red: ", bool_repr(cell_value.foreground[0] > 2 * most)};
            end else
                said = {"fg ", cell_value.foreground_repr(), "  bg ", cell_value.background_repr()};
            $display("    %s %s  %s", padded(what[column], 18), str_repr(cell_value.text), said);
        end
        s.close();
    endfunction

    // --------------------------------------------------------------- Terminal
    function void run_unnoticed();
        // RETURN: nothing; what the application sees: a terminal, the
        //         terminal's size, TERM, its question answered; its exit status.
        Terminal t;
        string   argv[$] = {};
        int      running, status;
        void'(set_environment("COLUMNS", "300"));
        t = Terminal::create(10, 44);
        if (missing(t)) return;
        argv    = '{"python3", "-c", SEEING_APP};
        running = t.run(argv);
        $display("-- still running after its first screen: %s", bool_repr(running == 1));
        shown(t);
        void'(t.send("q"));
        void'(t.wait_(status));
        $display("-- after 'q': exit status %0d", status);
        shown(t);
        t.close();
    endfunction

    function void run_keys();
        // RETURN: nothing; named keys, function keys, a modifier, a non-ASCII
        //         character: what the application READS for each.
        string   key[9]      = '{"up", "enter", "tab", "escape", "f5", "delete", "c", "x", "up"};
        string   modifier[9] = '{"", "", "", "", "", "", "ctrl", "alt", "shift"};
        Terminal t;
        SaidRead said = new();
        string   argv[$] = {};
        int      status;
        t = Terminal::create(10, 44);
        if (missing(t)) return;
        t.region("read", 8);
        t.on_change(said);
        said.pressed = "(start)";
        argv = '{"python3", "-c", SEEING_APP};
        void'(t.run(argv));
        for (int i = 0; i < 9; i++) begin
            said.pressed = modifier[i].len() ? {modifier[i], " ", key[i]} : key[i];
            void'(t.press(key[i], modifier[i]));
        end
        said.pressed = "send '\xc3\xa4'";
        void'(t.send("\xc3\xa4"));
        said.pressed = "send 'q'";
        void'(t.send("q"));
        void'(t.wait_(status));
        t.close();
    endfunction

    function void run_regions();
        // RETURN: nothing; three regions declared before the run; each key
        //         changes one of them, and ONLY that one is told -- once per
        //         pause, whatever the application wrote in between.
        string        said[6]  = '{"'n'", "'n'", "'r': a redraw, nothing new", "'f'", "'nnn', typed at once", "'q'"};
        string        typed[6] = '{"n", "n", "r", "f", "nnn", "q"};
        Terminal      t;
        SaidChange    told = new();
        string        argv[$] = {};
        string_list_t line_list;
        int           status;
        //  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must
        //  be ONE report on a loaded machine too.
        t = Terminal::create(8, 30, 0.3);
        if (missing(t)) return;
        t.region("head", 0);
        t.region("body", 2, 2);
        t.region("foot", -1);
        t.on_change(told);
        $display("-- run");
        argv = '{"python3", "-c", DRAWING_APP};
        void'(t.run(argv));
        for (int i = 0; i < 6; i++) begin
            $display("-- %s", said[i]);
            void'(t.send(typed[i]));
        end
        void'(t.wait_(status));
        void'(t.region_text("body", line_list));
        $display("-- exit status %0d; a region asked by name: %s", status, list_repr(line_list));
        if (!t.region_text("nosuch", line_list)) $display("-- no such region: %s %s", t.error.kind, t.error.message);
        t.close();
    endfunction

    function void run_events();
        // RETURN: nothing; the RAW layer, on bytes the test feeds itself; and
        //         the terminal's answer to a question, with no application.
        string    said[6] = '{"'ab'", "a line feed and 'c'", "the cursor to row 4, hidden", "the alternate screen",
                              "the bell", "nothing that draws: a reset of attributes"};
        string    data[6];
        Terminal  t;
        SaidEvent told = new();
        data = '{"ab", "\r\nc", {ESC, "[4;1H", ESC, "[?25l"}, {ESC, "[?1049h"}, "\x07", {ESC, "[0m"}};
        t = Terminal::create(4, 20);
        if (missing(t)) return;
        t.on_event(told);
        for (int i = 0; i < 6; i++) begin
            $display("-- fed: %s", said[i]);
            void'(t.feed(data[i]));
        end
        $display("-- asked where the cursor is, nobody running: the answer waits");
        void'(t.feed({ESC, "[2;5H", ESC, "[6n"}));
        $display("    answer() = %s", bytes_repr(t.answer()));
        $display("-- a key pressed with nobody running");
        void'(t.press("f1", "", 0));
        $display("    answer() = %s", bytes_repr(t.answer()));
        t.close();
    endfunction

    function void run_missing();
        // RETURN: nothing; HWUT_LIBVTERM naming no file: 'LibraryMissing', by
        //         name, with the hint how to install the library.
        Screen s;
        string message, first;
        int    cut;
        void'(set_environment(LIBRARY_VARIABLE, "/nowhere/libvterm.so"));
        reset_library();
        s = Screen::create();
        if (s != null) begin
            $display("a Screen stands on a library that is not there");
            s.close();
            return;
        end
        //  THE SYSTEM'S OWN WORDS for the failed load are left out; what this
        //  module says -- the line, and the way to install -- stands.
        message = last_error.message;
        cut     = message.len();
        for (int i = 0; i < message.len(); i++) if (message[i] == "\n") begin cut = i; break; end
        first = message.substr(0, cut - 1);
        for (int i = 0; i + 3 < first.len(); i++) if (first.substr(i, i + 3) == " -- ") begin first = first.substr(0, i - 1); break; end
        $display("%s: %s", last_error.kind, first);
        if (cut < message.len()) $display("%s", message.substr(cut + 1, message.len() - 1));
    endfunction

    virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' ran.
        case (choice)
            "text":       run_text();
            "screen":     run_screen();
            "attributes": run_attributes();
            "colours":    run_colours();
            "unnoticed":  run_unnoticed();
            "keys":       run_keys();
            "regions":    run_regions();
            "events":     run_events();
            "missing":    run_missing();
        endcase
    endtask
endclass

module test_hwut_vterm;
    initial begin
        Test test = new();
        test.run();
    end
endmodule
