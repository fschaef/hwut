/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE C PORT'S 'hwut_vterm' FOR A BASH TEST -- a small server that
 *          'hwut_vterm.sh' runs as its coprocess. Bash cannot call a C
 *          library, open a pseudo-terminal or wait on one with a timeout;
 *          this program does, through '../c/hwut_vterm.c' unchanged, and
 *          answers one line per request on stdin:
 *
 *     DOWN  <command> <field> ...            one line, fields by one blank
 *     UP    event <id> <text>                a raw event, while a command runs
 *           change <id> <name> <line> ...    a region changed, while ...
 *           ok <field> ...                   the command's result
 *           err <kind> <message>             Python's exception and its text
 *
 * A TEXT FIELD is %-encoded: every byte that is a blank, '%', '\', a control
 * character or beyond ASCII is '%XX'; an empty text is '%'. Objects are
 * numbered by the caller ('<id>'); one server serves every screen and
 * terminal of one bash process.
 *
 * Commands: detect | reset_library | screen_new <id> <rows> <cols> <lib> |
 * terminal_new <id> <rows> <cols> <settle_s> <lib> | free <id> | feed <id>
 * <data> | cursor <id> | cell <id> <row> <col> | lines <id> | on_event <id>
 * | on_change <id> | region <id> <name> <row> <row_n> <col> <col_n> |
 * region_text <id> <name> | report <id> | answer <id> | send <id> <text>
 * <react_s> | press <id> <key> <modifiers> <react_s> | run <id> <cwd>
 * <start_s> <env_n> <NAME=value> ... <arg> ... | pump <id> <first_s> |
 * expect <id> <text>
 * <timeout_s> | wait <id> <timeout_s>.  '<lib>' is the value HWUT_LIBVTERM
 * has in the bash process ('%' where unset); '<cwd>', '<modifiers>' '%'
 * for none.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hwut_vterm.h"

#define OBJECT_MAX 256
#define FIELD_MAX  4096        /* the environment travels in one line */

typedef struct { VtermScreen* screen; VtermTerminal* terminal; int id; } Object;

static Object object[OBJECT_MAX];

static void
put_encoded(const char* data, size_t length)
/* RETURN: nothing; 'data' is written %-encoded -- '%' for the empty text.  */
{
    static const char hex[] = "0123456789ABCDEF";
    size_t i;
    if( ! length ) { fputc('%', stdout); return; }
    for(i = 0; i < length; ++i) {
        unsigned char c = (unsigned char)data[i];
        if( c <= ' ' || c >= 0x7f || c == '%' || c == '\\' ) {
            fputc('%', stdout); fputc(hex[c >> 4], stdout); fputc(hex[c & 0xF], stdout);
        } else fputc(c, stdout);
    }
}

static size_t
decoded(char* text)
/* RETURN: the length of 'text' %-decoded in place ('%' alone: empty).      */
{
    char*  in = text;
    size_t n = 0;
    if( ! strcmp(text, "%") ) { text[0] = '\0'; return 0; }
    while( *in ) {
        if( in[0] == '%' && in[1] && in[2] ) {
            char hex[3] = { in[1], in[2], '\0' };
            text[n++] = (char)strtol(hex, NULL, 16);
            in += 3;
        } else text[n++] = *in++;
    }
    text[n] = '\0';
    return n;
}

static void
reply_error(const VtermError* error)
/* RETURN: nothing; 'err <kind> <message>' was written.                     */
{
    printf("err %s ", error->kind);
    put_encoded(error->message, strlen(error->message));
    printf("\n");
}

static Object*
find(const char* id_text)
/* RETURN: the object numbered 'id_text'; NULL where none is.               */
{
    int id = atoi(id_text), i;
    for(i = 0; i < OBJECT_MAX; ++i)
        if( (object[i].screen || object[i].terminal) && object[i].id == id ) return &object[i];
    return NULL;
}

static Object*
slot(void)
/* RETURN: a free object slot; NULL where all are taken.                    */
{
    int i;
    for(i = 0; i < OBJECT_MAX; ++i) if( ! object[i].screen && ! object[i].terminal ) return &object[i];
    return NULL;
}

static VtermScreen*
screen_of(Object* o) { return o->terminal ? &o->terminal->base : o->screen; }

static void
library_variable(char* value)
/* RETURN: nothing; HWUT_LIBVTERM is the bash process's value -- unset where
 *         that is '%'.                                                     */
{
    if( ! strcmp(value, "%") ) unsetenv(VTERM_LIBRARY_VARIABLE);
    else { decoded(value); setenv(VTERM_LIBRARY_VARIABLE, value, 1); }
}

static void
on_event(void* context, const VtermEvent* event)
{
    char text[256];
    VtermEvent_to_string(event, text, sizeof(text));
    printf("event %d ", ((Object*)context)->id); put_encoded(text, strlen(text)); printf("\n");
}

static void
on_change(void* context, const char* name, char** line_list, size_t line_n)
{
    size_t i;
    printf("change %d ", ((Object*)context)->id); put_encoded(name, strlen(name));
    for(i = 0; i < line_n; ++i) { fputc(' ', stdout); put_encoded(line_list[i], strlen(line_list[i])); }
    printf("\n");
}

static void
serve(char** field, int n)
/* RETURN: nothing; the command 'field[0]' was done and answered.           */
{
    const char* command = field[0];
    Object*     o = n > 1 ? find(field[1]) : NULL;
    VtermError  error;
    char        text[4096];

    if( ! strcmp(command, "detect") ) {
        Vterm_detection_text(text, sizeof(text));
        printf("ok "); put_encoded(text, strlen(text)); printf("\n");
        return;
    }
    if( ! strcmp(command, "reset_library") ) { Vterm_reset_library(); printf("ok\n"); return; }
    if( ! strcmp(command, "screen_new") && n == 5 ) {
        Object* s = slot();
        library_variable(field[4]);
        if( ! s ) { printf("err RuntimeError too%%20many%%20screens\n"); return; }
        if( ! (s->screen = VtermScreen_new(atoi(field[2]), atoi(field[3]), &error)) ) { reply_error(&error); return; }
        s->id = atoi(field[1]);
        printf("ok\n");
        return;
    }
    if( ! strcmp(command, "terminal_new") && n == 6 ) {
        Object* s = slot();
        library_variable(field[5]);
        if( ! s ) { printf("err RuntimeError too%%20many%%20terminals\n"); return; }
        if( ! (s->terminal = VtermTerminal_new(atoi(field[2]), atoi(field[3]), atof(field[4]), &error)) ) {
            reply_error(&error); return;
        }
        s->id = atoi(field[1]);
        printf("ok\n");
        return;
    }
    if( ! o ) { printf("err RuntimeError no%%20such%%20object\n"); return; }

    if( ! strcmp(command, "free") ) {
        if( o->terminal ) VtermTerminal_free(o->terminal); else VtermScreen_free(o->screen);
        o->terminal = NULL; o->screen = NULL;
        printf("ok\n");
    }
    else if( ! strcmp(command, "feed") && n == 3 ) {
        size_t length = decoded(field[2]);
        size_t taken  = o->terminal ? VtermTerminal_feed(o->terminal, field[2], length)
                                    : VtermScreen_feed(o->screen, field[2], length);
        printf("ok %zu\n", taken);
    }
    else if( ! strcmp(command, "cursor") ) {
        int row, column;
        VtermScreen_cursor(screen_of(o), &row, &column);
        printf("ok %d %d\n", row, column);
    }
    else if( ! strcmp(command, "cell") && n == 4 ) {
        VtermCell cell;
        char      said[256];
        if( VtermScreen_cell(screen_of(o), atoi(field[2]), atoi(field[3]), &cell) ) { reply_error(&screen_of(o)->error); return; }
        printf("ok "); put_encoded(cell.text, strlen(cell.text));
        printf(" %d %d %d %d %d %d %d %d", cell.width, cell.bold_f, cell.italic_f, cell.underline_f,
               cell.blink_f, cell.reverse_f, cell.conceal_f, cell.strike_f);
        printf(" %d %d %d %d", cell.foreground_f, cell.foreground[0], cell.foreground[1], cell.foreground[2]);
        printf(" %d %d %d %d ", cell.background_f, cell.background[0], cell.background[1], cell.background[2]);
        VtermCell_attribute_text(&cell, said, sizeof(said));
        put_encoded(said, strlen(said));
        printf("\n");
    }
    else if( ! strcmp(command, "lines") ) {
        VtermScreen* s = screen_of(o);
        int row;
        printf("ok");
        for(row = 0; row < s->row_n; ++row) {
            VtermScreen_line(s, row, text, sizeof(text));
            fputc(' ', stdout); put_encoded(text, strlen(text));
        }
        printf("\n");
    }
    else if( ! o->terminal ) printf("err AttributeError a%%20Screen%%20is%%20no%%20Terminal\n");
    else if( ! strcmp(command, "on_event") )  { VtermTerminal_on_event(o->terminal, on_event, o);   printf("ok\n"); }
    else if( ! strcmp(command, "on_change") ) { VtermTerminal_on_change(o->terminal, on_change, o); printf("ok\n"); }
    else if( ! strcmp(command, "region") && n == 7 ) {
        decoded(field[2]);
        VtermTerminal_region(o->terminal, field[2], atoi(field[3]), atoi(field[4]), atoi(field[5]), atoi(field[6]));
        printf("ok\n");
    }
    else if( ! strcmp(command, "region_text") && n == 3 ) {
        size_t line_n, i;
        char** line;
        decoded(field[2]);
        if( ! (line = VtermTerminal_region_text(o->terminal, field[2], &line_n)) ) { reply_error(&o->terminal->base.error); return; }
        printf("ok");
        for(i = 0; i < line_n; ++i) { fputc(' ', stdout); put_encoded(line[i], strlen(line[i])); }
        printf("\n");
        VtermTerminal_lines_free(line, line_n);
    }
    else if( ! strcmp(command, "report") ) printf("ok %zu\n", VtermTerminal_report(o->terminal));
    else if( ! strcmp(command, "answer") ) {
        size_t length;
        char*  data = VtermTerminal_answer(o->terminal, &length);
        printf("ok "); put_encoded(data, length); printf("\n");
        free(data);
    }
    else if( ! strcmp(command, "send") && n == 4 ) {
        decoded(field[2]);
        printf("ok %d\n", VtermTerminal_send(o->terminal, field[2], atof(field[3])));
    }
    else if( ! strcmp(command, "press") && n == 5 ) {
        int running;
        decoded(field[2]); decoded(field[3]);
        running = VtermTerminal_press(o->terminal, field[2], field[3][0] ? field[3] : NULL, atof(field[4]));
        if( running < 0 ) reply_error(&o->terminal->base.error);
        else              printf("ok %d\n", running);
    }
    else if( ! strcmp(command, "run") && n >= 6 && 5 + atoi(field[4]) < n ) {
        /* THE ENVIRONMENT IS THE BASH PROCESS'S, as it stands now: this
         * server's own is replaced by it, and the application inherits. */
        char* argv[FIELD_MAX + 1];
        int   i, k = 0, running, environment_n = atoi(field[4]);
        decoded(field[2]);
        clearenv();
        for(i = 5; i < 5 + environment_n; ++i) {
            char* equal;
            decoded(field[i]);
            if( (equal = strchr(field[i], '=')) ) { *equal = '\0'; setenv(field[i], equal + 1, 1); }
        }
        for(i = 5 + environment_n; i < n; ++i) { decoded(field[i]); argv[k++] = field[i]; }
        argv[k] = NULL;
        running = VtermTerminal_run(o->terminal, argv, field[2][0] ? field[2] : NULL, atof(field[3]));
        if( running < 0 ) reply_error(&o->terminal->base.error);
        else              printf("ok %d\n", running);
    }
    else if( ! strcmp(command, "pump") && n == 3 ) printf("ok %d\n", VtermTerminal_pump(o->terminal, atof(field[2])));
    else if( ! strcmp(command, "expect") && n == 4 ) {
        int row, column;
        decoded(field[2]);
        if( VtermTerminal_expect(o->terminal, field[2], atof(field[3]), &row, &column) ) reply_error(&o->terminal->base.error);
        else printf("ok %d %d\n", row, column);
    }
    else if( ! strcmp(command, "wait") && n == 3 ) {
        int status = 0, r = VtermTerminal_wait(o->terminal, atof(field[2]), &status);
        if( r < 0 )       reply_error(&o->terminal->base.error);
        else if( r == 0 ) printf("ok None\n");
        else              printf("ok %d\n", status);
    }
    else printf("err RuntimeError bad%%20command\n");
}

int
main(void)
/* RETURN: 0, once the input ended -- every object freed, every application
 *         still running killed.                                          */
{
    char*  line = NULL;
    size_t capacity = 0;
    int    i;
    while( getline(&line, &capacity, stdin) > 0 ) {
        static char* field[FIELD_MAX];
        int   n = 0;
        char* save = NULL;
        char* word = strtok_r(line, " \n", &save);
        while( word && n < FIELD_MAX ) { field[n++] = word; word = strtok_r(NULL, " \n", &save); }
        if( n ) serve(field, n);
        fflush(stdout);
    }
    for(i = 0; i < OBJECT_MAX; ++i) {
        if( object[i].terminal ) VtermTerminal_free(object[i].terminal);
        if( object[i].screen )   VtermScreen_free(object[i].screen);
    }
    free(line);
    return 0;
}
