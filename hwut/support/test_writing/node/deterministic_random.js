// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
//          'python/deterministic_random.py'. The same seed gives the same
//          numbers as the Python module, draw for draw: the core is Park-Miller
//          MINSTD, 'state = 48271 * state mod (2^31 - 1)'. In a JS number (a
//          double) the product stays below 48271 * 2^31 < 2^47 < 2^53, so it
//          is EXACT -- no BigInt needed.
//
//     const { DeterministicStream, SelectionMarker } =
//         require(path.join(__dirname, '..', 'deterministic_random.js'));
//     const s = new DeterministicStream(0x42);
//     s.next_int(0, 9);          s.next_float();        s.coin(0.5);
//     s.select(pool);            s.choice(pool);        s.gauss(0, 1);
//     s.sample_indices(10, 3);   s.sample(pool, 3);
//     const m = new SelectionMarker();
//     s.select_unchosen(pool, m);    // prefers what 'm' has not seen
//
// 'gauss' is the one path through the platform's libm, as in Python: a last
// bit may differ between languages, so a GOOD that prints a draw tolerates
// the last digits.
//
// IDENTITY IN JS: Python's marker remembers candidates by 'id(object)'. Here
// an object is remembered by its identity (a 'Set' of the objects), a
// primitive -- a string, a number -- by its value: two equal strings are one
// candidate, as in the Perl port.
//_____________________________________________________________________________
'use strict';

const MODULUS = 2147483647;

class SelectionMarker {
    /* RETURN: SelectionMarker, with nothing chosen yet. */
    constructor() { this.chosen = new Set(); }

    /* RETURN: undefined. Forgets every chosen candidate; the next cycle restarts. */
    reset() { this.chosen.clear(); }
}

class DeterministicStream {
    /* RETURN: DeterministicStream, seeded with 'seed' (0x42 where none);
     *         the state is 'seed & 0x7FFFFFFF'. */
    constructor(seed = 0x42) { this.state = Number(BigInt(seed) & 0x7FFFFFFFn); }

    /* RETURN: integer, uniform in [v_min, v_max]. The state steps even where
     *         the range is a single value. */
    next_int(v_min, v_max) {
        this.state = (48271 * this.state) % MODULUS;
        if (v_min === v_max) return v_min;
        return v_min + (this.state % (v_max - v_min + 1));
    }

    /* RETURN: number, in [0, 1): 1000001 values, 'next_int(0, 1000000) / 1000001'. */
    next_float() { return this.next_int(0, 1000000) / 1000001.0; }

    /* RETURN: true with probability 'p', false else -- resolved in steps of
     *         1/1000001 (any 0 < p <= 1/1000001 is exactly 1/1000001). */
    coin(p) { return this.next_float() < p; }

    /* RETURN: one element of the array (or string) 'candidates', uniformly drawn. */
    select(candidates) { return candidates[this.next_int(0, candidates.length - 1)]; }

    /* RETURN: one element of the array 'seq', uniformly drawn. */
    choice(seq) { return seq[this.next_int(0, seq.length - 1)]; }

    /* RETURN: one candidate the marker has not seen, uniformly drawn among
     *         those -- recorded in the marker. Where every candidate was seen,
     *         the marker is reset and the draw is over all of them. */
    select_unchosen(candidates, marker) {
        let unchosen = Array.from(candidates).filter(c => !marker.chosen.has(c));
        if (unchosen.length === 0) {
            marker.reset();
            unchosen = Array.from(candidates);
        }
        const choice = unchosen[this.next_int(0, unchosen.length - 1)];
        marker.chosen.add(choice);
        return choice;
    }

    /* RETURN: number, a draw of the normal distribution (mu, sigma) by the
     *         Box-Muller transform, clipped to [lower, upper] (default
     *         -Infinity, Infinity). */
    gauss(mu, sigma, lower = -Infinity, upper = Infinity) {
        const u1 = this.next_float() + 1e-9;
        const u2 = this.next_float();
        const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
        const result = z0 * sigma + mu;
        if (result < lower) return lower;
        if (result > upper) return upper;
        return result;
    }

    /* RETURN: integer, 'gauss' rounded to the nearest -- a half to the even
     *         one, as Python's 'round'. */
    gauss_int(mu, sigma, lower = -Infinity, upper = Infinity) {
        const x = this.gauss(mu, sigma, lower, upper);
        const f = Math.floor(x), d = x - f;
        return d < 0.5 ? f : d > 0.5 ? f + 1 : (f % 2 === 0 ? f : f + 1);
    }

    /* RETURN: array of 'k' distinct indices of 0 .. population_size - 1,
     *         drawn by Fisher-Yates; throws Error where k > population_size. */
    sample_indices(population_size, k) {
        if (k > population_size) throw new Error(`sample_indices: ${k} > ${population_size}`);
        const index = Array.from({ length: population_size }, (_, i) => i);
        const result = [];
        for (let i = 0; i < k; i += 1) {
            const j = this.next_int(i, population_size - 1);
            [index[i], index[j]] = [index[j], index[i]];
            result.push(index[i]);
        }
        return result;
    }

    /* RETURN: array of 'n' distinct elements of the array 'population'. */
    sample(population, n) {
        return this.sample_indices(population.length, n).map(i => population[i]);
    }
}

module.exports = { DeterministicStream, SelectionMarker };
