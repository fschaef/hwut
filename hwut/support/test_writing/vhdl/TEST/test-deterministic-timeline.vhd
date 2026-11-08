-- @hwut {
--     title      = "TriggerDispatcher: schedule, priority, and the end of time"
--     build      { framework = "make", target = "%.exe" }
--     choices {
--         abstract    { features = ["vhdl-timeline"] }
--         cancel      { features = ["vhdl-timeline"] }
--         edges       { features = ["vhdl-timeline"] }
--         priority    { features = ["vhdl-timeline"] }
--         schedule    { features = ["vhdl-timeline"] }
--         stable      { features = ["vhdl-timeline"] }
--         stop        { features = ["vhdl-timeline"] }
--         termination { features = ["vhdl-timeline"] }
--         yielding    { features = ["vhdl-timeline"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The VHDL port of 'python/TEST/test-deterministic-timeline.py',
--          choice for choice, held against its GOOD files by '.link'. The
--          trigger classes are kinds, their methods the generic subprograms of
--          'timeline'; where Python runs two coroutines, two processes take
--          turns ('run_task', 'consume_task').
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_runner.all;
use work.hwut_pytext.all;
use work.deterministic_timeline.all;

entity test_deterministic_timeline is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
end entity;

architecture test of test_deterministic_timeline is
    --  THE TRIGGER CLASSES of the Python test
    constant K_SPEAKING  : integer := 1;      -- SpeakingTrigger
    constant K_MUTE      : integer := 2;      -- MuteTrigger: no on_termination of its own
    constant K_PRODUCING : integer := 3;      -- ProducingTrigger ('yielding')
    constant K_STOPPING  : integer := 4;      -- StoppingTrigger ('stop')
    --  TRIGGER_BASE is Python's 'Trigger' itself -- the BareTrigger.

    --  THE TASKS beside the main process (task 0)
    constant RUN_TASK_ID     : natural := 1;
    constant CONSUME_TASK_ID : natural := 2;

    --  WHAT THE PRODUCER HOLDS -- ProducingTrigger's own members
    type ProducerState is protected
        procedure put(text : string);
        procedure take;
        impure function item return string;
        impure function has_item_f return boolean;
        procedure finish;
        impure function finished return boolean;
    end protected;

    type ProducerState is protected body
        variable item_text  : line;
        variable finished_f : boolean := false;
        procedure put(text : string) is begin item_text := new string'(text); end procedure;
        procedure take is begin deallocate(item_text); end procedure;
        impure function item return string is begin return item_text.all; end function;
        impure function has_item_f return boolean is begin return item_text /= null; end function;
        procedure finish is begin finished_f := true; end procedure;
        impure function finished return boolean is begin return finished_f; end function;
    end protected body;

    shared variable producer   : ProducerState;
    shared variable tasks      : TaskLoop;
    shared variable dispatcher : TriggerDispatcher;     -- the one 'run_task' runs
    signal          turn       : task_turn := 0;

    procedure test_fire(variable d : inout TriggerDispatcher; trigger : natural; pseudo_time : natural) is
        constant at_text : string := "  [t:" & integer'image(pseudo_time) & "] " & d.name(trigger);
    begin
        case d.kind(trigger) is
            when K_SPEAKING | K_MUTE =>
                print(at_text & " fires");
            when K_STOPPING =>
                print(at_text & " fires");
                print("  ... asks the dispatcher to stop");
                d.stop;
            when K_PRODUCING =>
                producer.put("item@" & integer'image(pseudo_time));
                print(at_text & " prepared " & producer.item);
            when others =>
                trigger_fire(d, trigger, pseudo_time);
        end case;
    end procedure;

    procedure test_on_termination(variable d : inout TriggerDispatcher; trigger : natural; end_tick : natural) is
        constant end_text : string := "  [end:" & integer'image(end_tick) & "] " & d.name(trigger);
    begin
        case d.kind(trigger) is
            when K_SPEAKING | K_STOPPING =>
                print(end_text & " notified");
            when K_PRODUCING =>
                producer.finish;
                print(end_text & " announced end-of-stream");
            when others =>
                trigger_on_termination(d, trigger, end_tick);
        end case;
    end procedure;

    package timeline is new work.deterministic_timeline_run
        generic map (fire => test_fire, on_termination => test_on_termination);

    procedure banner(label_text : string) is
    begin print(""); print("--- " & label_text & " ---"); end procedure;

    procedure setup(variable d : inout TriggerDispatcher; name : string; line_text : string;
                       kind : integer := K_SPEAKING) is
        -- RETURN: nothing; a trigger of 'kind' stands in 'd' and said so.
        variable t : natural;
    begin
        t := d.add(line_text, name, kind);
        if kind = K_MUTE then print("SETUP: " & ljust(name, 7) & " |" & line_text & "|  (no on_termination override)");
        else                print("SETUP: " & ljust(name, 7) & " |" & line_text & "|");
        end if;
    end procedure;
begin
    main : process
        variable runner : HwutRunner;

        procedure dispatch(variable d : inout TriggerDispatcher) is
            -- RETURN: nothing; 'd' ran to completion, in the main task.
        begin timeline.run(d, turn, tasks, 0); end procedure;

        procedure run_schedule is
            variable d1, d2, d3 : TriggerDispatcher;
        begin
            banner("staggered: A at 0, B at 2, C at 4");
            setup(d1, "A", "1    "); setup(d1, "B", "  1  "); setup(d1, "C", "    1");
            dispatch(d1);
            banner("a SHORT timeline stops contributing; the long one goes on");
            setup(d2, "SHORT", "11"); setup(d2, "LONG", "111111");
            dispatch(d2);
            banner("the SCHEDULE as built -- '[tick] (priority)name'");
            setup(d3, "A", "12"); setup(d3, "B", "21");
            print(d3.image);
        end procedure;

        procedure run_priority is
            variable d1, d2 : TriggerDispatcher;
        begin
            banner("digits swap between ticks: B leads at 0, A leads at 1");
            setup(d1, "A", "21"); setup(d1, "B", "12");
            dispatch(d1);
            banner("0 is the strongest digit, 9 the weakest");
            setup(d2, "WEAK", "9"); setup(d2, "STRONG", "0");
            dispatch(d2);
        end procedure;

        procedure run_stable is
            variable d1, d2 : TriggerDispatcher;
        begin
            banner("three triggers, all digit 1 at tick 0");
            setup(d1, "first", "1"); setup(d1, "second", "1"); setup(d1, "third", "1");
            dispatch(d1);
            banner("registered BACKWARDS -- the order follows registration, not the name");
            setup(d2, "third", "1"); setup(d2, "second", "1"); setup(d2, "first", "1");
            dispatch(d2);
        end procedure;

        procedure run_termination is
            variable d1, d2, d3, d4 : TriggerDispatcher;
        begin
            banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0");
            setup(d1, "EARLY", "1    ");
            dispatch(d1);
            banner("a trigger that NEVER fires is notified all the same");
            setup(d2, "FIRES", "1  "); setup(d2, "SILENT", "   ");
            dispatch(d2);
            banner("the LONGEST timeline sets end_tick for everybody");
            setup(d3, "SHORT", "1"); setup(d3, "LONG", "1      ");
            dispatch(d3);
            banner("a trigger that does not override is simply silent at the end");
            setup(d4, "SPEAKS", "1 "); setup(d4, "MUTE", "1 ", K_MUTE);
            dispatch(d4);
        end procedure;

        procedure run_yielding is
            variable t : natural;
        begin
            banner("producer fires at every tick; consumer waits between them");
            t := dispatcher.add("111", "PROD", K_PRODUCING);
            print("SETUP: " & ljust("PROD", 7) & " |111|");
            task_gather(turn, tasks, 0, (RUN_TASK_ID, CONSUME_TASK_ID));
            print("");
            print("Each item was taken BEFORE the next tick prepared one: the run yields.");
        end procedure;

        procedure run_stop is
            variable d : TriggerDispatcher;
        begin
            banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes");
            setup(d, "STOPPER", "1111", K_STOPPING);
            setup(d, "OTHER",   "1111");
            dispatch(d);
            print("");
            print("end_tick is still the timeline's length, not the tick the run stopped at.");
        end procedure;

        procedure run_cancel is
        begin
            banner("cancel() the task carrying run() -- no announcement follows");
            setup(dispatcher, "A", "1111111111");
            task_create(tasks, RUN_TASK_ID);
            task_yield(turn, tasks, 0);                     -- one tick passes
            tasks.cancel(RUN_TASK_ID);
            task_await(turn, tasks, 0, RUN_TASK_ID);
            if tasks.cancelled_f(RUN_TASK_ID) then print("  run() was cancelled"); end if;
            print("");
            print("No '[end:..]' line above: the triggers were abandoned, not ended.");
        end procedure;

        procedure run_edges is
            variable d1, d2, d3, d4 : TriggerDispatcher;
        begin
            banner("an EMPTY timeline -- end_tick 0");
            setup(d1, "EMPTY", "");
            dispatch(d1);
            banner("a timeline of BLANKS -- no digit, so nothing fires");
            setup(d2, "BLANK", "    ");
            dispatch(d2);
            banner("NO TRIGGERS at all -- nothing to announce, and no failure");
            dispatch(d3);
            print("  (dispatcher ran; nothing was scheduled)");
            banner("a timeline of blanks beside one that fires");
            setup(d4, "BLANK", "   "); setup(d4, "FIRES", " 1 ");
            dispatch(d4);
        end procedure;

        procedure run_abstract is
            variable d1, d2, d3 : TriggerDispatcher;
            variable t          : natural;
        begin
            banner("the BASE 'fire' is abstract -- it refuses");
            t := d1.add("1", "BARE");
            dispatch(d1);
            if d1.raised = "NotImplementedError" then
                print("  NotImplementedError -- as owed: a trigger must say what it does");
            end if;
            banner("the BASE 'on_termination' is optional -- it is silent");
            t := d2.add("", "BARE");
            test_on_termination(d2, t, 0);
            print("  returned quietly; nothing raised, nothing printed");
            banner("a NAME given is the name kept");
            t := d3.add("1", "GIVEN", K_SPEAKING);
            print("  name: " & d3.name(t));
        end procedure;
    begin
        runner.init(HWUT_ARGC, HWUT_ARGV1, "TriggerDispatcher: schedule, priority, and the end of time");
        runner.add("schedule"); runner.add("priority"); runner.add("stable");
        runner.add("termination"); runner.add("yielding"); runner.add("stop");
        runner.add("cancel"); runner.add("edges"); runner.add("abstract");
        while runner.dispatch loop
            if    runner.choice = "schedule"    then run_schedule;
            elsif runner.choice = "priority"    then run_priority;
            elsif runner.choice = "stable"      then run_stable;
            elsif runner.choice = "termination" then run_termination;
            elsif runner.choice = "yielding"    then run_yielding;
            elsif runner.choice = "stop"        then run_stop;
            elsif runner.choice = "cancel"      then run_cancel;
            elsif runner.choice = "edges"       then run_edges;
            elsif runner.choice = "abstract"    then run_abstract;
            end if;
            runner.choice_done;
        end loop;
        wait;
    end process;

    --  THE TASK THAT CARRIES 'dispatcher.run()' -- 'yielding', 'cancel'
    run_task : process
    begin
        task_begin(turn, tasks, RUN_TASK_ID);
        timeline.run(dispatcher, turn, tasks, RUN_TASK_ID);
        task_end(turn, tasks, RUN_TASK_ID);
        wait;
    end process;

    --  THE CONSUMER of 'yielding': takes each item as it appears, until the
    --  end is announced.
    consume_task : process
        variable taken : natural := 0;
    begin
        task_begin(turn, tasks, CONSUME_TASK_ID);
        loop
            while not producer.has_item_f loop
                if producer.finished then
                    print("  consumer saw end-of-stream after " & integer'image(taken) & " item(s)");
                    task_end(turn, tasks, CONSUME_TASK_ID);
                    wait;
                end if;
                task_yield(turn, tasks, CONSUME_TASK_ID);
            end loop;
            taken := taken + 1;
            print("        consumer took " & producer.item);
            producer.take;
        end loop;
    end process;
end architecture;
