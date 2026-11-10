// @hwut {
//     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
//     build   { framework = "make", target = "%.exe"
//               caps { file_size_mb = 256 } }
//     pype    = "build.pypes"
//     same    = true
//     choices = ["serial", "parallel"]
//     features = ["demo-go+cover-pype-in-header", "demo-go+cover-pype-system", "demo-go+cover-same-nominal", "demo-go+cover-choices-as-list",
//                 "demo-go+cover-pype-push-pop", "demo-go+cover-pype-entry-exit", "demo-go+cover-pype-import", "demo-go+cover-pype-repeat-group",
//                 "demo-go+cover-pype-quantity", "demo-go+cover-pype-anchors-globs-flush"]
//     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
// }
//
// _____________________________________________________________________________
// SUBJECT  the log of a recursive build -- configure, then the directories
//          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
//          a pype system makes of it.
// REQUIREMENT  A parallel build builds what the serial build builds: the same
//              sources, the same warnings, the same archives and the same
//              program, linked from the same parts.
//
// 'build.py' of the Python demonstration, in Go; the pype system and the GOOD
// file are Python's. The application only REPORTS the build as it happens,
// as 'make -w' would. The header's 'pype = "build.pypes"' puts a SYSTEM of
// two pype scripts between it and the comparison:
//
//     build.pypes       --> normalise.pype --> build.pype
//     normalise.pype    a parallel build tags each line with its job,
//                       'job2: cc -c ...'; the tag goes
//     build.pype        the summary, sorted -- modes pushed and popped over
//                       nested directories, '<entry>'/'<exit>', a vocabulary
//                       imported from 'compiler.pype', a repeat group,
//                       durations read as quantities
//
// 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.go.txt' -- a link
// to Python's 'build.py.txt'. 'choices' is a list.
//
// The laws: the compile times sum to under 5 s ('((compile: ...))'), and
// nothing in the log broke the build's grammar ('((breaches: 0))').
// _____________________________________________________________________________

package main

import (
	"fmt"
	"math/rand/v2"
	"os"
	"sync"
	"time"
)

type directory struct {
	sourceList []string
	warningDb  map[string]string
	product    string
}

// What each directory does: its sources, warnings and products.
var directoryDb = map[string]directory{
	"lib": {[]string{"lib/str.c", "lib/num.c", "lib/map.c"},
		map[string]string{"lib/num.c": "lib/num.c:14:9: warning: unused variable 'n'"},
		"ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o"},
	"app/plugins": {[]string{"app/plugins/png.c", "app/plugins/svg.c"},
		map[string]string{"app/plugins/svg.c": "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"},
		"ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o"},
	"app": {[]string{"app/main.c", "app/cli.c"},
		map[string]string{},
		"ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a"},
}

// RETURN: []string, what building directory 'name' prints, its sources
// compiled in the time each takes.
func compileLines(name string) []string {
	spec, lineList := directoryDb[name], []string{}
	for _, source := range spec.sourceList {
		took := 0.04 + 0.08*rand.Float64()
		time.Sleep(time.Duration(took * float64(time.Second)))
		spent := fmt.Sprintf("%.2f s", took)
		if took < 0.1 {
			spent = fmt.Sprintf("%d ms", int(took*1000))
		}
		object := source[:len(source)-2] + ".o"
		lineList = append(lineList, fmt.Sprintf("cc -c %s -o %s (took %s)", source, object, spent))
		if warning, ok := spec.warningDb[source]; ok {
			lineList = append(lineList, warning)
		}
	}
	return lineList
}

// RETURN: []string, the block 'make -w' prints for 'name' at 'level', the
// block of 'inner' nested before the product ("" for none).
func directoryBlock(name string, level int, inner string) []string {
	lineList := []string{fmt.Sprintf("make[%d]: Entering directory '%s'", level, name)}
	lineList = append(lineList, compileLines(name)...)
	if inner != "" {
		lineList = append(lineList, directoryBlock(inner, level+1, "")...)
	}
	lineList = append(lineList, directoryDb[name].product)
	return append(lineList, fmt.Sprintf("make[%d]: Leaving directory '%s'", level, name))
}

// RETURN: nothing. Prints what 'configure' prints, and that make enters the
// top directory.
func configure() {
	fmt.Println("configure: checking for cc... cc")
	fmt.Println("configure: checking for ar... ar")
	fmt.Println("make: Entering directory 'demo'")
}

// RETURN: nothing. Builds one directory after the other.
func serial() {
	configure()
	for _, line := range append(directoryBlock("lib", 1, ""), directoryBlock("app", 1, "app/plugins")...) {
		fmt.Println(line)
	}
	fmt.Println("make: Leaving directory 'demo'")
}

// RETURN: nothing. Builds 'lib' and 'app' at once. Each job prints its block
// whole when done ('make -O'), every line tagged with the job; which job
// finishes first is the scheduler's.
func parallel() {
	configure()
	var lock sync.Mutex
	var group sync.WaitGroup
	job := func(slot int, name, inner string) {
		defer group.Done()
		block := directoryBlock(name, 1, inner)
		lock.Lock()
		defer lock.Unlock()
		for _, line := range block {
			fmt.Printf("job%d: %s\n", slot, line)
		}
	}
	group.Add(2)
	go job(1, "lib", "")
	go job(2, "app", "app/plugins")
	group.Wait()
	fmt.Println("make: Leaving directory 'demo'")
}

// RETURN: nothing; the choice named is run -- else the choices are named
// and the exit status is 1.
func main() {
	choice := ""
	if len(os.Args) > 1 {
		choice = os.Args[1]
	}
	switch choice {
	case "serial":
		serial()
	case "parallel":
		parallel()
	default:
		fmt.Println("choices: serial, parallel")
		os.Exit(1)
	}
}
