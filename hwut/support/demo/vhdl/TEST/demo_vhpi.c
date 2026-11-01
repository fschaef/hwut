/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: WHAT THE DEMONSTRATION'S VHDL CANNOT DO ITSELF, by VHPIDIRECT --
 *          beside what the port's 'hwut_vhpi.c' gives: the clock (a seed,
 *          a calibration stamp), files and directories, SQLite (the shop),
 *          stderr, and the raw terminal of 'viewer.vhd'. It decides,
 *          formats and schedules nothing; 'demo_vhpi.vhd' declares it.
 *
 * Linked by 'Makefile' into the target's own 'libhwut_vhdl.so', with the
 * port's glue: one library, the name every 'foreign' attribute gives.
 * A text going back to VHDL is left in a RESULT buffer of this file
 * ('demo_vhpi_result_n' / '_get'), a database known by a handle.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#ifdef DEMO_SQLITE
#   include <sqlite3.h>
#endif

typedef struct { int32_t left, right; int8_t direction; int32_t length; } DemoVhpi_Bounds;
typedef struct { char* base; DemoVhpi_Bounds* bounds; } DemoVhpi_String;

/* ------------------------------------------------------------ the plumbing */
static char* argument_slot[4];

static const char*
_text(int slot, const DemoVhpi_String* s)
/* RETURN: the characters of 's', NUL-terminated, valid until 'slot' is used
 *         again.                                                            */
{
    size_t n = (size_t)s->bounds->length;
    free(argument_slot[slot]);
    argument_slot[slot] = malloc(n + 1);
    memcpy(argument_slot[slot], s->base, n);
    argument_slot[slot][n] = '\0';
    return argument_slot[slot];
}

static char*  result;
static size_t result_n;

static void
_result(const char* text, size_t n)
/* RETURN: nothing; 'n' bytes of 'text' are the result.                      */
{
    free(result);
    result = malloc(n + 1);
    if( n ) memcpy(result, text, n);
    result[n] = '\0';
    result_n  = n;
}

int demo_vhpi_result_n(void)
/* RETURN: the length of the result.                                         */
{ return (int)result_n; }

void demo_vhpi_result_get(DemoVhpi_String* out)
/* RETURN: nothing; 'out' (as long as the result) holds the result.          */
{ if( result_n ) memcpy(out->base, result, result_n); }

/* --------------------------------------------------------------- the clock */
int demo_vhpi_seed(int k)
/* RETURN: a seed from the clock's nanoseconds, 1 .. 2147483000, different
 *         for 'k' = 1 and 2 -- math_real.uniform's two seeds.               */
{
    struct timespec now;
    uint64_t        x;
    clock_gettime(CLOCK_REALTIME, &now);
    x  = (uint64_t)now.tv_sec * 1000000000u + (uint64_t)now.tv_nsec + (uint64_t)getpid() * 7919u;
    x ^= (uint64_t)k * 0x9E3779B97F4A7C15ull;
    x ^= x >> 33; x *= 0xff51afd7ed558ccdull; x ^= x >> 33;
    return (int)(x % 2147483000u) + 1;
}

void demo_vhpi_stamp(void)
/* RETURN: nothing; the result is the local time, '%Y-%m-%dT%H:%M:%S'.       */
{
    char      b[32];
    time_t    now = time(NULL);
    struct tm tm;
    localtime_r(&now, &tm);
    _result(b, strftime(b, sizeof(b), "%Y-%m-%dT%H:%M:%S", &tm));
}

/* ------------------------------------------------------- files and stderr */
int demo_vhpi_exists(const DemoVhpi_String* path)
/* RETURN: 1, 'path' stands; 0, else.                                        */
{ return access(_text(0, path), F_OK) == 0; }

void demo_vhpi_mkdir(const DemoVhpi_String* path)
/* RETURN: nothing; the directory 'path' stands (its parent must).           */
{ (void)mkdir(_text(0, path), 0755); }

void demo_vhpi_remove(const DemoVhpi_String* path)
/* RETURN: nothing; 'path' does not stand (any more).                        */
{ (void)unlink(_text(0, path)); }

void demo_vhpi_eprint(const DemoVhpi_String* text)
/* RETURN: nothing; 'text' and a newline stand on stderr.                    */
{ fflush(stdout); fprintf(stderr, "%s\n", _text(0, text)); fflush(stderr); }

/* ------------------------------------------- the raw terminal of a viewer */
static struct termios saved;
static int            saved_f = 0;

void demo_vhpi_write(const DemoVhpi_String* text)
/* RETURN: nothing; the bytes of 'text', no more, stand on stdout.           */
{
    size_t done = 0, n = (size_t)text->bounds->length;
    fflush(stdout);
    while( done < n ) {
        ssize_t k = write(1, text->base + done, n - done);
        if( k < 0 ) { if( errno == EINTR ) continue; return; }
        done += (size_t)k;
    }
}

int demo_vhpi_terminal_size(int which)
/* RETURN: the terminal's rows ('which' = 0) or columns (1) of stdout;
 *         24 / 80 where stdout is no terminal.                              */
{
    struct winsize w;
    if( ioctl(1, TIOCGWINSZ, &w) != 0 || w.ws_row == 0 ) return which ? 80 : 24;
    return which ? w.ws_col : w.ws_row;
}

void demo_vhpi_raw(int on)
/* RETURN: nothing; stdin is raw ('on' = 1) -- every byte as typed, no echo
 *         -- or as it was before (0).                                       */
{
    struct termios raw;
    if( on ) {
        if( tcgetattr(0, &saved) != 0 ) return;
        saved_f = 1;
        raw = saved;
        cfmakeraw(&raw);
        tcsetattr(0, TCSAFLUSH, &raw);
    } else if( saved_f ) {
        tcsetattr(0, TCSADRAIN, &saved);
    }
}

int demo_vhpi_read_key(void)
/* RETURN: the number of bytes one read of stdin gave (up to 8), the bytes
 *         the result; 0 at the end of the input.                            */
{
    char    b[8];
    ssize_t n;
    do n = read(0, b, sizeof(b)); while( n < 0 && errno == EINTR );
    _result(b, n > 0 ? (size_t)n : 0);
    return n > 0 ? (int)n : 0;
}

/* ------------------------------------------------------------------ SQLite */
#ifdef DEMO_SQLITE
#define DB_MAX 16
static sqlite3* db_table[DB_MAX];

static int
_trace(unsigned kind, void* context, void* statement, void* sql)
/* RETURN: 0; the statement about to run stands on stderr, as a server logs. */
{
    char* expanded = sqlite3_expanded_sql((sqlite3_stmt*)statement);
    (void)kind; (void)context; (void)sql;
    fprintf(stderr, "sql: %s\n", expanded ? expanded : (const char*)sql);
    sqlite3_free(expanded);
    return 0;
}

int demo_vhpi_sql_open(const DemoVhpi_String* path, int trace_f)
/* RETURN: a handle > 0 of the database 'path' (busy: waits up to 10 s), its
 *         statements logged on stderr where 'trace_f' is 1; 0, it cannot be
 *         opened -- the reason the result.                                  */
{
    int h;
    for(h = 1; h < DB_MAX && db_table[h]; ++h) {}
    if( h == DB_MAX ) { _result("too many databases", 18); return 0; }
    if( sqlite3_open(_text(0, path), &db_table[h]) != SQLITE_OK ) {
        const char* why = sqlite3_errmsg(db_table[h]);
        _result(why, strlen(why));
        sqlite3_close(db_table[h]); db_table[h] = NULL;
        return 0;
    }
    sqlite3_busy_timeout(db_table[h], 10000);
    if( trace_f ) sqlite3_trace_v2(db_table[h], SQLITE_TRACE_STMT, _trace, NULL);
    return h;
}

int demo_vhpi_sql(int h, const DemoVhpi_String* sql)
/* RETURN: 0, the statements of 'sql' ran -- the result their rows, the
 *         columns joined by ';', every row ended by LF;
 *         1, else -- the result SQLite's message.                           */
{
    sqlite3_stmt* statement;
    const char*   rest;
    char*         text = NULL;
    size_t        n = 0;
    FILE*         out;
    int           rc = 0, i;
    if( h <= 0 || h >= DB_MAX || ! db_table[h] ) { _result("no database", 11); return 1; }
    out  = open_memstream(&text, &n);
    rest = _text(0, sql);
    while( *rest ) {
        if( sqlite3_prepare_v2(db_table[h], rest, -1, &statement, &rest) != SQLITE_OK ) { rc = 1; break; }
        if( ! statement ) continue;
        for(;;) {
            int step = sqlite3_step(statement);
            if( step == SQLITE_DONE ) break;
            if( step != SQLITE_ROW )  { rc = 1; break; }
            for(i = 0; i < sqlite3_column_count(statement); ++i) {
                const unsigned char* v = sqlite3_column_text(statement, i);
                fprintf(out, "%s%s", i ? ";" : "", v ? (const char*)v : "");
            }
            fputc('\n', out);
        }
        sqlite3_finalize(statement);
        if( rc ) break;
    }
    fclose(out);
    if( rc ) { const char* why = sqlite3_errmsg(db_table[h]); _result(why, strlen(why)); }
    else     _result(text, n);
    free(text);
    return rc;
}

void demo_vhpi_sql_close(int h)
/* RETURN: nothing; the database of handle 'h' is closed.                    */
{
    if( h <= 0 || h >= DB_MAX || ! db_table[h] ) return;
    sqlite3_close(db_table[h]);
    db_table[h] = NULL;
}
#endif
