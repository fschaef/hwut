// @hwut {
//     title      = "space_iterator: every combination of a parameter basis"
//     build      { framework = "make", executable = "%.exe"
//                  caps { file_size_mb = 256 } }
//     choices {
//          product { features = ["go-space"] }
//          edges   { features = ["go-space"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The Go port of 'python/TEST/test-space-iterator.py', choice for
//          choice, held against its GOOD files by '.link'.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
	"strings"

	"hwut/test_writing_support/go/hwutrunner"
	"hwut/test_writing_support/go/pytext"
	"hwut/test_writing_support/go/spaceiterator"
)

func banner(label string) { fmt.Printf("\n--- %s ---\n", label) }

// points prints every point of 'basis', one per line, then the count.
func points(basis [][]any) {
	n := 0
	for point := range spaceiterator.Do(basis) {
		text := make([]string, len(point))
		for i, value := range point {
			text[i] = pytext.Str(value)
		}
		fmt.Printf("  (%s)\n", strings.Join(text, ", "))
		n++
	}
	fmt.Printf("  %d point(s)\n", n)
}

func runProduct() {
	banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points")
	points([][]any{{0, 2, 4}, {"otto", "heinz"}, {1, 2}})
}

func runEdges() {
	banner("an EMPTY basis -- one point, the empty one")
	points([][]any{})
	banner("a basis with an EMPTY dimension -- nothing")
	points([][]any{{1, 2}, {}, {3}})
	banner("ONE dimension -- its values one by one")
	points([][]any{{"a", "b", "c"}})
}

func main() {
	os.Exit(hwutrunner.New(os.Args, "space_iterator: every combination of a parameter basis", map[string]func(){
		"product": runProduct,
		"edges":   runEdges,
	}).Run())
}
