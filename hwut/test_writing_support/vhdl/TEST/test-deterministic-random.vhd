-- @hwut {
--     title      = "DeterministicStream RNG and SelectionMarker spread"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         gauss      { features = ["vhdl-random"] }
--         primitives { features = ["vhdl-random"] }
--         ranges     { features = ["vhdl-random"] }
--         sample     { features = ["vhdl-random"] }
--         seed_sweep { features = ["vhdl-random"] }
--         select     { features = ["vhdl-random"] }
--         unchosen   { features = ["vhdl-random"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The VHDL port of 'python/TEST/test-deterministic-random.py', choice
--          for choice, held against its GOOD files by '.link'. The stream is
--          VHDL's own (32-bit integers, Schrage); a float prints as Python's
--          repr ('hwut_pytext').
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_runner.all;
use work.hwut_pytext.all;
use work.deterministic_random.all;

entity test_deterministic_random is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
end entity;

architecture test of test_deterministic_random is
    constant SEED                   : integer := 16#42#;
    constant TOLERANCE_REGION_BEGIN : string  := "##! table numeric={1:1e-12}";
    constant REGION_END             : string  := "####";

    procedure banner(label_text : string) is
    begin print(""); print("--- " & label_text & " ---"); end procedure;

    procedure word(variable text : inout line; w : string) is
        -- RETURN: nothing; 'w' is appended to 'text', a blank before it
        --         unless it is the first -- Python's ' '.join.
    begin
        if text = null then text := new string'(w);
        else                write(text, " " & w);
        end if;
    end procedure;

    procedure say(variable text : inout line) is
    begin print(text.all); deallocate(text); end procedure;

    procedure run_primitives is
        variable s : DeterministicStream;
        variable t : line;
    begin
        banner("next_int(0, 1000000) -- first 20");
        s.init(SEED);
        for i in 0 to 19 loop print("[" & zfill(i, 2) & "] " & integer'image(s.next_int(0, 1000000))); end loop;
        banner("next_float -- first 10 (full precision)");
        s.init(SEED);
        for i in 0 to 9 loop print("[" & zfill(i, 2) & "] " & float_repr(s.next_float)); end loop;
        banner("coin(0.5) -- 40 draws");
        s.init(SEED);
        for i in 0 to 39 loop
            if s.coin(0.5) then word(t, "T"); else word(t, "F"); end if;
        end loop;
        say(t);
    end procedure;

    procedure run_ranges is
        variable s : DeterministicStream;
        variable t : line;
    begin
        banner("next_int(0, 9) -- 30 draws");
        s.init(SEED);
        for i in 0 to 29 loop word(t, integer'image(s.next_int(0, 9))); end loop;
        say(t);
        banner("next_int(5, 5) -- degenerate range returns the bound");
        s.init(SEED);
        for i in 0 to 4 loop word(t, integer'image(s.next_int(5, 5))); end loop;
        say(t);
        banner("next_int(-3, 3) -- spanning zero");
        s.init(SEED);
        for i in 0 to 19 loop word(t, signed_image(s.next_int(-3, 3))); end loop;
        say(t);
    end procedure;

    procedure run_gauss is
        variable s : DeterministicStream;
        variable t : line;
    begin
        banner("gauss(0, 1) -- 10 draws (full precision)");
        s.init(SEED);
        print(TOLERANCE_REGION_BEGIN);
        for i in 0 to 9 loop print("[" & zfill(i, 2) & "] " & float_repr(s.gauss(0.0, 1.0))); end loop;
        print(REGION_END);
        banner("gauss(0, 1) clamped to [-1, 1]");
        s.init(SEED);
        print(TOLERANCE_REGION_BEGIN);
        for i in 0 to 9 loop print("[" & zfill(i, 2) & "] " & float_repr(s.gauss(0.0, 1.0, -1.0, 1.0))); end loop;
        print(REGION_END);
        banner("gauss_int(100, 15) -- 20 draws");
        s.init(SEED);
        for i in 0 to 19 loop word(t, integer'image(s.gauss_int(100.0, 15.0))); end loop;
        say(t);
    end procedure;

    procedure run_sample is
        constant pool : str_list := "alpha" & LF & "beta" & LF & "gamma" & LF & "delta" & LF & "epsilon" & LF;
        constant letter : str_list := "A" & LF & "B" & LF & "C" & LF & "D" & LF & "E" & LF & "F" & LF
                                      & "G" & LF & "H" & LF;
        variable s : DeterministicStream;
        variable t : line;
    begin
        banner("sample_indices(10, 10) -- full permutation");
        s.init(SEED); print(list_repr(s.sample_indices(10, 10)));
        banner("sample_indices(20, 5) -- partial draw");
        s.init(SEED); print(list_repr(s.sample_indices(20, 5)));
        banner("choice from a list -- 20 draws");
        s.init(SEED);
        for i in 0 to 19 loop word(t, item(pool, s.choice(5))); end loop;
        say(t);
        banner("sample(list, 4) -- unique elements");
        s.init(SEED); print(list_repr(s.sample(letter, 4)));
    end procedure;

    procedure run_select is
        constant pool   : str_list := "a" & LF & "b" & LF & "c" & LF & "d" & LF;
        constant branch : str_list := "p" & LF & "q" & LF & "r" & LF;
        variable s : DeterministicStream;
        variable t : line;
    begin
        banner("select over a list -- 20 draws");
        s.init(SEED);
        for i in 0 to 19 loop word(t, item(pool, s.select_index(4))); end loop;
        say(t);
        banner("select over a tuple -- 12 draws");
        s.init(SEED);
        for i in 0 to 11 loop word(t, item(branch, s.select_index(3))); end loop;
        say(t);
    end procedure;

    procedure run_unchosen is
        --  THE CANDIDATES ARE OBJECTS: four lines, each made once -- as the
        --  four str objects of the Python test are.
        variable a      : line := new string'("a");
        variable b      : line := new string'("b");
        variable c      : line := new string'("c");
        variable d      : line := new string'("d");
        variable pool   : line_vector(0 to 3) := (a, b, c, d);
        variable fresh  : line_vector(0 to 3);
        variable sub    : line_vector(0 to 1) := (a, b);
        variable s      : DeterministicStream;
        variable m      : SelectionMarker;
        variable choice : line;
        variable t      : line;
        variable before : line;
    begin
        banner("stable pool -- three full cycles of 4 elements");
        s.init(SEED); reset(m);
        for i in 0 to 11 loop select_unchosen(s, pool, m, choice); word(t, choice.all); end loop;
        say(t);

        banner("FRESH container each call -- identical to the stable pool above");
        s.init(SEED); reset(m);
        for i in 0 to 11 loop
            fresh := (a, b, c, d);                         -- a new vector every call
            select_unchosen(s, fresh, m, choice); word(t, choice.all);
        end loop;
        say(t);

        banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]");
        s.init(SEED); reset(m);
        select_unchosen(s, sub, m, choice);
        t := new string'("first(from sub): " & choice.all & "  then(from full):");
        for i in 0 to 2 loop select_unchosen(s, pool, m, choice); write(t, " " & choice.all); end loop;
        say(t);

        banner("reset() restarts the cycle");
        s.init(SEED); reset(m);
        before := new string'("before reset:");
        for i in 0 to 3 loop select_unchosen(s, pool, m, choice); write(before, " " & choice.all); end loop;
        reset(m);
        t := new string'("after  reset:");
        for i in 0 to 3 loop select_unchosen(s, pool, m, choice); write(t, " " & choice.all); end loop;
        say(before);
        say(t);
    end procedure;

    procedure run_seed_sweep is
        variable s : DeterministicStream;
    begin
        banner("first next_int(0, 1000000) per seed 0..15");
        for seed_i in 0 to 15 loop
            s.init(seed_i);
            print("seed=" & rjust(integer'image(seed_i), 2) & " -> " & integer'image(s.next_int(0, 1000000)));
        end loop;
    end procedure;
begin
    main : process
        variable runner : HwutRunner;
    begin
        runner.init(HWUT_ARGC, HWUT_ARGV1, "DeterministicStream RNG and SelectionMarker spread");
        runner.add("primitives"); runner.add("ranges");   runner.add("gauss"); runner.add("sample");
        runner.add("select");     runner.add("unchosen"); runner.add("seed_sweep");
        while runner.dispatch loop
            if    runner.choice = "primitives" then run_primitives;
            elsif runner.choice = "ranges"     then run_ranges;
            elsif runner.choice = "gauss"      then run_gauss;
            elsif runner.choice = "sample"     then run_sample;
            elsif runner.choice = "select"     then run_select;
            elsif runner.choice = "unchosen"   then run_unchosen;
            elsif runner.choice = "seed_sweep" then run_seed_sweep;
            end if;
            runner.choice_done;
        end loop;
        wait;
    end process;
end architecture;
