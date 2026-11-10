-- @hwut {
--     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
--     build    { framework = "make", target = "%.exe" }
--     interactive = true
--     choices {
--         space       { features = ["demo-vhdl+cover-space-from-hocon", "demo-vhdl+cover-space-iterator", "demo-vhdl+cover-hwut-runner"]
--                       tolerance { constraints = ["mismatches == 0"] } }
--         random      { features = ["demo-vhdl+cover-deterministic-stream", "demo-vhdl+cover-hwut-runner"]
--                       tolerance { constraints = ["mismatches == 0"] } }
--         race-naive  { features = ["demo-vhdl+cover-deterministic-timeline", "demo-vhdl+cover-space-iterator", "demo-vhdl+cover-hwut-runner"]
--                       tolerance { constraints = ["overbooked > 0"] } }
--         race-atomic { features = ["demo-vhdl+cover-deterministic-timeline", "demo-vhdl+cover-space-iterator", "demo-vhdl+cover-hwut-runner"]
--                       tolerance { constraints = ["overbooked == 0"] } }
--     }
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- SUBJECT  the counter of free spaces at a garage's gates: which cars it
--          admits, which it refuses, and how many stand inside.
-- REQUIREMENT  The garage admits a car only while a space is free, lets a car
--              out only while one stands inside, and never holds more cars
--              than it has spaces -- also when two gates admit at once.
--
-- No choice writes its cases out by hand. Each GENERATES them, with one of
-- hwut's helpers for writing tests, in VHDL (support/test_writing/vhdl):
--
-- space        'garage-space.hocon' states the tested space, read by
--              'hwut_hocon'; 'SpaceIterator' walks every combination:
--              3 x 5 x 4 = 60 cases, checked against the model.
-- random       'DeterministicStream' seeded 4711 draws 1000 cars. The draw is
--              the same in every language hwut supports, so the GOOD is
--              exact -- this program's is the Python program's.
-- race-naive   two gates, one free space, on timelines drawn as strings
--              ('deterministic_timeline'); a gate checks, and later admits.
--              All six interleavings of four ticks; where both check first,
--              both admit: 'overbooked > 0' -- the GOOD is the accepted
--              violation report.
-- race-atomic  the same, the gate checking and admitting in ONE step.
--
-- THE FRONT END is the support's 'HwutRunner': the choices below are the
-- whole command line, '--hwut-info' included. 'interactive = true': hwut
-- starts the application ONCE and asks for the choices one after another.
--
-- A GATE IS A TRIGGER OF KIND 'GATE_NAIVE' OR 'GATE_ATOMIC' -- VHDL's
-- 'class Gate(Trigger)': its 'fire' is 'gate_fire', a generic subprogram of
-- the instance 'timeline' of 'deterministic_timeline_run'.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.hwut_runner.all;
use work.hwut_hocon.all;
use work.space_iterator.all;
use work.deterministic_random.all;
use work.deterministic_timeline.all;

entity garage is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture test of garage is
    --  THE UNIT UNDER TEST: a counter of the spaces a garage has.
    type Garage is protected
        procedure init(capacity_n : natural);
        impure function capacity return natural;
        impure function occupied return integer;
        impure function free return integer;
        impure function arrive return boolean;
        impure function leave return boolean;
        procedure admit_naively;
    end protected;

    type Garage is protected body
        variable capacity_k : natural := 0;
        variable occupied_k : integer := 0;
        procedure init(capacity_n : natural) is
            -- RETURN: nothing; an empty garage of 'capacity_n' spaces.
        begin capacity_k := capacity_n; occupied_k := 0; end procedure;
        impure function capacity return natural is
            -- RETURN: natural, the spaces the garage has.
        begin return capacity_k; end function;
        impure function occupied return integer is
            -- RETURN: integer, the cars inside.
        begin return occupied_k; end function;
        impure function free return integer is
            -- RETURN: integer, the spaces free now -- negative where the
            --         garage is overbooked.
        begin return capacity_k - occupied_k; end function;
        impure function arrive return boolean is
            -- RETURN: true, a car was admitted, if a space was free;
            --         false, else (the car is refused).
        begin
            if capacity_k - occupied_k <= 0 then return false; end if;
            occupied_k := occupied_k + 1;
            return true;
        end function;
        impure function leave return boolean is
            -- RETURN: true, a car drove out, if one stood inside;
            --         false, else.
        begin
            if occupied_k = 0 then return false; end if;
            occupied_k := occupied_k - 1;
            return true;
        end function;
        procedure admit_naively is
            -- RETURN: nothing; one car more inside, free or not.
        begin occupied_k := occupied_k + 1; end procedure;
    end protected body;

    function rstrip(text : string) return string is
        -- RETURN: string, 'text' without its trailing blanks.
        variable n : integer := text'right;
    begin
        while n >= text'left and text(n) = ' ' loop n := n - 1; end loop;
        return text(text'left to n);
    end function;

    function image(value : integer) return string is
        -- RETURN: string, Python's '%d' of 'value'.
    begin return integer'image(value); end function;

    -- _________________________________________________________________________
    -- space -- the tested space from HOCON, walked by SpaceIterator
    --
    impure function file_lines(path : string) return str_list is
        -- RETURN: str_list, the lines of the file 'path', each ended by LF.
        file     f    : text open read_mode is path;
        variable l    : line;
        variable text : line := new string'("");
    begin
        while not endfile(f) loop
            readline(f, l);
            text := new string'(text.all & l.all & LF);
        end loop;
        return text.all;
    end function;

    procedure run_space is
        -- RETURN: nothing; prints every case of the space as a matrix cell.
        variable document, space, dimension : HoconNodeAccess;
        variable faults     : HoconFaultVectorAccess;
        variable it         : SpaceIterator;
        variable g          : Garage;
        variable value      : integer_vector(0 to 3 * 16 - 1);    -- 3 dimensions of up to 16 values
        variable size       : integer_vector(0 to 2);
        variable point      : integer_vector(0 to 2);
        variable cell       : line_vector(0 to 3 * 16 * 16 - 1);  -- (capacity, arriving) -> its cells
        variable heading    : line := new string'("");
        variable row        : line;
        variable refused, admitted, expected_in, expected_out : integer;
        variable mismatch_n : natural := 0;
        variable ok         : boolean;
        variable cap_i, arr_i : natural;
        impure function v(dim : natural; i : natural) return integer is
            -- RETURN: integer, the value 'i' of dimension 'dim'.
        begin return value(dim * 16 + i); end function;
        impure function key(cap : natural; arr : natural) return natural is
            -- RETURN: natural, the cell row of capacity index 'cap', arriving index 'arr'.
        begin return cap * 16 + arr; end function;
        impure function values_of(dim : natural) return integer_vector is
            -- RETURN: integer_vector, the values of dimension 'dim'.
            variable result : integer_vector(0 to size(dim) - 1);
        begin
            for i in result'range loop result(i) := v(dim, i); end loop;
            return result;
        end function;
    begin
        parse(file_lines(HERE & "/garage-space.hocon"), "garage-space.hocon", document, faults);
        for i in faults'range loop print("!! " & faults(i).text.all); end loop;
        get(document, "space", space);
        for d in 0 to 2 loop
            dimension := space.entry(d).node;
            size(d)   := dimension.item'length;
            for i in 0 to size(d) - 1 loop
                value(d * 16 + i) := integer'value(dimension.item(dimension.item'left + i).value.all);
            end loop;
            if d /= 0 then heading := new string'(heading.all & "  x  "); end if;
            heading := new string'(heading.all & space.entry(d).key.all & " " & list_repr(values_of(d)));
        end loop;
        print("space: " & heading.all);
        print("cell: cars inside / cars refused at the gate ('!!' differs from the model)");
        it.do(size);
        while it.next_point loop
            point := it.point;
            g.init(v(0, point(0)));
            refused := 0;
            for i in 1 to v(1, point(1)) loop
                if not g.arrive then refused := refused + 1; end if;
            end loop;
            for i in 1 to v(2, point(2)) loop ok := g.leave; end loop;
            admitted     := minimum(v(1, point(1)), v(0, point(0)));
            expected_in  := admitted - minimum(v(2, point(2)), admitted);
            expected_out := v(1, point(1)) - admitted;
            row := new string'(image(g.occupied) & "/" & image(refused));
            if g.occupied = expected_in and refused = expected_out then
                row := new string'(row.all & "  ");
            else
                row := new string'(row.all & "!!");
                mismatch_n := mismatch_n + 1;
            end if;
            if cell(key(point(0), point(1))) = null then cell(key(point(0), point(1))) := new string'(""); end if;
            if cell(key(point(0), point(1))).all /= "" then
                cell(key(point(0), point(1))) := new string'(cell(key(point(0), point(1))).all & "  ");
            end if;
            cell(key(point(0), point(1))) := new string'(cell(key(point(0), point(1))).all & ljust(row.all, 9));
        end loop;
        for cap_i in 0 to size(0) - 1 loop
            row := new string'("");
            for l in 0 to size(2) - 1 loop
                if l /= 0 then row := new string'(row.all & "  "); end if;
                row := new string'(row.all & "leave " & ljust(image(v(2, l)), 3));
            end loop;
            print("capacity " & image(v(0, cap_i)) & "   " & rstrip(row.all));
            for arr_i in 0 to size(1) - 1 loop
                print(rstrip("  arrive " & image(v(1, arr_i)) & "   " & cell(key(cap_i, arr_i)).all));
            end loop;
        end loop;
        print("cases " & image(size(0) * size(1) * size(2)) & ", differing from the model ((mismatches: "
              & image(mismatch_n) & "))");
        free(document);
        free(faults);
    end procedure;

    -- _________________________________________________________________________
    -- random -- a deterministic stream of arrivals and departures
    --
    procedure run_random is
        -- RETURN: nothing; prints the summary of 1000 drawn cars, model-checked.
        variable stream    : DeterministicStream;
        variable g         : Garage;
        variable model     : integer := 0;
        variable arrive_n, refused_n, leave_n, empty_n : natural := 0;
        variable histogram : integer_vector(0 to 5) := (others => 0);
        variable mismatch_n : natural := 0;
        variable strip     : string(1 to 60);
    begin
        stream.init(4711);
        g.init(5);
        for i in 0 to 999 loop
            if stream.coin(0.55) then
                arrive_n := arrive_n + 1;
                if not g.arrive then refused_n := refused_n + 1; end if;
                model := minimum(5, model + 1);
                if i < 60 then strip(i + 1) := '+'; end if;
            else
                leave_n := leave_n + 1;
                if not g.leave then empty_n := empty_n + 1; end if;
                model := maximum(0, model - 1);
                if i < 60 then strip(i + 1) := '-'; end if;
            end if;
            if g.occupied /= model then mismatch_n := mismatch_n + 1; end if;
            histogram(g.occupied) := histogram(g.occupied) + 1;
        end loop;
        print("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves");
        print("first 60: " & strip);
        print("arrivals " & image(arrive_n) & ", refused " & image(refused_n) & "; departures "
              & image(leave_n) & ", from an empty garage " & image(empty_n));
        print("cars inside after each event:");
        for n in histogram'range loop
            print("    " & image(n) & "  " & rjust(image(histogram(n)), 4) & "  "
                  & (1 to histogram(n) / 10 => '#'));
        end loop;
        print("steps differing from the model ((mismatches: " & image(mismatch_n) & "))");
    end procedure;

    -- _________________________________________________________________________
    -- race -- two gates on drawn timelines
    --
    constant GATE_NAIVE  : integer := 1;     -- checks, then admits: two steps
    constant GATE_ATOMIC : integer := 2;     -- checks and admits in one step

    --  WHAT A GATE HOLDS -- Gate's own members, per trigger -- and the log.
    type GateBoard is protected
        procedure reset;
        impure function step(gate : natural) return natural;
        procedure stepped(gate : natural);
        impure function saw_free(gate : natural) return boolean;
        procedure set_saw_free(gate : natural; value : boolean);
        procedure log(text : string);
        impure function log_text return string;
    end protected;

    type GateBoard is protected body
        variable step_of     : integer_vector(0 to 1);
        variable saw_free_of : boolean_vector(0 to 1);
        variable log_line    : line := new string'("");
        procedure reset is
            -- RETURN: nothing; both gates at their first step, the log empty.
        begin step_of := (0, 0); saw_free_of := (false, false); log_line := new string'(""); end procedure;
        impure function step(gate : natural) return natural is
            -- RETURN: natural, the step 'gate' takes next.
        begin return step_of(gate); end function;
        procedure stepped(gate : natural) is
            -- RETURN: nothing; 'gate' took its step.
        begin step_of(gate) := step_of(gate) + 1; end procedure;
        impure function saw_free(gate : natural) return boolean is
            -- RETURN: boolean, whether 'gate' saw a space free.
        begin return saw_free_of(gate); end function;
        procedure set_saw_free(gate : natural; value : boolean) is
            -- RETURN: nothing; 'gate' saw a space free, or not.
        begin saw_free_of(gate) := value; end procedure;
        procedure log(text : string) is
            -- RETURN: nothing; 'text' is the next thing that happened.
        begin
            if log_line.all /= "" then log_line := new string'(log_line.all & ", "); end if;
            log_line := new string'(log_line.all & text);
        end procedure;
        impure function log_text return string is
            -- RETURN: string, what happened, ', '-joined.
        begin return log_line.all; end function;
    end protected body;

    shared variable lot   : Garage;
    shared variable gates : GateBoard;
    shared variable tasks : TaskLoop;
    signal          turn  : task_turn := 0;

    procedure gate_fire(variable d : inout TriggerDispatcher; trigger : natural; pseudo_time : natural) is
        -- RETURN: nothing; the gate 'trigger' performed its next step.
        constant name : string := d.name(trigger);
    begin
        if d.kind(trigger) /= GATE_NAIVE and d.kind(trigger) /= GATE_ATOMIC then
            trigger_fire(d, trigger, pseudo_time);
            return;
        end if;
        if gates.step(trigger) = 0 and d.kind(trigger) = GATE_ATOMIC then
            gates.set_saw_free(trigger, lot.arrive);
            if gates.saw_free(trigger) then gates.log(name & " checks+admits");
            else                            gates.log(name & " refuses");
            end if;
        elsif gates.step(trigger) = 0 then
            gates.set_saw_free(trigger, lot.free > 0);
            gates.log(name & " sees " & image(lot.free) & " free");
        elsif d.kind(trigger) = GATE_ATOMIC then
            if gates.saw_free(trigger) then gates.log(name & " opens");
            else                            gates.log(name & " stays shut");
            end if;
        elsif gates.saw_free(trigger) then
            lot.admit_naively;                                  -- the naive admit
            gates.log(name & " admits");
        else
            gates.log(name & " refuses");
        end if;
        gates.stepped(trigger);
    end procedure;

    package timeline is new work.deterministic_timeline_run
        generic map (fire => gate_fire, on_termination => trigger_on_termination);

    function line_of(x : natural; y : natural) return string is
        -- RETURN: string, a timeline of four ticks firing at ticks 'x' and 'y'.
        variable text : string(1 to 4) := (others => ' ');
    begin
        text(x + 1) := '1'; text(y + 1) := '1';
        return text;
    end function;

    impure function interleaving_list return str_list is
        -- RETURN: str_list, every pair of timelines in four ticks in which
        --         each of two gates fires twice, never at the same tick: gate
        --         A's and gate B's timeline, one item each, A's first.
        variable it     : SpaceIterator;
        variable p      : integer_vector(0 to 3);
        variable result : line := new string'("");
    begin
        it.do((4, 4, 4, 4));
        while it.next_point loop
            p := it.point;
            if p(0) < p(1) and p(2) < p(3) and p(0) /= p(2) and p(0) /= p(3)
               and p(1) /= p(2) and p(1) /= p(3) then
                result := new string'(result.all & line_of(p(0), p(1)) & LF & line_of(p(2), p(3)) & LF);
            end if;
        end loop;
        return result.all;
    end function;

begin
    main : process
        variable runner : HwutRunner;

        procedure run_race(kind : integer) is
            -- RETURN: nothing; plays every interleaving of two gates at one space.
            constant pairs : str_list := interleaving_list;
            variable overbooked_n : natural := 0;
            variable mark         : string(1 to 2);

            procedure play(timeline_a : string; timeline_b : string) is
                -- RETURN: nothing; the two gates ran on their timelines, at
                --         an empty garage of one space.
                variable d : TriggerDispatcher;
                variable t : natural;
            begin
                lot.init(1);
                gates.reset;
                t := d.add(timeline_a, "A", kind);
                t := d.add(timeline_b, "B", kind);
                timeline.run(d, turn, tasks, 0);
            end procedure;
        begin
            print("one free space, two gates, one car at each; timelines: a digit fires");
            print("    gate A  gate B  what happens                                    inside");
            for i in 0 to item_n(pairs) / 2 - 1 loop
                play(item(pairs, 2 * i), item(pairs, 2 * i + 1));
                mark := "  ";
                if lot.occupied > lot.capacity then mark := "!!"; overbooked_n := overbooked_n + 1; end if;
                print(rstrip("    """ & item(pairs, 2 * i) & """  """ & item(pairs, 2 * i + 1) & """  "
                             & ljust(gates.log_text, 46) & "  " & image(lot.occupied) & " " & mark));
            end loop;
            print("interleavings overbooking the garage ((overbooked: " & image(overbooked_n) & ")) of "
                  & image(item_n(pairs) / 2));
        end procedure;
    begin
        runner.init(HWUT_ARGC, HWUT_ARGV1,
                    "Demo: a garage's space counter -- a space, a stream and races, generated;");
        runner.add("space"); runner.add("random"); runner.add("race-naive"); runner.add("race-atomic");
        while runner.dispatch loop
            if    runner.choice = "space"       then run_space;
            elsif runner.choice = "random"      then run_random;
            elsif runner.choice = "race-naive"  then run_race(GATE_NAIVE);
            elsif runner.choice = "race-atomic" then run_race(GATE_ATOMIC);
            end if;
            runner.choice_done;
        end loop;
        wait;
    end process;
end architecture;
