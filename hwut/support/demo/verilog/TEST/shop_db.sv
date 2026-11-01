// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE SHOP'S DATABASE -- no test, the package 'shop.sv' and 'fixture.sv'
// share: SQLite, reached through DPI-C into the library itself
// ('-lsqlite3'; no C of this directory). A handle is a 'chandle'; a query's
// rows come back as texts, row after row.
//
//     import shop_db::*;
//     chandle db = connected(1);              -- every statement on stderr
//     void'(execute(db, "UPDATE ..."));
//     query(db, "SELECT item, qty FROM stock", cell_list);   -- 2 per row
// _____________________________________________________________________________
package shop_db;

    localparam string DB_PATH  = "TMP/shop.db";
    localparam string LOG_PATH = "TMP/frame.log";
    localparam int    SQLITE_ROW = 100;

    import "DPI-C" function int    sqlite3_open(string filename, output chandle db);
    import "DPI-C" function int    sqlite3_close(chandle db);
    import "DPI-C" function int    sqlite3_busy_timeout(chandle db, int ms);
    import "DPI-C" function int    sqlite3_exec(chandle db, string sql, chandle callback, chandle argument,
                                                chandle error_message);
    import "DPI-C" function string sqlite3_errmsg(chandle db);
    import "DPI-C" function int    sqlite3_prepare_v2(chandle db, string sql, int byte_n, output chandle statement,
                                                      input chandle tail);
    import "DPI-C" function int    sqlite3_step(chandle statement);
    import "DPI-C" function int    sqlite3_column_count(chandle statement);
    import "DPI-C" function string sqlite3_column_text(chandle statement, int column);
    import "DPI-C" function int    sqlite3_finalize(chandle statement);
    import "DPI-C" function int    mkdir(string path, int unsigned mode);
    import "DPI-C" function int    remove(string path);

    bit log_f = 0;                  // every statement on stderr

    function automatic bit exists(string path);
        // RETURN: 1, the file 'path' stands and can be read; 0, else.
        int fd;
        fd = $fopen(path, "r");
        if (fd == 0) return 0;
        $fclose(fd);
        return 1;
    endfunction

    function automatic chandle opened(string path);
        // RETURN: a connection to the database 'path' -- made where it does
        //         not stand -- waiting up to 10 s for a lock; null where it
        //         cannot be opened.
        chandle db;
        if (sqlite3_open(path, db) != 0) return null;
        void'(sqlite3_busy_timeout(db, 10000));
        return db;
    endfunction

    function automatic string execute(chandle db, string sql);
        // RETURN: '', 'sql' was executed; the database's error text, else.
        if (log_f) $fdisplay(32'h8000_0002, "sql: %s", sql);
        if (sqlite3_exec(db, sql, null, null, null) == 0) return "";
        return sqlite3_errmsg(db);
    endfunction

    function automatic string query(chandle db, string sql, ref string cell_list[$]);
        // RETURN: '', 'cell_list' holds the rows of 'sql', each its columns'
        //         texts in order, row after row; the database's error text,
        //         else.
        chandle statement;
        int     column_n;
        cell_list = {};
        if (log_f) $fdisplay(32'h8000_0002, "sql: %s", sql);
        if (sqlite3_prepare_v2(db, sql, -1, statement, null) != 0) return sqlite3_errmsg(db);
        column_n = sqlite3_column_count(statement);
        forever begin
            if (sqlite3_step(statement) != SQLITE_ROW) break;
            for (int i = 0; i < column_n; i++) cell_list.push_back(sqlite3_column_text(statement, i));
        end
        void'(sqlite3_finalize(statement));
        return "";
    endfunction

    function automatic void read_lines(string path, ref string line_list[$]);
        // RETURN: nothing; 'line_list' holds the lines of the file 'path',
        //         without their newline -- none where it cannot be read.
        int    fd;
        string line;
        line_list = {};
        fd = $fopen(path, "r");
        if (fd == 0) return;
        forever begin
            if ($fgets(line, fd) == 0) break;           // never a 'while' condition
            if (line.len() && line[line.len() - 1] == "\n") line = line.substr(0, line.len() - 2);
            line_list.push_back(line);
        end
        $fclose(fd);
    endfunction

endpackage
