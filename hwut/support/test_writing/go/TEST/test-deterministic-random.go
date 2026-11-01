// @hwut {
//     title      = "DeterministicStream RNG and SelectionMarker spread"
//     build      { framework = "make", executable = "%.exe"
//                  caps { file_size_mb = 256 } }
//     choices {
//          gauss      { features = ["go-random"] }
//          primitives { features = ["go-random"] }
//          ranges     { features = ["go-random"] }
//          sample     { features = ["go-random"] }
//          seed_sweep { features = ["go-random"] }
//          select     { features = ["go-random"] }
//          unchosen   { features = ["go-random"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The Go port of 'python/TEST/test-deterministic-random.py', choice
//          for choice, held against its GOOD files by '.link'.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
	"strings"

	dr "hwut/test_writing_support/go/deterministicrandom"
	"hwut/test_writing_support/go/hwutrunner"
	"hwut/test_writing_support/go/pytext"
)

const SEED = 0x42

// THE ONE PLACE THE LIBM PATH IS TOLERATED (see the Python test).
const TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}"
const REGION_END = "####"

func banner(label string) { fmt.Printf("\n--- %s ---\n", label) }

// joinedDraws returns the n draws of 'draw', separated by blanks.
func joinedDraws(n int, draw func() string) string {
	text := make([]string, n)
	for i := range text {
		text[i] = draw()
	}
	return strings.Join(text, " ")
}

func runPrimitives() {
	banner("next_int(0, 1000000) -- first 20")
	s := dr.New(SEED)
	for i := 0; i < 20; i++ {
		fmt.Printf("[%02d] %d\n", i, s.NextInt(0, 1000000))
	}
	banner("next_float -- first 10 (full precision)")
	s = dr.New(SEED)
	for i := 0; i < 10; i++ {
		fmt.Printf("[%02d] %s\n", i, pytext.FloatRepr(s.NextFloat()))
	}
	banner("coin(0.5) -- 40 draws")
	s = dr.New(SEED)
	fmt.Println(joinedDraws(40, func() string {
		if s.Coin(0.5) {
			return "T"
		}
		return "F"
	}))
}

func runRanges() {
	banner("next_int(0, 9) -- 30 draws")
	s := dr.New(SEED)
	fmt.Println(joinedDraws(30, func() string { return fmt.Sprint(s.NextInt(0, 9)) }))
	banner("next_int(5, 5) -- degenerate range returns the bound")
	s = dr.New(SEED)
	fmt.Println(joinedDraws(5, func() string { return fmt.Sprint(s.NextInt(5, 5)) }))
	banner("next_int(-3, 3) -- spanning zero")
	s = dr.New(SEED)
	fmt.Println(joinedDraws(20, func() string { return fmt.Sprintf("%+d", s.NextInt(-3, 3)) }))
}

func runGauss() {
	banner("gauss(0, 1) -- 10 draws (full precision)")
	s := dr.New(SEED)
	fmt.Println(TOLERANCE_REGION_BEGIN)
	for i := 0; i < 10; i++ {
		fmt.Printf("[%02d] %s\n", i, pytext.FloatRepr(s.Gauss(0.0, 1.0)))
	}
	fmt.Println(REGION_END)
	banner("gauss(0, 1) clamped to [-1, 1]")
	s = dr.New(SEED)
	fmt.Println(TOLERANCE_REGION_BEGIN)
	for i := 0; i < 10; i++ {
		fmt.Printf("[%02d] %s\n", i, pytext.FloatRepr(s.Gauss(0.0, 1.0, -1.0, 1.0)))
	}
	fmt.Println(REGION_END)
	banner("gauss_int(100, 15) -- 20 draws")
	s = dr.New(SEED)
	fmt.Println(joinedDraws(20, func() string { return fmt.Sprint(s.GaussInt(100.0, 15.0)) }))
}

func runSample() {
	banner("sample_indices(10, 10) -- full permutation")
	s := dr.New(SEED)
	fmt.Println(pytext.Repr(s.SampleIndices(10, 10)))
	banner("sample_indices(20, 5) -- partial draw")
	s = dr.New(SEED)
	fmt.Println(pytext.Repr(s.SampleIndices(20, 5)))
	banner("choice from a list -- 20 draws")
	s = dr.New(SEED)
	pool := []string{"alpha", "beta", "gamma", "delta", "epsilon"}
	fmt.Println(joinedDraws(20, func() string { return dr.Choice(s, pool) }))
	banner("sample(list, 4) -- unique elements")
	s = dr.New(SEED)
	fmt.Println(pytext.Repr(dr.Sample(s, strings.Split("ABCDEFGH", ""), 4)))
}

func runSelect() {
	banner("select over a list -- 20 draws")
	s := dr.New(SEED)
	pool := []string{"a", "b", "c", "d"}
	fmt.Println(joinedDraws(20, func() string { return dr.Select(s, pool) }))
	banner("select over a tuple -- 12 draws")
	s = dr.New(SEED)
	branches := [...]string{"p", "q", "r"}
	fmt.Println(joinedDraws(12, func() string { return dr.Select(s, branches[:]) }))
}

func runUnchosen() {
	banner("stable pool -- three full cycles of 4 elements")
	s := dr.New(SEED)
	pool := []string{"a", "b", "c", "d"}
	m := dr.NewSelectionMarker()
	fmt.Println(joinedDraws(12, func() string { return dr.SelectUnchosen(s, pool, m) }))

	banner("FRESH container each call -- identical to the stable pool above")
	s = dr.New(SEED)
	m = dr.NewSelectionMarker()
	fmt.Println(joinedDraws(12, func() string {
		fresh := []string{"a", "b", "c", "d"} // a new slice every call
		return dr.SelectUnchosen(s, fresh, m)
	}))

	banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]")
	s = dr.New(SEED)
	m = dr.NewSelectionMarker()
	full := []string{"a", "b", "c", "d"}
	sub := []string{"a", "b"}
	first := dr.SelectUnchosen(s, sub, m)
	rest := joinedDraws(3, func() string { return dr.SelectUnchosen(s, full, m) })
	fmt.Println("first(from sub):", first, " then(from full):", rest)

	banner("reset() restarts the cycle")
	s = dr.New(SEED)
	m = dr.NewSelectionMarker()
	before := joinedDraws(4, func() string { return dr.SelectUnchosen(s, pool, m) })
	m.Reset()
	after := joinedDraws(4, func() string { return dr.SelectUnchosen(s, pool, m) })
	fmt.Println("before reset:", before)
	fmt.Println("after  reset:", after)
}

func runSeedSweep() {
	banner("first next_int(0, 1000000) per seed 0..15")
	for seed := 0; seed < 16; seed++ {
		s := dr.New(int64(seed))
		fmt.Printf("seed=%2d -> %d\n", seed, s.NextInt(0, 1000000))
	}
}

func main() {
	os.Exit(hwutrunner.New(os.Args, "DeterministicStream RNG and SelectionMarker spread", map[string]func(){
		"primitives": runPrimitives,
		"ranges":     runRanges,
		"gauss":      runGauss,
		"sample":     runSample,
		"select":     runSelect,
		"unchosen":   runUnchosen,
		"seed_sweep": runSeedSweep,
	}).Run())
}
