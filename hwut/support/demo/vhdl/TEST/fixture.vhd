-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
--
--     fixture.exe open            a fresh 'TMP/shop.db', stocked as below, and
--                                 an empty 'TMP/frame.log' ('on_entry', and
--                                 'hwut.execute fixture open')
--     fixture.exe close           both removed ('on_exit')
--     fixture.exe check <when> <app> [<choice>]
--                                 'when' is 'before' or 'after': whether the
--                                 stock adds up around the test run '<app>
--                                 <choice>', appended to 'TMP/frame.log'
--                                 ('on_before_test', 'on_after_test')
--
-- 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
-- which hwut sets for the run the check stands around; a test without
-- choices has none. 'check' concerns the shop's tests alone. The stock ADDS
-- UP where every item's quantity is its opening quantity plus every movement
-- of the journal.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.demo_vhpi.all;
use work.demo_sql.all;

entity fixture is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture helper of fixture is
    constant TMP_PATH : string := HERE & "/TMP";
    constant DB_PATH  : string := TMP_PATH & "/shop.db";
    constant LOG_PATH : string := TMP_PATH & "/frame.log";
    constant OPENING  : string := "INSERT INTO opening VALUES ('apple', 10), ('pear', 5), ('plum', 5);"
                                  & "INSERT INTO stock   VALUES ('apple', 10), ('pear', 5), ('plum', 5);";

    procedure must(h : natural; statement : string) is
        -- RETURN: nothing, if 'statement' ran; else the process ends (2), the
        --         reason on stderr.
    begin
        if sql(h, statement) then return; end if;
        eprint("fixture.exe: " & sql_rows);
        process_exit(2);
    end procedure;

    procedure open_shop is
        -- RETURN: nothing; a fresh, stocked database and an empty log stand.
        variable h : natural;
        file     f : text;
    begin
        make_directory(TMP_PATH);
        remove(DB_PATH);
        remove(LOG_PATH);
        h := sql_open(DB_PATH, false);
        must(h, "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER);"
                & "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER);"
                & "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT);" & OPENING);
        sql_close(h);
        file_open(f, LOG_PATH, write_mode);
        file_close(f);
    end procedure;

    procedure close_shop is
        -- RETURN: nothing; the database and the log do not stand.
    begin remove(DB_PATH); remove(LOG_PATH); end procedure;

    impure function adds_up return boolean is
        -- RETURN: true, if every item's stock is its opening quantity plus its
        --         journal's movements; false, else.
        variable h : natural := sql_open(DB_PATH, false);
        variable ok : boolean;
    begin
        must(h, "SELECT count(*) FROM (SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0) AS expected, s.qty AS got"
                & "  FROM opening o JOIN stock s ON s.item = o.item"
                & "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item) WHERE expected <> got");
        ok := sql_rows = "0" & LF;
        sql_close(h);
        return ok;
    end function;

    procedure check(when_text : string; test : string; choice : string) is
        -- RETURN: nothing; one line more in the log, for a shop test run.
        file     f       : text;
        variable l       : line;
        variable verdict : line := new string'("STOCK BROKEN");
    begin
        if test /= "delivery.json" and test /= "shop.vhd" then return; end if;
        if adds_up then verdict := new string'("stock adds up"); end if;
        file_open(f, LOG_PATH, append_mode);
        if choice = "" then write(l, ljust(when_text, 6) & " " & ljust(test, 15) & " " & verdict.all);
        else                write(l, ljust(when_text, 6) & " " & ljust(test & " " & choice, 15) & " " & verdict.all);
        end if;
        writeline(f, l);
        file_close(f);
    end procedure;
begin
    main : process
        variable command : line;
    begin
        command := new string'(argument(1));
        if    command.all = "open"  then open_shop;
        elsif command.all = "close" then close_shop;
        elsif command.all = "check" then check(argument(2), argument(3), argument(4));
        else
            eprint("usage: fixture.exe open | close | check before|after <app> <choice>");
            process_exit(2);
        end if;
        wait;
    end process;
end architecture;
