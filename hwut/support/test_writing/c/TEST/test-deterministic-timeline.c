/* @hwut {
 *     title      = "TriggerDispatcher: schedule, priority, and the end of time"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         abstract    { features = ["c-timeline"] }
 *         cancel      { features = ["c-timeline"] }
 *         edges       { features = ["c-timeline"] }
 *         priority    { features = ["c-timeline"] }
 *         schedule    { features = ["c-timeline"] }
 *         stable      { features = ["c-timeline"] }
 *         stop        { features = ["c-timeline"] }
 *         termination { features = ["c-timeline"] }
 *         yielding    { features = ["c-timeline"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C port of 'python/TEST/test-deterministic-timeline.py', choice
 *          for choice, held against its GOOD files by '.link'. Where Python
 *          awaits, C steps a task.
 * _____________________________________________________________________________
 */
#include <stdio.h>
#include <string.h>
#include "hwut_runner.h"
#include "deterministic_timeline.h"

static void banner(const char* label) { printf("\n--- %s ---\n", label); }

/* ---------------------------------------------------------- the triggers */
typedef struct { Trigger base; int silent_termination_f; TriggerDispatcher* dispatcher; } SpeakingTrigger;

static int
SpeakingTrigger_fire(Trigger* self, int t)
{ printf("  [t:%d] %s fires\n", t, self->name); return TIMELINE_OK; }

static void
SpeakingTrigger_on_termination(Trigger* self, int end_tick)
{
    if( ((SpeakingTrigger*)self)->silent_termination_f ) return;
    printf("  [end:%d] %s notified\n", end_tick, self->name);
}

static const Trigger_Vtable SpeakingTrigger_vtable = { SpeakingTrigger_fire, SpeakingTrigger_on_termination };
static const Trigger_Vtable MuteTrigger_vtable     = { SpeakingTrigger_fire, NULL };
static const Trigger_Vtable BareTrigger_vtable     = { NULL, NULL };

static void
SpeakingTrigger_init(SpeakingTrigger* self, const char* name, const char* timeline)
{
    memset(self, 0, sizeof(*self));
    Trigger_init(&self->base, &SpeakingTrigger_vtable, timeline, name);
    printf("SETUP: %-7s |%s|\n", name, timeline);
}

static void
MuteTrigger_init(SpeakingTrigger* self, const char* name, const char* timeline)
{
    memset(self, 0, sizeof(*self));
    Trigger_init(&self->base, &MuteTrigger_vtable, timeline, name);
    printf("SETUP: %-7s |%s|  (no on_termination override)\n", name, timeline);
}

static int
dispatch(Trigger** list, size_t n)
{
    TriggerDispatcher d; int result;
    TriggerDispatcher_init(&d, list, n);
    result = TriggerDispatcher_run(&d);
    TriggerDispatcher_free(&d);
    return result;
}

#define SPEAKING(var, name, line) SpeakingTrigger var; SpeakingTrigger_init(&var, name, line)

static void
run_schedule(void)
{
    banner("staggered: A at 0, B at 2, C at 4");
    { SPEAKING(a, "A", "1    "); SPEAKING(b, "B", "  1  "); SPEAKING(c, "C", "    1");
      Trigger* l[] = { &a.base, &b.base, &c.base }; dispatch(l, 3); }
    banner("a SHORT timeline stops contributing; the long one goes on");
    { SPEAKING(s, "SHORT", "11"); SPEAKING(l2, "LONG", "111111");
      Trigger* l[] = { &s.base, &l2.base }; dispatch(l, 2); }
    banner("the SCHEDULE as built -- '[tick] (priority)name'");
    { SPEAKING(a, "A", "12"); SPEAKING(b, "B", "21");
      Trigger* l[] = { &a.base, &b.base }; TriggerDispatcher d;
      TriggerDispatcher_init(&d, l, 2); TriggerDispatcher_print(&d, stdout); printf("\n");
      TriggerDispatcher_free(&d); }
}

static void
run_priority(void)
{
    banner("digits swap between ticks: B leads at 0, A leads at 1");
    { SPEAKING(a, "A", "21"); SPEAKING(b, "B", "12"); Trigger* l[] = { &a.base, &b.base }; dispatch(l, 2); }
    banner("0 is the strongest digit, 9 the weakest");
    { SPEAKING(w, "WEAK", "9"); SPEAKING(s, "STRONG", "0"); Trigger* l[] = { &w.base, &s.base }; dispatch(l, 2); }
}

static void
run_stable(void)
{
    banner("three triggers, all digit 1 at tick 0");
    { SPEAKING(a, "first", "1"); SPEAKING(b, "second", "1"); SPEAKING(c, "third", "1");
      Trigger* l[] = { &a.base, &b.base, &c.base }; dispatch(l, 3); }
    banner("registered BACKWARDS -- the order follows registration, not the name");
    { SPEAKING(a, "third", "1"); SPEAKING(b, "second", "1"); SPEAKING(c, "first", "1");
      Trigger* l[] = { &a.base, &b.base, &c.base }; dispatch(l, 3); }
}

static void
run_termination(void)
{
    banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0");
    { SPEAKING(e, "EARLY", "1    "); Trigger* l[] = { &e.base }; dispatch(l, 1); }
    banner("a trigger that NEVER fires is notified all the same");
    { SPEAKING(f, "FIRES", "1  "); SPEAKING(s, "SILENT", "   "); Trigger* l[] = { &f.base, &s.base }; dispatch(l, 2); }
    banner("the LONGEST timeline sets end_tick for everybody");
    { SPEAKING(s, "SHORT", "1"); SPEAKING(g, "LONG", "1      "); Trigger* l[] = { &s.base, &g.base }; dispatch(l, 2); }
    banner("a trigger that does not override is simply silent at the end");
    { SPEAKING(s, "SPEAKS", "1 "); SpeakingTrigger m; MuteTrigger_init(&m, "MUTE", "1 ");
      Trigger* l[] = { &s.base, &m.base }; dispatch(l, 2); }
}

/* ------------------------------------------------------------- yielding */
typedef struct { Trigger base; char item[32]; int has_item_f; int finished; } ProducingTrigger;

static int
ProducingTrigger_fire(Trigger* self, int t)
{
    ProducingTrigger* p = (ProducingTrigger*)self;
    snprintf(p->item, sizeof(p->item), "item@%d", t); p->has_item_f = 1;
    printf("  [t:%d] %s prepared %s\n", t, self->name, p->item);
    return TIMELINE_OK;
}

static void
ProducingTrigger_on_termination(Trigger* self, int end_tick)
{
    ((ProducingTrigger*)self)->finished = 1;
    printf("  [end:%d] %s announced end-of-stream\n", end_tick, self->name);
}

static const Trigger_Vtable ProducingTrigger_vtable = { ProducingTrigger_fire, ProducingTrigger_on_termination };

typedef struct { ProducingTrigger* producer; int taken; } Consumer;

static int
consume_step(Task* task)
/* RETURN: 1 to wait (yield); 0 once the end-of-stream was seen.           */
{
    Consumer* c = (Consumer*)task->context;
    while( 1 ) {
        if( ! c->producer->has_item_f ) {
            if( c->producer->finished ) {
                printf("  consumer saw end-of-stream after %d item(s)\n", c->taken);
                return 0;
            }
            return 1;
        }
        c->taken += 1;
        printf("        consumer took %s\n", c->producer->item);
        c->producer->has_item_f = 0;
    }
}

static void
run_yielding(void)
{
    ProducingTrigger producer; Consumer consumer = { &producer, 0 };
    TriggerDispatcher d; Task run, take; Task* both[2];
    Trigger* l[1];
    banner("producer fires at every tick; consumer waits between them");
    memset(&producer, 0, sizeof(producer));
    Trigger_init(&producer.base, &ProducingTrigger_vtable, "111", "PROD");
    printf("SETUP: %-7s |%s|\n", "PROD", "111");
    l[0] = &producer.base;
    TriggerDispatcher_init(&d, l, 1);
    TriggerDispatcher_task(&d, &run);
    Task_init(&take, consume_step, &consumer);
    both[0] = &run; both[1] = &take;
    Task_gather(both, 2);
    TriggerDispatcher_free(&d);
    printf("\nEach item was taken BEFORE the next tick prepared one: the run yields.\n");
}

/* ----------------------------------------------------------- stop, cancel */
static int
StoppingTrigger_fire(Trigger* self, int t)
{
    SpeakingTrigger_fire(self, t);
    printf("  ... asks the dispatcher to stop\n");
    TriggerDispatcher_stop(((SpeakingTrigger*)self)->dispatcher);
    return TIMELINE_OK;
}

static const Trigger_Vtable StoppingTrigger_vtable = { StoppingTrigger_fire, SpeakingTrigger_on_termination };

static void
run_stop(void)
{
    SpeakingTrigger stopper, bystander; TriggerDispatcher d; Trigger* l[2];
    banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes");
    memset(&stopper, 0, sizeof(stopper));
    Trigger_init(&stopper.base, &StoppingTrigger_vtable, "1111", "STOPPER");
    printf("SETUP: %-7s |%s|\n", "STOPPER", "1111");
    SpeakingTrigger_init(&bystander, "OTHER", "1111");
    l[0] = &stopper.base; l[1] = &bystander.base;
    TriggerDispatcher_init(&d, l, 2);
    stopper.dispatcher = &d;
    TriggerDispatcher_run(&d);
    TriggerDispatcher_free(&d);
    printf("\nend_tick is still the timeline's length, not the tick the run stopped at.\n");
}

static void
run_cancel(void)
{
    TriggerDispatcher d; Task task; Trigger* l[1];
    banner("cancel() the task carrying run() -- no announcement follows");
    { SPEAKING(a, "A", "1111111111");
      l[0] = &a.base;
      TriggerDispatcher_init(&d, l, 1);
      TriggerDispatcher_task(&d, &task);
      Task_step(&task);                                 /* one tick passes */
      Task_cancel(&task);
      if( Task_await(&task) == TIMELINE_CANCELLED ) printf("  run() was cancelled\n");
      TriggerDispatcher_free(&d); }
    printf("\nNo '[end:..]' line above: the triggers were abandoned, not ended.\n");
}

static void
run_edges(void)
{
    banner("an EMPTY timeline -- end_tick 0");
    { SPEAKING(e, "EMPTY", ""); Trigger* l[] = { &e.base }; dispatch(l, 1); }
    banner("a timeline of BLANKS -- no digit, so nothing fires");
    { SPEAKING(b, "BLANK", "    "); Trigger* l[] = { &b.base }; dispatch(l, 1); }
    banner("NO TRIGGERS at all -- nothing to announce, and no failure");
    dispatch(NULL, 0);
    printf("  (dispatcher ran; nothing was scheduled)\n");
    banner("a timeline of blanks beside one that fires");
    { SPEAKING(b, "BLANK", "   "); SPEAKING(f, "FIRES", " 1 "); Trigger* l[] = { &b.base, &f.base }; dispatch(l, 2); }
}

static void
run_abstract(void)
{
    Trigger bare, given; Trigger* l[1];
    banner("the BASE 'fire' is abstract -- it refuses");
    Trigger_init(&bare, &BareTrigger_vtable, "1", "BARE");
    l[0] = &bare;
    if( dispatch(l, 1) == TIMELINE_NOT_IMPLEMENTED )
        printf("  NotImplementedError -- as owed: a trigger must say what it does\n");
    banner("the BASE 'on_termination' is optional -- it is silent");
    Trigger_init(&bare, &BareTrigger_vtable, "", "BARE");
    Trigger_on_termination(&bare, 0);
    printf("  returned quietly; nothing raised, nothing printed\n");
    banner("a NAME given is the name kept");
    Trigger_init(&given, NULL, "1", "GIVEN");
    printf("  name: %s\n", given.name);
}

int
main(int argc, char** argv)
{
    static const HwutRunner_Choice choice_list[] = {
        { "schedule", run_schedule }, { "priority", run_priority }, { "stable", run_stable },
        { "termination", run_termination }, { "yielding", run_yielding }, { "stop", run_stop },
        { "cancel", run_cancel }, { "edges", run_edges }, { "abstract", run_abstract }, { NULL, NULL }
    };
    HwutRunner runner;
    HwutRunner_init(&runner, argc, argv, "TriggerDispatcher: schedule, priority, and the end of time",
                    choice_list);
    return HwutRunner_run(&runner);
}
