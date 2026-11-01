// @hwut {
//     title   = "Demo: a door's state machine, watched by a pype"
//     build   { framework = "make", executable = "%.exe"
//               caps { file_size_mb = 256 } }
//     pype    = "door.pype"
//     choices {
//         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
//         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
//     }
// }
//
// _____________________________________________________________________________
// A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
// may do. 'door.py' of the Python demonstration, in Go; GOOD files Python's.
//
// The application prints its log as it happens: noise, and a line 'door:
// <event>' for each thing the door does. It prints no '<hwut-end>': the
// header names 'door.pype', which stands between it and the comparison and
// closes the stream at '<eof>'.
//
// 'door.pype' parses the log and fires every event into a state machine. A
// pype script's actions are Python -- the pype is hwut's face, whatever
// language the application is written in -- so the script takes Python's
// 'hwut_fsm'; a Go test that holds the model itself takes 'hwutfsm' of the Go
// support, the same machine (its GOOD files are the Python module's).
//
//     closed ---( open )---> open ---( close )---> closed
//     closed ---( lock )---> locked ---( unlock )---> closed
//     open   ---( slam )---> jammed          # forbidden
//
// kept     the door does what the model allows; the report shows which
//          transitions were taken and which not, and 'ended in closed'.
// broken   the controller locks an open door, slams it into a jam and tries
//          to unlock it: each surprise is ONE 'BREACH' line in the output,
//          the jam included, and the end outside the final states is one
//          more. The GOOD file holds them.
//
// Both choices pass on every run: what they print does not depend on time.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
)

var storyDb = map[string][]string{
	"kept":   {"open", "close", "lock", "unlock", "open", "close"},
	"broken": {"open", "lock", "slam", "unlock"},
}

// RETURN: int, 0 -- the log of the door for 'choice', printed.
func run(choice string) int {
	fmt.Println("controller 2.1 up")
	for i, event := range storyDb[choice] {
		fmt.Printf("tick %d: sensors read\n", i+1)
		fmt.Printf("door: %s\n", event)
	}
	fmt.Println("controller down")
	return 0
}

// RETURN: nothing; exits 0 with the log of the choice named, else 1 with
// the choices named.
func main() {
	if len(os.Args) != 2 || storyDb[os.Args[1]] == nil {
		fmt.Println("error: a choice is required: broken, kept")
		os.Exit(1)
	}
	os.Exit(run(os.Args[1]))
}
