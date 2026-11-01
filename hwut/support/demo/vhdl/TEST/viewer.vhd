-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- A TERMINAL FILE VIEWER -- the program 'screen.vhd' tests; no test itself.
--
--     viewer.exe <file>
--
-- Full screen, on the terminal's alternate screen: a title bar (reverse
-- video), as many lines of the file as fit, and a status line: the keys
-- flush left, the lines shown flush right. Keys: 'j' or down one line
-- further, 'k' or up one line back, 'q' quits.
--
-- VHDL draws; the terminal's raw mode, its size and the bytes of one key
-- come from 'demo_vhpi.c' -- textio reads lines, not keys.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_pytext.all;
use work.demo_vhpi.all;

entity viewer is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture program of viewer is
    constant ESC : character := character'val(27);
    constant CRLF : string := CR & LF;

    impure function file_lines(path : string) return str_list is
        -- RETURN: str_list, the lines of the file 'path'.
        file     f    : text open read_mode is path;
        variable l    : line;
        variable text : line := new string'("");
    begin
        while not endfile(f) loop readline(f, l); text := new string'(text.all & l.all & LF); end loop;
        return text.all;
    end function;

    function basename(path : string) return string is
        -- RETURN: string, 'path' after its last '/'.
    begin
        for i in path'right downto path'left loop
            if path(i) = '/' then return path(i + 1 to path'right); end if;
        end loop;
        return path;
    end function;

    function cut(text : string; width : natural) return string is
        -- RETURN: string, 'text', at most 'width' characters of it.
    begin
        if text'length <= width then return text; end if;
        return text(text'left to text'left + width - 1);
    end function;

    procedure draw(name : string; lines : str_list; top : natural; row_n : natural; column_n : natural) is
        -- RETURN: nothing; the whole screen is drawn with the file's line
        --         'top' (from 0) first.
        constant body_n  : natural := row_n - 2;
        constant shown_n : natural := minimum(body_n, item_n(lines) - top);
        constant keys    : string  := "j k q";
        constant where   : string  := "lines " & integer'image(top + 1) & "-" & integer'image(top + shown_n)
                                      & " of " & integer'image(item_n(lines));
        variable screen  : line := new string'(ESC & "[H" & ESC & "[2J");
    begin
        screen := new string'(screen.all & ESC & "[7m" & cut(ljust(" " & name, column_n), column_n) & ESC & "[0m" & CRLF);
        for i in top to top + shown_n - 1 loop
            screen := new string'(screen.all & cut(item(lines, i), column_n) & CRLF);
        end loop;
        for i in 1 to body_n - shown_n loop screen := new string'(screen.all & CRLF); end loop;
        screen := new string'(screen.all & ESC & "[" & integer'image(row_n) & ";1H" & keys
                              & rjust(where, column_n - 1 - keys'length));
        write_raw(screen.all);
    end procedure;
begin
    main : process
        variable path  : line;
        variable lines : line;
        variable key   : line;
        variable top   : natural := 0;
        variable row_n, column_n : natural;
    begin
        path     := new string'(argument(1));
        lines    := new string'(file_lines(path.all));
        row_n    := terminal_rows;
        column_n := terminal_columns;
        raw_mode(true);
        write_raw(ESC & "[?1049h");
        loop
            draw(basename(path.all), lines.all, top, row_n, column_n);
            key := new string'(read_key);
            exit when key.all = "q" or key.all = "";
            if key.all = "j" or key.all = ESC & "[B" then
                top := minimum(top + 1, maximum(0, item_n(lines.all) - (row_n - 2)));
            elsif key.all = "k" or key.all = ESC & "[A" then
                top := maximum(top - 1, 0);
            end if;
        end loop;
        write_raw(ESC & "[?1049l");
        raw_mode(false);
        wait;
    end process;
end architecture;
