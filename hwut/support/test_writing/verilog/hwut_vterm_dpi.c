/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE DPI-C FACE OF '../c/hwut_vterm.c' for 'hwut_vterm.sv'. The C
 *          port loads libvterm ('dlopen', no header), measures its cell,
 *          runs an application on a pseudo-terminal and reads its screen;
 *          this file converts between its C types and what DPI-C passes. A
 *          'chandle' is a 'VtermScreen*' or a 'VtermTerminal*'.
 *
 * WHAT THE TERMINAL REPORTS -- an event, a region changed -- goes to the
 * SystemVerilog terminal that owns it: the exported 'hwut_sv_vterm_event' and
 * 'hwut_sv_vterm_change', 'id' the terminal's number, called in the scope of
 * package 'hwut_vterm'. A region's lines travel joined by '\n' (a screen line
 * holds none), with their number.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "svdpi.h"
#include "hwut_vterm.h"

#define HWUT_SV_VTERM_TEXT_MAX (1 << 16)

extern void hwut_sv_vterm_event(int id, const char* text, const char* kind, int row, int column,
                                int row_end, int column_end, const char* name, int value_f, int value);
extern void hwut_sv_vterm_change(int id, const char* name, const char* joined, int line_n);

static VtermError _error;           /* the last constructor's               */
static char*      _argv[256];
static int        _argc;

static void _scope(void) { svSetScope(svGetScopeFromName("TOP.hwut_vterm")); }

/* ------------------------------------------------------------ the library */
const char*
hwut_sv_vterm_detection_text(void)
/* RETURN: 'libvterm found: <name>' where the library loads; the text of
 *         'LibraryMissing' -- what is wrong, how to install it -- else.    */
{
    static char buffer[4096];
    return Vterm_detection_text(buffer, sizeof(buffer));
}

void hwut_sv_vterm_reset_library(void)
/* RETURN: nothing; the next screen loads the library anew (HWUT_LIBVTERM). */
{ Vterm_reset_library(); }

int hwut_sv_vterm_setenv(const char* name, const char* value)
/* RETURN: 0, the environment holds 'name' = 'value'; -1, it could not.    */
{ return setenv(name, value, 1); }

const char* hwut_sv_vterm_install_hint(void)
/* RETURN: how to install the library, several lines.                       */
{ return VTERM_INSTALL_HINT; }

const char*
hwut_sv_vterm_error(void* screen, const char** kind)
/* RETURN: the message of the last error -- of 'screen' (a VtermScreen*, or a
 *         terminal's), or of the last constructor where NULL; '*kind' is
 *         Python's exception name.                                         */
{
    VtermError* error = screen ? &((VtermScreen*)screen)->error : &_error;
    *kind = error->kind;
    return error->message;
}

/* ----------------------------------------------------------------- Screen */
void* hwut_sv_vterm_screen_new(int row_n, int column_n)
/* RETURN: a blank screen; NULL where the library is missing.               */
{ return VtermScreen_new(row_n, column_n, &_error); }

void hwut_sv_vterm_screen_free(void* screen)
/* RETURN: nothing; the screen is gone.                                     */
{ VtermScreen_free((VtermScreen*)screen); }

int hwut_sv_vterm_screen_feed(void* screen, const char* data)
/* RETURN: the number of bytes of 'data' the screen took.                   */
{ return (int)VtermScreen_feed((VtermScreen*)screen, data, strlen(data)); }

void hwut_sv_vterm_cursor(void* screen, int* row, int* column)
/* RETURN: nothing; '*row', '*column' is where the cursor stands, from 0.   */
{ VtermScreen_cursor((VtermScreen*)screen, row, column); }

int
hwut_sv_vterm_cell(void* screen, int row, int column, const char** text, int* width, int* attribute,
                   int* foreground, int* background)
/* RETURN: 0, the cell at (row, column): '*text' what stands in it (UTF-8),
 *         '*width', '*attribute' a bit per attribute in the order of
 *         VTERM_ATTRIBUTE_NAME (bold the lowest), '*foreground' and
 *         '*background' 0xRRGGBB or -1 for the default; -1, the place is not
 *         on the screen ('IndexError').                                    */
{
    static VtermCell cell;
    const int*       flag[7];
    int              i;
    *text = "";
    if( VtermScreen_cell((VtermScreen*)screen, row, column, &cell) ) return -1;
    flag[0] = &cell.bold_f;  flag[1] = &cell.italic_f;  flag[2] = &cell.underline_f;  flag[3] = &cell.blink_f;
    flag[4] = &cell.reverse_f;  flag[5] = &cell.conceal_f;  flag[6] = &cell.strike_f;
    *text      = cell.text;
    *width     = cell.width;
    *attribute = 0;
    for(i = 0; i < 7; ++i) if( *flag[i] ) *attribute |= 1 << i;
    *foreground = cell.foreground_f ? (cell.foreground[0] << 16 | cell.foreground[1] << 8 | cell.foreground[2]) : -1;
    *background = cell.background_f ? (cell.background[0] << 16 | cell.background[1] << 8 | cell.background[2]) : -1;
    return 0;
}

const char*
hwut_sv_vterm_line(void* screen, int row)
/* RETURN: the text of row 'row', trailing blanks removed; 64 KiB at most.  */
{
    static char buffer[HWUT_SV_VTERM_TEXT_MAX];
    return VtermScreen_line((VtermScreen*)screen, row, buffer, sizeof(buffer));
}

/* --------------------------------------------------------------- Terminal */
static void
_on_event(void* context, const VtermEvent* event)
/* RETURN: nothing; 'event' went to the SystemVerilog terminal 'context'.   */
{
    char text[512];
    _scope();
    hwut_sv_vterm_event((int)(intptr_t)context, VtermEvent_to_string(event, text, sizeof(text)), event->kind,
                        event->row, event->column, event->row_end, event->column_end,
                        event->name ? event->name : "", event->value_f, event->value);
}

static char*
_joined(char** line_list, size_t line_n)
/* RETURN: the lines, '\n' between each two, newly allocated.               */
{
    size_t i, n = 1;
    char*  text;
    for(i = 0; i < line_n; ++i) n += strlen(line_list[i]) + 1;
    text = malloc(n);
    text[0] = '\0';
    for(i = 0; i < line_n; ++i) { if( i ) strcat(text, "\n"); strcat(text, line_list[i]); }
    return text;
}

static void
_on_change(void* context, const char* name, char** line_list, size_t line_n)
/* RETURN: nothing; the region 'name' and its lines went to the
 *         SystemVerilog terminal 'context'.                                */
{
    char* text = _joined(line_list, line_n);
    _scope();
    hwut_sv_vterm_change((int)(intptr_t)context, name, text, (int)line_n);
    free(text);
}

void*
hwut_sv_vterm_terminal_new(int row_n, int column_n, double settle_s, int id)
/* RETURN: a blank terminal, nothing running in it, reporting as terminal
 *         'id'; NULL where the library is missing.                         */
{
    VtermTerminal* self = VtermTerminal_new(row_n, column_n, settle_s, &_error);
    if( ! self ) return NULL;
    VtermTerminal_on_event(self, _on_event, (void*)(intptr_t)id);
    VtermTerminal_on_change(self, _on_change, (void*)(intptr_t)id);
    return self;
}

void* hwut_sv_vterm_terminal_screen(void* terminal)
/* RETURN: the terminal's screen, for the screen's functions.               */
{ return &((VtermTerminal*)terminal)->base; }

void hwut_sv_vterm_terminal_free(void* terminal)
/* RETURN: nothing; the application is ended where it runs, the terminal gone. */
{ VtermTerminal_free((VtermTerminal*)terminal); }

void hwut_sv_vterm_region(void* terminal, const char* name, int row, int row_n, int column, int column_n)
/* RETURN: nothing; the rectangle 'name' is observed from now on.           */
{ VtermTerminal_region((VtermTerminal*)terminal, name, row, row_n, column, column_n); }

const char*
hwut_sv_vterm_region_text(void* terminal, const char* name, int* line_n)
/* RETURN: the lines of the region 'name' now, '\n' between each two, and
 *         '*line_n' their number; -1 where no region has that name
 *         ('KeyError').                                                    */
{
    static char* text = NULL;
    size_t       n;
    char**       line_list = VtermTerminal_region_text((VtermTerminal*)terminal, name, &n);
    free(text);
    text = NULL;
    if( ! line_list ) { *line_n = -1; return ""; }
    text = _joined(line_list, n);
    VtermTerminal_lines_free(line_list, n);
    *line_n = (int)n;
    return text;
}

int hwut_sv_vterm_report(void* terminal)
/* RETURN: the number of regions told as changed.                           */
{ return (int)VtermTerminal_report((VtermTerminal*)terminal); }

int hwut_sv_vterm_terminal_feed(void* terminal, const char* data)
/* RETURN: the number of bytes of 'data' the terminal took, its events told. */
{ return (int)VtermTerminal_feed((VtermTerminal*)terminal, data, strlen(data)); }

const char*
hwut_sv_vterm_answer(void* terminal)
/* RETURN: what the terminal answered and nobody took yet, now taken.       */
{
    static char* text = NULL;
    size_t       n;
    free(text);
    text = VtermTerminal_answer((VtermTerminal*)terminal, &n);
    return text ? text : "";
}

int hwut_sv_vterm_send(void* terminal, const char* text, double react_s)
/* RETURN: 1, the application still runs after 'text' was typed; 0, it does not. */
{ return VtermTerminal_send((VtermTerminal*)terminal, text, react_s); }

int hwut_sv_vterm_press(void* terminal, const char* key, const char* modifier, double react_s)
/* RETURN: 1, the application still runs after 'key' was pressed with the
 *         modifiers 'modifier' (blank-separated, '' none); 0, it does not;
 *         -1, a name is unknown ('KeyError').                              */
{ return VtermTerminal_press((VtermTerminal*)terminal, key, *modifier ? modifier : NULL, react_s); }

void
hwut_sv_vterm_argv_clear(void)
/* RETURN: nothing; no word of a command line is held.                      */
{ while( _argc ) free(_argv[--_argc]); }

void
hwut_sv_vterm_argv_add(const char* word)
/* RETURN: nothing; 'word' is the next word of the command line held.       */
{ if( _argc < 255 ) _argv[_argc++] = strdup(word); }

int
hwut_sv_vterm_run(void* terminal, const char* cwd, double start_s)
/* RETURN: 1, the application of the command line held still runs once its
 *         first screen stands; 0, it does not; -1, one was already run
 *         ('RuntimeError').                                                */
{
    _argv[_argc] = NULL;
    return VtermTerminal_run((VtermTerminal*)terminal, _argv, *cwd ? cwd : NULL, start_s);
}

int hwut_sv_vterm_pump(void* terminal, double first_s)
/* RETURN: 1, the application still runs; 0, it does not -- read until quiet. */
{ return VtermTerminal_pump((VtermTerminal*)terminal, first_s); }

int hwut_sv_vterm_expect(void* terminal, const char* text, double timeout_s, int* row, int* column)
/* RETURN: 0, 'text' stands at '*row', '*column'; -1, it did not appear
 *         within 'timeout_s' ('TimeoutError').                             */
{ return VtermTerminal_expect((VtermTerminal*)terminal, text, timeout_s, row, column); }

int hwut_sv_vterm_wait(void* terminal, double timeout_s, int* status)
/* RETURN: 1, '*status' is the application's exit status; 0, none was run;
 *         -1, it still ran after 'timeout_s' and was killed ('TimeoutError'). */
{ return VtermTerminal_wait((VtermTerminal*)terminal, timeout_s, status); }
