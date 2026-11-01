/* @hwut {
 *     title      = "TriggerDispatcher: schedule, priority, and the end of time"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         abstract    { features = ["cpp-timeline"] }
 *         cancel      { features = ["cpp-timeline"] }
 *         edges       { features = ["cpp-timeline"] }
 *         priority    { features = ["cpp-timeline"] }
 *         schedule    { features = ["cpp-timeline"] }
 *         stable      { features = ["cpp-timeline"] }
 *         stop        { features = ["cpp-timeline"] }
 *         termination { features = ["cpp-timeline"] }
 *         yielding    { features = ["cpp-timeline"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C++ port of 'python/TEST/test-deterministic-timeline.py',
 *          choice for choice, held against its GOOD files by '.link'. Where
 *          Python awaits, C++ steps a task.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <string>
#include <vector>
#include "hwut_runner.hpp"
#include "deterministic_timeline.hpp"

using hwut::Trigger;
using hwut::TriggerDispatcher;

static void banner(const std::string& label) { std::printf("\n--- %s ---\n", label.c_str()); }

/* ---------------------------------------------------------- the triggers */
struct SpeakingTrigger : Trigger {
    SpeakingTrigger(const std::string& name, const std::string& timeline) : Trigger(timeline, name)
    { std::printf("SETUP: %-7s |%s|\n", name.c_str(), timeline.c_str()); }
    void fire(int t) override { std::printf("  [t:%d] %s fires\n", t, name().c_str()); }
    void on_termination(int end_tick) override { std::printf("  [end:%d] %s notified\n", end_tick, name().c_str()); }
};

struct MuteTrigger : Trigger {               // does not override 'on_termination'
    MuteTrigger(const std::string& name, const std::string& timeline) : Trigger(timeline, name)
    { std::printf("SETUP: %-7s |%s|  (no on_termination override)\n", name.c_str(), timeline.c_str()); }
    void fire(int t) override { std::printf("  [t:%d] %s fires\n", t, name().c_str()); }
};

static void dispatch(const std::vector<Trigger*>& list) { TriggerDispatcher(list).run(); }

static void
run_schedule()
{
    banner("staggered: A at 0, B at 2, C at 4");
    { SpeakingTrigger a("A", "1    "), b("B", "  1  "), c("C", "    1"); dispatch({ &a, &b, &c }); }
    banner("a SHORT timeline stops contributing; the long one goes on");
    { SpeakingTrigger s("SHORT", "11"), l("LONG", "111111"); dispatch({ &s, &l }); }
    banner("the SCHEDULE as built -- '[tick] (priority)name'");
    { SpeakingTrigger a("A", "12"), b("B", "21");
      std::printf("%s\n", TriggerDispatcher({ &a, &b }).to_string().c_str()); }
}

static void
run_priority()
{
    banner("digits swap between ticks: B leads at 0, A leads at 1");
    { SpeakingTrigger a("A", "21"), b("B", "12"); dispatch({ &a, &b }); }
    banner("0 is the strongest digit, 9 the weakest");
    { SpeakingTrigger w("WEAK", "9"), s("STRONG", "0"); dispatch({ &w, &s }); }
}

static void
run_stable()
{
    banner("three triggers, all digit 1 at tick 0");
    { SpeakingTrigger a("first", "1"), b("second", "1"), c("third", "1"); dispatch({ &a, &b, &c }); }
    banner("registered BACKWARDS -- the order follows registration, not the name");
    { SpeakingTrigger a("third", "1"), b("second", "1"), c("first", "1"); dispatch({ &a, &b, &c }); }
}

static void
run_termination()
{
    banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0");
    { SpeakingTrigger e("EARLY", "1    "); dispatch({ &e }); }
    banner("a trigger that NEVER fires is notified all the same");
    { SpeakingTrigger f("FIRES", "1  "), s("SILENT", "   "); dispatch({ &f, &s }); }
    banner("the LONGEST timeline sets end_tick for everybody");
    { SpeakingTrigger s("SHORT", "1"), g("LONG", "1      "); dispatch({ &s, &g }); }
    banner("a trigger that does not override is simply silent at the end");
    { SpeakingTrigger s("SPEAKS", "1 "); MuteTrigger m("MUTE", "1 "); dispatch({ &s, &m }); }
}

/* ------------------------------------------------------------- yielding */
struct ProducingTrigger : Trigger {
    ProducingTrigger() : Trigger("111", "PROD") { std::printf("SETUP: %-7s |%s|\n", "PROD", "111"); }
    void fire(int t) override
    {
        item = "item@" + std::to_string(t); has_item_f = true;
        std::printf("  [t:%d] %s prepared %s\n", t, name().c_str(), item.c_str());
    }
    void on_termination(int end_tick) override
    {
        finished = true;
        std::printf("  [end:%d] %s announced end-of-stream\n", end_tick, name().c_str());
    }
    std::string item;
    bool        has_item_f = false, finished = false;
};

static void
run_yielding()
{
    banner("producer fires at every tick; consumer waits between them");
    ProducingTrigger  producer;
    TriggerDispatcher d({ &producer });
    int               taken = 0;
    hwut::Task        run  = d.task();
    hwut::Task        take([&] {                    // true: wait (yield); false: done
        while( true ) {
            if( ! producer.has_item_f ) {
                if( ! producer.finished ) return true;
                std::printf("  consumer saw end-of-stream after %d item(s)\n", taken);
                return false;
            }
            taken += 1;
            std::printf("        consumer took %s\n", producer.item.c_str());
            producer.has_item_f = false;
        }
    });
    hwut::gather({ &run, &take });
    std::printf("\nEach item was taken BEFORE the next tick prepared one: the run yields.\n");
}

/* ----------------------------------------------------------- stop, cancel */
struct StoppingTrigger : SpeakingTrigger {
    StoppingTrigger() : SpeakingTrigger("STOPPER", "1111") {}
    void fire(int t) override
    {
        SpeakingTrigger::fire(t);
        std::printf("  ... asks the dispatcher to stop\n");
        dispatcher->stop();
    }
    TriggerDispatcher* dispatcher = nullptr;
};

static void
run_stop()
{
    banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes");
    StoppingTrigger   stopper;
    SpeakingTrigger   bystander("OTHER", "1111");
    TriggerDispatcher d({ &stopper, &bystander });
    stopper.dispatcher = &d;
    d.run();
    std::printf("\nend_tick is still the timeline's length, not the tick the run stopped at.\n");
}

static void
run_cancel()
{
    banner("cancel() the task carrying run() -- no announcement follows");
    {
        SpeakingTrigger   a("A", "1111111111");
        TriggerDispatcher d({ &a });
        hwut::Task        task = d.task();
        task.step();                                    // one tick passes
        task.cancel();
        try                                     { task.await(); }
        catch( const hwut::CancelledError& )    { std::printf("  run() was cancelled\n"); }
    }
    std::printf("\nNo '[end:..]' line above: the triggers were abandoned, not ended.\n");
}

static void
run_edges()
{
    banner("an EMPTY timeline -- end_tick 0");
    { SpeakingTrigger e("EMPTY", ""); dispatch({ &e }); }
    banner("a timeline of BLANKS -- no digit, so nothing fires");
    { SpeakingTrigger b("BLANK", "    "); dispatch({ &b }); }
    banner("NO TRIGGERS at all -- nothing to announce, and no failure");
    dispatch({});
    std::printf("  (dispatcher ran; nothing was scheduled)\n");
    banner("a timeline of blanks beside one that fires");
    { SpeakingTrigger b("BLANK", "   "), f("FIRES", " 1 "); dispatch({ &b, &f }); }
}

static void
run_abstract()
{
    banner("the BASE 'fire' is abstract -- it refuses");
    {
        Trigger bare("1", "BARE");
        try                                       { dispatch({ &bare }); }
        catch( const hwut::NotImplementedError& ) { std::printf("  NotImplementedError -- as owed: a trigger must say what it does\n"); }
    }
    banner("the BASE 'on_termination' is optional -- it is silent");
    {
        Trigger bare("", "BARE");
        bare.on_termination(0);
        std::printf("  returned quietly; nothing raised, nothing printed\n");
    }
    banner("a NAME given is the name kept");
    Trigger given("1", "GIVEN");
    std::printf("  name: %s\n", given.name().c_str());
}

int
main(int argc, char** argv)
{
    hwut::HwutRunner runner(argc, argv, "TriggerDispatcher: schedule, priority, and the end of time", {
        { "schedule", run_schedule }, { "priority", run_priority }, { "stable", run_stable },
        { "termination", run_termination }, { "yielding", run_yielding }, { "stop", run_stop },
        { "cancel", run_cancel }, { "edges", run_edges }, { "abstract", run_abstract },
    });
    return runner.run();
}
