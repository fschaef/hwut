/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A terminal's screen read by a test -- see 'hwut_vterm.h'. The
 *          library's structures are declared here as the Python binding
 *          declares them; what changed between its versions is measured.
 * _____________________________________________________________________________
 */
#define _DEFAULT_SOURCE
#define _XOPEN_SOURCE 700
#include "hwut_vterm.h"

#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <pty.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

const char* const VTERM_INSTALL_HINT =
    "HINT: install the library, or name its file:\n"
    "    Debian, Ubuntu   apt install libvterm0\n"
    "    Fedora           dnf install libvterm\n"
    "    Arch             pacman -S libvterm\n"
    "    macOS            brew install libvterm\n"
    "    elsewhere        export " VTERM_LIBRARY_VARIABLE "=<path>/libvterm.so\n"
    "    or work inside   hwut.dev.podman.enter   (the image holds it)";

const char* const VTERM_ATTRIBUTE_NAME[7] = { "bold", "italic", "underline", "blink", "reverse", "conceal", "strike" };
const char* const VTERM_ATTRIBUTE_SGR[7]  = { "1", "3", "4", "5", "7", "8", "9" };

/* WHAT IS THE SAME IN EVERY VERSION: six code points of four bytes, then the
 * width; everything behind them is measured.                             */
#define CHARS_PER_CELL_N 6
#define CHARS_BYTE_N     (4 * CHARS_PER_CELL_N)
#define CELL_BYTE_N      128                     /* room beyond any version's cell */
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
    char   name[1024];
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

/* THE MEASURED LAYOUT: 0 not yet, 1 while the defaults are read (colours are
 * converted already), 2 done.                                             */
static struct {
    int           stage;
    int           offset[7];  unsigned char mask[7];
    int           foreground_i, background_i;
    int           convert_f;
    unsigned char default_fg[3], default_bg[3];
} _layout;

static void
_error(VtermError* error, const char* kind, const char* format, ...)
/* RETURN: nothing; 'error' holds the kind and the formatted message.      */
{
    va_list arg;
    if( ! error ) return;
    snprintf(error->kind, sizeof(error->kind), "%s", kind);
    va_start(arg, format); vsnprintf(error->message, sizeof(error->message), format, arg); va_end(arg);
}

void
Vterm_reset_library(void)
/* RETURN: nothing; the library is looked for again at the next screen, and
 *         its layout measured again -- as 'hwut_vterm._library = None'.   */
{
    if( _library.handle ) dlclose(_library.handle);
    memset(&_library, 0, sizeof(_library));
    memset(&_layout, 0, sizeof(_layout));
}

static int
_load(VtermError* error)
/* RETURN: 0, 'libvterm' is loaded -- once -- and its functions are found;
 *         -1, it is not: 'error' is 'LibraryMissing' with the install hint. */
{
    static const char* candidate[] = { "libvterm.so.0", "libvterm.so", "libvterm.0.dylib", "libvterm.dylib", NULL };
    const char* name = getenv(VTERM_LIBRARY_VARIABLE);
    void*       handle = NULL;
    if( _library.handle ) return 0;
    if( name && *name ) {
        if( ! (handle = dlopen(name, RTLD_NOW)) ) {
            const char* why = dlerror();
            _error(error, "LibraryMissing", "libvterm cannot be loaded from '%s' -- %s\n%s",
                   name, why ? why : "", VTERM_INSTALL_HINT);
            return -1;
        }
    } else {
        const char* const* c;
        for(c = candidate; *c && ! handle; ++c) if( (handle = dlopen(*c, RTLD_NOW)) ) name = *c;
        if( ! handle ) {
            _error(error, "LibraryMissing", "libvterm is not installed, and '%s' names no file\n%s",
                   VTERM_LIBRARY_VARIABLE, VTERM_INSTALL_HINT);
            return -1;
        }
    }
#   define FIND(F) \
        if( ! (*(void**)&_library.F = dlsym(handle, #F)) ) { \
            _error(error, "LibraryMissing", "libvterm cannot be loaded from '%s' -- no function '%s'\n%s", \
                   name, #F, VTERM_INSTALL_HINT); \
            dlclose(handle); memset(&_library, 0, sizeof(_library)); return -1; }
    FIND(vterm_new) FIND(vterm_free) FIND(vterm_set_utf8) FIND(vterm_input_write)
    FIND(vterm_obtain_screen) FIND(vterm_obtain_state) FIND(vterm_screen_reset)
    FIND(vterm_screen_enable_altscreen) FIND(vterm_screen_get_cell) FIND(vterm_state_get_cursorpos)
    FIND(vterm_output_set_callback) FIND(vterm_keyboard_unichar) FIND(vterm_keyboard_key)
    FIND(vterm_screen_set_callbacks) FIND(vterm_screen_set_damage_merge) FIND(vterm_screen_flush_damage)
#   undef FIND
    /* ONLY 0.2 AND LATER hold an indexed colour that must be resolved. */
    *(void**)&_library.vterm_screen_convert_color_to_rgb = dlsym(handle, "vterm_screen_convert_color_to_rgb");
    snprintf(_library.name, sizeof(_library.name), "%s", name);
    _library.handle = handle;
    return 0;
}

const char*
Vterm_detection_text(char* buffer, size_t size)
/* RETURN: buffer, 'libvterm found: <name>' where the library loads; else the
 *         text of 'LibraryMissing' -- what is wrong and how to install it. */
{
    VtermError error;
    if( _load(&error) ) snprintf(buffer, size, "%s", error.message);
    else                snprintf(buffer, size, "libvterm found: %s", _library.name);
    return buffer;
}

/* ------------------------------------------------------------- the screen */
static void _measure(void);

int
VtermScreen_init(VtermScreen* self, int row_n, int column_n)
/* RETURN: 0, the screen is blank, the cursor at (0, 0); -1, the library is
 *         not found ('self->error' is 'LibraryMissing').                  */
{
    memset(self, 0, sizeof(*self));
    self->row_n = row_n; self->column_n = column_n;
    if( _load(&self->error) ) return -1;
    self->terminal = _library.vterm_new(row_n, column_n);
    _library.vterm_set_utf8(self->terminal, 1);
    self->screen   = _library.vterm_obtain_screen(self->terminal);
    self->state    = _library.vterm_obtain_state(self->terminal);
    /* THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR, and a
     * full-screen application draws on it.                               */
    _library.vterm_screen_enable_altscreen(self->screen, 1);
    _library.vterm_screen_reset(self->screen, 1);
    return 0;
}

VtermScreen*
VtermScreen_new(int row_n, int column_n, VtermError* error)
/* RETURN: VtermScreen of 'row_n' rows and 'column_n' columns, blank; NULL,
 *         the library is not found ('error' is 'LibraryMissing').        */
{
    VtermScreen* self = malloc(sizeof(VtermScreen));
    if( VtermScreen_init(self, row_n, column_n) ) {
        if( error ) *error = self->error;
        free(self);
        return NULL;
    }
    return self;
}

void
VtermScreen_close(VtermScreen* self)
/* RETURN: nothing; the terminal's memory is freed -- a second call does
 *         nothing.                                                        */
{
    if( ! self->terminal ) return;
    _library.vterm_free(self->terminal);
    self->terminal = self->screen = self->state = NULL;
}

void
VtermScreen_free(VtermScreen* self)
/* RETURN: nothing; the screen is closed and given back.                    */
{ if( self ) { VtermScreen_close(self); free(self); } }

size_t
VtermScreen_feed(VtermScreen* self, const char* data, size_t length)
/* RETURN: the number of bytes the terminal took -- all of them, where it
 *         works as documented. 'data' is what a program wrote.           */
{ return _library.vterm_input_write(self->terminal, data, length); }

void
VtermScreen_cursor(VtermScreen* self, int* row, int* column)
/* RETURN: nothing; '*row' and '*column' are the cursor's place, from 0.   */
{
    _Position p;
    _library.vterm_state_get_cursorpos(self->state, &p);
    *row = p.row; *column = p.col;
}

static void
_raw(VtermScreen* self, int row, int column, unsigned char* buffer)
/* RETURN: nothing; 'buffer' (CELL_BYTE_N) holds the library's own cell at
 *         that place, its colours resolved to red, green, blue where the
 *         library keeps them otherwise.                                   */
{
    _Position p = { row, column };
    memset(buffer, 0, CELL_BYTE_N);
    _library.vterm_screen_get_cell(self->screen, p, buffer);
    if( _layout.stage >= 1 && _layout.convert_f ) {
        /* THE COLOUR'S STRUCTURE begins one byte before its red. */
        _library.vterm_screen_convert_color_to_rgb(self->screen, buffer + _layout.foreground_i - 1);
        _library.vterm_screen_convert_color_to_rgb(self->screen, buffer + _layout.background_i - 1);
    }
}

static size_t
_utf8_encode(uint32_t code, char* out)
/* RETURN: the number of bytes 'code' takes in UTF-8, written to 'out'.    */
{
    if( code < 0x80 )    { out[0] = (char)code; return 1; }
    if( code < 0x800 )   { out[0] = (char)(0xC0 | (code >> 6)); out[1] = (char)(0x80 | (code & 0x3F)); return 2; }
    if( code < 0x10000 ) { out[0] = (char)(0xE0 | (code >> 12)); out[1] = (char)(0x80 | ((code >> 6) & 0x3F));
                           out[2] = (char)(0x80 | (code & 0x3F)); return 3; }
    out[0] = (char)(0xF0 | (code >> 18)); out[1] = (char)(0x80 | ((code >> 12) & 0x3F));
    out[2] = (char)(0x80 | ((code >> 6) & 0x3F)); out[3] = (char)(0x80 | (code & 0x3F));
    return 4;
}

int
VtermScreen_cell(VtermScreen* self, int row, int column, VtermCell* cell)
/* RETURN: 0, 'cell' holds what stands at that place; -1, the place is not
 *         on the screen ('self->error' is 'IndexError').                  */
{
    unsigned char raw[CELL_BYTE_N];
    size_t        i, k = 0;
    int*          flag[7];
    if( ! (0 <= row && row < self->row_n && 0 <= column && column < self->column_n) ) {
        _error(&self->error, "IndexError", "(%d, %d) is not on a screen of %d x %d", row, column, self->row_n, self->column_n);
        return -1;
    }
    _measure();
    _raw(self, row, column, raw);
    memset(cell, 0, sizeof(*cell));
    for(i = 0; i < CHARS_BYTE_N; i += 4) {
        uint32_t code = (uint32_t)raw[i] | (uint32_t)raw[i + 1] << 8 | (uint32_t)raw[i + 2] << 16 | (uint32_t)raw[i + 3] << 24;
        if( code == 0 || code == 0xFFFFFFFFu ) continue;
        if( k + 5 < sizeof(cell->text) ) k += _utf8_encode(code, cell->text + k);
    }
    cell->text[k] = '\0';
    cell->width = raw[CHARS_BYTE_N] ? raw[CHARS_BYTE_N] : 1;
    flag[0] = &cell->bold_f; flag[1] = &cell->italic_f; flag[2] = &cell->underline_f; flag[3] = &cell->blink_f;
    flag[4] = &cell->reverse_f; flag[5] = &cell->conceal_f; flag[6] = &cell->strike_f;
    for(i = 0; i < 7; ++i) *flag[i] = (raw[_layout.offset[i]] & _layout.mask[i]) != 0;
    if( memcmp(raw + _layout.foreground_i, _layout.default_fg, 3) ) {
        cell->foreground_f = 1; memcpy(cell->foreground, raw + _layout.foreground_i, 3);
    }
    if( memcmp(raw + _layout.background_i, _layout.default_bg, 3) ) {
        cell->background_f = 1; memcpy(cell->background, raw + _layout.background_i, 3);
    }
    return 0;
}

char*
VtermCell_attribute_text(const VtermCell* self, char* buffer, size_t size)
/* RETURN: buffer, the attributes that are set, by name and in one fixed
 *         order, separated by blanks -- 'bold reverse'; '' where none.    */
{
    const int flag[7] = { self->bold_f, self->italic_f, self->underline_f, self->blink_f,
                          self->reverse_f, self->conceal_f, self->strike_f };
    size_t    i, k = 0;
    buffer[0] = '\0';
    for(i = 0; i < 7; ++i)
        if( flag[i] ) k += (size_t)snprintf(buffer + k, size - k, "%s%s", k ? " " : "", VTERM_ATTRIBUTE_NAME[i]);
    return buffer;
}

static void
_rstrip(char* text)
/* RETURN: nothing; blanks at the text's end are gone.                      */
{
    size_t n = strlen(text);
    while( n && strchr(" \t\n\r\v\f", text[n - 1]) ) text[--n] = '\0';
}

static char*
_row_text(VtermScreen* self, int row, int column, int column_n, char* buffer, size_t size)
/* RETURN: buffer, the characters of 'column_n' columns from 'column' of the
 *         row, blanks at its end dropped; an unwritten cell reads a blank. */
{
    size_t    k = 0;
    int       at = column;
    VtermCell cell;
    buffer[0] = '\0';
    while( at < column + column_n ) {
        const char* text;
        size_t      n;
        VtermScreen_cell(self, row, at, &cell);
        text = cell.text[0] ? cell.text : " ";
        n    = strlen(text);
        if( k + n < size ) { memcpy(buffer + k, text, n); k += n; buffer[k] = '\0'; }
        at += cell.width > 1 ? cell.width : 1;
    }
    _rstrip(buffer);
    return buffer;
}

char*
VtermScreen_line(VtermScreen* self, int row, char* buffer, size_t size)
/* RETURN: buffer, the row's characters, blanks at its end dropped; a cell
 *         nothing was written to reads as a blank.                       */
{ return _row_text(self, row, 0, self->column_n, buffer, size); }

/* ---------------------------------------------------- measuring the layout */
static void
_cell_after(const char* sequence, unsigned char* raw)
/* RETURN: nothing; 'raw' is cell (0, 0) of a fresh terminal after
 *         '<esc>[<sequence>m' and one 'X'.                                 */
{
    VtermScreen scratch;
    char        text[64];
    VtermScreen_init(&scratch, 2, 4);
    if( sequence && *sequence ) {
        snprintf(text, sizeof(text), "\x1b[%sm", sequence);
        VtermScreen_feed(&scratch, text, strlen(text));
    }
    VtermScreen_feed(&scratch, "X", 1);
    _raw(&scratch, 0, 0, raw);
    VtermScreen_close(&scratch);
}

static int
_changed(const unsigned char* plain, const unsigned char* raw, int* offset, unsigned char* bits, int start_i)
/* RETURN: 1, '*offset' and '*bits' are the first byte behind the width from
 *         'start_i' on in which 'raw' differs from 'plain'; 0, none.      */
{
    int i;
    for(i = start_i; i < CELL_BYTE_N; ++i)
        if( plain[i] != raw[i] ) { *offset = i; *bits = (unsigned char)(plain[i] ^ raw[i]); return 1; }
    return 0;
}

static int
_colour_at(const char* code)
/* RETURN: the offset of the red byte of the colour '<code>;2;1;2;3' sets.  */
{
    unsigned char raw[CELL_BYTE_N];
    char          sequence[32];
    int           i;
    snprintf(sequence, sizeof(sequence), "%s;2;1;2;3", code);
    _cell_after(sequence, raw);
    for(i = CHARS_BYTE_N + 1; i + 2 < CELL_BYTE_N; ++i)
        if( raw[i] == 1 && raw[i + 1] == 2 && raw[i + 2] == 3 ) return i;
    return CHARS_BYTE_N + 1;
}

static void
_measure(void)
/* RETURN: nothing; '_layout' says where this library's cell keeps each
 *         attribute and each colour -- measured once on scratch terminals. */
{
    unsigned char plain[CELL_BYTE_N], raw[CELL_BYTE_N];
    int           i, offset;
    unsigned char bits;
    if( _layout.stage ) return;
    _cell_after("", plain);
    for(i = 0; i < 7; ++i) {
        _cell_after(VTERM_ATTRIBUTE_SGR[i], raw);
        /* NOTHING MOVED: this library does not know the attribute. */
        if( _changed(plain, raw, &offset, &bits, CHARS_BYTE_N + 1) ) { _layout.offset[i] = offset; _layout.mask[i] = bits; }
        else                                                          { _layout.offset[i] = CHARS_BYTE_N + 1; _layout.mask[i] = 0; }
    }
    /* UNDERLINE IS A NUMBER OF TWO BITS: the double's bit joins the mask. */
    _cell_after("21", raw);
    for(i = CHARS_BYTE_N + 1; i < CELL_BYTE_N; ++i)
        if( plain[i] != raw[i] && i == _layout.offset[2] ) _layout.mask[2] |= (unsigned char)(plain[i] ^ raw[i]);
    _layout.foreground_i = _colour_at("38");
    _layout.background_i = _colour_at("48");
    _layout.convert_f    = _library.vterm_screen_convert_color_to_rgb != NULL;
    /* THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell is read. */
    _layout.stage = 1;
    _cell_after("", raw);
    memcpy(_layout.default_fg, raw + _layout.foreground_i, 3);
    memcpy(_layout.default_bg, raw + _layout.background_i, 3);
    _layout.stage = 2;
}

/* ------------------------------------------------------------ the events */
static const struct { int number; const char* name; int plain_f; } _PROPERTY_DB[] = {
    { 1, "cursor-visible", 1 }, { 2, "cursor-blink", 1 }, { 3, "alternate-screen", 1 }, { 4, "title", 0 },
    { 5, "icon-name", 0 }, { 6, "reverse-video", 1 }, { 7, "cursor-shape", 1 }, { 8, "mouse", 1 },
    { 9, "focus-report", 1 }, { 0, NULL, 0 }
};

static const struct { const char* name; int key; } _KEY_DB[] = {
    { "enter", 1 }, { "tab", 2 }, { "backspace", 3 }, { "escape", 4 }, { "up", 5 }, { "down", 6 },
    { "left", 7 }, { "right", 8 }, { "insert", 9 }, { "delete", 10 }, { "home", 11 }, { "end", 12 },
    { "pageup", 13 }, { "pagedown", 14 },
    { "f1", 257 }, { "f2", 258 }, { "f3", 259 }, { "f4", 260 }, { "f5", 261 }, { "f6", 262 },
    { "f7", 263 }, { "f8", 264 }, { "f9", 265 }, { "f10", 266 }, { "f11", 267 }, { "f12", 268 },
    { NULL, 0 }
};

char*
VtermEvent_to_string(const VtermEvent* self, char* buffer, size_t size)
/* RETURN: buffer, the event on one line, as a test prints it.              */
{
    if( ! strcmp(self->kind, "damage") )
        snprintf(buffer, size, "damage    rows %d..%d  columns %d..%d", self->row, self->row_end, self->column, self->column_end);
    else if( ! strcmp(self->kind, "cursor") )
        snprintf(buffer, size, "cursor    (%d, %d)%s", self->row, self->column, self->value ? "" : "  hidden");
    else if( ! strcmp(self->kind, "property") ) {
        if( self->value_f ) snprintf(buffer, size, "property  %s = %d", self->name, self->value);
        else                snprintf(buffer, size, "property  %s = None", self->name);
    } else snprintf(buffer, size, "%s", self->kind);
    return buffer;
}

static int
_emit(VtermTerminal* self, const VtermEvent* event)
/* RETURN: 1, libvterm's 'handled'; the event reached every raw callback.  */
{
    size_t i;
    for(i = 0; i < self->event_f_n; ++i) self->event_f[i].f(self->event_f[i].context, event);
    return 1;
}

static int
_on_damage(_Rectangle r, void* user)
{
    VtermEvent e = { "damage", r.start_row, r.start_col, r.end_row, r.end_col, NULL, 0, 0 };
    return _emit(user, &e);
}

static int
_on_cursor(_Position p, _Position old, int visible, void* user)
{
    VtermEvent e = { "cursor", p.row, p.col, 0, 0, NULL, 1, visible != 0 };
    (void)old;
    return _emit(user, &e);
}

static int
_on_property(int number, int* value, void* user)
{
    static char unknown[32];
    VtermEvent  e = { "property", 0, 0, 0, 0, NULL, 0, 0 };
    size_t      i;
    for(i = 0; _PROPERTY_DB[i].name; ++i)
        if( _PROPERTY_DB[i].number == number ) { e.name = _PROPERTY_DB[i].name; e.value_f = _PROPERTY_DB[i].plain_f; }
    if( ! e.name ) { snprintf(unknown, sizeof(unknown), "property-%d", number); e.name = unknown; }
    if( e.value_f ) e.value = value[0];
    return _emit(user, &e);
}

static int
_on_bell(void* user)
{ VtermEvent e = { "bell", 0, 0, 0, 0, NULL, 0, 0 }; return _emit(user, &e); }

static void
_on_output(const char* data, size_t length, void* user)
/* RETURN: nothing; what the TERMINAL says -- a key's sequence, an answer --
 *         is collected for the application.                              */
{
    VtermTerminal* self = user;
    if( self->answer_n + length > self->answer_capacity ) {
        self->answer_capacity = 2 * (self->answer_n + length) + 64;
        self->answer = realloc(self->answer, self->answer_capacity);
    }
    memcpy(self->answer + self->answer_n, data, length);
    self->answer_n += length;
}

/* ----------------------------------------------------------- the terminal */
VtermTerminal*
VtermTerminal_new(int row_n, int column_n, double settle_s, VtermError* error)
/* RETURN: VtermTerminal, blank, nothing running in it; NULL, the library is
 *         not found ('error' is 'LibraryMissing'). 'settle_s' is how long
 *         the application must write nothing before its screen is taken as
 *         drawn (Python's default: 0.1).                                  */
{
    VtermTerminal*    self = calloc(1, sizeof(VtermTerminal));
    _ScreenCallbacks* callbacks;
    if( VtermScreen_init(&self->base, row_n, column_n) ) {
        if( error ) *error = self->base.error;
        free(self);
        return NULL;
    }
    self->settle_s = settle_s;
    self->master   = -1;
    /* THE CALLBACKS LIVE AS LONG AS THE TERMINAL: libvterm keeps their address. */
    self->callbacks = callbacks = calloc(1, sizeof(_ScreenCallbacks));
    callbacks->damage      = _on_damage;
    callbacks->movecursor  = _on_cursor;
    callbacks->settermprop = _on_property;
    callbacks->bell        = _on_bell;
    _library.vterm_output_set_callback(self->base.terminal, _on_output, self);
    _library.vterm_screen_set_callbacks(self->base.screen, callbacks, self);
    _library.vterm_screen_set_damage_merge(self->base.screen, DAMAGE_MERGE_ROW);
    return self;
}

static int
_poll(VtermTerminal* self)
/* RETURN: 1 where the application still runs; 0 where it ended (reaped,
 *         its status kept) or never ran.                                  */
{
    int status;
    if( ! self->process || self->reaped_f ) return 0;
    if( waitpid(self->process, &status, WNOHANG) != self->process ) return 1;
    self->reaped_f = 1;
    self->status   = WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status);
    return 0;
}

static void
_kill(VtermTerminal* self)
/* RETURN: nothing; the application is killed and reaped.                   */
{
    int status;
    kill(self->process, SIGKILL);
    waitpid(self->process, &status, 0);
    self->reaped_f = 1;
    self->status   = WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status);
}

void
VtermTerminal_close(VtermTerminal* self)
/* RETURN: nothing; an application still running is killed, the
 *         pseudo-terminal closed, the terminal's memory freed.           */
{
    if( _poll(self) ) _kill(self);
    if( self->master >= 0 ) { close(self->master); self->master = -1; }
    VtermScreen_close(&self->base);
}

void
VtermTerminal_free(VtermTerminal* self)
/* RETURN: nothing; the terminal is closed and all it holds given back.     */
{
    size_t i;
    if( ! self ) return;
    VtermTerminal_close(self);
    for(i = 0; i < self->region_n; ++i) {
        VtermTerminal_lines_free(self->region[i].told, (size_t)self->region[i].row_n);
        free(self->region[i].name);
    }
    free(self->answer); free(self->callbacks); free(self);
}

void
VtermTerminal_on_event(VtermTerminal* self, VtermTerminal_EventF f, void* context)
/* RETURN: nothing; 'f(context, event)' is called with every raw event from
 *         now on.                                                         */
{
    if( self->event_f_n == VTERM_CALLBACK_MAX ) return;
    self->event_f[self->event_f_n].f = f; self->event_f[self->event_f_n++].context = context;
}

void
VtermTerminal_on_change(VtermTerminal* self, VtermTerminal_ChangeF f, void* context)
/* RETURN: nothing; 'f(context, name, line_list, line_n)' is called for every
 *         region whose text changed, once the screen is quiet.          */
{
    if( self->change_f_n == VTERM_CALLBACK_MAX ) return;
    self->change_f[self->change_f_n].f = f; self->change_f[self->change_f_n++].context = context;
}

static VtermRegion*
_region(VtermTerminal* self, const char* name)
{
    size_t i;
    for(i = 0; i < self->region_n; ++i) if( ! strcmp(self->region[i].name, name) ) return &self->region[i];
    return NULL;
}

void
VtermTerminal_lines_free(char** line_list, size_t line_n)
/* RETURN: nothing; the lines and their list are given back.                */
{
    size_t i;
    if( ! line_list ) return;
    for(i = 0; i < line_n; ++i) free(line_list[i]);
    free(line_list);
}

static char**
_region_lines(VtermTerminal* self, const VtermRegion* r)
{
    char** result = malloc(sizeof(char*) * (size_t)(r->row_n > 0 ? r->row_n : 1));
    char   buffer[4096];
    int    i;
    for(i = 0; i < r->row_n; ++i)
        result[i] = strdup(_row_text(&self->base, r->row + i, r->column, r->column_n, buffer, sizeof(buffer)));
    return result;
}

void
VtermTerminal_region(VtermTerminal* self, const char* name, int row, int row_n, int column, int column_n)
/* RETURN: nothing; the rectangle 'name' is observed from now on: 'row_n'
 *         rows from 'row', 'column_n' columns from 'column' -- to the right
 *         edge where negative. A NEGATIVE 'row' counts from the bottom: -1
 *         is the last row. What stands there now is known, not news.     */
{
    VtermRegion* r = _region(self, name);
    if( row < 0 ) row += self->base.row_n;
    if( column_n < 0 ) column_n = self->base.column_n - column;
    if( r ) VtermTerminal_lines_free(r->told, (size_t)r->row_n);
    else {
        if( self->region_n == VTERM_REGION_MAX ) return;
        r = &self->region[self->region_n++];
        r->name = strdup(name);
    }
    r->row = row; r->row_n = row_n; r->column = column; r->column_n = column_n;
    r->told = _region_lines(self, r);
}

char**
VtermTerminal_region_text(VtermTerminal* self, const char* name, size_t* line_n)
/* RETURN: the region's rows as they stand now, blanks at each row's end
 *         dropped -- a new list of '*line_n' lines, for
 *         'VtermTerminal_lines_free'; NULL, no such region was declared
 *         ('self->base.error' is 'KeyError').                            */
{
    VtermRegion* r = _region(self, name);
    if( ! r ) { _error(&self->base.error, "KeyError", "'%s'", name); return NULL; }
    *line_n = (size_t)r->row_n;
    return _region_lines(self, r);
}

size_t
VtermTerminal_report(VtermTerminal* self)
/* RETURN: the number of regions whose text differs from what was last told
 *         -- each told to every 'on_change' callback, in the order of
 *         declaration.                                                    */
{
    size_t i, k, changed_n = 0;
    for(i = 0; i < self->region_n; ++i) {
        VtermRegion* r    = &self->region[i];
        char**       line = _region_lines(self, r);
        int          same_f = 1, j;
        for(j = 0; j < r->row_n; ++j) if( strcmp(line[j], r->told[j]) ) { same_f = 0; break; }
        if( same_f ) { VtermTerminal_lines_free(line, (size_t)r->row_n); continue; }
        VtermTerminal_lines_free(r->told, (size_t)r->row_n);
        r->told = line;
        ++changed_n;
        for(k = 0; k < self->change_f_n; ++k)
            self->change_f[k].f(self->change_f[k].context, r->name, r->told, (size_t)r->row_n);
    }
    return changed_n;
}

static void
_forward(VtermTerminal* self)
/* RETURN: nothing; the terminal's words reach the application, if one runs;
 *         they wait in 'answer' otherwise.                               */
{
    size_t done = 0;
    if( self->master < 0 || ! self->answer_n ) return;
    while( done < self->answer_n ) {
        ssize_t n = write(self->master, self->answer + done, self->answer_n - done);
        if( n < 0 ) { if( errno == EINTR ) continue; self->ended_f = 1; break; }
        done += (size_t)n;
    }
    self->answer_n = 0;
}

size_t
VtermTerminal_feed(VtermTerminal* self, const char* data, size_t length)
/* RETURN: the number of bytes the terminal took; the raw events of what was
 *         fed fired before this returns, what the terminal answered went
 *         to the application, where one runs.                            */
{
    size_t taken_n = VtermScreen_feed(&self->base, data, length);
    _library.vterm_screen_flush_damage(self->base.screen);
    _forward(self);
    return taken_n;
}

char*
VtermTerminal_answer(VtermTerminal* self, size_t* length)
/* RETURN: a new buffer of '*length' bytes, what the terminal said since the
 *         last call and no application took -- for 'free'.             */
{
    char* data = malloc(self->answer_n + 1);
    memcpy(data, self->answer ? self->answer : "", self->answer_n);
    data[self->answer_n] = '\0';
    *length = self->answer_n;
    self->answer_n = 0;
    return data;
}

static size_t
_utf8_decode(const char* text, uint32_t* code)
/* RETURN: the number of bytes of the code point at 'text', in '*code'.     */
{
    const unsigned char* s = (const unsigned char*)text;
    if( s[0] < 0x80 )                { *code = s[0]; return 1; }
    if( (s[0] & 0xE0) == 0xC0 && s[1] ) { *code = (uint32_t)(s[0] & 0x1F) << 6 | (s[1] & 0x3F); return 2; }
    if( (s[0] & 0xF0) == 0xE0 && s[1] && s[2] ) {
        *code = (uint32_t)(s[0] & 0x0F) << 12 | (uint32_t)(s[1] & 0x3F) << 6 | (s[2] & 0x3F); return 3; }
    if( (s[0] & 0xF8) == 0xF0 && s[1] && s[2] && s[3] ) {
        *code = (uint32_t)(s[0] & 0x07) << 18 | (uint32_t)(s[1] & 0x3F) << 12 | (uint32_t)(s[2] & 0x3F) << 6 | (s[3] & 0x3F);
        return 4; }
    *code = s[0]; return 1;
}

int
VtermTerminal_send(VtermTerminal* self, const char* text, double react_s)
/* RETURN: 1, the application still runs after 'text' (UTF-8) was typed
 *         character by character, as a keyboard sends it, and the screen
 *         read until quiet ('react_s' to begin answering); 0, it does not. */
{
    while( *text ) {
        uint32_t code;
        text += _utf8_decode(text, &code);
        _library.vterm_keyboard_unichar(self->base.terminal, code, 0);
    }
    _forward(self);
    return VtermTerminal_pump(self, react_s);
}

int
VtermTerminal_press(VtermTerminal* self, const char* key, const char* modifier, double react_s)
/* RETURN: 1, the application still runs after 'key' was pressed; 0, it does
 *         not; -1, 'key' or a modifier has no name here ('KeyError').
 *         'key' is 'enter', 'up', 'f5', ... or one character; 'modifier'
 *         names 'shift', 'alt', 'ctrl' separated by blanks, or is NULL --
 *         'press(t, "c", "ctrl", 1.0)' is Ctrl-C.                         */
{
    int         mask = 0;
    uint32_t    code;
    const char* p = modifier ? modifier : "";
    while( *p ) {
        char   word[32];
        size_t n = strcspn(p, " ");
        if( ! n ) { ++p; continue; }
        snprintf(word, sizeof(word), "%.*s", (int)n, p);
        if( ! strcmp(word, "shift") )     mask |= 1;
        else if( ! strcmp(word, "alt") )  mask |= 2;
        else if( ! strcmp(word, "ctrl") ) mask |= 4;
        else { _error(&self->base.error, "KeyError", "'%s'", word); return -1; }
        p += n;
    }
    if( key[0] && ! key[_utf8_decode(key, &code)] ) _library.vterm_keyboard_unichar(self->base.terminal, code, mask);
    else {
        size_t i;
        for(i = 0; _KEY_DB[i].name && strcmp(_KEY_DB[i].name, key); ++i) {}
        if( ! _KEY_DB[i].name ) { _error(&self->base.error, "KeyError", "'%s'", key); return -1; }
        _library.vterm_keyboard_key(self->base.terminal, _KEY_DB[i].key, mask);
    }
    _forward(self);
    return VtermTerminal_pump(self, react_s);
}

int
VtermTerminal_run(VtermTerminal* self, char* const* argv, const char* cwd, double start_s)
/* RETURN: 1, the application 'argv' still runs once its first screen
 *         stands; 0, it does not; -1, one was already run here
 *         ('RuntimeError'). It is started on a pseudo-terminal of this
 *         terminal's size: its three streams are that terminal, it is the
 *         controlling one, TERM is 'xterm-256color', and LINES and COLUMNS
 *         are taken OUT of its environment -- they would overrule the size. */
{
    int            slave;
    struct winsize size;
    pid_t          pid;
    if( self->process ) {
        _error(&self->base.error, "RuntimeError", "an application already runs in this terminal");
        return -1;
    }
    if( openpty(&self->master, &slave, NULL, NULL, NULL) ) {
        _error(&self->base.error, "OSError", "openpty: %s", strerror(errno));
        return -1;
    }
    memset(&size, 0, sizeof(size));
    size.ws_row = (unsigned short)self->base.row_n; size.ws_col = (unsigned short)self->base.column_n;
    ioctl(slave, TIOCSWINSZ, &size);
    fflush(stdout); fflush(stderr);
    if( (pid = fork()) == 0 ) {
        int fd;
        setsid();
        dup2(slave, 0); dup2(slave, 1); dup2(slave, 2);
        ioctl(0, TIOCSCTTY, 0);
        for(fd = 3; fd < 1024; ++fd) close(fd);
        setenv("TERM", "xterm-256color", 1);
        unsetenv("LINES"); unsetenv("COLUMNS");
        signal(SIGPIPE, SIG_DFL);
        if( cwd && chdir(cwd) ) _exit(127);
        execvp(argv[0], argv);
        _exit(127);
    }
    close(slave);
    self->process  = pid;
    self->reaped_f = 0;
    self->ended_f  = 0;
    return VtermTerminal_pump(self, start_s);
}

static double
_now(void)
{ struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (double)t.tv_sec + 1e-9 * (double)t.tv_nsec; }

int
VtermTerminal_pump(VtermTerminal* self, double first_s)
/* RETURN: 1, the application still runs; 0, it does not. READ UNTIL QUIET:
 *         up to 'first_s' for the application to write at all, then on
 *         until it wrote nothing for 'settle_s'; then the changed regions
 *         are reported.                                                  */
{
    static char data[65536];
    double      wait_s = first_s;
    while( self->master >= 0 && ! self->ended_f ) {
        fd_set         ready;
        struct timeval t;
        ssize_t        n;
        int            r;
        FD_ZERO(&ready); FD_SET(self->master, &ready);
        t.tv_sec  = (time_t)wait_s;
        t.tv_usec = (suseconds_t)((wait_s - (double)t.tv_sec) * 1e6);
        r = select(self->master + 1, &ready, NULL, NULL, &t);
        if( r < 0 && errno == EINTR ) continue;
        if( r <= 0 ) break;
        n = read(self->master, data, sizeof(data));
        if( n < 0 && errno == EINTR ) continue;
        if( n <= 0 ) { self->ended_f = 1; break; }       /* the last writer closed: it ended */
        VtermTerminal_feed(self, data, (size_t)n);
        wait_s = self->settle_s;
    }
    VtermTerminal_report(self);
    return _poll(self) && ! self->ended_f;
}

int
VtermTerminal_expect(VtermTerminal* self, const char* text, double timeout_s, int* row, int* column)
/* RETURN: 0, 'text' stands on the screen at '*row', '*column' (counted in
 *         characters); -1, it did not appear within 'timeout_s'
 *         ('TimeoutError', carrying the screen).                         */
{
    double deadline = _now() + timeout_s;
    char   line[4096];
    while( 1 ) {
        int r;
        for(r = 0; r < self->base.row_n; ++r) {
            const char* at = strstr(VtermScreen_line(&self->base, r, line, sizeof(line)), text);
            const char* p;
            int         c = 0;
            if( ! at ) continue;
            for(p = line; p < at; ++p) c += (*p & 0xC0) != 0x80;
            *row = r; *column = c;
            return 0;
        }
        if( _now() >= deadline || self->ended_f || self->master < 0 ) {
            size_t k = (size_t)snprintf(self->base.error.message, sizeof(self->base.error.message),
                                        "'%s' did not appear; the screen:", text);
            snprintf(self->base.error.kind, sizeof(self->base.error.kind), "TimeoutError");
            for(r = 0; r < self->base.row_n && k < sizeof(self->base.error.message); ++r)
                k += (size_t)snprintf(self->base.error.message + k, sizeof(self->base.error.message) - k,
                                      "\n%s", VtermScreen_line(&self->base, r, line, sizeof(line)));
            return -1;
        }
        VtermTerminal_pump(self, self->settle_s);
    }
}

int
VtermTerminal_wait(VtermTerminal* self, double timeout_s, int* status)
/* RETURN: 1, '*status' is the application's exit status (negative: the
 *         signal that ended it), once it ended and its last words are on
 *         the screen; 0, no application was run; -1, it still ran after
 *         'timeout_s' and was killed ('TimeoutError').                   */
{
    double deadline;
    if( ! self->process ) return 0;
    deadline = _now() + timeout_s;
    while( VtermTerminal_pump(self, self->settle_s) ) {
        if( _now() >= deadline ) {
            _kill(self);
            _error(&self->base.error, "TimeoutError", "the application still ran after %.1f s", timeout_s);
            return -1;
        }
    }
    {   double until = _now() + (deadline - _now() > 0.1 ? deadline - _now() : 0.1);
        while( _poll(self) ) {
            struct timespec pause = { 0, 10 * 1000 * 1000 };
            if( _now() >= until ) {
                _kill(self);
                _error(&self->base.error, "TimeoutError", "the application closed its terminal and did not end");
                return -1;
            }
            nanosleep(&pause, NULL);
        }
    }
    *status = self->status;
    return 1;
}
