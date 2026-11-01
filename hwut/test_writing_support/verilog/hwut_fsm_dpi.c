/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE DPI-C FACE OF '../c/hwut_fsm.c' for 'hwut_fsm.sv'. The C port
 *          reads the model text, holds the machine and writes its lines; this
 *          file converts between its C types and what DPI-C passes: a
 *          'chandle' is the 'FsmMachine*', '' stands for C's NULL (Python's
 *          None), and a list of names is left in a buffer of this file that
 *          'hwut_sv_fsm_list_n' and 'hwut_sv_fsm_list_at' read.
 *
 * EVERY LINE THE MACHINE WRITES goes to the SystemVerilog machine that owns
 * it: the exported 'hwut_sv_fsm_write(id, line)', 'id' the machine's number,
 * called in the scope of package 'hwut_fsm'. So the lines pass '$display'
 * like every other line of the test, or the writer the test gave.
 * _____________________________________________________________________________
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "svdpi.h"
#include "hwut_fsm.h"

#define HWUT_SV_FSM_TEXT_MAX (1 << 16)
#define HWUT_SV_FSM_LIST_MAX 4096

extern void hwut_sv_fsm_write(int id, const char* line);     /* SystemVerilog */

static char        _refusal[FSM_ERROR_MAX];
static const char* _list[HWUT_SV_FSM_LIST_MAX];
static int         _list_n;

static const char* _or_null(const char* text) { return text && *text ? text : NULL; }

static void
_write(void* context, const char* line)
/* RETURN: nothing; 'line' went to the SystemVerilog machine numbered by
 *         'context'.                                                       */
{
    svSetScope(svGetScopeFromName("TOP.hwut_fsm"));
    hwut_sv_fsm_write((int)(intptr_t)context, line);
}

static void*
_attached(FsmMachine* m, int id)
/* RETURN: 'm', writing through '_write' as machine 'id'; NULL for NULL.    */
{
    if( ! m ) return NULL;
    m->write         = _write;
    m->write_context = (void*)(intptr_t)id;
    return m;
}

/* ------------------------------------------------------------ the builder */
static FsmTransition _transition[HWUT_SV_FSM_LIST_MAX];
static const char*   _forbidden[HWUT_SV_FSM_LIST_MAX];
static const char*   _final[HWUT_SV_FSM_LIST_MAX];
static const char*   _state[HWUT_SV_FSM_LIST_MAX];
static size_t        _transition_n, _forbidden_n, _final_n, _state_n;
static char*         _owned[4 * HWUT_SV_FSM_LIST_MAX];
static size_t        _owned_n;

static const char* _keep(const char* text) { return _owned_n < 4 * HWUT_SV_FSM_LIST_MAX ? (_owned[_owned_n++] = strdup(text)) : ""; }

void
hwut_sv_fsm_builder_clear(void)
/* RETURN: nothing; no transition, forbidden, final or extra state is held. */
{
    while( _owned_n ) free(_owned[--_owned_n]);
    _transition_n = _forbidden_n = _final_n = _state_n = 0;
}

void
hwut_sv_fsm_builder_add(int what, const char* a, const char* b, const char* c)
/* RETURN: nothing; held for 'hwut_sv_fsm_build': 'what' 0 the transition
 *         (a, b, c), 1 a forbidden state 'a', 2 a final state 'a', 3 a
 *         state 'a' of no transition.                                      */
{
    if( what == 0 && _transition_n < HWUT_SV_FSM_LIST_MAX ) {
        _transition[_transition_n].source = _keep(a);
        _transition[_transition_n].event  = _keep(b);
        _transition[_transition_n].target = _keep(c);
        _transition_n += 1;
    }
    else if( what == 1 && _forbidden_n < HWUT_SV_FSM_LIST_MAX ) _forbidden[_forbidden_n++] = _keep(a);
    else if( what == 2 && _final_n     < HWUT_SV_FSM_LIST_MAX ) _final[_final_n++]         = _keep(a);
    else if( what == 3 && _state_n     < HWUT_SV_FSM_LIST_MAX ) _state[_state_n++]         = _keep(a);
}

void*
hwut_sv_fsm_build(const char* initial, int dfa_f, const char* name, int id)
/* RETURN: the machine of what the builder holds, standing in 'initial',
 *         writing as machine 'id'; NULL where the model cannot be meant --
 *         'hwut_sv_fsm_refusal' says why.                                  */
{
    FsmMachine* m = FsmMachine_new(_transition, _transition_n, initial, _forbidden, _forbidden_n,
                                   _final, _final_n, dfa_f, name, _state, _state_n,
                                   _refusal, sizeof(_refusal));
    return _attached(m, id);
}

void*
hwut_sv_fsm_from_string(const char* text, int dfa_f, const char* name, int id)
/* RETURN: the machine the model 'text' describes, writing as machine 'id';
 *         NULL where the model cannot be meant -- 'hwut_sv_fsm_refusal'
 *         says why (Python's FsmError).                                    */
{ return _attached(FsmMachine_from_string(text, dfa_f, name, _refusal, sizeof(_refusal)), id); }

const char* hwut_sv_fsm_refusal(void)
/* RETURN: why the last machine was not made.                               */
{ return _refusal; }

void hwut_sv_fsm_free(void* m)
/* RETURN: nothing; the machine 'm' is gone.                                */
{ FsmMachine_free((FsmMachine*)m); }

const char* hwut_sv_fsm_error(void* m)
/* RETURN: why the last method of 'm' was refused (Python's FsmError).      */
{ return ((FsmMachine*)m)->error; }

const char*
hwut_sv_fsm_to_string(void* m)
/* RETURN: the model in the text 'from_string' reads, sorted; 64 KiB at most. */
{
    static char buffer[HWUT_SV_FSM_TEXT_MAX];
    return FsmMachine_to_string((FsmMachine*)m, buffer, sizeof(buffer));
}

/* ------------------------------------------------------- the run, the law */
void hwut_sv_fsm_reset(void* m)
/* RETURN: nothing; the machine stands in its initial state, nothing fired. */
{ FsmMachine_reset((FsmMachine*)m); }

int hwut_sv_fsm_fire(void* m, const char* event, const char* where)
/* RETURN: 1 where 'event' moved the machine and no forbidden state was
 *         entered; 0 where a breach was written.                           */
{ return FsmMachine_fire((FsmMachine*)m, event, _or_null(where)); }

int hwut_sv_fsm_disallow(void* m, const char* event, const char* state, const char* where)
/* RETURN: 0, 'event' is disallowed in 'state' ('' every state); -1, refused. */
{ return FsmMachine_disallow((FsmMachine*)m, event, _or_null(state), _or_null(where)); }

int hwut_sv_fsm_allow(void* m, const char* event, const char* state)
/* RETURN: 0, 'event' is allowed again in 'state' ('' every state); -1, refused. */
{ return FsmMachine_allow((FsmMachine*)m, event, _or_null(state)); }

int hwut_sv_fsm_forbid(void* m, const char* state, const char* where)
/* RETURN: 0, 'state' is forbidden; -1, refused.                            */
{ return FsmMachine_forbid((FsmMachine*)m, state, _or_null(where)); }

int hwut_sv_fsm_permit(void* m, const char* state, const char* where)
/* RETURN: 0, 'state' is permitted; -1, refused.                            */
{ return FsmMachine_permit((FsmMachine*)m, state, _or_null(where)); }

/* -------------------------------------------------------------- questions */
int
hwut_sv_fsm_state(void* m, const char** state)
/* RETURN: 1, '*state' is the one state the machine stands in; 0, it stands
 *         in a set -- 'hwut_sv_fsm_error' says so.                         */
{
    const char* one = FsmMachine_state((FsmMachine*)m);
    *state = one ? one : "";
    return one != NULL;
}

int hwut_sv_fsm_in_state(void* m, const char* state)
/* RETURN: 1 where the machine stands in 'state'; 0 else.                   */
{ return FsmMachine_in_state((FsmMachine*)m, state); }

int hwut_sv_fsm_can(void* m, const char* event)
/* RETURN: 1 where 'event' is allowed where the machine stands; 0 else.     */
{ return FsmMachine_can((FsmMachine*)m, event); }

int hwut_sv_fsm_breach_n(void* m)
/* RETURN: the breaches written so far.                                     */
{ return FsmMachine_breach_n((FsmMachine*)m); }

int hwut_sv_fsm_list_n(void)
/* RETURN: the number of names the last list question left.                 */
{ return _list_n; }

const char* hwut_sv_fsm_list_at(int i)
/* RETURN: the i-th name the last list question left; '' beyond.            */
{ return i >= 0 && i < _list_n ? _list[i] : ""; }

static int _listed(size_t n) { _list_n = (int)(n < HWUT_SV_FSM_LIST_MAX ? n : HWUT_SV_FSM_LIST_MAX); return _list_n; }

int
hwut_sv_fsm_list(void* m, int what, int masked_f)
/* RETURN: the number of names listed, sorted: 'what' 0 the states the
 *         machine stands in, 1 the events allowed now, 2 the unreachable
 *         states, 3 the dead ends, 4 the forbidden states reachable --
 *         2..4 under the masks where 'masked_f'.                           */
{
    FsmMachine* self = (FsmMachine*)m;
    switch( what ) {
    case 0:  return _listed(FsmMachine_current(self, _list, HWUT_SV_FSM_LIST_MAX));
    case 1:  return _listed(FsmMachine_allowed(self, _list, HWUT_SV_FSM_LIST_MAX));
    case 2:  return _listed(FsmMachine_unreachable(self, masked_f, _list, HWUT_SV_FSM_LIST_MAX));
    case 3:  return _listed(FsmMachine_dead_ends(self, masked_f, _list, HWUT_SV_FSM_LIST_MAX));
    default: return _listed(FsmMachine_forbidden_reachable(self, masked_f, _list, HWUT_SV_FSM_LIST_MAX));
    }
}

int
hwut_sv_fsm_path_to(void* m, const char* state, const char* start, int masked_f)
/* RETURN: the length of the shortest path of events from 'start' ('' the
 *         initial state, 'now' where the machine stands) into 'state', the
 *         events listed; -1 where none leads there.                        */
{
    int n = FsmMachine_path_to((FsmMachine*)m, state, _or_null(start), masked_f, _list, HWUT_SV_FSM_LIST_MAX);
    _list_n = n < 0 ? 0 : n;
    return n;
}

int hwut_sv_fsm_state_reachable(void* m, const char* state, const char* start, int masked_f)
/* RETURN: 1 where a path leads from 'start' into 'state'; 0 else.          */
{ return FsmMachine_state_reachable((FsmMachine*)m, state, _or_null(start), masked_f); }

int hwut_sv_fsm_check(void* m, int masked_f)
/* RETURN: the findings about the model alone, each written as a line.      */
{ return FsmMachine_check((FsmMachine*)m, masked_f); }

int hwut_sv_fsm_report(void* m)
/* RETURN: the breaches seen, a non-final end counted; the coverage written. */
{ return FsmMachine_report((FsmMachine*)m); }

int
hwut_sv_fsm_trace_n(void* m)
/* RETURN: the number of transitions fired.                                 */
{ const FsmTraceEntry* entry; return (int)FsmMachine_trace((FsmMachine*)m, &entry); }

const char*
hwut_sv_fsm_trace_field(void* m, int i, int k)
/* RETURN: of the i-th transition fired, 'k' 0 its 'where' ('' none), 1 the
 *         state it left, 2 the event, 3 the state it entered.              */
{
    const FsmTraceEntry* entry;
    size_t               n = FsmMachine_trace((FsmMachine*)m, &entry);
    const char*          text;
    if( i < 0 || (size_t)i >= n ) return "";
    text = k == 0 ? entry[i].where : k == 1 ? entry[i].state : k == 2 ? entry[i].event : entry[i].target;
    return text ? text : "";
}
