-- @hwut {
--     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
--     build     { framework = "make", target = "%.exe" }
--     tolerance { stderr_ignored = true }
--     choices {
--         sell   { features = ["demo-vhdl+cover-unordered-table", "demo-vhdl+cover-stderr-ignored", "demo-vhdl+cover-collision"] }
--         report { features = ["demo-vhdl+cover-output-file", "demo-vhdl+cover-keyed-table-separator", "demo-vhdl+cover-dependency",
--                              "demo-vhdl+cover-frame-scripts", "demo-vhdl+cover-test-scripts", "demo-vhdl+cover-stderr-ignored"]
--                  output   = ["<stdout>", "stock.csv"] }
--     }
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
--          comes in, three clerks sell at once, and the stock is reported.
-- REQUIREMENT  Every movement of the stock is journalled, so that the stock
--              always ADDS UP: opening quantity plus the journal's movements.
--
-- THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
-- this file, read it first. hwut, when it enters this directory:
--
--     on_entry        builds the helpers, then 'fixture.exe open': a fresh
--                     'TMP/shop.db', stocked
--     on_before_test  'fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
--     on_after_test   'fixture.exe check after ...': around every test run,
--                     whether the stock adds up, into 'TMP/frame.log'
--     on_exit         'fixture.exe close'
--     apps            'delivery.json' is a test, though it carries no
--                     header; 'admit' takes it out of the files hwut ignores
--                     by default ('*.json'); 'execute' says how it is run --
--                     'shop.exe deliver delivery.json'.
--     collision       'delivery.json' and 'shop.vhd sell' both write the
--                     database: hwut never runs the two at once.
--     dependency      'shop.vhd report' runs after both, whatever their
--                     verdict: it reports what they left.
--
-- STDERR  Every SQL statement is logged on stderr, as a server would; the
-- header says 'stderr_ignored = true': the words there are on purpose.
--
-- CHOICES
--
-- sell     three clerks sell at once, each a process with a connection of
--          its own, a drawn time between two sales. The sales are printed as
--          '##! table unordered sep={;}': rows of 'item;qty', in any order.
-- report   the stock, as '##! table key=0 sep={;}', and the same rows
--          written to 'stock.csv': 'output' names the file, hwut compares it
--          with its own GOOD. Then the frame log of the shop's tests
--          ('##! potpourri': which ran first is free), and before this report.
-- deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
--          delivery note: every line on the stock and into the journal, in
--          one transaction.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.demo_vhpi.all;
use work.demo_sql.all;

entity shop is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture test of shop is
    constant DB_PATH  : string := HERE & "/TMP/shop.db";
    constant LOG_PATH : string := HERE & "/TMP/frame.log";

    --  What each clerk sells, one item per sale.
    function clerk_name(c : natural) return string is
        -- RETURN: string, the name of clerk 'c'.
    begin
        case c is when 0 => return "anna"; when 1 => return "ben"; when others => return "chloe"; end case;
    end function;
    function clerk_items(c : natural) return str_list is
        -- RETURN: str_list, what clerk 'c' sells.
    begin
        case c is
            when 0      => return "apple" & LF & "apple" & LF & "pear" & LF;
            when 1      => return "apple" & LF & "plum" & LF;
            when others => return "apple" & LF;
        end case;
    end function;

    type SaleBoard is protected
        procedure sold(text : string);
        procedure failed(text : string);
        procedure finished;
        impure function sales return str_list;
        impure function errors return string;
        impure function finished_n return natural;
    end protected;
    type SaleBoard is protected body
        variable sale_text  : line := new string'("");
        variable error_text : line := new string'("");
        variable n          : natural := 0;
        procedure sold(text : string) is
            -- RETURN: nothing; 'text' is the next sale booked.
        begin sale_text := new string'(sale_text.all & text & LF); end procedure;
        procedure failed(text : string) is
            -- RETURN: nothing; 'text' is the next failure.
        begin
            if error_text.all /= "" then error_text := new string'(error_text.all & "; "); end if;
            error_text := new string'(error_text.all & text);
        end procedure;
        procedure finished is
            -- RETURN: nothing; one more clerk is done.
        begin n := n + 1; end procedure;
        impure function sales return str_list is
            -- RETURN: str_list, the sales in the order booked.
        begin return sale_text.all; end function;
        impure function errors return string is
            -- RETURN: string, the failures, '; '-joined; "" for none.
        begin return error_text.all; end function;
        impure function finished_n return natural is
            -- RETURN: natural, the clerks done.
        begin return n; end function;
    end protected body;

    shared variable rng   : ClockRandom;
    shared variable board : SaleBoard;
    signal sell_go : boolean := false;

    function field(row : string; n : positive) return string is
        -- RETURN: string, the column 'n' (from 1) of the ';'-separated 'row'.
        variable k     : positive := 1;
        variable first : integer  := row'left;
    begin
        for i in row'range loop
            if row(i) = ';' then
                if k = n then return row(first to i - 1); end if;
                k := k + 1; first := i + 1;
            end if;
        end loop;
        if k = n then return row(first to row'right); end if;
        return "";
    end function;

    function contains(text : string; part : string) return boolean is
        -- RETURN: true, 'part' stands somewhere in 'text'; false, else.
    begin
        for i in text'left to text'right - part'length + 1 loop
            if text(i to i + part'length - 1) = part then return true; end if;
        end loop;
        return false;
    end function;

    function rstrip(text : string) return string is
        -- RETURN: string, 'text' without its trailing blanks.
        variable n : integer := text'right;
    begin
        while n >= text'left and text(n) = ' ' loop n := n - 1; end loop;
        return text(text'left to n);
    end function;

    impure function connect return natural is
        -- RETURN: natural, the handle of the shop's database, every
        --         statement it runs logged on stderr. Ends the process (1)
        --         where the database does not stand: 'on_entry' writes it.
    begin
        if not exists(DB_PATH) then
            eprint("shop.exe: no " & DB_PATH & " -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'");
            process_exit(1);
        end if;
        return sql_open(DB_PATH, true);
    end function;

    impure function move(h : natural; item_text : string; delta : integer; source : string) return boolean is
        -- RETURN: true, the stock of 'item_text' changed by 'delta' and the
        --         journal says so, in one transaction; false, else -- the
        --         reason is 'sql_rows'.
    begin
        return sql(h, "BEGIN IMMEDIATE;"
                      & "UPDATE stock SET qty = qty + " & integer'image(delta) & " WHERE item = '" & item_text & "';"
                      & "INSERT INTO journal VALUES ('" & item_text & "', " & integer'image(delta) & ", '" & source & "');"
                      & "COMMIT;");
    end function;

    procedure must(h : natural; statement : string) is
        -- RETURN: nothing, if 'statement' ran; else the process ends (1), the
        --         reason on stderr.
    begin
        if sql(h, statement) then return; end if;
        eprint("shop.exe: " & sql_rows);
        process_exit(1);
    end procedure;

    --  THE DELIVERY NOTE: JSON, read as the words it is made of -- a string,
    --  a number, or one of ':,{}[]'.
    impure function file_text(path : string) return string is
        -- RETURN: string, the file 'path', its lines ended by LF.
        file     f    : text open read_mode is path;
        variable l    : line;
        variable text : line := new string'("");
    begin
        while not endfile(f) loop readline(f, l); text := new string'(text.all & l.all & LF); end loop;
        return text.all;
    end function;

    impure function json_words(text : string) return str_list is
        -- RETURN: str_list, the words of the JSON 'text': a string without its
        --         quotes (no escapes are read), a number, or a sign.
        variable words : line := new string'("");
        variable i, j  : integer := text'left;
    begin
        while i <= text'right loop
            case text(i) is
                when '"' =>
                    j := i + 1;
                    while text(j) /= '"' loop j := j + 1; end loop;
                    words := new string'(words.all & text(i + 1 to j - 1) & LF);
                    i := j + 1;
                when '0' to '9' | '-' =>
                    j := i;
                    while j < text'right and (text(j + 1) = '-' or (text(j + 1) >= '0' and text(j + 1) <= '9')) loop
                        j := j + 1;
                    end loop;
                    words := new string'(words.all & text(i to j) & LF);
                    i := j + 1;
                when ':' | ',' | '{' | '}' | '[' | ']' =>
                    words := new string'(words.all & text(i) & LF);
                    i := i + 1;
                when others =>
                    i := i + 1;
            end case;
        end loop;
        return words.all;
    end function;

    procedure deliver(path : string) is
        -- RETURN: nothing; books the delivery note in 'path' and prints it.
        constant words : str_list := json_words(file_text(path));
        variable note, supplier, item_text : line := new string'("");
        variable lines : line := new string'("");       -- 'item;qty' & LF, in order
        variable statement : line := new string'("BEGIN IMMEDIATE;");
        variable h : natural;
    begin
        for i in 0 to item_n(words) - 3 loop
            if item(words, i + 1) = ":" then
                if    item(words, i) = "note"     then note      := new string'(item(words, i + 2));
                elsif item(words, i) = "supplier" then supplier  := new string'(item(words, i + 2));
                elsif item(words, i) = "item"     then item_text := new string'(item(words, i + 2));
                elsif item(words, i) = "qty"      then
                    lines := new string'(lines.all & item_text.all & ";" & item(words, i + 2) & LF);
                end if;
            end if;
        end loop;
        h := connect;
        for i in 0 to item_n(lines.all) - 1 loop
            statement := new string'(statement.all
                & "UPDATE stock SET qty = qty + " & field(item(lines.all, i), 2) & " WHERE item = '" & field(item(lines.all, i), 1) & "';"
                & "INSERT INTO journal VALUES ('" & field(item(lines.all, i), 1) & "', "
                & field(item(lines.all, i), 2) & ", '" & note.all & "');");
        end loop;
        must(h, statement.all & "COMMIT;");
        sql_close(h);
        print("delivery note " & note.all & " from " & supplier.all & ":");
        for i in 0 to item_n(lines.all) - 1 loop
            print("    " & ljust(field(item(lines.all, i), 1), 6) & " +" & field(item(lines.all, i), 2));
        end loop;
    end procedure;

    procedure report_stock is
        -- RETURN: nothing; prints the stock and the frame log; writes
        --         'stock.csv'.
        constant h    : natural := connect;
        file     csv  : text;
        file     log  : text;
        variable l    : line;
        variable rows : line;
        variable frame : line := new string'("");
    begin
        must(h, "SELECT item, qty FROM stock ORDER BY item");
        rows := new string'(sql_rows);
        file_open(csv, HERE & "/stock.csv", write_mode);
        write(l, string'("item;qty")); writeline(csv, l);
        for i in 0 to item_n(rows.all) - 1 loop write(l, item(rows.all, i)); writeline(csv, l); end loop;
        file_close(csv);
        must(h, "SELECT item, qty FROM stock ORDER BY qty, item");
        rows := new string'(sql_rows);
        sql_close(h);
        print("stock, item;qty (also written to stock.csv):");
        print("##! table key=0 sep={;}");
        for i in 0 to item_n(rows.all) - 1 loop print(item(rows.all, i)); end loop;
        print("####");
        file_open(log, LOG_PATH, read_mode);
        while not endfile(log) loop
            readline(log, l);
            frame := new string'(frame.all & l.all & LF);
        end loop;
        file_close(log);
        print("the frame, around the delivery and the sale:");
        print("##! potpourri");
        for i in 0 to item_n(frame.all) - 1 loop
            if not contains(item(frame.all, i), "shop.vhd report") then print(rstrip(item(frame.all, i))); end if;
        end loop;
        print("####");
        for i in 0 to item_n(frame.all) - 1 loop
            if contains(item(frame.all, i), "shop.vhd report") then print(rstrip(item(frame.all, i))); end if;
        end loop;
    end procedure;
begin
    main : process
        variable command : line;
        variable h : natural;
    begin
        rng.init;
        command := new string'(argument(1));
        if command.all = "deliver" then
            deliver(argument(2));
        elsif command.all = "sell" then
            h := connect;
            sql_close(h);
            sell_go <= true;
            wait for 0 ns;
            while board.finished_n < 3 loop wait for 1 ms; end loop;
            if board.errors /= "" then
                eprint("shop.exe: a sale failed -- " & board.errors);
                process_exit(1);
            end if;
            print("sales, item;qty -- in the order the clerks booked them:");
            print("##! table unordered sep={;}");
            for i in 0 to item_n(board.sales) - 1 loop print(item(board.sales, i)); end loop;
            print("####");
        elsif command.all = "report" then
            report_stock;
        else
            print("choices: sell, report");
            process_exit(1);
        end if;
        print("<hwut-end>");
        wait;
    end process;

    clerks : for c in 0 to 2 generate
        clerk : process
            constant item_list : str_list := clerk_items(c);
            variable h : natural;
        begin
            wait until sell_go;
            h := connect;
            for i in 0 to item_n(item_list) - 1 loop
                wait for rng.uniform(0.0, 5.0) * 1 ms;
                if move(h, item(item_list, i), -1, clerk_name(c)) then
                    board.sold(item(item_list, i) & ";1");
                else
                    board.failed(clerk_name(c) & ": " & sql_rows);
                    exit;
                end if;
            end loop;
            sql_close(h);
            board.finished;
            wait;
        end process;
    end generate;
end architecture;
