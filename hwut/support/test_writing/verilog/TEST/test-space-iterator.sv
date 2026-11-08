// @hwut {
//     title      = "space_iterator: every combination of a parameter basis"
//     build      { framework = "make", target = "%.exe"
//                  caps { memory_mb = 2048 } }
//     choices {
//         product { features = ["sv-space"] }
//         edges   { features = ["sv-space"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The SystemVerilog port of 'python/TEST/test-space-iterator.py',
//          choice for choice, held against its GOOD files by '.link'.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import space_iterator::*;

class Test extends HwutRunner;
    function new();
        // RETURN: the runner of this test.
        super.new("space_iterator: every combination of a parameter basis", '{"product", "edges"});
    endfunction

    function void banner(string label);
        // RETURN: nothing; the section heading is printed.
        $display("");
        $display("--- %s ---", label);
    endfunction

    function void points(basis_t basis);
        // RETURN: nothing; every point of 'basis', one per line, then the count.
        SpaceIterator it = SpaceIterator::do_(basis);
        string        point[$] = {};
        int           n = 0;
        while (it.next_point(point)) begin
            $display("  (%s)", join_text(point));
            n += 1;
        end
        $display("  %0d point(s)", n);
    endfunction

    function void run_product();
        // RETURN: nothing; three dimensions; the rightmost changes fastest.
        basis_t     basis = {};
        dimension_t dimension;
        dimension = '{"0", "2", "4"};  basis.push_back(dimension);
        dimension = '{"otto", "heinz"}; basis.push_back(dimension);
        dimension = '{"1", "2"};       basis.push_back(dimension);
        banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points");
        points(basis);
    endfunction

    function void run_edges();
        // RETURN: nothing; the empty basis, an empty dimension, one dimension.
        basis_t     empty = {};
        basis_t     with_empty = {};
        basis_t     one = {};
        dimension_t dimension;
        banner("an EMPTY basis -- one point, the empty one");
        points(empty);
        banner("a basis with an EMPTY dimension -- nothing");
        dimension = '{"1", "2"}; with_empty.push_back(dimension);
        dimension = {};          with_empty.push_back(dimension);
        dimension = '{"3"};      with_empty.push_back(dimension);
        points(with_empty);
        banner("ONE dimension -- its values one by one");
        dimension = '{"a", "b", "c"}; one.push_back(dimension);
        points(one);
    endfunction

    virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' ran.
        case (choice)
            "product": run_product();
            "edges":   run_edges();
        endcase
    endtask
endclass

module test_space_iterator;
    initial begin
        Test test = new();
        test.run();
    end
endmodule
