// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls,
// built as 'fixture.exe' by 'on_entry' ('make -s fixture.exe').
//
//     fixture.exe open            a fresh 'TMP/shop.db', stocked as below, and
//                                 an empty 'TMP/frame.log' ('on_entry', and
//                                 'hwut.execute fixture open')
//     fixture.exe close           both removed ('on_exit')
//     fixture.exe check <when> <app> [<choice>]
//                                 'when' is 'before' or 'after': whether the
//                                 stock adds up around the test run '<app>
//                                 <choice>', appended to 'TMP/frame.log'
//                                 ('on_before_test', 'on_after_test')
//
// 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE'. The
// stock ADDS UP where every item's quantity is its opening quantity plus
// every movement of the journal.
// _____________________________________________________________________________
#include <cstdio>
#include <string>
#include <utility>
#include <vector>
#include <sqlite3.h>
#include <sys/stat.h>
#include <unistd.h>
#include <limits.h>

static std::string here()
/* RETURN: std::string, the directory this executable stands in. */
{
    char path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    std::string self = n > 0 ? std::string(path, (size_t)n) : std::string(".");
    size_t slash = self.rfind('/');
    return slash == std::string::npos ? "." : self.substr(0, slash);
}

static const std::string DB_PATH  = here() + "/TMP/shop.db";
static const std::string LOG_PATH = here() + "/TMP/frame.log";
static const std::vector<std::pair<const char*, int>> OPENING = { { "apple", 10 }, { "pear", 5 }, { "plum", 5 } };
static const std::vector<std::string> SHOP_TEST = { "delivery.json", "shop.cpp" };

static int open_shop()
/* RETURN: 0, a fresh, stocked database and an empty log written;
 *         1, where the database cannot be written.                       */
{
    mkdir((here() + "/TMP").c_str(), 0777);
    std::remove(DB_PATH.c_str());
    std::remove(LOG_PATH.c_str());
    sqlite3* db = nullptr;
    if( sqlite3_open(DB_PATH.c_str(), &db) != SQLITE_OK ) return 1;
    std::string sql = "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER);"
                      "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER);"
                      "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT);";
    for(const auto& [item, qty] : OPENING) {
        const std::string values = "('" + std::string(item) + "', " + std::to_string(qty) + ");";
        sql += "INSERT INTO opening VALUES " + values + "INSERT INTO stock VALUES " + values;
    }
    int rc = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr);
    sqlite3_close(db);
    if( FILE* fh = std::fopen(LOG_PATH.c_str(), "w") ) std::fclose(fh);
    return rc == SQLITE_OK ? 0 : 1;
}

static int close_shop()
/* RETURN: 0, the database and the log removed (where they stood). */
{
    std::remove(DB_PATH.c_str());
    std::remove(LOG_PATH.c_str());
    return 0;
}

static bool adds_up()
/* RETURN: true, if every item's stock is its opening quantity plus its
 *         journal's movements;
 *         false, else.                                                   */
{
    sqlite3* db = nullptr;
    if( sqlite3_open_v2(DB_PATH.c_str(), &db, SQLITE_OPEN_READONLY, nullptr) != SQLITE_OK ) return false;
    sqlite3_busy_timeout(db, 10000);
    sqlite3_stmt* statement = nullptr;
    bool ok = sqlite3_prepare_v2(db,
        "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty"
        "  FROM opening o JOIN stock s ON s.item = o.item"
        "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item", -1, &statement, nullptr) == SQLITE_OK;
    int rc;
    while( ok && (rc = sqlite3_step(statement)) == SQLITE_ROW )
        ok = sqlite3_column_int(statement, 1) == sqlite3_column_int(statement, 2);
    if( ok && rc != SQLITE_DONE ) ok = false;
    sqlite3_finalize(statement);
    sqlite3_close(db);
    return ok;
}

static int check(const std::string& when, const std::string& test, const std::string& choice)
/* RETURN: 0, one line appended to the log for a shop test run (none for any
 *         other test).                                                   */
{
    bool shop_f = false;
    for(const std::string& name : SHOP_TEST) shop_f |= name == test;
    if( ! shop_f ) return 0;
    std::string run = choice.empty() ? test : test + " " + choice;
    FILE* fh = std::fopen(LOG_PATH.c_str(), "a");
    if( ! fh ) return 1;
    std::fprintf(fh, "%-6s %-15s %s\n", when.c_str(), run.c_str(), adds_up() ? "stock adds up" : "STOCK BROKEN");
    std::fclose(fh);
    return 0;
}

int main(int argc, char** argv)
/* RETURN: 0, the command 'argv[1]' done;
 *         2, where no known command is named (the usage on stderr).      */
{
    const std::string command = argc > 1 ? argv[1] : "";
    if( command == "open" )  return open_shop();
    if( command == "close" ) return close_shop();
    if( command == "check" && argc >= 4 ) return check(argv[2], argv[3], argc > 4 ? argv[4] : "");
    std::fprintf(stderr, "usage: fixture.exe open | close | check before|after <app> <choice>\n");
    return 2;
}
