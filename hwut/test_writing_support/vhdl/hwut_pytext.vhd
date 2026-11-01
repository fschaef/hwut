-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: TEXT AS PYTHON PRINTS IT -- so a VHDL test and a Python test of
--          the same module print the same bytes and share one GOOD file by a
--          '.link' (bookkeeper B-32). The VHDL twin of '../c/hwut_pytext.h'.
--
--     print("text")                      Python's print: the text, a newline
--     float_repr(0.1)        "0.1"       the shortest text that reads back
--     str_repr("it's")       "it's" in "  Python's choice of quotes
--     bytes_repr(ESC & "[A") b'\x1b[A'
--     bool_repr(true)        True
--     list_repr((3, 1))      [3, 1]      an integer_vector
--     list_repr("a" & LF & "b" & LF)     ['a', 'b']  a str_list (below)
--     tuple_repr("a" & LF)               ('a',)
--     ljust("ä", 3)          "ä  "       '%-3s': CHARACTERS of UTF-8, not bytes
--
-- WHAT VHDL CANNOT SAY ITSELF comes from '../c/hwut_pytext.c' by VHPIDIRECT:
-- a float's shortest repr (VHDL's real'image is no such text), and the
-- quotes and escapes of a str or bytes literal -- one implementation, checked
-- against Python's repr (C RATIONALE C-1). What VHDL can say -- True, a list,
-- a padding -- is said here.
--
-- PYTHON'S list[str] IS A 'str_list': one string, every item ENDED by LF --
-- "a" & LF & "b" & LF is ['a', 'b'], "" is [], LF alone is ['']. A VHDL
-- function takes and returns it (a vector of 'line' it could not: no function
-- parameter holds an access value), and no item of these modules holds a LF.
--     item_n(list)  item(list, i)  joined(list, ", ")
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;

package hwut_pytext is
    -- Python's list[str] where identity counts (a pool of candidates):
    -- texts of their own lengths, each an object of its own.
    type line_vector is array (natural range <>) of line;
    -- Python's list[str] as a value: every item ended by LF.
    subtype str_list is string;

    procedure print(text : string);

    impure function float_repr(x : real)     return string;
    impure function str_repr(text : string)  return string;
    impure function bytes_repr(data : string) return string;
    function        bool_repr(value : boolean) return string;

    function        list_repr(value : integer_vector) return string;
    impure function list_repr(value : str_list) return string;
    impure function tuple_repr(value : str_list) return string;
    function item_n(list : str_list) return natural;
    function item(list : str_list; i : natural) return string;
    function joined(list : str_list; separator : string) return string;

    function character_n(text : string) return natural;
    function ljust(text : string; width : natural) return string;
    function rjust(text : string; width : natural) return string;
    function zfill(value : integer; width : natural) return string;
    function signed_image(value : integer) return string;
end package;

package body hwut_pytext is
    procedure hwut_vhpi_float_repr(x : real);
    attribute foreign of hwut_vhpi_float_repr : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_float_repr";
    procedure hwut_vhpi_float_repr(x : real) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_str_repr(text : string);
    attribute foreign of hwut_vhpi_str_repr : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_str_repr";
    procedure hwut_vhpi_str_repr(text : string) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_bytes_repr(data : string);
    attribute foreign of hwut_vhpi_bytes_repr : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_bytes_repr";
    procedure hwut_vhpi_bytes_repr(data : string) is begin assert false severity failure; end procedure;

    procedure print(text : string) is
        -- RETURN: nothing; 'text' and a newline stand on 'output' (stdout).
        variable l : line;
    begin
        write(l, text);
        writeline(output, l);
    end procedure;

    impure function float_repr(x : real) return string is
        -- RETURN: string, 'x' as Python's repr(float) writes it -- the
        --         shortest decimal that reads back to the same double, fixed
        --         where the decimal point falls in (-4, 16], else exponential.
    begin
        hwut_vhpi_float_repr(x);
        return result;
    end function;

    impure function str_repr(text : string) return string is
        -- RETURN: string, the UTF-8 'text' as Python's repr(str) writes it:
        --         single quotes, or double ones where it holds a single quote
        --         and no double one; the backslash, that quote and what does
        --         not print escaped.
    begin
        hwut_vhpi_str_repr(text);
        return result;
    end function;

    impure function bytes_repr(data : string) return string is
        -- RETURN: string, the characters of 'data', taken as bytes, as
        --         Python's repr(bytes) writes them: b'...', every byte from
        --         0x7f on escaped too.
    begin
        hwut_vhpi_bytes_repr(data);
        return result;
    end function;

    function bool_repr(value : boolean) return string is
        -- RETURN: string, "True" where 'value'; "False", else.
    begin
        if value then return "True"; end if;
        return "False";
    end function;

    function list_repr(value : integer_vector) return string is
        -- RETURN: string, 'value' as Python prints a list of int: "[3, 1]",
        --         "[]" for none.
        variable text : line;
    begin
        write(text, string'("["));
        for i in value'range loop
            if i /= value'left then write(text, string'(", ")); end if;
            write(text, integer'image(value(i)));
        end loop;
        write(text, string'("]"));
        return text.all;
    end function;

    function normal(text : string) return string is
        -- RETURN: string, 'text' indexed from 1.
        constant result : string(1 to text'length) := text;
    begin return result; end function;

    function item_n(list : str_list) return natural is
        -- RETURN: natural, the number of items of 'list' -- its LFs.
        variable n : natural := 0;
    begin
        for i in list'range loop
            if list(i) = LF then n := n + 1; end if;
        end loop;
        return n;
    end function;

    function item(list : str_list; i : natural) return string is
        -- RETURN: string, item 'i' (from 0) of 'list', without its LF,
        --         indexed from 1; "" where 'list' has no such item.
        variable k     : natural  := 0;
        variable begin_i : positive := list'left;
    begin
        for j in list'range loop
            if list(j) = LF then
                if k = i then return normal(list(begin_i to j - 1)); end if;
                k := k + 1; begin_i := j + 1;
            end if;
        end loop;
        return "";
    end function;

    function joined(list : str_list; separator : string) return string is
        -- RETURN: string, the items of 'list' with 'separator' between them
        --         -- Python's 'separator.join(list)'.
        variable text : line := new string'("");
    begin
        for i in 0 to item_n(list) - 1 loop
            if i /= 0 then write(text, separator); end if;
            write(text, item(list, i));
        end loop;
        return text.all;
    end function;

    impure function repr_joined(list : str_list; open_text : string; close_text : string;
                                one_text : string) return string is
        -- RETURN: string, the repr of every item of 'list', ', '-joined,
        --         between 'open_text' and 'close_text' -- 'one_text' closing
        --         a single one.
        variable text : line;
        constant n    : natural := item_n(list);
    begin
        write(text, open_text);
        for i in 0 to n - 1 loop
            if i /= 0 then write(text, string'(", ")); end if;
            write(text, str_repr(item(list, i)));
        end loop;
        if n = 1 then write(text, one_text);
        else          write(text, close_text);
        end if;
        return text.all;
    end function;

    impure function list_repr(value : str_list) return string is
        -- RETURN: string, 'value' as Python prints a list of str:
        --         "['a', 'b']", "[]" for none.
    begin return repr_joined(value, "[", "]", "]"); end function;

    impure function tuple_repr(value : str_list) return string is
        -- RETURN: string, 'value' as Python prints a tuple of str:
        --         "('a', 'b')", "('a',)" for one, "()" for none.
    begin return repr_joined(value, "(", ")", ",)"); end function;

    function character_n(text : string) return natural is
        -- RETURN: natural, the number of CHARACTERS the UTF-8 'text' holds --
        --         its bytes but the continuation ones (10xxxxxx).
        variable n : natural := 0;
    begin
        for i in text'range loop
            if character'pos(text(i)) < 16#80# or character'pos(text(i)) >= 16#C0# then n := n + 1; end if;
        end loop;
        return n;
    end function;

    function ljust(text : string; width : natural) return string is
        -- RETURN: string, 'text' filled with blanks on the right to 'width'
        --         characters -- Python's '%-Ns'; 'text' itself where longer.
        constant n : natural := character_n(text);
    begin
        if n >= width then return text; end if;
        return text & (1 to width - n => ' ');
    end function;

    function rjust(text : string; width : natural) return string is
        -- RETURN: string, 'text' filled with blanks on the left to 'width'
        --         characters -- Python's '%Ns'; 'text' itself where longer.
        constant n : natural := character_n(text);
    begin
        if n >= width then return text; end if;
        return (1 to width - n => ' ') & text;
    end function;

    function zfill(value : integer; width : natural) return string is
        -- RETURN: string, 'value' in decimal, zeros before its digits up to
        --         'width' characters -- Python's '%0Nd'.
        constant digits : string := integer'image(abs value);
        constant sign   : string := "-";
        constant n      : natural := digits'length + boolean'pos(value < 0);
    begin
        if n >= width then return integer'image(value); end if;
        if value < 0 then return sign & (1 to width - n => '0') & digits; end if;
        return (1 to width - n => '0') & digits;
    end function;

    function signed_image(value : integer) return string is
        -- RETURN: string, 'value' in decimal with its sign, '+' too --
        --         Python's '%+d'.
    begin
        if value >= 0 then return "+" & integer'image(value); end if;
        return integer'image(value);
    end function;
end package body;
