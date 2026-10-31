/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The HOCON subset into the annotated tree -- see 'hwut_hocon.h'.
 *          Function for function the Python parser; its regular expressions
 *          are written out as small scanners.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include "hwut_hocon.h"
#include "hwut_pytext.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------- the faults */
void
HoconFaultList_init(HoconFaultList* self)
/* RETURN: nothing; the list is empty.                                      */
{ self->fault = NULL; self->n = 0; self->capacity = 0; }

void
HoconFaultList_free(HoconFaultList* self)
/* RETURN: nothing; every fault's message is given back, the list empty.    */
{
    size_t i;
    for(i = 0; i < self->n; ++i) free(self->fault[i].message);
    free(self->fault);
    HoconFaultList_init(self);
}

char*
HoconPosition_to_string(HoconPosition self, char* buffer, size_t size)
/* RETURN: buffer, 'line:column'.                                           */
{ snprintf(buffer, size, "%d:%d", self.line, self.column); return buffer; }

char*
HoconFault_to_string(const HoconFault* self, char* buffer, size_t size)
/* RETURN: buffer, 'file:line:column: KIND: message'.                       */
{
    snprintf(buffer, size, "%s:%d:%d: %s: %s", self->file, self->position.line, self->position.column,
             self->kind == HOCON_SYNTAX ? "SYNTAX" : "REFUSED", self->message);
    return buffer;
}

static void
_fault(HoconFaultList* list, HoconFaultKind kind, const char* file, HoconPosition position,
       const char* format, ...)
/* RETURN: nothing; one fault more stands at the list's end.                */
{
    char    message[1024];
    va_list arg;
    va_start(arg, format); vsnprintf(message, sizeof(message), format, arg); va_end(arg);
    if( list->n == list->capacity ) {
        list->capacity = list->capacity ? 2 * list->capacity : 8;
        list->fault    = realloc(list->fault, list->capacity * sizeof(HoconFault));
    }
    list->fault[list->n].kind     = kind;
    list->fault[list->n].file     = file;
    list->fault[list->n].position = position;
    list->fault[list->n].message  = strdup(message);
    list->n += 1;
}

/* -------------------------------------------------------------- the nodes */
static HoconNode*
_node(HoconNodeKind kind, HoconPosition position)
{ HoconNode* n = calloc(1, sizeof(HoconNode)); n->kind = kind; n->position = position; return n; }

static HoconNode*
_scalar(HoconValueKind value_kind, HoconPosition position)
{ HoconNode* n = _node(HOCON_SCALAR, position); n->value_kind = value_kind; return n; }

void
HoconNode_free(HoconNode* self)
/* RETURN: nothing; the node and every node below it are given back.        */
{
    size_t i;
    if( ! self ) return;
    if( self->kind == HOCON_SCALAR && self->value_kind == HOCON_STR ) free(self->value.s);
    for(i = 0; i < self->item_n; ++i) HoconNode_free(self->item[i]);
    for(i = 0; i < self->entry_n; ++i) { free(self->entry[i].key); HoconNode_free(self->entry[i].node); }
    free(self->item); free(self->entry); free(self);
}

HoconEntry*
HoconNode_get(HoconNode* self, const char* key)
/* RETURN: the entry named 'key' of the object 'self'; NULL, no such entry. */
{
    size_t i;
    for(i = 0; i < self->entry_n; ++i) if( ! strcmp(self->entry[i].key, key) ) return &self->entry[i];
    return NULL;
}

const char*
HoconNode_type_name(const HoconNode* self)
/* RETURN: the name Python's 'type(value).__name__' gives a scalar's value:
 *         'str', 'int', 'float', 'bool', 'NoneType'.                       */
{
    switch( self->value_kind ) {
    case HOCON_NULL:  return "NoneType";
    case HOCON_BOOL:  return "bool";
    case HOCON_INT:   return "int";
    case HOCON_FLOAT: return "float";
    case HOCON_STR:   return "str";
    default:          return "object";
    }
}

char*
HoconNode_value_repr(const HoconNode* self, char* buffer, size_t size)
/* RETURN: buffer, the scalar's value as Python's '%r' prints it.           */
{
    switch( self->value_kind ) {
    case HOCON_NULL:  snprintf(buffer, size, "None"); break;
    case HOCON_BOOL:  snprintf(buffer, size, "%s", pytext_bool(self->value.b)); break;
    case HOCON_INT:   snprintf(buffer, size, "%lld", self->value.i); break;
    case HOCON_FLOAT: pytext_float_repr(buffer, size, self->value.f); break;
    case HOCON_STR:   pytext_str_repr(buffer, size, self->value.s); break;
    default:          snprintf(buffer, size, "<object object>"); break;
    }
    return buffer;
}

static void
_append_item(HoconNode* list, HoconNode* item)
{
    if( list->item_n == list->item_capacity ) {
        list->item_capacity = list->item_capacity ? 2 * list->item_capacity : 4;
        list->item = realloc(list->item, list->item_capacity * sizeof(HoconNode*));
    }
    list->item[list->item_n++] = item;
}

static void
_append_entry(HoconNode* object, char* key, HoconPosition key_position, HoconNode* node)
{
    if( object->entry_n == object->entry_capacity ) {
        object->entry_capacity = object->entry_capacity ? 2 * object->entry_capacity : 4;
        object->entry = realloc(object->entry, object->entry_capacity * sizeof(HoconEntry));
    }
    object->entry[object->entry_n].key          = key;
    object->entry[object->entry_n].key_position = key_position;
    object->entry[object->entry_n].node         = node;
    object->entry_n += 1;
}

/* ------------------------------------------------------------- the cursor */
typedef struct {
    const HoconSourceLine* line_list;
    size_t                 line_n, i_line, i_col;
    const char*            text;
    size_t                 text_n;
    const char*            file;
    HoconFaultList*        fault;
} HoconCursor;

static void
HoconCursor_init(HoconCursor* self, const HoconSourceLine* line, size_t line_n, const char* file, HoconFaultList* fault)
/* RETURN: nothing; the cursor stands at the first character.               */
{
    self->line_list = line; self->line_n = line_n; self->i_line = 0; self->i_col = 0;
    self->text      = line_n ? line[0].text : "";
    self->text_n    = strlen(self->text);
    self->file      = file; self->fault = fault;
}

static int
HoconCursor_at_end(const HoconCursor* self)
/* RETURN: 1, no character remains; 0 else.                                 */
{ return self->i_line >= self->line_n; }

static int
HoconCursor_peek(const HoconCursor* self, size_t ahead)
/* RETURN: the character 'ahead' places from here on this line; '\n' at the
 *         line's end; 0 beyond the last line.                              */
{
    size_t i;
    if( self->i_line >= self->line_n ) return 0;
    i = self->i_col + ahead;
    return i < self->text_n ? (unsigned char)self->text[i] : '\n';
}

static void
HoconCursor_skip_line(HoconCursor* self)
/* RETURN: nothing; the cursor stands at the beginning of the next line.    */
{
    self->i_line += 1;
    self->i_col   = 0;
    self->text    = self->i_line < self->line_n ? self->line_list[self->i_line].text : "";
    self->text_n  = strlen(self->text);
}

static void
HoconCursor_skip(HoconCursor* self, size_t n)
/* RETURN: nothing; 'n' characters WITHIN the line are stepped over.        */
{ self->i_col += n; }

static HoconPosition
HoconCursor_position(const HoconCursor* self)
/* RETURN: the file-relative position of the character at the cursor.       */
{
    HoconPosition p;
    if( self->i_line >= self->line_n ) {
        const HoconSourceLine* last;
        if( ! self->line_n ) { p.line = 1; p.column = 1; return p; }
        last     = &self->line_list[self->line_n - 1];
        p.line   = last->line;
        p.column = last->column_offset + (int)strlen(last->text) + 1;
        return p;
    }
    p.line   = self->line_list[self->i_line].line;
    p.column = self->line_list[self->i_line].column_offset + (int)self->i_col + 1;
    return p;
}

/* -------------------------------------------------------- characters, runs */
static int
_space_f(int c)
/* RETURN: 1 for what Python's '\s' is among the ASCII characters.          */
{ return c == ' ' || (c >= '\t' && c <= '\r') || (c >= 0x1c && c <= 0x1f); }

static size_t
_token_length(const char* text, size_t text_n, size_t i)
/* RETURN: the length of the run '[^\s{}\[\]=,:"#]*' beginning at 'i'.     */
{
    size_t k = i;
    while( k < text_n && ! _space_f((unsigned char)text[k]) && ! strchr("{}[]=,:\"#", text[k]) ) ++k;
    return k - i;
}

static size_t
_blank_end(const char* text, size_t text_n, size_t i)
/* RETURN: the index of the first character at or after 'i' that is no
 *         blank.                                                           */
{
    while( i < text_n && (text[i] == ' ' || text[i] == '\t') ) ++i;
    return i;
}

static void
_strip_char(char* out, int c)
/* RETURN: nothing; 'out' holds the character -- empty for a blank, as
 *         Python's 'strip()' leaves it.                                    */
{
    if( ! c || _space_f(c) ) out[0] = '\0';
    else { out[0] = (char)c; out[1] = '\0'; }
}

static void
_skip_space(HoconCursor* cursor)
/* RETURN: nothing; blanks and a comment on the current line are skipped.  */
{
    const char* text = cursor->text;
    size_t      n = cursor->text_n, i = cursor->i_col;
    while( i < n && (text[i] == ' ' || text[i] == '\t') ) ++i;
    cursor->i_col = i;
    if( i < n && (text[i] == '#' || (text[i] == '/' && i + 1 < n && text[i + 1] == '/')) )
        HoconCursor_skip_line(cursor);
}

static void
_skip_blank(HoconCursor* cursor)
/* RETURN: nothing; blanks, newlines, commas and comments are skipped.      */
{
    while( cursor->i_line < cursor->line_n ) {
        const char* text = cursor->text;
        size_t      n = cursor->text_n, i = cursor->i_col;
        int         c;
        while( i < n && (text[i] == ' ' || text[i] == '\t' || text[i] == ',') ) ++i;
        if( i >= n ) { HoconCursor_skip_line(cursor); continue; }
        cursor->i_col = i;
        c = text[i];
        if( c == '#' || (c == '/' && i + 1 < n && text[i + 1] == '/') ) { HoconCursor_skip_line(cursor); continue; }
        return;
    }
}

/* ------------------------------------------------------------ the numbers */
static size_t
_digit_run(const char* s, size_t i, size_t n)
/* RETURN: the length of '[0-9](?:_?[0-9])*' at 'i'; 0 where none.         */
{
    size_t k = i;
    if( k >= n || s[k] < '0' || s[k] > '9' ) return 0;
    ++k;
    while( 1 ) {
        if( k < n && s[k] >= '0' && s[k] <= '9' ) { ++k; continue; }
        if( k + 1 < n && s[k] == '_' && s[k + 1] >= '0' && s[k + 1] <= '9' ) { k += 2; continue; }
        break;
    }
    return k - i;
}

static int
_decimal_f(const char* s)
/* RETURN: 1 where 's' matches Python's '_DECIMAL_RE' whole.                */
{
    size_t n = strlen(s), i = 0, d;
    if( i < n && (s[i] == '+' || s[i] == '-') ) ++i;
    if( (d = _digit_run(s, i, n)) ) {
        i += d;
        if( i < n && s[i] == '.' ) { ++i; i += _digit_run(s, i, n); }
    } else if( i < n && s[i] == '.' && (d = _digit_run(s, i + 1, n)) ) {
        i += 1 + d;
    } else return 0;
    if( i < n && (s[i] == 'e' || s[i] == 'E') ) {
        size_t k = i + 1;
        if( k < n && (s[k] == '+' || s[k] == '-') ) ++k;
        if( ! (d = _digit_run(s, k, n)) ) return 0;
        i = k + d;
    }
    return i == n;
}

static int
_roman_group(const char* s, size_t i, int group);

static int
_roman_rest(const char* s, size_t i, int group)
/* RETURN: 1 where the groups from 'group' on match 's' from 'i' to its end. */
{ return group == 4 ? s[i] == '\0' : _roman_group(s, i, group); }

static int
_roman_group(const char* s, size_t i, int group)
/* RETURN: 1 where 'M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$'
 *         matches from group 'group' on -- with the regex's backtracking.  */
{
    static const char one[] = "MCXI", five[] = " DLV", ten[] = " MCX";
    int k, f;
    if( group == 0 ) {
        for(k = 3; k >= 0; --k) {
            int j, ok = 1;
            for(j = 0; j < k; ++j) if( s[i + (size_t)j] != 'M' ) { ok = 0; break; }
            if( ok && _roman_rest(s, i + (size_t)k, 1) ) return 1;
        }
        return 0;
    }
    if( s[i] == one[group] && s[i + 1] == ten[group] && _roman_rest(s, i + 2, group + 1) ) return 1;
    if( s[i] == one[group] && s[i + 1] == five[group] && _roman_rest(s, i + 2, group + 1) ) return 1;
    for(f = 1; f >= 0; --f) {
        size_t at = i;
        if( f ) { if( s[at] != five[group] ) continue; ++at; }
        for(k = 3; k >= 0; --k) {
            int j, ok = 1;
            for(j = 0; j < k; ++j) if( s[at + (size_t)j] != one[group] ) { ok = 0; break; }
            if( ok && _roman_rest(s, at + (size_t)k, group + 1) ) return 1;
        }
    }
    return 0;
}

static int
_roman(const char* text, long long* value)
/* RETURN: 1, '*value' the number the roman numeral spells; 0, the text is
 *         no roman numeral -- 'IIII' and 'VX' among them.                  */
{
    long long total = 0; int previous = 0;
    size_t    n = strlen(text), i;
    if( ! n || ! _roman_group(text, 0, 0) ) return 0;
    for(i = n; i > 0; --i) {
        int v = 0;
        switch( text[i - 1] ) {
        case 'I': v = 1; break;    case 'V': v = 5; break;   case 'X': v = 10; break;
        case 'L': v = 50; break;   case 'C': v = 100; break; case 'D': v = 500; break;
        case 'M': v = 1000; break;
        }
        total    = v < previous ? total - v : total + v;
        previous = v > previous ? v : previous;
    }
    *value = total;
    return 1;
}

static int
_without_helper(const char* text, const char* digit_set, char* out, size_t size)
/* RETURN: 1, 'out' holds the digits with every '_' removed; 0, the text
 *         carries no digit, a character no digit of the radix, or an '_'
 *         that separates nothing.                                         */
{
    size_t n = strlen(text), i, k = 0;
    if( ! n || text[0] == '_' || text[n - 1] == '_' || strstr(text, "__") ) return 0;
    for(i = 0; i < n; ++i) {
        if( text[i] == '_' ) continue;
        if( ! strchr(digit_set, text[i]) ) return 0;
        if( k + 1 < size ) out[k++] = text[i];
    }
    out[k] = '\0';
    return k > 0;
}

static HoconValueKind
_number(const char* raw, long long* i_value, double* f_value)
/* RETURN: HOCON_INT or HOCON_FLOAT, the number the text spells, in whatever
 *         radix it spells it ('_' enters no value), in '*i_value' or
 *         '*f_value'; HOCON_NOT_A_TOKEN, it spells no number.             */
{
    const char* body = (raw[0] == '+' || raw[0] == '-') ? raw + 1 : raw;
    long long   sign = raw[0] == '-' ? -1 : 1;
    char        digit[4096];
    size_t      i, k;

    if( body[0] == '0' && (body[1] == 'r' || body[1] == 'R') ) {
        long long v;
        if( ! _roman(body + 2, &v) ) return HOCON_NOT_A_TOKEN;
        *i_value = sign * v;
        return HOCON_INT;
    }
    if( body[0] == '0' && body[1] && strchr("xXbBoO", body[1]) ) {
        int                radix = (body[1] == 'x' || body[1] == 'X') ? 16 : (body[1] == 'b' || body[1] == 'B') ? 2 : 8;
        const char*        set   = radix == 16 ? "0123456789abcdefABCDEF" : radix == 2 ? "01" : "01234567";
        unsigned long long v     = 0;
        if( ! _without_helper(body + 2, set, digit, sizeof(digit)) ) return HOCON_NOT_A_TOKEN;
        for(i = 0; digit[i]; ++i) {
            int c = digit[i];
            v = v * (unsigned long long)radix
              + (unsigned long long)(c <= '9' ? c - '0' : (c | 0x20) - 'a' + 10);
        }
        *i_value = (long long)((unsigned long long)sign * v);
        return HOCON_INT;
    }
    if( ! _decimal_f(raw) ) return HOCON_NOT_A_TOKEN;
    for(i = 0, k = 0; raw[i] && k + 1 < sizeof(digit); ++i) if( raw[i] != '_' ) digit[k++] = raw[i];
    digit[k] = '\0';
    if( strpbrk(digit, ".eE") ) { *f_value = strtod(digit, NULL); return HOCON_FLOAT; }
    *i_value = strtoll(digit, NULL, 10);
    return HOCON_INT;
}

static HoconNode*
_interpret(const char* raw, HoconPosition position)
/* RETURN: the scalar the bare text says -- null, a boolean, a number; NULL,
 *         the text is no bare token: an unquoted string, which this
 *         language has none of.                                            */
{
    static const char* null_set[] = { "null", "nil", "none", "nihil", NULL };
    const char* const* p;
    HoconNode*         node;
    long long          i_value; double f_value;
    HoconValueKind     kind;
    for(p = null_set; *p; ++p) if( ! strcmp(raw, *p) ) return _scalar(HOCON_NULL, position);
    if( ! strcmp(raw, "true") || ! strcmp(raw, "yes") ) { node = _scalar(HOCON_BOOL, position); node->value.b = 1; return node; }
    if( ! strcmp(raw, "false") || ! strcmp(raw, "no") ) { node = _scalar(HOCON_BOOL, position); node->value.b = 0; return node; }
    kind = _number(raw, &i_value, &f_value);
    if( kind == HOCON_NOT_A_TOKEN ) return NULL;
    node = _scalar(kind, position);
    if( kind == HOCON_INT ) node->value.i = i_value; else node->value.f = f_value;
    return node;
}

/* ---------------------------------------------------------------- strings */
char*
Hocon_cleandoc(const char* text)
/* RETURN: a new text, 'text' laid out as Python 3.13's 'inspect.cleandoc':
 *         tabs expanded, the blank indentation common to the lines after
 *         the first removed, the first line's leading blanks removed, empty
 *         lines at both ends dropped.                                      */
{
    size_t  n = 0, line_n = 1, i, k, column = 0, margin = (size_t)-1, first, last;
    char*   expanded;
    char**  line;
    char*   result;
    for(i = 0; text[i]; ++i) n += text[i] == '\t' ? 8 : 1;
    expanded = malloc(n + 1);
    for(i = 0, k = 0; text[i]; ++i) {
        if( text[i] == '\t' ) { do { expanded[k++] = ' '; ++column; } while( column % 8 ); }
        else { expanded[k++] = text[i]; column = (text[i] == '\n' || text[i] == '\r') ? 0 : column + 1; }
        if( text[i] == '\n' ) ++line_n;
    }
    expanded[k] = '\0';
    line = malloc(line_n * sizeof(char*));
    line[0] = expanded;
    for(i = 0, k = 1; expanded[i]; ++i) if( expanded[i] == '\n' ) { expanded[i] = '\0'; line[k++] = expanded + i + 1; }
    for(i = 1; i < line_n; ++i) {
        size_t indent = strspn(line[i], " ");
        if( line[i][indent] && indent < margin ) margin = indent;
    }
    line[0] += strspn(line[0], " ");
    if( margin != (size_t)-1 )
        for(i = 1; i < line_n; ++i) { size_t len = strlen(line[i]); line[i] += len < margin ? len : margin; }
    last = line_n;
    while( last && ! *line[last - 1] ) --last;
    first = 0;
    while( first < last && ! *line[first] ) ++first;
    for(i = first, n = 0; i < last; ++i) n += strlen(line[i]) + 1;
    result = malloc(n + 1); result[0] = '\0';
    for(i = first, k = 0; i < last; ++i) {
        size_t len = strlen(line[i]);
        memcpy(result + k, line[i], len); k += len;
        if( i + 1 < last ) result[k++] = '\n';
    }
    result[k] = '\0';
    free(line); free(expanded);
    return result;
}

static char*
_parse_triple_quoted(HoconCursor* cursor)
/* RETURN: a new text, the one between three double quotes and the next
 *         three, AS WRITTEN and laid out by 'Hocon_cleandoc'; NULL, no
 *         closing three quotes stand before the end (fault recorded).     */
{
    HoconPosition begin = HoconCursor_position(cursor);
    char*         joined = malloc(1);
    size_t        joined_n = 0, piece_n = 0;
    joined[0] = '\0';
    HoconCursor_skip(cursor, 3);
    while( ! HoconCursor_at_end(cursor) ) {
        const char* text  = cursor->text;
        size_t      from  = cursor->i_col < cursor->text_n ? cursor->i_col : cursor->text_n;
        const char* end   = strstr(text + from, "\"\"\"");
        size_t      piece = end ? (size_t)(end - text) - from : cursor->text_n - from;
        joined = realloc(joined, joined_n + piece + 2);
        if( piece_n++ ) joined[joined_n++] = '\n';
        memcpy(joined + joined_n, text + from, piece); joined_n += piece;
        joined[joined_n] = '\0';
        if( end ) {
            char* result;
            cursor->i_col = (size_t)(end - text) + 3;
            result = Hocon_cleandoc(joined);
            free(joined);
            return result;
        }
        HoconCursor_skip_line(cursor);
    }
    free(joined);
    _fault(cursor->fault, HOCON_SYNTAX, cursor->file, begin,
           "unterminated triple-quoted string: closing '\"\"\"' missing");
    return NULL;
}

static char*
_parse_quoted(HoconCursor* cursor)
/* RETURN: a new text, the string's content with escapes resolved; NULL, the
 *         string is unterminated at its line's end (fault recorded).      */
{
    HoconPosition begin = HoconCursor_position(cursor);
    const char*   text  = cursor->text;
    size_t        n = cursor->text_n, i = cursor->i_col + 1, k = 0;
    char*         piece = malloc(n + 1);
    while( 1 ) {
        int c;
        if( i >= n ) {
            _fault(cursor->fault, HOCON_SYNTAX, cursor->file, begin, "unterminated string");
            cursor->i_col = i;
            free(piece);
            return NULL;
        }
        c = (unsigned char)text[i];
        if( c == '"' ) { cursor->i_col = i + 1; piece[k] = '\0'; return piece; }
        if( c == '\\' ) {
            int e;
            i += 1;
            e = i < n ? (unsigned char)text[i] : 0;
            if( e ) piece[k++] = e == 'n' ? '\n' : e == 't' ? '\t' : (char)e;
            i += 1;
        } else { piece[k++] = (char)c; i += 1; }
    }
}

/* ----------------------------------------------------------------- values */
static HoconNode* _parse_body(HoconCursor* cursor, int terminator);
static HoconNode* _parse_value(HoconCursor* cursor, int in_list_f);

static char*
_parse_key(HoconCursor* cursor)
/* RETURN: a new text, the key; NULL, no key stands here (fault recorded). */
{
    size_t n;
    char*  key;
    if( HoconCursor_peek(cursor, 0) == '"' ) return _parse_quoted(cursor);
    n = cursor->i_col < cursor->text_n ? _token_length(cursor->text, cursor->text_n, cursor->i_col) : 0;
    if( ! n ) {
        char found[2];
        _strip_char(found, HoconCursor_peek(cursor, 0));
        _fault(cursor->fault, HOCON_SYNTAX, cursor->file, HoconCursor_position(cursor), "expected a key, found '%s'", found);
        return NULL;
    }
    key = strndup(cursor->text + cursor->i_col, n);
    HoconCursor_skip(cursor, n);
    return key;
}

static HoconNode*
_parse_bare(HoconCursor* cursor, HoconPosition position, int in_list_f)
/* RETURN: the scalar of the bare token here -- a boolean, a number, a
 *         spelling of nothing; NULL, the token is none of those (fault
 *         recorded): a string value is written in double quotes.          */
{
    const char* text = cursor->text;
    size_t      n    = cursor->text_n;
    size_t      at   = cursor->i_col < n ? cursor->i_col : n;
    size_t      raw_n = _token_length(text, n, at);
    char*       raw  = strndup(text + at, raw_n);
    char*       cut;
    HoconNode*  node;

    /* A SIGN STANDING APART from its digits: '- 0.12'. */
    if( ! strcmp(raw, "+") || ! strcmp(raw, "-") ) {
        size_t    from    = _blank_end(text, n, at + 1);
        size_t    after_n = _token_length(text, n, from);
        long long i_value; double f_value;
        if( after_n ) {
            char* after = strndup(text + from, after_n);
            if( _number(after, &i_value, &f_value) != HOCON_NOT_A_TOKEN ) {
                char*          joined = malloc(after_n + 2);
                HoconValueKind kind;
                joined[0] = raw[0]; memcpy(joined + 1, after, after_n + 1);
                cursor->i_col = from + after_n;
                kind = _number(joined, &i_value, &f_value);
                node = _scalar(kind, position);
                if( kind == HOCON_INT ) node->value.i = i_value; else if( kind == HOCON_FLOAT ) node->value.f = f_value;
                free(joined); free(after); free(raw);
                return node;
            }
            free(after);
        }
    }
    if( ! strncmp(raw, "${", 2) ) {
        _fault(cursor->fault, HOCON_REFUSED, cursor->file, HoconCursor_position(cursor),
               "substitutions '${...}' do not exist here");
        HoconCursor_skip_line(cursor);
        free(raw);
        return NULL;
    }
    if( (cut = strstr(raw, "//")) ) *cut = '\0';
    HoconCursor_skip(cursor, strlen(raw));
    if( ! *raw ) {
        free(raw);
        if( in_list_f ) {
            char found[2];
            _strip_char(found, HoconCursor_peek(cursor, 0));
            _fault(cursor->fault, HOCON_SYNTAX, cursor->file, position, "expected a value, found '%s'", found);
            return NULL;
        }
        return _scalar(HOCON_NULL, position);            /* an empty value is null */
    }
    if( ! (node = _interpret(raw, position)) )
        _fault(cursor->fault, HOCON_SYNTAX, cursor->file, position, "a string is written in double quotes: \"%s\"", raw);
    free(raw);
    return node;
}

static HoconNode*
_parse_list(HoconCursor* cursor, HoconPosition position)
/* RETURN: the list of the items up to ']'.                                 */
{
    HoconNode* list = _node(HOCON_LIST, position);
    while( 1 ) {
        int c;
        _skip_blank(cursor);
        if( HoconCursor_at_end(cursor) ) {
            _fault(cursor->fault, HOCON_SYNTAX, cursor->file, HoconCursor_position(cursor), "unterminated list: ']' missing");
            break;
        }
        c = HoconCursor_peek(cursor, 0);
        if( c == ']' ) { HoconCursor_skip(cursor, 1); break; }
        if( c == ',' ) { HoconCursor_skip(cursor, 1); continue; }
        if( c == '}' ) {
            /* A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' forgotten. */
            _fault(cursor->fault, HOCON_SYNTAX, cursor->file, HoconCursor_position(cursor),
                   "unterminated list: ']' missing before '}'");
            break;
        }
        {
            size_t     line = cursor->i_line, column = cursor->i_col;
            HoconNode* item = _parse_value(cursor, 1);
            if( item ) _append_item(list, item);
            /* NO VALUE READ AND NOTHING CONSUMED: step over what was refused. */
            else if( cursor->i_line == line && cursor->i_col == column ) HoconCursor_skip(cursor, 1);
        }
    }
    return list;
}

static HoconNode*
_parse_value(HoconCursor* cursor, int in_list_f)
/* RETURN: the value here -- a scalar, a list or an object; NULL, nothing
 *         usable stands here (fault recorded).                             */
{
    HoconPosition position;
    int           c;
    _skip_space(cursor);
    position = HoconCursor_position(cursor);
    c = HoconCursor_peek(cursor, 0);
    if( c == '{' ) { HoconCursor_skip(cursor, 1); return _parse_body(cursor, '}'); }
    if( c == '[' ) { HoconCursor_skip(cursor, 1); return _parse_list(cursor, position); }
    if( c == '"' ) {
        char*      value;
        HoconNode* node;
        if( HoconCursor_peek(cursor, 1) == '"' && HoconCursor_peek(cursor, 2) == '"' ) value = _parse_triple_quoted(cursor);
        else                                                                         value = _parse_quoted(cursor);
        if( ! value ) return NULL;
        node = _scalar(HOCON_STR, position);
        node->value.s = value;
        return node;
    }
    if( c == '$' && HoconCursor_peek(cursor, 1) == '{' ) {
        _fault(cursor->fault, HOCON_REFUSED, cursor->file, position,
               "substitutions '${...}' do not exist here: a specification refers to nothing outside its file");
        HoconCursor_skip_line(cursor);
        return NULL;
    }
    return _parse_bare(cursor, position, in_list_f);
}

static void
_parse_entry(HoconCursor* cursor, HoconNode* object)
/* RETURN: nothing; one 'key = value' pair entered 'object', or a fault was
 *         recorded and the parse recovers at the next line.               */
{
    HoconPosition key_position = HoconCursor_position(cursor);
    char*         key          = _parse_key(cursor);
    HoconNode*    node;
    int           c;
    if( ! key ) { HoconCursor_skip_line(cursor); return; }
    if( ! strcmp(key, "include") ) {
        _fault(cursor->fault, HOCON_REFUSED, cursor->file, key_position,
               "'include' does not exist here: a specification refers to nothing outside its file");
        HoconCursor_skip_line(cursor);
        free(key);
        return;
    }
    _skip_space(cursor);
    c = HoconCursor_peek(cursor, 0);
    if( c == '=' || c == ':' ) { HoconCursor_skip(cursor, 1); _skip_space(cursor); }
    else if( c == '{' ) { /* a brace binds without a sign */ }
    else if( c == '+' && HoconCursor_peek(cursor, 1) == '=' ) {
        _fault(cursor->fault, HOCON_REFUSED, cursor->file, HoconCursor_position(cursor), "'+=' does not exist here");
        HoconCursor_skip_line(cursor);
        free(key);
        return;
    } else {
        _fault(cursor->fault, HOCON_SYNTAX, cursor->file, HoconCursor_position(cursor),
               "expected '=', ':' or '{' after key '%s'", key);
        HoconCursor_skip_line(cursor);
        free(key);
        return;
    }
    /* The value parser recovers by itself; a second skip would eat a line. */
    if( ! (node = _parse_value(cursor, 0)) ) { free(key); return; }
    if( HoconNode_get(object, key) ) {
        _fault(cursor->fault, HOCON_SYNTAX, cursor->file, key_position,
               "duplicate key '%s'; the first stands, this one is refused", key);
        HoconNode_free(node); free(key);
        return;
    }
    _append_entry(object, key, key_position, node);
}

static HoconNode*
_parse_body(HoconCursor* cursor, int terminator)
/* RETURN: the object of the entries up to 'terminator' -- '}', or 0 for the
 *         end of the text.                                                 */
{
    HoconNode* result = _node(HOCON_OBJECT, HoconCursor_position(cursor));
    while( 1 ) {
        int c;
        _skip_blank(cursor);
        if( HoconCursor_at_end(cursor) ) {
            if( terminator )
                _fault(cursor->fault, HOCON_SYNTAX, cursor->file, HoconCursor_position(cursor),
                       "unterminated object: '%c' missing", terminator);
            return result;
        }
        c = HoconCursor_peek(cursor, 0);
        if( terminator && c == terminator ) { HoconCursor_skip(cursor, 1); return result; }
        if( c == '}' ) {
            _fault(cursor->fault, HOCON_SYNTAX, cursor->file, HoconCursor_position(cursor), "unmatched '}'");
            HoconCursor_skip(cursor, 1);
        } else _parse_entry(cursor, result);
    }
}

HoconNode*
Hocon_parse(const HoconSourceLine* line, size_t line_n, const char* file, HoconFaultList* fault)
/* RETURN: the document -- an object holding every entry of the outermost
 *         level, possibly none; every fault found appended to 'fault',
 *         none on a clean parse. 'file' names the file in the faults.     */
{
    HoconCursor cursor;
    HoconCursor_init(&cursor, line, line_n, file, fault);
    return _parse_body(&cursor, 0);
}
