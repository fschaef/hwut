-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
--          'python/deterministic_timeline.py', in VHDL alone. Triggers fire
--          at the ticks their timeline strings mark with a digit; within one
--          tick the LOWER digit fires first, equal digits in registration
--          order:
--
--              Trigger A: "1  12 1"
--              Trigger B: " 1  1 2"
--
--          When the last tick has passed, every trigger is told
--          'on_termination(end_tick)', 'end_tick' being the LONGEST
--          timeline's length. 'stop' leaves early and still announces; a
--          CANCELLED task announces nothing.
--
-- A TRIGGER is registered in its dispatcher and is known by its INDEX there
-- (from 0, in registration order); its CLASS is a 'kind', an integer the test
-- chooses (TRIGGER_BASE, 0, is Python's 'Trigger' itself):
--
--     variable d : TriggerDispatcher;
--     t := d.add("1 1 3", "SUB", SPEAKING);       -- Python: SpeakingTrigger(...)
--
-- THE VIRTUAL METHODS ARE GENERIC SUBPROGRAMS: a test instantiates the
-- generic package 'deterministic_timeline_run' with its own 'fire' and
-- 'on_termination', each dispatching on the trigger's kind -- VHDL's
-- 'class MyTrigger(Trigger)':
--
--     procedure my_fire(variable d : inout TriggerDispatcher; trigger, pseudo_time : natural) is
--     begin
--         case d.kind(trigger) is
--             when SPEAKING => print(...);
--             when others   => trigger_fire(d, trigger, pseudo_time);   -- the base: abstract
--         end case;
--     end procedure;
--     package timeline is new work.deterministic_timeline_run
--         generic map (fire => my_fire, on_termination => my_on_termination);
--     ...
--     timeline.run(d, turn, tasks);                -- Python: await d.run()
--
-- THE BASE 'fire' IS ABSTRACT: 'trigger_fire' raises -- VHDL has no
-- exceptions, so the dispatcher holds Python's exception name
-- ('d.raised' = "NotImplementedError") and the run ends there, announcing
-- nothing, as the exception would leave it. 'trigger_on_termination' says
-- nothing.
--
-- THE YIELD: asyncio's tasks are VHDL PROCESSES, its event loop a 'TaskLoop'
-- and a signal 'turn' of subtype 'task_turn' that hands the turn from process
-- to process -- one process runs at a time, the next in the ready queue's
-- order, which is asyncio's (Python's 'sleep(0)' puts the yielder last; a
-- created task is run in creation order; 'gather' awaits all):
--
--     signal turn          : task_turn := 0;        -- in the architecture
--     shared variable tasks : TaskLoop;
--
--     consumer : process begin                     -- task 2
--         task_begin(turn, tasks, 2);
--         ... task_yield(turn, tasks, 2); ...       -- Python: await asyncio.sleep(0)
--         task_end(turn, tasks, 2);
--         wait;
--     end process;
--
--     task_gather(turn, tasks, 0, (1, 2));         -- in the main process, task 0
--
-- The main process -- the one the runner gives the choice -- is task 0 and
-- runs from the start. Every switch is a delta cycle of the simulation: no
-- simulation time passes, and the order does not depend on the order in
-- which the simulator resumes processes of one delta -- only the process
-- whose turn it is goes on.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_pytext.all;

package deterministic_timeline is
    constant TRIGGER_BASE   : integer  := 0;
    constant TRIGGER_MAX    : positive := 64;
    constant FIRING_MAX     : positive := 1024;
    constant TASK_MAX       : positive := 16;

    type TriggerDispatcher is protected
        impure function add(timeline_text : string; trigger_name : string := ""; trigger_kind : integer := TRIGGER_BASE) return natural;
        impure function trigger_n return natural;
        impure function name(trigger : natural) return string;
        impure function timeline(trigger : natural) return string;
        impure function kind(trigger : natural) return integer;
        impure function end_tick return natural;
        procedure stop;
        impure function running return boolean;
        procedure raise(exception : string);
        impure function raised return string;
        impure function image return string;
        -- the run's cursor ('deterministic_timeline_run.run' walks it)
        procedure restart;
        procedure next_firing(found : out boolean; trigger : out natural; pseudo_time : out natural);
    end protected;

    procedure trigger_fire(variable dispatcher : inout TriggerDispatcher; trigger : natural; pseudo_time : natural);
    procedure trigger_on_termination(variable dispatcher : inout TriggerDispatcher; trigger : natural; end_tick : natural);

    -- THE TURN: the newest serial wins -- every process drives it, the
    -- loop's last decision is the largest.
    function maximum_serial(serial : integer_vector) return integer;
    subtype task_turn is maximum_serial integer;

    type TaskLoop is protected
        procedure create(task : natural);
        impure function current return natural;
        impure function serial return integer;
        procedure yield(me : natural);
        impure function block_on(me : natural; task_list : integer_vector) return boolean;
        procedure finish(me : natural);
        procedure cancel(task : natural);
        impure function cancel_requested_f(task : natural) return boolean;
        impure function done_f(task : natural) return boolean;
        impure function cancelled_f(task : natural) return boolean;
    end protected;

    procedure task_create(variable tasks : inout TaskLoop; task : natural);
    procedure task_begin(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural);
    procedure task_yield(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural);
    procedure task_await(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural;
                         task : natural);
    procedure task_gather(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural;
                          task_list : integer_vector);
    procedure task_end(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural);
end package;

package body deterministic_timeline is
    type TriggerDispatcher is protected body
        variable timeline_of : line_vector(0 to TRIGGER_MAX - 1);
        variable name_of     : line_vector(0 to TRIGGER_MAX - 1);
        variable kind_of     : integer_vector(0 to TRIGGER_MAX - 1);
        variable n           : natural := 0;
        variable running_f   : boolean := true;
        variable exception_text : line := new string'("");
        -- the schedule, built at the first run or image: firing i stands at
        -- tick 'firing_tick(i)' and is the trigger 'firing_trigger(i)'
        variable built_f        : boolean := false;
        variable firing_tick    : integer_vector(0 to FIRING_MAX - 1);
        variable firing_digit   : integer_vector(0 to FIRING_MAX - 1);
        variable firing_trigger : integer_vector(0 to FIRING_MAX - 1);
        variable firing_n       : natural := 0;
        variable cursor         : natural := 0;

        impure function add(timeline_text : string; trigger_name : string := ""; trigger_kind : integer := TRIGGER_BASE) return natural is
            -- RETURN: natural, the index of the trigger now registered with
            --         'timeline_text', 'trigger_name' -- "trigger-<index>"
            --         where none is given -- and the class 'trigger_kind'.
        begin
            assert n < TRIGGER_MAX severity failure;
            timeline_of(n) := new string'(timeline_text);
            if trigger_name = "" then name_of(n) := new string'("trigger-" & integer'image(n));
            else                      name_of(n) := new string'(trigger_name);
            end if;
            kind_of(n) := trigger_kind;
            built_f    := false;
            n          := n + 1;
            return n - 1;
        end function;

        impure function trigger_n return natural is
            -- RETURN: natural, the number of triggers registered.
        begin return n; end function;

        impure function name(trigger : natural) return string is
            -- RETURN: string, the trigger's name.
        begin return name_of(trigger).all; end function;

        impure function timeline(trigger : natural) return string is
            -- RETURN: string, the trigger's timeline.
        begin return timeline_of(trigger).all; end function;

        impure function kind(trigger : natural) return integer is
            -- RETURN: integer, the trigger's class, as registered.
        begin return kind_of(trigger); end function;

        impure function end_tick return natural is
            -- RETURN: natural, the length of the LONGEST timeline -- one past
            --         the last tick that could fire; 0 for none.
            variable result : natural := 0;
        begin
            for i in 0 to n - 1 loop result := maximum(result, timeline_of(i)'length); end loop;
            return result;
        end function;

        procedure build is
            -- RETURN: nothing; the firings stand tick by tick, within a tick
            --         by digit and, digits being equal, in registration order.
            variable c : character;
        begin
            if built_f then return; end if;
            firing_n := 0;
            for tick in 0 to end_tick - 1 loop
                for digit in 0 to 9 loop
                    for i in 0 to n - 1 loop
                        if tick < timeline_of(i)'length then
                            c := timeline_of(i)(timeline_of(i)'left + tick);
                            if character'pos(c) = character'pos('0') + digit then
                                assert firing_n < FIRING_MAX severity failure;
                                firing_tick(firing_n)    := tick;
                                firing_digit(firing_n)   := digit;
                                firing_trigger(firing_n) := i;
                                firing_n := firing_n + 1;
                            end if;
                        end if;
                    end loop;
                end loop;
            end loop;
            built_f := true;
        end procedure;

        procedure stop is
            -- RETURN: nothing; the run leaves the timeline at its next step --
            --         and still announces termination.
        begin running_f := false; end procedure;

        impure function running return boolean is
            -- RETURN: true until 'stop' was called.
        begin return running_f; end function;

        procedure raise(exception : string) is
            -- RETURN: nothing; Python's exception 'exception' stands raised:
            --         the run ends at once.
        begin exception_text := new string'(exception); end procedure;

        impure function raised return string is
            -- RETURN: string, the name of the exception raised in the run --
            --         "NotImplementedError" from an abstract 'fire'; "", none.
        begin return exception_text.all; end function;

        impure function image return string is
            -- RETURN: string, Python's repr: "TriggerDispatcher", then per
            --         scheduled firing a line '[tick] (priority)name', in the
            --         order the run fires them.
            variable text : line := new string'("TriggerDispatcher");
        begin
            build;
            for i in 0 to firing_n - 1 loop
                write(text, LF & "[" & integer'image(firing_tick(i)) & "] (" & integer'image(firing_digit(i))
                            & ")" & name_of(firing_trigger(i)).all);
            end loop;
            return text.all;
        end function;

        procedure restart is
            -- RETURN: nothing; the cursor stands before the first firing.
        begin build; cursor := 0; end procedure;

        procedure next_firing(found : out boolean; trigger : out natural; pseudo_time : out natural) is
            -- RETURN: nothing; 'found' true: 'trigger' fires now, at
            --         'pseudo_time'; false: the timeline has passed, or the
            --         run was stopped.
        begin
            found := false; trigger := 0; pseudo_time := 0;
            if not running_f or cursor >= firing_n then return; end if;
            found       := true;
            trigger     := firing_trigger(cursor);
            pseudo_time := firing_tick(cursor);
            cursor      := cursor + 1;
        end procedure;
    end protected body;

    procedure trigger_fire(variable dispatcher : inout TriggerDispatcher; trigger : natural; pseudo_time : natural) is
        -- RETURN: nothing; Python's 'Trigger.fire' -- ABSTRACT: raises
        --         NotImplementedError (see 'raised'). A trigger that does
        --         nothing at its tick has no reason to stand in the timeline.
    begin dispatcher.raise("NotImplementedError"); end procedure;

    procedure trigger_on_termination(variable dispatcher : inout TriggerDispatcher; trigger : natural; end_tick : natural) is
        -- RETURN: nothing; Python's 'Trigger.on_termination': says nothing.
    begin end procedure;

    function maximum_serial(serial : integer_vector) return integer is
        -- RETURN: integer, the largest of the drivers' serials.
        variable result : integer := integer'low;
    begin
        for i in serial'range loop result := maximum(result, serial(i)); end loop;
        return result;
    end function;

    type TaskLoop is protected body
        variable ready        : integer_vector(0 to TASK_MAX - 1);
        variable ready_n      : natural := 0;
        variable running_task : natural := 0;
        variable serial_n     : integer := 0;
        variable done         : boolean_vector(0 to TASK_MAX - 1) := (others => false);
        variable cancel_f     : boolean_vector(0 to TASK_MAX - 1) := (others => false);
        variable waiting      : boolean_vector(0 to TASK_MAX - 1) := (others => false);
        variable awaited      : integer_vector(0 to TASK_MAX - 1) := (others => 0);   -- bit mask per task

        procedure push(task : natural) is
        begin ready(ready_n) := task; ready_n := ready_n + 1; end procedure;

        procedure pick is
            -- RETURN: nothing; the first ready task is the running one, and
            --         a new serial says so.
        begin
            assert ready_n > 0 report "TaskLoop: every task waits -- deadlock" severity failure;
            running_task := ready(0);
            ready(0 to ready_n - 2) := ready(1 to ready_n - 1);
            ready_n  := ready_n - 1;
            serial_n := serial_n + 1;
        end procedure;

        procedure create(task : natural) is
            -- RETURN: nothing; 'task' is ready to run -- after those ready
            --         before it (asyncio.create_task).
        begin
            done(task) := false; cancel_f(task) := false;
            push(task);
        end procedure;

        impure function current return natural is
            -- RETURN: natural, the task whose turn it is.
        begin return running_task; end function;

        impure function serial return integer is
            -- RETURN: integer, the serial of the loop's last decision.
        begin return serial_n; end function;

        procedure yield(me : natural) is
            -- RETURN: nothing; 'me' stands last in the ready queue, the
            --         first one runs (asyncio.sleep(0)).
        begin push(me); pick; end procedure;

        impure function block_on(me : natural; task_list : integer_vector) return boolean is
            -- RETURN: true, 'me' waits until every task of 'task_list' is
            --         done -- the next ready task runs; false, they are done
            --         already and 'me' goes on.
            variable mask : integer := 0;
        begin
            for i in task_list'range loop
                if not done(task_list(i)) then mask := mask + 2 ** task_list(i); end if;
            end loop;
            if mask = 0 then return false; end if;
            waiting(me) := true; awaited(me) := mask;
            pick;
            return true;
        end function;

        procedure finish(me : natural) is
            -- RETURN: nothing; 'me' is done; a task awaiting it and nothing
            --         else is ready again; the next ready task runs.
            constant bit : integer := 2 ** me;
        begin
            done(me) := true;
            for t in 0 to TASK_MAX - 1 loop
                if waiting(t) and (awaited(t) / bit) mod 2 = 1 then
                    awaited(t) := awaited(t) - bit;
                    if awaited(t) = 0 then waiting(t) := false; push(t); end if;
                end if;
            end loop;
            pick;
        end procedure;

        procedure cancel(task : natural) is
            -- RETURN: nothing; 'task' is asked to end where it yields next.
        begin cancel_f(task) := true; end procedure;

        impure function cancel_requested_f(task : natural) return boolean is
            -- RETURN: true, 'task' was cancelled and is to end at its yield.
        begin return cancel_f(task); end function;

        impure function done_f(task : natural) return boolean is
            -- RETURN: true, 'task' ended.
        begin return done(task); end function;

        impure function cancelled_f(task : natural) return boolean is
            -- RETURN: true, 'task' ended by a cancellation -- awaiting it,
            --         Python raises CancelledError.
        begin return done(task) and cancel_f(task); end function;
    end protected body;

    procedure task_switch(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural) is
        -- RETURN: nothing; once it is the turn of 'me' again.
    begin
        turn <= tasks.serial;
        wait on turn until tasks.current = me;
    end procedure;

    procedure task_create(variable tasks : inout TaskLoop; task : natural) is
        -- RETURN: nothing; 'task' (a process waiting in 'task_begin') is
        --         ready to run -- asyncio.create_task.
    begin tasks.create(task); end procedure;

    procedure task_begin(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural) is
        -- RETURN: nothing; once the task 'me' was created and its turn came.
    begin wait on turn until tasks.current = me; end procedure;

    procedure task_yield(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural) is
        -- RETURN: nothing; every task ready before 'me' had its turn, and
        --         'me' has it again -- asyncio.sleep(0).
    begin tasks.yield(me); task_switch(turn, tasks, me); end procedure;

    procedure task_await(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural;
                         task : natural) is
        -- RETURN: nothing; once 'task' is done ('tasks.cancelled_f(task)':
        --         it was cancelled).
    begin
        if tasks.block_on(me, (0 => task)) then task_switch(turn, tasks, me); end if;
    end procedure;

    procedure task_gather(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural;
                          task_list : integer_vector) is
        -- RETURN: nothing; every task of 'task_list' was created, in that
        --         order, and is done -- asyncio.gather.
    begin
        for i in task_list'range loop tasks.create(task_list(i)); end loop;
        if tasks.block_on(me, task_list) then task_switch(turn, tasks, me); end if;
    end procedure;

    procedure task_end(signal turn : inout task_turn; variable tasks : inout TaskLoop; me : natural) is
        -- RETURN: nothing; the task 'me' is done, the next ready one runs.
        --         The process of 'me' waits for ever after.
    begin
        tasks.finish(me);
        turn <= tasks.serial;
    end procedure;
end package body;

-- _____________________________________________________________________________
--
-- THE RUN, OVER THE TEST'S OWN TRIGGERS: 'fire' and 'on_termination' are the
-- test's -- Python's overridden methods (see the package above).
-- _____________________________________________________________________________
use work.deterministic_timeline.all;

package deterministic_timeline_run is
    generic (
        procedure fire(variable dispatcher : inout TriggerDispatcher; trigger : natural; pseudo_time : natural);
        procedure on_termination(variable dispatcher : inout TriggerDispatcher; trigger : natural; end_tick : natural)
    );

    procedure run(variable dispatcher : inout TriggerDispatcher; signal turn : inout task_turn;
                  variable tasks : inout TaskLoop; me : natural := 0);
end package;

package body deterministic_timeline_run is
    procedure run(variable dispatcher : inout TriggerDispatcher; signal turn : inout task_turn;
                  variable tasks : inout TaskLoop; me : natural := 0) is
        -- RETURN: nothing; the timeline was stepped tick by tick, every
        --         trigger due fired in priority order, and the task 'me'
        --         yielded after each one, so that a consumer of what the
        --         trigger produced may progress.
        --         THE ANNOUNCEMENT ALWAYS FOLLOWS -- walked to its end or cut
        --         short by 'stop', every trigger is told
        --         'on_termination(end_tick)', 'end_tick' the timeline's
        --         LENGTH -- unless the run was ABANDONED: the task 'me' was
        --         cancelled (it returns at the yield), or a 'fire' raised
        --         ('dispatcher.raised').
        variable found          : boolean;
        variable trigger, tick  : natural;
    begin
        dispatcher.restart;
        loop
            dispatcher.next_firing(found, trigger, tick);
            exit when not found;
            fire(dispatcher, trigger, tick);
            if dispatcher.raised /= "" then return; end if;
            task_yield(turn, tasks, me);
            if tasks.cancel_requested_f(me) then return; end if;
        end loop;
        for i in 0 to dispatcher.trigger_n - 1 loop
            on_termination(dispatcher, i, dispatcher.end_tick);
        end loop;
    end procedure;
end package body;
