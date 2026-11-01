/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
 *
 *     fixture.exe open            a fresh 'TMP/shop.db', stocked as below, and
 *                                 an empty 'TMP/frame.log' ('on_entry', and
 *                                 'hwut.execute fixture open')
 *     fixture.exe close           both removed ('on_exit')
 *     fixture.exe check <when> <app> [<choice>]
 *                                 'when' is 'before' or 'after': whether the
 *                                 stock adds up around the test run '<app>
 *                                 <choice>', appended to 'TMP/frame.log'
 *                                 ('on_before_test', 'on_after_test')
 *
 * 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
 * which hwut sets for the run the check stands around; a test without
 * choices has none. 'check' concerns the shop's tests alone. The stock ADDS
 * UP where every item's quantity is its opening quantity plus every movement
 * of the journal.
 *
 * Built by 'on_entry' ('make fixture.exe'), before it opens the shop.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <sqlite3.h>

static char TMP[PATH_MAX + 8], DB_PATH[PATH_MAX + 32], LOG_PATH[PATH_MAX + 32];

static const struct { const char* item; int qty; } OPENING_DB[3] = {
    { "apple", 10 }, { "pear", 5 }, { "plum", 5 }
};
static const char* const SHOP_TEST_SET[] = { "delivery.json", "shop.c", NULL };

static void
paths_init(void)
/* RETURN: nothing; TMP is 'TMP/' beside this executable (the test
 *         directory's), DB_PATH and LOG_PATH the shop's files in it.       */
{
    char    path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if( n < 0 ) n = (ssize_t)strlen(strcpy(path, "./x"));
    path[n] = '\0';
    snprintf(TMP,      sizeof(TMP),      "%s/TMP",       dirname(path));
    snprintf(DB_PATH,  sizeof(DB_PATH),  "%s/shop.db",   TMP);
    snprintf(LOG_PATH, sizeof(LOG_PATH), "%s/frame.log", TMP);
}

static int
open_shop(void)
/* RETURN: int, 0 -- a fresh, stocked database and an empty log written;
 *         1, else (SQLite's word on stderr).                               */
{
    sqlite3* db;
    char     sql[256];
    int      i;
    FILE*    fh;
    mkdir(TMP, 0777);
    remove(DB_PATH); remove(LOG_PATH);
    if( sqlite3_open(DB_PATH, &db) != SQLITE_OK ) { fprintf(stderr, "fixture.exe: %s\n", sqlite3_errmsg(db)); return 1; }
    sqlite3_exec(db, "BEGIN;"
                     "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER);"
                     "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER);"
                     "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT);", NULL, NULL, NULL);
    for(i = 0; i < 3; ++i) {
        snprintf(sql, sizeof(sql), "INSERT INTO opening VALUES ('%s', %d);"
                                   "INSERT INTO stock   VALUES ('%s', %d);",
                 OPENING_DB[i].item, OPENING_DB[i].qty, OPENING_DB[i].item, OPENING_DB[i].qty);
        sqlite3_exec(db, sql, NULL, NULL, NULL);
    }
    if( sqlite3_exec(db, "COMMIT", NULL, NULL, NULL) != SQLITE_OK ) {
        fprintf(stderr, "fixture.exe: %s\n", sqlite3_errmsg(db)); sqlite3_close(db); return 1;
    }
    sqlite3_close(db);
    if( (fh = fopen(LOG_PATH, "w")) ) fclose(fh);
    return 0;
}

static int
close_shop(void)
/* RETURN: int, 0 -- the database and the log removed (where they stood). */
{
    remove(DB_PATH); remove(LOG_PATH);
    return 0;
}

static int
adds_up(void)
/* RETURN: 1, if every item's stock is its opening quantity plus its
 *            journal's movements;
 *         0, else.                                                          */
{
    sqlite3*      db;
    sqlite3_stmt* statement;
    int           ok_f = 1;
    if( sqlite3_open_v2(DB_PATH, &db, SQLITE_OPEN_READONLY, NULL) != SQLITE_OK ) { sqlite3_close(db); return 0; }
    sqlite3_busy_timeout(db, 10000);
    if( sqlite3_prepare_v2(db,
            "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty"
            "  FROM opening o JOIN stock s ON s.item = o.item"
            "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item", -1, &statement, NULL) != SQLITE_OK ) {
        sqlite3_close(db); return 0;
    }
    while( sqlite3_step(statement) == SQLITE_ROW )
        ok_f &= sqlite3_column_int(statement, 1) == sqlite3_column_int(statement, 2);
    sqlite3_finalize(statement);
    sqlite3_close(db);
    return ok_f;
}

static int
check(const char* when, const char* test, const char* choice)
/* RETURN: int, 0 -- one line appended to the log for a shop test run;
 *         nothing done for any other test.                                 */
{
    char  run[256];
    int   i;
    FILE* fh;
    for(i = 0; SHOP_TEST_SET[i] && strcmp(SHOP_TEST_SET[i], test) != 0; ++i);
    if( ! SHOP_TEST_SET[i] ) return 0;
    snprintf(run, sizeof(run), "%s%s%s", test, choice && *choice ? " " : "", choice && *choice ? choice : "");
    if( ! (fh = fopen(LOG_PATH, "a")) ) return 0;
    fprintf(fh, "%-6s %-15s %s\n", when, run, adds_up() ? "stock adds up" : "STOCK BROKEN");
    fclose(fh);
    return 0;
}

int
main(int argc, char** argv)
/* RETURN: int, 0 -- the command done; 1, the shop could not be opened;
 *         2, the command line cannot be read (the usage on stderr).        */
{
    const char* command = argc > 1 ? argv[1] : "";
    paths_init();
    if( strcmp(command, "open")  == 0 ) return open_shop();
    if( strcmp(command, "close") == 0 ) return close_shop();
    if( strcmp(command, "check") == 0 && argc >= 4 ) return check(argv[2], argv[3], argc > 4 ? argv[4] : "");
    fprintf(stderr, "usage: fixture.exe open | close | check before|after <app> <choice>\n");
    return 2;
}
