// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
//          'python/deterministic_timeline.py'. Triggers fire at the ticks
//          their timeline strings mark with a digit; within one tick the
//          LOWER digit fires first, equal digits in registration order:
//
//              Trigger A: "1  12 1"
//              Trigger B: " 1  1 2"
//
//          When the last tick has passed, every trigger is told
//          'on_termination(end_tick)', 'end_tick' being the LONGEST
//          timeline's length. 'stop' leaves early and still announces; a
//          CANCELLED task announces nothing.
//
// A TRIGGER OF ONE'S OWN derives 'Trigger' and overrides the task 'fire':
//
//     class MyTrigger extends deterministic_timeline::Trigger;
//         function new(string timeline, string name); super.new(timeline, name); endfunction
//         virtual task fire(int pseudo_time); $display("[%0d] %s fired", pseudo_time, name); endtask
//     endclass
//
//     Trigger           list[$] = '{MyTrigger'(...), ...};
//     TriggerDispatcher d = new(list);
//     d.run();
//
// THE YIELD IS SYSTEMVERILOG'S OWN: a Task is an SV PROCESS ('fork ...
// join_none'), and 'Loop::sleep0()' -- Python's 'await asyncio.sleep(0)' --
// hands the turn to the next task waiting, and waits for its own (a
// semaphore per task). One task runs at a time, the others wait in the
// order they yielded: asyncio's round-robin, so the interleaving the GOOD
// files record is the one that happens -- not left to the simulator's
// order of waking processes of one time slot, which the language leaves
// open (and Verilator 5.020 answers otherwise; '#0' crashes it).
//
//     Loop::create_task(t)    asyncio.create_task(...)  t: a Task, 'body' its coroutine
//     Loop::gather(list)      asyncio.gather(...)       in the order given
//     Loop::sleep0()          await asyncio.sleep(0)
//     t.cancel()              task.cancel()
//     t.await_(raised)        await task                'raised': 'CancelledError', or ''
//
// WHAT PYTHON RAISES stands in a 'raised' text (SystemVerilog has no
// exceptions): the base 'fire' sets its trigger's 'raised' to
// 'NotImplementedError', and the run ends there, announcing nothing -- as
// the exception leaves Python's run. 'd.raised' says it.
// _____________________________________________________________________________
package deterministic_timeline;

    typedef class Loop;
    typedef class DispatcherTask;

    class Task;
        // An asyncio Task: 'body' is its coroutine, run in an SV process of
        // its own; it yields by 'Loop::sleep0()'.
        string    name;
        process   proc;
        semaphore go;
        bit       done_f;
        bit       cancelled_f;
        string    raised;           // what the coroutine raised; '' none

        function new(string name = "task");
            // RETURN: a task not yet created on the loop ('Loop::create_task').
            this.name = name;
            go        = new(0);
        endfunction

        virtual task body();
            // RETURN: nothing; the coroutine ran to its end. Derived tasks
            //         override it; this one does nothing.
        endtask

        function void cancel();
            // RETURN: nothing; the task is abandoned where it waits -- it
            //         runs no further, and announces nothing. A task that is
            //         done stays as it ended.
            if (done_f) return;
            foreach (Loop::ready[i]) if (Loop::ready[i] == this) begin Loop::ready.delete(i); break; end
            if (proc != null) proc.kill();
            cancelled_f = 1;
            done_f      = 1;
            raised      = "CancelledError";
        endfunction

        task await_(output string raised);
            // RETURN: nothing; the task is done -- the caller yielded until
            //         it was; 'raised' is what it raised ('CancelledError'
            //         where it was cancelled), '' where it ended.
            while (!done_f) Loop::sleep0();
            raised = this.raised;
        endtask
    endclass

    class Loop;
        // The event loop: the tasks waiting for their turn, in order, and
        // the one that has it.
        static Task ready[$];
        static Task current;
        static Task main_task;      // the choice itself, where it yields

        static function void pass_();
            // RETURN: nothing; the turn went to the first task waiting, or
            //         to nobody where none waits.
            current = null;
            if (ready.size() == 0) return;
            current = ready.pop_front();
            current.go.put(1);
        endfunction

        static task sleep0();
            // RETURN: nothing; every task that waited for its turn had it,
            //         in order, and this one's came again -- 'await
            //         asyncio.sleep(0)'.
            Task self;
            if (current == null) begin
                if (main_task == null) main_task = new("main");
                current = main_task;
            end
            self = current;
            ready.push_back(self);
            pass_();
            self.go.get(1);
        endtask

        static task create_task(Task t);
            // RETURN: nothing; 't' waits for its first turn, behind every
            //         task waiting -- 'asyncio.create_task'.
            ready.push_back(t);
            fork
                begin
                    t.proc = process::self();
                    t.go.get(1);
                    t.body();
                    t.done_f = 1;
                    pass_();
                end
            join_none
        endtask

        static task gather(Task task_list[$]);
            // RETURN: nothing; every task of 'task_list' ran to its end,
            //         started in the order given -- 'asyncio.gather'.
            bit done_f;
            foreach (task_list[i]) create_task(task_list[i]);
            do begin
                sleep0();
                done_f = 1;
                foreach (task_list[i]) if (!task_list[i].done_f) done_f = 0;
            end while (!done_f);
        endtask
    endclass

    class Trigger;
        // A dispatchable event: digits 0-9 in 'timeline' mark the ticks it
        // fires at, and their priority. A derived trigger overrides 'fire'.
        string     timeline;
        string     name;
        string     raised;          // what 'fire' raised; '' none
        static int made_n = 0;

        function new(string timeline, string name = "");
            // RETURN: a trigger firing at the digits of 'timeline', named
            //         'name' -- 'trigger-<n>' where none is given.
            this.timeline = timeline;
            this.name     = name.len() ? name : $sformatf("trigger-%0d", made_n);
            made_n += 1;
        endfunction

        virtual task fire(int pseudo_time);
            // RETURN: nothing; the action at 'pseudo_time', a tick the
            //         timeline marked. THIS ONE IS ABSTRACT: it does nothing
            //         and sets 'raised' to 'NotImplementedError' -- a trigger
            //         that does nothing has no reason to stand in a timeline.
            raised = "NotImplementedError";
        endtask

        virtual function void on_termination(int end_tick);
            // RETURN: nothing; the timeline has passed -- 'end_tick' is its
            //         length. Does nothing by default; overriding is optional.
        endfunction
    endclass

    class TriggerDispatcher;
        // Executes triggers according to their timelines, built once.
        bit     running_f;
        Trigger trigger_list[$];
        int     end_tick;
        string  raised;             // what a trigger raised; '' none
        // THE SCHEDULE, one entry per firing: tick ascending; within a tick
        // priority ascending, then registration order.
        int     firing_tick[$];
        int     firing_priority[$];
        Trigger firing_trigger[$];

        function new(Trigger trigger_list[$]);
            // RETURN: a dispatcher over 'trigger_list', its schedule built:
            //         as long as the LONGEST timeline; a shorter one adds
            //         nothing beyond its end.
            running_f          = 1;
            this.trigger_list  = trigger_list;
            end_tick           = 0;
            firing_tick        = {};
            firing_priority    = {};
            firing_trigger     = {};
            foreach (trigger_list[i]) if (trigger_list[i].timeline.len() > end_tick) end_tick = trigger_list[i].timeline.len();
            for (int t = 0; t < end_tick; t++)
                for (int priority_ = 0; priority_ <= 9; priority_++)
                    foreach (trigger_list[i]) begin
                        string timeline = trigger_list[i].timeline;
                        if (t < timeline.len() && timeline[t] == 8'h30 + priority_) begin
                            firing_tick.push_back(t);
                            firing_priority.push_back(priority_);
                            firing_trigger.push_back(trigger_list[i]);
                        end
                    end
        endfunction

        function void stop();
            // RETURN: nothing; the run leaves the timeline at the next firing
            //         -- and still announces termination.
            running_f = 0;
        endfunction

        task run();
            // RETURN: nothing; the timeline was stepped, every trigger due
            //         fired in order, with a yield ('Loop::sleep0') after each
            //         one; then every trigger was told 'on_termination
            //         (end_tick)' -- also where 'stop()' cut the run short.
            //         Where a trigger raised, the run ended there, 'raised'
            //         says what, and nothing was announced.
            foreach (firing_trigger[i]) begin
                if (!running_f) break;
                firing_trigger[i].fire(firing_tick[i]);
                if (firing_trigger[i].raised.len()) begin
                    raised = firing_trigger[i].raised;
                    return;
                end
                Loop::sleep0();
            end
            foreach (trigger_list[i]) trigger_list[i].on_termination(end_tick);
        endtask

        function Task run_task();
            // RETURN: a Task whose coroutine is this dispatcher's 'run' --
            //         for 'Loop::create_task' and 'Loop::gather'.
            DispatcherTask t = new(this);
            return t;
        endfunction

        function string to_string();
            // RETURN: the built timeline, one line per firing --
            //         '[tick] (priority)name' -- in the order the run fires.
            string text = "TriggerDispatcher";
            foreach (firing_trigger[i])
                text = {text, $sformatf("\n[%0d] (%0d)%s", firing_tick[i], firing_priority[i], firing_trigger[i].name)};
            return text;
        endfunction
    endclass

    class DispatcherTask extends Task;
        // The task carrying a dispatcher's 'run'.
        TriggerDispatcher dispatcher;

        function new(TriggerDispatcher dispatcher);
            // RETURN: a task that runs 'dispatcher'.
            super.new("run");
            this.dispatcher = dispatcher;
        endfunction

        virtual task body();
            // RETURN: nothing; the dispatcher ran; what it raised is raised.
            dispatcher.run();
            raised = dispatcher.raised;
        endtask
    endclass

endpackage
