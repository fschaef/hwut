// @hwut {
//     title      = "TriggerDispatcher: schedule, priority, and the end of time"
//     build      { framework = "make", target = "%.exe"
//                  caps { memory_mb = 2048 } }
//     choices {
//         abstract    { features = ["sv-timeline"] }
//         cancel      { features = ["sv-timeline"] }
//         edges       { features = ["sv-timeline"] }
//         priority    { features = ["sv-timeline"] }
//         schedule    { features = ["sv-timeline"] }
//         stable      { features = ["sv-timeline"] }
//         stop        { features = ["sv-timeline"] }
//         termination { features = ["sv-timeline"] }
//         yielding    { features = ["sv-timeline"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The SystemVerilog port of 'python/TEST/test-deterministic-timeline.py',
//          choice for choice, held against its GOOD files by '.link'. The run
//          and the consumer of 'yielding' are SV processes taking turns at
//          every yield; 'cancel' kills the process carrying a run.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import deterministic_timeline::*;

class SpeakingTrigger extends Trigger;
    // A trigger that says what it is asked to do, and when.
    bit silent_termination_f;

    function new(string name, string timeline, bit silent_termination_f = 0);
        // RETURN: the trigger; its setup is said.
        super.new(timeline, name);
        this.silent_termination_f = silent_termination_f;
        $display("SETUP: %s |%s|", padded(name, 7), timeline);
    endfunction

    virtual task fire(int pseudo_time);
        // RETURN: nothing; it was said that this trigger fired, and when.
        $display("  [t:%0d] %s fires", pseudo_time, name);
    endtask

    virtual function void on_termination(int end_tick);
        // RETURN: nothing; it was said that the timeline has passed, and where.
        if (silent_termination_f) return;
        $display("  [end:%0d] %s notified", end_tick, name);
    endfunction
endclass

class MuteTrigger extends Trigger;
    // A trigger that fires and does NOT override 'on_termination' -- the
    // base's silence is what this one demonstrates.
    function new(string name, string timeline);
        // RETURN: the trigger; its setup is said.
        super.new(timeline, name);
        $display("SETUP: %s |%s|  (no on_termination override)", padded(name, 7), timeline);
    endfunction

    virtual task fire(int pseudo_time);
        // RETURN: nothing; it was said that this trigger fired, and when.
        $display("  [t:%0d] %s fires", pseudo_time, name);
    endtask
endclass

class BareTrigger extends Trigger;
    // A trigger that overrides nothing.
    function new(string timeline, string name);
        // RETURN: the trigger.
        super.new(timeline, name);
    endfunction
endclass

class ProducingTrigger extends Trigger;
    // Prepares one item per tick; announces end-of-stream at the end.
    string item;
    bit    item_f;
    bit    finished;

    function new(string name, string timeline);
        // RETURN: the trigger; its setup is said.
        super.new(timeline, name);
        $display("SETUP: %s |%s|", padded(name, 7), timeline);
    endfunction

    virtual task fire(int pseudo_time);
        // RETURN: nothing; one item stands, stamped with its tick.
        item   = $sformatf("item@%0d", pseudo_time);
        item_f = 1;
        $display("  [t:%0d] %s prepared %s", pseudo_time, name, item);
    endtask

    virtual function void on_termination(int end_tick);
        // RETURN: nothing; end-of-stream is announced to the consumer.
        finished = 1;
        $display("  [end:%0d] %s announced end-of-stream", end_tick, name);
    endfunction
endclass

class Consumer extends Task;
    // Takes each item as it appears, until the end is announced.
    ProducingTrigger producer;

    function new(ProducingTrigger producer);
        // RETURN: the consumer of 'producer'.
        super.new("consume");
        this.producer = producer;
    endfunction

    virtual task body();
        // RETURN: nothing; every item was taken, and the end seen.
        int taken = 0;
        while (1) begin
            while (!producer.item_f) begin
                if (producer.finished) begin
                    $display("  consumer saw end-of-stream after %0d item(s)", taken);
                    return;
                end
                Loop::sleep0();
            end
            taken += 1;
            $display("        consumer took %s", producer.item);
            producer.item_f = 0;
        end
    endtask
endclass

class StoppingTrigger extends SpeakingTrigger;
    // Fires once, then asks the run to leave.
    TriggerDispatcher dispatcher;

    function new(string name, string timeline);
        // RETURN: the trigger; its setup is said.
        super.new(name, timeline);
    endfunction

    virtual task fire(int pseudo_time);
        // RETURN: nothing; it fired and asked the dispatcher to stop.
        super.fire(pseudo_time);
        $display("  ... asks the dispatcher to stop");
        dispatcher.stop();
    endtask
endclass

class Test extends HwutRunner;
    function new();
        // RETURN: the runner of this test.
        super.new("TriggerDispatcher: schedule, priority, and the end of time",
                  '{"schedule", "priority", "stable", "termination", "yielding", "stop", "cancel", "edges", "abstract"});
    endfunction

    function void banner(string label);
        // RETURN: nothing; the section heading is printed.
        $display("");
        $display("--- %s ---", label);
    endfunction

    function Trigger speaking(string name, string timeline);
        // RETURN: a SpeakingTrigger, set up.
        SpeakingTrigger t = new(name, timeline);
        return t;
    endfunction

    task dispatch(Trigger trigger_list[$], output string raised);
        // RETURN: nothing; a dispatcher over 'trigger_list' ran to its end;
        //         'raised' is what it raised, '' none.
        TriggerDispatcher d = new(trigger_list);
        d.run();
        raised = d.raised;
    endtask

    task run_schedule();
        // RETURN: nothing; a digit's position is its tick.
        Trigger           l[$] = {};
        string            raised;
        TriggerDispatcher d;
        banner("staggered: A at 0, B at 2, C at 4");
        l = {}; l.push_back(speaking("A", "1    ")); l.push_back(speaking("B", "  1  ")); l.push_back(speaking("C", "    1"));
        dispatch(l, raised);
        banner("a SHORT timeline stops contributing; the long one goes on");
        l = {}; l.push_back(speaking("SHORT", "11")); l.push_back(speaking("LONG", "111111"));
        dispatch(l, raised);
        banner("the SCHEDULE as built -- '[tick] (priority)name'");
        l = {}; l.push_back(speaking("A", "12")); l.push_back(speaking("B", "21"));
        d = new(l);
        $display("%s", d.to_string());
    endtask

    task run_priority();
        // RETURN: nothing; lower digit first within one tick, registration
        //         order notwithstanding.
        Trigger l[$] = {};
        string  raised;
        banner("digits swap between ticks: B leads at 0, A leads at 1");
        l = {}; l.push_back(speaking("A", "21")); l.push_back(speaking("B", "12"));
        dispatch(l, raised);
        banner("0 is the strongest digit, 9 the weakest");
        l = {}; l.push_back(speaking("WEAK", "9")); l.push_back(speaking("STRONG", "0"));
        dispatch(l, raised);
    endtask

    task run_stable();
        // RETURN: nothing; equal digits fire in registration order.
        Trigger l[$] = {};
        string  raised;
        banner("three triggers, all digit 1 at tick 0");
        l = {}; l.push_back(speaking("first", "1")); l.push_back(speaking("second", "1")); l.push_back(speaking("third", "1"));
        dispatch(l, raised);
        banner("registered BACKWARDS -- the order follows registration, not the name");
        l = {}; l.push_back(speaking("third", "1")); l.push_back(speaking("second", "1")); l.push_back(speaking("first", "1"));
        dispatch(l, raised);
    endtask

    task run_termination();
        // RETURN: nothing; the end of the timeline is an event with a stated tick.
        Trigger     l[$] = {};
        string      raised;
        MuteTrigger mute;
        banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0");
        l = {}; l.push_back(speaking("EARLY", "1    "));
        dispatch(l, raised);
        banner("a trigger that NEVER fires is notified all the same");
        l = {}; l.push_back(speaking("FIRES", "1  ")); l.push_back(speaking("SILENT", "   "));
        dispatch(l, raised);
        banner("the LONGEST timeline sets end_tick for everybody");
        l = {}; l.push_back(speaking("SHORT", "1")); l.push_back(speaking("LONG", "1      "));
        dispatch(l, raised);
        banner("a trigger that does not override is simply silent at the end");
        l = {}; l.push_back(speaking("SPEAKS", "1 "));
        mute = new("MUTE", "1 ");
        l.push_back(mute);
        dispatch(l, raised);
    endtask

    task run_yielding();
        // RETURN: nothing; the run yields to a consumer between firings:
        //         each item is taken BEFORE the next tick prepares one.
        ProducingTrigger  producer;
        Consumer          consumer;
        Trigger           l[$] = {};
        Task              both[$] = {};
        TriggerDispatcher d;
        banner("producer fires at every tick; consumer waits between them");
        producer = new("PROD", "111");
        l.push_back(producer);
        d        = new(l);
        consumer = new(producer);
        both.push_back(d.run_task());
        both.push_back(consumer);
        Loop::gather(both);
        $display("");
        $display("Each item was taken BEFORE the next tick prepared one: the run yields.");
    endtask

    task run_stop();
        // RETURN: nothing; a stopped run is an ended run: it still announces.
        StoppingTrigger   stopper;
        Trigger           l[$] = {};
        TriggerDispatcher d;
        banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes");
        stopper = new("STOPPER", "1111");
        l.push_back(stopper);
        l.push_back(speaking("OTHER", "1111"));
        d = new(l);
        stopper.dispatcher = d;
        d.run();
        $display("");
        $display("end_tick is still the timeline's length, not the tick the run stopped at.");
    endtask

    task run_cancel();
        // RETURN: nothing; a cancellation is an abandonment: it announces nothing.
        Trigger           l[$] = {};
        TriggerDispatcher d;
        Task              t;
        string            raised;
        banner("cancel() the task carrying run() -- no announcement follows");
        l.push_back(speaking("A", "1111111111"));
        d = new(l);
        t = d.run_task();
        Loop::create_task(t);
        Loop::sleep0();
        t.cancel();
        t.await_(raised);
        if (raised == "CancelledError") $display("  run() was cancelled");
        $display("");
        $display("No '[end:..]' line above: the triggers were abandoned, not ended.");
    endtask

    task run_edges();
        // RETURN: nothing; degenerate timelines announce and do not fail.
        Trigger l[$] = {};
        string  raised;
        banner("an EMPTY timeline -- end_tick 0");
        l = {}; l.push_back(speaking("EMPTY", ""));
        dispatch(l, raised);
        banner("a timeline of BLANKS -- no digit, so nothing fires");
        l = {}; l.push_back(speaking("BLANK", "    "));
        dispatch(l, raised);
        banner("NO TRIGGERS at all -- nothing to announce, and no failure");
        l = {};
        dispatch(l, raised);
        $display("  (dispatcher ran; nothing was scheduled)");
        banner("a timeline of blanks beside one that fires");
        l = {}; l.push_back(speaking("BLANK", "   ")); l.push_back(speaking("FIRES", " 1 "));
        dispatch(l, raised);
    endtask

    task run_abstract();
        // RETURN: nothing; 'fire' refuses; 'on_termination' is silent.
        Trigger     l[$] = {};
        string      raised;
        BareTrigger bare;
        Trigger     given;
        banner("the BASE 'fire' is abstract -- it refuses");
        bare = new("1", "BARE");
        l.push_back(bare);
        dispatch(l, raised);
        if (raised == "NotImplementedError")
            $display("  NotImplementedError -- as owed: a trigger must say what it does");
        banner("the BASE 'on_termination' is optional -- it is silent");
        bare = new("", "BARE");
        bare.on_termination(0);
        $display("  returned quietly; nothing raised, nothing printed");
        banner("a NAME given is the name kept");
        given = new("1", "GIVEN");
        $display("  name: %s", given.name);
    endtask

    virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' ran.
        case (choice)
            "schedule":    run_schedule();
            "priority":    run_priority();
            "stable":      run_stable();
            "termination": run_termination();
            "yielding":    run_yielding();
            "stop":        run_stop();
            "cancel":      run_cancel();
            "edges":       run_edges();
            "abstract":    run_abstract();
        endcase
    endtask
endclass

module test_deterministic_timeline;
    initial begin
        Test test = new();
        test.run();
    end
endmodule
