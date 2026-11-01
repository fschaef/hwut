/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE C PORT'S 'hwut_vterm' AS FOREIGN PREDICATES OF SWI-PROLOG --
 *          '../c/hwut_vterm.c', unchanged, linked into one shared object
 *          that 'hwut_vterm.pro' loads ('use_foreign_library'). Prolog cannot
 *          call into libvterm, open a pseudo-terminal or wait on one with a
 *          timeout; SWI-Prolog's own foreign interface ('SWI-Prolog.h') is
 *          the way it reaches C, and the C port is what it reaches.
 *
 * Every predicate is 'hwut_vterm:$vterm_...'; the Prolog module wraps them.
 * A screen or terminal is its C address, an integer. What the C module
 * reports as an error is raised as
 *
 *     error(vterm_error(Kind, Message), _)      Kind Python's exception name
 *
 * THE CALLBACKS GO BACK INTO PROLOG while the C call that caused them runs:
 * a raw event calls 'hwut_vterm:$vterm_event(Address, Event)', a changed
 * region 'hwut_vterm:$vterm_change(Address, Name, Lines)'. An exception a
 * callback raises is kept and raised once the C call has returned.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <SWI-Prolog.h>
#include "hwut_vterm.h"

static record_t _pending = 0;            /* an exception of a callback      */

static foreign_t
_raise(const VtermError* error)
/* RETURN: FALSE, with error(vterm_error(Kind, Message), _) raised.         */
{
    term_t ex = PL_new_term_ref(), formal = PL_new_term_ref();
    if( ! PL_unify_term(formal, PL_FUNCTOR_CHARS, "vterm_error", 2,
                        PL_CHARS, error->kind, PL_UTF8_STRING, error->message) ) return FALSE;
    if( ! PL_unify_term(ex, PL_FUNCTOR_CHARS, "error", 2, PL_TERM, formal, PL_VARIABLE) ) return FALSE;
    return PL_raise_exception(ex);
}

static foreign_t
_done(int ok)
/* RETURN: 'ok', where no callback raised meanwhile; FALSE with the
 *         callback's exception raised, else.                              */
{
    if( _pending ) {
        term_t ex = PL_new_term_ref();
        PL_recorded(_pending, ex);
        PL_erase(_pending);
        _pending = 0;
        return PL_raise_exception(ex);
    }
    return ok;
}

static int
_address(term_t t, void** p)
/* RETURN: TRUE, '*p' is the C address the integer 't' holds; FALSE with a
 *         type error raised, else.                                        */
{ int64_t v; if( ! PL_get_int64_ex(t, &v) ) return FALSE; *p = (void*)(intptr_t)v; return TRUE; }

static int
_text(term_t t, char** s, size_t* n)
/* RETURN: TRUE, '*s' is the text 't' (atom, string, code list) as UTF-8 --
 *         or, for 'bytes(Codes)', those bytes as they stand.              */
{
    if( PL_is_functor(t, PL_new_functor(PL_new_atom("bytes"), 1)) ) {
        term_t a = PL_new_term_ref();
        _PL_get_arg(1, t, a);
        return PL_get_nchars(a, n, s, CVT_LIST|CVT_EXCEPTION|REP_ISO_LATIN_1|BUF_STACK);
    }
    return PL_get_nchars(t, n, s, CVT_ATOM|CVT_STRING|CVT_LIST|CVT_EXCEPTION|REP_UTF8|BUF_STACK);
}

static void
_call(const char* name, int arity, term_t args)
/* RETURN: nothing; 'hwut_vterm:<name>' was called with 'args' -- once; an
 *         exception it raised is kept for '_done'.                         */
{
    predicate_t p = PL_predicate(name, arity, "hwut_vterm");
    qid_t       q = PL_open_query(NULL, PL_Q_CATCH_EXCEPTION, p, args);
    if( ! PL_next_solution(q) ) {
        term_t ex = PL_exception(q);
        if( ex && ! _pending ) _pending = PL_record(ex);
    }
    PL_cut_query(q);
}

static void
_on_event(void* context, const VtermEvent* e)
/* RETURN: nothing; the event, as a term, went to '$vterm_event'.
 *     event(Kind, Row, Column, RowEnd, ColumnEnd, Name, Value)  -- 'none'
 *     where the field is no part of the kind                             */
{
    fid_t  f    = PL_open_foreign_frame();
    term_t args = PL_new_term_refs(2), ev = args + 1;
    term_t field = PL_new_term_refs(7);
    int    i, ok = PL_put_int64(args, (int64_t)(intptr_t)context);
    for(i = 0; i < 7; ++i) ok = ok && PL_put_atom_chars(field + i, "none");
    ok = ok && PL_put_atom_chars(field, e->kind);
    if( ! strcmp(e->kind, "damage") ) {
        ok = ok && PL_put_integer(field + 1, e->row)     && PL_put_integer(field + 2, e->column)
                && PL_put_integer(field + 3, e->row_end) && PL_put_integer(field + 4, e->column_end);
    } else if( ! strcmp(e->kind, "cursor") ) {
        ok = ok && PL_put_integer(field + 1, e->row) && PL_put_integer(field + 2, e->column)
                && PL_put_atom_chars(field + 6, e->value ? "true" : "false");
    } else if( ! strcmp(e->kind, "property") ) {
        ok = ok && PL_put_atom_chars(field + 5, e->name);
        if( e->value_f ) ok = ok && PL_put_integer(field + 6, e->value);
    }
    ok = ok && PL_cons_functor_v(ev, PL_new_functor(PL_new_atom("event"), 7), field);
    if( ok ) _call("$vterm_event", 2, args);
    PL_discard_foreign_frame(f);
}

static void
_on_change(void* context, const char* name, char** line, size_t line_n)
/* RETURN: nothing; the region's name and its lines (strings) went to
 *         '$vterm_change'.                                                 */
{
    fid_t  f    = PL_open_foreign_frame();
    term_t args = PL_new_term_refs(3), list = PL_new_term_ref(), head = PL_new_term_ref();
    size_t i;
    int    ok = PL_put_int64(args, (int64_t)(intptr_t)context)
             && PL_put_atom_chars(args + 1, name)
             && PL_put_nil(list);
    for(i = line_n; ok && i > 0; --i)
        ok = PL_put_chars(head, PL_STRING|REP_UTF8, (size_t)-1, line[i - 1]) && PL_cons_list(list, head, list);
    ok = ok && PL_put_term(args + 2, list);
    if( ok ) _call("$vterm_change", 3, args);
    PL_discard_foreign_frame(f);
}

/* ---------------------------------------------------------------- library
 *
 * EVERY 'pl_<name>' BELOW IS 'hwut_vterm:$vterm_<name>'. RETURN: TRUE, its
 * output arguments unified with what the C function of the same name
 * returned; FALSE with error(vterm_error(Kind, Message), _) raised where
 * that function failed (or a callback raised meanwhile), or with a type
 * error where an argument is no integer, number or text. What each one
 * means is said at its wrapper in 'hwut_vterm.pro'.                       */
static foreign_t
pl_detection_text(term_t text)
{ char b[4096]; return PL_unify_chars(text, PL_STRING|REP_UTF8, (size_t)-1, Vterm_detection_text(b, sizeof(b))); }

static foreign_t
pl_reset_library(void)
{ Vterm_reset_library(); return TRUE; }

/* ----------------------------------------------------------------- screen */
static foreign_t
pl_screen_new(term_t rows, term_t columns, term_t address)
{
    int r, c; VtermError error; VtermScreen* s;
    if( ! PL_get_integer_ex(rows, &r) || ! PL_get_integer_ex(columns, &c) ) return FALSE;
    if( ! (s = VtermScreen_new(r, c, &error)) ) return _raise(&error);
    return PL_unify_int64(address, (int64_t)(intptr_t)s);
}

static foreign_t
pl_screen_free(term_t address)
{ void* p; if( ! _address(address, &p) ) return FALSE; VtermScreen_free(p); return TRUE; }

static foreign_t
pl_feed(term_t address, term_t terminal_f, term_t data, term_t taken)
{
    void* p; char* s; size_t n, k; int t;
    if( ! _address(address, &p) || ! PL_get_bool_ex(terminal_f, &t) || ! _text(data, &s, &n) ) return FALSE;
    k = t ? VtermTerminal_feed(p, s, n) : VtermScreen_feed(p, s, n);
    return _done(PL_unify_int64(taken, (int64_t)k));
}

static foreign_t
pl_cursor(term_t address, term_t row, term_t column)
{
    void* p; int r, c;
    if( ! _address(address, &p) ) return FALSE;
    VtermScreen_cursor(p, &r, &c);
    return PL_unify_integer(row, r) && PL_unify_integer(column, c);
}

static int
_colour(term_t t, int set_f, const unsigned char* rgb)
/* RETURN: TRUE, 't' is 'none' (the default) or tuple([R, G, B]).           */
{
    term_t list = PL_new_term_ref(), head = PL_new_term_ref(), tuple = PL_new_term_ref();
    int    i, ok;
    if( ! set_f ) return PL_unify_atom_chars(t, "none");
    ok = PL_put_nil(list);
    for(i = 2; ok && i >= 0; --i) ok = PL_put_integer(head, rgb[i]) && PL_cons_list(list, head, list);
    return ok && PL_cons_functor(tuple, PL_new_functor(PL_new_atom("tuple"), 1), list) && PL_unify(t, tuple);
}

static foreign_t
pl_cell(term_t address, term_t row, term_t column, term_t cell)
/* cell(Text, Width, Bold, Italic, Underline, Blink, Reverse, Conceal,
 *      Strike, Foreground, Background)                                    */
{
    VtermScreen* s; int r, c, i; VtermCell x;
    term_t       a = PL_new_term_refs(11);
    if( ! _address(address, (void**)&s) || ! PL_get_integer_ex(row, &r) || ! PL_get_integer_ex(column, &c) )
        return FALSE;
    if( VtermScreen_cell(s, r, c, &x) ) return _raise(&s->error);
    {
        const int flag[7] = { x.bold_f, x.italic_f, x.underline_f, x.blink_f, x.reverse_f, x.conceal_f, x.strike_f };
        if( ! PL_unify_chars(a, PL_STRING|REP_UTF8, (size_t)-1, x.text) || ! PL_unify_integer(a + 1, x.width) )
            return FALSE;
        for(i = 0; i < 7; ++i) if( ! PL_unify_atom_chars(a + 2 + i, flag[i] ? "true" : "false") ) return FALSE;
    }
    if( ! _colour(a + 9, x.foreground_f, x.foreground) || ! _colour(a + 10, x.background_f, x.background) )
        return FALSE;
    {
        term_t t = PL_new_term_ref();
        return PL_cons_functor_v(t, PL_new_functor(PL_new_atom("cell"), 11), a) && PL_unify(cell, t);
    }
}

static foreign_t
pl_line(term_t address, term_t row, term_t text)
{
    void* p; int r; char b[4096];
    if( ! _address(address, &p) || ! PL_get_integer_ex(row, &r) ) return FALSE;
    return PL_unify_chars(text, PL_STRING|REP_UTF8, (size_t)-1, VtermScreen_line(p, r, b, sizeof(b)));
}

/* --------------------------------------------------------------- terminal */
static foreign_t
pl_terminal_new(term_t rows, term_t columns, term_t settle, term_t address)
{
    int r, c; double s; VtermError error; VtermTerminal* t;
    if( ! PL_get_integer_ex(rows, &r) || ! PL_get_integer_ex(columns, &c) || ! PL_get_float_ex(settle, &s) )
        return FALSE;
    if( ! (t = VtermTerminal_new(r, c, s, &error)) ) return _raise(&error);
    /* THE CALLBACKS ARE THE MODULE'S ONE DOOR EACH: what a test registers
     * stands on the Prolog side ('$vterm_event', '$vterm_change').        */
    VtermTerminal_on_event(t, _on_event, t);
    VtermTerminal_on_change(t, _on_change, t);
    return PL_unify_int64(address, (int64_t)(intptr_t)t);
}

static foreign_t
pl_terminal_free(term_t address)
{ void* p; if( ! _address(address, &p) ) return FALSE; VtermTerminal_free(p); return TRUE; }

static foreign_t
pl_region(term_t address, term_t name, term_t row, term_t row_n, term_t column, term_t column_n)
{
    void* p; char* s; size_t n; int a, b, c, d;
    if( ! _address(address, &p) || ! _text(name, &s, &n) || ! PL_get_integer_ex(row, &a)
        || ! PL_get_integer_ex(row_n, &b) || ! PL_get_integer_ex(column, &c) || ! PL_get_integer_ex(column_n, &d) )
        return FALSE;
    VtermTerminal_region(p, s, a, b, c, d);
    return TRUE;
}

static foreign_t
pl_region_text(term_t address, term_t name, term_t lines)
{
    VtermTerminal* t; char* s; size_t n, line_n, i; char** line;
    term_t list = PL_new_term_ref(), head = PL_new_term_ref();
    int    ok;
    if( ! _address(address, (void**)&t) || ! _text(name, &s, &n) ) return FALSE;
    if( ! (line = VtermTerminal_region_text(t, s, &line_n)) ) return _raise(&t->base.error);
    ok = PL_put_nil(list);
    for(i = line_n; ok && i > 0; --i)
        ok = PL_put_chars(head, PL_STRING|REP_UTF8, (size_t)-1, line[i - 1]) && PL_cons_list(list, head, list);
    VtermTerminal_lines_free(line, line_n);
    return ok && PL_unify(lines, list);
}

static foreign_t
pl_report(term_t address, term_t changed_n)
{
    void* p; size_t n;
    if( ! _address(address, &p) ) return FALSE;
    n = VtermTerminal_report(p);
    return _done(PL_unify_int64(changed_n, (int64_t)n));
}

static foreign_t
pl_answer(term_t address, term_t codes)
{
    void* p; size_t n; char* data; int ok;
    if( ! _address(address, &p) ) return FALSE;
    data = VtermTerminal_answer(p, &n);
    ok   = PL_unify_chars(codes, PL_CODE_LIST|REP_ISO_LATIN_1, n, data);
    free(data);
    return ok;
}

static foreign_t
pl_send(term_t address, term_t text, term_t react, term_t running)
{
    void* p; char* s; size_t n; double r; char* z;
    if( ! _address(address, &p) || ! _text(text, &s, &n) || ! PL_get_float_ex(react, &r) ) return FALSE;
    z = malloc(n + 1); memcpy(z, s, n); z[n] = '\0';
    n = (size_t)VtermTerminal_send(p, z, r);
    free(z);
    return _done(PL_unify_bool(running, (int)n));
}

static foreign_t
pl_press(term_t address, term_t key, term_t modifier, term_t react, term_t running)
{
    VtermTerminal* t; char *k, *m; size_t kn, mn; double r; int result;
    if( ! _address(address, (void**)&t) || ! PL_get_float_ex(react, &r) ) return FALSE;
    if( ! PL_get_nchars(key, &kn, &k, CVT_ATOM|CVT_STRING|CVT_EXCEPTION|REP_UTF8|BUF_MALLOC) ) return FALSE;
    if( ! PL_get_nchars(modifier, &mn, &m, CVT_ATOM|CVT_STRING|CVT_EXCEPTION|REP_UTF8|BUF_MALLOC) ) {
        PL_free(k); return FALSE;
    }
    result = VtermTerminal_press(t, k, m, r);
    PL_free(k); PL_free(m);
    if( result < 0 ) return _done(_raise(&t->base.error));
    return _done(PL_unify_bool(running, result));
}

static foreign_t
pl_run(term_t address, term_t argv, term_t cwd, term_t start, term_t running)
{
    VtermTerminal* t; double s; size_t argc = 0, i, n; int result;
    term_t  list = PL_copy_term_ref(argv), head = PL_new_term_ref();
    char**  arg;
    char*   dir = NULL;
    if( ! _address(address, (void**)&t) || ! PL_get_float_ex(start, &s) ) return FALSE;
    if( PL_skip_list(argv, 0, &argc) != PL_LIST ) return PL_type_error("list", argv);
    arg = calloc(argc + 1, sizeof(char*));
    for(i = 0; PL_get_list(list, head, list); ++i) {
        char* a;
        if( ! PL_get_nchars(head, &n, &a, CVT_ATOMIC|CVT_LIST|CVT_EXCEPTION|REP_UTF8|BUF_MALLOC) ) {
            while( i > 0 ) PL_free(arg[--i]);
            free(arg); return FALSE;
        }
        arg[i] = a;
    }
    if( PL_is_atom(cwd) && PL_get_atom_chars(cwd, &dir) && strcmp(dir, "none") == 0 ) dir = NULL;
    else if( ! PL_get_nchars(cwd, &n, &dir, CVT_ATOM|CVT_STRING|CVT_EXCEPTION|REP_UTF8|BUF_STACK) ) {
        for(i = 0; i < argc; ++i) PL_free(arg[i]);
        free(arg); return FALSE;
    }
    result = VtermTerminal_run(t, arg, dir, s);
    for(i = 0; i < argc; ++i) PL_free(arg[i]);
    free(arg);
    if( result < 0 ) return _done(_raise(&t->base.error));
    return _done(PL_unify_bool(running, result));
}

static foreign_t
pl_pump(term_t address, term_t first, term_t running)
{
    void* p; double f;
    if( ! _address(address, &p) || ! PL_get_float_ex(first, &f) ) return FALSE;
    return _done(PL_unify_bool(running, VtermTerminal_pump(p, f)));
}

static foreign_t
pl_expect(term_t address, term_t text, term_t timeout, term_t row, term_t column)
{
    VtermTerminal* t; char* s; size_t n; double d; int r, c; char* z; int result;
    if( ! _address(address, (void**)&t) || ! _text(text, &s, &n) || ! PL_get_float_ex(timeout, &d) ) return FALSE;
    z = malloc(n + 1); memcpy(z, s, n); z[n] = '\0';
    result = VtermTerminal_expect(t, z, d, &r, &c);
    free(z);
    if( result < 0 ) return _done(_raise(&t->base.error));
    return _done(PL_unify_integer(row, r) && PL_unify_integer(column, c));
}

static foreign_t
pl_wait(term_t address, term_t timeout, term_t status)
{
    VtermTerminal* t; double d; int s, result;
    if( ! _address(address, (void**)&t) || ! PL_get_float_ex(timeout, &d) ) return FALSE;
    result = VtermTerminal_wait(t, d, &s);
    if( result < 0 ) return _done(_raise(&t->base.error));
    if( result == 0 ) return _done(PL_unify_atom_chars(status, "none"));
    return _done(PL_unify_integer(status, s));
}

install_t
install_hwut_vterm4pl(void)
/* RETURN: nothing; the foreign predicates stand in module 'hwut_vterm'.    */
{
    PL_register_foreign_in_module("hwut_vterm", "$vterm_detection_text", 1, pl_detection_text, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_reset_library",  0, pl_reset_library, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_screen_new",     3, pl_screen_new, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_screen_free",    1, pl_screen_free, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_feed",           4, pl_feed, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_cursor",         3, pl_cursor, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_cell",           4, pl_cell, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_line",           3, pl_line, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_terminal_new",   4, pl_terminal_new, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_terminal_free",  1, pl_terminal_free, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_region",         6, pl_region, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_region_text",    3, pl_region_text, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_report",         2, pl_report, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_answer",         2, pl_answer, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_send",           4, pl_send, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_press",          5, pl_press, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_run",            5, pl_run, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_pump",           3, pl_pump, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_expect",         5, pl_expect, 0);
    PL_register_foreign_in_module("hwut_vterm", "$vterm_wait",           3, pl_wait, 0);
}
