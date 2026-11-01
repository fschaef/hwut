// @hwut {
//     title      = "DeterministicStream RNG and SelectionMarker spread"
//     build      { framework = "make", executable = "%.exe" }
//     choices {
//         gauss      { features = ["rust-random"] }
//         primitives { features = ["rust-random"] }
//         ranges     { features = ["rust-random"] }
//         sample     { features = ["rust-random"] }
//         seed_sweep { features = ["rust-random"] }
//         select     { features = ["rust-random"] }
//         unchosen   { features = ["rust-random"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: The Rust port of 'python/TEST/test-deterministic-random.py',
//          choice for choice, held against its GOOD files by '.link'.
//______________________________________________________________________________
use hwut::deterministic_random::{DeterministicStream, SelectionMarker};
use hwut::hwut_pytext::{float_repr, PyRepr};
use hwut::hwut_runner::HwutRunner;

const SEED: i64 = 0x42;
const TOLERANCE_REGION_BEGIN: &str = "##! table numeric={1:1e-12}";
const REGION_END: &str = "####";

fn banner(label: &str) { println!("\n--- {} ---", label); }

fn stream() -> DeterministicStream { DeterministicStream::new(SEED) }

fn run_primitives() {
    banner("next_int(0, 1000000) -- first 20");
    let mut s = stream();
    for i in 0..20 { println!("[{:02}] {}", i, s.next_int(0, 1000000)); }
    banner("next_float -- first 10 (full precision)");
    let mut s = stream();
    for i in 0..10 { println!("[{:02}] {}", i, float_repr(s.next_float())); }
    banner("coin(0.5) -- 40 draws");
    let mut s = stream();
    println!("{}", (0..40).map(|_| if s.coin(0.5) { "T" } else { "F" }).collect::<Vec<_>>().join(" "));
}

fn run_ranges() {
    banner("next_int(0, 9) -- 30 draws");
    let mut s = stream();
    println!("{}", (0..30).map(|_| s.next_int(0, 9).to_string()).collect::<Vec<_>>().join(" "));
    banner("next_int(5, 5) -- degenerate range returns the bound");
    let mut s = stream();
    println!("{}", (0..5).map(|_| s.next_int(5, 5).to_string()).collect::<Vec<_>>().join(" "));
    banner("next_int(-3, 3) -- spanning zero");
    let mut s = stream();
    println!("{}", (0..20).map(|_| format!("{:+}", s.next_int(-3, 3))).collect::<Vec<_>>().join(" "));
}

fn run_gauss() {
    banner("gauss(0, 1) -- 10 draws (full precision)");
    let mut s = stream();
    println!("{}", TOLERANCE_REGION_BEGIN);
    for i in 0..10 { println!("[{:02}] {}", i, float_repr(s.gauss(0.0, 1.0))); }
    println!("{}", REGION_END);
    banner("gauss(0, 1) clamped to [-1, 1]");
    let mut s = stream();
    println!("{}", TOLERANCE_REGION_BEGIN);
    for i in 0..10 { println!("[{:02}] {}", i, float_repr(s.gauss_within(0.0, 1.0, -1.0, 1.0))); }
    println!("{}", REGION_END);
    banner("gauss_int(100, 15) -- 20 draws");
    let mut s = stream();
    println!("{}", (0..20).map(|_| s.gauss_int(100.0, 15.0).to_string()).collect::<Vec<_>>().join(" "));
}

fn run_sample() {
    banner("sample_indices(10, 10) -- full permutation");
    let mut s = stream();
    println!("{}", s.sample_indices(10, 10).py_repr());
    banner("sample_indices(20, 5) -- partial draw");
    let mut s = stream();
    println!("{}", s.sample_indices(20, 5).py_repr());
    banner("choice from a list -- 20 draws");
    let mut s = stream();
    let pool = ["alpha", "beta", "gamma", "delta", "epsilon"];
    println!("{}", (0..20).map(|_| *s.choice(&pool)).collect::<Vec<_>>().join(" "));
    banner("sample(list, 4) -- unique elements");
    let mut s = stream();
    let letter: Vec<String> = "ABCDEFGH".chars().map(|c| c.to_string()).collect();
    println!("{}", s.sample(&letter, 4).py_repr());
}

fn run_select() {
    banner("select over a list -- 20 draws");
    let mut s = stream();
    let pool = ["a", "b", "c", "d"];
    println!("{}", (0..20).map(|_| *s.select(&pool)).collect::<Vec<_>>().join(" "));
    banner("select over a tuple -- 12 draws");
    let mut s = stream();
    let branches = ("p", "q", "r");
    let branches = [branches.0, branches.1, branches.2];
    println!("{}", (0..12).map(|_| *s.select(&branches)).collect::<Vec<_>>().join(" "));
}

//  ONE OBJECT PER TEXT, as Python's interned "a": a candidate is known by
//  the address it refers to.
static A: &str = "a";
static B: &str = "b";
static C: &str = "c";
static D: &str = "d";

fn run_unchosen() {
    banner("stable pool -- three full cycles of 4 elements");
    let mut s = stream();
    let pool = [A, B, C, D];
    let mut m = SelectionMarker::new();
    println!("{}", (0..12).map(|_| s.select_unchosen(&pool, &mut m)).collect::<Vec<_>>().join(" "));

    banner("FRESH container each call -- identical to the stable pool above");
    let mut s = stream();
    let mut m = SelectionMarker::new();
    let mut out = Vec::new();
    for _ in 0..12 {
        let fresh = vec![A, B, C, D];                 // a new container every call
        out.push(s.select_unchosen(&fresh, &mut m));
    }
    println!("{}", out.join(" "));

    banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]");
    let mut s = stream();
    let mut m = SelectionMarker::new();
    let full = [A, B, C, D];
    let sub  = [A, B];
    let first = s.select_unchosen(&sub, &mut m);
    let rest: Vec<&str> = (0..3).map(|_| s.select_unchosen(&full, &mut m)).collect();
    println!("first(from sub): {}  then(from full): {}", first, rest.join(" "));

    banner("reset() restarts the cycle");
    let mut s = stream();
    let pool = [A, B, C, D];
    let mut m = SelectionMarker::new();
    let before: Vec<&str> = (0..4).map(|_| s.select_unchosen(&pool, &mut m)).collect();
    m.reset();
    let after: Vec<&str> = (0..4).map(|_| s.select_unchosen(&pool, &mut m)).collect();
    println!("before reset: {}", before.join(" "));
    println!("after  reset: {}", after.join(" "));
}

fn run_seed_sweep() {
    banner("first next_int(0, 1000000) per seed 0..15");
    for seed in 0..16 {
        let mut s = DeterministicStream::new(seed);
        println!("seed={:2} -> {}", seed, s.next_int(0, 1000000));
    }
}

fn main() {
    HwutRunner::new(std::env::args().collect(), "DeterministicStream RNG and SelectionMarker spread", vec![
        ("primitives", run_primitives),
        ("ranges",     run_ranges),
        ("gauss",      run_gauss),
        ("sample",     run_sample),
        ("select",     run_select),
        ("unchosen",   run_unchosen),
        ("seed_sweep", run_seed_sweep),
    ]).exit();
}
