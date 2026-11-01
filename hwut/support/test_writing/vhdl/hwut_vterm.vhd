-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
--          'python/hwut_vterm.py' (README-hwut_vterm.txt): a THIN FACE over
--          the C module '../c/hwut_vterm.c' by VHPIDIRECT, which loads
--          libvterm at run time ('dlopen'; HWUT_LIBVTERM names the file) and
--          runs an application on a pseudo-terminal.
--
--     variable s : Screen;                        -- 'with Screen(24, 80) as s:' --
--                                                 'open' is a reserved word
--     if not s.create(24, 80) then print("NOT PROBED: " & s.error_message); end if;
--     s.feed(ESC & "[1mbold" & ESC & "[0m plain");
--     s.line(0)                                   -- 'bold plain'
--     cell := s.cell(0, 0);  cell.bold            -- true
--     s.close;
--
-- TWO CLASSES:
--     Screen     (package hwut_vterm) the grid alone: bytes in, cells out.
--     Terminal   (generic package hwut_vterm_terminal) a screen an
--                APPLICATION RUNS IN, on a pseudo-terminal. Python's
--                'on_event(f)' and 'on_change(f)' are the package's GENERIC
--                SUBPROGRAMS -- VHDL hands no function at run time:
--
--     procedure said(name : string; lines : str_list) is ... end procedure;
--     package watched is new work.hwut_vterm_terminal
--         generic map (on_event => no_event, on_change => said);
--     variable t : watched.Terminal;
--     t.create(10, 44, 0.1);  t.region("read", 8, 1);
--     t.run("python3" & NUL & "-c" & NUL & app & NUL);   -- argv: words ended by NUL
--     t.send("q");  status := t.wait_exit;
--
-- WHEN A CALLBACK IS CALLED: C cannot call into VHDL, so the C module's
-- callbacks are queued, and every Terminal method that may have told
-- something delivers them, in the order told, before it returns.
--
-- WHERE PYTHON RAISES, a method returns false (a text: "") and 'error_kind'
-- is the exception's name -- 'LibraryMissing', 'IndexError', 'KeyError',
-- 'TimeoutError', 'RuntimeError' -- 'error_message' its text. Reserved words of
-- VHDL rename two methods: 'wait' is 'wait_exit', 'report' is 'report_changes'.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;

package hwut_vterm is
    constant VTERM_LIBRARY_VARIABLE : string   := "HWUT_LIBVTERM";
    --  the attributes, in the order of the C module's names and codes
    constant VTERM_ATTRIBUTE_NAME : str_list := "bold" & LF & "italic" & LF & "underline" & LF & "blink" & LF
                                                & "reverse" & LF & "conceal" & LF & "strike" & LF;
    constant VTERM_ATTRIBUTE_SGR  : str_list := "1" & LF & "3" & LF & "4" & LF & "5" & LF & "7" & LF & "8" & LF
                                                & "9" & LF;

    type VtermCell is record
        text_n         : natural;                -- 'text(1 to text_n)': UTF-8; '' for an unwritten cell
        text           : string(1 to 32);        --   and for the right half of a wide one
        width          : natural;
        bold, italic, underline, blink, reverse, conceal, strike : boolean;
        foreground_f   : boolean;                -- false: the default colour
        foreground     : integer_vector(0 to 2); -- r, g, b
        background_f   : boolean;
        background     : integer_vector(0 to 2);
        attribute_n    : natural;
        attribute_text : string(1 to 128);       -- 'bold, underline', as Python's 'attribute_text()'
    end record;
    function cell_text(cell : VtermCell) return string;
    function attribute_text(cell : VtermCell) return string;

    --  ONE THING THE TERMINAL DID (the RAW layer): 'kind' "damage",
    --  "cursor", "property" or "bell".
    type VtermEvent is record
        kind_n      : natural;
        kind        : string(1 to 16);
        row, column, row_end, column_end : integer;
        name_n      : natural;
        name        : string(1 to 64);
        value_f     : boolean;                   -- false: a property's value is a text
        value       : integer;
        text_n      : natural;
        text        : string(1 to 512);          -- Python's str(event)
    end record;
    function to_string(event : VtermEvent) return string;
    function kind_of(event : VtermEvent) return string;

    impure function detection_text return string;
    procedure reset_library;

    --  the callbacks of a Terminal that is told nothing
    procedure no_event(event : VtermEvent);
    procedure no_change(name : string; lines : str_list);

    type Screen is protected
        impure function create(row_count : positive := 24; column_count : positive := 80) return boolean;
        procedure close;
        impure function feed(data : string) return natural;
        procedure feed(data : string);
        impure function cursor return integer_vector;
        impure function cell(row : integer; column : integer) return VtermCell;
        impure function line(row : integer) return string;
        impure function line_list return str_list;
        impure function row_n return natural;
        impure function failed return boolean;
        impure function error_kind return string;
        impure function error_message return string;
    end protected;

    -- ------------------------------------------- for the faces of this file
    impure function hwut_vhpi_vterm_screen_new(row_n : integer; column_n : integer) return integer;
    attribute foreign of hwut_vhpi_vterm_screen_new : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_screen_new";
    impure function hwut_vhpi_vterm_terminal_new(row_n : integer; column_n : integer; settle_s : real) return integer;
    attribute foreign of hwut_vhpi_vterm_terminal_new : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_terminal_new";
    procedure hwut_vhpi_vterm_free(h : integer);
    attribute foreign of hwut_vhpi_vterm_free : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_free";
    impure function hwut_vhpi_vterm_feed(h : integer; data : string) return integer;
    attribute foreign of hwut_vhpi_vterm_feed : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_feed";
    impure function hwut_vhpi_vterm_cursor(h : integer) return integer;
    attribute foreign of hwut_vhpi_vterm_cursor : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_cursor";
    procedure hwut_vhpi_vterm_line(h : integer; row : integer);
    attribute foreign of hwut_vhpi_vterm_line : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_line";
    impure function hwut_vhpi_vterm_cell(h : integer; row : integer; column : integer) return integer;
    attribute foreign of hwut_vhpi_vterm_cell : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_cell";
    procedure hwut_vhpi_vterm_cell_text;
    attribute foreign of hwut_vhpi_vterm_cell_text : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_cell_text";
    procedure hwut_vhpi_vterm_cell_attribute_text;
    attribute foreign of hwut_vhpi_vterm_cell_attribute_text : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_cell_attribute_text";
    impure function hwut_vhpi_vterm_cell_field(i : integer) return integer;
    attribute foreign of hwut_vhpi_vterm_cell_field : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_cell_field";
    procedure hwut_vhpi_vterm_error;
    attribute foreign of hwut_vhpi_vterm_error : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_error";
    procedure hwut_vhpi_vterm_region(h : integer; name : string; row : integer; row_n : integer; column : integer; column_n : integer);
    attribute foreign of hwut_vhpi_vterm_region : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_region";
    impure function hwut_vhpi_vterm_region_text(h : integer; name : string) return integer;
    attribute foreign of hwut_vhpi_vterm_region_text : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_region_text";
    impure function hwut_vhpi_vterm_report(h : integer) return integer;
    attribute foreign of hwut_vhpi_vterm_report : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_report";
    procedure hwut_vhpi_vterm_answer(h : integer);
    attribute foreign of hwut_vhpi_vterm_answer : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_answer";
    impure function hwut_vhpi_vterm_send(h : integer; text : string; react_s : real) return integer;
    attribute foreign of hwut_vhpi_vterm_send : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_send";
    impure function hwut_vhpi_vterm_press(h : integer; key : string; modifier : string; react_s : real) return integer;
    attribute foreign of hwut_vhpi_vterm_press : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_press";
    impure function hwut_vhpi_vterm_run(h : integer; argv : string; cwd : string; start_s : real) return integer;
    attribute foreign of hwut_vhpi_vterm_run : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_run";
    impure function hwut_vhpi_vterm_pump(h : integer; first_s : real) return integer;
    attribute foreign of hwut_vhpi_vterm_pump : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_pump";
    impure function hwut_vhpi_vterm_expect(h : integer; text : string; timeout_s : real) return integer;
    attribute foreign of hwut_vhpi_vterm_expect : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_expect";
    impure function hwut_vhpi_vterm_wait(h : integer; timeout_s : real) return integer;
    attribute foreign of hwut_vhpi_vterm_wait : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_wait";
    impure function hwut_vhpi_vterm_status return integer;
    attribute foreign of hwut_vhpi_vterm_status : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_status";
    procedure hwut_vhpi_vterm_close(h : integer);
    attribute foreign of hwut_vhpi_vterm_close : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_close";
    impure function hwut_vhpi_vterm_told return integer;
    attribute foreign of hwut_vhpi_vterm_told : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_told";

    impure function cell_of(h : integer; row : integer; column : integer) return VtermCell;
    impure function event_of(text : string) return VtermEvent;
    function after_line(text : string) return string;
end package;

package body hwut_vterm is
    procedure hwut_vhpi_vterm_detection_text;
    attribute foreign of hwut_vhpi_vterm_detection_text : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_detection_text";
    procedure hwut_vhpi_vterm_detection_text is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_vterm_reset_library;
    attribute foreign of hwut_vhpi_vterm_reset_library : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_vterm_reset_library";
    procedure hwut_vhpi_vterm_reset_library is begin assert false severity failure; end procedure;

    --  THE FOREIGN BODIES -- never run: GHDL calls the C function.
    impure function hwut_vhpi_vterm_screen_new(row_n : integer; column_n : integer) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_terminal_new(row_n : integer; column_n : integer; settle_s : real) return integer is
    begin assert false severity failure; return 0; end function;
    procedure hwut_vhpi_vterm_free(h : integer) is begin assert false severity failure; end procedure;
    impure function hwut_vhpi_vterm_feed(h : integer; data : string) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_cursor(h : integer) return integer is
    begin assert false severity failure; return 0; end function;
    procedure hwut_vhpi_vterm_line(h : integer; row : integer) is begin assert false severity failure; end procedure;
    impure function hwut_vhpi_vterm_cell(h : integer; row : integer; column : integer) return integer is
    begin assert false severity failure; return 0; end function;
    procedure hwut_vhpi_vterm_cell_text is begin assert false severity failure; end procedure;
    procedure hwut_vhpi_vterm_cell_attribute_text is begin assert false severity failure; end procedure;
    impure function hwut_vhpi_vterm_cell_field(i : integer) return integer is
    begin assert false severity failure; return 0; end function;
    procedure hwut_vhpi_vterm_error is begin assert false severity failure; end procedure;
    procedure hwut_vhpi_vterm_region(h : integer; name : string; row : integer; row_n : integer; column : integer; column_n : integer) is
    begin assert false severity failure; end procedure;
    impure function hwut_vhpi_vterm_region_text(h : integer; name : string) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_report(h : integer) return integer is
    begin assert false severity failure; return 0; end function;
    procedure hwut_vhpi_vterm_answer(h : integer) is begin assert false severity failure; end procedure;
    impure function hwut_vhpi_vterm_send(h : integer; text : string; react_s : real) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_press(h : integer; key : string; modifier : string; react_s : real) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_run(h : integer; argv : string; cwd : string; start_s : real) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_pump(h : integer; first_s : real) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_expect(h : integer; text : string; timeout_s : real) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_wait(h : integer; timeout_s : real) return integer is
    begin assert false severity failure; return 0; end function;
    impure function hwut_vhpi_vterm_status return integer is
    begin assert false severity failure; return 0; end function;
    procedure hwut_vhpi_vterm_close(h : integer) is begin assert false severity failure; end procedure;
    impure function hwut_vhpi_vterm_told return integer is
    begin assert false severity failure; return 0; end function;

    function cell_text(cell : VtermCell) return string is
        -- RETURN: string, the cell's text (UTF-8) -- '' for an unwritten cell.
    begin return cell.text(1 to cell.text_n); end function;

    function attribute_text(cell : VtermCell) return string is
        -- RETURN: string, the cell's attributes by name, ', '-joined -- ''
        --         for none.
    begin return cell.attribute_text(1 to cell.attribute_n); end function;

    function to_string(event : VtermEvent) return string is
        -- RETURN: string, the event as Python's str(event) writes it.
    begin return event.text(1 to event.text_n); end function;

    function kind_of(event : VtermEvent) return string is
        -- RETURN: string, the event's kind: "damage", "cursor", "property", "bell".
    begin return event.kind(1 to event.kind_n); end function;

    function after_line(text : string) return string is
        -- RETURN: string, what follows the first LF of 'text'; "" for none.
    begin
        for i in text'range loop
            if text(i) = LF then return text(i + 1 to text'right); end if;
        end loop;
        return "";
    end function;

    impure function cell_of(h : integer; row : integer; column : integer) return VtermCell is
        -- RETURN: VtermCell, what stands at ('row', 'column') of the screen
        --         'h', if success; a cell of no text, width 0, else -- the
        --         place is off the screen (IndexError: see the C error).
        variable cell : VtermCell;
        variable text : std.textio.line;
    begin
        cell.text_n := 0; cell.attribute_n := 0; cell.width := 0;
        if hwut_vhpi_vterm_cell(h, row, column) /= 0 then return cell; end if;
        hwut_vhpi_vterm_cell_text;
        text := new string'(result);
        cell.text_n := minimum(text'length, cell.text'length);
        cell.text(1 to cell.text_n) := text(1 to cell.text_n);
        hwut_vhpi_vterm_cell_attribute_text;
        text := new string'(result);
        cell.attribute_n := minimum(text'length, cell.attribute_text'length);
        cell.attribute_text(1 to cell.attribute_n) := text(1 to cell.attribute_n);
        deallocate(text);
        cell.width        := hwut_vhpi_vterm_cell_field(0);
        cell.bold         := hwut_vhpi_vterm_cell_field(1) /= 0;
        cell.italic       := hwut_vhpi_vterm_cell_field(2) /= 0;
        cell.underline    := hwut_vhpi_vterm_cell_field(3) /= 0;
        cell.blink        := hwut_vhpi_vterm_cell_field(4) /= 0;
        cell.reverse      := hwut_vhpi_vterm_cell_field(5) /= 0;
        cell.conceal      := hwut_vhpi_vterm_cell_field(6) /= 0;
        cell.strike       := hwut_vhpi_vterm_cell_field(7) /= 0;
        cell.foreground_f := hwut_vhpi_vterm_cell_field(8) /= 0;
        cell.background_f := hwut_vhpi_vterm_cell_field(12) /= 0;
        for i in 0 to 2 loop
            cell.foreground(i) := hwut_vhpi_vterm_cell_field(9 + i);
            cell.background(i) := hwut_vhpi_vterm_cell_field(13 + i);
        end loop;
        return cell;
    end function;

    impure function event_of(text : string) return VtermEvent is
        -- RETURN: VtermEvent, the event the C module queued as 'text' --
        --         its text, kind, row, column, row_end, column_end, name,
        --         value_f, value, each ended by LF but the last.
        constant list  : string := text & LF;
        variable event : VtermEvent;
        procedure put(variable target : out string; variable n : out natural; value : string) is
        begin
            n := minimum(value'length, target'length);
            target(1 to n) := value(value'left to value'left + n - 1);
        end procedure;
    begin
        put(event.text, event.text_n, item(list, 0));
        put(event.kind, event.kind_n, item(list, 1));
        event.row        := integer'value(item(list, 2));
        event.column     := integer'value(item(list, 3));
        event.row_end    := integer'value(item(list, 4));
        event.column_end := integer'value(item(list, 5));
        put(event.name, event.name_n, item(list, 6));
        event.value_f    := item(list, 7) /= "0";
        event.value      := integer'value(item(list, 8));
        return event;
    end function;

    impure function detection_text return string is
        -- RETURN: string, whether libvterm loads here, and which file.
    begin hwut_vhpi_vterm_detection_text; return result; end function;

    procedure reset_library is
        -- RETURN: nothing; the next Screen loads the library anew -- under
        --         the name HWUT_LIBVTERM gives now.
    begin hwut_vhpi_vterm_reset_library; end procedure;

    procedure no_event(event : VtermEvent) is
        -- RETURN: nothing; the event is not looked at.
    begin end procedure;

    procedure no_change(name : string; lines : str_list) is
        -- RETURN: nothing; the change is not looked at.
    begin end procedure;

    type Screen is protected body
        variable handle   : integer := 0;
        variable rows     : natural := 0;
        variable kind_text, message_text : std.textio.line := new string'("");

        procedure fail is
            -- RETURN: nothing; the C module's last error is this screen's.
        begin
            hwut_vhpi_vterm_error;
            kind_text    := new string'(item(result & LF, 0));
            message_text := new string'(after_line(result));
        end procedure;

        procedure clear is
        begin kind_text := new string'(""); message_text := new string'(""); end procedure;

        impure function create(row_count : positive := 24; column_count : positive := 80) return boolean is
            -- RETURN: true, the screen stands, 'row_count' rows of 'column_count'
            --         columns, blank; false, else -- libvterm was not found:
            --         'error_kind' is 'LibraryMissing', 'error_message' says
            --         how to install it.
        begin
            clear;
            if handle /= 0 then hwut_vhpi_vterm_free(handle); end if;
            handle := hwut_vhpi_vterm_screen_new(row_count, column_count);
            if handle = 0 then fail; return false; end if;
            rows := row_count;
            return true;
        end function;

        procedure close is
            -- RETURN: nothing; the screen is given back.
        begin
            if handle /= 0 then hwut_vhpi_vterm_free(handle); end if;
            handle := 0;
        end procedure;

        impure function feed(data : string) return natural is
            -- RETURN: natural, the bytes of 'data' the screen took -- 'data'
            --         is bytes; a str is its UTF-8.
        begin return hwut_vhpi_vterm_feed(handle, data); end function;

        procedure feed(data : string) is
            -- RETURN: nothing; as the function 'feed', its count dropped.
            variable n : natural;
        begin n := feed(data); end procedure;

        impure function cursor return integer_vector is
            -- RETURN: integer_vector, (row, column) of the cursor, from 0.
            constant place : integer := hwut_vhpi_vterm_cursor(handle);
        begin return (place / 65536, place mod 65536); end function;

        impure function cell(row : integer; column : integer) return VtermCell is
            -- RETURN: VtermCell, what stands at ('row', 'column'), if success;
            --         a cell of no text, else -- the place is off the screen:
            --         'failed', 'error_kind' 'IndexError'.
        begin
            clear;
            if hwut_vhpi_vterm_cell(handle, row, column) /= 0 then fail; end if;
            return cell_of(handle, row, column);
        end function;

        impure function line(row : integer) return string is
            -- RETURN: string, the text of row 'row', the blanks at its end
            --         removed.
        begin hwut_vhpi_vterm_line(handle, row); return result; end function;

        impure function line_list return str_list is
            -- RETURN: str_list, every row's text, as 'line' gives it.
            variable text : std.textio.line := new string'("");
        begin
            for row in 0 to rows - 1 loop
                hwut_vhpi_vterm_line(handle, row);
                std.textio.write(text, result & LF);
            end loop;
            return text.all;
        end function;

        impure function row_n return natural is
            -- RETURN: natural, the number of rows.
        begin return rows; end function;

        impure function failed return boolean is
            -- RETURN: true, the last method refused -- see 'error_kind'.
        begin return kind_text'length > 0; end function;

        impure function error_kind return string is
            -- RETURN: string, Python's name of the last refusal's exception.
        begin return kind_text.all; end function;

        impure function error_message return string is
            -- RETURN: string, the last refusal's text.
        begin return message_text.all; end function;
    end protected body;
end package body;

-- _____________________________________________________________________________
--
-- THE TERMINAL, its callbacks the generics.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.hwut_vterm.all;

package hwut_vterm_terminal is
    generic (
        procedure on_event(event : VtermEvent);
        procedure on_change(name : string; lines : str_list)
    );

    type Terminal is protected
        impure function create(row_count : positive := 24; column_count : positive := 80; settle_s : real := 0.1) return boolean;
        procedure close;
        procedure free;
        procedure region(name : string; row : integer; row_n : positive := 1; column : natural := 0;
                         column_n : integer := -1);
        impure function region_text(name : string) return str_list;
        impure function report_changes return natural;
        impure function feed(data : string) return natural;
        procedure feed(data : string);
        impure function answer return string;
        impure function send(text : string; react_s : real := 1.0) return boolean;
        procedure send(text : string; react_s : real := 1.0);
        impure function press(key : string; modifier : string := ""; react_s : real := 1.0) return boolean;
        procedure press(key : string; modifier : string := ""; react_s : real := 1.0);
        impure function run(argv : string; cwd : string := ""; start_s : real := 10.0) return boolean;
        procedure run(argv : string; cwd : string := ""; start_s : real := 10.0);
        impure function pump(first_s : real := 1.0) return boolean;
        impure function expect(text : string; timeout_s : real := 10.0) return integer_vector;
        impure function wait_exit(timeout_s : real := 10.0) return integer;
        impure function cursor return integer_vector;
        impure function cell(row : integer; column : integer) return VtermCell;
        impure function line(row : integer) return string;
        impure function failed return boolean;
        impure function error_kind return string;
        impure function error_message return string;
    end protected;
end package;

package body hwut_vterm_terminal is
    type Terminal is protected body
        variable handle : integer := 0;
        variable kind_text, message_text : std.textio.line := new string'("");

        procedure tell is
            -- RETURN: nothing; every event and change the C module queued
            --         was handed to 'on_event' and 'on_change', in order.
            variable kind  : integer;
            variable text  : std.textio.line;
        begin
            loop
                kind := hwut_vhpi_vterm_told;
                exit when kind = 0;
                text := new string'(result);
                if kind = 1 then
                    on_event(event_of(text.all));
                else
                    if item_n(text.all & LF) = 1 then on_change(item(text.all & LF, 0), "");
                    else                              on_change(item(text.all & LF, 0), after_line(text.all) & LF);
                    end if;
                end if;
                deallocate(text);
            end loop;
        end procedure;

        procedure fail is
            -- RETURN: nothing; the C module's last error is this terminal's.
        begin
            hwut_vhpi_vterm_error;
            kind_text    := new string'(item(result & LF, 0));
            message_text := new string'(after_line(result));
        end procedure;

        procedure clear is
        begin kind_text := new string'(""); message_text := new string'(""); end procedure;

        impure function said(r : integer) return boolean is
            -- RETURN: true, 'r' (C's) is 1; false, else -- where -1, the
            --         refusal is this terminal's error. What was told is told.
        begin
            if r < 0 then fail; end if;
            tell;
            return r = 1;
        end function;

        impure function create(row_count : positive := 24; column_count : positive := 80; settle_s : real := 0.1) return boolean is
            -- RETURN: true, the terminal stands, 'row_count' rows of 'column_count'
            --         columns; a read is over once the application wrote
            --         nothing for 'settle_s' seconds; false, else -- libvterm
            --         was not found ('LibraryMissing').
        begin
            clear;
            free;
            handle := hwut_vhpi_vterm_terminal_new(row_count, column_count, settle_s);
            if handle = 0 then fail; return false; end if;
            return true;
        end function;

        procedure close is
            -- RETURN: nothing; the application is ended, the terminal closed.
        begin
            if handle /= 0 then hwut_vhpi_vterm_close(handle); tell; end if;
        end procedure;

        procedure free is
            -- RETURN: nothing; the terminal is closed and given back.
        begin
            if handle /= 0 then hwut_vhpi_vterm_free(handle); tell; end if;
            handle := 0;
        end procedure;

        procedure region(name : string; row : integer; row_n : positive := 1; column : natural := 0;
                         column_n : integer := -1) is
            -- RETURN: nothing; the rows 'row' .. of the columns 'column' ..
            --         are watched as 'name' ('row' -1: the last row,
            --         'column_n' -1: to the right end): 'on_change' is told
            --         when their text changed.
        begin hwut_vhpi_vterm_region(handle, name, row, row_n, column, column_n); end procedure;

        impure function region_text(name : string) return str_list is
            -- RETURN: str_list, the region's rows as they stand now, if
            --         success; "", else -- no region is so named ('KeyError').
        begin
            clear;
            if hwut_vhpi_vterm_region_text(handle, name) < 0 then fail; return ""; end if;
            return result;
        end function;

        impure function report_changes return natural is
            -- RETURN: natural, the number of regions whose change was told
            --         now -- Python's 'report()'.
            constant n : natural := hwut_vhpi_vterm_report(handle);
        begin tell; return n; end function;

        impure function feed(data : string) return natural is
            -- RETURN: natural, the bytes of 'data' the screen took; what the
            --         terminal did is told.
            constant n : natural := hwut_vhpi_vterm_feed(handle, data);
        begin tell; return n; end function;

        procedure feed(data : string) is
            variable n : natural;
        begin n := feed(data); end procedure;

        impure function answer return string is
            -- RETURN: string, what the terminal answered (bytes) and no
            --         application took -- taken now.
        begin hwut_vhpi_vterm_answer(handle); return result; end function;

        impure function send(text : string; react_s : real := 1.0) return boolean is
            -- RETURN: true, the application still runs after 'text' (UTF-8)
            --         was typed and the screen read until quiet; false, else.
        begin clear; return said(hwut_vhpi_vterm_send(handle, text, react_s)); end function;

        procedure send(text : string; react_s : real := 1.0) is
            variable running_f : boolean;
        begin running_f := send(text, react_s); end procedure;

        impure function press(key : string; modifier : string := ""; react_s : real := 1.0) return boolean is
            -- RETURN: true, the application still runs after 'key' was
            --         pressed -- 'enter', 'up', 'f5', ... or one character --
            --         with 'modifier' ('shift', 'alt', 'ctrl', blank-
            --         separated); false, else, or no such key ('KeyError').
        begin clear; return said(hwut_vhpi_vterm_press(handle, key, modifier, react_s)); end function;

        procedure press(key : string; modifier : string := ""; react_s : real := 1.0) is
            variable running_f : boolean;
        begin running_f := press(key, modifier, react_s); end procedure;

        impure function run(argv : string; cwd : string := ""; start_s : real := 10.0) return boolean is
            -- RETURN: true, the application 'argv' -- its words, each ended
            --         by NUL -- still runs once its first screen stands; false,
            --         else, or one was run here already ('RuntimeError').
        begin clear; return said(hwut_vhpi_vterm_run(handle, argv, cwd, start_s)); end function;

        procedure run(argv : string; cwd : string := ""; start_s : real := 10.0) is
            variable running_f : boolean;
        begin running_f := run(argv, cwd, start_s); end procedure;

        impure function pump(first_s : real := 1.0) return boolean is
            -- RETURN: true, the application still runs after the screen was
            --         read until quiet; false, else.
        begin return said(hwut_vhpi_vterm_pump(handle, first_s)); end function;

        impure function expect(text : string; timeout_s : real := 10.0) return integer_vector is
            -- RETURN: integer_vector, (row, column) where 'text' stands on
            --         the screen, if success; (-1, -1), it did not appear
            --         within 'timeout_s' ('TimeoutError').
            variable place : integer;
        begin
            clear;
            place := hwut_vhpi_vterm_expect(handle, text, timeout_s);
            tell;
            if place < 0 then fail; return (-1, -1); end if;
            return (place / 65536, place mod 65536);
        end function;

        impure function wait_exit(timeout_s : real := 10.0) return integer is
            -- RETURN: integer, the application's exit status (negative: the
            --         signal that ended it) once it ended and its last words
            --         are on the screen; 0 where none was run; -1000, it still
            --         ran after 'timeout_s' and was killed ('TimeoutError').
            --         Python's 'wait' ('wait' is a reserved word).
            variable r : integer;
        begin
            clear;
            r := hwut_vhpi_vterm_wait(handle, timeout_s);
            if r < 0 then fail; end if;
            tell;
            if r < 0 then return -1000; end if;
            return hwut_vhpi_vterm_status;
        end function;

        impure function cursor return integer_vector is
            -- RETURN: integer_vector, (row, column) of the cursor, from 0.
            constant place : integer := hwut_vhpi_vterm_cursor(handle);
        begin return (place / 65536, place mod 65536); end function;

        impure function cell(row : integer; column : integer) return VtermCell is
            -- RETURN: VtermCell, what stands at ('row', 'column'); see
            --         'Screen.cell'.
        begin
            clear;
            if hwut_vhpi_vterm_cell(handle, row, column) /= 0 then fail; end if;
            return cell_of(handle, row, column);
        end function;

        impure function line(row : integer) return string is
            -- RETURN: string, the text of row 'row', blanks at its end removed.
        begin hwut_vhpi_vterm_line(handle, row); return result; end function;

        impure function failed return boolean is
            -- RETURN: true, the last method refused -- see 'error_kind'.
        begin return kind_text'length > 0; end function;

        impure function error_kind return string is
            -- RETURN: string, Python's name of the last refusal's exception.
        begin return kind_text.all; end function;

        impure function error_message return string is
            -- RETURN: string, the last refusal's text.
        begin return message_text.all; end function;
    end protected body;
end package body;
