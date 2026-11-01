-- @hwut {
--     title   = "Demo: what hwut tolerates, and where it is said"
--     build   { framework = "make", executable = "%.exe" }
--     choices {
--         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
--         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
--                       tolerance {
--                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
--                           numeric_ratio = 0.01
--                       } }
--         constraints { features = ["demo-passes-on-every-run", "constraints"]
--                       tolerance {
--                           constraints = ["load >= 0 and load <= 100",
--                                          "even % 2 == 0",
--                                          "twice == 2 * once"]
--                       } }
--         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
--         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
--         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
--         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
--                       tolerance { nothing = ["[.]+"] } }
--         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
--                       tolerance { analogy = ["{", "}"] } }
--         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
--     }
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- A TEST APPLICATION OF HWUT, FOR READING -- the template, in VHDL.
--
--     hwut.run                   builds 'demo.exe' (by 'Makefile', as the
--                                header's 'build' says), runs every choice
--                                below, compares with GOOD/
--     hwut.play demo.vhd plain   runs one choice and records it in OUT/
--     hwut.accept demo.vhd plain blesses that recording as GOOD
--     hwut.config.show demo.vhd  prints what hwut READ from the header above
--
-- The header above is the whole configuration: a title, how the program is
-- built, and one scope per choice. hwut calls 'demo.exe <choice>' and
-- compares what it prints on stdout with 'GOOD/demo.vhd--<choice>.txt' -- a
-- '.link' to the Python demonstration's GOOD: the VHDL program prints the
-- same. '<hwut-end>' closes the stream.
--
-- Every run is seeded by the clock, so the output differs from run to run --
-- and every choice passes anyway. What each choice shows, and why it passes,
-- is the Python demonstration's ('../../python/TEST/demo.py'): the
-- tolerances live in the header, not in the language.
--
-- THE THREADS OF PYTHON ARE PROCESSES HERE. 'race' and 'pool' run their
-- workers as VHDL processes that wait a drawn time -- of the SIMULATION --
-- and the simulator wakes them in the order of their times: the order is
-- the draw's, as the scheduler's is in Python.
-- _____________________________________________________________________________
library ieee;
use ieee.math_real.all;
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.demo_vhpi.all;

entity demo is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture test of demo is
    constant GREETING : str_list := "hello" & LF & "bonjour" & LF & "hallo" & LF & "buongiorno" & LF
                                    & "hola" & LF & "ahoj" & LF;
    constant CHOICES  : string   := "plain, tolerance, constraints, analogies, race, pool, progress, lisp, clusters";

    --  WHAT THE WORKERS SHARE: a queue of jobs, the lines done, who ended.
    type WorkBoard is protected
        procedure fill(n : natural);
        impure function take return boolean;
        procedure done(text : string);
        impure function done_line(i : natural) return string;
        impure function done_n return natural;
        procedure finished;
        impure function finished_n return natural;
    end protected;

    type WorkBoard is protected body
        variable job_n      : natural := 0;
        variable lines      : line_vector(0 to 63);
        variable line_n     : natural := 0;
        variable finished_k : natural := 0;
        procedure fill(n : natural) is
            -- RETURN: nothing; 'n' jobs wait in the queue.
        begin job_n := n; end procedure;
        impure function take return boolean is
            -- RETURN: true, a job was taken from the queue; false, it is empty.
        begin
            if job_n = 0 then return false; end if;
            job_n := job_n - 1;
            return true;
        end function;
        procedure done(text : string) is
            -- RETURN: nothing; 'text' is the next line done.
        begin lines(line_n) := new string'(text); line_n := line_n + 1; end procedure;
        impure function done_line(i : natural) return string is
            -- RETURN: string, the line done 'i'-th (from 0).
        begin return lines(i).all; end function;
        impure function done_n return natural is
            -- RETURN: natural, the number of lines done.
        begin return line_n; end function;
        procedure finished is
            -- RETURN: nothing; one more worker ended.
        begin finished_k := finished_k + 1; end procedure;
        impure function finished_n return natural is
            -- RETURN: natural, the number of workers that ended.
        begin return finished_k; end function;
    end protected body;

    shared variable rng   : ClockRandom;
    shared variable board : WorkBoard;
    signal race_go, pool_go : boolean := false;

    procedure plain is
        -- RETURN: nothing; prints what never varies.
    begin
        print("the first line");
        print("the second line: 1 2 3");
    end procedure;

    procedure tolerance is
        -- RETURN: nothing; prints a greeting and a value, both drawn at random.
    begin
        print("greeting: " & item(GREETING, rng.randint(0, 5)) & ", world");
        print("value:    " & to_string(rng.uniform(19.91, 20.09), "%.2f"));
    end procedure;

    procedure constraints is
        -- RETURN: nothing; prints bindings, each drawn at random, each lawful.
        variable once : integer;
    begin
        print("load  ((load: " & to_string(rng.uniform(0.0, 100.0), "%.1f") & ")) %");
        print("even  ((even: " & integer'image(2 * rng.randint(0, 500)) & "))");
        once := rng.randint(1, 50);
        print("once  ((once: " & integer'image(once) & "))");
        print("twice ((twice: " & integer'image(2 * once) & "))");
    end procedure;

    procedure analogies is
        -- RETURN: nothing; prints two handles, each drawn at random, each used
        --         consistently from opening to closing.
        variable first, second : natural;
    begin
        first := rng.randint(16#1000#, 16#FFFF#);
        loop
            second := rng.randint(16#1000#, 16#FFFF#);
            exit when second /= first;
        end loop;
        print("open  ((" & hex(first, 4) & ")) input.txt");
        print("open  ((" & hex(second, 4) & ")) output.txt");
        print("read  ((" & hex(first, 4) & ")) 17 lines");
        print("write ((" & hex(second, 4) & ")) 17 lines");
        print("close ((" & hex(first, 4) & "))");
        print("close ((" & hex(second, 4) & "))");
    end procedure;

    procedure progress is
        -- RETURN: nothing; a download that prints dots while it waits; how
        --         many is the network's.
        variable dots : line;
    begin
        print("connecting to mirror");
        for i in 1 to rng.randint(0, 3) loop
            dots := new string'("");
            for j in 1 to rng.randint(1, 8) loop dots := new string'(dots.all & '.'); end loop;
            print(dots.all);
        end loop;
        print("connected");
        print("received 1024 bytes");
    end procedure;

    impure function address return string is
        -- RETURN: string, an address of the Lisp heap, 16#1000000000# ..
        --         16#10FFFFFFFF#, in upper-case hexadecimal.
    begin return "10" & hex(rng.randint(0, 16#FFFF#), 4, true) & hex(rng.randint(0, 16#FFFF#), 4, true); end function;

    procedure lisp is
        -- RETURN: nothing; a Lisp session at its prompt: two objects, each
        --         printed with its address '{...}', drawn anew per run, and
        --         each used again.
        constant table  : string := address;
        variable thread : line   := new string'(address);
    begin
        while thread.all = table loop thread := new string'(address); end loop;
        print("* (defvar *cache* (make-hash-table))");
        print("#<HASH-TABLE :TEST EQL :COUNT 0 {" & table & "}>");
        print("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name ""worker""))");
        print("#<THREAD ""worker"" RUNNING {" & thread.all & "}>");
        print("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))");
        print("#<THREAD ""worker"" RUNNING {" & thread.all & "}>");
        print("* *cache*");
        print("#<HASH-TABLE :TEST EQL :COUNT 1 {" & table & "}>");
    end procedure;

    procedure clusters is
        -- RETURN: nothing; clusters 90 noisy points around three centres and
        --         prints the centroids in the order the run found them.
        type real_vector is array (natural range <>) of real;
        constant CX : real_vector(0 to 2) := (1.0, 5.0, 9.0);
        constant CY : real_vector(0 to 2) := (1.0, 4.0, 1.0);
        variable px, py, qx, qy : real_vector(0 to 89);
        variable order          : integer_vector(0 to 89);
        variable mx, my         : real_vector(0 to 2);
        variable sx, sy         : real_vector(0 to 2);
        variable count          : integer_vector(0 to 2);
        variable k, best, nearest : integer;
        variable d, d_min, far  : real;
    begin
        for c in 0 to 2 loop
            for i in 0 to 29 loop
                qx(30 * c + i) := CX(c) + rng.gauss(0.0, 0.3);
                qy(30 * c + i) := CY(c) + rng.gauss(0.0, 0.3);
            end loop;
        end loop;
        order := rng.permutation(90);
        for i in 0 to 89 loop px(i) := qx(order(i)); py(i) := qy(order(i)); end loop;
        --  The start: one point at random, then twice the point farthest
        --  from every start chosen so far -- one start per cluster.
        k := rng.randint(0, 89);
        mx(0) := px(k); my(0) := py(k);
        for n in 1 to 2 loop
            far := -1.0; best := 0;
            for i in 0 to 89 loop
                d_min := real'high;
                for c in 0 to n - 1 loop
                    d := (px(i) - mx(c)) ** 2 + (py(i) - my(c)) ** 2;
                    if d < d_min then d_min := d; end if;
                end loop;
                if d_min > far then far := d_min; best := i; end if;
            end loop;
            mx(n) := px(best); my(n) := py(best);
        end loop;
        for round in 1 to 10 loop
            sx := (others => 0.0); sy := (others => 0.0); count := (others => 0);
            for i in 0 to 89 loop
                nearest := 0; d_min := real'high;
                for c in 0 to 2 loop
                    d := (px(i) - mx(c)) ** 2 + (py(i) - my(c)) ** 2;
                    if d < d_min then d_min := d; nearest := c; end if;
                end loop;
                sx(nearest) := sx(nearest) + px(i); sy(nearest) := sy(nearest) + py(i);
                count(nearest) := count(nearest) + 1;
            end loop;
            for c in 0 to 2 loop
                mx(c) := sx(c) / real(count(c)); my(c) := sy(c) / real(count(c));
            end loop;
        end loop;
        print("centroids (x y), in the order found:");
        print("##! point-cloud limit=0.3 pair dist=Linf");
        for c in 0 to 2 loop
            print("    " & to_string(mx(c), "%5.2f") & " " & to_string(my(c), "%5.2f"));
        end loop;
        print("####");
    end procedure;
begin
    main : process
        constant choice : string := HWUT_ARGV1;
    begin
        rng.init;
        if    choice = "plain"       then plain;
        elsif choice = "tolerance"   then tolerance;
        elsif choice = "constraints" then constraints;
        elsif choice = "analogies"   then analogies;
        elsif choice = "progress"    then progress;
        elsif choice = "lisp"        then lisp;
        elsif choice = "clusters"    then clusters;
        elsif choice = "race" then
            --  Three workers print as they finish; the order is the draw's,
            --  the facts are not. The program frames the unordered block
            --  itself: '##! potpourri' ... '####'.
            print("start");
            print("##! potpourri");
            race_go <= true;
            while board.finished_n < 3 loop wait for 1 ms; end loop;
            print("####");
            print("all joined");
        elsif choice = "pool" then
            --  Four workers take twelve jobs from one queue; each reports
            --  the job it finished. Who takes how many is the draw's.
            board.fill(12);
            pool_go <= true;
            wait for 0 ns;
            while board.finished_n < 4 loop wait for 1 ms; end loop;
            print("twelve jobs, four workers:");
            print("##! potpourri subset duplicates");
            for i in 0 to board.done_n - 1 loop print(board.done_line(i)); end loop;
            print("####");
            print("jobs done: " & integer'image(board.done_n));
        else
            print("choices: " & CHOICES);
            process_exit(1);
        end if;
        print("<hwut-end>");
        wait;
    end process;

    race_workers : for w in 0 to 2 generate
        constant NAME : string(1 to 1)      := (1 => character'val(character'pos('A') + w));
        constant JOBS : integer_vector(0 to 2) := (3, 5, 2);
    begin
        worker : process
        begin
            wait until race_go;
            wait for rng.uniform(0.0, 20.0) * 1 ms;
            print("worker " & NAME & " done: " & integer'image(JOBS(w)) & " jobs");
            board.finished;
            wait;
        end process;
    end generate;

    pool_workers : for w in 0 to 3 generate
        constant NAME : string(1 to 1) := (1 => character'val(character'pos('A') + w));
    begin
        worker : process
        begin
            wait until pool_go;
            while board.take loop
                wait for rng.uniform(0.0, 5.0) * 1 ms;
                board.done("job done by worker " & NAME);
            end loop;
            board.finished;
            wait;
        end process;
    end generate;
end architecture;
