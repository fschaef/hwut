/* @hwut {
 *     title      = "TriggerDispatcher: schedule, priority, and the end of time"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         abstract    { features = ["java-timeline"] }
 *         cancel      { features = ["java-timeline"] }
 *         edges       { features = ["java-timeline"] }
 *         priority    { features = ["java-timeline"] }
 *         schedule    { features = ["java-timeline"] }
 *         stable      { features = ["java-timeline"] }
 *         stop        { features = ["java-timeline"] }
 *         termination { features = ["java-timeline"] }
 *         yielding    { features = ["java-timeline"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The Java port of 'python/TEST/test-deterministic-timeline.py',
 *          choice for choice, held against its GOOD files by '.link'. Where
 *          Python awaits, this test runs in 'Async' tasks: the dispatcher's
 *          run yields to a consumer beside it exactly as under asyncio.
 * _____________________________________________________________________________
 */
import hwut.Async;
import hwut.HwutRunner;
import hwut.PyText;
import hwut.Trigger;
import hwut.TriggerDispatcher;

import java.util.List;

final class TestDeterministicTimeline {
    /** RETURN: nothing; the section heading is printed. */
    static void banner(String label) {
        System.out.println();
        System.out.println("--- " + label + " ---");
    }

    /** A trigger that says what it is asked to do, and when. */
    static class SpeakingTrigger extends Trigger {
        final boolean silentTerminationF;

        SpeakingTrigger(String name, String timeline) { this(name, timeline, false); }

        SpeakingTrigger(String name, String timeline, boolean silentTerminationF) {
            super(timeline, name);
            this.silentTerminationF = silentTerminationF;
            System.out.println("SETUP: " + PyText.ljust(name, 7) + " |" + timeline + "|");
        }

        /** RETURN: nothing; says that this trigger fired, and at which tick. */
        @Override public void fire(int pseudoTime) {
            System.out.println("  [t:" + pseudoTime + "] " + name + " fires");
        }

        /** RETURN: nothing; says that the timeline has passed, and where. */
        @Override public void onTermination(int endTick) {
            if (silentTerminationF) return;
            System.out.println("  [end:" + endTick + "] " + name + " notified");
        }
    }

    /** A trigger that fires and does NOT override 'onTermination'. */
    static class MuteTrigger extends Trigger {
        MuteTrigger(String name, String timeline) {
            super(timeline, name);
            System.out.println("SETUP: " + PyText.ljust(name, 7) + " |" + timeline + "|  (no on_termination override)");
        }

        /** RETURN: nothing; says that this trigger fired, and at which tick. */
        @Override public void fire(int pseudoTime) {
            System.out.println("  [t:" + pseudoTime + "] " + name + " fires");
        }
    }

    /** RETURN: nothing; a dispatcher over 'triggerList' ran to completion. */
    static void dispatch(List<? extends Trigger> triggerList) {
        Async.run(new TriggerDispatcher(triggerList)::run);
    }

    /** RETURN: nothing; a digit's position is its tick. */
    static void runSchedule() {
        banner("staggered: A at 0, B at 2, C at 4");
        dispatch(List.of(new SpeakingTrigger("A", "1    "),
                         new SpeakingTrigger("B", "  1  "),
                         new SpeakingTrigger("C", "    1")));

        banner("a SHORT timeline stops contributing; the long one goes on");
        dispatch(List.of(new SpeakingTrigger("SHORT", "11"),
                         new SpeakingTrigger("LONG",  "111111")));

        banner("the SCHEDULE as built -- '[tick] (priority)name'");
        System.out.println(new TriggerDispatcher(List.of(new SpeakingTrigger("A", "12"),
                                                         new SpeakingTrigger("B", "21"))));
    }

    /** RETURN: nothing; lower digit first within one tick. */
    static void runPriority() {
        banner("digits swap between ticks: B leads at 0, A leads at 1");
        dispatch(List.of(new SpeakingTrigger("A", "21"),
                         new SpeakingTrigger("B", "12")));

        banner("0 is the strongest digit, 9 the weakest");
        dispatch(List.of(new SpeakingTrigger("WEAK",   "9"),
                         new SpeakingTrigger("STRONG", "0")));
    }

    /** RETURN: nothing; equal digits fire in registration order. */
    static void runStable() {
        banner("three triggers, all digit 1 at tick 0");
        dispatch(List.of(new SpeakingTrigger("first",  "1"),
                         new SpeakingTrigger("second", "1"),
                         new SpeakingTrigger("third",  "1")));

        banner("registered BACKWARDS -- the order follows registration, not the name");
        dispatch(List.of(new SpeakingTrigger("third",  "1"),
                         new SpeakingTrigger("second", "1"),
                         new SpeakingTrigger("first",  "1")));
    }

    /** RETURN: nothing; the end of the timeline is an event with a stated tick. */
    static void runTermination() {
        banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0");
        dispatch(List.of(new SpeakingTrigger("EARLY", "1    ")));

        banner("a trigger that NEVER fires is notified all the same");
        dispatch(List.of(new SpeakingTrigger("FIRES",  "1  "),
                         new SpeakingTrigger("SILENT", "   ")));

        banner("the LONGEST timeline sets end_tick for everybody");
        dispatch(List.of(new SpeakingTrigger("SHORT", "1"),
                         new SpeakingTrigger("LONG",  "1      ")));

        banner("a trigger that does not override is simply silent at the end");
        dispatch(List.of(new SpeakingTrigger("SPEAKS", "1 "),
                         new MuteTrigger("MUTE",       "1 ")));
    }

    /** A provider: one item per tick, end-of-stream announced at the end. */
    static final class ProducingTrigger extends Trigger {
        String  item;
        boolean finished;

        ProducingTrigger(String name, String timeline) {
            super(timeline, name);
            System.out.println("SETUP: " + PyText.ljust(name, 7) + " |" + timeline + "|");
        }

        /** RETURN: nothing; one item prepared, stamped with its tick. */
        @Override public void fire(int pseudoTime) {
            item = "item@" + pseudoTime;
            System.out.println("  [t:" + pseudoTime + "] " + name + " prepared " + item);
        }

        /** RETURN: nothing; end-of-stream announced to the consumer. */
        @Override public void onTermination(int endTick) {
            finished = true;
            System.out.println("  [end:" + endTick + "] " + name + " announced end-of-stream");
        }
    }

    /** RETURN: nothing; each item taken as it appears, until the end is
     *          announced. A coroutine: it yields while nothing is there. */
    static void consume(ProducingTrigger producer) {
        int taken = 0;
        while (true) {
            while (producer.item == null) {
                if (producer.finished) {
                    System.out.println("  consumer saw end-of-stream after " + taken + " item(s)");
                    return;
                }
                Async.sleep0();
            }
            taken += 1;
            System.out.println("        consumer took " + producer.item);
            producer.item = null;
        }
    }

    /** RETURN: nothing; the run yields to a consumer between firings. */
    static void runYielding() {
        banner("producer fires at every tick; consumer waits between them");
        Async.run(() -> {
            ProducingTrigger producer = new ProducingTrigger("PROD", "111");
            Async.gather(new TriggerDispatcher(List.of(producer))::run, () -> consume(producer));
        });
        System.out.println();
        System.out.println("Each item was taken BEFORE the next tick prepared one: the run yields.");
    }

    /** A trigger that fires once, then asks the run to leave. */
    static final class StoppingTrigger extends SpeakingTrigger {
        TriggerDispatcher dispatcher;

        StoppingTrigger(String name, String timeline) { super(name, timeline); }

        /** RETURN: nothing; fires, then asks the dispatcher to stop. */
        @Override public void fire(int pseudoTime) {
            super.fire(pseudoTime);
            System.out.println("  ... asks the dispatcher to stop");
            dispatcher.stop();
        }
    }

    /** RETURN: nothing; a stopped run is an ended run: it still announces. */
    static void runStop() {
        banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes");
        StoppingTrigger   stopper    = new StoppingTrigger("STOPPER", "1111");
        SpeakingTrigger   bystander  = new SpeakingTrigger("OTHER",   "1111");
        TriggerDispatcher dispatcher = new TriggerDispatcher(List.of(stopper, bystander));
        stopper.dispatcher = dispatcher;
        Async.run(dispatcher::run);
        System.out.println();
        System.out.println("end_tick is still the timeline's length, not the tick the run stopped at.");
    }

    /** RETURN: nothing; a cancellation is an abandonment: it announces nothing. */
    static void runCancel() {
        banner("cancel() the task carrying run() -- no announcement follows");
        Async.run(() -> {
            TriggerDispatcher dispatcher = new TriggerDispatcher(List.of(new SpeakingTrigger("A", "1111111111")));
            Async.Task task = Async.createTask(dispatcher::run);
            Async.sleep0();
            task.cancel();
            try {
                task.await_();
            } catch (Async.CancelledError cancelled) {
                System.out.println("  run() was cancelled");
            }
        });
        System.out.println();
        System.out.println("No '[end:..]' line above: the triggers were abandoned, not ended.");
    }

    /** RETURN: nothing; degenerate timelines announce and do not fail. */
    static void runEdges() {
        banner("an EMPTY timeline -- end_tick 0");
        dispatch(List.of(new SpeakingTrigger("EMPTY", "")));

        banner("a timeline of BLANKS -- no digit, so nothing fires");
        dispatch(List.of(new SpeakingTrigger("BLANK", "    ")));

        banner("NO TRIGGERS at all -- nothing to announce, and no failure");
        dispatch(List.of());
        System.out.println("  (dispatcher ran; nothing was scheduled)");

        banner("a timeline of blanks beside one that fires");
        dispatch(List.of(new SpeakingTrigger("BLANK", "   "),
                         new SpeakingTrigger("FIRES", " 1 ")));
    }

    /** A trigger that overrides nothing. */
    static final class BareTrigger extends Trigger {
        BareTrigger(String timeline, String name) { super(timeline, name); }
    }

    /** RETURN: nothing; 'fire' refuses; 'onTermination' is silent. */
    static void runAbstract() {
        banner("the BASE 'fire' is abstract -- it refuses");
        try {
            dispatch(List.of(new BareTrigger("1", "BARE")));
        } catch (UnsupportedOperationException error) {
            System.out.println("  NotImplementedError -- as owed: a trigger must say what it does");
        }

        banner("the BASE 'on_termination' is optional -- it is silent");
        BareTrigger bare = new BareTrigger("", "BARE");
        bare.onTermination(0);
        System.out.println("  returned quietly; nothing raised, nothing printed");

        banner("a NAME given is the name kept");
        System.out.println("  name: " + new Trigger("1", "GIVEN").name);
    }

    public static void main(String[] args) {
        new HwutRunner(args, "TriggerDispatcher: schedule, priority, and the end of time")
            .choice("schedule",    TestDeterministicTimeline::runSchedule)
            .choice("priority",    TestDeterministicTimeline::runPriority)
            .choice("stable",      TestDeterministicTimeline::runStable)
            .choice("termination", TestDeterministicTimeline::runTermination)
            .choice("yielding",    TestDeterministicTimeline::runYielding)
            .choice("stop",        TestDeterministicTimeline::runStop)
            .choice("cancel",      TestDeterministicTimeline::runCancel)
            .choice("edges",       TestDeterministicTimeline::runEdges)
            .choice("abstract",    TestDeterministicTimeline::runAbstract)
            .run();
    }
}
