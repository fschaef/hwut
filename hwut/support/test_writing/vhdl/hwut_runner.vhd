-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN VHDL -- the port of
--          'python/hwut_runner.py': the same modes, the same words.
--
--     app --hwut-info      the info block; exit 0.
--     app <choice>         one choice; test output on stdout and stderr,
--                          '<hwut-end>' after it. '-' runs a choice-less test.
--     app --interactive    choices started over stdin, output into two named
--                          sink files per choice, 'done' on the original stdout.
--     app                  the choice-less test; where the application has
--                          choices, refused, naming them.
--
-- USAGE -- a VHDL process has no command line and VHDL no function values: the
-- launcher 'test-x.exe' hands the command line in as two generics, and the
-- runner tells the process WHICH choice to run, which it runs itself:
--
--     entity test_x is
--         generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
--     end entity;
--     architecture test of test_x is
--     begin
--         main : process
--             variable runner : HwutRunner;
--         begin
--             runner.init(HWUT_ARGC, HWUT_ARGV1, "What this tests");
--             runner.add("plain");  runner.add("tricky");
--             while runner.dispatch loop
--                 if    runner.choice = "plain"  then run_plain;
--                 elsif runner.choice = "tricky" then run_tricky;
--                 end if;
--                 runner.choice_done;
--             end loop;
--         end process;
--     end architecture;
--
-- A choice-less test adds the one choice "-". Before 'dispatch' a test may
-- 'add_happy' patterns and 'set_same'. 'dispatch' and 'choice_done' END THE
-- PROCESS where the mode is done (exit status as Python's), so the loop runs
-- one choice: a choice may 'wait' (it runs in the process), and may use any
-- other process of the design.
--
-- THE INTERACTIVE PROTOCOL is Python's, line for line, read from stdin by
-- textio:
--     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
--     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
-- EVERY CHOICE RUNS IN A CHILD PROCESS of its own (fork, through 'hwut_vhpi'):
-- a choice that ends the process ends that choice, not the session -- what
-- Python gets by catching SystemExit -- and no choice inherits another's state.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;

package hwut_runner is
    constant HWUT_RUNNER_CHOICE_MAX : positive := 256;

    type HwutRunner is protected
        procedure init(argc : natural; argv1 : string; title : string);
        procedure add(name : string);
        procedure add_happy(pattern : string);
        procedure set_same;
        impure function dispatch return boolean;
        impure function choice return string;
        procedure choice_done;
    end protected;

    function levenshtein_distance(a : string; b : string) return natural;
end package;

package body hwut_runner is
    function levenshtein_distance(a : string; b : string) return natural is
        -- RETURN: natural, the Levenshtein distance between 'a' and 'b'.
        variable prev, cur : integer_vector(0 to b'length);
        variable ca, cb    : character;
    begin
        if a = b         then return 0; end if;
        if a'length = 0  then return b'length; end if;
        if b'length = 0  then return a'length; end if;
        for j in 0 to b'length loop prev(j) := j; end loop;
        for i in 1 to a'length loop
            cur(0) := i;
            ca     := a(a'left + i - 1);
            for j in 1 to b'length loop
                cb     := b(b'left + j - 1);
                cur(j) := minimum(minimum(cur(j - 1) + 1, prev(j) + 1), prev(j - 1) + boolean'pos(ca /= cb));
            end loop;
            prev := cur;
        end loop;
        return prev(b'length);
    end function;

    type HwutRunner is protected body
        type Mode is (MODE_NORMAL, MODE_CHILD);
        variable argc_n     : natural := 0;
        variable argument   : line;
        variable title_text : line;
        variable sorted     : line_vector(0 to HWUT_RUNNER_CHOICE_MAX - 1);
        variable choice_n   : natural := 0;
        variable happy      : line_vector(0 to 31);
        variable happy_n    : natural := 0;
        variable same_f     : boolean := false;
        variable mode_now   : Mode    := MODE_NORMAL;
        variable chosen     : line;

        procedure init(argc : natural; argv1 : string; title : string) is
            -- RETURN: nothing; the runner holds the command line -- 'argc'
            --         arguments, the first 'argv1' -- and the title.
        begin
            argc_n     := argc;
            argument   := new string'(argv1);
            title_text := new string'(title);
        end procedure;

        procedure add(name : string) is
            -- RETURN: nothing; 'name' is one of the application's choices,
            --         kept in sorted order ("-": the one choice-less test).
            variable i : natural := choice_n;
        begin
            assert choice_n < HWUT_RUNNER_CHOICE_MAX severity failure;
            while i > 0 and sorted(i - 1).all > name loop
                sorted(i) := sorted(i - 1);
                i := i - 1;
            end loop;
            sorted(i) := new string'(name);
            choice_n  := choice_n + 1;
        end procedure;

        procedure add_happy(pattern : string) is
            -- RETURN: nothing; 'pattern' is one more 'HAPPY:' line of the info block.
        begin
            happy(happy_n) := new string'(pattern);
            happy_n        := happy_n + 1;
        end procedure;

        procedure set_same is
            -- RETURN: nothing; the info block carries 'SAME;'.
        begin same_f := true; end procedure;

        impure function none_f return boolean is
            -- RETURN: true, the application is choice-less ('-' its one choice).
        begin return choice_n = 1 and sorted(0).all = "-"; end function;

        impure function found_f(name : string) return boolean is
            -- RETURN: true, 'name' is one of the choices; false, else.
        begin
            for i in 0 to choice_n - 1 loop
                if sorted(i).all = name then return true; end if;
            end loop;
            return false;
        end function;

        impure function choice_list_text return string is
            -- RETURN: string, the sorted choices, ', '-joined.
            variable text : line := new string'("");
        begin
            for i in 0 to choice_n - 1 loop
                if i /= 0 then write(text, string'(", ")); end if;
                write(text, sorted(i).all);
            end loop;
            return text.all;
        end function;

        impure function info_lines return str_list is
            -- RETURN: str_list, the lines of the info block.
            variable text : line := new string'("");
        begin
            write(text, title_text.all);
            if title_text'length = 0 or title_text(title_text'right) /= ';' then write(text, string'(";")); end if;
            write(text, string'("" & LF));
            if not none_f then write(text, "CHOICES: " & choice_list_text & ";" & LF); end if;
            for i in 0 to happy_n - 1 loop write(text, "HAPPY: " & happy(i).all & ";" & LF); end loop;
            if same_f then write(text, "SAME;" & LF); end if;
            write(text, "INTERACTIVE;" & LF);
            return text.all;
        end function;

        impure function choose(name : string; how : Mode) return boolean is
            -- RETURN: true; 'name' is the choice the caller runs now.
        begin
            chosen   := new string'(name);
            mode_now := how;
            return true;
        end function;

        impure function digits_f(word : string) return boolean is
            -- RETURN: true, 'word' is one or more decimal digits; false, else.
        begin
            if word'length = 0 then return false; end if;
            for i in word'range loop
                if word(i) < '0' or word(i) > '9' then return false; end if;
            end loop;
            return true;
        end function;

        impure function choice_of_token(token : string) return string is
            -- RETURN: string, the choice 'token' names -- by name, by its
            --         decimal index into the sorted list, or '-' for the
            --         choice-less test; "" where it names none.
            variable i : integer;
        begin
            if found_f(token) then return token; end if;
            if digits_f(token) and token'length < 9 then
                i := integer'value(token);
                if i < choice_n then return sorted(i).all; end if;
            end if;
            return "";
        end function;

        impure function interactive return boolean is
            -- RETURN: true in the child made for a 'run' command -- the
            --         caller runs 'choice' there; never else: the session
            --         ends the process once it ended ('quit' or end of input).
            variable l      : line;
            variable field  : line_vector(0 to 4);
            variable n, i   : natural;
            variable status : integer;
            variable lines  : line;
        begin
            interactive_begin;
            while not endfile(input) loop
                readline(input, l);
                --  THE FIELDS: words between blanks and tabs, five at most
                n := 0; i := l'left;
                while i <= l'right and n < 5 loop
                    while i <= l'right and (l(i) = ' ' or l(i) = HT or l(i) = CR) loop i := i + 1; end loop;
                    exit when i > l'right;
                    field(n) := new string'("");
                    while i <= l'right and l(i) /= ' ' and l(i) /= HT and l(i) /= CR loop
                        write(field(n), l(i to i)); i := i + 1;
                    end loop;
                    n := n + 1;
                end loop;
                if n = 0 then
                    next;
                elsif n = 1 and (field(0).all = "quit" or field(0).all = "q" or field(0).all = "exit") then
                    exit;
                elsif n = 1 and field(0).all = "info" then
                    lines := new string'(info_lines);
                    for k in 0 to item_n(lines.all) - 1 loop up("info: " & item(lines.all, k)); end loop;
                    up("done - 0");
                elsif n = 4 and field(0).all = "run" then
                    if choice_of_token(field(1).all) = "" then
                        up("fail " & field(1).all & " unknown-choice");
                    else
                        status := run_into_sinks(field(2).all, field(3).all);
                        if status = RUN_IN_CHILD then
                            return choose(choice_of_token(field(1).all), MODE_CHILD);
                        end if;
                        up("done " & field(1).all & " " & integer'image(status));
                    end if;
                else
                    up("fail - bad-command");
                end if;
            end loop;
            up("bye");
            process_exit(0);
            return false;
        end function;

        impure function dispatch return boolean is
            -- RETURN: true, the caller runs the choice 'choice' names now and
            --         calls 'choice_done' after it; never else: the mode the
            --         command line selects is done, and the process ended --
            --         0 for the info block and a session, 1 for a refusal.
            constant word   : string := argument.all;
            variable info   : line;
            variable best   : line;
            variable best_d : integer := -1;
        begin
            if argc_n = 0 then
                if none_f then return choose("-", MODE_NORMAL); end if;
                print("error: a choice is required: " & choice_list_text
                      & " -- name one, or let 'hwut.play' ask.");
                process_exit(1);
            end if;
            if word = "-h" or word = "--hi" or word = "--hwut-info" or word = "--sos" or word = "--wtf" then
                info := new string'(info_lines);
                print(info(1 to info'length - 1));
                process_exit(0);
            end if;
            if word = "--interactive" then return interactive; end if;
            if found_f(word) then return choose(word, MODE_NORMAL); end if;
            if none_f then
                print("error: '" & word & "': this application has no choices -- call it without one.");
                process_exit(1);
            end if;
            print("error: choice '" & word & "' not available.");
            print("error: available: " & choice_list_text & ".");
            for i in 0 to choice_n - 1 loop
                if best_d < 0 or levenshtein_distance(word, sorted(i).all) < best_d then
                    best_d := levenshtein_distance(word, sorted(i).all);
                    best   := sorted(i);
                end if;
            end loop;
            if best /= null then print("error: did you mean '" & best.all & "'?"); end if;
            process_exit(1);
            return false;
        end function;

        impure function choice return string is
            -- RETURN: string, the choice 'dispatch' gave to run.
        begin return chosen.all; end function;

        procedure choice_done is
            -- RETURN: never; the choice ran: '<hwut-end>' is said (R-70) --
            --         in a session's child unless HWUT_NO_TERMINAL is set, a
            --         canonicaliser then owning stdout -- and the process ends 0.
        begin
            if mode_now = MODE_NORMAL or not getenv_f("HWUT_NO_TERMINAL") then
                print("<hwut-end>");
            end if;
            process_exit(0);
        end procedure;
    end protected body;
end package body;
