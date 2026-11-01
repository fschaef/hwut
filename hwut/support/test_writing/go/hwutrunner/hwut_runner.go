// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package hwutrunner is the FRONT END OF A HWUT TEST APPLICATION IN GO -- the
// port of 'python/hwut_runner.py': the same modes, the same words.
//
//	app --hwut-info      the info block; exit 0.
//	app <choice>         one choice; test output on stdout and stderr,
//	                     '<hwut-end>' after it. '-' runs a choice-less test.
//	app --interactive    choices started over stdin, output into two named
//	                     sink files per choice, 'done' on the original stdout.
//	app                  the choice-less test; where the application has
//	                     choices, refused, naming them.
//
// USAGE:
//
//	func main() {
//	    os.Exit(hwutrunner.New(os.Args, "What this tests", map[string]func(){
//	        "plain":  runPlain,
//	        "tricky": runTricky,
//	    }).Run())
//	}
//
// A choice-less test names its one function hwutrunner.NoChoice ("-").
// Before 'Run' a test may set 'Happy' (patterns), 'Same' and 'Parallel'
// (interactive: choices run concurrently) -- Python's 'happy', 'same_f',
// 'parallel="process"'.
//
// THE INTERACTIVE PROTOCOL is Python's, line for line:
//
//	DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
//	UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
//
// EVERY CHOICE RUNS IN A CHILD PROCESS of its own -- the application started
// again on that one choice, its stdout and stderr the two sinks: a choice
// that calls 'os.Exit' or panics ends that choice, not the session -- what
// Python gets by catching SystemExit -- and no choice inherits another's
// state. Go has no 'fork'; starting the own executable again is its way.
// _____________________________________________________________________________
package hwutrunner

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
)

// NoChoice is the name of the one function of a choice-less application --
// Python's key 'None', listed as '-'.
const NoChoice = "-"

// sinkVariable marks the child of interactive mode: it runs the choice
// argv[1] names, its stdout and stderr being the sinks, and writes
// '<hwut-end>' unless HWUT_NO_TERMINAL is set.
const sinkVariable = "HWUT_GO_RUNNER_SINK"

// HwutRunner is the front end; 'New' makes one, 'Run' runs it.
type HwutRunner struct {
	Argv      []string
	Title     string
	ChoiceMap map[string]func()
	Happy     []string // patterns of the info block's 'HAPPY:' lines
	Same      bool     // the info block carries 'SAME;'
	Parallel  bool     // interactive mode: one child per choice, concurrently

	sortedChoiceList []string
	control          *os.File   // UP channel: the original stdout
	controlLock      sync.Mutex // one UP line at a time
	pending          sync.WaitGroup
}

// New
//
// RETURN: *HwutRunner, ready for 'Run', if success; panics, else -- an empty
// 'choiceMap', or one that holds NoChoice beside other choices (an
// application has choices or has none, not both).
//
// 'argv' is the command line ('os.Args'), 'title' the info block's title
// line, 'choiceMap' maps a choice's name to its test function.
func New(argv []string, title string, choiceMap map[string]func()) *HwutRunner {
	if len(choiceMap) == 0 {
		panic("hwutrunner.New: no choice")
	}
	if _, noneFound := choiceMap[NoChoice]; noneFound && len(choiceMap) != 1 {
		panic("hwutrunner.New: the choice-less function stands beside choices")
	}
	sorted := make([]string, 0, len(choiceMap))
	for name := range choiceMap {
		sorted = append(sorted, name)
	}
	sort.Strings(sorted)
	return &HwutRunner{Argv: argv, Title: title, ChoiceMap: choiceMap, sortedChoiceList: sorted}
}

// noneF
//
// RETURN: bool, true where the application is choice-less (NoChoice its one
// function).
func (self *HwutRunner) noneF() bool {
	_, found := self.ChoiceMap[NoChoice]
	return found
}

// Run
//
// RETURN: int, the exit status of the mode the command line selects -- 0
// where the info block was printed, a choice ran, or an interactive session
// ended; 1 where a choice is missing or names none of the application's.
// The caller hands it to 'os.Exit'.
func (self *HwutRunner) Run() int {
	word, givenF := "", len(self.Argv) > 1
	if givenF {
		word = self.Argv[1]
	}
	if os.Getenv(sinkVariable) != "" {
		os.Unsetenv(sinkVariable)
		return self.modeSink(word)
	}
	switch {
	case givenF && (word == "-h" || word == "--hi" || word == "--hwut-info" || word == "--sos" || word == "--wtf"):
		for _, line := range self.infoBlockLines() {
			fmt.Println(line)
		}
		return 0
	case givenF && word == "--interactive":
		return self.modeInteractive()
	case !givenF:
		if self.noneF() {
			return self.runOne(NoChoice)
		}
		fmt.Printf("error: a choice is required: %s -- name one, or let 'hwut.play' ask.\n",
			strings.Join(self.sortedChoiceList, ", "))
		return 1
	}
	if _, found := self.ChoiceMap[word]; found {
		return self.runOne(word)
	}
	if self.noneF() {
		fmt.Printf("error: '%s': this application has no choices -- call it without one.\n", word)
		return 1
	}
	fmt.Printf("error: choice '%s' not available.\n", word)
	fmt.Printf("error: available: %s.\n", strings.Join(self.sortedChoiceList, ", "))
	if best, found := LevenshteinBestMatch(word, self.sortedChoiceList); found {
		fmt.Printf("error: did you mean '%s'?\n", best)
	}
	return 1
}

// runOne
//
// RETURN: int, 0 -- the choice 'name' ran, then '<hwut-end>' was printed
// (R-70: the stream testifies its own completeness).
func (self *HwutRunner) runOne(name string) int {
	self.ChoiceMap[name]()
	fmt.Println("<hwut-end>")
	return 0
}

// modeSink
//
// RETURN: int, 0 -- the child of interactive mode ran the choice 'name'
// into the sinks its stdout and stderr are, then '<hwut-end>' unless
// HWUT_NO_TERMINAL is set (a canonicaliser owns stdout and writes it).
func (self *HwutRunner) modeSink(name string) int {
	self.ChoiceMap[name]()
	if os.Getenv("HWUT_NO_TERMINAL") == "" {
		fmt.Println("<hwut-end>")
	}
	return 0
}

// infoBlockLines
//
// RETURN: []string, the lines of the info block: the title (with its ';'),
// 'CHOICES: ...;' where the application has choices, a 'HAPPY: ...;' per
// pattern, 'SAME;' where set, 'INTERACTIVE;'.
func (self *HwutRunner) infoBlockLines() []string {
	title := self.Title
	if !strings.HasSuffix(title, ";") {
		title += ";"
	}
	result := []string{title}
	if !self.noneF() {
		result = append(result, "CHOICES: "+strings.Join(self.sortedChoiceList, ", ")+";")
	}
	for _, pattern := range self.Happy {
		result = append(result, "HAPPY: "+pattern+";")
	}
	if self.Same {
		result = append(result, "SAME;")
	}
	return append(result, "INTERACTIVE;")
}

// ------------------------------------------------------------ interactive mode

// up
//
// RETURN: nothing; 'message' and a newline are written on the UP channel,
// one message at a time.
func (self *HwutRunner) up(message string) {
	self.controlLock.Lock()
	defer self.controlLock.Unlock()
	self.control.WriteString(message + "\n")
}

// modeInteractive
//
// RETURN: int, 0, once the session ended ('quit' or the end of stdin) and
// every choice started was reported 'done'; 'bye' is the last UP line.
// The original stdout is the UP channel; fd 1 and fd 2 point at a stray
// sink, so output outside a running choice never enters the protocol.
func (self *HwutRunner) modeInteractive() int {
	controlFd, err := syscall.Dup(1)
	if err != nil {
		return 1
	}
	self.control = os.NewFile(uintptr(controlFd), "control")
	if stray, err := os.CreateTemp("", "hwut_stray_*.txt"); err == nil {
		syscall.Dup3(int(stray.Fd()), 1, 0)
		syscall.Dup3(int(stray.Fd()), 2, 0)
		stray.Close()
	}
	reader := bufio.NewReader(os.Stdin)
	for {
		line, err := reader.ReadString('\n')
		if line = strings.TrimSpace(line); line != "" {
			if !self.interprete(line) {
				break
			}
		}
		if err != nil {
			break
		}
	}
	self.pending.Wait()
	self.up("bye")
	return 0
}

// interprete
//
// RETURN: bool, true where the session goes on, false where it ends. One
// DOWN command is executed and answered on the UP channel.
func (self *HwutRunner) interprete(line string) bool {
	field := strings.Fields(line)
	switch {
	case len(field) == 1 && (field[0] == "quit" || field[0] == "q" || field[0] == "exit"):
		return false
	case len(field) == 1 && field[0] == "info":
		for _, infoLine := range self.infoBlockLines() {
			self.up("info: " + infoLine)
		}
		self.up("done - 0")
	case len(field) == 4 && field[0] == "run":
		token := field[1]
		name, found := self.findChoice(token)
		if !found {
			self.up(fmt.Sprintf("fail %s unknown-choice", token))
		} else if self.Parallel {
			self.pending.Add(1)
			go func() {
				defer self.pending.Done()
				self.up(fmt.Sprintf("done %s %d", token, self.runIntoSinks(name, field[2], field[3])))
			}()
		} else {
			self.up(fmt.Sprintf("done %s %d", token, self.runIntoSinks(name, field[2], field[3])))
		}
	default:
		self.up("fail - bad-command")
	}
	return true
}

// findChoice
//
// RETURN: (string, true), the name of the choice 'token' names -- by its
// name, by its decimal index into the sorted choice list, or '-' for the
// choice-less test; ("", false), else.
func (self *HwutRunner) findChoice(token string) (string, bool) {
	if token == NoChoice {
		return NoChoice, self.noneF()
	}
	if _, found := self.ChoiceMap[token]; found {
		return token, true
	}
	if index, err := strconv.Atoi(token); err == nil && strings.Trim(token, "0123456789") == "" {
		if index < len(self.sortedChoiceList) {
			return self.sortedChoiceList[index], true
		}
	}
	return "", false
}

// runIntoSinks
//
// RETURN: int, the exit status of the child that ran the choice 'name' with
// its stdout and stderr in the files 'sinkOut' and 'sinkErr' -- 0 where the
// choice returned; the status it exited with; minus the signal that ended
// it; 1 where no sink could be opened or no child started. Upon return the
// child has ended: its sinks are complete and closed (the 'done' barrier).
func (self *HwutRunner) runIntoSinks(name, sinkOut, sinkErr string) int {
	out, err := os.OpenFile(sinkOut, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o644)
	if err != nil {
		return 1
	}
	defer out.Close()
	errOut, err := os.OpenFile(sinkErr, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o644)
	if err != nil {
		return 1
	}
	defer errOut.Close()
	executable, err := os.Executable()
	if err != nil {
		return 1
	}
	child := exec.Command(executable, name)
	child.Stdout, child.Stderr = out, errOut
	child.Env = append(os.Environ(), sinkVariable+"=1")
	err = child.Run()
	if child.ProcessState == nil {
		return 1
	}
	if status, ok := child.ProcessState.Sys().(syscall.WaitStatus); ok && status.Signaled() {
		return -int(status.Signal())
	}
	var exitError *exec.ExitError
	if err != nil && !errors.As(err, &exitError) {
		return 1
	}
	return child.ProcessState.ExitCode()
}

// ------------------------------------------------------------ the suggestion

// LevenshteinDistance
//
// RETURN: int >= 0, the Levenshtein distance between 'a' and 'b', counted
// in characters (runes).
func LevenshteinDistance(a, b string) int {
	ra, rb := []rune(a), []rune(b)
	switch {
	case a == b:
		return 0
	case len(ra) == 0:
		return len(rb)
	case len(rb) == 0:
		return len(ra)
	}
	if len(ra) < len(rb) {
		ra, rb = rb, ra
	}
	prev := make([]int, len(rb)+1)
	for j := range prev {
		prev[j] = j
	}
	for i, ca := range ra {
		cur := make([]int, len(rb)+1)
		cur[0] = i + 1
		for j, cb := range rb {
			substitution := prev[j]
			if ca != cb {
				substitution++
			}
			cur[j+1] = min(cur[j]+1, prev[j+1]+1, substitution)
		}
		prev = cur
	}
	return prev[len(rb)]
}

// LevenshteinBestMatch
//
// RETURN: (string, true), the element of 'haystack' least distant from
// 'needle' -- the first of equally distant ones; ("", false), where
// 'haystack' is empty.
func LevenshteinBestMatch(needle string, haystack []string) (string, bool) {
	if len(haystack) == 0 {
		return "", false
	}
	best, bestDistance := "", -1
	for _, key := range haystack {
		if key == needle {
			return needle, true
		}
	}
	for _, key := range haystack {
		if distance := LevenshteinDistance(needle, key); bestDistance < 0 || distance < bestDistance {
			best, bestDistance = key, distance
		}
	}
	return best, true
}
