/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
 *          port of 'python/hwut_fsm.py' (README-hwut_fsm.txt). The states it
 *          may be in, the events that move it, the states it must never
 *          reach. A test FIRES the events it observes; every event the model
 *          does not allow, and every forbidden state entered, is WRITTEN as a
 *          line -- so it lands in the GOOD file and the comparison judges it.
 *
 *     char error[256];
 *     FsmMachine* m = FsmMachine_from_string(
 *         "initial: idle\n"
 *         "forbidden: crashed\n"
 *         "idle ---( request )---> waiting ---( grant )---> busy\n"
 *         "busy ---( release )---> idle\n"
 *         ":    ---( fault )--->   crashed\n", 1, "fsm", error, sizeof(error));
 *     FsmMachine_fire(m, "request", "1");    -- 1
 *     FsmMachine_fire(m, "release", "2");    -- BREACH line 2: 'release' in ...
 *     FsmMachine_report(m);
 *     FsmMachine_free(m);
 *
 * The same model text, the same words, the same sorted reports as Python.
 *
 * A MODEL THAT CANNOT BE MEANT is refused where it is read: the constructor
 * returns NULL and 'error' holds Python's FsmError text. A method refused
 * returns -1 (or NULL) and 'self->error' holds the text.
 *
 * 'where' (a breach's place) is a text: digits name a line ('line 3'), any
 * other text stands as written, NULL names no place.
 *
 * 'dfa_f' 1 (the default in Python): one state; 0: the machine holds a SET.
 * Every line goes through 'self->write(self->write_context, line)' -- stdout
 * by default.
 * _____________________________________________________________________________
 */
#ifndef HWUT_FSM_H
#define HWUT_FSM_H

#include <stddef.h>

#define FSM_NAME_MAX   128
#define FSM_ERROR_MAX  512

typedef struct { const char* source; const char* event; const char* target; } FsmTransition;

typedef struct { char* state; char* event; char* since; } FsmMask;   /* state NULL: every state */
typedef struct { char* where; const char* state; const char* event; const char* target; } FsmTraceEntry;

typedef struct FsmMachine {
    char      name[FSM_NAME_MAX];
    int       dfa_f;
    void    (*write)(void* context, const char* line);
    void*     write_context;
    char      error[FSM_ERROR_MAX];

    char**    state_list;   size_t state_n;     /* sorted, the forbidden among them */
    char**    event_list;   size_t event_n;     /* sorted                           */
    FsmTransition* edge;    size_t edge_n;      /* sorted (source, event, target)   */
    const char* initial;
    int*      model_forbidden_f;                /* per state                        */
    int*      final_f;                          /* per state                        */
    size_t    final_n;

    /* the run, and the law as it stands now */
    int*      current_f;                        /* per state                        */
    int*      visit_n;                          /* per state                        */
    int*      taken_n;                          /* per edge                         */
    int*      forbid_f;     char** forbid_since;   /* per state                     */
    int*      permit_f;     char** permit_since;   /* per state                     */
    FsmMask*  mask;         size_t mask_n, mask_capacity;
    FsmTraceEntry* trace;   size_t trace_n, trace_capacity;
    int       breach_n;
} FsmMachine;

FsmMachine* FsmMachine_new(const FsmTransition* transition, size_t transition_n,
                           const char* initial, const char* const* forbidden, size_t forbidden_n,
                           const char* const* final, size_t final_n, int dfa_f, const char* name,
                           const char* const* state, size_t state_n,
                           char* error, size_t error_size);
FsmMachine* FsmMachine_from_string(const char* text, int dfa_f, const char* name,
                                   char* error, size_t error_size);
void        FsmMachine_free(FsmMachine* self);
char*       FsmMachine_to_string(FsmMachine* self, char* buffer, size_t size);

void        FsmMachine_reset(FsmMachine* self);
int         FsmMachine_fire(FsmMachine* self, const char* event, const char* where);

int         FsmMachine_disallow(FsmMachine* self, const char* event, const char* state, const char* where);
int         FsmMachine_allow(FsmMachine* self, const char* event, const char* state);
int         FsmMachine_forbid(FsmMachine* self, const char* state, const char* where);
int         FsmMachine_permit(FsmMachine* self, const char* state, const char* where);
int         FsmMachine_disallowed(FsmMachine* self, const char* event, const char* state, const char* where,
                                  void (*block)(void* context), void* context);
int         FsmMachine_forbidding(FsmMachine* self, const char* state, const char* where,
                                  void (*block)(void* context), void* context);

const char* FsmMachine_state(FsmMachine* self);
size_t      FsmMachine_current(FsmMachine* self, const char** out, size_t out_n);
int         FsmMachine_in_state(FsmMachine* self, const char* state);
int         FsmMachine_can(FsmMachine* self, const char* event);
size_t      FsmMachine_allowed(FsmMachine* self, const char** out, size_t out_n);
size_t      FsmMachine_trace(FsmMachine* self, const FsmTraceEntry** out);
int         FsmMachine_breach_n(FsmMachine* self);

int         FsmMachine_path_to(FsmMachine* self, const char* state, const char* start, int masked_f,
                               const char** out, size_t out_n);
int         FsmMachine_state_reachable(FsmMachine* self, const char* state, const char* start, int masked_f);
size_t      FsmMachine_unreachable(FsmMachine* self, int masked_f, const char** out, size_t out_n);
size_t      FsmMachine_dead_ends(FsmMachine* self, int masked_f, const char** out, size_t out_n);
size_t      FsmMachine_forbidden_reachable(FsmMachine* self, int masked_f, const char** out, size_t out_n);
int         FsmMachine_check(FsmMachine* self, int masked_f);
int         FsmMachine_report(FsmMachine* self);

#endif
