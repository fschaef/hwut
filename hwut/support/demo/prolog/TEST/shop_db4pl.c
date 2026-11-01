/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SQLITE FOR THE SHOP -- no test: the foreign predicates behind 'shop_db.pro',
 * the few calls of SQLite 'shop.pro' and 'fixture.pro' make.
 *
 * SWI-Prolog carries no SQLite (its 'prosqlite' is a pack, not given), and
 * nothing is downloaded. The C library is LOADED at run time by 'dlopen' --
 * 'libsqlite3.so.0', the file Python's own 'sqlite3' module stands on -- so
 * building needs a C compiler and SWI-Prolog's header, no header of SQLite.
 * The handful of prototypes are declared here.
 *
 *     '$db_open'(+Path, +TimeoutMs, +Trace, -Handle)
 *     '$db_execute'(+Handle, +Sql, +Parameters, -Rows)
 *     '$db_close'(+Handle)
 *
 * A fault raises error(sqlite_error(Message), _), Message SQLite's own text
 * ('database is locked', ...). With Trace 1, every statement is written to
 * stderr as 'sql: <statement>', its parameters bound -- Python's
 * 'set_trace_callback'.
 * _____________________________________________________________________________
 */
#include <SWI-Prolog.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

typedef struct sqlite3      sqlite3;
typedef struct sqlite3_stmt sqlite3_stmt;

#define SQLITE_OK       0
#define SQLITE_ROW    100
#define SQLITE_DONE   101
#define SQLITE_INTEGER  1
#define SQLITE_FLOAT    2
#define SQLITE_NULL     5
#define SQLITE_TRANSIENT ((void (*)(void*))-1)

static int           (*p_open)(const char*, sqlite3**);
static int           (*p_close)(sqlite3*);
static int           (*p_busy_timeout)(sqlite3*, int);
static const char*   (*p_errmsg)(sqlite3*);
static int           (*p_prepare_v2)(sqlite3*, const char*, int, sqlite3_stmt**, const char**);
static int           (*p_bind_int64)(sqlite3_stmt*, int, long long);
static int           (*p_bind_text)(sqlite3_stmt*, int, const char*, int, void (*)(void*));
static int           (*p_step)(sqlite3_stmt*);
static int           (*p_column_count)(sqlite3_stmt*);
static int           (*p_column_type)(sqlite3_stmt*, int);
static long long     (*p_column_int64)(sqlite3_stmt*, int);
static double        (*p_column_double)(sqlite3_stmt*, int);
static const unsigned char* (*p_column_text)(sqlite3_stmt*, int);
static int           (*p_finalize)(sqlite3_stmt*);
static char*         (*p_expanded_sql)(sqlite3_stmt*);
static void          (*p_free)(void*);

typedef struct { sqlite3* db; int trace; } connection_t;

static int
raise_sqlite(const char* message)
/* RETURN: FALSE, with the Prolog exception error(sqlite_error(Message), _)
 *         raised. */
{
    term_t formal = PL_new_term_ref(), error = PL_new_term_ref();
    if(   !PL_unify_term(formal, PL_FUNCTOR_CHARS, "sqlite_error", 1, PL_UTF8_STRING, message)
       || !PL_unify_term(error, PL_FUNCTOR_CHARS, "error", 2, PL_TERM, formal, PL_VARIABLE) )
        return FALSE;
    return PL_raise_exception(error);
}

static int
library_loaded(void)
/* RETURN: TRUE, if every function of 'libsqlite3.so.0' is bound;
 *         FALSE, else, with an exception raised that names the library. */
{
    static void* handle = NULL;
    if( handle ) return TRUE;
    handle = dlopen("libsqlite3.so.0", RTLD_NOW);
    if( ! handle ) return raise_sqlite("libsqlite3.so.0 not found (apt install libsqlite3-0)");
#   define BIND(P, NAME) do { *(void**)(&P) = dlsym(handle, NAME); \
                              if( ! P ) { handle = NULL; return raise_sqlite("libsqlite3.so.0 lacks " NAME); } } while(0)
    BIND(p_open,          "sqlite3_open");
    BIND(p_close,         "sqlite3_close");
    BIND(p_busy_timeout,  "sqlite3_busy_timeout");
    BIND(p_errmsg,        "sqlite3_errmsg");
    BIND(p_prepare_v2,    "sqlite3_prepare_v2");
    BIND(p_bind_int64,    "sqlite3_bind_int64");
    BIND(p_bind_text,     "sqlite3_bind_text");
    BIND(p_step,          "sqlite3_step");
    BIND(p_column_count,  "sqlite3_column_count");
    BIND(p_column_type,   "sqlite3_column_type");
    BIND(p_column_int64,  "sqlite3_column_int64");
    BIND(p_column_double, "sqlite3_column_double");
    BIND(p_column_text,   "sqlite3_column_text");
    BIND(p_finalize,      "sqlite3_finalize");
    BIND(p_expanded_sql,  "sqlite3_expanded_sql");
    BIND(p_free,          "sqlite3_free");
#   undef BIND
    return TRUE;
}

static int
connection_of(term_t handle, connection_t** result)
/* RETURN: TRUE, '*result' the connection 'handle' names, if it is one;
 *         FALSE, else, with a type error raised. */
{
    void* pointer;
    if( ! PL_get_pointer_ex(handle, &pointer) ) return FALSE;
    *result = (connection_t*)pointer;
    return TRUE;
}

static foreign_t
pl_db_open(term_t path, term_t timeout_ms, term_t trace, term_t handle)
/* RETURN: TRUE, 'handle' bound to a connection to the database 'path', which
 *         waits up to 'timeout_ms' for a lock, if success;
 *         FALSE, else, with sqlite_error raised. */
{
    char*         file;
    int           timeout, trace_f;
    sqlite3*      db = NULL;
    connection_t* connection;
    if(   ! library_loaded()
       || ! PL_get_chars(path, &file, CVT_ATOM | CVT_STRING | REP_UTF8 | CVT_EXCEPTION)
       || ! PL_get_integer_ex(timeout_ms, &timeout)
       || ! PL_get_integer_ex(trace, &trace_f) ) return FALSE;
    if( p_open(file, &db) != SQLITE_OK ) {
        char message[512];
        snprintf(message, sizeof(message), "%s", db ? p_errmsg(db) : "out of memory");
        if( db ) p_close(db);
        return raise_sqlite(message);
    }
    p_busy_timeout(db, timeout);
    connection        = (connection_t*)PL_malloc(sizeof(connection_t));
    connection->db    = db;
    connection->trace = trace_f;
    return PL_unify_pointer(handle, connection);
}

static int
parameters_bound(sqlite3_stmt* statement, term_t parameters)
/* RETURN: TRUE, if every element of the list 'parameters' -- an integer or a
 *         text -- is bound to its place in 'statement';
 *         FALSE, else, with an exception raised. */
{
    term_t    tail = PL_copy_term_ref(parameters), head = PL_new_term_ref();
    int       index = 1;
    int64_t   integer;
    char*     text;
    while( PL_get_list(tail, head, tail) ) {
        if( PL_is_integer(head) ) {
            if( ! PL_get_int64_ex(head, &integer) ) return FALSE;
            p_bind_int64(statement, index, (long long)integer);
        } else {
            if( ! PL_get_chars(head, &text, CVT_ATOM | CVT_STRING | REP_UTF8 | CVT_EXCEPTION) )
                return FALSE;
            p_bind_text(statement, index, text, -1, SQLITE_TRANSIENT);
        }
        ++index;
    }
    return PL_get_nil_ex(tail);
}

static int
row_unified(sqlite3_stmt* statement, term_t row)
/* RETURN: TRUE, if 'row' is unified with the list of the current row's
 *         columns -- an integer, a float, a string, or the atom 'null';
 *         FALSE, else. */
{
    term_t tail = PL_copy_term_ref(row), head = PL_new_term_ref();
    int    i, n = p_column_count(statement), ok;
    for(i = 0; i < n; ++i) {
        if( ! PL_unify_list(tail, head, tail) ) return FALSE;
        switch( p_column_type(statement, i) ) {
        case SQLITE_INTEGER: ok = PL_unify_int64(head, (int64_t)p_column_int64(statement, i)); break;
        case SQLITE_FLOAT:   ok = PL_unify_float(head, p_column_double(statement, i));          break;
        case SQLITE_NULL:    ok = PL_unify_atom_chars(head, "null");                             break;
        default:             ok = PL_unify_chars(head, PL_STRING | REP_UTF8, (size_t)-1,
                                                 (const char*)p_column_text(statement, i));
        }
        if( ! ok ) return FALSE;
    }
    return PL_unify_nil(tail);
}

static foreign_t
pl_db_execute(term_t handle, term_t sql, term_t parameters, term_t rows)
/* RETURN: TRUE, 'rows' the list of the rows the ONE statement 'sql' gave,
 *         each a list of columns ([] for a statement that gives none), its
 *         '?' bound to 'parameters', if success;
 *         FALSE, else, with sqlite_error raised (SQLite's message). */
{
    connection_t* connection;
    char*         text;
    sqlite3_stmt* statement = NULL;
    term_t        tail = PL_copy_term_ref(rows), head = PL_new_term_ref();
    int           status;
    if(   ! connection_of(handle, &connection)
       || ! PL_get_chars(sql, &text, CVT_ATOM | CVT_STRING | REP_UTF8 | CVT_EXCEPTION) )
        return FALSE;
    if( p_prepare_v2(connection->db, text, -1, &statement, NULL) != SQLITE_OK )
        return raise_sqlite(p_errmsg(connection->db));
    if( ! parameters_bound(statement, parameters) ) { p_finalize(statement); return FALSE; }
    if( connection->trace ) {
        char* expanded = p_expanded_sql(statement);
        fprintf(stderr, "sql: %s\n", expanded ? expanded : text);
        fflush(stderr);
        if( expanded ) p_free(expanded);
    }
    while( (status = p_step(statement)) == SQLITE_ROW ) {
        if( ! PL_unify_list(tail, head, tail) || ! row_unified(statement, head) ) {
            p_finalize(statement);
            return FALSE;
        }
    }
    if( status != SQLITE_DONE ) {
        char message[512];
        snprintf(message, sizeof(message), "%s", p_errmsg(connection->db));
        p_finalize(statement);
        return raise_sqlite(message);
    }
    p_finalize(statement);
    return PL_unify_nil(tail);
}

static foreign_t
pl_db_close(term_t handle)
/* RETURN: TRUE, once the connection 'handle' is closed and freed; the handle
 *         names nothing from now on. */
{
    connection_t* connection;
    if( ! connection_of(handle, &connection) ) return FALSE;
    p_close(connection->db);
    PL_free(connection);
    return TRUE;
}

install_t
install_shop_db4pl(void)
/* RETURN: nothing; the foreign predicates are registered in 'shop_db'. */
{
    PL_register_foreign_in_module("shop_db", "$db_open",    4, pl_db_open,    0);
    PL_register_foreign_in_module("shop_db", "$db_execute", 4, pl_db_execute, 0);
    PL_register_foreign_in_module("shop_db", "$db_close",   1, pl_db_close,   0);
}
