-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: SQLITE FOR THE SHOP AND ITS FIXTURE -- no test. VHDL opens no
--          database: 'demo_vhpi.c' does (built with -DDEMO_SQLITE for
--          'shop.exe' and 'fixture.exe' alone, the only two that link
--          libsqlite3).
--
--     h := sql_open(path, true);                  -- statements logged on stderr
--     if not sql(h, "SELECT item, qty FROM stock") then eprint(sql_rows); end if;
--     rows := sql_rows;                           -- 'apple;10' & LF & ...
--     sql_close(h);
-- _____________________________________________________________________________
use work.demo_vhpi.all;

package demo_sql is
    impure function sql_open(path : string; trace_f : boolean) return natural;
    impure function sql(h : natural; statement : string) return boolean;
    impure function sql_rows return string;
    procedure sql_close(h : natural);
end package;

package body demo_sql is
    impure function demo_vhpi_sql_open(path : string; trace_f : integer) return integer;
    attribute foreign of demo_vhpi_sql_open : function is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_sql_open";
    impure function demo_vhpi_sql_open(path : string; trace_f : integer) return integer is
    begin assert false severity failure; return 0; end function;

    impure function demo_vhpi_sql(h : integer; statement : string) return integer;
    attribute foreign of demo_vhpi_sql : function is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_sql";
    impure function demo_vhpi_sql(h : integer; statement : string) return integer is
    begin assert false severity failure; return 0; end function;

    procedure demo_vhpi_sql_close(h : integer);
    attribute foreign of demo_vhpi_sql_close : procedure is "VHPIDIRECT libhwut_vhdl.so demo_vhpi_sql_close";
    procedure demo_vhpi_sql_close(h : integer) is begin assert false severity failure; end procedure;

    impure function sql_open(path : string; trace_f : boolean) return natural is
        -- RETURN: natural, the handle (> 0) of the database 'path', waiting
        --         up to 10 s where another writer holds it, every statement
        --         logged on stderr where 'trace_f'; 0, it cannot be opened
        --         -- the reason is 'sql_rows'.
    begin return demo_vhpi_sql_open(path, boolean'pos(trace_f)); end function;

    impure function sql(h : natural; statement : string) return boolean is
        -- RETURN: true, the statements of 'statement' ran -- their rows are
        --         'sql_rows'; false, else -- SQLite's message is 'sql_rows'.
    begin return demo_vhpi_sql(h, statement) = 0; end function;

    impure function sql_rows return string is
        -- RETURN: string, the rows of the last 'sql' -- the columns joined by
        --         ';', every row ended by LF (a str_list) -- or its message.
    begin return demo_result; end function;

    procedure sql_close(h : natural) is
        -- RETURN: nothing; the database of handle 'h' is closed.
    begin demo_vhpi_sql_close(h); end procedure;
end package body;
