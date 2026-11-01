/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE C PORT'S 'hwut_vterm' AS AN ERLANG PORT PROGRAM -- one screen
 *          or terminal per program, served to 'hwut_vterm.erl' over the
 *          port's pipes. Erlang reaches C only through a NIF (in the VM's
 *          own process: a crash of libvterm or a blocking 'select' would be
 *          the VM's) or through a PORT (a process of its own, spoken to by
 *          messages): this is the port. '../c/hwut_vterm.c' is used
 *          UNCHANGED.
 *
 * THE FRAMING IS ERLANG'S '{packet, 4}': every message is a 4-byte length
 * (big-endian) and that many bytes. A message is a list of FIELDS, each a
 * 4-byte length and its bytes -- any byte may stand in a field, so nothing
 * is encoded:
 *
 *     DOWN  <command> <field> ...           numbers in decimal
 *     UP    event <kind> <row> <column> <row_end> <column_end> <name>
 *                 <value_f> <value>         a raw event, while a command runs
 *           change <name> <line> ...        a region changed, while ...
 *           ok <field> ...                  the command's result
 *           err <kind> <message>            Python's exception and its text
 *
 * The first command makes the object: 'screen <rows> <columns>' or
 * 'terminal <rows> <columns> <settle_s>'; 'detect' answers without one.
 * Then: feed <data> | cursor | cell <row> <column> | lines | on_event |
 * on_change | region <name> <row> <row_n> <column> <column_n> |
 * region_text <name> | report | answer | send <text> <react_s> |
 * press <key> <modifiers> <react_s> | run <cwd> <start_s> <env_n>
 * <NAME=value> ... <arg> ... | pump <first_s> | expect <text> <timeout_s>
 * | wait <timeout_s> | free. 'free', and the end of the input, free the
 * object -- an application still running is killed.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include "hwut_vterm.h"

#define FIELD_MAX 4096

static VtermScreen*   screen;          /* the object: a screen, ...           */
static VtermTerminal* terminal;        /* ... or a terminal (its 'base')     */

/* ---------------------------------------------------------- the transport */
static unsigned char* out;             /* the message being built           */
static size_t         out_n, out_capacity;

static void
put(const void* data, size_t length)
/* RETURN: nothing; 'length' bytes appended to the message being built.     */
{
    if( out_n + length > out_capacity ) {
        out_capacity = 2 * (out_n + length) + 256;
        if( ! (out = realloc(out, out_capacity)) ) exit(2);
    }
    memcpy(out + out_n, data, length);
    out_n += length;
}

static void
put_u32(size_t n)
{
    unsigned char b[4] = { (unsigned char)(n >> 24), (unsigned char)(n >> 16),
                           (unsigned char)(n >> 8),  (unsigned char)n };
    put(b, 4);
}

static void
field(const char* data, size_t length)
/* RETURN: nothing; one field -- its length, its bytes -- appended.         */
{ put_u32(length); put(data, length); }

static void
text(const char* s) { field(s, strlen(s)); }

static void
number(long n) { char b[32]; snprintf(b, sizeof(b), "%ld", n); text(b); }

static void
begin(const char* kind) { out_n = 0; put_u32(0); text(kind); }
/* RETURN: nothing; a message of 'kind' begun (its length filled at 'send'). */

static void
send_message(void)
/* RETURN: nothing; the message built is written, length first, and flushed;
 *         the program ends where the VM is gone.                           */
{
    size_t length = out_n - 4, k = 0;
    out[0] = (unsigned char)(length >> 24); out[1] = (unsigned char)(length >> 16);
    out[2] = (unsigned char)(length >> 8);  out[3] = (unsigned char)length;
    while( k < out_n ) {
        ssize_t n = write(1, out + k, out_n - k);
        if( n < 0 && errno == EINTR ) continue;
        if( n <= 0 ) exit(0);
        k += (size_t)n;
    }
}

static int
read_all(void* buffer, size_t length)
/* RETURN: 1, 'length' bytes were read; 0, the input ended.                 */
{
    size_t k = 0;
    while( k < length ) {
        ssize_t n = read(0, (char*)buffer + k, length - k);
        if( n < 0 && errno == EINTR ) continue;
        if( n <= 0 ) return 0;
        k += (size_t)n;
    }
    return 1;
}

static unsigned long
u32(const unsigned char* b) { return ((unsigned long)b[0] << 24) | ((unsigned long)b[1] << 16) | ((unsigned long)b[2] << 8) | b[3]; }

/* ------------------------------------------------------------- the replies */
static void
reply_error(const char* kind, const char* message)
{ begin("err"); text(kind); text(message); send_message(); }

static void
reply_ok(void) { begin("ok"); send_message(); }

static void
reply_number(long n) { begin("ok"); number(n); send_message(); }

static void
on_event(void* context, const VtermEvent* event)
/* RETURN: nothing; the raw event is reported, every field of it.           */
{
    begin("event");
    text(event->kind);
    number(event->row); number(event->column); number(event->row_end); number(event->column_end);
    text(event->name ? event->name : "");
    number(event->value_f); number(event->value);
    send_message();
}

static void
on_change(void* context, const char* name, char** line_list, size_t line_n)
/* RETURN: nothing; the changed region is reported with its lines.          */
{
    size_t i;
    begin("change");
    text(name);
    for(i = 0; i < line_n; ++i) text(line_list[i]);
    send_message();
}

static char*
z(char* f, size_t n) { f[n] = '\0'; return f; }
/* RETURN: 'f' terminated after its 'n' bytes (the byte behind it is free). */

static void
serve(char** f, size_t* n, int k)
/* RETURN: nothing; the command 'f[0]' was done and answered.               */
{
    const char*  command = f[0];
    VtermScreen* s = terminal ? &terminal->base : screen;
    VtermError   error;
    char         buffer[4096];

    if( ! strcmp(command, "detect") ) {
        begin("ok"); text(Vterm_detection_text(buffer, sizeof(buffer))); send_message();
        return;
    }
    if( ! strcmp(command, "screen") && k == 3 && ! s ) {
        if( ! (screen = VtermScreen_new(atoi(f[1]), atoi(f[2]), &error)) ) reply_error(error.kind, error.message);
        else reply_ok();
        return;
    }
    if( ! strcmp(command, "terminal") && k == 4 && ! s ) {
        if( ! (terminal = VtermTerminal_new(atoi(f[1]), atoi(f[2]), atof(f[3]), &error)) ) reply_error(error.kind, error.message);
        else reply_ok();
        return;
    }
    if( ! s ) { reply_error("RuntimeError", "no screen stands here"); return; }

    if( ! strcmp(command, "free") ) {
        if( terminal ) VtermTerminal_free(terminal);
        if( screen )   VtermScreen_free(screen);
        terminal = NULL; screen = NULL;
        reply_ok();
    }
    else
    if( ! strcmp(command, "feed") && k == 2 )
        reply_number((long)(terminal ? VtermTerminal_feed(terminal, f[1], n[1]) : VtermScreen_feed(s, f[1], n[1])));
    else if( ! strcmp(command, "cursor") ) {
        int row, column;
        VtermScreen_cursor(s, &row, &column);
        begin("ok"); number(row); number(column); send_message();
    }
    else if( ! strcmp(command, "cell") && k == 3 ) {
        VtermCell cell;
        int       i;
        if( VtermScreen_cell(s, atoi(f[1]), atoi(f[2]), &cell) ) { reply_error(s->error.kind, s->error.message); return; }
        begin("ok");
        text(cell.text); number(cell.width);
        number(cell.bold_f); number(cell.italic_f); number(cell.underline_f); number(cell.blink_f);
        number(cell.reverse_f); number(cell.conceal_f); number(cell.strike_f);
        number(cell.foreground_f); for(i = 0; i < 3; ++i) number(cell.foreground[i]);
        number(cell.background_f); for(i = 0; i < 3; ++i) number(cell.background[i]);
        send_message();
    }
    else if( ! strcmp(command, "lines") ) {
        int row;
        begin("ok");
        for(row = 0; row < s->row_n; ++row) text(VtermScreen_line(s, row, buffer, sizeof(buffer)));
        send_message();
    }
    else if( ! terminal ) reply_error("AttributeError", "a Screen is no Terminal");
    else if( ! strcmp(command, "on_event") )  { VtermTerminal_on_event(terminal, on_event, NULL);   reply_ok(); }
    else if( ! strcmp(command, "on_change") ) { VtermTerminal_on_change(terminal, on_change, NULL); reply_ok(); }
    else if( ! strcmp(command, "region") && k == 6 ) {
        VtermTerminal_region(terminal, f[1], atoi(f[2]), atoi(f[3]), atoi(f[4]), atoi(f[5]));
        reply_ok();
    }
    else if( ! strcmp(command, "region_text") && k == 2 ) {
        size_t line_n, i;
        char** line = VtermTerminal_region_text(terminal, f[1], &line_n);
        if( ! line ) { reply_error(s->error.kind, s->error.message); return; }
        begin("ok");
        for(i = 0; i < line_n; ++i) text(line[i]);
        send_message();
        VtermTerminal_lines_free(line, line_n);
    }
    else if( ! strcmp(command, "report") ) reply_number((long)VtermTerminal_report(terminal));
    else if( ! strcmp(command, "answer") ) {
        size_t length;
        char*  data = VtermTerminal_answer(terminal, &length);
        begin("ok"); field(data, length); send_message();
        free(data);
    }
    else if( ! strcmp(command, "send") && k == 3 )
        reply_number(VtermTerminal_send(terminal, f[1], atof(f[2])));
    else if( ! strcmp(command, "press") && k == 4 ) {
        int running = VtermTerminal_press(terminal, f[1], n[2] ? f[2] : NULL, atof(f[3]));
        if( running < 0 ) reply_error(s->error.kind, s->error.message);
        else              reply_number(running);
    }
    else if( ! strcmp(command, "run") && k >= 4 && 4 + atoi(f[3]) < k ) {
        /* THE ENVIRONMENT IS THE VM'S, as it stands now ('os:getenv()'):
         * this program's own is replaced by it, and the application
         * inherits it -- Python passes 'os.environ' at that moment. */
        char* argv[FIELD_MAX + 1];
        int   i, a = 0, running, environment_n = atoi(f[3]);
        clearenv();
        for(i = 4; i < 4 + environment_n; ++i) {
            char* equal = strchr(f[i], '=');
            if( equal ) { *equal = '\0'; setenv(f[i], equal + 1, 1); }
        }
        for(i = 4 + environment_n; i < k; ++i) argv[a++] = f[i];
        argv[a] = NULL;
        running = VtermTerminal_run(terminal, argv, n[1] ? f[1] : NULL, atof(f[2]));
        if( running < 0 ) reply_error(s->error.kind, s->error.message);
        else              reply_number(running);
    }
    else if( ! strcmp(command, "pump") && k == 2 ) reply_number(VtermTerminal_pump(terminal, atof(f[1])));
    else if( ! strcmp(command, "expect") && k == 3 ) {
        int row, column;
        if( VtermTerminal_expect(terminal, f[1], atof(f[2]), &row, &column) ) reply_error(s->error.kind, s->error.message);
        else { begin("ok"); number(row); number(column); send_message(); }
    }
    else if( ! strcmp(command, "wait") && k == 2 ) {
        int status = 0, r = VtermTerminal_wait(terminal, atof(f[1]), &status);
        if( r < 0 )       reply_error(s->error.kind, s->error.message);
        else if( r == 0 ) { begin("ok"); text("None"); send_message(); }
        else              reply_number(status);
    }
    else reply_error("RuntimeError", "bad command");
}

int
main(void)
/* RETURN: 0, once the input ended -- the object freed, an application still
 *         running in it killed.                                          */
{
    unsigned char  head[4];
    unsigned char* message = NULL;
    size_t         capacity = 0;
    while( read_all(head, 4) ) {
        static char*  f[FIELD_MAX];
        static size_t n[FIELD_MAX];
        size_t length = u32(head), i = 0;
        int    k = 0;
        if( length + 1 > capacity ) {
            capacity = length + 1;
            if( ! (message = realloc(message, capacity)) ) return 2;
        }
        if( ! read_all(message, length) ) break;
        /* EVERY FIELD IS MADE A C STRING IN PLACE: its bytes are moved onto
         * its own 4 length bytes, which frees 4 bytes behind it -- room for
         * the terminator before the next field's length begins. */
        while( i + 4 <= length && k < FIELD_MAX ) {
            size_t field_n = u32(message + i);
            if( i + 4 + field_n > length ) break;
            memmove(message + i, message + i + 4, field_n);
            f[k] = z((char*)message + i, field_n); n[k] = field_n;
            i += 4 + field_n;
            k++;
        }
        if( k ) serve(f, n, k);
    }
    if( terminal ) VtermTerminal_free(terminal);
    if( screen )   VtermScreen_free(screen);
    free(message); free(out);
    return 0;
}
