-- @hwut {
--     title      = "space_iterator: every combination of a parameter basis"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         product { features = ["vhdl-space"] }
--         edges   { features = ["vhdl-space"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The VHDL port of 'python/TEST/test-space-iterator.py', held against
--          its GOOD files by '.link'. A dimension of the basis is a str_list of
--          the values' texts; the iterator yields the indices.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_runner.all;
use work.hwut_pytext.all;
use work.space_iterator.all;

entity test_space_iterator is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
end entity;

architecture test of test_space_iterator is
    procedure banner(label_text : string) is
    begin print(""); print("--- " & label_text & " ---"); end procedure;

    procedure points(variable basis : inout line_vector) is
        -- RETURN: nothing; every point of 'basis' is printed, one per line,
        --         then the count.
        variable it   : SpaceIterator;
        variable size : integer_vector(0 to basis'length - 1);
        variable text : line;
        variable n    : natural := 0;
    begin
        for i in size'range loop size(i) := item_n(basis(basis'left + i).all); end loop;
        it.do(size);
        while it.next_point loop
            text := new string'("  (");
            for i in size'range loop
                if i /= 0 then write(text, string'(", ")); end if;
                write(text, item(basis(basis'left + i).all, it.point(i)));
            end loop;
            write(text, string'(")"));
            print(text.all);
            n := n + 1;
        end loop;
        print("  " & integer'image(n) & " point(s)");
    end procedure;

    procedure run_product is
        variable basis : line_vector(0 to 2) := (new string'("0" & LF & "2" & LF & "4" & LF),
                                                 new string'("otto" & LF & "heinz" & LF),
                                                 new string'("1" & LF & "2" & LF));
    begin
        banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points");
        points(basis);
    end procedure;

    procedure run_edges is
        variable empty  : line_vector(1 to 0);
        variable hollow : line_vector(0 to 2) := (new string'("1" & LF & "2" & LF), new string'(""),
                                                  new string'("3" & LF));
        variable one    : line_vector(0 to 0) := (0 => new string'("a" & LF & "b" & LF & "c" & LF));
    begin
        banner("an EMPTY basis -- one point, the empty one");
        points(empty);
        banner("a basis with an EMPTY dimension -- nothing");
        points(hollow);
        banner("ONE dimension -- its values one by one");
        points(one);
    end procedure;
begin
    main : process
        variable runner : HwutRunner;
    begin
        runner.init(HWUT_ARGC, HWUT_ARGV1, "space_iterator: every combination of a parameter basis");
        runner.add("product");
        runner.add("edges");
        while runner.dispatch loop
            if    runner.choice = "product" then run_product;
            elsif runner.choice = "edges"   then run_edges;
            end if;
            runner.choice_done;
        end loop;
        wait;
    end process;
end architecture;
