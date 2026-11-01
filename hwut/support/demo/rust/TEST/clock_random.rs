// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: A RANDOM NUMBER GENERATOR SEEDED BY THE CLOCK -- what the Python
//          demonstration takes from 'random', for the applications here that
//          draw at random ('demo.rs', 'chamber.rs', 'build.rs', 'producer.rs').
//          No test itself: a module, 'mod clock_random;'. Rust's standard
//          library has no random numbers; this is xorshift64*, plenty for
//          noise. ('garage.rs' draws by the support's DeterministicStream:
//          its draws are the same everywhere, these are not meant to be.)
//______________________________________________________________________________
#![allow(dead_code)]
use std::time::{SystemTime, UNIX_EPOCH};

/// A stream of random numbers.
pub struct Random { state: u64 }

impl Random {
    /// RETURN: Random, seeded by the clock's nanoseconds and the process id
    ///         -- two threads or two processes started at once differ.
    pub fn from_clock() -> Random {
        let ns = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_nanos() as u64).unwrap_or(1);
        let mut random = Random { state: ns ^ ((std::process::id() as u64) << 32) | 1 };
        for _ in 0..8 { random.next_u64(); }
        random
    }

    /// RETURN: u64, the next 64 random bits.
    pub fn next_u64(&mut self) -> u64 {
        self.state ^= self.state >> 12;
        self.state ^= self.state << 25;
        self.state ^= self.state >> 27;
        self.state.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// RETURN: f64, uniform in [0, 1).
    pub fn random(&mut self) -> f64 { (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64 }

    /// RETURN: f64, uniform in [low, high] -- Python's 'random.uniform'.
    pub fn uniform(&mut self, low: f64, high: f64) -> f64 { low + (high - low) * self.random() }

    /// RETURN: i64, uniform in [low, high], both included -- Python's
    ///         'random.randint'.
    pub fn randint(&mut self, low: i64, high: i64) -> i64 {
        low + (self.next_u64() % ((high - low + 1) as u64)) as i64
    }

    /// RETURN: f64, normally distributed around 'mu' with deviation 'sigma'
    ///         (Box-Muller) -- Python's 'random.gauss'.
    pub fn gauss(&mut self, mu: f64, sigma: f64) -> f64 {
        let u1 = 1.0 - self.random();
        let u2 = self.random();
        mu + sigma * (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
    }

    /// RETURN: &T, one element of 'seq' at random -- Python's 'random.choice'.
    pub fn choice<'a, T>(&mut self, seq: &'a [T]) -> &'a T {
        &seq[self.randint(0, seq.len() as i64 - 1) as usize]
    }

    /// RETURN: nothing; 'seq' is shuffled in place (Fisher-Yates).
    pub fn shuffle<T>(&mut self, seq: &mut [T]) {
        for i in (1..seq.len()).rev() {
            let j = self.randint(0, i as i64) as usize;
            seq.swap(i, j);
        }
    }

    /// RETURN: (i64, i64), two DIFFERENT numbers of [low, high) -- Python's
    ///         'random.sample(range(low, high), 2)'.
    pub fn two_of(&mut self, low: i64, high: i64) -> (i64, i64) {
        let first = self.randint(low, high - 1);
        loop {
            let second = self.randint(low, high - 1);
            if second != first { return (first, second); }
        }
    }

    /// RETURN: nothing; the thread slept for 'low' to 'high' seconds.
    pub fn sleep(&mut self, low: f64, high: f64) {
        std::thread::sleep(std::time::Duration::from_secs_f64(self.uniform(low, high)));
    }
}
