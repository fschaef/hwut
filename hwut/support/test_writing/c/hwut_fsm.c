/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A state machine as a test's model -- see 'hwut_fsm.h'. Models are
 *          small: sets are flags over the sorted state list, and every
 *          question is a walk over a few dozen entries at most.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include "hwut_fsm.h"

#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------- the small */
static int
_compare_text(const void* a, const void* b)
{ return strcmp(*(const char* const*)a, *(const char* const*)b); }

static int
_compare_edge(const void* a, const void* b)
{
    const FsmTransition* x = a; const FsmTransition* y = b;
    int c = strcmp(x->source, y->source);
    if( ! c ) c = strcmp(x->event, y->event);
    if( ! c ) c = strcmp(x->target, y->target);
    return c;
}

static void
_say(char* error, size_t size, const char* format, ...)
/* RETURN: nothing; 'error' holds the formatted text, cut to its size.      */
{
    va_list arg;
    if( ! error || ! size ) return;
    va_start(arg, format); vsnprintf(error, size, format, arg); va_end(arg);
}

static void
_write_stdout(void* context, const char* line)
{ (void)context; printf("%s\n", line); }

static void
_write(FsmMachine* self, const char* format, ...)
/* RETURN: nothing; one formatted line went through 'self->write'.          */
{
    char    line[2048];
    va_list arg;
    va_start(arg, format); vsnprintf(line, sizeof(line), format, arg); va_end(arg);
    self->write(self->write_context, line);
}

static int
_line_f(const char* where)
/* RETURN: 1 where 'where' is a number -- it names a line.                  */
{
    const char* p = where;
    if( *p == '-' ) ++p;
    if( ! *p ) return 0;
    for(; *p; ++p) if( ! isdigit((unsigned char)*p) ) return 0;
    return 1;
}

static const char*
_where_text(char* buffer, size_t size, const char* where)
/* RETURN: buffer, ' line 3' for "3", ' <text>' for a text, '' for NULL.    */
{
    if( ! where )          buffer[0] = '\0';
    else if( _line_f(where) ) snprintf(buffer, size, " line %s", where);
    else                   snprintf(buffer, size, " %s", where);
    return buffer;
}

static const char*
_since_text(char* buffer, size_t size, const char* where)
/* RETURN: buffer, ' since line 9', ' since <text>', or '' for NULL.        */
{
    char inner[256];
    if( ! where ) { buffer[0] = '\0'; return buffer; }
    snprintf(buffer, size, " since%s", _where_text(inner, sizeof(inner), where));
    return buffer;
}

static char* _copy(const char* s) { return s ? strdup(s) : NULL; }

static long
_index_of(char** list, size_t n, const char* text)
/* RETURN: the index of 'text' in the sorted 'list'; -1 where absent.       */
{
    size_t low = 0, high = n;
    while( low < high ) {
        size_t mid = (low + high) / 2;
        int c = strcmp(list[mid], text);
        if( ! c ) return (long)mid;
        if( c < 0 ) low = mid + 1; else high = mid;
    }
    return -1;
}

static long _state_i(FsmMachine* self, const char* s) { return _index_of(self->state_list, self->state_n, s); }
static long _event_i(FsmMachine* self, const char* e) { return _index_of(self->event_list, self->event_n, e); }

/* ---------------------------------------------------------- construction */
static void
_unique_sorted(char*** list, size_t* n)
/* RETURN: nothing; '*list' is sorted and holds each text once.             */
{
    size_t i, k = 0;
    qsort(*list, *n, sizeof(char*), _compare_text);
    for(i = 0; i < *n; ++i) {
        if( k && ! strcmp((*list)[k - 1], (*list)[i]) ) { free((*list)[i]); continue; }
        (*list)[k++] = (*list)[i];
    }
    *n = k;
}

FsmMachine*
FsmMachine_new(const FsmTransition* transition, size_t transition_n,
               const char* initial, const char* const* forbidden, size_t forbidden_n,
               const char* const* final, size_t final_n, int dfa_f, const char* name,
               const char* const* state, size_t state_n,
               char* error, size_t error_size)
/* RETURN: FsmMachine standing in 'initial'; NULL where the model cannot be
 *         meant -- a DFA with two transitions for one (state, event), a
 *         forbidden or final state named nowhere else -- 'error' says why. */
{
    FsmMachine* self = calloc(1, sizeof(FsmMachine));
    size_t      i, j, cap = 2 + state_n + 2 * transition_n + forbidden_n;
    char        list[1024];

    snprintf(self->name, sizeof(self->name), "%s", name ? name : "fsm");
    self->dfa_f = dfa_f;
    self->write = _write_stdout;

    /* THE STATES: the initial, those named alone, every end of a transition */
    self->state_list = calloc(cap, sizeof(char*));
    self->state_list[self->state_n++] = _copy(initial);
    for(i = 0; i < state_n; ++i) self->state_list[self->state_n++] = _copy(state[i]);
    for(i = 0; i < transition_n; ++i) {
        self->state_list[self->state_n++] = _copy(transition[i].source);
        self->state_list[self->state_n++] = _copy(transition[i].target);
    }
    /* A DFA moves one way per (state, event): checked before anything else. */
    if( dfa_f ) {
        for(i = 0; i < transition_n; ++i) for(j = 0; j < i; ++j) {
            if( strcmp(transition[i].source, transition[j].source) || strcmp(transition[i].event, transition[j].event)
                || ! strcmp(transition[i].target, transition[j].target) ) continue;
            {   /* the smallest target standing before this one */
                const char* first = transition[j].target; size_t k;
                for(k = 0; k < i; ++k)
                    if( ! strcmp(transition[k].source, transition[i].source) && ! strcmp(transition[k].event, transition[i].event)
                        && strcmp(transition[k].target, first) < 0 ) first = transition[k].target;
                _say(error, error_size, "'%s' --(%s)--> '%s' and '%s': a DFA moves one way per event -- or 'DFA=False'",
                     transition[i].source, transition[i].event, first, transition[i].target);
            }
            for(i = 0; i < self->state_n; ++i) free(self->state_list[i]);
            free(self->state_list); free(self);
            return NULL;
        }
    }
    _unique_sorted(&self->state_list, &self->state_n);
    /* forbidden and final must be named elsewhere -- forbidden joins after. */
    {
        const char* const* chosen[2] = { forbidden, final };
        size_t             chosen_n[2] = { forbidden_n, final_n };
        const char*        label[2] = { "forbidden", "final" };
        int c;
        for(c = 0; c < 2; ++c) {
            char* unknown[64]; size_t u = 0, k = 0;
            for(i = 0; i < chosen_n[c] && u < 64; ++i)
                if( _state_i(self, chosen[c][i]) < 0 ) unknown[u++] = (char*)chosen[c][i];
            if( ! u ) continue;
            qsort(unknown, u, sizeof(char*), _compare_text);
            list[0] = '\0';
            for(i = 0; i < u; ++i) {
                if( i && ! strcmp(unknown[i], unknown[i - 1]) ) continue;
                k += (size_t)snprintf(list + k, sizeof(list) - k, "%s'%s'", k ? ", " : "", unknown[i]);
            }
            _say(error, error_size, "%s state(s) %s: named nowhere else in the model", label[c], list);
            for(i = 0; i < self->state_n; ++i) free(self->state_list[i]);
            free(self->state_list); free(self);
            return NULL;
        }
    }
    /* the model's forbidden states belong to the states too */
    for(i = 0; i < forbidden_n; ++i) self->state_list[self->state_n++] = _copy(forbidden[i]);
    _unique_sorted(&self->state_list, &self->state_n);

    self->event_list = calloc(transition_n + 1, sizeof(char*));
    for(i = 0; i < transition_n; ++i) self->event_list[self->event_n++] = _copy(transition[i].event);
    _unique_sorted(&self->event_list, &self->event_n);

    /* THE EDGES, by the canonical texts, sorted, each once */
    self->edge = calloc(transition_n + 1, sizeof(FsmTransition));
    for(i = 0; i < transition_n; ++i) {
        FsmTransition e = { self->state_list[_state_i(self, transition[i].source)],
                            self->event_list[_event_i(self, transition[i].event)],
                            self->state_list[_state_i(self, transition[i].target)] };
        self->edge[self->edge_n++] = e;
    }
    qsort(self->edge, self->edge_n, sizeof(FsmTransition), _compare_edge);
    for(i = 0, j = 0; i < self->edge_n; ++i)
        if( ! j || _compare_edge(&self->edge[j - 1], &self->edge[i]) ) self->edge[j++] = self->edge[i];
    self->edge_n = j;

    self->initial           = self->state_list[_state_i(self, initial)];
    self->model_forbidden_f = calloc(self->state_n, sizeof(int));
    self->final_f           = calloc(self->state_n, sizeof(int));
    for(i = 0; i < forbidden_n; ++i) self->model_forbidden_f[_state_i(self, forbidden[i])] = 1;
    for(i = 0; i < final_n; ++i)     self->final_f[_state_i(self, final[i])] = 1;
    for(i = 0; i < self->state_n; ++i) self->final_n += (size_t)self->final_f[i];

    self->current_f    = calloc(self->state_n, sizeof(int));
    self->visit_n      = calloc(self->state_n, sizeof(int));
    self->taken_n      = calloc(self->edge_n + 1, sizeof(int));
    self->forbid_f     = calloc(self->state_n, sizeof(int));
    self->forbid_since = calloc(self->state_n, sizeof(char*));
    self->permit_f     = calloc(self->state_n, sizeof(int));
    self->permit_since = calloc(self->state_n, sizeof(char*));
    FsmMachine_reset(self);
    return self;
}

static void
_clear_run(FsmMachine* self)
/* RETURN: nothing; the masks, the trace and the law since are forgotten.   */
{
    size_t i;
    for(i = 0; i < self->mask_n; ++i) { free(self->mask[i].state); free(self->mask[i].event); free(self->mask[i].since); }
    self->mask_n = 0;
    for(i = 0; i < self->trace_n; ++i) free(self->trace[i].where);
    self->trace_n = 0;
    for(i = 0; i < self->state_n; ++i) {
        free(self->forbid_since[i]); self->forbid_since[i] = NULL;
        free(self->permit_since[i]); self->permit_since[i] = NULL;
    }
}

void
FsmMachine_free(FsmMachine* self)
/* RETURN: nothing; the machine and all it holds are given back.            */
{
    size_t i;
    if( ! self ) return;
    _clear_run(self);
    for(i = 0; i < self->state_n; ++i) free(self->state_list[i]);
    for(i = 0; i < self->event_n; ++i) free(self->event_list[i]);
    free(self->state_list); free(self->event_list); free(self->edge);
    free(self->model_forbidden_f); free(self->final_f); free(self->current_f); free(self->visit_n);
    free(self->taken_n); free(self->forbid_f); free(self->forbid_since); free(self->permit_f);
    free(self->permit_since); free(self->mask); free(self->trace);
    free(self);
}

void
FsmMachine_reset(FsmMachine* self)
/* RETURN: nothing; the machine stands in its initial state again, under the
 *         model as written: what was seen, every mask and every state
 *         forbidden or permitted since are forgotten.                      */
{
    size_t i;
    _clear_run(self);
    for(i = 0; i < self->state_n; ++i) {
        self->current_f[i] = 0; self->visit_n[i] = 0;
        self->forbid_f[i]  = self->model_forbidden_f[i];
        self->permit_f[i]  = 0;
    }
    for(i = 0; i < self->edge_n; ++i) self->taken_n[i] = 0;
    i = (size_t)_state_i(self, self->initial);
    self->current_f[i] = 1; self->visit_n[i] = 1;
    self->breach_n = 0;
}

/* ---------------------------------------------------------------- reading */
static void
_strip(char* s)
/* RETURN: nothing; blanks at both ends of 's' are gone.                    */
{
    size_t n = strlen(s), k = 0;
    while( n && isspace((unsigned char)s[n - 1]) ) s[--n] = '\0';
    while( s[k] && isspace((unsigned char)s[k]) ) ++k;
    if( k ) memmove(s, s + k, n - k + 1);
}

static int
_name_of(const char* text, int number, char* out, size_t size, char* error, size_t error_size)
/* RETURN: 1, 'out' holds the state 'text' names -- 'A' or 'state A'; 0, it
 *         names none and 'error' says so with line 'number'.               */
{
    char  t[512]; const char* p; const char* q;
    snprintf(t, sizeof(t), "%s", text); _strip(t);
    p = t;
    if( ! strncmp(p, "state", 5) && isspace((unsigned char)p[5]) ) {
        p += 5; while( isspace((unsigned char)*p) ) ++p;
    }
    if( ! (isalpha((unsigned char)*p) || *p == '_') ) goto refused;
    for(q = p + 1; *q; ++q)
        if( ! (isalnum((unsigned char)*q) || *q == '_' || *q == '.' || *q == '-') ) goto refused;
    snprintf(out, size, "%s", p);
    return 1;
refused:
    _say(error, error_size, "line %d: '%s' names no state -- a state is a word ('A', 'state A')", number, t);
    return 0;
}

static int
_arrow_at(const char* line, size_t p, size_t* end, char* event, size_t event_size)
/* RETURN: 1 where an arrow '-+ \s* ( \s* event \s* ) \s* -* >' begins at
 *         'p' -- '*end' after it, 'event' its stripped text; 0 else.       */
{
    size_t q = p, open, close;
    if( line[q] != '-' ) return 0;
    while( line[q] == '-' ) ++q;
    while( isspace((unsigned char)line[q]) ) ++q;
    if( line[q] != '(' ) return 0;
    open = q + 1;
    for(close = open; line[close] && line[close] != ')'; ++close)
        if( line[close] == '(' ) return 0;
    if( line[close] != ')' ) return 0;
    q = close + 1;
    while( isspace((unsigned char)line[q]) ) ++q;
    while( line[q] == '-' ) ++q;
    if( line[q] != '>' ) return 0;
    *end = q + 1;
    snprintf(event, event_size, "%.*s", (int)(close - open), line + open);
    _strip(event);
    return 1;
}

typedef struct { char* text[1024]; size_t n; } _Words;
static const char* _keep(_Words* w, const char* s) { return (w->text[w->n++] = strdup(s)); }

FsmMachine*
FsmMachine_from_string(const char* text, int dfa_f, const char* name, char* error, size_t error_size)
/* RETURN: FsmMachine, the model 'text' states; NULL where it cannot be meant,
 *         'error' naming the line. One statement per line, '#' a comment:
 *         'initial:', 'forbidden:', 'final:', 'state A',
 *         'A ---( ev )---> B ---( ev2 )---> C', ':' for the state that began
 *         the line above.                                                  */
{
    _Words        word = { {0}, 0 };
    FsmTransition triple[256];
    int           line_of[256];
    size_t        triple_n = 0, k;
    const char*   alone[256];   size_t alone_n = 0;
    const char*   declared[3][128]; size_t declared_n[3] = { 0, 0, 0 };
    const char*   first = NULL; const char* previous_head = NULL;
    const char*   p = text;
    int           number = 0;
    FsmMachine*   result = NULL;
    char          name_buffer[512];

    while( *p ) {
        char        line[4096];
        const char* end = strchr(p, '\n');
        size_t      length = end ? (size_t)(end - p) : strlen(p);
        char*       hash;
        number += 1;
        snprintf(line, sizeof(line), "%.*s", (int)length, p);
        p += length + (end ? 1 : 0);
        if( (hash = strchr(line, '#')) ) *hash = '\0';
        _strip(line);
        if( ! *line ) continue;
        {   /* KEY: 'initial:', 'forbidden:', 'final:' */
            static const char* key[3] = { "initial", "forbidden", "final" };
            int c, found = -1; const char* rest = NULL;
            for(c = 0; c < 3; ++c) {
                size_t n = strlen(key[c]); const char* q = line + n;
                if( strncmp(line, key[c], n) ) continue;
                while( isspace((unsigned char)*q) ) ++q;
                if( *q != ':' ) continue;
                found = c; rest = q + 1; break;
            }
            if( found >= 0 ) {
                size_t before = declared_n[found];
                char   piece[512];
                const char* r = rest;
                while( 1 ) {
                    const char* comma = strchr(r, ',');
                    size_t n = comma ? (size_t)(comma - r) : strlen(r);
                    snprintf(piece, sizeof(piece), "%.*s", (int)n, r);
                    _strip(piece);
                    if( *piece ) {
                        if( ! _name_of(piece, number, name_buffer, sizeof(name_buffer), error, error_size) ) goto done;
                        declared[found][declared_n[found]++] = _keep(&word, name_buffer);
                    }
                    if( ! comma ) break;
                    r = comma + 1;
                }
                if( found == 0 && declared_n[0] - before != 1 ) {
                    _say(error, error_size, "line %d: 'initial:' names one state", number);
                    goto done;
                }
                continue;
            }
        }
        {   /* the parts: head, then (event, state) per arrow */
            char   part[64][512]; size_t part_n = 0, at = 0, start = 0, end_at;
            char   event[512];
            size_t i; const char* head; const char* source;
            while( line[at] ) {
                if( _arrow_at(line, at, &end_at, event, sizeof(event)) ) {
                    snprintf(part[part_n++], 512, "%.*s", (int)(at - start), line + start);
                    snprintf(part[part_n++], 512, "%s", event);
                    at = start = end_at;
                } else ++at;
            }
            snprintf(part[part_n++], 512, "%s", line + start);
            if( part_n == 1 ) {
                if( ! _name_of(line, number, name_buffer, sizeof(name_buffer), error, error_size) ) goto done;
                head = _keep(&word, name_buffer);
                if( ! first ) first = head;
                alone[alone_n++] = head;
                previous_head = head;
                continue;
            }
            for(i = 1; i < part_n; i += 2)
                if( ! *part[i] ) {
                    _say(error, error_size, "line %d: an arrow names no event -- '---( event )--->'", number);
                    goto done;
                }
            _strip(part[0]);
            if( ! strcmp(part[0], ":") ) {
                if( ! previous_head ) {
                    _say(error, error_size, "line %d: ':' stands for the state of the line above, and none stands there", number);
                    goto done;
                }
                head = previous_head;
            } else {
                if( ! _name_of(part[0], number, name_buffer, sizeof(name_buffer), error, error_size) ) goto done;
                head = _keep(&word, name_buffer);
            }
            if( ! first ) first = head;
            previous_head = head;
            source = head;
            for(i = 1; i < part_n; i += 2) {
                const char* target; const char* ev = _keep(&word, part[i]);
                if( ! _name_of(part[i + 1], number, name_buffer, sizeof(name_buffer), error, error_size) ) goto done;
                target = _keep(&word, name_buffer);
                if( dfa_f ) {   /* THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines */
                    for(k = 0; k < triple_n; ++k) {
                        if( strcmp(triple[k].source, source) || strcmp(triple[k].event, ev) ) continue;
                        if( strcmp(triple[k].target, target) ) {
                            _say(error, error_size, "line %d: '%s' --(%s)--> '%s', and line %d: --> '%s' -- a DFA moves one way per event, or 'DFA=False'",
                                 number, source, ev, target, line_of[k], triple[k].target);
                            goto done;
                        }
                        break;
                    }
                }
                triple[triple_n].source = source; triple[triple_n].event = ev; triple[triple_n].target = target;
                line_of[triple_n++] = number;
                source = target;
            }
        }
    }
    if( ! first && ! declared_n[0] ) { _say(error, error_size, "the model names no state"); goto done; }
    result = FsmMachine_new(triple, triple_n, declared_n[0] ? declared[0][0] : first,
                            declared[1], declared_n[1], declared[2], declared_n[2], dfa_f, name,
                            alone, alone_n, error, error_size);
done:
    for(k = 0; k < word.n; ++k) free(word.text[k]);
    return result;
}

char*
FsmMachine_to_string(FsmMachine* self, char* buffer, size_t size)
/* RETURN: buffer, the model in the text 'from_string' reads, one transition
 *         per line, sorted.                                                */
{
    size_t i, k = 0;
    int*   named = calloc(self->state_n, sizeof(int));
#   define ADD(...) (k += (size_t)snprintf(buffer + k, k < size ? size - k : 0, __VA_ARGS__))
    ADD("initial: %s", self->initial);
    {   int any = 0;
        for(i = 0; i < self->state_n; ++i) if( self->model_forbidden_f[i] ) {
            ADD(any ? ", %s" : "\nforbidden: %s", self->state_list[i]); any = 1; } }
    {   int any = 0;
        for(i = 0; i < self->state_n; ++i) if( self->final_f[i] ) {
            ADD(any ? ", %s" : "\nfinal: %s", self->state_list[i]); any = 1; } }
    named[_state_i(self, self->initial)] = 1;
    for(i = 0; i < self->edge_n; ++i) {
        ADD("\n%s ---( %s )---> %s", self->edge[i].source, self->edge[i].event, self->edge[i].target);
        named[_state_i(self, self->edge[i].source)] = 1;
        named[_state_i(self, self->edge[i].target)] = 1;
    }
    for(i = 0; i < self->state_n; ++i)
        if( ! named[i] && ! self->model_forbidden_f[i] ) ADD("\nstate %s", self->state_list[i]);
#   undef ADD
    free(named);
    return buffer;
}

/* ---------------------------------------------------------------- running */
static long
_mask_i(FsmMachine* self, const char* state, const char* event)
/* RETURN: the index of the mask (state | NULL for every state, event); -1. */
{
    size_t i;
    for(i = 0; i < self->mask_n; ++i) {
        FsmMask* m = &self->mask[i];
        if( strcmp(m->event, event) ) continue;
        if( (state == NULL) != (m->state == NULL) ) continue;
        if( state && strcmp(state, m->state) ) continue;
        return (long)i;
    }
    return -1;
}

static int
_masked_f(FsmMachine* self, const char* state, const char* event)
{ return _mask_i(self, NULL, event) >= 0 || _mask_i(self, state, event) >= 0; }

static int
_edge_f(FsmMachine* self, const char* state, const char* event)
{
    size_t i;
    for(i = 0; i < self->edge_n; ++i)
        if( ! strcmp(self->edge[i].source, state) && ! strcmp(self->edge[i].event, event) ) return 1;
    return 0;
}

static const char*
_here(FsmMachine* self, char* buffer, size_t size)
/* RETURN: buffer, where the machine stands: "'idle'", or "{'a', 'b'}".     */
{
    size_t i, n = 0, k = 0;
    for(i = 0; i < self->state_n; ++i) n += (size_t)self->current_f[i];
    if( n == 1 ) {
        for(i = 0; i < self->state_n; ++i)
            if( self->current_f[i] ) snprintf(buffer, size, "'%s'", self->state_list[i]);
        return buffer;
    }
    k += (size_t)snprintf(buffer, size, "{");
    for(i = 0, n = 0; i < self->state_n; ++i)
        if( self->current_f[i] ) k += (size_t)snprintf(buffer + k, size - k, "%s'%s'", n++ ? ", " : "", self->state_list[i]);
    snprintf(buffer + k, size - k, "}");
    return buffer;
}

size_t
FsmMachine_allowed(FsmMachine* self, const char** out, size_t out_n)
/* RETURN: the number of events that would move the machine now; the first
 *         'out_n' of them, sorted, in 'out'.                               */
{
    size_t e, i, n = 0;
    for(e = 0; e < self->event_n; ++e) {
        for(i = 0; i < self->edge_n; ++i) {
            const FsmTransition* edge = &self->edge[i];
            if( strcmp(edge->event, self->event_list[e]) ) continue;
            if( ! self->current_f[_state_i(self, edge->source)] ) continue;
            if( _masked_f(self, edge->source, edge->event) ) continue;
            if( n < out_n ) out[n] = self->event_list[e];
            ++n; break;
        }
    }
    return n;
}

static void
_trace_add(FsmMachine* self, const char* where, const FsmTransition* edge)
{
    if( self->trace_n == self->trace_capacity ) {
        self->trace_capacity = self->trace_capacity ? 2 * self->trace_capacity : 16;
        self->trace = realloc(self->trace, self->trace_capacity * sizeof(FsmTraceEntry));
    }
    self->trace[self->trace_n].where  = _copy(where);
    self->trace[self->trace_n].state  = edge->source;
    self->trace[self->trace_n].event  = edge->event;
    self->trace[self->trace_n].target = edge->target;
    self->trace_n += 1;
}

int
FsmMachine_fire(FsmMachine* self, const char* event, const char* where)
/* RETURN: 1, 'event' moved the machine and entered no forbidden state;
 *         0, it was not allowed where the machine stands -- a BREACH line
 *            is written and the machine stays -- or it entered a forbidden
 *            state, which is written too.                                  */
{
    int*        moved = calloc(self->state_n, sizeof(int));
    const char* masked = NULL;
    size_t      s, i, moved_n = 0;
    char        w[300], here[1024], since[300];
    int         entered = 0;

    for(s = 0; s < self->state_n; ++s) {
        const char* state = self->state_list[s];
        if( ! self->current_f[s] ) continue;
        if( _masked_f(self, state, event) ) {
            if( ! masked && _edge_f(self, state, event) ) masked = state;
            continue;
        }
        for(i = 0; i < self->edge_n; ++i) {
            if( strcmp(self->edge[i].source, state) || strcmp(self->edge[i].event, event) ) continue;
            moved[_state_i(self, self->edge[i].target)] = 1;
            self->taken_n[i] += 1;
            _trace_add(self, where, &self->edge[i]);
        }
    }
    for(s = 0; s < self->state_n; ++s) moved_n += (size_t)moved[s];
    if( ! moved_n ) {
        char        hint[1024]; const char* allowed[128];
        size_t      n = FsmMachine_allowed(self, allowed, 128), k = 0;
        self->breach_n += 1;
        if( n ) {
            k += (size_t)snprintf(hint, sizeof(hint), "allowed: ");
            for(i = 0; i < n; ++i) k += (size_t)snprintf(hint + k, sizeof(hint) - k, "%s%s", i ? ", " : "", allowed[i]);
        } else snprintf(hint, sizeof(hint), "no event leaves it");
        if( _event_i(self, event) < 0 ) snprintf(hint, sizeof(hint), "an event the model never names");
        else if( masked ) {
            long        own = _mask_i(self, masked, event);
            long        all = _mask_i(self, NULL, event);
            const char* when = own >= 0 ? self->mask[own].since : (all >= 0 ? self->mask[all].since : NULL);
            snprintf(hint, sizeof(hint), "disallowed%s", _since_text(since, sizeof(since), when));
        }
        _write(self, "BREACH%s: '%s' in %s -- %s", _where_text(w, sizeof(w), where), event,
               _here(self, here, sizeof(here)), hint);
        free(moved);
        return 0;
    }
    for(s = 0; s < self->state_n; ++s) {
        self->current_f[s] = moved[s];
        if( moved[s] ) self->visit_n[s] += 1;
    }
    for(s = 0; s < self->state_n; ++s) {
        if( ! moved[s] || ! self->forbid_f[s] ) continue;
        self->breach_n += 1; entered = 1;
        if( self->model_forbidden_f[s] && ! self->forbid_since[s] )
            _write(self, "BREACH%s: '%s' entered by '%s' -- a forbidden state",
                   _where_text(w, sizeof(w), where), self->state_list[s], event);
        else
            _write(self, "BREACH%s: '%s' entered by '%s' -- forbidden%s", _where_text(w, sizeof(w), where),
                   self->state_list[s], event, _since_text(since, sizeof(since), self->forbid_since[s]));
    }
    free(moved);
    return ! entered;
}

/* ------------------------------------------------------- the law, changing */
static int
_known(FsmMachine* self, const char* event, const char* state)
/* RETURN: 0 where 'event' and 'state' are named by the model; -1 else, and
 *         'self->error' names what is not.                                 */
{
    char   list[2048]; size_t i, k = 0;
    if( event && _event_i(self, event) < 0 ) {
        for(i = 0; i < self->event_n; ++i) k += (size_t)snprintf(list + k, sizeof(list) - k, "%s%s", i ? ", " : "", self->event_list[i]);
        _say(self->error, sizeof(self->error), "'%s': an event the model never names -- events: %s", event, k ? list : "");
        return -1;
    }
    if( state && _state_i(self, state) < 0 ) {
        for(i = 0; i < self->state_n; ++i) k += (size_t)snprintf(list + k, sizeof(list) - k, "%s%s", i ? ", " : "", self->state_list[i]);
        _say(self->error, sizeof(self->error), "'%s': a state the model never names -- states: %s", state, k ? list : "");
        return -1;
    }
    return 0;
}

int
FsmMachine_disallow(FsmMachine* self, const char* event, const char* state, const char* where)
/* RETURN: 0; from now on 'event' is a breach -- in 'state' alone, in every
 *         state where NULL -- until 'allow'. -1 where the model names no
 *         such event or state.                                             */
{
    if( _known(self, event, state) ) return -1;
    if( _mask_i(self, state, event) >= 0 ) return 0;
    if( self->mask_n == self->mask_capacity ) {
        self->mask_capacity = self->mask_capacity ? 2 * self->mask_capacity : 8;
        self->mask = realloc(self->mask, self->mask_capacity * sizeof(FsmMask));
    }
    self->mask[self->mask_n].state = _copy(state);
    self->mask[self->mask_n].event = _copy(event);
    self->mask[self->mask_n].since = _copy(where);
    self->mask_n += 1;
    return 0;
}

int
FsmMachine_allow(FsmMachine* self, const char* event, const char* state)
/* RETURN: 0; the mask 'disallow(event, state)' set is lifted, a mask of
 *         another scope stays. -1 where the model names no such word.      */
{
    long i;
    if( _known(self, event, state) ) return -1;
    if( (i = _mask_i(self, state, event)) < 0 ) return 0;
    free(self->mask[i].state); free(self->mask[i].event); free(self->mask[i].since);
    memmove(&self->mask[i], &self->mask[i + 1], (self->mask_n - (size_t)i - 1) * sizeof(FsmMask));
    self->mask_n -= 1;
    return 0;
}

int
FsmMachine_forbid(FsmMachine* self, const char* state, const char* where)
/* RETURN: 0; entering 'state' is a breach from now on, until 'permit'; where
 *         the machine STANDS in it, one BREACH line at once. -1 where the
 *         model names no such state.                                       */
{
    long s; char w[300], since[300];
    if( _known(self, NULL, state) ) return -1;
    s = _state_i(self, state);
    if( self->forbid_f[s] ) return 0;
    self->forbid_f[s] = 1;
    free(self->forbid_since[s]); self->forbid_since[s] = _copy(where);
    self->permit_f[s] = 0; free(self->permit_since[s]); self->permit_since[s] = NULL;
    if( self->current_f[s] ) {
        self->breach_n += 1;
        _write(self, "BREACH%s: stands in '%s' -- forbidden%s", _where_text(w, sizeof(w), where),
               state, _since_text(since, sizeof(since), where));
    }
    return 0;
}

int
FsmMachine_permit(FsmMachine* self, const char* state, const char* where)
/* RETURN: 0; 'state' is no longer forbidden -- a state of the model's own
 *         'forbidden:' too, until 'forbid' again. -1 where unknown.        */
{
    long s;
    if( _known(self, NULL, state) ) return -1;
    s = _state_i(self, state);
    if( ! self->forbid_f[s] ) return 0;
    self->forbid_f[s] = 0; free(self->forbid_since[s]); self->forbid_since[s] = NULL;
    if( self->model_forbidden_f[s] ) {
        self->permit_f[s] = 1; free(self->permit_since[s]); self->permit_since[s] = _copy(where);
    }
    return 0;
}

int
FsmMachine_disallowed(FsmMachine* self, const char* event, const char* state, const char* where,
                      void (*block)(void* context), void* context)
/* RETURN: 0 once 'block(context)' ran with 'event' disallowed, and it is
 *         allowed again; -1 where the model names no such word.           */
{
    if( FsmMachine_disallow(self, event, state, where) ) return -1;
    block(context);
    return FsmMachine_allow(self, event, state);
}

int
FsmMachine_forbidding(FsmMachine* self, const char* state, const char* where,
                      void (*block)(void* context), void* context)
/* RETURN: 0 once 'block(context)' ran with 'state' forbidden, and it is
 *         permitted again; -1 where the model names no such state.        */
{
    if( FsmMachine_forbid(self, state, where) ) return -1;
    block(context);
    return FsmMachine_permit(self, state, NULL);
}

/* -------------------------------------------------------------- questions */
const char*
FsmMachine_state(FsmMachine* self)
/* RETURN: the one state the machine stands in; NULL where it stands in a
 *         set (dfa_f 0) -- 'self->error' says so.                          */
{
    size_t i, n = 0; const char* one = NULL; char here[1024];
    for(i = 0; i < self->state_n; ++i) if( self->current_f[i] ) { one = self->state_list[i]; ++n; }
    if( n == 1 ) return one;
    _say(self->error, sizeof(self->error), "the machine stands in %s: ask 'current()'", _here(self, here, sizeof(here)));
    return NULL;
}

size_t
FsmMachine_current(FsmMachine* self, const char** out, size_t out_n)
/* RETURN: the number of states the machine stands in; the first 'out_n',
 *         sorted, in 'out'.                                                */
{
    size_t i, n = 0;
    for(i = 0; i < self->state_n; ++i) if( self->current_f[i] ) { if( n < out_n ) out[n] = self->state_list[i]; ++n; }
    return n;
}

int
FsmMachine_in_state(FsmMachine* self, const char* state)
/* RETURN: 1 where the machine stands in 'state'; 0 else.                   */
{ long s = _state_i(self, state); return s >= 0 && self->current_f[s]; }

int
FsmMachine_can(FsmMachine* self, const char* event)
/* RETURN: 1 where 'event' would move the machine now; 0 else.              */
{
    size_t i;
    for(i = 0; i < self->edge_n; ++i)
        if( ! strcmp(self->edge[i].event, event) && self->current_f[_state_i(self, self->edge[i].source)]
            && ! _masked_f(self, self->edge[i].source, event) ) return 1;
    return 0;
}

size_t
FsmMachine_trace(FsmMachine* self, const FsmTraceEntry** out)
/* RETURN: the number of transitions fired; '*out' the entries, in order.   */
{ *out = self->trace; return self->trace_n; }

int
FsmMachine_breach_n(FsmMachine* self)
/* RETURN: the breaches written so far.                                     */
{ return self->breach_n; }

/* -------------------------------------------------------- the model alone */
int
FsmMachine_path_to(FsmMachine* self, const char* state, const char* start, int masked_f,
                   const char** out, size_t out_n)
/* RETURN: the length of the shortest path of events from 'start' -- the
 *         initial state where NULL, "now" for where the machine stands --
 *         into 'state', the events in 'out' (0 where 'start' is 'state');
 *         -1 where no path leads there. Among equally short paths the first
 *         in event order; under the masks where 'masked_f'.                */
{
    size_t  n = self->state_n, head = 0, tail = 0, i;
    long*   queue  = malloc(sizeof(long) * (n + 1));
    long*   parent = malloc(sizeof(long) * n);
    long*   via    = malloc(sizeof(long) * n);              /* edge index    */
    int*    seen   = calloc(n, sizeof(int));
    long    goal   = _state_i(self, state), found = -1;
    int     length = -1;

    for(i = 0; i < n; ++i) {
        int in_f = start == NULL ? self->state_list[i] == self->initial
                 : ! strcmp(start, "now") ? self->current_f[i]
                 : ! strcmp(start, self->state_list[i]);
        if( ! in_f ) continue;
        if( (long)i == goal ) { length = 0; goto done; }
        seen[i] = 1; parent[i] = -1; queue[tail++] = (long)i;
    }
    while( head < tail && found < 0 ) {
        long here = queue[head++];
        /* successors of 'here', sorted by (event, target): the edge order */
        for(i = 0; i < self->edge_n && found < 0; ++i) {
            const FsmTransition* e = &self->edge[i];
            long t;
            if( strcmp(e->source, self->state_list[here]) ) continue;
            if( masked_f && _masked_f(self, e->source, e->event) ) continue;
            t = _state_i(self, e->target);
            if( seen[t] ) continue;
            seen[t] = 1; parent[t] = here; via[t] = (long)i;
            if( t == goal ) { found = t; break; }
            queue[tail++] = t;
        }
    }
    if( found >= 0 ) {
        long at = found; int k = 0;
        while( parent[at] >= 0 ) { ++k; at = parent[at]; }
        length = k;
        for(at = found; parent[at] >= 0; at = parent[at]) {
            --k;
            if( (size_t)k < out_n ) out[k] = self->edge[via[at]].event;
        }
    }
done:
    free(queue); free(parent); free(via); free(seen);
    return length;
}

int
FsmMachine_state_reachable(FsmMachine* self, const char* state, const char* start, int masked_f)
/* RETURN: 1 where 'state' can be reached from 'start' (see 'path_to'); 0.  */
{ const char* path[256]; return FsmMachine_path_to(self, state, start, masked_f, path, 256) >= 0; }

static int
_forbidden_at(FsmMachine* self, size_t s, int masked_f)
{ return masked_f ? self->forbid_f[s] : self->model_forbidden_f[s]; }

size_t
FsmMachine_unreachable(FsmMachine* self, int masked_f, const char** out, size_t out_n)
/* RETURN: the number of states no path from the initial state reaches,
 *         forbidden ones left out; the first 'out_n', sorted, in 'out'.    */
{
    size_t s, n = 0;
    for(s = 0; s < self->state_n; ++s) {
        if( _forbidden_at(self, s, masked_f) ) continue;
        if( FsmMachine_state_reachable(self, self->state_list[s], NULL, masked_f) ) continue;
        if( n < out_n ) out[n] = self->state_list[s];
        ++n;
    }
    return n;
}

size_t
FsmMachine_dead_ends(FsmMachine* self, int masked_f, const char** out, size_t out_n)
/* RETURN: the number of states no event leaves that are neither final nor
 *         forbidden; the first 'out_n', sorted, in 'out'.                  */
{
    size_t s, i, n = 0;
    for(s = 0; s < self->state_n; ++s) {
        int leaves_f = 0;
        for(i = 0; i < self->edge_n; ++i)
            if( ! strcmp(self->edge[i].source, self->state_list[s])
                && ! (masked_f && _masked_f(self, self->edge[i].source, self->edge[i].event)) ) { leaves_f = 1; break; }
        if( leaves_f || self->final_f[s] || _forbidden_at(self, s, masked_f) ) continue;
        if( n < out_n ) out[n] = self->state_list[s];
        ++n;
    }
    return n;
}

size_t
FsmMachine_forbidden_reachable(FsmMachine* self, int masked_f, const char** out, size_t out_n)
/* RETURN: the number of forbidden states the model lets the system reach
 *         from the initial state; the first 'out_n', sorted, in 'out'.     */
{
    size_t s, n = 0;
    for(s = 0; s < self->state_n; ++s) {
        if( ! _forbidden_at(self, s, masked_f) ) continue;
        if( ! FsmMachine_state_reachable(self, self->state_list[s], NULL, masked_f) ) continue;
        if( n < out_n ) out[n] = self->state_list[s];
        ++n;
    }
    return n;
}

int
FsmMachine_check(FsmMachine* self, int masked_f)
/* RETURN: the number of findings the MODEL has, each written as one line
 *         'MODEL: ...'; 0 where it has none.                               */
{
    const char* list[256]; const char* path[256];
    size_t      n, i; int count = 0, k, length;
    char        text[2048];
    n = FsmMachine_unreachable(self, masked_f, list, 256);
    for(i = 0; i < n; ++i, ++count) _write(self, "MODEL: '%s' cannot be reached", list[i]);
    n = FsmMachine_dead_ends(self, masked_f, list, 256);
    for(i = 0; i < n; ++i, ++count) _write(self, "MODEL: '%s' is a dead end -- no event leaves it", list[i]);
    n = FsmMachine_forbidden_reachable(self, masked_f, list, 256);
    for(i = 0; i < n; ++i, ++count) {
        size_t at = 0;
        length = FsmMachine_path_to(self, list[i], NULL, masked_f, path, 256);
        text[0] = '\0';
        for(k = 0; k < length; ++k) at += (size_t)snprintf(text + at, sizeof(text) - at, "%s%s", k ? " " : "", path[k]);
        _write(self, "MODEL: forbidden '%s' is reachable: %s", list[i], text);
    }
    return count;
}

/* ---------------------------------------------------------------- the end */
static int
_compare_mask(const void* a, const void* b)
/* RETURN: the order of two masks by (event, state), every state as ''.    */
{
    const FsmMask* x = a; const FsmMask* y = b;
    int c = strcmp(x->event, y->event);
    return c ? c : strcmp(x->state ? x->state : "", y->state ? y->state : "");
}

int
FsmMachine_report(FsmMachine* self)
/* RETURN: the breaches seen, counting a non-final end; written before it,
 *         sorted, what the events covered of the model -- states counted
 *         without the model's forbidden ones.                              */
{
    size_t  s, i, goal = 0, visited = 0, taken = 0;
    int     breach_n = self->breach_n, end_f = self->final_n == 0;
    char    here[1024], since[300], suffix[32];
    FsmMask* mask;

    for(s = 0; s < self->state_n; ++s) if( self->current_f[s] && self->final_f[s] ) end_f = 1;
    if( ! end_f ) breach_n += 1;
    for(s = 0; s < self->state_n; ++s) {
        if( self->model_forbidden_f[s] ) continue;
        ++goal; if( self->visit_n[s] ) ++visited;
    }
    for(i = 0; i < self->edge_n; ++i) if( self->taken_n[i] ) ++taken;
    _write(self, "%s: %zu of %zu states visited, %zu of %zu transitions taken, %d breach%s",
           self->name, visited, goal, taken, self->edge_n, breach_n, breach_n == 1 ? "" : "es");
    for(i = 0; i < self->edge_n; ++i) {
        int n = self->taken_n[i];
        if( n > 1 ) snprintf(suffix, sizeof(suffix), "   x%d", n); else suffix[0] = '\0';
        _write(self, "  %s  %s ---( %s )---> %s%s", n ? "taken    " : "not taken",
               self->edge[i].source, self->edge[i].event, self->edge[i].target, suffix);
    }
    for(s = 0; s < self->state_n; ++s)
        if( ! self->visit_n[s] && ! self->model_forbidden_f[s] ) _write(self, "  never in   '%s'", self->state_list[s]);
    _write(self, "  ended in   %s", _here(self, here, sizeof(here)));
    mask = malloc(sizeof(FsmMask) * (self->mask_n + 1));
    if( self->mask_n ) memcpy(mask, self->mask, sizeof(FsmMask) * self->mask_n);
    qsort(mask, self->mask_n, sizeof(FsmMask), _compare_mask);
    for(i = 0; i < self->mask_n; ++i) {
        char scope[300];
        if( mask[i].state ) snprintf(scope, sizeof(scope), "in '%s'", mask[i].state);
        else                snprintf(scope, sizeof(scope), "in every state");
        _write(self, "  disallowed '%s' %s%s", mask[i].event, scope, _since_text(since, sizeof(since), mask[i].since));
    }
    free(mask);
    for(s = 0; s < self->state_n; ++s)
        if( self->forbid_f[s] && ! self->model_forbidden_f[s] )
            _write(self, "  forbidden  '%s'%s", self->state_list[s], _since_text(since, sizeof(since), self->forbid_since[s]));
    for(s = 0; s < self->state_n; ++s)
        if( self->permit_f[s] )
            _write(self, "  permitted  '%s'%s", self->state_list[s], _since_text(since, sizeof(since), self->permit_since[s]));
    if( ! end_f ) {
        char final[1024]; size_t k = 0; final[0] = '\0';
        for(s = 0; s < self->state_n; ++s)
            if( self->final_f[s] ) k += (size_t)snprintf(final + k, sizeof(final) - k, "%s%s", k ? ", " : "", self->state_list[s]);
        _write(self, "BREACH: ended in %s -- final: %s", _here(self, here, sizeof(here)), final);
    }
    return breach_n;
}
