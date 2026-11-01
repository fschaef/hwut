-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: WHAT THE DEMONSTRATION'S TESTS SHARE, beside the port -- no test.
--
--     ClockRandom      Python's 'random' seeded by the clock: uniform,
--                      randint, gauss, a shuffled order (ieee.math_real's
--                      generator; the seed from 'demo_vhpi.c')
--     argument(i)      the program's argument i (from 1) -- the launcher
--                      gives two as generics, every one in 'HWUT_ARGV'
--     hex(v, width)    '%0<width>x' / '%0<width>X'
--     stamp            the local time, '%Y-%m-%dT%H:%M:%S'
--     eprint(text)     a line on stderr (textio knows no stderr)
--     exists, make_directory, remove
--     write_raw(text)  bytes on stdout, no newline after (a terminal's)
--     raw_mode, read_key, terminal_rows, terminal_columns
--                      the terminal of 'viewer.vhd'
--
-- The C side is 'demo_vhpi.c', linked into the target's 'libhwut_vhdl.so'.
-- _____________________________________________________________________________
library ieee;
use ieee.math_real.all;
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;

package demo_vhpi is
    type ClockRandom is protected
        procedure init;
        impure function uniform(low : real; high : real) return real;
        impure function randint(low : integer; high : integer) return integer;
        impure function gauss(mu : real; sigma : real) return real;
        impure function permutation(n : positive) return integer_vector;
    end protected;

    function hex(value : natural; width : natural; upper : boolean := false) return string;
    impure function stamp return string;
    procedure eprint(text : string);
    impure function exists(path : string) return boolean;
    procedure make_directory(path : string);
    procedure remove(path : string);

    procedure write_raw(text : string);
    procedure raw_mode(raw_f : boolean);
    impure function read_key return string;
    impure function terminal_rows return natural;
    impure function terminal_columns return natural;

    impure function argument(i : positive) return string;
    impure function demo_result return string;
end package;

package body demo_vhpi is
    impure function demo_vhpi_result_n return integer;
    attribute foreign of demo_vhpi_result_n : function is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_result_n";
    impure function demo_vhpi_result_n return integer is begin assert false severity failure; return 0; end function;

    procedure demo_vhpi_result_get(text : inout string);
    attribute foreign of demo_vhpi_result_get : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_result_get";
    procedure demo_vhpi_result_get(text : inout string) is begin assert false severity failure; end procedure;

    impure function demo_vhpi_seed(k : integer) return integer;
    attribute foreign of demo_vhpi_seed : function is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_seed";
    impure function demo_vhpi_seed(k : integer) return integer is begin assert false severity failure; return 0; end function;

    procedure demo_vhpi_stamp;
    attribute foreign of demo_vhpi_stamp : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_stamp";
    procedure demo_vhpi_stamp is begin assert false severity failure; end procedure;

    procedure demo_vhpi_eprint(text : string);
    attribute foreign of demo_vhpi_eprint : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_eprint";
    procedure demo_vhpi_eprint(text : string) is begin assert false severity failure; end procedure;

    impure function demo_vhpi_exists(path : string) return integer;
    attribute foreign of demo_vhpi_exists : function is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_exists";
    impure function demo_vhpi_exists(path : string) return integer is begin assert false severity failure; return 0; end function;

    procedure demo_vhpi_mkdir(path : string);
    attribute foreign of demo_vhpi_mkdir : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_mkdir";
    procedure demo_vhpi_mkdir(path : string) is begin assert false severity failure; end procedure;

    procedure demo_vhpi_remove(path : string);
    attribute foreign of demo_vhpi_remove : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_remove";
    procedure demo_vhpi_remove(path : string) is begin assert false severity failure; end procedure;

    procedure demo_vhpi_write(text : string);
    attribute foreign of demo_vhpi_write : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_write";
    procedure demo_vhpi_write(text : string) is begin assert false severity failure; end procedure;

    procedure demo_vhpi_raw(raw_f : integer);
    attribute foreign of demo_vhpi_raw : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_raw";
    procedure demo_vhpi_raw(raw_f : integer) is begin assert false severity failure; end procedure;

    impure function demo_vhpi_read_key return integer;
    attribute foreign of demo_vhpi_read_key : function is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_read_key";
    impure function demo_vhpi_read_key return integer is begin assert false severity failure; return 0; end function;

    impure function demo_vhpi_terminal_size(which : integer) return integer;
    attribute foreign of demo_vhpi_terminal_size : function is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_terminal_size";
    impure function demo_vhpi_terminal_size(which : integer) return integer is begin assert false severity failure; return 0; end function;

    impure function demo_result return string is
        -- RETURN: string, the text the last call of 'demo_vhpi.c' left.
        variable text : string(1 to demo_vhpi_result_n);
    begin
        demo_vhpi_result_get(text);
        return text;
    end function;

    type ClockRandom is protected body
        variable seed1 : positive := 1;
        variable seed2 : positive := 1;

        procedure init is
            -- RETURN: nothing; the stream starts where the clock says.
        begin
            seed1 := demo_vhpi_seed(1);
            seed2 := 1 + demo_vhpi_seed(2) mod 2147483397;
        end procedure;

        impure function uniform(low : real; high : real) return real is
            -- RETURN: real, drawn evenly from [low, high].
            variable x : real;
        begin
            ieee.math_real.uniform(seed1, seed2, x);
            return low + (high - low) * x;
        end function;

        impure function randint(low : integer; high : integer) return integer is
            -- RETURN: integer, drawn evenly from low .. high, both included.
            variable x : real;
        begin
            ieee.math_real.uniform(seed1, seed2, x);
            return minimum(high, low + integer(floor(x * real(high - low + 1))));
        end function;

        impure function gauss(mu : real; sigma : real) return real is
            -- RETURN: real, drawn from the normal distribution (mu, sigma)
            --         -- Box and Muller.
            variable u1, u2 : real;
        begin
            ieee.math_real.uniform(seed1, seed2, u1);
            ieee.math_real.uniform(seed1, seed2, u2);
            return mu + sigma * sqrt(-2.0 * log(1.0 - u1)) * cos(MATH_2_PI * u2);
        end function;

        impure function permutation(n : positive) return integer_vector is
            -- RETURN: integer_vector, 0 .. n-1 in a drawn order (Fisher, Yates).
            variable p    : integer_vector(0 to n - 1);
            variable j, t : integer;
        begin
            for i in p'range loop p(i) := i; end loop;
            for i in n - 1 downto 1 loop
                j := randint(0, i);
                t := p(i); p(i) := p(j); p(j) := t;
            end loop;
            return p;
        end function;
    end protected body;

    function hex(value : natural; width : natural; upper : boolean := false) return string is
        -- RETURN: string, 'value' in hexadecimal, at least 'width' digits,
        --         zeros in front -- '%0<width>x' ('upper': '%0<width>X').
        constant DIGIT : string(1 to 16) := "0123456789abcdef";
        variable text  : line := new string'("");
        variable v     : natural := value;
        variable c     : character;
    begin
        loop
            c := DIGIT(v mod 16 + 1);
            if upper and c >= 'a' then c := character'val(character'pos(c) - 32); end if;
            text := new string'(c & text.all);
            v := v / 16;
            exit when v = 0 and text.all'length >= width;
        end loop;
        return text.all;
    end function;

    impure function stamp return string is
        -- RETURN: string, the local time now, '%Y-%m-%dT%H:%M:%S'.
    begin demo_vhpi_stamp; return demo_result; end function;

    procedure eprint(text : string) is
        -- RETURN: nothing; 'text' and a newline stand on stderr.
    begin demo_vhpi_eprint(text); end procedure;

    impure function exists(path : string) return boolean is
        -- RETURN: true, 'path' stands; false, else.
    begin return demo_vhpi_exists(path) /= 0; end function;

    procedure make_directory(path : string) is
        -- RETURN: nothing; the directory 'path' stands.
    begin demo_vhpi_mkdir(path); end procedure;

    procedure remove(path : string) is
        -- RETURN: nothing; the file 'path' does not stand.
    begin demo_vhpi_remove(path); end procedure;

    procedure write_raw(text : string) is
        -- RETURN: nothing; the bytes of 'text' stand on stdout, no newline.
    begin demo_vhpi_write(text); end procedure;

    procedure raw_mode(raw_f : boolean) is
        -- RETURN: nothing; stdin is raw ('on') or as it was before.
    begin demo_vhpi_raw(boolean'pos(raw_f)); end procedure;

    impure function read_key return string is
        -- RETURN: string, the bytes one key gave on stdin; "" at the end of
        --         the input.
        variable n : integer := demo_vhpi_read_key;
    begin
        if n = 0 then return ""; end if;
        return demo_result;
    end function;

    impure function argument(i : positive) return string is
        -- RETURN: string, the program's argument 'i' (from 1), as the
        --         launcher left them in 'HWUT_ARGV'; "" beyond the last.
        constant list : str_list := getenv("HWUT_ARGV");
    begin
        if i > item_n(list) then return ""; end if;
        return item(list, i - 1);
    end function;

    impure function terminal_rows return natural is
        -- RETURN: natural, the rows of the terminal on stdout (24 for none).
    begin return demo_vhpi_terminal_size(0); end function;

    impure function terminal_columns return natural is
        -- RETURN: natural, the columns of the terminal on stdout (80 for none).
    begin return demo_vhpi_terminal_size(1); end function;
end package body;
