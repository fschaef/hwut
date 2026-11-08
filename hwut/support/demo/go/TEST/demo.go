// @hwut {
//     title   = "Demo: what hwut tolerates, and where it is said"
//     build   { framework = "make", target = "%.exe"
//               caps { file_size_mb = 256 } }
//     choices {
//         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
//         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
//                       tolerance {
//                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
//                           numeric_ratio = 0.01
//                       } }
//         constraints { features = ["demo-passes-on-every-run", "constraints"]
//                       tolerance {
//                           constraints = ["load >= 0 and load <= 100",
//                                          "even % 2 == 0",
//                                          "twice == 2 * once"]
//                       } }
//         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
//         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
//         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
//         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
//                       tolerance { nothing = ["[.]+"] } }
//         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
//                       tolerance { analogy = ["{", "}"] } }
//         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
//     }
// }
//
// _____________________________________________________________________________
// A TEST APPLICATION OF HWUT, FOR READING -- 'demo.py' of the Python
// demonstration, in Go, choice for choice; its GOOD files are Python's.
//
//     hwut.run                   builds 'demo.exe' (the Makefile), runs every
//                                choice below, compares with GOOD/
//     hwut.play demo.go plain    runs one choice and records it in OUT/
//     hwut.accept demo.go plain  blesses that recording as GOOD
//     hwut.config.show demo.go   prints what hwut READ from the header above
//
// The header above is the whole configuration: a title, how the program is
// built ('build': make, 'demo.exe'), and one scope per choice. hwut calls
// 'demo.exe <choice>' and compares what it prints on stdout with
// 'GOOD/demo.go--<choice>.txt' -- a '.link' to Python's text.
//
// Every run is seeded by the clock, so the output differs from run to run --
// and every choice passes anyway. What each shows is said in '../../python/
// TEST/demo.py', word for word the same:
//
//     plain        nothing varies, nothing is tolerated
//     tolerance    'eq_pattern' and 'numeric_ratio'
//     constraints  '((name: value))' judged by laws, not by GOOD's value
//     race         '##! potpourri': lines in any order
//     analogies    '((x))' handles, consistent throughout
//     pool         '##! potpourri subset duplicates'
//     progress     'nothing': lines that count as none
//     lisp         'analogy' markers of one's own
//     clusters     '##! point-cloud limit=0.3 pair dist=Linf'
//
// The 'build' scope's 'file_size_mb': on a cold cache Go writes its runtime's
// archive, above the default cap of 10 MB per file (services E-212).
// _____________________________________________________________________________

package main

import (
	"fmt"
	"math"
	"math/rand/v2"
	"os"
	"strings"
	"sync"
	"time"
)

var greetingList = []string{"hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj"}

// RETURN: float64, drawn uniformly from [low, high].
func uniform(low, high float64) float64 {
	return low + (high-low)*rand.Float64()
}

// RETURN: int, drawn uniformly from [low, high], both included.
func randint(low, high int) int {
	return low + rand.IntN(high-low+1)
}

// RETURN: nothing. Prints what never varies.
func plain() {
	fmt.Println("the first line")
	fmt.Println("the second line: 1 2 3")
}

// RETURN: nothing. Prints a greeting and a value, both drawn at random.
func tolerance() {
	fmt.Printf("greeting: %s, world\n", greetingList[rand.IntN(len(greetingList))])
	fmt.Printf("value:    %.2f\n", uniform(19.91, 20.09))
}

// RETURN: nothing. Prints bindings, each drawn at random, each lawful.
func constraints() {
	fmt.Printf("load  ((load: %.1f)) %%\n", uniform(0.0, 100.0))
	fmt.Printf("even  ((even: %d))\n", 2*randint(0, 500))
	once := randint(1, 50)
	fmt.Printf("once  ((once: %d))\n", once)
	fmt.Printf("twice ((twice: %d))\n", 2*once)
}

// RETURN: (int, int), two different numbers drawn from [low, high).
func twoDifferent(low, high int64) (int64, int64) {
	first := low + rand.Int64N(high-low)
	for {
		second := low + rand.Int64N(high-low)
		if second != first {
			return first, second
		}
	}
}

// RETURN: nothing. Prints two handles, each drawn at random, each used
// consistently from opening to closing.
func analogies() {
	first, second := twoDifferent(0x1000, 0x10000)
	fmt.Printf("open  ((%04x)) input.txt\n", first)
	fmt.Printf("open  ((%04x)) output.txt\n", second)
	fmt.Printf("read  ((%04x)) 17 lines\n", first)
	fmt.Printf("write ((%04x)) 17 lines\n", second)
	fmt.Printf("close ((%04x))\n", first)
	fmt.Printf("close ((%04x))\n", second)
}

// RETURN: nothing. Three workers print as they finish; the order is the
// scheduler's, the facts are not. The program frames the unordered block
// itself: '##! potpourri' ... '####'.
func race() {
	var lock sync.Mutex
	var group sync.WaitGroup
	work := func(name string, jobs int) {
		defer group.Done()
		time.Sleep(time.Duration(uniform(0.0, 0.02) * float64(time.Second)))
		lock.Lock()
		defer lock.Unlock()
		fmt.Printf("worker %s done: %d jobs\n", name, jobs)
	}
	fmt.Println("start")
	fmt.Println("##! potpourri")
	group.Add(3)
	go work("A", 3)
	go work("B", 5)
	go work("C", 2)
	group.Wait()
	fmt.Println("####")
	fmt.Println("all joined")
}

// RETURN: nothing. Four workers take twelve jobs from one queue; each
// reports the job it finished. Who takes how many is the scheduler's.
func pool() {
	jobQueue := make(chan int, 12)
	for job := 0; job < 12; job++ {
		jobQueue <- job
	}
	close(jobQueue)
	var lock sync.Mutex
	var group sync.WaitGroup
	var doneList []string
	work := func(name string) {
		defer group.Done()
		for range jobQueue {
			time.Sleep(time.Duration(uniform(0.0, 0.005) * float64(time.Second)))
			lock.Lock()
			doneList = append(doneList, "job done by worker "+name)
			lock.Unlock()
		}
	}
	for _, name := range []string{"A", "B", "C", "D"} {
		group.Add(1)
		go work(name)
	}
	group.Wait()
	fmt.Println("twelve jobs, four workers:")
	fmt.Println("##! potpourri subset duplicates")
	for _, line := range doneList {
		fmt.Println(line)
	}
	fmt.Println("####")
	fmt.Printf("jobs done: %d\n", len(doneList))
}

// RETURN: nothing. A download that prints dots while it waits; how many is
// the network's.
func progress() {
	fmt.Println("connecting to mirror")
	for n := randint(0, 3); n > 0; n-- {
		fmt.Println(strings.Repeat(".", randint(1, 8)))
	}
	fmt.Println("connected")
	fmt.Println("received 1024 bytes")
}

// RETURN: nothing. A Lisp session at its prompt: two objects, each printed
// with its address '{...}', drawn anew per run, and each used again.
func lisp() {
	table, thread := twoDifferent(0x1000000000, 0x1100000000)
	fmt.Println("* (defvar *cache* (make-hash-table))")
	fmt.Printf("#<HASH-TABLE :TEST EQL :COUNT 0 {%X}>\n", table)
	fmt.Println("* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))")
	fmt.Printf("#<THREAD \"worker\" RUNNING {%X}>\n", thread)
	fmt.Println("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))")
	fmt.Printf("#<THREAD \"worker\" RUNNING {%X}>\n", thread)
	fmt.Println("* *cache*")
	fmt.Printf("#<HASH-TABLE :TEST EQL :COUNT 1 {%X}>\n", table)
}

type point struct{ x, y float64 }

// RETURN: float64, the square of the distance between 'p' and 'q'.
func distance2(p, q point) float64 {
	return (p.x-q.x)*(p.x-q.x) + (p.y-q.y)*(p.y-q.y)
}

// RETURN: nothing. Clusters 90 noisy points around three centres and prints
// the centroids in the order the run found them.
func clusters() {
	centreList := []point{{1.0, 1.0}, {5.0, 4.0}, {9.0, 1.0}}
	var pointList []point
	for _, c := range centreList {
		for i := 0; i < 30; i++ {
			pointList = append(pointList, point{c.x + rand.NormFloat64()*0.3, c.y + rand.NormFloat64()*0.3})
		}
	}
	rand.Shuffle(len(pointList), func(i, j int) { pointList[i], pointList[j] = pointList[j], pointList[i] })
	// The start: one point at random, then twice the point farthest from
	// every start chosen so far -- one start per cluster.
	centroidList := []point{pointList[rand.IntN(len(pointList))]}
	for len(centroidList) < 3 {
		best, bestD := pointList[0], -1.0
		for _, p := range pointList {
			d := math.Inf(1)
			for _, c := range centroidList {
				d = math.Min(d, distance2(p, c))
			}
			if d > bestD {
				best, bestD = p, d
			}
		}
		centroidList = append(centroidList, best)
	}
	for round := 0; round < 10; round++ {
		memberList := make([][]point, 3)
		for _, p := range pointList {
			nearest := 0
			for i := 1; i < 3; i++ {
				if distance2(p, centroidList[i]) < distance2(p, centroidList[nearest]) {
					nearest = i
				}
			}
			memberList[nearest] = append(memberList[nearest], p)
		}
		for i, m := range memberList {
			var sx, sy float64
			for _, p := range m {
				sx, sy = sx+p.x, sy+p.y
			}
			centroidList[i] = point{sx / float64(len(m)), sy / float64(len(m))}
		}
	}
	fmt.Println("centroids (x y), in the order found:")
	fmt.Println("##! point-cloud limit=0.3 pair dist=Linf")
	for _, c := range centroidList {
		fmt.Printf("    %5.2f %5.2f\n", c.x, c.y)
	}
	fmt.Println("####")
}

var choiceList = []struct {
	name     string
	function func()
}{
	{"plain", plain},
	{"tolerance", tolerance},
	{"constraints", constraints},
	{"analogies", analogies},
	{"race", race},
	{"pool", pool},
	{"progress", progress},
	{"lisp", lisp},
	{"clusters", clusters},
}

// RETURN: nothing; the choice named on the command line is run and
// '<hwut-end>' printed -- else the choices are named and the exit status
// is 1.
func main() {
	choice := ""
	if len(os.Args) > 1 {
		choice = os.Args[1]
	}
	var nameList []string
	for _, entry := range choiceList {
		if entry.name == choice {
			entry.function()
			fmt.Println("<hwut-end>")
			return
		}
		nameList = append(nameList, entry.name)
	}
	fmt.Printf("choices: %s\n", strings.Join(nameList, ", "))
	os.Exit(1)
}
