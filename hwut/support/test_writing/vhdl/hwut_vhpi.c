/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE VHPIDIRECT GLUE -- what the VHDL packages of this directory
 *          call where VHDL cannot do a thing itself: the process (exit,
 *          fork, file descriptors, the environment), Python's text of a
 *          float, a str and a bytes, and the C modules of '../c' that parse
 *          (FSM model text, HOCON) and drive libvterm and the pseudo-terminal.
 *          It parses, draws and schedules nothing itself (VHDL RATIONALE VH-1).
 *
 * GHDL PASSES an unconstrained 'string' as a FAT POINTER: the characters and
 * the bounds ('HwutVhpi_String'); scalars 'in' by value. A text going BACK to
 * VHDL is left in one RESULT buffer here, and fetched by
 * 'hwut_vhpi_result_n' / 'hwut_vhpi_result_get' ('hwut_vhpi.result' in VHDL)
 * before the next call that sets it. A C object is known to VHDL by a HANDLE,
 * an integer > 0 indexing a table here -- VHDL integers are 32 bits, an
 * address is not.
 *
 * Built into 'libhwut_vhdl.so' with the C modules of '../c' it wraps; GHDL loads it at
 * elaboration by the name the 'foreign' attributes give ('libhwut_vhdl.so',
 * found along LD_LIBRARY_PATH, which the launcher of a test sets).
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <fcntl.h>
#include <math.h>
#include <setjmp.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

#include "hwut_pytext.h"
#include "hwut_fsm.h"
#include "hwut_hocon.h"
#include "hwut_vterm.h"

typedef struct { int32_t left, right; int8_t direction; int32_t length; } HwutVhpi_Bounds;
typedef struct { char* base; HwutVhpi_Bounds* bounds; } HwutVhpi_String;

/* ------------------------------------------------------------ the plumbing */
#define ARGUMENT_SLOT_N 8
static char*  argument_slot[ARGUMENT_SLOT_N];

static const char*
_text(int slot, const HwutVhpi_String* s)
/* RETURN: the characters of 's', NUL-terminated, in argument slot 'slot' --
 *         valid until the slot is used again.                              */
{
    size_t n = (size_t)s->bounds->length;
    free(argument_slot[slot]);
    argument_slot[slot] = malloc(n + 1);
    memcpy(argument_slot[slot], s->base, n);
    argument_slot[slot][n] = '\0';
    return argument_slot[slot];
}

static const char*
_optional(int slot, const HwutVhpi_String* s)
/* RETURN: as '_text'; NULL where 's' is empty -- VHDL's "" for Python's None. */
{ return s->bounds->length ? _text(slot, s) : NULL; }

static char*  result;
static size_t result_n;

static void
_result(const char* text, size_t n)
/* RETURN: nothing; 'n' bytes of 'text' (NULL: none) are the result.        */
{
    free(result);
    result   = malloc(n + 1);
    if( n ) memcpy(result, text, n);
    result[n] = '\0';
    result_n  = n;
}

static void _result_text(const char* text) { _result(text ? text : "", text ? strlen(text) : 0); }

int  hwut_vhpi_result_n(void)
/* RETURN: the length of the result.                                         */
{ return (int)result_n; }

void hwut_vhpi_result_get(HwutVhpi_String* out)
/* RETURN: nothing; 'out' (as long as the result) holds the result.          */
{ if( result_n ) memcpy(out->base, result, result_n); }

#define HANDLE_MAX 4096
static void* handle_object[HANDLE_MAX];
static int   handle_kind[HANDLE_MAX];
enum { KIND_FSM = 1, KIND_HOCON_DOCUMENT, KIND_HOCON_NODE, KIND_SCREEN, KIND_TERMINAL };

static int
_handle_new(void* object, int kind)
/* RETURN: a handle > 0 for 'object'; 0 where the table is full.            */
{
    int h;
    for(h = 1; h < HANDLE_MAX; ++h) {
        if( handle_object[h] ) continue;
        handle_object[h] = object; handle_kind[h] = kind;
        return h;
    }
    return 0;
}

static void*
_object(int h, int kind)
/* RETURN: the object of handle 'h' if it is one of 'kind'; NULL, else.     */
{
    if( h <= 0 || h >= HANDLE_MAX || handle_kind[h] != kind ) return NULL;
    return handle_object[h];
}

static void _handle_free(int h) { if( h > 0 && h < HANDLE_MAX ) { handle_object[h] = NULL; handle_kind[h] = 0; } }

static void _flush(void) { fflush(stdout); fflush(stderr); }

/* ------------------------------------------------------------- the process */
void hwut_vhpi_flush(void)
/* RETURN: nothing; stdout and stderr are flushed -- what VHDL's 'output'
 *         wrote stands in the file.                                         */
{ _flush(); }

void hwut_vhpi_exit(int status)
/* RETURN: never; the process ends with 'status', its streams flushed.      */
{ _flush(); _exit(status & 0xFF); }

int hwut_vhpi_getenv(const HwutVhpi_String* name)
/* RETURN: 1, the variable 'name' is set -- its value the result; 0, else.  */
{
    const char* value = getenv(_text(0, name));
    _result_text(value);
    return value != NULL;
}

void hwut_vhpi_setenv(const HwutVhpi_String* name, const HwutVhpi_String* value)
/* RETURN: nothing; the variable 'name' holds 'value'.                       */
{ setenv(_text(0, name), _text(1, value), 1); }

/* -------------------------------------------------------------------- libm */
/* THE PLATFORM'S libm, as Python's 'math' uses it: GHDL's math_real is IEEE's
 * reference body in VHDL, whose 'cos' is off from libm's in the 9th digit. */
double hwut_vhpi_sqrt(double x) { return sqrt(x); }   /* RETURN: libm's sqrt(x). */
double hwut_vhpi_log(double x)  { return log(x);  }   /* RETURN: libm's log(x).  */
double hwut_vhpi_cos(double x)  { return cos(x);  }   /* RETURN: libm's cos(x).  */

/* ----------------------------------------------- the runner's interactive */
static int control_fd = -1;

void hwut_vhpi_interactive_begin(void)
/* RETURN: nothing; the original stdout is the UP channel, fd 1 and fd 2
 *         point at a stray sink -- output outside a choice lands there.    */
{
    char path[] = "/tmp/hwut_stray_XXXXXX";
    int  stray;
    _flush();
    control_fd = dup(1);
    stray      = mkstemp(path);
    if( stray >= 0 ) { dup2(stray, 1); dup2(stray, 2); close(stray); }
}

void hwut_vhpi_up(const HwutVhpi_String* message)
/* RETURN: nothing; 'message' and a newline are written on the UP channel.  */
{
    if( write(control_fd, message->base, (size_t)message->bounds->length) < 0
        || write(control_fd, "\n", 1) < 0 ) {}
}

int hwut_vhpi_run_into_sinks(const HwutVhpi_String* sink_out, const HwutVhpi_String* sink_err)
/* RETURN: -1000 in the CHILD made for one choice, its fd 1 and fd 2 on the
 *         two sinks -- it runs the choice and exits;
 *         the child's exit status in the parent once it ended (minus the
 *         signal that ended it); 1 where no child could be made.           */
{
    int pid, status;
    _flush();
    pid = fork();
    if( pid < 0 ) return 1;
    if( pid == 0 ) {
        int out = open(_text(0, sink_out), O_WRONLY | O_CREAT | O_TRUNC, 0644);
        int err = open(_text(1, sink_err), O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if( out < 0 || err < 0 ) _exit(1);
        dup2(out, 1); dup2(err, 2); close(out); close(err);
        close(control_fd);
        return -1000;
    }
    while( waitpid(pid, &status, 0) < 0 ) {}
    if( WIFEXITED(status) )   return WEXITSTATUS(status);
    if( WIFSIGNALED(status) ) return -WTERMSIG(status);
    return 1;
}

/* ------------------------------------------------------------------ pytext */
void hwut_vhpi_float_repr(double x)
/* RETURN: nothing; the result is 'x' as Python's repr writes it.           */
{ char b[64]; _result_text(pytext_float_repr(b, sizeof(b), x)); }

void hwut_vhpi_str_repr(const HwutVhpi_String* text)
/* RETURN: nothing; the result is the UTF-8 'text' as Python's repr(str).   */
{
    size_t n = (size_t)text->bounds->length * 4 + 3;
    char*  b = malloc(n);
    _result_text(pytext_str_repr(b, n, _text(0, text)));
    free(b);
}

void hwut_vhpi_bytes_repr(const HwutVhpi_String* data)
/* RETURN: nothing; the result is 'data' as Python's repr(bytes).           */
{
    size_t n = (size_t)data->bounds->length * 4 + 4;
    char*  b = malloc(n);
    _result_text(pytext_bytes_repr(b, n, data->base, (size_t)data->bounds->length));
    free(b);
}

/* --------------------------------------------------------------------- fsm */
static char fsm_error[FSM_ERROR_MAX];

static FsmMachine* _fsm(int h) { return (FsmMachine*)_object(h, KIND_FSM); }

static void
_list_result(const char** list, size_t n)
/* RETURN: nothing; the result is the texts of 'list', each ended by '\n'.  */
{
    size_t i, k = 0, size = 1;
    char*  text;
    for(i = 0; i < n; ++i) size += strlen(list[i]) + 1;
    text = malloc(size);
    for(i = 0; i < n; ++i) { size_t m = strlen(list[i]); memcpy(text + k, list[i], m); k += m; text[k++] = '\n'; }
    _result(text, k);
    free(text);
}

int hwut_vhpi_fsm_from_string(const HwutVhpi_String* text, int dfa_f, const HwutVhpi_String* name)
/* RETURN: the handle of the machine 'text' models, if success; 0, else --
 *         the result is the FsmError's text.                               */
{
    FsmMachine* m = FsmMachine_from_string(_text(0, text), dfa_f, _text(1, name), fsm_error, sizeof(fsm_error));
    if( ! m ) { _result_text(fsm_error); return 0; }
    return _handle_new(m, KIND_FSM);
}

void hwut_vhpi_fsm_free(int h)
/* RETURN: nothing; the machine of 'h' is gone, 'h' is free.                */
{ FsmMachine* m = _fsm(h); if( m ) { FsmMachine_free(m); _handle_free(h); } }

void hwut_vhpi_fsm_error(int h)
/* RETURN: nothing; the result is the text of the machine's last refusal.   */
{ _result_text(_fsm(h)->error); }

void hwut_vhpi_fsm_to_string(int h)
/* RETURN: nothing; the result is the model, written back as text.          */
{
    size_t size = 1 << 16;
    char*  b    = malloc(size);
    _result_text(FsmMachine_to_string(_fsm(h), b, size));
    free(b);
}

void hwut_vhpi_fsm_reset(int h)
/* RETURN: nothing; the machine stands where its run began.                 */
{ FsmMachine_reset(_fsm(h)); }

int hwut_vhpi_fsm_fire(int h, const HwutVhpi_String* event, const HwutVhpi_String* where)
/* RETURN: what 'FsmMachine_fire' returns -- 1, the event moved the machine. */
{ return FsmMachine_fire(_fsm(h), _text(0, event), _optional(1, where)); }

int hwut_vhpi_fsm_disallow(int h, const HwutVhpi_String* event, const HwutVhpi_String* state, const HwutVhpi_String* where)
/* RETURN: 0, if success; -1, else -- the machine's error says why.         */
{ return FsmMachine_disallow(_fsm(h), _text(0, event), _optional(1, state), _optional(2, where)); }

int hwut_vhpi_fsm_allow(int h, const HwutVhpi_String* event, const HwutVhpi_String* state)
/* RETURN: 0, if success; -1, else -- the machine's error says why.         */
{ return FsmMachine_allow(_fsm(h), _text(0, event), _optional(1, state)); }

int hwut_vhpi_fsm_forbid(int h, const HwutVhpi_String* state, const HwutVhpi_String* where)
/* RETURN: 0, if success; -1, else -- the machine's error says why.         */
{ return FsmMachine_forbid(_fsm(h), _text(0, state), _optional(1, where)); }

int hwut_vhpi_fsm_permit(int h, const HwutVhpi_String* state, const HwutVhpi_String* where)
/* RETURN: 0, if success; -1, else -- the machine's error says why.         */
{ return FsmMachine_permit(_fsm(h), _text(0, state), _optional(1, where)); }

int hwut_vhpi_fsm_state(int h)
/* RETURN: 1, the machine stands in one state -- the result; 0, else -- the
 *         result is the FsmError's text.                                   */
{
    const char* state = FsmMachine_state(_fsm(h));
    _result_text(state ? state : _fsm(h)->error);
    return state != NULL;
}

void hwut_vhpi_fsm_current(int h)
/* RETURN: nothing; the result is every state the machine stands in, sorted,
 *         each ended by '\n'.                                              */
{
    const char* list[1024];
    _list_result(list, FsmMachine_current(_fsm(h), list, 1024));
}

void hwut_vhpi_fsm_allowed(int h)
/* RETURN: nothing; the result is every event allowed now, sorted, each
 *         ended by '\n'.                                                   */
{
    const char* list[1024];
    _list_result(list, FsmMachine_allowed(_fsm(h), list, 1024));
}

int hwut_vhpi_fsm_in_state(int h, const HwutVhpi_String* state)
/* RETURN: 1, the machine stands in 'state'; 0, else.                       */
{ return FsmMachine_in_state(_fsm(h), _text(0, state)); }

int hwut_vhpi_fsm_can(int h, const HwutVhpi_String* event)
/* RETURN: 1, 'event' is allowed where the machine stands; 0, else.         */
{ return FsmMachine_can(_fsm(h), _text(0, event)); }

void hwut_vhpi_fsm_trace(int h)
/* RETURN: nothing; the result is the trace, one firing per line ended by
 *         '\n': where, state, event, target, separated by '\t' -- 'where'
 *         empty where it named no place.                                   */
{
    const FsmTraceEntry* trace;
    size_t i, n = FsmMachine_trace(_fsm(h), &trace), k = 0, size = 1;
    char*  text;
    for(i = 0; i < n; ++i)
        size += strlen(trace[i].where ? trace[i].where : "") + strlen(trace[i].state ? trace[i].state : "")
              + strlen(trace[i].event) + strlen(trace[i].target ? trace[i].target : "") + 4;
    text = malloc(size);
    for(i = 0; i < n; ++i)
        k += (size_t)sprintf(text + k, "%s\t%s\t%s\t%s\n", trace[i].where ? trace[i].where : "",
                             trace[i].state ? trace[i].state : "", trace[i].event,
                             trace[i].target ? trace[i].target : "");
    _result(text, k);
    free(text);
}

int hwut_vhpi_fsm_breach_n(int h)
/* RETURN: the number of breaches written so far.                           */
{ return FsmMachine_breach_n(_fsm(h)); }

int hwut_vhpi_fsm_path_to(int h, const HwutVhpi_String* state, const HwutVhpi_String* start, int masked_f)
/* RETURN: the length of the shortest path of events to 'state' -- the result
 *         its events, each ended by '\n'; -1 where none leads there.       */
{
    const char* list[1024];
    int n = FsmMachine_path_to(_fsm(h), _text(0, state), _optional(1, start), masked_f, list, 1024);
    _list_result(list, n < 0 ? 0 : (size_t)n);
    return n;
}

int hwut_vhpi_fsm_state_reachable(int h, const HwutVhpi_String* state, const HwutVhpi_String* start, int masked_f)
/* RETURN: 1, 'state' can be reached from 'start'; 0, else.                  */
{ return FsmMachine_state_reachable(_fsm(h), _text(0, state), _optional(1, start), masked_f); }

void hwut_vhpi_fsm_unreachable(int h, int masked_f)
/* RETURN: nothing; the result is every unreachable state, each ended by '\n'. */
{ const char* list[1024]; _list_result(list, FsmMachine_unreachable(_fsm(h), masked_f, list, 1024)); }

void hwut_vhpi_fsm_dead_ends(int h, int masked_f)
/* RETURN: nothing; the result is every dead end, each ended by '\n'.        */
{ const char* list[1024]; _list_result(list, FsmMachine_dead_ends(_fsm(h), masked_f, list, 1024)); }

void hwut_vhpi_fsm_forbidden_reachable(int h, int masked_f)
/* RETURN: nothing; the result is every reachable forbidden state, each
 *         ended by '\n'.                                                   */
{ const char* list[1024]; _list_result(list, FsmMachine_forbidden_reachable(_fsm(h), masked_f, list, 1024)); }

int hwut_vhpi_fsm_check(int h, int masked_f)
/* RETURN: the number of model findings, each written as a line.            */
{ return FsmMachine_check(_fsm(h), masked_f); }

int hwut_vhpi_fsm_report(int h)
/* RETURN: the number of breaches; the coverage report is written.          */
{ return FsmMachine_report(_fsm(h)); }

/* ------------------------------------------------------------------- hocon */
typedef struct { HoconNode* document; HoconFaultList fault; char* file; } HoconDocument;   /* faults point at 'file' */

static sigjmp_buf hocon_jump;
static void       _hocon_alarmed(int signal_id) { (void)signal_id; siglongjmp(hocon_jump, 1); }

static void
_timer(long microseconds)
{
    struct itimerval t;
    memset(&t, 0, sizeof(t));
    t.it_value.tv_sec  = microseconds / 1000000;
    t.it_value.tv_usec = microseconds % 1000000;
    setitimer(ITIMER_REAL, &t, NULL);
}

int hwut_vhpi_hocon_parse(const HwutVhpi_String* text, int line_offset, int column_offset,
                          const HwutVhpi_String* file, int bound_us)
/* RETURN: the handle of the parsed document, if success -- 'text' split at
 *         every '\n' (an ending one gives a last, empty line), line i
 *         numbered i + 1 + line_offset, every line 'column_offset' columns
 *         in; -1 where the parse took longer than 'bound_us' microseconds
 *         ('bound_us' 0: unbounded) -- its tree is lost.                   */
{
    static HoconSourceLine* volatile line;
    static HoconDocument*   volatile document;
    static char*            volatile copy;
    volatile size_t n = 1;
    size_t k;
    char*  p;
    copy = strdup(_text(0, text));
    for(p = copy; *p; ++p) n += *p == '\n';
    line = malloc(n * sizeof(HoconSourceLine));
    for(p = copy, k = 0; ; ) {
        char* end = strchr(p, '\n');
        line[k].text = p; line[k].line = (int)k + 1 + line_offset; line[k].column_offset = column_offset;
        ++k;
        if( ! end ) break;
        *end = '\0'; p = end + 1;
    }
    document = calloc(1, sizeof(HoconDocument));
    document->file = strdup(_text(1, file));
    HoconFaultList_init(&document->fault);
    if( bound_us > 0 ) {
        signal(SIGALRM, _hocon_alarmed);
        if( sigsetjmp(hocon_jump, 1) ) {
            HoconFaultList_free(&document->fault); free(document->file); free(document); free(line); free(copy);
            return -1;
        }
        _timer(bound_us);
    }
    document->document = Hocon_parse(line, n, document->file, &document->fault);
    if( bound_us > 0 ) _timer(0);
    /* the tree keeps no pointer into the lines: the parser copies (C-1) */
    free(line); free(copy);
    return _handle_new(document, KIND_HOCON_DOCUMENT);
}

static HoconDocument* _document(int h) { return (HoconDocument*)_object(h, KIND_HOCON_DOCUMENT); }

int hwut_vhpi_hocon_root(int h)
/* RETURN: a node handle of the document's root object.                     */
{ return _handle_new(_document(h)->document, KIND_HOCON_NODE); }

void hwut_vhpi_hocon_free(int h)
/* RETURN: nothing; the document, its faults and EVERY node handle are gone. */
{
    HoconDocument* d = _document(h);
    int            i;
    if( ! d ) return;
    for(i = 1; i < HANDLE_MAX; ++i) if( handle_kind[i] == KIND_HOCON_NODE ) _handle_free(i);
    HoconNode_free(d->document); HoconFaultList_free(&d->fault); free(d->file); free(d);
    _handle_free(h);
}

int hwut_vhpi_hocon_fault_n(int h)
/* RETURN: the number of faults the parse found.                            */
{ return (int)_document(h)->fault.n; }

void hwut_vhpi_hocon_fault(int h, int i)
/* RETURN: nothing; the result is fault 'i' as Python's str(fault) writes it,
 *         then '\n', its kind ('syntax' or 'refused'), its line and column,
 *         each ended by '\n', and its message.                             */
{
    const HoconFault* f = &_document(h)->fault.fault[i];
    size_t size = strlen(f->message) * 2 + 4096;
    char*  b    = malloc(size);
    char*  t    = malloc(size);
    snprintf(t, size, "%s\n%s\n%d\n%d\n%s", HoconFault_to_string(f, b, size),
             f->kind == HOCON_SYNTAX ? "syntax" : "refused", f->position.line, f->position.column, f->message);
    _result_text(t);
    free(b); free(t);
}

static HoconNode* _node(int h) { return (HoconNode*)_object(h, KIND_HOCON_NODE); }

void hwut_vhpi_hocon_node(int h)
/* RETURN: nothing; the result describes the node, one field per line:
 *         kind ('scalar', 'list', 'object'), line, column, count (items or
 *         entries; 0 for a scalar), Python's type name, the value's repr --
 *         and, for a scalar, its value as text (a str as it stands, a bool
 *         'True'/'False', a number as repr'd, nothing as 'None').          */
{
    const HoconNode* n = _node(h);
    size_t size = 1 << 16;
    char*  repr = malloc(size);
    char*  t    = malloc(2 * size + 256);
    const char* kind = n->kind == HOCON_OBJECT ? "object" : n->kind == HOCON_LIST ? "list" : "scalar";
    size_t count = n->kind == HOCON_OBJECT ? n->entry_n : n->kind == HOCON_LIST ? n->item_n : 0;
    int    k = snprintf(t, 2 * size + 256, "%s\n%d\n%d\n%zu\n%s\n%s\n", kind, n->position.line, n->position.column,
                        count, HoconNode_type_name(n), n->kind == HOCON_SCALAR ? HoconNode_value_repr(n, repr, size) : "");
    if( n->kind == HOCON_SCALAR ) {
        switch( n->value_kind ) {
        case HOCON_STR:  snprintf(t + k, 2 * size + 256 - (size_t)k, "%s", n->value.s); break;
        case HOCON_BOOL: snprintf(t + k, 2 * size + 256 - (size_t)k, "%s", n->value.b ? "True" : "False"); break;
        case HOCON_NULL: snprintf(t + k, 2 * size + 256 - (size_t)k, "None"); break;
        default:         snprintf(t + k, 2 * size + 256 - (size_t)k, "%s", repr); break;
        }
    }
    _result_text(t);
    free(repr); free(t);
}

int hwut_vhpi_hocon_item(int h, int i)
/* RETURN: a node handle of item 'i' of the list node 'h'.                  */
{ return _handle_new(_node(h)->item[i], KIND_HOCON_NODE); }

int hwut_vhpi_hocon_entry(int h, int i)
/* RETURN: a node handle of entry 'i' of the object node 'h'; the result is
 *         the entry's key line, key column and key, each but the last ended
 *         by '\n'.                                                         */
{
    const HoconEntry* e = &_node(h)->entry[i];
    size_t size = strlen(e->key) + 64;
    char*  t    = malloc(size);
    snprintf(t, size, "%d\n%d\n%s", e->key_position.line, e->key_position.column, e->key);
    _result_text(t);
    free(t);
    return _handle_new(e->node, KIND_HOCON_NODE);
}

void hwut_vhpi_hocon_cleandoc(const HwutVhpi_String* text)
/* RETURN: nothing; the result is 'text' laid out as inspect.cleandoc does. */
{ char* t = Hocon_cleandoc(_text(0, text)); _result_text(t); free(t); }

/* ------------------------------------------------------------------- vterm */
static VtermError vterm_error;          /* a constructor's, and the last one */
static VtermCell  vterm_cell;

/* THE CALLBACKS ARE QUEUED: C cannot call into VHDL; the VHDL face drains the
 * queue after every call that may have told something, in the order told.  */
typedef struct { int change_f; char* text; } Told;
static Told*  told;
static size_t told_n, told_capacity, told_i;

static void
_tell(int change_f, char* text)
{
    if( told_n == told_capacity ) {
        told_capacity = told_capacity ? 2 * told_capacity : 64;
        told = realloc(told, told_capacity * sizeof(Told));
    }
    told[told_n].change_f = change_f; told[told_n].text = text;
    ++told_n;
}

static void
_told_event(void* context, const VtermEvent* e)
/* RETURN: nothing; the event is queued: its text, then kind, row, column,
 *         row_end, column_end, name, value_f, value -- each after '\n'.    */
{
    char b[512], t[1024];
    (void)context;
    snprintf(t, sizeof(t), "%s\n%s\n%d\n%d\n%d\n%d\n%s\n%d\n%d", VtermEvent_to_string(e, b, sizeof(b)),
             e->kind, e->row, e->column, e->row_end, e->column_end, e->name ? e->name : "", e->value_f, e->value);
    _tell(0, strdup(t));
}

static void
_told_change(void* context, const char* name, char** line_list, size_t line_n)
/* RETURN: nothing; the change is queued: the region's name, then each line,
 *         each after '\n'.                                                 */
{
    size_t i, size = strlen(name) + 1, k;
    char*  t;
    (void)context;
    for(i = 0; i < line_n; ++i) size += strlen(line_list[i]) + 1;
    t = malloc(size);
    k = (size_t)sprintf(t, "%s", name);
    for(i = 0; i < line_n; ++i) k += (size_t)sprintf(t + k, "\n%s", line_list[i]);
    _tell(1, t);
}

int hwut_vhpi_vterm_told(void)
/* RETURN: 0, nothing more was told; 1, an event, 2, a change -- the result
 *         is its text (see '_told_event', '_told_change').                 */
{
    int kind;
    if( told_i == told_n ) { told_i = told_n = 0; return 0; }
    kind = told[told_i].change_f ? 2 : 1;
    _result_text(told[told_i].text);
    free(told[told_i].text);
    ++told_i;
    return kind;
}

static VtermScreen*
_screen(int h)
/* RETURN: the screen of handle 'h' -- a Terminal's own screen for a terminal. */
{
    if( h > 0 && h < HANDLE_MAX && handle_kind[h] == KIND_TERMINAL ) return &((VtermTerminal*)handle_object[h])->base;
    return (VtermScreen*)_object(h, KIND_SCREEN);
}

static VtermTerminal* _terminal(int h) { return (VtermTerminal*)_object(h, KIND_TERMINAL); }

static int
_failed(VtermError* error)
/* RETURN: -1; the error is the last one.                                   */
{ if( error != &vterm_error ) vterm_error = *error; return -1; }

void hwut_vhpi_vterm_error(void)
/* RETURN: nothing; the result is the last error's kind, '\n', its message. */
{
    size_t size = strlen(vterm_error.message) + 64;
    char*  t    = malloc(size);
    snprintf(t, size, "%s\n%s", vterm_error.kind, vterm_error.message);
    _result_text(t);
    free(t);
}

void hwut_vhpi_vterm_detection_text(void)
/* RETURN: nothing; the result says whether libvterm loads, and which.      */
{ char b[4096]; _result_text(Vterm_detection_text(b, sizeof(b))); }

void hwut_vhpi_vterm_reset_library(void)
/* RETURN: nothing; the next screen loads the library anew.                 */
{ Vterm_reset_library(); }

int hwut_vhpi_vterm_screen_new(int row_n, int column_n)
/* RETURN: the handle of a new screen, if success; 0, else -- see the error. */
{
    VtermScreen* s = VtermScreen_new(row_n, column_n, &vterm_error);
    return s ? _handle_new(s, KIND_SCREEN) : 0;
}

int hwut_vhpi_vterm_terminal_new(int row_n, int column_n, double settle_s)
/* RETURN: the handle of a new terminal, if success; 0, else -- see the
 *         error. Its events and changes are queued (hwut_vhpi_vterm_told). */
{
    VtermTerminal* t = VtermTerminal_new(row_n, column_n, settle_s, &vterm_error);
    if( ! t ) return 0;
    VtermTerminal_on_event(t, _told_event, NULL);
    VtermTerminal_on_change(t, _told_change, NULL);
    return _handle_new(t, KIND_TERMINAL);
}

void hwut_vhpi_vterm_free(int h)
/* RETURN: nothing; the screen or terminal of 'h' is gone -- an application
 *         it ran is ended -- and 'h' is free.                              */
{
    if( _terminal(h) )    { VtermTerminal_free(_terminal(h)); _handle_free(h); }
    else if( _screen(h) ) { VtermScreen_free(_screen(h));     _handle_free(h); }
}

int hwut_vhpi_vterm_feed(int h, const HwutVhpi_String* data)
/* RETURN: the number of bytes of 'data' the screen took.                   */
{
    size_t n = (size_t)data->bounds->length;
    if( _terminal(h) ) return (int)VtermTerminal_feed(_terminal(h), data->base, n);
    return (int)VtermScreen_feed(_screen(h), data->base, n);
}

int hwut_vhpi_vterm_cursor(int h)
/* RETURN: the cursor's place as row * 65536 + column.                      */
{ int row, column; VtermScreen_cursor(_screen(h), &row, &column); return row * 65536 + column; }

void hwut_vhpi_vterm_line(int h, int row)
/* RETURN: nothing; the result is the text of row 'row', its blanks at the
 *         end removed.                                                     */
{ char b[8192]; _result_text(VtermScreen_line(_screen(h), row, b, sizeof(b))); }

int hwut_vhpi_vterm_cell(int h, int row, int column)
/* RETURN: 0, if success -- the cell is read (hwut_vhpi_vterm_cell_*); -1,
 *         else -- the place is off the screen: see the error.              */
{
    VtermScreen* s = _screen(h);
    if( VtermScreen_cell(s, row, column, &vterm_cell) ) return _failed(&s->error);
    return 0;
}

void hwut_vhpi_vterm_cell_text(void)
/* RETURN: nothing; the result is the cell's text (UTF-8).                  */
{ _result_text(vterm_cell.text); }

void hwut_vhpi_vterm_cell_attribute_text(void)
/* RETURN: nothing; the result names the cell's attributes, ', '-joined.    */
{ char b[512]; _result_text(VtermCell_attribute_text(&vterm_cell, b, sizeof(b))); }

int hwut_vhpi_vterm_cell_field(int i)
/* RETURN: field 'i' of the cell: 0 width, 1..7 bold italic underline blink
 *         reverse conceal strike, 8 foreground_f, 9..11 its r g b, 12
 *         background_f, 13..15 its r g b.                                  */
{
    const VtermCell* c = &vterm_cell;
    switch( i ) {
    case 0: return c->width;       case 1: return c->bold_f;    case 2: return c->italic_f;
    case 3: return c->underline_f; case 4: return c->blink_f;   case 5: return c->reverse_f;
    case 6: return c->conceal_f;   case 7: return c->strike_f;  case 8: return c->foreground_f;
    case 9: case 10: case 11:      return c->foreground[i - 9];
    case 12: return c->background_f;
    case 13: case 14: case 15:     return c->background[i - 13];
    default: return 0;
    }
}

void hwut_vhpi_vterm_region(int h, const HwutVhpi_String* name, int row, int row_n, int column, int column_n)
/* RETURN: nothing; the region 'name' is watched.                           */
{ VtermTerminal_region(_terminal(h), _text(0, name), row, row_n, column, column_n); }

int hwut_vhpi_vterm_region_text(int h, const HwutVhpi_String* name)
/* RETURN: the number of lines of region 'name' -- the result each line,
 *         each ended by '\n'; -1, no region is so named: see the error.    */
{
    VtermTerminal* t = _terminal(h);
    size_t         n;
    char**         line = VtermTerminal_region_text(t, _text(0, name), &n);
    if( ! line ) return _failed(&t->base.error);
    _list_result((const char**)line, n);
    VtermTerminal_lines_free(line, n);
    return (int)n;
}

int hwut_vhpi_vterm_report(int h)
/* RETURN: the number of regions whose change was told now.                 */
{ return (int)VtermTerminal_report(_terminal(h)); }

void hwut_vhpi_vterm_answer(int h)
/* RETURN: nothing; the result is what the terminal answered and no
 *         application took, taken now.                                     */
{ size_t n; char* a = VtermTerminal_answer(_terminal(h), &n); _result(a, n); free(a); }

int hwut_vhpi_vterm_send(int h, const HwutVhpi_String* text, double react_s)
/* RETURN: what 'VtermTerminal_send' returns; -1 -- see the error.          */
{
    VtermTerminal* t = _terminal(h);
    int r = VtermTerminal_send(t, _text(0, text), react_s);
    return r < 0 ? _failed(&t->base.error) : r;
}

int hwut_vhpi_vterm_press(int h, const HwutVhpi_String* key, const HwutVhpi_String* modifier, double react_s)
/* RETURN: what 'VtermTerminal_press' returns; -1 -- see the error.         */
{
    VtermTerminal* t = _terminal(h);
    int r = VtermTerminal_press(t, _text(0, key), _optional(1, modifier), react_s);
    return r < 0 ? _failed(&t->base.error) : r;
}

int hwut_vhpi_vterm_run(int h, const HwutVhpi_String* argv, const HwutVhpi_String* cwd, double start_s)
/* RETURN: what 'VtermTerminal_run' returns -- 'argv' its words, each ended
 *         by NUL; -1 -- see the error.                                     */
{
    VtermTerminal* t = _terminal(h);
    const char*    words = _text(0, argv);
    size_t         n = (size_t)argv->bounds->length, i, k = 0;
    char**         list = malloc((n + 1) * sizeof(char*));
    int            r;
    for(i = 0; i < n; i += strlen(words + i) + 1) list[k++] = (char*)words + i;
    list[k] = NULL;
    r = VtermTerminal_run(t, list, _optional(1, cwd), start_s);
    free(list);
    return r < 0 ? _failed(&t->base.error) : r;
}

int hwut_vhpi_vterm_pump(int h, double first_s)
/* RETURN: what 'VtermTerminal_pump' returns.                               */
{ return VtermTerminal_pump(_terminal(h), first_s); }

int hwut_vhpi_vterm_expect(int h, const HwutVhpi_String* text, double timeout_s)
/* RETURN: the place 'text' was found as row * 65536 + column; -1 -- see the
 *         error.                                                           */
{
    VtermTerminal* t = _terminal(h);
    int row, column;
    if( VtermTerminal_expect(t, _text(0, text), timeout_s, &row, &column) < 0 ) return _failed(&t->base.error);
    return row * 65536 + column;
}

static int vterm_status;

int hwut_vhpi_vterm_wait(int h, double timeout_s)
/* RETURN: what 'VtermTerminal_wait' returns -- 1: the exit status is
 *         'hwut_vhpi_vterm_status'; -1 -- see the error.                   */
{
    VtermTerminal* t = _terminal(h);
    int r;
    vterm_status = 0;
    r = VtermTerminal_wait(t, timeout_s, &vterm_status);
    return r < 0 ? _failed(&t->base.error) : r;
}

int hwut_vhpi_vterm_status(void)
/* RETURN: the exit status the last 'hwut_vhpi_vterm_wait' found.            */
{ return vterm_status; }

void hwut_vhpi_vterm_close(int h)
/* RETURN: nothing; the application is ended, the terminal closed.          */
{ VtermTerminal_close(_terminal(h)); }
