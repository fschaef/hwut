// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: ITERATION OVER ALL COMBINATIONS of the parameters of a basis --
//          the port of 'python/space_iterator.py'. 'r#do(basis)' yields the
//          cartesian product, one element of each dimension per point, the
//          RIGHTMOST dimension changing fastest:
//
//     use hwut::space_iterator;
//     let basis = vec![vec![0, 2, 4], vec![1, 2, 3]];
//     for point in space_iterator::r#do(&basis) {      // [0, 1], [0, 2], ...
//         run_test(point[0], point[1]);
//     }
//
// An EMPTY basis yields exactly one point, the empty one; a basis with an
// empty dimension yields nothing. Where the dimensions hold values of
// different types (Python's lists do), a dimension holds '&dyn Display' or
// an enum of the test's own.
//
// 'do' is a keyword in Rust: the function is written 'r#do', its name kept.
//______________________________________________________________________________

/// The cartesian product of a basis, point by point.
pub struct SpaceIterator<T: Clone> {
    basis:   Vec<Vec<T>>,
    index:   Vec<usize>,
    done_f:  bool,
}

/// RETURN: SpaceIterator over every point of 'basis' -- a Vec of one element
///         per dimension, the rightmost dimension changing fastest.
pub fn r#do<T: Clone>(basis: &[Vec<T>]) -> SpaceIterator<T> {
    let done_f = basis.iter().any(|dimension| dimension.is_empty());
    SpaceIterator { basis: basis.to_vec(), index: vec![0; basis.len()], done_f }
}

impl<T: Clone> Iterator for SpaceIterator<T> {
    type Item = Vec<T>;

    /// RETURN: Some(point), the next point of the product; None once every
    ///         point was given.
    fn next(&mut self) -> Option<Vec<T>> {
        if self.done_f { return None; }
        let point: Vec<T> = self.index.iter().enumerate().map(|(d, i)| self.basis[d][*i].clone()).collect();
        //  THE ODOMETER: the rightmost dimension steps; a carry moves left.
        let mut d = self.index.len();
        loop {
            if d == 0 { self.done_f = true; break; }
            d -= 1;
            self.index[d] += 1;
            if self.index[d] < self.basis[d].len() { break; }
            self.index[d] = 0;
        }
        Some(point)
    }
}
