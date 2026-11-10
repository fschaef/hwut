/* @hwut {
 *     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
 *     build     { framework = "make", target = "%.exe" }
 *     tolerance { stderr_ignored = true }
 *     choices {
 *         sell   { features = ["demo-c+cover-unordered-table", "demo-c+cover-stderr-ignored", "demo-c+cover-collision"] }
 *         report { features = ["demo-c+cover-output-file", "demo-c+cover-keyed-table-separator", "demo-c+cover-dependency",
 *                              "demo-c+cover-frame-scripts", "demo-c+cover-test-scripts", "demo-c+cover-stderr-ignored"]
 *                  output   = ["<stdout>", "stock.csv"] }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
 *          comes in, three clerks sell at once, and the stock is reported.
 * REQUIREMENT  Every movement of the stock is journalled, so that the stock
 *              always ADDS UP: opening quantity plus the journal's movements.
 *
 * THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
 * this file, read it first. hwut, when it enters this directory:
 *
 *     on_entry        'make ... && ./fixture.exe open': the helpers built,
 *                     and a fresh 'TMP/shop.db', stocked
 *     on_before_test  './fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
 *     on_after_test   './fixture.exe check after ...': around every test
 *                     run, whether the stock adds up, into 'TMP/frame.log'
 *                     -- hwut sets the two variables for the run
 *     on_exit         './fixture.exe close'
 *     apps            'delivery.json' is a test, though it carries no
 *                     header: JSON has no comment to carry one. 'admit'
 *                     takes it out of the files hwut ignores by default
 *                     ('*.json'); 'execute' says how it is run --
 *                     './shop.exe deliver delivery.json'.
 *     collision       'delivery.json' and 'shop.c sell' both write the
 *                     database. SQLite lets one writer at a time hold the
 *                     file; one that waits too long fails with 'database
 *                     is locked'. hwut never runs the two at once.
 *     dependency      'shop.c report' runs after both, whatever their
 *                     verdict: it reports what they left.
 *
 * STDERR  Every SQL statement is logged on stderr, as a server would. A word
 * on stderr fails a run ('unexpected stderr') unless the header says
 * 'stderr_ignored = true': the words there are on purpose, and no error.
 *
 * CHOICES
 *
 * sell     three clerks sell at once, each in a thread of its own with a
 *          connection of its own. The sales are printed as '##! table
 *          unordered sep={;}': rows of 'item;qty', in any order -- and no
 *          column is a key, 'apple;1' stands four times.
 *
 * report   the stock, as '##! table key=0 sep={;}', and the same rows
 *          written to 'stock.csv': 'output' names the file, hwut reads it
 *          after the run and compares it with its own GOOD. Then the frame
 *          log of the shop's tests: what 'on_before_test' and 'on_after_test'
 *          found around the delivery and the sale ('##! potpourri': which
 *          ran first is free), and before this report.
 *
 * deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
 *          delivery note: every line on the stock and into the journal, in
 *          one transaction. The note is read by the small JSON reader below.
 *
 * WANTS the SQLite library and its header (Debian: libsqlite3-dev).
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <libgen.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sqlite3.h>

static char HERE[PATH_MAX], DB_PATH[PATH_MAX + 16], LOG_PATH[PATH_MAX + 16];

/* What each clerk sells, one item per sale. */
static const struct { const char* name; const char* item[4]; } CLERK_DB[3] = {
    { "anna",  { "apple", "apple", "pear", NULL } },
    { "ben",   { "apple", "plum", NULL } },
    { "chloe", { "apple", NULL } },
};

static void
paths_init(void)
/* RETURN: nothing; HERE is the directory this executable stands in (the test
 *         directory), DB_PATH and LOG_PATH the shop's files in its 'TMP/'. */
{
    char    path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if( n < 0 ) n = (ssize_t)strlen(strcpy(path, "./x"));
    path[n] = '\0';
    snprintf(HERE, sizeof(HERE), "%s", dirname(path));
    snprintf(DB_PATH,  sizeof(DB_PATH),  "%s/TMP/shop.db",   HERE);
    snprintf(LOG_PATH, sizeof(LOG_PATH), "%s/TMP/frame.log", HERE);
}

static int
traced(unsigned kind, void* context, void* statement, void* sql)
/* RETURN: int, 0 -- the statement about to run logged on stderr, 'sql: ...'. */
{
    (void)kind; (void)context; (void)statement;
    fprintf(stderr, "sql: %s\n", (const char*)sql);
    return 0;
}

static sqlite3*
connect(void)
/* RETURN: sqlite3*, a connection to the shop's database, every statement it
 *         executes logged on stderr, waiting up to 10 s for a lock.
 *         Exits 1 where the database does not stand: 'on_entry' writes it. */
{
    sqlite3* db;
    if( access(DB_PATH, F_OK) != 0 ) {
        fprintf(stderr, "shop.exe: no %s -- 'on_entry' writes it; by hand: "
                        "'hwut.execute fixture open'\n", DB_PATH);
        exit(1);
    }
    if( sqlite3_open(DB_PATH, &db) != SQLITE_OK ) {
        fprintf(stderr, "shop.exe: %s\n", sqlite3_errmsg(db));
        exit(1);
    }
    sqlite3_busy_timeout(db, 10000);
    sqlite3_trace_v2(db, SQLITE_TRACE_STMT, traced, NULL);
    return db;
}

static int
move(sqlite3* db, const char* item, int delta, const char* source)
/* RETURN: int, SQLITE_OK -- the stock of 'item' changed by 'delta' and the
 *         change journalled, in one transaction; else SQLite's error code
 *         (the transaction rolled back).                                   */
{
    sqlite3_stmt* statement;
    int           result = sqlite3_exec(db, "BEGIN IMMEDIATE", NULL, NULL, NULL);
    if( result != SQLITE_OK ) return result;
    sqlite3_prepare_v2(db, "UPDATE stock SET qty = qty + ? WHERE item = ?", -1, &statement, NULL);
    sqlite3_bind_int(statement, 1, delta);
    sqlite3_bind_text(statement, 2, item, -1, SQLITE_STATIC);
    result = sqlite3_step(statement) == SQLITE_DONE ? SQLITE_OK : sqlite3_errcode(db);
    sqlite3_finalize(statement);
    if( result == SQLITE_OK ) {
        sqlite3_prepare_v2(db, "INSERT INTO journal VALUES (?, ?, ?)", -1, &statement, NULL);
        sqlite3_bind_text(statement, 1, item, -1, SQLITE_STATIC);
        sqlite3_bind_int(statement, 2, delta);
        sqlite3_bind_text(statement, 3, source, -1, SQLITE_STATIC);
        result = sqlite3_step(statement) == SQLITE_DONE ? SQLITE_OK : sqlite3_errcode(db);
        sqlite3_finalize(statement);
    }
    if( result == SQLITE_OK ) result = sqlite3_exec(db, "COMMIT", NULL, NULL, NULL);
    if( result != SQLITE_OK ) sqlite3_exec(db, "ROLLBACK", NULL, NULL, NULL);
    return result;
}

/* _____________________________________________________________________________
 * THE DELIVERY NOTE -- JSON, read into a tree. Enough JSON for a note:
 * objects, arrays, strings (with the simple escapes), numbers, true, false,
 * null.
 */
typedef enum { JSON_NULL, JSON_BOOL, JSON_NUMBER, JSON_STRING, JSON_ARRAY, JSON_OBJECT } JsonKind;

typedef struct Json {
    JsonKind      kind;
    double        number;
    char*         string;                   /* JSON_STRING                  */
    struct Json** item;   size_t item_n;    /* JSON_ARRAY, JSON_OBJECT      */
    char**        key;                      /* JSON_OBJECT: one per item    */
} Json;

static void
skip(const char** at)
/* RETURN: nothing; '*at' stands past any white space. */
{ while( isspace((unsigned char)**at) ) ++*at; }

static Json* Json_parse(const char** at);

static char*
Json_string(const char** at)
/* RETURN: char*, the string that starts at '*at' (on its quote), allocated;
 *         NULL where none does. '*at' stands past its closing quote.       */
{
    size_t n = 0;
    char*  text;
    if( **at != '"' ) return NULL;
    text = malloc(strlen(*at) + 1);
    for(++*at; **at && **at != '"'; ++*at) {
        if( **at == '\\' && (*at)[1] ) {
            ++*at;
            text[n++] = **at == 'n' ? '\n' : **at == 't' ? '\t' : **at;
        } else text[n++] = **at;
    }
    if( **at == '"' ) ++*at;
    text[n] = '\0';
    return text;
}

static Json*
Json_parse(const char** at)
/* RETURN: Json*, the value that starts at '*at', allocated; NULL where the
 *         text is no JSON there. '*at' stands past the value.              */
{
    Json* self = calloc(1, sizeof(Json));
    skip(at);
    if( **at == '{' || **at == '[' ) {
        char closing = **at == '{' ? '}' : ']';
        self->kind = **at == '{' ? JSON_OBJECT : JSON_ARRAY;
        for(++*at, skip(at); **at && **at != closing; skip(at)) {
            self->item = realloc(self->item, (self->item_n + 1) * sizeof(Json*));
            if( self->kind == JSON_OBJECT ) {
                self->key = realloc(self->key, (self->item_n + 1) * sizeof(char*));
                self->key[self->item_n] = Json_string(at);
                skip(at);
                if( **at == ':' ) ++*at;
            }
            if( ! (self->item[self->item_n++] = Json_parse(at)) ) return NULL;
            skip(at);
            if( **at == ',' ) ++*at;
        }
        if( **at != closing ) return NULL;
        ++*at;
    }
    else if( **at == '"' )                 { self->kind = JSON_STRING; self->string = Json_string(at); }
    else if( strncmp(*at, "true", 4) == 0 ) { self->kind = JSON_BOOL;  self->number = 1; *at += 4; }
    else if( strncmp(*at, "false", 5) == 0 ){ self->kind = JSON_BOOL;  *at += 5; }
    else if( strncmp(*at, "null", 4) == 0 ) { self->kind = JSON_NULL;  *at += 4; }
    else {
        char* end;
        self->kind   = JSON_NUMBER;
        self->number = strtod(*at, &end);
        if( end == *at ) return NULL;
        *at = end;
    }
    return self;
}

static const Json*
Json_get(const Json* self, const char* key)
/* RETURN: const Json*, the member 'key' of the object 'self'; NULL where
 *         'self' is no object or has no such member.                       */
{
    size_t i;
    if( ! self || self->kind != JSON_OBJECT ) return NULL;
    for(i = 0; i < self->item_n; ++i) if( self->key[i] && strcmp(self->key[i], key) == 0 ) return self->item[i];
    return NULL;
}

static void
deliver(const char* path)
/* RETURN: nothing. Books the delivery note in 'path' and prints it; exits 1
 *         where the note cannot be read or booked.                         */
{
    FILE*       fh = fopen(path, "r");
    static char text[65536];
    const char* at = text;
    size_t      n, i;
    const Json *note, *line_list, *line;
    sqlite3*    db;
    sqlite3_stmt* statement;
    int         ok_f = 1;
    if( ! fh ) { fprintf(stderr, "shop.exe: cannot read %s\n", path); exit(1); }
    n = fread(text, 1, sizeof(text) - 1, fh); text[n] = '\0'; fclose(fh);
    note      = Json_parse(&at);
    line_list = Json_get(note, "lines");
    if( ! line_list || ! Json_get(note, "note") || ! Json_get(note, "supplier") ) {
        fprintf(stderr, "shop.exe: %s is no delivery note\n", path); exit(1);
    }
    db = connect();
    sqlite3_exec(db, "BEGIN IMMEDIATE", NULL, NULL, NULL);
    for(i = 0; i < line_list->item_n; ++i) {
        line = line_list->item[i];
        sqlite3_prepare_v2(db, "UPDATE stock SET qty = qty + ? WHERE item = ?", -1, &statement, NULL);
        sqlite3_bind_int(statement, 1, (int)Json_get(line, "qty")->number);
        sqlite3_bind_text(statement, 2, Json_get(line, "item")->string, -1, SQLITE_STATIC);
        ok_f &= sqlite3_step(statement) == SQLITE_DONE;
        sqlite3_finalize(statement);
        sqlite3_prepare_v2(db, "INSERT INTO journal VALUES (?, ?, ?)", -1, &statement, NULL);
        sqlite3_bind_text(statement, 1, Json_get(line, "item")->string, -1, SQLITE_STATIC);
        sqlite3_bind_int(statement, 2, (int)Json_get(line, "qty")->number);
        sqlite3_bind_text(statement, 3, Json_get(note, "note")->string, -1, SQLITE_STATIC);
        ok_f &= sqlite3_step(statement) == SQLITE_DONE;
        sqlite3_finalize(statement);
    }
    if( ! ok_f || sqlite3_exec(db, "COMMIT", NULL, NULL, NULL) != SQLITE_OK ) {
        fprintf(stderr, "shop.exe: the delivery failed -- %s\n", sqlite3_errmsg(db)); exit(1);
    }
    sqlite3_close(db);
    printf("delivery note %s from %s:\n", Json_get(note, "note")->string, Json_get(note, "supplier")->string);
    for(i = 0; i < line_list->item_n; ++i)
        printf("    %-6s +%d\n", Json_get(line_list->item[i], "item")->string,
               (int)Json_get(line_list->item[i], "qty")->number);
}

/* _____________________________________________________________________________
 * sell -- three clerks at once
 */
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static char            sale_list[16][32];
static size_t          sale_n;
static char            error_text[1024];

static void*
clerk(void* argument)
/* RETURN: NULL. The clerk sold her items, each in a transaction of its own;
 *         a failure is noted in 'error_text'.                              */
{
    size_t   k = (size_t)argument, i;
    sqlite3* db = connect();
    int      result;
    for(i = 0; CLERK_DB[k].item[i]; ++i) {
        result = move(db, CLERK_DB[k].item[i], -1, CLERK_DB[k].name);
        pthread_mutex_lock(&lock);
        if( result == SQLITE_OK )
            snprintf(sale_list[sale_n++], sizeof(sale_list[0]), "%s;1", CLERK_DB[k].item[i]);
        else
            snprintf(error_text + strlen(error_text), sizeof(error_text) - strlen(error_text),
                     "%s%s: %s", error_text[0] ? "; " : "", CLERK_DB[k].name, sqlite3_errstr(result));
        pthread_mutex_unlock(&lock);
        if( result != SQLITE_OK ) break;
    }
    sqlite3_close(db);
    return NULL;
}

static void
sell(void)
/* RETURN: nothing. Three clerks sell at once; prints every sale. Exits 1
 *         where a sale failed.                                              */
{
    pthread_t thread[3];
    size_t    i;
    sqlite3_close(connect());
    for(i = 0; i < 3; ++i) pthread_create(&thread[i], NULL, clerk, (void*)i);
    for(i = 0; i < 3; ++i) pthread_join(thread[i], NULL);
    if( error_text[0] ) {
        fprintf(stderr, "shop.exe: a sale failed -- %s\n", error_text);
        exit(1);
    }
    printf("sales, item;qty -- in the order the clerks booked them:\n");
    printf("##! table unordered sep={;}\n");
    for(i = 0; i < sale_n; ++i) printf("%s\n", sale_list[i]);
    printf("####\n");
}

/* _____________________________________________________________________________
 * report -- the stock, 'stock.csv', and the frame log
 */
static void
report(void)
/* RETURN: nothing. Prints the stock and the frame log; writes 'stock.csv'. */
{
    sqlite3*      db = connect();
    sqlite3_stmt* statement;
    char          path[PATH_MAX + 16], line[256];
    FILE*         fh;
    snprintf(path, sizeof(path), "%s/stock.csv", HERE);
    fh = fopen(path, "w");
    fprintf(fh, "item;qty\n");
    sqlite3_prepare_v2(db, "SELECT item, qty FROM stock ORDER BY item", -1, &statement, NULL);
    while( sqlite3_step(statement) == SQLITE_ROW )
        fprintf(fh, "%s;%d\n", sqlite3_column_text(statement, 0), sqlite3_column_int(statement, 1));
    sqlite3_finalize(statement);
    fclose(fh);
    printf("stock, item;qty (also written to stock.csv):\n");
    printf("##! table key=0 sep={;}\n");
    sqlite3_prepare_v2(db, "SELECT item, qty FROM stock ORDER BY qty, item", -1, &statement, NULL);
    while( sqlite3_step(statement) == SQLITE_ROW )
        printf("%s;%d\n", sqlite3_column_text(statement, 0), sqlite3_column_int(statement, 1));
    sqlite3_finalize(statement);
    sqlite3_close(db);
    printf("####\n");
    printf("the frame, around the delivery and the sale:\n");
    printf("##! potpourri\n");
    if( (fh = fopen(LOG_PATH, "r")) ) {
        while( fgets(line, sizeof(line), fh) ) {
            line[strcspn(line, "\n")] = '\0';
            if( ! strstr(line, "shop.c report") ) printf("%s\n", line);
        }
        rewind(fh);
        printf("####\n");
        while( fgets(line, sizeof(line), fh) ) {
            line[strcspn(line, "\n")] = '\0';
            if( strstr(line, "shop.c report") ) printf("%s\n", line);
        }
        fclose(fh);
    } else printf("####\n");
}

int
main(int argc, char** argv)
/* RETURN: int, 0 -- the command ran and '<hwut-end>' closed its output;
 *         1, an unknown command (the choices are named), or a failure that
 *         was said on stderr.                                               */
{
    const char* command = argc > 1 ? argv[1] : "";
    paths_init();
    if     ( strcmp(command, "deliver") == 0 && argc > 2 ) deliver(argv[2]);
    else if( strcmp(command, "sell")    == 0 )             sell();
    else if( strcmp(command, "report")  == 0 )             report();
    else { printf("choices: sell, report\n"); return 1; }
    printf("<hwut-end>\n");
    return 0;
}
