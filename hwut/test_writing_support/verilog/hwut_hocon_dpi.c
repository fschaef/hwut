/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE DPI-C FACE OF '../c/hwut_hocon.c' for 'hwut_hocon.sv'. The C
 *          port parses; this file holds the lines it is given, runs the parse
 *          -- bounded in time where asked -- and lets SystemVerilog walk the
 *          tree and the faults through 'chandle's: a parse ('HwutSvParse*'),
 *          a node ('HoconNode*').
 *
 * THE BOUND: 'hwut_sv_hocon_parse(file, bound_us)' with 'bound_us' > 0 ends a
 * parse that outlasts it ('setitimer', 'siglongjmp' out of the C parser into
 * this file -- no SystemVerilog frame is crossed) and says 'hang'; the tree
 * of a hung parse is lost, as the bound is a failure anyway.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <setjmp.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include "hwut_hocon.h"

typedef struct {
    HoconNode*     document;
    HoconFaultList fault;
    char*          file;
} HwutSvParse;

static HoconSourceLine* _line;
static size_t           _line_n, _line_capacity;

void
hwut_sv_hocon_lines_clear(void)
/* RETURN: nothing; no line is held.                                        */
{
    while( _line_n ) free((char*)_line[--_line_n].text);
}

void
hwut_sv_hocon_lines_add(const char* text, int line, int column_offset)
/* RETURN: nothing; the line 'text' -- number 'line', 'column_offset' columns
 *         removed before it -- is held for the next parse.                 */
{
    if( _line_n == _line_capacity ) {
        _line_capacity = _line_capacity ? 2 * _line_capacity : 64;
        _line          = realloc(_line, _line_capacity * sizeof(HoconSourceLine));
    }
    _line[_line_n].text          = strdup(text);
    _line[_line_n].line          = line;
    _line[_line_n].column_offset = column_offset;
    _line_n += 1;
}

static sigjmp_buf _hang_jump;
static void       _alarmed(int signal_id) { (void)signal_id; siglongjmp(_hang_jump, 1); }

static void
_set_timer(long microseconds)
{
    struct itimerval t;
    memset(&t, 0, sizeof(t));
    t.it_value.tv_sec  = microseconds / 1000000;
    t.it_value.tv_usec = microseconds % 1000000;
    setitimer(ITIMER_REAL, &t, NULL);
}

void*
hwut_sv_hocon_parse(const char* file, int bound_us)
/* RETURN: the parse of the lines held, 'file' named in its faults; NULL
 *         where 'bound_us' > 0 and the parse outlasted it (a hang).        */
{
    HwutSvParse* volatile self = calloc(1, sizeof(HwutSvParse));
    self->file = strdup(file);
    HoconFaultList_init(&self->fault);
    if( bound_us <= 0 ) {
        self->document = Hocon_parse(_line, _line_n, self->file, &self->fault);
        return self;
    }
    signal(SIGALRM, _alarmed);
    if( sigsetjmp(_hang_jump, 1) ) {                /* the tree of a hung parse is lost */
        free(self->file); free(self);
        return NULL;
    }
    _set_timer(bound_us);
    self->document = Hocon_parse(_line, _line_n, self->file, &self->fault);
    _set_timer(0);
    return self;
}

void
hwut_sv_hocon_parse_free(void* parse)
/* RETURN: nothing; the parse, its tree and its faults are gone.            */
{
    HwutSvParse* self = parse;
    if( ! self ) return;
    HoconNode_free(self->document);
    HoconFaultList_free(&self->fault);
    free(self->file);
    free(self);
}

void* hwut_sv_hocon_document(void* parse)
/* RETURN: the parse's document, the outermost object.                      */
{ return ((HwutSvParse*)parse)->document; }

int hwut_sv_hocon_fault_n(void* parse)
/* RETURN: the number of the parse's faults.                                */
{ return (int)((HwutSvParse*)parse)->fault.n; }

const char*
hwut_sv_hocon_fault_field(void* parse, int i, int* kind, int* line, int* column)
/* RETURN: the i-th fault's message; '*kind' 0 SYNTAX, 1 REFUSED, '*line'
 *         and '*column' its position.                                      */
{
    const HoconFault* fault = &((HwutSvParse*)parse)->fault.fault[i];
    *kind   = fault->kind == HOCON_SYNTAX ? 0 : 1;
    *line   = fault->position.line;
    *column = fault->position.column;
    return fault->message;
}

/* ------------------------------------------------------------- the tree */
int
hwut_sv_hocon_node(void* node, int* line, int* column, int* value_kind)
/* RETURN: the node's kind -- 0 scalar, 1 list, 2 object; '*line', '*column'
 *         its position; '*value_kind' a scalar's: 0 null, 1 bool, 2 int,
 *         3 float, 4 str, 5 the parser's marker.                           */
{
    const HoconNode* self = node;
    *line       = self->position.line;
    *column     = self->position.column;
    *value_kind = (int)self->value_kind;
    return self->kind == HOCON_SCALAR ? 0 : self->kind == HOCON_LIST ? 1 : 2;
}

int hwut_sv_hocon_bool(void* node)
/* RETURN: a bool scalar's value, 0 or 1.                                   */
{ return ((HoconNode*)node)->value.b != 0; }

long long hwut_sv_hocon_int(void* node)
/* RETURN: an int scalar's value.                                           */
{ return ((HoconNode*)node)->value.i; }

double hwut_sv_hocon_float(void* node)
/* RETURN: a float scalar's value.                                          */
{ return ((HoconNode*)node)->value.f; }

const char* hwut_sv_hocon_str(void* node)
/* RETURN: a str scalar's value.                                            */
{ const char* s = ((HoconNode*)node)->value.s; return s ? s : ""; }

int hwut_sv_hocon_item_n(void* node)
/* RETURN: the number of a list's items.                                    */
{ return (int)((HoconNode*)node)->item_n; }

void* hwut_sv_hocon_item(void* node, int i)
/* RETURN: a list's i-th item.                                              */
{ return ((HoconNode*)node)->item[i]; }

int hwut_sv_hocon_entry_n(void* node)
/* RETURN: the number of an object's entries.                               */
{ return (int)((HoconNode*)node)->entry_n; }

const char*
hwut_sv_hocon_entry(void* node, int i, int* line, int* column, void** value)
/* RETURN: an object's i-th key; '*line', '*column' the key's position,
 *         '*value' its node.                                               */
{
    const HoconEntry* entry = &((HoconNode*)node)->entry[i];
    *line   = entry->key_position.line;
    *column = entry->key_position.column;
    *value  = entry->node;
    return entry->key;
}
