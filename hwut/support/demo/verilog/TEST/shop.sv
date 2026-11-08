// @hwut {
//     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
//     build     { framework = "make", target = "%.exe"
//                 caps { memory_mb = 2048  file_size_mb = 256  disk_mb = 1024 } }
//     tolerance { stderr_ignored = true }
//     choices {
//         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
//         report { features = ["output-file", "keyed-table-separator", "dependency",
//                              "frame-scripts", "test-scripts", "stderr-ignored"]
//                  output   = ["<stdout>", "stock.csv"] }
//     }
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
//          comes in, three clerks sell at once, and the stock is reported.
// REQUIREMENT  Every movement of the stock is journalled, so that the stock
//              always ADDS UP: opening quantity plus the journal's movements.
//
// THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
// this file, read it first. hwut, when it enters this directory:
//
//     on_entry        builds the helpers ('make'), then 'fixture.exe open':
//                     a fresh 'TMP/shop.db', stocked
//     on_before_test  'fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
//     on_after_test   'fixture.exe check after ...': around every test run,
//                     whether the stock adds up, into 'TMP/frame.log' --
//                     hwut sets the two variables for the run
//     on_exit         'fixture.exe close'
//     apps            'delivery.json' is a test, though it carries no
//                     header: JSON has no comment to carry one. 'admit'
//                     takes it out of the files hwut ignores by default
//                     ('*.json'); 'execute' says how it is run --
//                     'shop.exe deliver delivery.json'.
//     collision       'delivery.json' and 'shop.sv sell' both write the
//                     database. SQLite lets one writer at a time hold the
//                     file; one that waits too long fails with 'database
//                     is locked'. hwut never runs the two at once.
//     dependency      'shop.sv report' runs after both, whatever their
//                     verdict: it reports what they left.
//
// STDERR  Every SQL statement is logged on stderr, as a server would. A
// word on stderr fails a run ('unexpected stderr') unless the header says
// 'stderr_ignored = true': the words there are on purpose, and no error.
//
// SQLITE is the C library itself, reached through DPI-C ('shop_db.sv');
// the delivery note, JSON, is read by 'hwut_hocon' -- HOCON is JSON's
// superset, the note's outer object bound to a key.
//
// CHOICES
//
// sell     three clerks sell at once, each a PROCESS of the simulation with
//          a connection of its own, a delay drawn between two sales. The
//          sales are printed as '##! table unordered sep={;}': rows of
//          'item;qty', in any order -- and no column is a key, 'apple;1'
//          stands four times.
//
// report   the stock, as '##! table key=0 sep={;}', and the same rows
//          written to 'stock.csv': 'output' names the file, hwut reads it
//          after the run and compares it with its own GOOD. Then the frame
//          log of the shop's tests: what 'on_before_test' and
//          'on_after_test' found around the delivery and the sale ('##!
//          potpourri': which ran first is free), and before this report.
//
// deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
//          delivery note: every line on the stock and into the journal, in
//          one transaction.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_hocon::*;
import deterministic_random::*;
import shop_db::*;

module shop;
    timeunit 1ms;
    timeprecision 1us;

    DeterministicStream stream;

    function automatic chandle connect();
        // RETURN: a connection to the shop's database, every statement it
        //         executes logged on stderr. Exits 1 where the database does
        //         not stand: 'on_entry' writes it.
        chandle db;
        if (!exists(DB_PATH)) begin
            $fdisplay(32'h8000_0002, "shop.exe: no %s -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'",
                      DB_PATH);
            exit_(1);
        end
        log_f = 1;
        db    = opened(DB_PATH);
        if (db == null) begin
            $fdisplay(32'h8000_0002, "shop.exe: %s cannot be opened", DB_PATH);
            exit_(1);
        end
        return db;
    endfunction

    function automatic string move(chandle db, string item, int delta, string source);
        // RETURN: '', the stock of 'item' changed by 'delta' and journalled,
        //         in one transaction; the database's error text, else.
        string error = execute(db, "BEGIN IMMEDIATE");
        if (error.len()) return error;
        error = execute(db, $sformatf("UPDATE stock SET qty = qty + %0d WHERE item = '%s'", delta, item));
        if (error.len() == 0)
            error = execute(db, $sformatf("INSERT INTO journal VALUES ('%s', %0d, '%s')", item, delta, source));
        if (error.len()) begin void'(execute(db, "ROLLBACK")); return error; end
        return execute(db, "COMMIT");
    endfunction

    function automatic void deliver(string path);
        // RETURN: nothing; the delivery note in 'path' was booked and printed.
        string     text_list[$] = {};
        SourceLine line_list[$] = {};
        Fault      fault_list[$] = {};
        ObjectNode document, note;
        ListNode   lines;
        ScalarNode name, supplier;
        string     item[$] = {};
        int        qty[$] = {};
        chandle    db;
        read_lines(path, text_list);
        foreach (text_list[i])
            line_list.push_back(SourceLine::make(i == 0 ? {"delivery = ", text_list[i]} : text_list[i], i + 1, 0));
        document = parse(line_list, path, fault_list);
        foreach (fault_list[i]) $fdisplay(32'h8000_0002, "%s", fault_list[i].to_string());
        if (document == null || fault_list.size() || !$cast(note, document.get("delivery"))) begin
            $fdisplay(32'h8000_0002, "shop.exe: '%s' is no delivery note", path);
            exit_(1);
        end
        void'($cast(name, note.get("note")));
        void'($cast(supplier, note.get("supplier")));
        void'($cast(lines, note.get("lines")));
        foreach (lines.item_list[i]) begin
            ObjectNode line;
            ScalarNode field;
            void'($cast(line, lines.item_list[i]));
            void'($cast(field, line.get("item")));   item.push_back(field.s);
            void'($cast(field, line.get("qty")));    qty.push_back(int'(field.i));
        end
        db = connect();
        void'(execute(db, "BEGIN IMMEDIATE"));
        foreach (item[i]) begin
            void'(execute(db, $sformatf("UPDATE stock SET qty = qty + %0d WHERE item = '%s'", qty[i], item[i])));
            void'(execute(db, $sformatf("INSERT INTO journal VALUES ('%s', %0d, '%s')", item[i], qty[i], name.s)));
        end
        void'(execute(db, "COMMIT"));
        void'(sqlite3_close(db));
        $display("delivery note %s from %s:", name.s, supplier.s);
        foreach (item[i]) $display("    %-6s +%0d", item[i], qty[i]);
    endfunction

    task automatic clerk(string name, string item_list[$], ref string sale_list[$], ref string error_list[$]);
        // RETURN: nothing; the clerk 'name' sold 'item_list', one item per
        //         sale, each noted in 'sale_list' -- what failed in
        //         'error_list'.
        chandle db = connect();
        foreach (item_list[i]) begin
            string error;
            #(5.0 * stream.next_float());
            error = move(db, item_list[i], -1, name);
            if (error.len()) begin error_list.push_back({name, ": ", error}); break; end
            sale_list.push_back({item_list[i], ";1"});
        end
        void'(sqlite3_close(db));
    endtask

    task automatic sell();
        // RETURN: nothing; three clerks sold at once; every sale was printed.
        string sale_list[$] = {}, error_list[$] = {};
        string anna[$] = {}, ben[$] = {}, chloe[$] = {};
        string text = "";
        //  What each clerk sells, one item per sale.
        anna.push_back("apple"); anna.push_back("apple"); anna.push_back("pear");
        ben.push_back("apple");  ben.push_back("plum");
        chloe.push_back("apple");
        void'(sqlite3_close(connect()));
        fork
            clerk("anna",  anna,  sale_list, error_list);
            clerk("ben",   ben,   sale_list, error_list);
            clerk("chloe", chloe, sale_list, error_list);
        join
        if (error_list.size()) begin
            foreach (error_list[i]) text = {text, i ? string'("; ") : string'(""), error_list[i]};
            $fdisplay(32'h8000_0002, "shop.exe: a sale failed -- %s", text);
            exit_(1);
        end
        $display("sales, item;qty -- in the order the clerks booked them:");
        $display("##! table unordered sep={;}");
        foreach (sale_list[i]) $display("%s", sale_list[i]);
        $display("####");
    endtask

    function automatic void report();
        // RETURN: nothing; the stock and the frame log were printed;
        //         'stock.csv' was written.
        chandle db = connect();
        string  cell_list[$] = {};
        string  line_list[$] = {};
        int     fd;
        void'(query(db, "SELECT item, qty FROM stock ORDER BY item", cell_list));
        fd = $fopen("stock.csv", "w");
        $fdisplay(fd, "item;qty");
        for (int i = 0; i + 1 < cell_list.size(); i += 2) $fdisplay(fd, "%s;%s", cell_list[i], cell_list[i + 1]);
        $fclose(fd);
        void'(query(db, "SELECT item, qty FROM stock ORDER BY qty, item", cell_list));
        void'(sqlite3_close(db));
        $display("stock, item;qty (also written to stock.csv):");
        $display("##! table key=0 sep={;}");
        for (int i = 0; i + 1 < cell_list.size(); i += 2) $display("%s;%s", cell_list[i], cell_list[i + 1]);
        $display("####");
        read_lines(LOG_PATH, line_list);
        $display("the frame, around the delivery and the sale:");
        $display("##! potpourri");
        foreach (line_list[i]) if (!contains(line_list[i], "shop.sv report")) $display("%s", line_list[i]);
        $display("####");
        foreach (line_list[i]) if (contains(line_list[i], "shop.sv report")) $display("%s", line_list[i]);
    endfunction

    function automatic bit contains(string text, string part);
        // RETURN: 1, 'part' stands in 'text'; 0, else.
        for (int i = 0; i + part.len() <= text.len(); i++)
            if (text.substr(i, i + part.len() - 1) == part) return 1;
        return 0;
    endfunction

    initial begin
        string  command = hwut_sv_argc() > 1 ? hwut_sv_argv(1) : "";
        longint seed = 0;
        int     fd;
        fd = $fopen("/dev/urandom", "rb");
        if (fd != 0) begin void'($fread(seed, fd)); $fclose(fd); end
        seed   = (seed ^ (seed >> 31)) & 'h7FFFFFFF;
        stream = new(seed == 0 ? 1 : seed);
        if      (command == "deliver" && hwut_sv_argc() > 2) deliver(hwut_sv_argv(2));
        else if (command == "sell")                         sell();
        else if (command == "report")                       report();
        else begin
            $display("choices: sell, report");
            exit_(1);
        end
        $display("<hwut-end>");
        exit_(0);
    end
endmodule
