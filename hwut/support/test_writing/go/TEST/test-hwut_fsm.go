// @hwut {
//     title      = "hwut_fsm: a state machine as the test's model of the system"
//     build      { framework = "make", executable = "%.exe"
//                  caps { file_size_mb = 256 } }
//     choices {
//          syntax    { features = ["go-fsm"] }
//          refused   { features = ["go-fsm"] }
//          dfa       { features = ["go-fsm"] }
//          nfa       { features = ["go-fsm"] }
//          forbidden { features = ["go-fsm"] }
//          model     { features = ["go-fsm"] }
//          report    { features = ["go-fsm"] }
//          masks     { features = ["go-fsm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The Go port of 'python/TEST/test-hwut_fsm.py', choice for choice,
//          held against its GOOD files by '.link'.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
	"strings"

	"hwut/test_writing_support/go/hwutfsm"
	"hwut/test_writing_support/go/hwutrunner"
	"hwut/test_writing_support/go/pytext"
)

// THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released; a
// fault while busy crashes it -- which must never happen.
const PROTOCOL = `
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
`

func banner(label string) { fmt.Printf("\n--- %s ---\n", label) }

// machine returns the model 'text' states; a test's model is meant.
func machine(text string, option ...hwutfsm.Option) *hwutfsm.Machine {
	m, err := hwutfsm.FromString(text, option...)
	if err != nil {
		panic(err)
	}
	return m
}

// state returns where 'm' stands; the test asks a machine of one state.
func state(m *hwutfsm.Machine) string {
	s, err := m.State()
	if err != nil {
		panic(err)
	}
	return s
}

// path returns 'path_to' as Python prints it: a tuple, or None.
func path(eventList []string, found bool) string {
	if !found {
		return "None"
	}
	tuple := make(pytext.Tuple, len(eventList))
	for i, event := range eventList {
		tuple[i] = event
	}
	return pytext.Repr(tuple)
}

func runSyntax() {
	banner("the protocol, written back")
	fmt.Println(machine(PROTOCOL).ToString())
	banner("the author's form: 'state', a chain, ':', blanks around '-->'")
	fmt.Println(machine(`
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    `).ToString())
}

func runRefused() {
	for _, text := range []string{
		"A ---( x )---> B\n: ---( x )---> C",
		"A ---(  )---> B",
		": ---( x )---> B",
		"A B ---( x )---> C",
		"initial: A, B\nA ---( x )---> B",
		"forbidden: Q\nA ---( x )---> B",
		"# nothing but a comment",
	} {
		banner(strings.ReplaceAll(text, "\n", " | "))
		if _, err := hwutfsm.FromString(text); err != nil {
			fmt.Printf("FsmError: %s\n", err)
		} else {
			fmt.Println("accepted")
		}
	}
}

func runDfa() {
	m := machine(PROTOCOL)
	for i, event := range []string{"request", "release", "grant", "release", "jump", "request"} {
		moved := m.Fire(event, i+1)
		fmt.Printf("    %-8s -> %-5s now %-8s allowed: %s\n",
			event, pytext.Bool(moved), state(m), strings.Join(m.Allowed(), ", "))
	}
	banner("questions where it stands")
	fmt.Println("can('grant')  ", pytext.Bool(m.Can("grant")))
	fmt.Println("can('release')", pytext.Bool(m.Can("release")))
	fmt.Println("in_state('waiting')", pytext.Bool(m.InState("waiting")))
	var trace []string
	for _, entry := range m.Trace() {
		trace = append(trace, fmt.Sprintf("%v:%s>%s", entry.Where, entry.Event, entry.Target))
	}
	fmt.Println("trace:", strings.Join(trace, " "))
}

func runNfa() {
	m := machine(`
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    `, hwutfsm.DFA(false))
	for _, event := range []string{"x", "z", "y"} {
		m.Fire(event, "t="+event)
		fmt.Printf("    after %s: %s\n", event, strings.Join(m.Current(), ", "))
	}
	banner("'state' asked of a set")
	m.Reset()
	m.Fire("x", nil)
	if s, err := m.State(); err != nil {
		fmt.Printf("FsmError: %s\n", err)
	} else {
		fmt.Println(s)
	}
}

func runForbidden() {
	m := machine(PROTOCOL)
	for i, event := range []string{"request", "grant", "fault"} {
		fmt.Printf("    %-8s -> %s\n", event, pytext.Bool(m.Fire(event, i+1)))
	}
	fmt.Println("now in", state(m), "-- breaches:", m.BreachN)
}

func runModel() {
	m := machine(PROTOCOL + "\n    state limbo\n    limbo ---( kick )---> idle\n")
	fmt.Println("check:", m.Check(true))
	banner("path_to")
	for _, s := range []string{"busy", "crashed", "limbo", "idle"} {
		fmt.Printf("    %-8s %s\n", s, path(m.PathTo(s, "", true)))
	}
	m.Fire("request", nil)
	fmt.Println("    busy from now:", path(m.PathTo("busy", "now", true)))
	fmt.Println("    state_reachable('idle', start='now'):", pytext.Bool(m.StateReachable("idle", "now", true)))
}

func runReport() {
	m := machine(PROTOCOL, hwutfsm.Name("protocol"))
	for _, event := range []string{"request", "grant", "release", "request", "grant"} {
		m.Fire(event, nil)
	}
	fmt.Println("report returns", m.Report())
}

func runMasks() {
	m := machine(PROTOCOL)
	banner("'grant' disallowed in every state, since line 2")
	m.Disallow("grant", "", 2)
	m.Fire("request", 3)
	fmt.Println("    allowed now:", strings.Join(m.Allowed(), ", "), "-- can('grant'):", pytext.Bool(m.Can("grant")))
	m.Fire("grant", 4)
	fmt.Println("    path_to('busy'):              ", path(m.PathTo("busy", "", true)))
	fmt.Println("    path_to('busy', masked=False):", path(m.PathTo("busy", "", false)))
	fmt.Println("    check():", m.Check(true))
	fmt.Println("    check(masked=False):", m.Check(false))
	banner("allowed again; 'busy' forbidden while standing in it")
	m.Allow("grant", "")
	m.Fire("grant", 6)
	m.Forbid("busy", 7)
	m.Fire("release", 8)
	m.Fire("request", 9)
	m.Fire("grant", 10)
	banner("permitted: 'busy', and the model's own 'crashed'")
	m.Permit("busy", 11)
	m.Permit("crashed", 12)
	fmt.Println("    fault ->", pytext.Bool(m.Fire("fault", 13)), "-- now in", state(m))
	banner("a phase: 'release' disallowed in 'busy' for a block")
	m.Reset()
	m.Fire("request", nil)
	m.Fire("grant", nil)
	m.Disallowed("release", "busy", "phase", func() {
		m.Fire("release", 20)
	})
	m.Fire("release", 21)
	m.Disallow("cancel", "", 22)
	m.Report()
	banner("refused: a word the model never names")
	for _, call := range []func() error{
		func() error { return m.Disallow("jump", "", nil) },
		func() error { return m.Forbid("limbo", nil) },
		func() error { return m.Allow("grant", "nowhere") },
	} {
		if err := call(); err != nil {
			fmt.Printf("FsmError: %s\n", err)
		}
	}
}

func main() {
	os.Exit(hwutrunner.New(os.Args, "hwut_fsm: a state machine as the test's model of the system", map[string]func(){
		"syntax":    runSyntax,
		"refused":   runRefused,
		"dfa":       runDfa,
		"nfa":       runNfa,
		"forbidden": runForbidden,
		"model":     runModel,
		"report":    runReport,
		"masks":     runMasks,
	}).Run())
}
