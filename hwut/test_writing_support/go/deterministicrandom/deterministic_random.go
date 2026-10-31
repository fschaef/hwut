// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package deterministicrandom is A RANDOM STREAM THAT IS THE SAME EVERYWHERE
// -- the port of 'python/deterministic_random.py'. The same seed gives the
// same numbers as the Python module, draw for draw: Park-Miller MINSTD,
// 'state = 48271 * state mod (2^31 - 1)'.
//
//	s := deterministicrandom.New(0x42)
//	s.NextInt(0, 9)        s.NextFloat()         s.Coin(0.5)
//	s.Gauss(0, 1)          s.Gauss(0, 1, -1, 1)  s.GaussInt(100, 15)
//	s.SampleIndices(10, 3)
//	deterministicrandom.Select(s, pool)          deterministicrandom.Choice(s, pool)
//	deterministicrandom.Sample(s, pool, 4)
//
//	m := deterministicrandom.NewSelectionMarker()
//	deterministicrandom.SelectUnchosen(s, pool, m)
//
// A METHOD OF GO HAS NO TYPE PARAMETER: what draws from a slice of any
// element type -- Python's 'select', 'choice', 'sample', 'select_unchosen'
// -- is a function of the package taking the stream first.
//
// IDENTITY, AS IN PYTHON: a marker remembers a candidate by the candidate
// itself (it is 'comparable'): a pointer by its address -- what 'id()' is in
// Python -- a string or a number by its value, as two equal short strings
// are one object in Python.
//
// 'Gauss' is the one path through 'math' (log, cos, sqrt): a last bit may
// differ from Python's libm, so a GOOD that prints a draw tolerates the last
// digits.
// _____________________________________________________________________________
package deterministicrandom

import "math"

// SelectionMarker remembers which candidates were chosen at one selection
// site; caller-owned, one per site.
type SelectionMarker struct {
	chosen map[any]struct{}
}

// NewSelectionMarker
//
// RETURN: *SelectionMarker, with nothing chosen yet.
func NewSelectionMarker() *SelectionMarker {
	return &SelectionMarker{chosen: map[any]struct{}{}}
}

// Reset
//
// RETURN: nothing; every chosen candidate is forgotten -- the next cycle
// restarts.
func (self *SelectionMarker) Reset() { clear(self.chosen) }

// SeenF
//
// RETURN: bool, true where 'candidate' was chosen since the last reset.
func (self *SelectionMarker) SeenF(candidate any) bool {
	_, found := self.chosen[candidate]
	return found
}

// DeterministicStream is the generator; its State is all there is of it.
type DeterministicStream struct {
	State int64
}

// New
//
// RETURN: *DeterministicStream, standing at 'seed' (its low 31 bits).
func New(seed int64) *DeterministicStream {
	return &DeterministicStream{State: seed & 0x7FFFFFFF}
}

// NextInt
//
// RETURN: int, uniform in [vMin, vMax]; the state steps even where the range
// is one value (then 'vMin' is returned).
func (self *DeterministicStream) NextInt(vMin, vMax int) int {
	self.State = (48271 * self.State) % 2147483647
	if vMin == vMax {
		return vMin
	}
	return vMin + int(self.State%int64(vMax-vMin+1))
}

// NextFloat
//
// RETURN: float64 in [0, 1): 'NextInt(0, 1000000) / 1000001'.
func (self *DeterministicStream) NextFloat() float64 {
	return float64(self.NextInt(0, 1000000)) / 1000001.0
}

// Coin
//
// RETURN: bool, true with 'probabilityOfTrue', false else. THE FLOOR (TW-1):
// the probability is resolved in steps of 1/1000001.
func (self *DeterministicStream) Coin(probabilityOfTrue float64) bool {
	return self.NextFloat() < probabilityOfTrue
}

// Gauss
//
// RETURN: float64, a draw of the normal distribution (mu, sigma) by the
// Box-Muller transform, clipped to [lower, upper] -- 'bound' is Python's
// optional 'lower, upper': none, the lower alone, or both; -inf and +inf
// where not given.
func (self *DeterministicStream) Gauss(mu, sigma float64, bound ...float64) float64 {
	lower, upper := math.Inf(-1), math.Inf(1)
	if len(bound) > 0 {
		lower = bound[0]
	}
	if len(bound) > 1 {
		upper = bound[1]
	}
	u1 := self.NextFloat() + 1e-9 // avoid log(0)
	u2 := self.NextFloat()
	z0 := math.Sqrt(-2.0*math.Log(u1)) * math.Cos(2.0*math.Pi*u2)
	result := z0*sigma + mu
	switch {
	case result < lower:
		return lower
	case result > upper:
		return upper
	}
	return result
}

// GaussInt
//
// RETURN: int, 'Gauss(mu, sigma, bound...)' rounded to the nearest integer,
// a half to the even one -- as Python's 'round'.
func (self *DeterministicStream) GaussInt(mu, sigma float64, bound ...float64) int {
	return int(math.RoundToEven(self.Gauss(mu, sigma, bound...)))
}

// SampleIndices
//
// RETURN: []int, 'k' distinct indices of 0 .. populationSize-1, drawn by
// Fisher-Yates, if success; panics, else -- 'k' > 'populationSize'.
func (self *DeterministicStream) SampleIndices(populationSize, k int) []int {
	if k > populationSize {
		panic("deterministicrandom: sample larger than the population")
	}
	index := make([]int, populationSize)
	for i := range index {
		index[i] = i
	}
	result := make([]int, 0, k)
	for i := 0; i < k; i++ {
		j := self.NextInt(i, populationSize-1)
		index[i], index[j] = index[j], index[i]
		result = append(result, index[i])
	}
	return result
}

// Select
//
// RETURN: T, a candidate of 'candidates' uniformly drawn by 's' -- the same
// stream state and the same candidates give the same one.
func Select[T any](s *DeterministicStream, candidates []T) T {
	return candidates[s.NextInt(0, len(candidates)-1)]
}

// Choice
//
// RETURN: T, an element of 'seq' uniformly drawn by 's' (as 'Select').
func Choice[T any](s *DeterministicStream, seq []T) T {
	return seq[s.NextInt(0, len(seq)-1)]
}

// Sample
//
// RETURN: []T, 'n' elements of 'population' at distinct places, in the
// order 'SampleIndices' draws them.
func Sample[T any](s *DeterministicStream, population []T, n int) []T {
	result := make([]T, 0, n)
	for _, i := range s.SampleIndices(len(population), n) {
		result = append(result, population[i])
	}
	return result
}

// SelectUnchosen
//
// RETURN: T, a candidate 'marker' has not seen, uniformly drawn among those
// and recorded in 'marker'; where every candidate was seen, the marker is
// reset and the draw is over all of them.
func SelectUnchosen[T comparable](s *DeterministicStream, candidates []T, marker *SelectionMarker) T {
	unchosen := make([]T, 0, len(candidates))
	for _, candidate := range candidates {
		if !marker.SeenF(candidate) {
			unchosen = append(unchosen, candidate)
		}
	}
	if len(unchosen) == 0 {
		marker.Reset()
		unchosen = append(unchosen, candidates...)
	}
	choice := unchosen[s.NextInt(0, len(unchosen)-1)]
	marker.chosen[choice] = struct{}{}
	return choice
}
