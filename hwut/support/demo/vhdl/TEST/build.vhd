-- @hwut {
--     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
--     build   { framework = "make", executable = "%.exe" }
--     pype    = "build.pypes"
--     same    = true
--     choices = ["serial", "parallel"]
--     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
--                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
--                 "pype-quantity", "pype-anchors-globs-flush"]
--     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- SUBJECT  the log of a recursive build -- configure, then the directories
--          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
--          a pype system makes of it.
-- REQUIREMENT  A parallel build builds what the serial build builds: the same
--              sources, the same warnings, the same archives and the same
--              program, linked from the same parts.
--
-- The application only REPORTS the build as it happens, as 'make -w' would.
-- The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
-- between it and the comparison: 'normalise.pype' takes the job tag off a
-- parallel build's lines, 'build.pype' writes the summary (see their own
-- comments). The application prints no '<hwut-end>'.
--
-- 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.vhd.txt'. Serial
-- or parallel, the summary must be the same. 'choices' is a list.
--
-- A COMPILE TAKES A DRAWN TIME OF THE SIMULATION, 40 to 120 ms; the parallel
-- build's two jobs are processes, and the one whose compiles sum to less
-- prints its block first -- whichever the draw makes it.
-- _____________________________________________________________________________
library ieee;
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.demo_vhpi.all;

entity build is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture test of build is
    --  What each directory does: its sources, warnings and products.
    constant LIB     : natural := 0;
    constant PLUGINS : natural := 1;
    constant APP     : natural := 2;
    constant NO_INNER : integer := -1;

    function directory_name(d : natural) return string is
        -- RETURN: string, the name of directory 'd'.
    begin
        case d is
            when LIB     => return "lib";
            when PLUGINS => return "app/plugins";
            when others  => return "app";
        end case;
    end function;

    function sources(d : natural) return str_list is
        -- RETURN: str_list, the sources of directory 'd'.
    begin
        case d is
            when LIB     => return "lib/str.c" & LF & "lib/num.c" & LF & "lib/map.c" & LF;
            when PLUGINS => return "app/plugins/png.c" & LF & "app/plugins/svg.c" & LF;
            when others  => return "app/main.c" & LF & "app/cli.c" & LF;
        end case;
    end function;

    function warning(source : string) return string is
        -- RETURN: string, the warning compiling 'source' prints; "" for none.
    begin
        if source = "lib/num.c"         then return "lib/num.c:14:9: warning: unused variable 'n'"; end if;
        if source = "app/plugins/svg.c" then return "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"; end if;
        return "";
    end function;

    function product(d : natural) return string is
        -- RETURN: string, what building directory 'd' makes at its end.
    begin
        case d is
            when LIB     => return "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o";
            when PLUGINS => return "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o";
            when others  => return "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a";
        end case;
    end function;

    shared variable rng : ClockRandom;

    procedure add(variable block_text : inout line; text : string) is
        -- RETURN: nothing; 'text' is the next line of 'block_text' (a str_list).
    begin
        if block_text = null then block_text := new string'(""); end if;
        block_text := new string'(block_text.all & text & LF);
    end procedure;

    function object_of(source : string) return string is
        -- RETURN: string, the object file of the C file 'source'.
    begin return source(source'left to source'right - 2) & ".o"; end function;

    function spent(took : real) return string is
        -- RETURN: string, 'took' seconds as the log writes them: in ms below
        --         0.1 s (cut, as Python's '%d'), in s with two digits else.
    begin
        if took < 0.1 then return integer'image(integer(ieee.math_real.floor(took * 1000.0))) & " ms"; end if;
        return to_string(took, "%.2f") & " s";
    end function;

    procedure compile_lines(d : natural; variable block_text : inout line) is
        -- RETURN: nothing; what building directory 'd' prints stands in
        --         'block_text', its sources compiled in the time each takes.
        constant list : str_list := sources(d);
        variable took : real;
    begin
        for i in 0 to item_n(list) - 1 loop
            took := rng.uniform(0.04, 0.12);
            wait for took * 1 sec;
            add(block_text, "cc -c " & item(list, i) & " -o " & object_of(item(list, i)) & " (took " & spent(took) & ")");
            if warning(item(list, i)) /= "" then add(block_text, warning(item(list, i))); end if;
        end loop;
    end procedure;

    procedure directory_block(d : natural; level : natural; inner : integer; variable block_text : inout line) is
        -- RETURN: nothing; the block 'make -w' prints for directory 'd' at
        --         'level' stands in 'block_text', the block of 'inner' nested
        --         before the product.
    begin
        add(block_text, "make[" & integer'image(level) & "]: Entering directory '" & directory_name(d) & "'");
        compile_lines(d, block_text);
        if inner /= NO_INNER then directory_block(inner, level + 1, NO_INNER, block_text); end if;
        add(block_text, product(d));
        add(block_text, "make[" & integer'image(level) & "]: Leaving directory '" & directory_name(d) & "'");
    end procedure;

    procedure say(text : string) is
        -- RETURN: nothing; 'text' stands on stdout, flushed.
    begin print(text); flush; end procedure;

    procedure configure is
        -- RETURN: nothing; prints what 'configure' prints, and that make
        --         enters the top directory.
    begin
        say("configure: checking for cc... cc");
        say("configure: checking for ar... ar");
        say("make: Entering directory 'demo'");
    end procedure;

    type JobBoard is protected
        procedure finished;
        impure function finished_n return natural;
    end protected;
    type JobBoard is protected body
        variable n : natural := 0;
        procedure finished is
            -- RETURN: nothing; one more job is done.
        begin n := n + 1; end procedure;
        impure function finished_n return natural is
            -- RETURN: natural, the jobs done.
        begin return n; end function;
    end protected body;
    shared variable jobs : JobBoard;
    signal parallel_go : boolean := false;
begin
    main : process
        constant choice : string := HWUT_ARGV1;
        variable block_text : line;
    begin
        rng.init;
        if choice = "serial" then
            --  One directory after the other.
            configure;
            directory_block(LIB, 1, NO_INNER, block_text);
            directory_block(APP, 1, PLUGINS, block_text);
            for i in 0 to item_n(block_text.all) - 1 loop say(item(block_text.all, i)); end loop;
            say("make: Leaving directory 'demo'");
        elsif choice = "parallel" then
            --  'lib' and 'app' at once. Each job prints its block whole when
            --  done ('make -O'), every line tagged with the job.
            configure;
            parallel_go <= true;
            wait for 0 ns;
            while jobs.finished_n < 2 loop wait for 1 ms; end loop;
            say("make: Leaving directory 'demo'");
        else
            print("choices: serial, parallel");
            process_exit(1);
        end if;
        wait;
    end process;

    job : for slot in 1 to 2 generate
    begin
        worker : process
            variable block_text : line;
        begin
            wait until parallel_go;
            if slot = 1 then directory_block(LIB, 1, NO_INNER, block_text);
            else             directory_block(APP, 1, PLUGINS, block_text);
            end if;
            for i in 0 to item_n(block_text.all) - 1 loop
                say("job" & integer'image(slot) & ": " & item(block_text.all, i));
            end loop;
            jobs.finished;
            wait;
        end process;
    end generate;
end architecture;
