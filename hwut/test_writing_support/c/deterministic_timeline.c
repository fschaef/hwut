/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The deterministic event dispatcher -- see 'deterministic_timeline.h'.
 * _____________________________________________________________________________
 */
#include "deterministic_timeline.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

void
Trigger_init(Trigger* self, const Trigger_Vtable* vtable, const char* timeline, const char* name)
/* RETURN: nothing; the trigger carries its timeline and name -- a name chosen
 *         by the machine where none is given.                              */
{
    self->vtable   = vtable;
    self->timeline = timeline ? timeline : "";
    if( name && *name ) snprintf(self->name, sizeof(self->name), "%s", name);
    else                snprintf(self->name, sizeof(self->name), "trigger-%p", (void*)self);
}

int
Trigger_fire(Trigger* self, int pseudo_time)
/* RETURN: TIMELINE_OK where the trigger did what it does at its tick;
 *         TIMELINE_NOT_IMPLEMENTED where it says nothing it does (abstract). */
{
    if( ! self->vtable || ! self->vtable->fire ) return TIMELINE_NOT_IMPLEMENTED;
    return self->vtable->fire(self, pseudo_time);
}

void
Trigger_on_termination(Trigger* self, int end_tick)
/* RETURN: nothing; the trigger was told the timeline has passed.           */
{
    if( self->vtable && self->vtable->on_termination ) self->vtable->on_termination(self, end_tick);
}

void
Task_init(Task* self, int (*step_f)(Task*), void* context)
/* RETURN: nothing; the task is ready, not stepped yet.                     */
{
    self->step_f = step_f; self->context = context;
    self->done_f = 0; self->cancelled_f = 0; self->error = TIMELINE_OK;
}

int
Task_step(Task* self)
/* RETURN: 1, the task yielded and goes on; 0, it is done or cancelled.     */
{
    if( self->done_f ) return 0;
    if( ! self->step_f(self) ) self->done_f = 1;
    return ! self->done_f;
}

void
Task_cancel(Task* self)
/* RETURN: nothing; the task is abandoned: never stepped again, and what it
 *         would have done at its end is not done.                          */
{ self->done_f = 1; self->cancelled_f = 1; }

int
Task_await(Task* self)
/* RETURN: the task's end, once done: TIMELINE_OK, TIMELINE_CANCELLED where it
 *         was cancelled (Python's CancelledError), or its own error.       */
{
    while( Task_step(self) ) {}
    return self->cancelled_f ? TIMELINE_CANCELLED : self->error;
}

void
Task_gather(Task** task_list, size_t task_n)
/* RETURN: nothing, once every task is done -- stepped in turn, in the order
 *         given, each up to its next yield.                                */
{
    size_t i;
    int    live_f = 1;
    while( live_f ) {
        live_f = 0;
        for(i = 0; i < task_n; ++i) {
            if( task_list[i]->done_f ) continue;
            Task_step(task_list[i]);
            live_f = 1;
        }
    }
}

void
TriggerDispatcher_init(TriggerDispatcher* self, Trigger** trigger_list, size_t trigger_n)
/* RETURN: nothing; the schedule is built: per tick the (priority, trigger)
 *         pairs due there, the lower digit first, registration order between
 *         equal digits (an insertion sort, stable).                        */
{
    size_t t, k, j;
    int    end_tick = 0;
    memset(self, 0, sizeof(*self));
    self->trigger_list = trigger_list;
    self->trigger_n    = trigger_n;
    self->running_f    = 1;
    for(k = 0; k < trigger_n; ++k)
        if( (int)strlen(trigger_list[k]->timeline) > end_tick ) end_tick = (int)strlen(trigger_list[k]->timeline);
    self->end_tick = end_tick;
    self->schedule = calloc((size_t)end_tick + 1, sizeof(*self->schedule));
    self->firing_n = calloc((size_t)end_tick + 1, sizeof(*self->firing_n));
    for(t = 0; t < (size_t)end_tick; ++t) {
        self->schedule[t] = calloc(trigger_n + 1, sizeof(TriggerDispatcher_Firing));
        for(k = 0; k < trigger_n; ++k) {
            const char* line = trigger_list[k]->timeline;
            if( t < strlen(line) && isdigit((unsigned char)line[t]) ) {
                TriggerDispatcher_Firing firing = { line[t] - '0', trigger_list[k] };
                j = self->firing_n[t]++;
                while( j > 0 && self->schedule[t][j - 1].priority > firing.priority ) {
                    self->schedule[t][j] = self->schedule[t][j - 1]; --j;
                }
                self->schedule[t][j] = firing;
            }
        }
    }
}

void
TriggerDispatcher_free(TriggerDispatcher* self)
/* RETURN: nothing; the schedule's memory is given back.                    */
{
    int t;
    for(t = 0; t < self->end_tick; ++t) free(self->schedule[t]);
    free(self->schedule); free(self->firing_n);
    self->schedule = NULL; self->firing_n = NULL;
}

void
TriggerDispatcher_stop(TriggerDispatcher* self)
/* RETURN: nothing; the run leaves at the next firing and still announces.  */
{ self->running_f = 0; }

static int
_step(Task* task)
/* RETURN: 1 after one firing (the yield); 0 once the timeline passed and
 *         every trigger was told -- or a trigger had nothing to do.        */
{
    TriggerDispatcher* self = (TriggerDispatcher*)task->context;
    size_t k;
    while( self->running_f && self->tick < self->end_tick ) {
        if( (size_t)self->i < self->firing_n[self->tick] ) {
            Trigger* trigger = self->schedule[self->tick][self->i++].trigger;
            int error = Trigger_fire(trigger, self->tick);
            if( error ) { task->error = error; return 0; }
            return 1;
        }
        self->tick += 1; self->i = 0;
    }
    for(k = 0; k < self->trigger_n; ++k) Trigger_on_termination(self->trigger_list[k], self->end_tick);
    return 0;
}

void
TriggerDispatcher_task(TriggerDispatcher* self, Task* task)
/* RETURN: nothing; 'task' is the run, ready to be stepped or gathered.     */
{
    self->tick = 0; self->i = 0;
    Task_init(task, _step, self);
}

int
TriggerDispatcher_run(TriggerDispatcher* self)
/* RETURN: TIMELINE_OK once the timeline passed and the triggers were told;
 *         TIMELINE_NOT_IMPLEMENTED where a trigger said nothing it does.   */
{
    Task task;
    TriggerDispatcher_task(self, &task);
    return Task_await(&task);
}

void
TriggerDispatcher_print(TriggerDispatcher* self, FILE* out)
/* RETURN: nothing; 'TriggerDispatcher', then one line per firing,
 *         '[tick] (priority)name', in the order of the run, were written.  */
{
    int t; size_t k;
    fprintf(out, "TriggerDispatcher");
    for(t = 0; t < self->end_tick; ++t)
        for(k = 0; k < self->firing_n[t]; ++k)
            fprintf(out, "\n[%d] (%d)%s", t, self->schedule[t][k].priority, self->schedule[t][k].trigger->name);
}
