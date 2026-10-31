// @hwut {
//     title      = "HOCON parser: subset (A), annotated tree"
//     build      { framework = "make", executable = "%.exe"
//                  caps { file_size_mb = 256 } }
//     choices {
//          comments  { features = ["go-hocon"] }
//          faults    { features = ["go-hocon"] }
//          fuzz      { features = ["go-hocon"] }
//          numbers   { features = ["go-hocon"] }
//          oneline   { features = ["go-hocon"] }
//          positions { features = ["go-hocon"] }
//          quoting   { features = ["go-hocon"] }
//          refused   { features = ["go-hocon"] }
//          scalars   { features = ["go-hocon"] }
//          structure { features = ["go-hocon"] }
//          triple    { features = ["go-hocon"] }
//          unclosed  { features = ["go-hocon"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The Go port of 'python/TEST/test-hwut_hocon.py', choice for choice,
//          held against its GOOD files by '.link'. The fuzz draws the
//          deterministic stream exactly as Python does: the same 3000 mutated
//          headers, the same counts.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	dr "hwut/test_writing_support/go/deterministicrandom"
	"hwut/test_writing_support/go/hwuthocon"
	"hwut/test_writing_support/go/hwutrunner"
	"hwut/test_writing_support/go/pytext"
)

func banner(label string) { fmt.Printf("\n--- %s ---\n", label) }

// lines splits 'text' into SourceLines, offsets applied uniformly.
func lines(text string, lineOffset, columnOffset int) []hwuthocon.SourceLine {
	var result []hwuthocon.SourceLine
	for i, line := range strings.Split(text, "\n") {
		result = append(result, hwuthocon.SourceLine{Text: line, Line: i + 1 + lineOffset, ColumnOffset: columnOffset})
	}
	return result
}

// show prints the annotated tree, positions included.
func show(node hwuthocon.Node, indent int) {
	pad := strings.Repeat("    ", indent)
	switch n := node.(type) {
	case *hwuthocon.ObjectNode:
		fmt.Printf("%s{ at %s\n", pad, n.Position)
		for _, entry := range n.EntryList {
			fmt.Printf("%s  key '%s' at %s ->\n", pad, entry.Key, entry.KeyPosition)
			show(entry.Node, indent+1)
		}
		fmt.Printf("%s}\n", pad)
	case *hwuthocon.ListNode:
		fmt.Printf("%s[ at %s\n", pad, n.Position)
		for _, item := range n.ItemList {
			show(item, indent+1)
		}
		fmt.Printf("%s]\n", pad)
	case *hwuthocon.ScalarNode:
		fmt.Printf("%s%s (%s) at %s\n", pad, pytext.Repr(n.Value), pytext.TypeName(n.Value), n.Position)
	}
}

// run parses 'text' and prints tree and faults.
func run(label, text string, offset ...int) {
	lineOffset, columnOffset := 0, 0
	if len(offset) == 2 {
		lineOffset, columnOffset = offset[0], offset[1]
	}
	banner(label)
	document, faultList := hwuthocon.Parse(lines(text, lineOffset, columnOffset), "f.hocon")
	show(document, 0)
	for _, fault := range faultList {
		fmt.Printf("FAULT %s\n", fault)
	}
}

func testScalars() {
	run("scalars",
		"a = bare\n"+
			"b = \"quoted \\\"x\\\" and \\n\"\n"+
			"c = 42\n"+
			"d = -3.14\n"+
			"e = 1e-6\n"+
			"f = true\n"+
			"g = no\n"+
			"h = make %.exe\n"+
			"i: \"colon-bound\"\n"+
			"j = null\n"+
			"k = nihil\n"+
			"l =\n")
}

func testNumbers() {
	run("decimal, with sign and exponent", "a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n")
	run("the visual helper enters no value", "a = 1_000\nb = 7_000.5_5\n")
	run("hexadecimal, binary, octal", "a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n")
	run("roman", "a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n")
	run("a sign standing apart from its digits", "a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n")
	run("what spells no number is a string, and carries quotes",
		"a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n")
	run("no arithmetic: this language computes nothing", "a = 5 - 1\n")
}

func testQuoting() {
	run("quoted: blanks, comment markers and binders are content",
		"a = \"make %.exe\"\nb = \"not # a comment\"\nc = \"x = y\"\nd = \"yes\"\n")
	run("unquoted: refused, and shown in the quotes it wants",
		"a = make\nb = strip.pype\nc = [one, two]\nd = 1\n")
}

func testStructure() {
	run("nesting and key-brace",
		"outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n")
	run("lists",
		"commas   = [one, two, three]\n"+
			"newlines = [\n"+
			"    1\n"+
			"    2\n"+
			"]\n"+
			"objects  = [ { a = 1 }, { a = 2 } ]\n"+
			"empty    = []\n")
}

func testOneline() {
	run("two entries, one line, no comma", "caps { timeout_sec = 30  network = false }\n")
	run("a quoted value with blanks, beside a following key", "a { build = \"make %.exe\"  timeout_sec = 5 }\n")
	run("three entries, one line", "x { a = 1  b = \"two\"  c = { d = 3 } }\n")
}

func testComments() {
	run("comments",
		"# whole line\n"+
			"a = 1   # trailing\n"+
			"// slashes too\n"+
			"b = 2   // trailing slashes\n"+
			"c = bare value # comment cut\n")
}

func testRefused() {
	run("refused, each by name",
		"include \"other.conf\"\n"+
			"a = ${outside.value}\n"+
			"b += appended\n"+
			"d = survives\n")
}

func testTriple() {
	q := `"""`
	run("several lines: indentation and blank ends go",
		fmt.Sprintf("doc = %s\n"+
			"    First line.\n"+
			"\n"+
			"      indented more\n"+
			"    last line\n"+
			"    %s\n"+
			"after = 1\n", q, q))
	run("on one line; beside another entry; in a list",
		fmt.Sprintf("a = %sone line%s  b = 2\nc = [%sx%s, \"y\"]\n", q, q, q, q))
	run("as written: a quote, a backslash-n, a comment marker",
		fmt.Sprintf("a = %ssays \"no\" \\n # not a comment%s\n", q, q))
	run("never closed: a fault, at its beginning",
		fmt.Sprintf("a = 1\nb = %sopen\nc = 2\n", q))
}

func testFaults() {
	run("faults accumulate", "a = 1\na = 2\nb = \"unterminated\n}\nc {\n    d = 3\n")
}

func testUnclosed() {
	run("a list closed by the object's brace", "@hwut { title = \"B\" choices = [ }\nafter = 1\n")
	run("a stray character in a list", "a = [1, ; 2]\n")
}

var FUZZ_SEED_TUPLE = []string{
	"@hwut {\n" +
		"    title    = \"T\"\n" +
		"    choices  = [\"a\", \"b\"]\n" +
		"    tolerance { eq_pattern = [\"x.*\"] }\n" +
		"    n        = -1.5e3\n" +
		"    f        = true\n" +
		"}\n",
	"hwut {\n" +
		"    target     { clean = \"./c.sh\" }\n" +
		"    dependency { \"a.py\" = [\"b.py one\"] }\n" +
		"    ignore     = [\"x\"]   // comment\n" +
		"    # comment\n" +
		"}\n",
}

// WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few that
// it refuses by name, and some ordinary ones.
var FUZZ_ALPHABET = append(strings.Split("{}[]\",=:#/\\$ \n\t-+.eE0a", ""), `"""`, "${", "//", "+=")

const FUZZ_INPUT_N = 3000
const FUZZ_BOUND = 500 * time.Millisecond // one parse takes well under a millisecond

// mutated returns 'text' edited by one to four random insertions, deletions
// and duplications of a short stretch -- the stream drawn as Python draws it.
func mutated(stream *dr.DeterministicStream, text string) string {
	t := []rune(text)
	for n := stream.NextInt(1, 4); n > 0; n-- {
		i := stream.NextInt(0, len(t))
		switch stream.NextInt(0, 2) {
		case 0:
			t = append(append(append([]rune{}, t[:i]...), []rune(dr.Select(stream, FUZZ_ALPHABET))...), t[i:]...)
		case 1:
			t = append(append([]rune{}, t[:i]...), t[min(i+1, len(t)):]...)
		default:
			j := stream.NextInt(0, len(t))
			t = append(append(append([]rune{}, t[:i]...), t[j:min(j+5, len(t))]...), t[i:]...)
		}
	}
	return string(t)
}

// parseBounded parses 'text' on a goroutine of its own: "clean" or "with
// faults" where it ended within FUZZ_BOUND, "hang" where it did not (the
// goroutine is abandoned), "exception" with the panic's text where it
// panicked.
func parseBounded(text string) (string, string) {
	type verdict struct{ kind, what string }
	done := make(chan verdict, 1)
	go func() {
		defer func() {
			if failure := recover(); failure != nil {
				done <- verdict{"exception", fmt.Sprintf("panic: %v", failure)}
			}
		}()
		_, faultList := hwuthocon.Parse(lines(text, 0, 0), "f.hocon")
		if len(faultList) != 0 {
			done <- verdict{"with faults", ""}
		} else {
			done <- verdict{"clean", ""}
		}
	}()
	select {
	case v := <-done:
		return v.kind, v.what
	case <-time.After(FUZZ_BOUND):
		return "hang", ""
	}
}

func testFuzz() {
	stream := dr.New(4711)
	keyList := []string{"clean", "with faults", "hang", "exception"}
	tally := map[string]int{}
	var exampleKeyList []string
	example := map[string]string{}
	for k := 0; k < FUZZ_INPUT_N; k++ {
		text := mutated(stream, dr.Select(stream, FUZZ_SEED_TUPLE))
		kind, what := parseBounded(text)
		tally[kind]++
		if _, found := example[kind]; !found && (kind == "hang" || kind == "exception") {
			exampleKeyList = append(exampleKeyList, kind)
			if kind == "exception" {
				text = what + "\n" + text
			}
			example[kind] = text
		}
	}
	banner(fmt.Sprintf("%d mutated headers", FUZZ_INPUT_N))
	for _, key := range keyList {
		fmt.Printf("    %-12s %d\n", key, tally[key])
	}
	for _, key := range exampleKeyList {
		fmt.Printf("FIRST %s:\n%s\n", strings.ToUpper(key), example[key])
	}
}

func testPositions() {
	text := "@hwut {\n    title = \"T\"\n}"
	run("plain: as its own file", text)
	run("offset: same text, region begins at line 40, 3 columns stripped", text, 39, 3)
}

func main() {
	os.Exit(hwutrunner.New(os.Args, "HOCON parser: subset (A), annotated tree;", map[string]func(){
		"scalars":   testScalars,
		"numbers":   testNumbers,
		"quoting":   testQuoting,
		"structure": testStructure,
		"oneline":   testOneline,
		"comments":  testComments,
		"refused":   testRefused,
		"triple":    testTriple,
		"unclosed":  testUnclosed,
		"fuzz":      testFuzz,
		"faults":    testFaults,
		"positions": testPositions,
	}).Run())
}
