/* @hwut {
 *     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
 *     build     { framework = "make", target = "%.exe" }
 *     tolerance { stderr_ignored = true }
 *     choices {
 *         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
 *         report { features = ["output-file", "keyed-table-separator", "dependency",
 *                              "frame-scripts", "test-scripts", "stderr-ignored"]
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
 *     on_entry        'make -s fixture.exe && ./fixture.exe open': a fresh
 *                     'TMP/shop.db', stocked
 *     on_before_test  './fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
 *     on_after_test   './fixture.exe check after ...': around every test run,
 *                     whether the stock adds up, into 'TMP/frame.log'
 *     on_exit         './fixture.exe close'
 *     apps            'delivery.json' is a test, though it carries no header.
 *                     'admit' takes it out of the files hwut ignores by
 *                     default ('*.json'); 'build' makes 'delivery.exe' -- this
 *                     source, a target of its own -- and 'execute' says how it
 *                     is run: 'delivery.exe deliver delivery.json'.
 *     collision       'delivery.json' and 'shop.cpp sell' both write the
 *                     database; hwut never runs the two at once.
 *     dependency      'shop.cpp report' runs after both, whatever their
 *                     verdict: it reports what they left.
 *
 * STDERR  Every SQL statement is logged on stderr, as a server would;
 * 'stderr_ignored = true': the words there are on purpose, and no error.
 *
 * CHOICES
 *
 * sell     three clerks sell at once, each in a thread of its own, each on a
 *          connection of its own. The sales are printed as '##! table
 *          unordered sep={;}': rows of 'item;qty', in any order.
 *
 * report   the stock, as '##! table key=0 sep={;}', and the same rows written
 *          to 'stock.csv': 'output' names the file, hwut compares it with its
 *          own GOOD. Then the frame log of the shop's tests ('##! potpourri':
 *          which ran first is free), and before this report. The log names
 *          this test 'shop.cpp' where Python's names 'shop.py': this
 *          choice's stdout GOOD is its own (RATIONALE DEMO-CPP-4).
 *
 * deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
 *          delivery note: every line on the stock and into the journal, in
 *          one transaction.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <fstream>
#include <map>
#include <mutex>
#include <regex>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>
#include <sqlite3.h>
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

//  What each clerk sells, one item per sale.
static const std::vector<std::pair<std::string, std::vector<std::string>>> CLERK = {
    { "anna",  { "apple", "apple", "pear" } },
    { "ben",   { "apple", "plum" } },
    { "chloe", { "apple" } },
};

static int trace(unsigned kind, void*, void* statement, void*)
/* RETURN: 0. The statement about to run, logged on stderr. */
{
    if( kind == SQLITE_TRACE_STMT ) {
        char* sql = sqlite3_expanded_sql((sqlite3_stmt*)statement);
        std::fprintf(stderr, "sql: %s\n", sql ? sql : "");
        sqlite3_free(sql);
    }
    return 0;
}

static sqlite3* connect()
/* RETURN: sqlite3*, a connection to the shop's database, every statement it
 *         executes logged on stderr. Exits 1 where the database does not
 *         stand: 'on_entry' writes it.                                   */
{
    if( access(DB_PATH.c_str(), F_OK) != 0 ) {
        std::fprintf(stderr, "shop.exe: no %s -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'\n",
                     DB_PATH.c_str());
        std::exit(1);
    }
    sqlite3* db = nullptr;
    if( sqlite3_open(DB_PATH.c_str(), &db) != SQLITE_OK ) {
        std::fprintf(stderr, "shop.exe: %s\n", sqlite3_errmsg(db));
        std::exit(1);
    }
    sqlite3_busy_timeout(db, 10000);
    sqlite3_trace_v2(db, SQLITE_TRACE_STMT, trace, nullptr);
    return db;
}

static void execute(sqlite3* db, const std::string& sql, const std::vector<std::string>& parameter = {})
/* RETURN: nothing. 'sql' executed with 'parameter' bound ('?'), to the end;
 *         throws std::runtime_error with SQLite's text where it fails.   */
{
    sqlite3_stmt* statement = nullptr;
    if( sqlite3_prepare_v2(db, sql.c_str(), -1, &statement, nullptr) != SQLITE_OK )
        throw std::runtime_error(sqlite3_errmsg(db));
    for(size_t i = 0; i < parameter.size(); ++i)
        sqlite3_bind_text(statement, (int)i + 1, parameter[i].c_str(), -1, SQLITE_TRANSIENT);
    int rc;
    while( (rc = sqlite3_step(statement)) == SQLITE_ROW ) ;
    sqlite3_finalize(statement);
    if( rc != SQLITE_DONE ) throw std::runtime_error(sqlite3_errmsg(db));
}

static void move(sqlite3* db, const std::string& item, int delta, const std::string& source)
/* RETURN: nothing. Changes the stock of 'item' by 'delta' and journals it,
 *         in one transaction.                                            */
{
    execute(db, "BEGIN IMMEDIATE");
    execute(db, "UPDATE stock SET qty = qty + ? WHERE item = ?", { std::to_string(delta), item });
    execute(db, "INSERT INTO journal VALUES (?, ?, ?)", { item, std::to_string(delta), source });
    execute(db, "COMMIT");
}

struct Note {
    std::string                              note, supplier;
    std::vector<std::pair<std::string, int>> line_list;
};

static Note read_note(const std::string& path)
/* RETURN: Note, the delivery note in 'path' -- the JSON of 'delivery.json':
 *         "note", "supplier", and "lines" of { "item", "qty" }.          */
{
    std::ifstream in(path);
    std::stringstream buffer;
    buffer << in.rdbuf();
    const std::string text = buffer.str();
    Note result;
    std::smatch m;
    if( std::regex_search(text, m, std::regex("\"note\"\\s*:\\s*\"([^\"]*)\"")) )     result.note     = m[1];
    if( std::regex_search(text, m, std::regex("\"supplier\"\\s*:\\s*\"([^\"]*)\"")) ) result.supplier = m[1];
    const std::regex line("\\{\\s*\"item\"\\s*:\\s*\"([^\"]*)\"\\s*,\\s*\"qty\"\\s*:\\s*(-?[0-9]+)\\s*\\}");
    for(auto it = std::sregex_iterator(text.begin(), text.end(), line); it != std::sregex_iterator(); ++it)
        result.line_list.push_back({ (*it)[1], std::stoi((*it)[2]) });
    return result;
}

static void deliver(const std::string& path)
/* RETURN: nothing. Books the delivery note in 'path' and prints it. */
{
    const Note note = read_note(path);
    sqlite3* db = connect();
    execute(db, "BEGIN IMMEDIATE");
    for(const auto& [item, qty] : note.line_list) {
        execute(db, "UPDATE stock SET qty = qty + ? WHERE item = ?", { std::to_string(qty), item });
        execute(db, "INSERT INTO journal VALUES (?, ?, ?)", { item, std::to_string(qty), note.note });
    }
    execute(db, "COMMIT");
    sqlite3_close(db);
    std::printf("delivery note %s from %s:\n", note.note.c_str(), note.supplier.c_str());
    for(const auto& [item, qty] : note.line_list) std::printf("    %-6s +%d\n", item.c_str(), qty);
}

static void sell()
/* RETURN: nothing. Three clerks sell at once; prints every sale. */
{
    std::vector<std::string> sale_list, error_list;
    std::mutex lock;
    sqlite3_close(connect());
    std::vector<std::thread> pool;
    for(const auto& [name, item_list] : CLERK) {
        pool.emplace_back([&, name = name, item_list = item_list] {
            sqlite3* db = connect();
            try {
                for(const std::string& item : item_list) {
                    move(db, item, -1, name);
                    std::lock_guard<std::mutex> guard(lock);
                    sale_list.push_back(item + ";1");
                }
            } catch( const std::exception& error ) {
                std::lock_guard<std::mutex> guard(lock);
                error_list.push_back(name + ": " + error.what());
            }
            sqlite3_close(db);
        });
    }
    for(auto& thread : pool) thread.join();
    if( ! error_list.empty() ) {
        std::string text;
        for(const std::string& e : error_list) text += (text.empty() ? "" : "; ") + e;
        std::fprintf(stderr, "shop.exe: a sale failed -- %s\n", text.c_str());
        std::exit(1);
    }
    std::printf("sales, item;qty -- in the order the clerks booked them:\n");
    std::printf("##! table unordered sep={;}\n");
    for(const std::string& row : sale_list) std::printf("%s\n", row.c_str());
    std::printf("####\n");
}

static void report()
/* RETURN: nothing. Prints the stock and the frame log; writes 'stock.csv'. */
{
    sqlite3* db = connect();
    sqlite3_stmt* statement = nullptr;
    std::vector<std::pair<std::string, int>> row_list;
    sqlite3_prepare_v2(db, "SELECT item, qty FROM stock ORDER BY qty, item", -1, &statement, nullptr);
    while( sqlite3_step(statement) == SQLITE_ROW )
        row_list.push_back({ (const char*)sqlite3_column_text(statement, 0), sqlite3_column_int(statement, 1) });
    sqlite3_finalize(statement);
    sqlite3_close(db);
    std::map<std::string, int> sorted(row_list.begin(), row_list.end());
    if( FILE* fh = std::fopen((here() + "/stock.csv").c_str(), "w") ) {
        std::fprintf(fh, "item;qty\n");
        for(const auto& [item, qty] : sorted) std::fprintf(fh, "%s;%d\n", item.c_str(), qty);
        std::fclose(fh);
    }
    std::printf("stock, item;qty (also written to stock.csv):\n");
    std::printf("##! table key=0 sep={;}\n");
    for(const auto& [item, qty] : row_list) std::printf("%s;%d\n", item.c_str(), qty);
    std::printf("####\n");
    std::vector<std::string> line_list;
    std::ifstream in(LOG_PATH);
    for(std::string line; std::getline(in, line); ) {
        line.erase(line.find_last_not_of(" \t\r") + 1);
        line_list.push_back(line);
    }
    std::printf("the frame, around the delivery and the sale:\n");
    std::printf("##! potpourri\n");
    for(const std::string& line : line_list)
        if( line.find("shop.cpp report") == std::string::npos ) std::printf("%s\n", line.c_str());
    std::printf("####\n");
    for(const std::string& line : line_list)
        if( line.find("shop.cpp report") != std::string::npos ) std::printf("%s\n", line.c_str());
}

int main(int argc, char** argv)
/* RETURN: 0, the command 'argv[1]' done, '<hwut-end>' after its output;
 *         1, where no known command is named (the choices are printed)
 *            or the database fails.                                      */
{
    const std::string command = argc > 1 ? argv[1] : "";
    try {
        if     ( command == "deliver" && argc > 2 ) deliver(argv[2]);
        else if( command == "sell" )                sell();
        else if( command == "report" )              report();
        else { std::printf("choices: sell, report\n"); return 1; }
    } catch( const std::exception& error ) {
        std::fprintf(stderr, "shop.exe: %s\n", error.what());
        return 1;
    }
    std::printf("<hwut-end>\n");
    return 0;
}
