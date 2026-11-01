// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
//          'python/hwut_vterm.py' (README-hwut_vterm.txt): libvterm, loaded
//          at run time.
//
//     import hwut_vterm::*;
//     Screen screen = Screen::create(24, 80);
//     Cell   cell;
//     if (screen == null) begin $display("NOT PROBED: %s", last_error.message); return; end
//     void'(screen.feed("\x1b[1mbold\x1b[0m plain"));
//     screen.line(0)                          -- 'bold plain'
//     cell = screen.cell_(0, 0);              -- cell.bold_f 1 ('cell' is a keyword)
//     screen.close();
//
// THE LIBRARY IS THE C PORT'S BUSINESS ('../c/hwut_vterm.c', through DPI-C:
// 'hwut_vterm_dpi.c'): it is FOUND at run time ('dlopen') -- under the name
// HWUT_LIBVTERM gives, or as the system knows it ('libvterm.so.0'; Debian:
// 'libvterm0') -- no header is needed to build, and the cell's layout is
// measured, not assumed. So is the pseudo-terminal an application runs on.
//
// TWO CLASSES:
//     Screen     the grid alone: bytes in, cells out. No process.
//     Terminal   a Screen an APPLICATION RUNS IN, on a pseudo-terminal.
//
// WHAT PYTHON RAISES is returned: a constructor ('create') gives null and
// 'last_error' says why ('LibraryMissing'); a method refused returns -1 or 0
// and the object's 'error' holds 'kind' (Python's exception name --
// 'IndexError', 'KeyError', 'TimeoutError', 'RuntimeError') and 'message'.
//
// CALLBACKS ARE OBJECTS: 'on_event' takes an EventCallback, 'on_change' a
// ChangeCallback -- derive and override; Python's lambdas.
// _____________________________________________________________________________
package hwut_vterm;

    import hwut_pytext::*;

    typedef string string_list_t[$];

    localparam string LIBRARY_VARIABLE = "HWUT_LIBVTERM";
    //  THE ATTRIBUTES A CELL IS ASKED FOR, in Python's order, each with the
    //  SGR code that sets it.
    localparam string ATTRIBUTE_NAME[7] = '{"bold", "italic", "underline", "blink", "reverse", "conceal", "strike"};
    localparam string ATTRIBUTE_SGR[7]  = '{"1", "3", "4", "5", "7", "8", "9"};

    import "DPI-C" function string  hwut_sv_vterm_detection_text();
    import "DPI-C" function void    hwut_sv_vterm_reset_library();
    import "DPI-C" function int     hwut_sv_vterm_setenv(string name, string value);
    import "DPI-C" function string  hwut_sv_vterm_install_hint();
    import "DPI-C" function string  hwut_sv_vterm_error(chandle screen, output string kind);
    import "DPI-C" function chandle hwut_sv_vterm_screen_new(int row_n, int column_n);
    import "DPI-C" function void    hwut_sv_vterm_screen_free(chandle screen);
    import "DPI-C" function int     hwut_sv_vterm_screen_feed(chandle screen, string data);
    import "DPI-C" function void    hwut_sv_vterm_cursor(chandle screen, output int row, output int column);
    import "DPI-C" function int     hwut_sv_vterm_cell(chandle screen, int row, int column, output string text,
                                                       output int width, output int attribute,
                                                       output int foreground, output int background);
    import "DPI-C" function string  hwut_sv_vterm_line(chandle screen, int row);
    import "DPI-C" function chandle hwut_sv_vterm_terminal_new(int row_n, int column_n, real settle_s, int id);
    import "DPI-C" function chandle hwut_sv_vterm_terminal_screen(chandle terminal);
    import "DPI-C" context function void hwut_sv_vterm_terminal_free(chandle terminal);
    import "DPI-C" function void    hwut_sv_vterm_region(chandle terminal, string name, int row, int row_n,
                                                         int column, int column_n);
    import "DPI-C" function string  hwut_sv_vterm_region_text(chandle terminal, string name, output int line_n);
    import "DPI-C" context function int hwut_sv_vterm_report(chandle terminal);
    import "DPI-C" context function int hwut_sv_vterm_terminal_feed(chandle terminal, string data);
    import "DPI-C" function string  hwut_sv_vterm_answer(chandle terminal);
    import "DPI-C" context function int hwut_sv_vterm_send(chandle terminal, string text, real react_s);
    import "DPI-C" context function int hwut_sv_vterm_press(chandle terminal, string key, string modifier,
                                                             real react_s);
    import "DPI-C" function void    hwut_sv_vterm_argv_clear();
    import "DPI-C" function void    hwut_sv_vterm_argv_add(string word);
    import "DPI-C" context function int hwut_sv_vterm_run(chandle terminal, string cwd, real start_s);
    import "DPI-C" context function int hwut_sv_vterm_pump(chandle terminal, real first_s);
    import "DPI-C" context function int hwut_sv_vterm_expect(chandle terminal, string text, real timeout_s,
                                                              output int row, output int column);
    import "DPI-C" context function int hwut_sv_vterm_wait(chandle terminal, real timeout_s, output int status);

    class Error;
        string kind;                // Python's exception name; '' no error
        string message;

        function new(string kind = "", string message = "");
            // RETURN: the error 'kind': 'message'.
            this.kind    = kind;
            this.message = message;
        endfunction

        function string to_string();
            // RETURN: 'kind: message'.
            return {kind, ": ", message};
        endfunction
    endclass

    Error last_error = new();       // the last constructor's

    function automatic Error error_of(chandle screen);
        // RETURN: the last error of 'screen' (a screen's handle), or of the
        //         last constructor where null.
        string kind;
        string message = hwut_sv_vterm_error(screen, kind);
        Error  error   = new(kind, message);
        return error;
    endfunction

    function automatic string detection_text();
        // RETURN: 'libvterm found: <name>' where the library loads; the text
        //         of 'LibraryMissing' -- what is wrong, how to install it --
        //         else.
        return hwut_sv_vterm_detection_text();
    endfunction

    function automatic void reset_library();
        // RETURN: nothing; the next screen loads the library anew, under the
        //         name HWUT_LIBVTERM gives then -- Python's '_library = None'.
        hwut_sv_vterm_reset_library();
    endfunction

    function automatic bit set_environment(string name, string value);
        // RETURN: 1, the process's environment holds 'name' = 'value' --
        //         Python's 'os.environ[name] = value'; 0, it could not.
        return hwut_sv_vterm_setenv(name, value) == 0;
    endfunction

    function automatic string install_hint();
        // RETURN: how to install the library -- the lines 'LibraryMissing'
        //         ends with.
        return hwut_sv_vterm_install_hint();
    endfunction

    function automatic string_list_t split_lines(string text, int line_n);
        // RETURN: the 'line_n' lines 'text' holds, '\n' between each two.
        string_list_t result = {};
        string        line   = "";
        if (line_n <= 0) return result;
        for (int i = 0; i < text.len(); i++) begin
            if (text[i] == "\n") begin result.push_back(line); line = ""; end
            else line = {line, string'(text[i])};
        end
        result.push_back(line);
        return result;
    endfunction

    class Cell;
        // ONE CELL OF THE SCREEN, as plain values. 'text' is what stands in
        // it -- '' for a cell nothing was written to, and for the right half
        // of a wide character. A colour is (red, green, blue), its '_f' 0
        // where the cell wears the terminal's default (Python's None).
        string text;
        int    width = 1;
        bit    bold_f, italic_f, underline_f, blink_f, reverse_f, conceal_f, strike_f;
        bit    foreground_f;
        int    foreground[3];
        bit    background_f;
        int    background[3];

        function bit attribute_f(int i);
            // RETURN: 1 where the attribute ATTRIBUTE_NAME[i] is set; 0 else.
            case (i)
                0: return bold_f;
                1: return italic_f;
                2: return underline_f;
                3: return blink_f;
                4: return reverse_f;
                5: return conceal_f;
                default: return strike_f;
            endcase
        endfunction

        function string attribute_text();
            // RETURN: the attributes that are set, by name, in one fixed
            //         order, blank-separated -- 'bold reverse'; '' where none.
            string said[$] = {};
            for (int i = 0; i < 7; i++) if (attribute_f(i)) said.push_back(ATTRIBUTE_NAME[i]);
            return join_text(said, " ");
        endfunction

        function string foreground_repr();
            // RETURN: the foreground as Python prints it: '(r, g, b)' or 'None'.
            if (!foreground_f) return "None";
            return $sformatf("(%0d, %0d, %0d)", foreground[0], foreground[1], foreground[2]);
        endfunction

        function string background_repr();
            // RETURN: the background as Python prints it: '(r, g, b)' or 'None'.
            if (!background_f) return "None";
            return $sformatf("(%0d, %0d, %0d)", background[0], background[1], background[2]);
        endfunction
    endclass

    class Event;
        // ONE THING THE TERMINAL DID (the RAW layer): 'kind' is 'damage'
        // (rows 'row'..'row_end', columns 'column'..'column_end', ends
        // excluded), 'cursor' ('row', 'column'; 'value' 1 where visible),
        // 'property' ('name' is now 'value'; 'value_f' 0 where it is a text)
        // or 'bell'.
        string kind;
        int    row, column, row_end, column_end;
        string name;
        bit    value_f;
        int    value;
        string text;

        function string to_string();
            // RETURN: the event on one line, as a test prints it.
            return text;
        endfunction
    endclass

    virtual class EventCallback;
        pure virtual function void on_event(Event event_);
        // RETURN: nothing; 'event_' was handled.
    endclass

    virtual class ChangeCallback;
        pure virtual function void on_change(string name, string line_list[$]);
        // RETURN: nothing; the change of region 'name', now 'line_list',
        //         was handled.
    endclass

    class Screen;
        int     row_n;
        int     column_n;
        chandle screen;             // VtermScreen*
        Error   error;              // the last method's

        function new(int row_n, int column_n);
            // RETURN: a screen not yet bound to the library; use 'create'.
            this.row_n    = row_n;
            this.column_n = column_n;
            error         = new();
        endfunction

        static function Screen create(int row_n = 24, int column_n = 80);
            // RETURN: a blank screen of 'row_n' rows and 'column_n' columns;
            //         null where the library is missing -- 'last_error' is
            //         'LibraryMissing', its text says how to install it.
            Screen self = new(row_n, column_n);
            self.screen = hwut_sv_vterm_screen_new(row_n, column_n);
            if (self.screen == null) begin
                last_error = error_of(null);
                return null;
            end
            return self;
        endfunction

        virtual function void close();
            // RETURN: nothing; the library's screen is gone ('with' left).
            if (screen != null) hwut_sv_vterm_screen_free(screen);
            screen = null;
        endfunction

        virtual function int feed(string data);
            // RETURN: the number of bytes of 'data' the screen took -- a str
            //         is its UTF-8 bytes.
            return hwut_sv_vterm_screen_feed(screen, data);
        endfunction

        function void cursor(output int row, output int column);
            // RETURN: nothing; ('row', 'column') is where the cursor stands,
            //         counted from 0.
            hwut_sv_vterm_cursor(screen, row, column);
        endfunction

        function string cursor_repr();
            // RETURN: the cursor as Python prints the tuple: '(row, column)'.
            int row, column;
            cursor(row, column);
            return $sformatf("(%0d, %0d)", row, column);
        endfunction

        function Cell cell_(int row, int column);
            // RETURN: what stands at ('row', 'column') -- Python's 'cell', a keyword here; null where the place
            //         is not on the screen -- 'error' is 'IndexError'.
            Cell result = new();
            int  attribute, foreground, background;
            if (hwut_sv_vterm_cell(screen, row, column, result.text, result.width, attribute, foreground,
                                   background) != 0) begin
                error = error_of(screen);
                return null;
            end
            {result.strike_f, result.conceal_f, result.reverse_f, result.blink_f, result.underline_f,
             result.italic_f, result.bold_f} = attribute[6:0];
            result.foreground_f = foreground >= 0;
            result.background_f = background >= 0;
            for (int i = 0; i < 3; i++) begin
                result.foreground[i] = result.foreground_f ? (foreground >> (16 - 8 * i)) & 'hFF : 0;
                result.background[i] = result.background_f ? (background >> (16 - 8 * i)) & 'hFF : 0;
            end
            return result;
        endfunction

        function string line(int row);
            // RETURN: the text of row 'row', trailing blanks removed.
            return hwut_sv_vterm_line(screen, row);
        endfunction

        function string_list_t line_list();
            // RETURN: every row's text, top to bottom.
            string_list_t result = {};
            for (int row = 0; row < row_n; row++) result.push_back(line(row));
            return result;
        endfunction
    endclass

    typedef class Terminal;

    class Registry;
        // The terminals by number: the C core names its terminal by it when
        // it reports.
        static Terminal terminal_db[int];
        static int      next_id = 1;
    endclass

    class Terminal extends Screen;
        chandle        terminal;    // VtermTerminal*
        int            id;
        real           settle_s;
        EventCallback  event_callback_list[$];
        ChangeCallback change_callback_list[$];

        function new(int row_n, int column_n, real settle_s);
            // RETURN: a terminal not yet bound to the library; use 'create'.
            super.new(row_n, column_n);
            this.settle_s = settle_s;
            id = Registry::next_id;
            Registry::next_id += 1;
        endfunction

        static function Terminal create(int row_n = 24, int column_n = 80, real settle_s = 0.1);
            // RETURN: a blank terminal, nothing running in it; null where the
            //         library is missing ('last_error'). 'settle_s' is how
            //         long the application must write nothing before its
            //         screen is taken as drawn.
            Terminal self = new(row_n, column_n, settle_s);
            self.terminal = hwut_sv_vterm_terminal_new(row_n, column_n, settle_s, self.id);
            if (self.terminal == null) begin
                last_error = error_of(null);
                return null;
            end
            self.screen = hwut_sv_vterm_terminal_screen(self.terminal);
            Registry::terminal_db[self.id] = self;
            return self;
        endfunction

        virtual function void close();
            // RETURN: nothing; the application is ended where it runs, the
            //         terminal gone.
            if (terminal != null) hwut_sv_vterm_terminal_free(terminal);
            Registry::terminal_db.delete(id);
            terminal = null;
            screen   = null;
        endfunction

        function bit refused(int result);
            // RETURN: 1 where the C call 'result' was refused (< 0), 'error'
            //         its kind and text; 0 else.
            if (result >= 0) return 0;
            error = error_of(screen);
            return 1;
        endfunction

        function void on_event(EventCallback callback);
            // RETURN: nothing; 'callback' is told every event from now on.
            event_callback_list.push_back(callback);
        endfunction

        function void on_change(ChangeCallback callback);
            // RETURN: nothing; 'callback' is told every region changed.
            change_callback_list.push_back(callback);
        endfunction

        function void region(string name, int row, int row_n = 1, int column = 0, int column_n = -1);
            // RETURN: nothing; the rectangle 'name' is observed from now on:
            //         'row_n' rows from 'row' (negative: from the bottom, -1
            //         the last), 'column_n' columns from 'column' -- to the
            //         right edge where negative (Python's None).
            hwut_sv_vterm_region(terminal, name, row, row_n, column, column_n);
        endfunction

        function bit region_text(string name, output string_list_t line_list);
            // RETURN: 1, 'line_list' holds the lines of the region 'name' now;
            //         0, no region has that name -- 'error' is 'KeyError'.
            int    n;
            string text = hwut_sv_vterm_region_text(terminal, name, n);
            line_list = split_lines(text, n);
            if (n >= 0) return 1;
            error = error_of(screen);
            return 0;
        endfunction

        function int report();
            // RETURN: the number of regions whose text differs from what was
            //         last told -- each told to every ChangeCallback.
            return hwut_sv_vterm_report(terminal);
        endfunction

        virtual function int feed(string data);
            // RETURN: the number of bytes of 'data' the terminal took, as if
            //         an application had written them; its events told.
            return hwut_sv_vterm_terminal_feed(terminal, data);
        endfunction

        function string answer();
            // RETURN: the bytes the terminal answered and nobody took yet --
            //         now taken.
            return hwut_sv_vterm_answer(terminal);
        endfunction

        function bit send(string text, real react_s = 1.0);
            // RETURN: 1, the application still runs after 'text' (UTF-8) was
            //         typed, character by character, and the screen read until
            //         quiet; 0, it does not.
            return hwut_sv_vterm_send(terminal, text, react_s) == 1;
        endfunction

        function int press(string key, string modifier = "", real react_s = 1.0);
            // RETURN: 1, the application still runs after 'key' ('enter',
            //         'up', 'f5', ... or one character) was pressed with the
            //         modifiers 'modifier' ('shift', 'alt', 'ctrl',
            //         blank-separated); 0, it does not; -1, a name is unknown
            //         -- 'error' is 'KeyError'.
            int result = hwut_sv_vterm_press(terminal, key, modifier, react_s);
            void'(refused(result));
            return result;
        endfunction

        function int run(string argv[$], string cwd = "", real start_s = 10.0);
            // RETURN: 1, the application 'argv' still runs once its first
            //         screen stands; 0, it does not; -1, one was already run
            //         here ('RuntimeError'). Its three streams are this
            //         terminal, it is the controlling one, TERM is
            //         'xterm-256color', LINES and COLUMNS are taken out of its
            //         environment.
            int result;
            hwut_sv_vterm_argv_clear();
            foreach (argv[i]) hwut_sv_vterm_argv_add(argv[i]);
            result = hwut_sv_vterm_run(terminal, cwd, start_s);
            hwut_sv_vterm_argv_clear();
            void'(refused(result));
            return result;
        endfunction

        function bit pump(real first_s = 1.0);
            // RETURN: 1, the application still runs; 0, it does not -- read up
            //         to 'first_s' for it to write at all, then until it wrote
            //         nothing for 'settle_s'; the changed regions reported.
            return hwut_sv_vterm_pump(terminal, first_s) == 1;
        endfunction

        function bit expect_(string text, output int row, output int column, input real timeout_s = 10.0);
            // RETURN: 1, 'text' stands on the screen at ('row', 'column');
            //         0, it did not appear within 'timeout_s' -- 'error' is
            //         'TimeoutError', carrying the screen. ('expect' is a
            //         keyword.)
            return !refused(hwut_sv_vterm_expect(terminal, text, timeout_s, row, column));
        endfunction

        function int wait_(output int status, input real timeout_s = 10.0);
            // RETURN: 1, 'status' is the application's exit status (negative:
            //         the signal that ended it); 0, no application was run;
            //         -1, it still ran after 'timeout_s' and was killed --
            //         'error' is 'TimeoutError'. ('wait' is a keyword.)
            int result = hwut_sv_vterm_wait(terminal, timeout_s, status);
            void'(refused(result));
            return result;
        endfunction
    endclass

    export "DPI-C" function hwut_sv_vterm_event;
    function automatic void hwut_sv_vterm_event(int id, string text, string kind, int row, int column,
                                                int row_end, int column_end, string name, int value_f,
                                                int value);
        // RETURN: nothing; the event the C terminal 'id' reported went to
        //         every EventCallback of its SystemVerilog terminal.
        Event    event_ = new();
        Terminal t;
        if (!Registry::terminal_db.exists(id)) return;
        t = Registry::terminal_db[id];
        event_.text       = text;
        event_.kind       = kind;
        event_.row        = row;
        event_.column     = column;
        event_.row_end    = row_end;
        event_.column_end = column_end;
        event_.name       = name;
        event_.value_f    = value_f != 0;
        event_.value      = value;
        foreach (t.event_callback_list[i]) t.event_callback_list[i].on_event(event_);
    endfunction

    export "DPI-C" function hwut_sv_vterm_change;
    function automatic void hwut_sv_vterm_change(int id, string name, string joined, int line_n);
        // RETURN: nothing; the region 'name' the C terminal 'id' reported
        //         changed went to every ChangeCallback of its SystemVerilog
        //         terminal, with its lines.
        string_list_t line_list = split_lines(joined, line_n);
        Terminal      t;
        if (!Registry::terminal_db.exists(id)) return;
        t = Registry::terminal_db[id];
        foreach (t.change_callback_list[i]) t.change_callback_list[i].on_change(name, line_list);
    endfunction

endpackage
