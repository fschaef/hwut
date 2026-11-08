// @hwut {
//     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
//     build    { framework = "make", target = "%.exe"
//                caps { file_size_mb = 256 } }
//     interactive = true
//     choices {
//         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         random      { features = ["deterministic-stream", "hwut-runner"]
//                       tolerance { constraints = ["mismatches == 0"] } }
//         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
//                       tolerance { constraints = ["overbooked > 0"] } }
//         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
//                       tolerance { constraints = ["overbooked == 0"] } }
//     }
// }
//
// _____________________________________________________________________________
// SUBJECT  the counter of free spaces at a garage's gates: which cars it
//          admits, which it refuses, and how many stand inside.
// REQUIREMENT  The garage admits a car only while a space is free, lets a car
//              out only while one stands inside, and never holds more cars
//              than it has spaces -- also when two gates admit at once.
//
// 'garage.py' of the Python demonstration, in Go; its GOOD files are
// Python's. No choice writes its cases out by hand. Each GENERATES them, with
// one of hwut's helpers for writing tests, in Go
// (hwut/support/test_writing/go):
//
// space        'garage-space.hocon' states the tested space, read by
//              'hwuthocon'; 'spaceiterator.DoOf' walks every combination:
//              3 x 5 x 4 = 60 cases, each one cell of a matrix, checked
//              against the model: admitted = min(arriving, capacity),
//              out = min(leaving, admitted).
// random       'deterministicrandom.New(4711)' draws 1000 cars arriving and
//              leaving at a garage of 5. The draw is the same on every
//              machine and in every language hwut supports -- Python's GOOD
//              holds the Go draw byte for byte.
// race-naive   two gates, one free space, a gate CHECKS and later ADMITS.
//              'deterministictimeline' runs the gates as Triggers on
//              timelines drawn as strings; 'spaceiterator' generates all six
//              interleavings of two two-step gates in four ticks. The law is
//              'overbooked > 0': the GOOD is the accepted violation report.
// race-atomic  the same six interleavings, the gate checking and admitting
//              in ONE step. 'overbooked == 0'.
//
// THE FRONT END is 'hwutrunner': the choice map below is the whole command
// line, '--hwut-info' included. 'interactive = true': hwut starts the
// application ONCE and asks for the choices one after another; the Go
// runner starts each choice as a child of its own -- a choice's output
// equals what it prints when run alone.
// _____________________________________________________________________________

package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"hwut/support/test_writing/go/deterministicrandom"
	"hwut/support/test_writing/go/deterministictimeline"
	"hwut/support/test_writing/go/hwuthocon"
	"hwut/support/test_writing/go/hwutrunner"
	"hwut/support/test_writing/go/pytext"
	"hwut/support/test_writing/go/spaceiterator"
)

// Garage is the unit under test: a counter of the spaces a garage has.
type Garage struct{ capacity, occupied int }

// RETURN: int, the number of spaces free now -- negative where the garage is
// overbooked.
func (self *Garage) free() int { return self.capacity - self.occupied }

// RETURN: true, a car was admitted, if a space was free;
//         false, else (the car is refused).
func (self *Garage) arrive() bool {
	if self.free() <= 0 {
		return false
	}
	self.occupied++
	return true
}

// RETURN: true, a car drove out, if one stood inside;
//         false, else.
func (self *Garage) leave() bool {
	if self.occupied == 0 {
		return false
	}
	self.occupied--
	return true
}

// RETURN: string, the directory the executable stands in -- this test's.
func here() string {
	path, err := os.Executable()
	if err != nil {
		return "."
	}
	return filepath.Dir(path)
}

// _____________________________________________________________________________
// space -- the tested space from HOCON, walked by spaceiterator
//

type dimension struct {
	name      string
	valueList []int
}

// RETURN: []dimension, the dimensions of the space in 'path', in the order
// written: (name, values). Every fault the HOCON reader found is printed
// with '!!' first.
func readSpace(path string) []dimension {
	fh, err := os.Open(path)
	if err != nil {
		fmt.Printf("!! %s\n", err)
		return nil
	}
	defer fh.Close()
	var lineList []hwuthocon.SourceLine
	scanner := bufio.NewScanner(fh)
	for i := 1; scanner.Scan(); i++ {
		lineList = append(lineList, hwuthocon.SourceLine{Text: scanner.Text(), Line: i})
	}
	document, faultList := hwuthocon.Parse(lineList, filepath.Base(path))
	for _, fault := range faultList {
		fmt.Printf("!! %s\n", fault)
	}
	var result []dimension
	for _, entry := range document.Get("space").Node.(*hwuthocon.ObjectNode).EntryList {
		var valueList []int
		for _, item := range entry.Node.(*hwuthocon.ListNode).ItemList {
			valueList = append(valueList, int(item.(*hwuthocon.ScalarNode).Value.(int64)))
		}
		result = append(result, dimension{entry.Key, valueList})
	}
	return result
}

// RETURN: nothing. Prints every case of the space as a matrix cell.
func space() {
	dimensionList := readSpace(filepath.Join(here(), "garage-space.hocon"))
	var basis [][]int
	var headList []string
	for _, d := range dimensionList {
		basis = append(basis, d.valueList)
		headList = append(headList, fmt.Sprintf("%s %s", d.name, pytext.Repr(d.valueList)))
	}
	fmt.Printf("space: %s\n", strings.Join(headList, "  x  "))
	fmt.Println("cell: cars inside / cars refused at the gate ('!!' differs from the model)")
	mismatchN, caseN := 0, 0
	rowDb := map[[2]int][]string{}
	for p := range spaceiterator.DoOf(basis) {
		capacity, arriving, leaving := p[0], p[1], p[2]
		garage, refused := &Garage{capacity: capacity}, 0
		for i := 0; i < arriving; i++ {
			if !garage.arrive() {
				refused++
			}
		}
		for i := 0; i < leaving; i++ {
			garage.leave()
		}
		admitted := min(arriving, capacity)
		expected := [2]int{admitted - min(leaving, admitted), arriving - admitted}
		got := [2]int{garage.occupied, refused}
		mark := "  "
		if got != expected {
			mark = "!!"
			mismatchN++
		}
		key := [2]int{capacity, arriving}
		rowDb[key] = append(rowDb[key], fmt.Sprintf("%d/%d%s", got[0], got[1], mark))
		caseN++
	}
	for _, capacity := range basis[0] {
		var leaveList []string
		for _, l := range basis[2] {
			leaveList = append(leaveList, fmt.Sprintf("leave %-3d", l))
		}
		fmt.Println(strings.TrimRight(fmt.Sprintf("capacity %d   %s", capacity, strings.Join(leaveList, "  ")), " "))
		for _, arriving := range basis[1] {
			var cellList []string
			for _, c := range rowDb[[2]int{capacity, arriving}] {
				cellList = append(cellList, fmt.Sprintf("%-9s", c))
			}
			fmt.Println(strings.TrimRight(fmt.Sprintf("  arrive %d   %s", arriving, strings.Join(cellList, "  ")), " "))
		}
	}
	fmt.Printf("cases %d, differing from the model ((mismatches: %d))\n", caseN, mismatchN)
}

// _____________________________________________________________________________
// random -- a deterministic stream of arrivals and departures
//

// RETURN: nothing. Prints the summary of 1000 drawn cars, model-checked.
func randomStream() {
	stream := deterministicrandom.New(4711)
	garage, model := &Garage{capacity: 5}, 0
	arriveN, refusedN, leaveN, emptyN := 0, 0, 0, 0
	histogram := make([]int, 6)
	mismatchN := 0
	var strip strings.Builder
	for i := 0; i < 1000; i++ {
		if stream.Coin(0.55) {
			arriveN++
			if !garage.arrive() {
				refusedN++
			}
			model = min(5, model+1)
			strip.WriteByte('+')
		} else {
			leaveN++
			if !garage.leave() {
				emptyN++
			}
			model = max(0, model-1)
			strip.WriteByte('-')
		}
		if garage.occupied != model {
			mismatchN++
		}
		histogram[garage.occupied]++
	}
	fmt.Println("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves")
	fmt.Printf("first 60: %s\n", strip.String()[:60])
	fmt.Printf("arrivals %d, refused %d; departures %d, from an empty garage %d\n", arriveN, refusedN, leaveN, emptyN)
	fmt.Println("cars inside after each event:")
	for n, count := range histogram {
		fmt.Printf("    %d  %4d  %s\n", n, count, strings.Repeat("#", count/10))
	}
	fmt.Printf("steps differing from the model ((mismatches: %d))\n", mismatchN)
}

// _____________________________________________________________________________
// race -- two gates on drawn timelines
//

// Gate is a gate on a timeline: its first tick checks, its second admits.
type Gate struct {
	*deterministictimeline.TriggerBase
	garage  *Garage
	atomic  bool
	log     func(string)
	step    int
	sawFree bool
}

// RETURN: nil; the gate's next step is performed at 'pseudoTime'.
func (self *Gate) Fire(task *deterministictimeline.Task, pseudoTime int) error {
	name := self.Name()
	switch {
	case self.step == 0 && self.atomic:
		self.sawFree = self.garage.arrive()
		if self.sawFree {
			self.log(name + " checks+admits")
		} else {
			self.log(name + " refuses")
		}
	case self.step == 0:
		self.sawFree = self.garage.free() > 0
		self.log(fmt.Sprintf("%s sees %d free", name, self.garage.free()))
	case self.atomic:
		if self.sawFree {
			self.log(name + " opens")
		} else {
			self.log(name + " stays shut")
		}
	case self.sawFree:
		self.garage.occupied++ // the naive admit
		self.log(name + " admits")
	default:
		self.log(name + " refuses")
	}
	self.step++
	return nil
}

// RETURN: [][2]string, every pair of timelines in four ticks in which each
// of two gates fires twice, never at the same tick: gate A's and gate B's.
func interleavingList() [][2]string {
	var result [][2]string
	tick := []int{0, 1, 2, 3}
	line := func(x, y int) string {
		var text strings.Builder
		for t := 0; t < 4; t++ {
			if t == x || t == y {
				text.WriteByte('1')
			} else {
				text.WriteByte(' ')
			}
		}
		return text.String()
	}
	for p := range spaceiterator.DoOf([][]int{tick, tick, tick, tick}) {
		a1, a2, b1, b2 := p[0], p[1], p[2], p[3]
		distinct := map[int]bool{a1: true, a2: true, b1: true, b2: true}
		if a1 < a2 && b1 < b2 && len(distinct) == 4 {
			result = append(result, [2]string{line(a1, a2), line(b1, b2)})
		}
	}
	return result
}

// RETURN: nothing. Plays every interleaving of two gates at one space.
func race(atomic bool) {
	fmt.Println("one free space, two gates, one car at each; timelines: a digit fires")
	fmt.Println("    gate A  gate B  what happens                                    inside")
	overbookedN := 0
	for _, pair := range interleavingList() {
		garage, eventList := &Garage{capacity: 1}, []string{}
		log := func(text string) { eventList = append(eventList, text) }
		gateList := []deterministictimeline.Trigger{
			&Gate{TriggerBase: deterministictimeline.NewTriggerBase(pair[0], "A"), garage: garage, atomic: atomic, log: log},
			&Gate{TriggerBase: deterministictimeline.NewTriggerBase(pair[1], "B"), garage: garage, atomic: atomic, log: log},
		}
		deterministictimeline.Run(deterministictimeline.NewTriggerDispatcher(gateList).Run)
		mark := "  "
		if garage.occupied > garage.capacity {
			mark = "!!"
			overbookedN++
		}
		fmt.Println(strings.TrimRight(fmt.Sprintf("    \"%s\"  \"%s\"  %-46s  %d %s", pair[0], pair[1],
			strings.Join(eventList, ", "), garage.occupied, mark), " "))
	}
	fmt.Printf("interleavings overbooking the garage ((overbooked: %d)) of %d\n",
		overbookedN, len(interleavingList()))
}

// RETURN: nothing. The gates check, then admit, in two steps.
func raceNaive() { race(false) }

// RETURN: nothing. The gates check and admit in one step.
func raceAtomic() { race(true) }

// RETURN: nothing; exits with the runner's status.
func main() {
	os.Exit(hwutrunner.New(os.Args, "Demo: a garage's space counter -- a space, a stream and races, generated;",
		map[string]func(){
			"space":       space,
			"random":      randomStream,
			"race-naive":  raceNaive,
			"race-atomic": raceAtomic,
		}).Run())
}
