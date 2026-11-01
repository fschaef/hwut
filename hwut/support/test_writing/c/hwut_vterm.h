/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
 *          'python/hwut_vterm.py': libvterm, loaded by 'dlopen'.
 *
 *     VtermError   error;
 *     VtermScreen* screen = VtermScreen_new(24, 80, &error);
 *     VtermCell    cell;
 *     if( ! screen ) { printf("NOT PROBED: %s\n", error.message); return; }
 *     VtermScreen_feed(screen, "\x1b[1mbold\x1b[0m plain", 19);
 *     VtermScreen_line(screen, 0, buffer, sizeof(buffer));   -- 'bold plain'
 *     VtermScreen_cell(screen, 0, 0, &cell);                 -- cell.bold_f 1
 *     VtermScreen_free(screen);
 *
 * NO HEADER OF THE LIBRARY IS NEEDED to build this: its few structures are
 * declared here, as the Python binding declares them for 'ctypes', and the
 * library is FOUND at run time -- under the name HWUT_LIBVTERM gives, or as
 * the system knows it ('libvterm.so.0'; Debian: 'libvterm0'). Where neither
 * loads, the constructor returns NULL with the error 'LibraryMissing', whose
 * text says how to install it.
 *
 * THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED -- it changed between libvterm's
 * versions. Once per library a scratch terminal is fed one attribute at a time
 * and the bit or the bytes that changed are where that attribute stands.
 *
 * TWO CLASSES:
 *     VtermScreen     the grid alone: bytes in, cells out. No process.
 *     VtermTerminal   a screen an APPLICATION RUNS IN, on a pseudo-terminal;
 *                     its first member is its VtermScreen ('base'), so every
 *                     VtermScreen_ function applies to '&terminal->base'.
 *
 * ERRORS: a function that fails returns NULL or -1 and fills 'self->error'
 * (or the 'error' given to a constructor): the 'kind' is Python's exception
 * name -- 'LibraryMissing', 'IndexError', 'KeyError', 'TimeoutError',
 * 'RuntimeError' -- the 'message' its text.
 * _____________________________________________________________________________
 */
#ifndef HWUT_VTERM_H
#define HWUT_VTERM_H

#include <stddef.h>
#include <sys/types.h>

#define VTERM_LIBRARY_VARIABLE "HWUT_LIBVTERM"
#define VTERM_REGION_MAX        32
#define VTERM_CALLBACK_MAX      8

extern const char* const VTERM_INSTALL_HINT;
extern const char* const VTERM_ATTRIBUTE_NAME[7];   /* bold italic underline blink reverse conceal strike */
extern const char* const VTERM_ATTRIBUTE_SGR[7];    /* "1" "3" "4" "5" "7" "8" "9"                        */

typedef struct { char kind[32]; char message[2048]; } VtermError;

typedef struct {
    char text[32];                  /* UTF-8; '' for an unwritten cell, and
                                     * for the right half of a wide one     */
    int  width;
    int  bold_f, italic_f, underline_f, blink_f, reverse_f, conceal_f, strike_f;
    int  foreground_f;  unsigned char foreground[3];   /* _f 0: the default */
    int  background_f;  unsigned char background[3];
} VtermCell;

char*         VtermCell_attribute_text(const VtermCell* self, char* buffer, size_t size);

typedef struct VtermScreen {
    int         row_n, column_n;
    void*       terminal;           /* VTerm*                               */
    void*       screen;             /* VTermScreen*                         */
    void*       state;              /* VTermState*                          */
    VtermError  error;
} VtermScreen;

const char*   Vterm_detection_text(char* buffer, size_t size);
void          Vterm_reset_library(void);

VtermScreen*  VtermScreen_new(int row_n, int column_n, VtermError* error);
int           VtermScreen_init(VtermScreen* self, int row_n, int column_n);
void          VtermScreen_close(VtermScreen* self);
void          VtermScreen_free(VtermScreen* self);
size_t        VtermScreen_feed(VtermScreen* self, const char* data, size_t length);
void          VtermScreen_cursor(VtermScreen* self, int* row, int* column);
int           VtermScreen_cell(VtermScreen* self, int row, int column, VtermCell* cell);
char*         VtermScreen_line(VtermScreen* self, int row, char* buffer, size_t size);

/* ONE THING THE TERMINAL DID (the RAW layer): 'kind' is "damage", "cursor",
 * "property" or "bell". A property's 'value_f' 0 where its value is a text. */
typedef struct {
    const char* kind;
    int         row, column, row_end, column_end;
    const char* name;
    int         value_f, value;
} VtermEvent;

char*         VtermEvent_to_string(const VtermEvent* self, char* buffer, size_t size);

typedef void (*VtermTerminal_EventF)(void* context, const VtermEvent* event);
typedef void (*VtermTerminal_ChangeF)(void* context, const char* name, char** line_list, size_t line_n);

typedef struct {
    char*  name;
    int    row, row_n, column, column_n;
    char** told;                    /* the lines last told; row_n of them  */
} VtermRegion;

typedef struct VtermTerminal {
    VtermScreen  base;
    double       settle_s;
    struct { VtermTerminal_EventF  f; void* context; } event_f[VTERM_CALLBACK_MAX];  size_t event_f_n;
    struct { VtermTerminal_ChangeF f; void* context; } change_f[VTERM_CALLBACK_MAX]; size_t change_f_n;
    VtermRegion  region[VTERM_REGION_MAX];  size_t region_n;
    char*        answer;  size_t answer_n, answer_capacity;
    int          master;            /* -1: nothing runs                     */
    pid_t        process;           /* 0: never started                     */
    int          reaped_f, status;  /* the exit status, once reaped         */
    int          ended_f;
    void*        callbacks;         /* VTermScreenCallbacks, owned          */
} VtermTerminal;

VtermTerminal* VtermTerminal_new(int row_n, int column_n, double settle_s, VtermError* error);
void           VtermTerminal_free(VtermTerminal* self);
void           VtermTerminal_close(VtermTerminal* self);
void           VtermTerminal_on_event(VtermTerminal* self, VtermTerminal_EventF f, void* context);
void           VtermTerminal_on_change(VtermTerminal* self, VtermTerminal_ChangeF f, void* context);
void           VtermTerminal_region(VtermTerminal* self, const char* name, int row, int row_n, int column, int column_n);
char**         VtermTerminal_region_text(VtermTerminal* self, const char* name, size_t* line_n);
void           VtermTerminal_lines_free(char** line_list, size_t line_n);
size_t         VtermTerminal_report(VtermTerminal* self);
size_t         VtermTerminal_feed(VtermTerminal* self, const char* data, size_t length);
char*          VtermTerminal_answer(VtermTerminal* self, size_t* length);
int            VtermTerminal_send(VtermTerminal* self, const char* text, double react_s);
int            VtermTerminal_press(VtermTerminal* self, const char* key, const char* modifier, double react_s);
int            VtermTerminal_run(VtermTerminal* self, char* const* argv, const char* cwd, double start_s);
int            VtermTerminal_pump(VtermTerminal* self, double first_s);
int            VtermTerminal_expect(VtermTerminal* self, const char* text, double timeout_s, int* row, int* column);
int            VtermTerminal_wait(VtermTerminal* self, double timeout_s, int* status);

#endif
