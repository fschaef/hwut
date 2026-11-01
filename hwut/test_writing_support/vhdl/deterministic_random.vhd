-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
--          'python/deterministic_random.py', in VHDL alone. The same seed
--          gives the same numbers as the Python module, draw for draw:
--          Park-Miller MINSTD, 'state = 48271 * state mod (2^31 - 1)'.
--
--     variable s : DeterministicStream;            -- stands at seed 0x42
--     s.init(16#42#);
--     s.next_int(0, 9);   s.next_float;   s.coin(0.5);
--     pool(s.select_index(pool'length)).all        -- 'select' returns an INDEX
--     s.gauss(0.0, 1.0);  s.gauss_int(100.0, 15.0);
--     s.sample_indices(10, 3);                     -- an integer_vector
--     s.sample("A" & LF & "B" & LF & "C" & LF, 2)  -- a str_list
--
--     variable m : SelectionMarker;
--     select_unchosen(s, pool, m, choice);         -- 'choice' one of pool's lines
--
-- 'select' IS A RESERVED WORD of VHDL: the method is 'select_index'; it and
-- 'choice' return the index into the caller's candidates, which VHDL cannot
-- hand to a function as a list of any type.
--
-- 32-BIT INTEGERS: '48271 * state' does not fit; Schrage's decomposition
-- (q = m / a, r = m mod a) computes the same product modulo 2^31 - 1 without
-- leaving the integer range -- no 64-bit arithmetic is needed.
--
-- IDENTITY, AS IN PYTHON: a marker remembers a candidate as the OBJECT it is
-- -- the 'line' (access value) that holds it, Python's 'id()'. A fresh vector
-- of the same lines is the same pool, as a fresh list of the same objects is.
--
-- 'gauss' is the one path through libm -- the PLATFORM'S sqrt, log and cos,
-- by VHPIDIRECT ('hwut_vhpi.c'), as Python's 'math' calls them: GHDL's
-- math_real is IEEE's reference body written in VHDL, its 'cos' off in the
-- 9th digit (measured). A last bit may still differ between platforms, so a
-- GOOD that prints a draw tolerates the last digits.
-- _____________________________________________________________________________
use std.textio.all;
library ieee;
use ieee.math_real.floor;
use ieee.math_real.MATH_PI;
use work.hwut_pytext.all;

package deterministic_random is
    constant SELECTION_MARKER_MAX : positive := 256;

    type SelectionMarker is record
        chosen   : line_vector(0 to SELECTION_MARKER_MAX - 1);
        chosen_n : natural;
    end record;

    procedure reset(variable marker : inout SelectionMarker);

    type DeterministicStream is protected
        procedure init(seed : integer := 16#42#);
        impure function next_int(v_min : integer; v_max : integer) return integer;
        impure function next_float return real;
        impure function coin(probability_of_true : real) return boolean;
        impure function select_index(candidate_n : positive) return natural;
        impure function choice(candidate_n : positive) return natural;
        impure function gauss(mu : real; sigma : real; lower : real := real'low;
                              upper : real := real'high) return real;
        impure function gauss_int(mu : real; sigma : real; lower : real := real'low;
                                  upper : real := real'high) return integer;
        impure function sample_indices(population_size : natural; k : natural) return integer_vector;
        impure function sample(population : str_list; n : natural) return str_list;
    end protected;

    procedure select_unchosen(variable stream     : inout DeterministicStream;
                              variable candidates : inout line_vector;
                              variable marker     : inout SelectionMarker;
                              variable choice     : out   line);

    function round_half_even(x : real) return integer;
end package;

package body deterministic_random is
    function libm_sqrt(x : real) return real;
    attribute foreign of libm_sqrt : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_sqrt";
    function libm_sqrt(x : real) return real is begin assert false severity failure; return 0.0; end function;

    function libm_log(x : real) return real;
    attribute foreign of libm_log : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_log";
    function libm_log(x : real) return real is begin assert false severity failure; return 0.0; end function;

    function libm_cos(x : real) return real;
    attribute foreign of libm_cos : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_cos";
    function libm_cos(x : real) return real is begin assert false severity failure; return 0.0; end function;

    procedure reset(variable marker : inout SelectionMarker) is
        -- RETURN: nothing; every chosen candidate is forgotten -- the next
        --         cycle restarts.
    begin marker.chosen_n := 0; end procedure;

    function round_half_even(x : real) return integer is
        -- RETURN: integer, 'x' rounded to the nearest integer, a half to the
        --         even one -- Python's round().
        constant low  : real := floor(x);
        constant rest : real := x - low;
    begin
        if rest > 0.5 then return integer(low) + 1; end if;
        if rest < 0.5 then return integer(low);     end if;
        if integer(low) mod 2 = 0 then return integer(low); end if;
        return integer(low) + 1;
    end function;

    type DeterministicStream is protected body
        constant M : integer := 2147483647;     -- 2^31 - 1
        constant A : integer := 48271;
        constant Q : integer := M / A;          -- 44488
        constant R : integer := M mod A;        -- 3399
        variable state : integer := 16#42#;

        procedure init(seed : integer := 16#42#) is
            -- RETURN: nothing; the stream stands at 'seed & 0x7FFFFFFF'.
        begin
            if seed < 0 then state := (seed + M) + 1;    -- the low 31 bits
            else             state := seed;
            end if;
        end procedure;

        impure function next_int(v_min : integer; v_max : integer) return integer is
            -- RETURN: integer, uniform in [v_min, v_max]; the state steps
            --         even where the range is one value -- then 'v_min'.
            variable t : integer;
        begin
            t := A * (state mod Q) - R * (state / Q);
            if t < 0 then t := t + M; end if;
            state := t;
            if v_min = v_max then return v_min; end if;
            return v_min + (state mod (v_max - v_min + 1));
        end function;

        impure function next_float return real is
            -- RETURN: real in [0, 1): 'next_int(0, 1000000) / 1000001'.
        begin return real(next_int(0, 1000000)) / 1000001.0; end function;

        impure function coin(probability_of_true : real) return boolean is
            -- RETURN: true with 'probability_of_true', false else. THE FLOOR
            --         (TW-1): resolved in steps of 1/1000001.
        begin return next_float < probability_of_true; end function;

        impure function select_index(candidate_n : positive) return natural is
            -- RETURN: natural, an index into 'candidate_n' candidates,
            --         uniformly drawn -- Python's 'select'. Stateless: the
            --         same state and count give the same index.
        begin return next_int(0, candidate_n - 1); end function;

        impure function choice(candidate_n : positive) return natural is
            -- RETURN: natural, an index into 'candidate_n' elements,
            --         uniformly drawn -- Python's 'choice'.
        begin return next_int(0, candidate_n - 1); end function;

        impure function gauss(mu : real; sigma : real; lower : real := real'low;
                              upper : real := real'high) return real is
            -- RETURN: real, a draw of the normal distribution (mu, sigma) by
            --         the Box-Muller transform, clipped to [lower, upper].
            constant u1     : real := next_float + 1.0e-9;          -- avoid log(0)
            constant u2     : real := next_float;
            constant z0     : real := libm_sqrt(-2.0 * libm_log(u1)) * libm_cos(2.0 * MATH_PI * u2);
            constant result : real := z0 * sigma + mu;
        begin
            if result < lower then return lower; end if;
            if result > upper then return upper; end if;
            return result;
        end function;

        impure function gauss_int(mu : real; sigma : real; lower : real := real'low;
                                  upper : real := real'high) return integer is
            -- RETURN: integer, 'gauss' rounded to the nearest integer, a half
            --         to the even one (Python's round()).
        begin return round_half_even(gauss(mu, sigma, lower, upper)); end function;

        impure function sample_indices(population_size : natural; k : natural) return integer_vector is
            -- RETURN: integer_vector, 'k' distinct indices of 0 ..
            --         population_size - 1, by Fisher-Yates -- as many draws
            --         as Python's, in the same order.
            variable index  : integer_vector(0 to population_size - 1);
            variable result : integer_vector(0 to k - 1);
            variable j, t   : integer;
        begin
            assert population_size >= k severity failure;
            for i in index'range loop index(i) := i; end loop;
            for i in 0 to k - 1 loop
                j        := next_int(i, population_size - 1);
                t        := index(i); index(i) := index(j); index(j) := t;
                result(i) := index(i);
            end loop;
            return result;
        end function;

        impure function sample(population : str_list; n : natural) return str_list is
            -- RETURN: str_list, 'n' distinct items of 'population', drawn as
            --         'sample_indices' draws their indices.
            constant index : integer_vector := sample_indices(item_n(population), n);
            variable text  : line := new string'("");
        begin
            for i in index'range loop write(text, item(population, index(i)) & LF); end loop;
            return text.all;
        end function;
    end protected body;

    procedure select_unchosen(variable stream     : inout DeterministicStream;
                              variable candidates : inout line_vector;
                              variable marker     : inout SelectionMarker;
                              variable choice     : out   line) is
        -- RETURN: nothing; 'choice' is a candidate -- one of the lines of
        --         'candidates' -- that 'marker' has not seen, uniformly drawn
        --         among those, and now recorded. Where every candidate was
        --         seen, the marker is reset and the draw is from them all.
        variable unchosen : line_vector(0 to candidates'length - 1);
        variable n        : natural := 0;
        variable pick     : line;
        variable seen_f   : boolean;
    begin
        for i in candidates'range loop
            seen_f := false;
            for k in 0 to marker.chosen_n - 1 loop
                seen_f := seen_f or marker.chosen(k) = candidates(i);       -- the object, Python's id()
            end loop;
            if not seen_f then unchosen(n) := candidates(i); n := n + 1; end if;
        end loop;
        if n = 0 then
            reset(marker);
            for i in candidates'range loop unchosen(n) := candidates(i); n := n + 1; end loop;
        end if;
        pick := unchosen(stream.next_int(0, n - 1));
        if marker.chosen_n < SELECTION_MARKER_MAX then
            marker.chosen(marker.chosen_n) := pick;
            marker.chosen_n                := marker.chosen_n + 1;
        end if;
        choice := pick;
    end procedure;
end package body;
