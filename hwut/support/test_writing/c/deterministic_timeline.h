/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
 *          'python/deterministic_timeline.py'. Triggers fire at the ticks
 *          their timeline strings mark with a digit; within one tick the
 *          LOWER digit fires first, equal digits in registration order:
 *
 *              Trigger A: "1  12 1"
 *              Trigger B: " 1  1 2"
 *
 *          When the last tick has passed, every trigger is told
 *          'on_termination(end_tick)', 'end_tick' being the LONGEST
 *          timeline's length. 'stop' leaves early and still announces; a
 *          CANCELLED task announces nothing.
 *
 * A TRIGGER OF ONE'S OWN embeds 'Trigger' first and brings a vtable:
 *
 *     typedef struct { Trigger base; int count; } MyTrigger;
 *     static int  MyTrigger_fire(Trigger* self, int t) { ...; return 0; }
 *     static const Trigger_Vtable MyTrigger_vtable = { MyTrigger_fire, NULL };
 *     Trigger_init(&my.base, &MyTrigger_vtable, "1 1 3", "SUB");
 *
 *     Trigger* list[] = { &my.base };
 *     TriggerDispatcher d;  TriggerDispatcher_init(&d, list, 1);
 *     TriggerDispatcher_run(&d);  TriggerDispatcher_free(&d);
 *
 * 'fire' NULL is ABSTRACT: the run ends there with TIMELINE_NOT_IMPLEMENTED
 * -- Python's NotImplementedError. 'on_termination' NULL says nothing.
 *
 * THE YIELD WITHOUT COROUTINES: a Task is a step function; one 'Task_step'
 * runs up to the next yield. 'Task_gather' steps tasks in turn, in the order
 * given -- the order 'asyncio.gather' gives them -- until each is done.
 * _____________________________________________________________________________
 */
#ifndef HWUT_DETERMINISTIC_TIMELINE_H
#define HWUT_DETERMINISTIC_TIMELINE_H

#include <stddef.h>
#include <stdio.h>

enum { TIMELINE_OK = 0, TIMELINE_NOT_IMPLEMENTED = 1, TIMELINE_CANCELLED = 2 };

typedef struct Trigger Trigger;

typedef struct {
    int  (*fire)(Trigger* self, int pseudo_time);         /* NULL: abstract  */
    void (*on_termination)(Trigger* self, int end_tick);  /* NULL: silent    */
} Trigger_Vtable;

struct Trigger {
    const Trigger_Vtable* vtable;
    const char*           timeline;
    char                  name[64];
};

void Trigger_init(Trigger* self, const Trigger_Vtable* vtable, const char* timeline, const char* name);
int  Trigger_fire(Trigger* self, int pseudo_time);
void Trigger_on_termination(Trigger* self, int end_tick);

typedef struct Task Task;
struct Task {
    int   (*step_f)(Task* self);      /* 1: yielded, more to come; 0: done */
    void*   context;
    int     done_f;
    int     cancelled_f;
    int     error;                    /* TIMELINE_*, once done             */
};

void Task_init(Task* self, int (*step_f)(Task*), void* context);
int  Task_step(Task* self);
void Task_cancel(Task* self);
int  Task_await(Task* self);
void Task_gather(Task** task_list, size_t task_n);

typedef struct { int priority; Trigger* trigger; } TriggerDispatcher_Firing;

typedef struct {
    Trigger**                  trigger_list;
    size_t                     trigger_n;
    TriggerDispatcher_Firing** schedule;      /* one array per tick         */
    size_t*                    firing_n;      /* firings per tick           */
    int                        end_tick;
    int                        running_f;
    int                        tick, i;       /* where the run stands       */
} TriggerDispatcher;

void TriggerDispatcher_init(TriggerDispatcher* self, Trigger** trigger_list, size_t trigger_n);
void TriggerDispatcher_free(TriggerDispatcher* self);
void TriggerDispatcher_stop(TriggerDispatcher* self);
void TriggerDispatcher_task(TriggerDispatcher* self, Task* task);
int  TriggerDispatcher_run(TriggerDispatcher* self);
void TriggerDispatcher_print(TriggerDispatcher* self, FILE* out);

#endif
