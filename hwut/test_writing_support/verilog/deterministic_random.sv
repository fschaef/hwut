// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
//          'python/deterministic_random.py'. Park-Miller MINSTD:
//          'state = 48271 * state mod (2^31 - 1)', pure integer arithmetic,
//          so the numbers are Python's on every machine and simulator.
//
//     import deterministic_random::*;
//     DeterministicStream s = new(32'h42);
//     SelectionMarker     m = new();
//     int    n    = s.next_int(0, 9);
//     string word = s.select('{"a", "b", "c"});
//     string next = s.select_unchosen('{"a", "b", "c"}, m);
//
// CANDIDATES ARE STRINGS. A SystemVerilog list is typed; the stream picks a
// string, or -- for anything else -- an INDEX ('select_index', 'choice_index',
// 'sample_indices') into the caller's own list. A string is a value, so
// 'SelectionMarker' knows a candidate by its text: two equal strings are one
// candidate -- as Python's interned literals are one object, and the
// property 'unchosen' pins (a fresh list of the same words is the same pool)
// holds. Where equal texts must be distinct alternatives, select by index
// ('select_unchosen_index') and give each its own name.
//
// 'gauss' is the only libm path ($ln, $cos, $sqrt): NOT BIT-PORTABLE (S3).
// _____________________________________________________________________________
package deterministic_random;

    localparam real PI = 3.141592653589793;           // Python's 'math.pi'
    localparam real INF = $bitstoreal(64'h7FF0000000000000);  // Python's 'math.inf'

    class SelectionMarker;
        // Remembers which candidates have been chosen at one selection site,
        // keyed by the candidate's text (strings are values, see the head).
        bit chosen[string];

        function new();
            // RETURN: a marker that has seen nothing yet.
        endfunction

        function void reset();
            // RETURN: nothing; every chosen candidate is forgotten; the next
            //         cycle restarts.
            chosen.delete();
        endfunction
    endclass

    class DeterministicStream;
        longint state;

        function new(longint seed = 'h42);
            // RETURN: a stream standing at 'seed' (its lower 31 bits).
            state = seed & 'h7FFFFFFF;
        endfunction

        function longint next_int(longint v_min, longint v_max);
            // RETURN: an integer uniform in [v_min, v_max]; the state steps
            //         also where the range is one value (which is returned).
            state = (48271 * state) % 2147483647;
            if (v_min == v_max) return v_min;
            return v_min + (state % (v_max - v_min + 1));
        endfunction

        function real next_float();
            // RETURN: a number in [0, 1): 'next_int(0, 1000000) / 1000001'.
            return real'(next_int(0, 1000000)) / 1000001.0;
        endfunction

        function bit coin(real probability_of_true);
            // RETURN: 1 with 'probability_of_true', 0 else -- resolved in
            //         steps of 1/1000001 (TW-1).
            return next_float() < probability_of_true;
        endfunction

        function int select_index(int candidate_n);
            // RETURN: an index into 'candidate_n' candidates, uniformly drawn;
            //         stateless: the same state and 'candidate_n' give the
            //         same index.
            return int'(next_int(0, candidate_n - 1));
        endfunction

        function string select(string candidate_list[$]);
            // RETURN: a candidate of 'candidate_list', uniformly drawn.
            return candidate_list[select_index(candidate_list.size())];
        endfunction

        function int choice_index(int element_n);
            // RETURN: an index into 'element_n' elements, uniformly drawn.
            return select_index(element_n);
        endfunction

        function string choice(string element_list[$]);
            // RETURN: an element of 'element_list', uniformly drawn.
            return element_list[choice_index(element_list.size())];
        endfunction

        function string select_unchosen(string candidate_list[$], SelectionMarker marker);
            // RETURN: a candidate 'marker' has not seen, uniformly drawn among
            //         those, and now seen; where every candidate was seen,
            //         'marker' is reset and the draw is from all of them.
            string unchosen[$] = {};
            string chosen;
            foreach (candidate_list[i]) if (!marker.chosen.exists(candidate_list[i])) unchosen.push_back(candidate_list[i]);
            if (unchosen.size() == 0) begin
                marker.reset();
                unchosen = candidate_list;
            end
            chosen = unchosen[next_int(0, unchosen.size() - 1)];
            marker.chosen[chosen] = 1;
            return chosen;
        endfunction

        function int select_unchosen_index(string name_list[$], SelectionMarker marker);
            // RETURN: the index into 'name_list' of the candidate
            //         'select_unchosen' draws -- the first of that name.
            string chosen = select_unchosen(name_list, marker);
            foreach (name_list[i]) if (name_list[i] == chosen) return i;
            return -1;
        endfunction

        function real gauss(real mu, real sigma, real lower = -INF, real upper = INF);
            // RETURN: a draw of the normal distribution (mu, sigma) by the
            //         Box-Muller transform, clipped to [lower, upper].
            real u1 = next_float() + 1e-9;                     // avoid log(0)
            real u2 = next_float();
            real z0 = $sqrt(-2.0 * $ln(u1)) * $cos(2.0 * PI * u2);
            real result = z0 * sigma + mu;
            if (result < lower) return lower;
            if (result > upper) return upper;
            return result;
        endfunction

        function longint gauss_int(real mu, real sigma, real lower = -INF, real upper = INF);
            // RETURN: 'gauss' rounded to the nearest integer, a half to the
            //         even one -- Python's 'round'.
            real    x     = gauss(mu, sigma, lower, upper);
            real    below = $floor(x);
            longint n     = longint'(below);
            if (x - below > 0.5 || (x - below == 0.5 && n % 2 != 0)) n += 1;
            return n;
        endfunction

        function void sample_indices(int population_size, int k, ref int result[$]);
            // RETURN: nothing; 'result' holds 'k' distinct indices of
            //         0 .. population_size-1, drawn by Fisher-Yates in
            //         Python's order. 'population_size' >= 'k'.
            int index[$] = {};
            result = {};
            for (int i = 0; i < population_size; i++) index.push_back(i);
            for (int i = 0; i < k; i++) begin
                int j = int'(next_int(i, population_size - 1));
                int t = index[i];
                index[i] = index[j];
                index[j] = t;
                result.push_back(index[i]);
            end
        endfunction

        function void sample(string population[$], int n, ref string result[$]);
            // RETURN: nothing; 'result' holds 'n' elements of 'population' at
            //         distinct places, in the order 'sample_indices' draws.
            int index[$] = {};
            sample_indices(population.size(), n, index);
            result = {};
            foreach (index[i]) result.push_back(population[index[i]]);
        endfunction
    endclass

endpackage
