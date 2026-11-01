// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
//          'python/deterministic_random.py'. The same seed gives the same
//          numbers as the Python module, draw for draw: Park-Miller MINSTD,
//          'state = 48271 * state mod (2^31 - 1)'.
//
//     use hwut::deterministic_random::{DeterministicStream, SelectionMarker};
//     let mut s = DeterministicStream::new(0x42);
//     s.next_int(0, 9);           s.next_float();        s.coin(0.5);
//     s.select(&pool);            s.choice(&pool);       -- a reference into 'pool'
//     s.gauss(0.0, 1.0);          s.gauss_within(0.0, 1.0, -1.0, 1.0);
//     s.sample_indices(10, 3);    s.sample(&pool, 3);
//
//     let mut m = SelectionMarker::new();
//     s.select_unchosen(&["a", "b"], &mut m);
//
// THE ARITHMETIC IS i64: Python's integers are unbounded, but the stream's
// product stays below 48271 * 2^31, far inside i64.
//
// IDENTITY, AS IN PYTHON: a marker remembers a candidate by the ADDRESS of
// the object a candidate REFERS to -- what 'id()' is in Python. Two string
// literals of one text are commonly one object in Rust, as two equal short
// strings are in Python; a test that relies on it names each once ('static').
//
// 'gauss' is the one path through libm: a last bit may differ between
// platforms, so a GOOD that prints a draw tolerates the last digits.
//______________________________________________________________________________
use std::collections::HashSet;

/// Remembers which candidate OBJECTS have been chosen at one selection site.
#[derive(Default)]
pub struct SelectionMarker {
    chosen: HashSet<usize>,                       // addresses of the candidates
}

impl SelectionMarker {
    /// RETURN: SelectionMarker, nothing chosen yet.
    pub fn new() -> SelectionMarker { SelectionMarker { chosen: HashSet::new() } }

    /// RETURN: nothing; every chosen candidate is forgotten, the next cycle
    ///         restarts.
    pub fn reset(&mut self) { self.chosen.clear(); }

    /// RETURN: bool, true where 'candidate' (by the address it refers to) was
    ///         chosen.
    pub fn seen_f<T: ?Sized>(&self, candidate: &T) -> bool { self.chosen.contains(&identity(candidate)) }
}

/// RETURN: usize, the address of the object 'candidate' is -- its identity.
fn identity<T: ?Sized>(candidate: &T) -> usize { candidate as *const T as *const () as usize }

/// A platform-independent random number generator (MINSTD).
#[derive(Clone, Debug)]
pub struct DeterministicStream {
    pub state: i64,
}

impl DeterministicStream {
    /// RETURN: DeterministicStream standing at 'seed' (masked to 31 bits);
    ///         Python's default seed is 0x42.
    pub fn new(seed: i64) -> DeterministicStream { DeterministicStream { state: seed & 0x7FFF_FFFF } }

    /// RETURN: i64, an integer uniform in [v_min, v_max]; the state steps
    ///         even where the range is one value.
    pub fn next_int(&mut self, v_min: i64, v_max: i64) -> i64 {
        self.state = (48271 * self.state) % 2147483647;
        if v_min == v_max { return v_min; }
        v_min + self.state.rem_euclid(v_max - v_min + 1)
    }

    /// RETURN: f64, a number in [0, 1): 'next_int(0, 1000000) / 1000001'.
    pub fn next_float(&mut self) -> f64 { self.next_int(0, 1000000) as f64 / 1000001.0 }

    /// RETURN: bool, true with 'probability_of_true', false else. THE FLOOR
    ///         (TW-1): resolved in steps of 1/1000001.
    pub fn coin(&mut self, probability_of_true: f64) -> bool { self.next_float() < probability_of_true }

    /// RETURN: &T, a uniformly drawn element of 'candidates' (not empty);
    ///         stateless: the same state and candidates give the same one.
    pub fn select<'a, T>(&mut self, candidates: &'a [T]) -> &'a T {
        &candidates[self.next_int(0, candidates.len() as i64 - 1) as usize]
    }

    /// RETURN: &T, a uniformly drawn element of 'seq' (not empty) -- 'select'.
    pub fn choice<'a, T>(&mut self, seq: &'a [T]) -> &'a T { self.select(seq) }

    /// RETURN: &T, a candidate whose identity 'marker' has not seen, drawn
    ///         uniformly among those and recorded in 'marker'; where every one
    ///         was seen, 'marker' is reset and the draw is over all.
    ///
    /// A candidate is a REFERENCE; its identity is the address it refers to,
    /// so the same objects offered in a fresh container, or in a sub-pool,
    /// are the same candidates.
    pub fn select_unchosen<'a, T: ?Sized>(&mut self, candidates: &[&'a T],
                                          marker: &mut SelectionMarker) -> &'a T {
        let mut unchosen: Vec<&'a T> = candidates.iter().copied()
                                                 .filter(|c| !marker.seen_f(*c)).collect();
        if unchosen.is_empty() {
            marker.reset();
            unchosen = candidates.to_vec();
        }
        let choice = unchosen[self.next_int(0, unchosen.len() as i64 - 1) as usize];
        marker.chosen.insert(identity(choice));
        choice
    }

    /// RETURN: f64, a draw of the normal distribution (mu, sigma) by the
    ///         Box-Muller transform, unclipped.
    pub fn gauss(&mut self, mu: f64, sigma: f64) -> f64 {
        self.gauss_within(mu, sigma, f64::NEG_INFINITY, f64::INFINITY)
    }

    /// RETURN: f64, a draw of the normal distribution (mu, sigma) by the
    ///         Box-Muller transform, clipped to [lower, upper] -- Python's
    ///         'gauss(mu, sigma, lower, upper)'. NOT BIT-PORTABLE (S3): libm.
    pub fn gauss_within(&mut self, mu: f64, sigma: f64, lower: f64, upper: f64) -> f64 {
        let u1 = self.next_float() + 1e-9;               // avoid log(0)
        let u2 = self.next_float();
        let z0 = (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos();
        let result = z0 * sigma + mu;
        if result < lower { lower } else if result > upper { upper } else { result }
    }

    /// RETURN: i64, 'gauss' rounded to the nearest integer, a half to the
    ///         even one -- as Python's 'round'.
    pub fn gauss_int(&mut self, mu: f64, sigma: f64) -> i64 { self.gauss(mu, sigma).round_ties_even() as i64 }

    /// RETURN: i64, 'gauss_within' rounded as 'gauss_int' rounds.
    pub fn gauss_int_within(&mut self, mu: f64, sigma: f64, lower: i64, upper: i64) -> i64 {
        self.gauss_within(mu, sigma, lower as f64, upper as f64).round_ties_even() as i64
    }

    /// RETURN: Vec<usize>, 'k' distinct indices of 0 .. population_size-1,
    ///         drawn by Fisher-Yates. Panics where k > population_size, as
    ///         Python's assertion fails.
    pub fn sample_indices(&mut self, population_size: usize, k: usize) -> Vec<usize> {
        assert!(population_size >= k);
        let mut index: Vec<usize> = (0..population_size).collect();
        let mut result = Vec::with_capacity(k);
        for i in 0..k {
            let j = self.next_int(i as i64, population_size as i64 - 1) as usize;
            index.swap(i, j);
            result.push(index[i]);
        }
        result
    }

    /// RETURN: Vec<T>, 'n' elements of 'population' at distinct places, in
    ///         the order 'sample_indices' draws them.
    pub fn sample<T: Clone>(&mut self, population: &[T], n: usize) -> Vec<T> {
        self.sample_indices(population.len(), n).into_iter().map(|i| population[i].clone()).collect()
    }
}
