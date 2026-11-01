// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
//
//     fixture.exe open           a fresh 'TMP/shop.db', stocked as below, and
//                                an empty 'TMP/frame.log' ('on_entry', and
//                                'hwut.execute fixture open')
//     fixture.exe close          both removed ('on_exit')
//     fixture.exe check <when> <app> [<choice>]
//                                'when' is 'before' or 'after': whether the
//                                stock adds up around the test run '<app>
//                                <choice>', appended to 'TMP/frame.log'
//                                ('on_before_test', 'on_after_test')
//
// 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
// which hwut sets for the run the check stands around; a test without
// choices has none. 'check' concerns the shop's tests alone. The stock ADDS
// UP where every item's quantity is its opening quantity plus every movement
// of the journal.
// _____________________________________________________________________________
import hwut_runner::*;
import shop_db::*;

function automatic void open_shop();
    // RETURN: nothing; a fresh, stocked database and an empty log stand.
    chandle db;
    int     fd;
    void'(mkdir("TMP", 'o755));
    void'(remove(DB_PATH));
    void'(remove(LOG_PATH));
    db = opened(DB_PATH);
    void'(execute(db, "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)"));
    void'(execute(db, "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)"));
    void'(execute(db, "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)"));
    void'(execute(db, "INSERT INTO opening VALUES ('apple', 10), ('pear', 5), ('plum', 5)"));
    void'(execute(db, "INSERT INTO stock   VALUES ('apple', 10), ('pear', 5), ('plum', 5)"));
    void'(sqlite3_close(db));
    fd = $fopen(LOG_PATH, "w");
    if (fd != 0) $fclose(fd);
endfunction

function automatic void close_shop();
    // RETURN: nothing; the database and the log are gone.
    void'(remove(DB_PATH));
    void'(remove(LOG_PATH));
endfunction

function automatic bit adds_up();
    // RETURN: 1, if every item's stock is its opening quantity plus its
    //         journal's movements; 0, else.
    string  cell_list[$] = {};
    chandle db = opened(DB_PATH);
    void'(query(db, {"SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty",
                     "  FROM opening o JOIN stock s ON s.item = o.item",
                     "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item"}, cell_list));
    void'(sqlite3_close(db));
    for (int i = 0; i + 2 < cell_list.size(); i += 3)
        if (cell_list[i + 1] != cell_list[i + 2]) return 0;
    return 1;
endfunction

function automatic void check(string when, string test, string choice);
    // RETURN: nothing; one line was appended to the log, for a shop test run.
    string run = choice.len() ? {test, " ", choice} : test;
    int    fd;
    if (test != "delivery.json" && test != "shop.sv") return;
    fd = $fopen(LOG_PATH, "a");
    if (fd == 0) return;
    $fdisplay(fd, "%-6s %-15s %s", when, run, adds_up() ? "stock adds up" : "STOCK BROKEN");
    $fclose(fd);
endfunction

module fixture;
    initial begin
        string command = hwut_sv_argc() > 1 ? hwut_sv_argv(1) : "";
        if      (command == "open")                         open_shop();
        else if (command == "close")                        close_shop();
        else if (command == "check" && hwut_sv_argc() >= 4) check(hwut_sv_argv(2), hwut_sv_argv(3),
                                                                  hwut_sv_argc() > 4 ? hwut_sv_argv(4) : "");
        else begin
            $fdisplay(32'h8000_0002, "usage: fixture.exe open | close | check before|after <app> <choice>");
            exit_(2);
        end
        exit_(0);
    end
endmodule
