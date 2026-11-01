// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package spaceiterator yields EVERY COMBINATION OF A PARAMETER BASIS -- the
// port of 'python/space_iterator.py': the cartesian product, the RIGHTMOST
// dimension changing fastest.
//
//	basis := [][]any{{0, 2, 4}, {"otto", "heinz"}, {1, 2}}
//	for point := range spaceiterator.Do(basis) {
//	    runTest(point[0].(int), point[1].(string), point[2].(int))
//	}
//
// yields (0, otto, 1), (0, otto, 2), (0, heinz, 1), ... An empty basis yields
// exactly one point, the empty one; a basis with an empty dimension yields
// nothing -- as 'itertools.product'. 'DoOf' is the same for a basis whose
// dimensions share one element type.
// _____________________________________________________________________________
package spaceiterator

import "iter"

// Do
//
// RETURN: iter.Seq[[]any], every point of the cartesian product of 'basis'
// -- one element of each dimension, in the basis's order -- the rightmost
// dimension changing fastest; one empty point for an empty basis, none
// where a dimension is empty. Each point is a slice of its own.
func Do(basis [][]any) iter.Seq[[]any] { return DoOf(basis) }

// DoOf
//
// RETURN: iter.Seq[[]T], as 'Do', for dimensions of one element type T.
func DoOf[T any](basis [][]T) iter.Seq[[]T] {
	return func(yield func([]T) bool) {
		for _, dimension := range basis {
			if len(dimension) == 0 {
				return
			}
		}
		index := make([]int, len(basis))
		for {
			point := make([]T, len(basis))
			for i, dimension := range basis {
				point[i] = dimension[index[i]]
			}
			if !yield(point) {
				return
			}
			i := len(basis) - 1
			for ; i >= 0; i-- {
				if index[i]++; index[i] < len(basis[i]) {
					break
				}
				index[i] = 0
			}
			if i < 0 {
				return
			}
		}
	}
}
