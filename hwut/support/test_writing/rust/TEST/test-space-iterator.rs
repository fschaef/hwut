// @hwut {
//     title      = "space_iterator: every combination of a parameter basis"
//     build      { framework = "make", executable = "%.exe" }
//     choices {
//         product { features = ["rust-space"] }
//         edges   { features = ["rust-space"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: The Rust port of 'python/TEST/test-space-iterator.py', held
//          against its GOOD files by '.link'. Python's dimensions mix ints
//          and strs; here a dimension holds '&dyn Display'.
//______________________________________________________________________________
use std::fmt::Display;

use hwut::hwut_runner::HwutRunner;
use hwut::space_iterator;

fn banner(label: &str) { println!("\n--- {} ---", label); }

/// Every point of 'basis', one per line, then the count.
fn points(basis: &[Vec<&dyn Display>]) {
    let mut n = 0;
    for point in space_iterator::r#do(basis) {
        println!("  ({})", point.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(", "));
        n += 1;
    }
    println!("  {} point(s)", n);
}

fn run_product() {
    banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points");
    points(&[vec![&0, &2, &4], vec![&"otto", &"heinz"], vec![&1, &2]]);
}

fn run_edges() {
    banner("an EMPTY basis -- one point, the empty one");
    points(&[]);
    banner("a basis with an EMPTY dimension -- nothing");
    points(&[vec![&1, &2], vec![], vec![&3]]);
    banner("ONE dimension -- its values one by one");
    points(&[vec![&"a", &"b", &"c"]]);
}

fn main() {
    HwutRunner::new(std::env::args().collect(), "space_iterator: every combination of a parameter basis", vec![
        ("product", run_product),
        ("edges",   run_edges),
    ]).exit();
}
