// @hwut {
//     title      = "DeterministicStream RNG and SelectionMarker spread"
//     build      { framework = "make", target = "%.exe"
//                  caps { memory_mb = 2048 } }
//     choices {
//         gauss      { features = ["sv-random"] }
//         primitives { features = ["sv-random"] }
//         ranges     { features = ["sv-random"] }
//         sample     { features = ["sv-random"] }
//         seed_sweep { features = ["sv-random"] }
//         select     { features = ["sv-random"] }
//         unchosen   { features = ["sv-random"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The SystemVerilog port of 'python/TEST/test-deterministic-random.py',
//          choice for choice, held against its GOOD files by '.link'.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import deterministic_random::*;

class Test extends HwutRunner;
    localparam longint SEED = 'h42;
    localparam string  TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}";
    localparam string  REGION_END             = "####";

    function new();
        // RETURN: the runner of this test.
        super.new("DeterministicStream RNG and SelectionMarker spread",
                  '{"primitives", "ranges", "gauss", "sample", "select", "unchosen", "seed_sweep"});
    endfunction

    function void banner(string label);
        // RETURN: nothing; the section heading is printed.
        $display("");
        $display("--- %s ---", label);
    endfunction

    function string index_list_repr(int index[$]);
        // RETURN: the indices as Python prints a list of int.
        string text[$] = {};
        foreach (index[i]) text.push_back($sformatf("%0d", index[i]));
        return {"[", join_text(text), "]"};
    endfunction

    function void run_primitives();
        // RETURN: nothing; the bare generator: next_int, next_float, coin.
        DeterministicStream s;
        string              said[$] = {};
        banner("next_int(0, 1000000) -- first 20");
        s = new(SEED);
        for (int i = 0; i < 20; i++) $display("[%02d] %0d", i, s.next_int(0, 1000000));
        banner("next_float -- first 10 (full precision)");
        s = new(SEED);
        for (int i = 0; i < 10; i++) $display("[%02d] %s", i, float_repr(s.next_float()));
        banner("coin(0.5) -- 40 draws");
        s = new(SEED);
        for (int i = 0; i < 40; i++) said.push_back(s.coin(0.5) ? string'("T") : string'("F"));
        $display("%s", join_text(said, " "));
    endfunction

    function void run_ranges();
        // RETURN: nothing; next_int over small and degenerate ranges.
        DeterministicStream s;
        string              said[$] = {};
        banner("next_int(0, 9) -- 30 draws");
        s = new(SEED);
        for (int i = 0; i < 30; i++) said.push_back($sformatf("%0d", s.next_int(0, 9)));
        $display("%s", join_text(said, " "));
        banner("next_int(5, 5) -- degenerate range returns the bound");
        s = new(SEED);
        said = {};
        for (int i = 0; i < 5; i++) said.push_back($sformatf("%0d", s.next_int(5, 5)));
        $display("%s", join_text(said, " "));
        banner("next_int(-3, 3) -- spanning zero");
        s = new(SEED);
        said = {};
        for (int i = 0; i < 20; i++) begin
            longint n = s.next_int(-3, 3);
            said.push_back($sformatf("%s%0d", n >= 0 ? string'("+") : string'(""), n));     // '%+d'
        end
        $display("%s", join_text(said, " "));
    endfunction

    function void run_gauss();
        // RETURN: nothing; the libm path: gauss, clamped gauss, gauss_int --
        //         the two full-precision blocks framed as a 'table' region
        //         with a per-column numeric tolerance (see the Python test).
        DeterministicStream s;
        string              said[$] = {};
        banner("gauss(0, 1) -- 10 draws (full precision)");
        s = new(SEED);
        $display("%s", TOLERANCE_REGION_BEGIN);
        for (int i = 0; i < 10; i++) $display("[%02d] %s", i, float_repr(s.gauss(0.0, 1.0)));
        $display("%s", REGION_END);
        banner("gauss(0, 1) clamped to [-1, 1]");
        s = new(SEED);
        $display("%s", TOLERANCE_REGION_BEGIN);
        for (int i = 0; i < 10; i++) $display("[%02d] %s", i, float_repr(s.gauss(0.0, 1.0, -1.0, 1.0)));
        $display("%s", REGION_END);
        banner("gauss_int(100, 15) -- 20 draws");
        s = new(SEED);
        for (int i = 0; i < 20; i++) said.push_back($sformatf("%0d", s.gauss_int(100.0, 15.0)));
        $display("%s", join_text(said, " "));
    endfunction

    function void run_sample();
        // RETURN: nothing; sample_indices (Fisher-Yates) and sample over a list.
        DeterministicStream s;
        int                 index[$] = {};
        string              said[$] = {};
        string              pool[$] = '{"alpha", "beta", "gamma", "delta", "epsilon"};
        string              letter[$] = '{"A", "B", "C", "D", "E", "F", "G", "H"};
        banner("sample_indices(10, 10) -- full permutation");
        s = new(SEED);
        s.sample_indices(10, 10, index);
        $display("%s", index_list_repr(index));
        banner("sample_indices(20, 5) -- partial draw");
        s = new(SEED);
        s.sample_indices(20, 5, index);
        $display("%s", index_list_repr(index));
        banner("choice from a list -- 20 draws");
        s = new(SEED);
        for (int i = 0; i < 20; i++) said.push_back(s.choice(pool));
        $display("%s", join_text(said, " "));
        banner("sample(list, 4) -- unique elements");
        s = new(SEED);
        s.sample(letter, 4, said);
        $display("%s", list_repr(said));
    endfunction

    function void run_select();
        // RETURN: nothing; stateless select: same state + same pool -> same
        //         element.
        DeterministicStream s;
        string              said[$] = {};
        string              pool[$] = '{"a", "b", "c", "d"};
        string              branches[$] = '{"p", "q", "r"};
        banner("select over a list -- 20 draws");
        s = new(SEED);
        for (int i = 0; i < 20; i++) said.push_back(s.select(pool));
        $display("%s", join_text(said, " "));
        banner("select over a tuple -- 12 draws");
        s = new(SEED);
        said = {};
        for (int i = 0; i < 12; i++) said.push_back(s.select(branches));
        $display("%s", join_text(said, " "));
    endfunction

    function void run_unchosen();
        // RETURN: nothing; select_unchosen spread is keyed by the candidate,
        //         not by the container: a stable pool, a FRESH pool every
        //         call, sub-pool coherence, and reset.
        DeterministicStream s;
        SelectionMarker     m;
        string              said[$] = {};
        string              before_reset[$] = {};
        string              after_reset[$] = {};
        string              first;
        string              pool[$] = '{"a", "b", "c", "d"};
        string              sub[$]  = '{"a", "b"};
        banner("stable pool -- three full cycles of 4 elements");
        s = new(SEED);
        m = new();
        for (int i = 0; i < 12; i++) said.push_back(s.select_unchosen(pool, m));
        $display("%s", join_text(said, " "));
        banner("FRESH container each call -- identical to the stable pool above");
        s = new(SEED);
        m = new();
        said = {};
        for (int i = 0; i < 12; i++) begin
            string fresh[$] = '{"a", "b", "c", "d"};          // a new queue every call
            said.push_back(s.select_unchosen(fresh, m));
        end
        $display("%s", join_text(said, " "));
        banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]");
        s = new(SEED);
        m = new();
        first = s.select_unchosen(sub, m);
        said = {};
        for (int i = 0; i < 3; i++) said.push_back(s.select_unchosen(pool, m));
        $display("first(from sub): %s  then(from full): %s", first, join_text(said, " "));
        banner("reset() restarts the cycle");
        s = new(SEED);
        m = new();
        for (int i = 0; i < 4; i++) before_reset.push_back(s.select_unchosen(pool, m));
        m.reset();
        for (int i = 0; i < 4; i++) after_reset.push_back(s.select_unchosen(pool, m));
        $display("before reset: %s", join_text(before_reset, " "));
        $display("after  reset: %s", join_text(after_reset, " "));
    endfunction

    function void run_seed_sweep();
        // RETURN: nothing; the first next_int per seed -- pins seed handling.
        banner("first next_int(0, 1000000) per seed 0..15");
        for (int seed = 0; seed < 16; seed++) begin
            DeterministicStream s = new(seed);
            $display("seed=%2d -> %0d", seed, s.next_int(0, 1000000));
        end
    endfunction

    virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' ran.
        case (choice)
            "primitives": run_primitives();
            "ranges":     run_ranges();
            "gauss":      run_gauss();
            "sample":     run_sample();
            "select":     run_select();
            "unchosen":   run_unchosen();
            "seed_sweep": run_seed_sweep();
        endcase
    endtask
endclass

module test_deterministic_random;
    initial begin
        Test test = new();
        test.run();
    end
endmodule
