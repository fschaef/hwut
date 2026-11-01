/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C side of 'hwutvterm' -- see 'vterm_library.h'.
 * _____________________________________________________________________________
 */
#define _GNU_SOURCE
#include "vterm_library.h"
#include "_cgo_export.h"

#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DAMAGE_MERGE_ROW 1

/* ------------------------------------------- the library's own structures */
typedef struct { int row; int col; } _Position;                               /* VTermPos  */
typedef struct { int start_row, end_row, start_col, end_col; } _Rectangle;    /* VTermRect */

typedef struct {                                         /* VTermScreenCallbacks */
    int  (*damage)(_Rectangle rectangle, void* user);
    int  (*moverect)(_Rectangle destination, _Rectangle source, void* user);
    int  (*movecursor)(_Position position, _Position old, int visible, void* user);
    int  (*settermprop)(int property, int* value, void* user);
    int  (*bell)(void* user);
    void*  resize;
    void*  sb_pushline;
    void*  sb_popline;
    void*  spare[8];                    /* what later versions append: null */
} _ScreenCallbacks;

static struct {
    void*  handle;
    void*  (*vterm_new)(int, int);
    void   (*vterm_free)(void*);
    void   (*vterm_set_utf8)(void*, int);
    size_t (*vterm_input_write)(void*, const char*, size_t);
    void*  (*vterm_obtain_screen)(void*);
    void*  (*vterm_obtain_state)(void*);
    void   (*vterm_screen_reset)(void*, int);
    void   (*vterm_screen_enable_altscreen)(void*, int);
    int    (*vterm_screen_get_cell)(void*, _Position, void*);
    void   (*vterm_state_get_cursorpos)(void*, _Position*);
    void   (*vterm_output_set_callback)(void*, void (*)(const char*, size_t, void*), void*);
    void   (*vterm_keyboard_unichar)(void*, uint32_t, int);
    void   (*vterm_keyboard_key)(void*, int, int);
    void   (*vterm_screen_set_callbacks)(void*, const void*, void*);
    void   (*vterm_screen_set_damage_merge)(void*, int);
    void   (*vterm_screen_flush_damage)(void*);
    void   (*vterm_screen_convert_color_to_rgb)(void*, void*);   /* 0.2 on, else NULL */
} _library;

int
hv_load(const char* name, char* why, size_t why_size)
/* RETURN: 0, the library 'name' is loaded and its functions found;
 *         -1, it does not load ('why' is the system's words);
 *         -2, a function is missing ('why' names it).                     */
{
    void* handle;
    if( _library.handle ) return 0;
    if( ! (handle = dlopen(name, RTLD_NOW)) ) {
        const char* text = dlerror();
        snprintf(why, why_size, "%s", text ? text : "");
        return -1;
    }
#   define FIND(F) \
        if( ! (*(void**)&_library.F = dlsym(handle, #F)) ) { \
            snprintf(why, why_size, "%s", #F); \
            dlclose(handle); memset(&_library, 0, sizeof(_library)); return -2; }
    FIND(vterm_new) FIND(vterm_free) FIND(vterm_set_utf8) FIND(vterm_input_write)
    FIND(vterm_obtain_screen) FIND(vterm_obtain_state) FIND(vterm_screen_reset)
    FIND(vterm_screen_enable_altscreen) FIND(vterm_screen_get_cell) FIND(vterm_state_get_cursorpos)
    FIND(vterm_output_set_callback) FIND(vterm_keyboard_unichar) FIND(vterm_keyboard_key)
    FIND(vterm_screen_set_callbacks) FIND(vterm_screen_set_damage_merge) FIND(vterm_screen_flush_damage)
#   undef FIND
    /* ONLY 0.2 AND LATER hold an indexed colour that must be resolved. */
    *(void**)&_library.vterm_screen_convert_color_to_rgb = dlsym(handle, "vterm_screen_convert_color_to_rgb");
    _library.handle = handle;
    return 0;
}

void
hv_unload(void)
/* RETURN: nothing; the library is closed, to be looked for again.           */
{
    if( _library.handle ) dlclose(_library.handle);
    memset(&_library, 0, sizeof(_library));
}

int
hv_convert_f(void)
/* RETURN: 1 where the library resolves indexed colours ('0.2' on); 0 else. */
{ return _library.vterm_screen_convert_color_to_rgb != NULL; }

void*
hv_new(int row_n, int column_n)
/* RETURN: a new terminal of that size, UTF-8, the alternate screen enabled,
 *         reset -- 'VTerm*'.                                               */
{
    void* vt = _library.vterm_new(row_n, column_n);
    void* screen;
    _library.vterm_set_utf8(vt, 1);
    screen = _library.vterm_obtain_screen(vt);
    /* THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR, and a
     * full-screen application draws on it.                               */
    _library.vterm_screen_enable_altscreen(screen, 1);
    _library.vterm_screen_reset(screen, 1);
    return vt;
}

/* RETURN: nothing, nothing but the library's own function called, each:
 * the terminal freed; its screen; its state; the damage told now.         */
void   hv_free(void* vt)          { _library.vterm_free(vt); }
void*  hv_obtain_screen(void* vt) { return _library.vterm_obtain_screen(vt); }
void*  hv_obtain_state(void* vt)  { return _library.vterm_obtain_state(vt); }
void   hv_flush_damage(void* screen) { _library.vterm_screen_flush_damage(screen); }

size_t
hv_input_write(void* vt, const char* data, size_t length)
/* RETURN: the number of bytes the terminal took.                           */
{ return _library.vterm_input_write(vt, data, length); }

void
hv_cursor(void* state, int* row, int* column)
/* RETURN: nothing; '*row' and '*column' are the cursor's place, from 0.     */
{
    _Position p;
    _library.vterm_state_get_cursorpos(state, &p);
    *row = p.row; *column = p.col;
}

void
hv_get_cell(void* screen, int row, int column, unsigned char* out, size_t out_size,
            int convert_f, int foreground_i, int background_i)
/* RETURN: nothing; 'out' holds the library's own cell at that place -- its
 *         colours resolved to red, green, blue where 'convert_f', the
 *         colour's structure beginning one byte before its red.           */
{
    _Position p = { row, column };
    memset(out, 0, out_size);
    _library.vterm_screen_get_cell(screen, p, out);
    if( convert_f && _library.vterm_screen_convert_color_to_rgb ) {
        _library.vterm_screen_convert_color_to_rgb(screen, out + foreground_i - 1);
        _library.vterm_screen_convert_color_to_rgb(screen, out + background_i - 1);
    }
}

/* RETURN: nothing; the key -- a character, or a VTermKey -- was pressed
 * with 'modifier' held: its sequence is the terminal's output.            */
void hv_keyboard_unichar(void* vt, uint32_t code, int modifier) { _library.vterm_keyboard_unichar(vt, code, modifier); }
void hv_keyboard_key(void* vt, int key, int modifier)          { _library.vterm_keyboard_key(vt, key, modifier); }

/* ------------------------------------------------- the callbacks, to Go
 * RETURN (each): what the Go function returns -- 1, handled.              */
static int _on_damage(_Rectangle r, void* user)
{ return hwutVtermDamage((uintptr_t)user, r.start_row, r.end_row, r.start_col, r.end_col); }

static int _on_cursor(_Position p, _Position old, int visible, void* user)
{ (void)old; return hwutVtermCursor((uintptr_t)user, p.row, p.col, visible); }

static int _on_property(int number, int* value, void* user)
{ return hwutVtermProperty((uintptr_t)user, number, value ? value[0] : 0); }

static int _on_bell(void* user)
{ return hwutVtermBell((uintptr_t)user); }

static void _on_output(const char* data, size_t length, void* user)
{ hwutVtermOutput((uintptr_t)user, (char*)data, length); }

void*
hv_observe(void* vt, void* screen, uintptr_t handle)
/* RETURN: the callbacks' structure (for 'free'), set on 'screen': damage per
 *         row, cursor, property, bell and the terminal's output reach the Go
 *         terminal 'handle' names. It lives as long as the terminal.       */
{
    _ScreenCallbacks* callbacks = calloc(1, sizeof(_ScreenCallbacks));
    callbacks->damage      = _on_damage;
    callbacks->movecursor  = _on_cursor;
    callbacks->settermprop = _on_property;
    callbacks->bell        = _on_bell;
    _library.vterm_output_set_callback(vt, _on_output, (void*)handle);
    _library.vterm_screen_set_callbacks(screen, callbacks, (void*)handle);
    _library.vterm_screen_set_damage_merge(screen, DAMAGE_MERGE_ROW);
    return callbacks;
}
