/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: PARSE THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE INTO THE
 *          ANNOTATED TREE -- the port of 'python/hwut_hocon.py': every key,
 *          every value and every block carries its file-relative position.
 *
 *     HoconSourceLine line[] = { { "a = 1", 1, 0 }, { "b = \"x\"", 2, 0 } };
 *     HoconFaultList  fault;
 *     HoconNode*      document;
 *     HoconFaultList_init(&fault);
 *     document = Hocon_parse(line, 2, "f.hocon", &fault);
 *     ... HoconNode_get(document, "a")->node->value.i ...
 *     HoconNode_free(document); HoconFaultList_free(&fault);
 *
 * THE SUBSET, word for word Python's: nested objects, lists, numbers in every
 * radix (with '_' as a visual helper, and roman '0rIV'), booleans
 * (true/false/yes/no), the spellings of nothing (null/nil/none/nihil), '#'
 * and '//' comments, '=' or ':' before a value, a brace directly after a key.
 * A STRING VALUE IS WRITTEN IN DOUBLE QUOTES; a text of several lines in
 * triple quotes, laid out as 'inspect.cleandoc' lays it out. 'include',
 * '${...}' and '+=' are refused by name.
 *
 * The parser accumulates faults and recovers at the next line; it never
 * fails. The fault messages are Python's, character for character.
 * _____________________________________________________________________________
 */
#ifndef HWUT_HOCON_H
#define HWUT_HOCON_H

#include <stddef.h>

typedef struct { int line; int column; } HoconPosition;

typedef enum { HOCON_SYNTAX, HOCON_REFUSED } HoconFaultKind;

typedef struct {
    HoconFaultKind kind;
    const char*    file;            /* as given to 'Hocon_parse'            */
    HoconPosition  position;
    char*          message;
} HoconFault;

typedef struct { HoconFault* fault; size_t n, capacity; } HoconFaultList;

typedef struct {
    const char* text;               /* the line, without its newline        */
    int         line;
    int         column_offset;      /* what was removed before 'text'       */
} HoconSourceLine;

typedef enum { HOCON_SCALAR, HOCON_LIST, HOCON_OBJECT } HoconNodeKind;

/* A scalar's value; HOCON_NOT_A_TOKEN only where Python's parser, too, binds
 * its '_NOT_A_TOKEN' marker into a node (a sign before a signed number).   */
typedef enum { HOCON_NULL, HOCON_BOOL, HOCON_INT, HOCON_FLOAT, HOCON_STR, HOCON_NOT_A_TOKEN } HoconValueKind;

struct HoconNode;
typedef struct { char* key; HoconPosition key_position; struct HoconNode* node; } HoconEntry;

typedef struct HoconNode {
    HoconNodeKind  kind;
    HoconPosition  position;
    /* HOCON_SCALAR */
    HoconValueKind value_kind;
    union { int b; long long i; double f; char* s; } value;
    /* HOCON_LIST */
    struct HoconNode** item;   size_t item_n, item_capacity;
    /* HOCON_OBJECT */
    HoconEntry*        entry;  size_t entry_n, entry_capacity;
} HoconNode;

void        HoconFaultList_init(HoconFaultList* self);
void        HoconFaultList_free(HoconFaultList* self);
char*       HoconFault_to_string(const HoconFault* self, char* buffer, size_t size);
char*       HoconPosition_to_string(HoconPosition self, char* buffer, size_t size);

HoconNode*  Hocon_parse(const HoconSourceLine* line, size_t line_n, const char* file, HoconFaultList* fault);
void        HoconNode_free(HoconNode* self);
HoconEntry* HoconNode_get(HoconNode* self, const char* key);
const char* HoconNode_type_name(const HoconNode* self);
char*       HoconNode_value_repr(const HoconNode* self, char* buffer, size_t size);

char*       Hocon_cleandoc(const char* text);

#endif
