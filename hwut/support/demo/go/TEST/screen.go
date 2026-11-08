// @hwut {
//     title     = "Demo: a terminal program's screen, as a person sees it"
//     build     { framework = "make", target = "%.exe"
//                 caps { file_size_mb = 256 } }
//     tolerance { regions    = false
//                 comment    = false
//                 whitespace = false }
//     choices {
//         open   { features = ["terminal-screen", "screen-as-seen"] }
//         scroll { features = ["terminal-screen", "screen-as-seen"] }
//     }
// }
//
// _____________________________________________________________________________
// SUBJECT  the screen of 'viewer.exe' ('viewer.go'), a full-screen file
//          viewer, run in a terminal of 9 rows and 40 columns and driven by
//          its keys.
// REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
//              as they fit, and a status line -- the keys flush left, the
//              lines shown flush right; 'j' and the down key go one line
//              further, 'k' one back.
//
// 'screen.py' of the Python demonstration, in Go. 'hwutvterm's Terminal runs
// the viewer on a pseudo-terminal: the viewer cannot tell it from a real one.
// The test PRESSES KEYS and is told what CHANGED: three regions are declared
// -- title, body, status -- and after every key, once the viewer has gone
// quiet, each region whose text changed is printed.
//
// THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
// off, in the header: 'regions = false' (the file shown is a GOOD file of
// hwut, its '##! potpourri' is characters here), 'comment = false' ('## ...'
// lines are characters too), 'whitespace = false' (every blank between the
// status line's two halves counts).
//
// libvterm must be installed ('apt install libvterm0'); where it is not, the
// test prints why and probes nothing -- its output differs from GOOD and the
// reason stands in the difference.
//
// CHOICES  open    the viewer opened, then quit.
//          scroll  down, down, 'j', then 'k': three lines on, one back.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"hwut/support/test_writing/go/hwutvterm"
)

const SAMPLE = `## demo.go race -- three workers
start
##! potpourri
worker B done: 5 jobs
worker A done: 3 jobs
worker C done: 2 jobs
####
all joined
## the order between the markers is
## free; the lines are not.
`

// RETURN: string, the directory the executable stands in -- this test's.
func here() string {
	path, err := os.Executable()
	if err != nil {
		return "."
	}
	return filepath.Dir(path)
}

// RETURN: nothing. Prints one region that changed, its rows as they stand on
// the screen, from the first column.
func show(name string, lineList []string) {
	fmt.Printf("-- %s\n", name)
	for _, line := range lineList {
		fmt.Println(line)
	}
}

// RETURN: nil, the viewer run on the sample, 'keyList' pressed, quit, and
// what changed after each step printed, if success;
// the error of the terminal, else -- 'LibraryMissing' where libvterm is not
// found.
func view(keyList []string) error {
	path := filepath.Join(here(), "TMP", "race.txt")
	os.MkdirAll(filepath.Dir(path), 0o755)
	if err := os.WriteFile(path, []byte(SAMPLE), 0o644); err != nil {
		return err
	}
	terminal, err := hwutvterm.NewTerminal(9, 40, 100*time.Millisecond)
	if err != nil {
		return err
	}
	defer terminal.Close()
	terminal.Region("title", 0, 1, 0, -1)
	terminal.Region("body", 1, 7, 0, -1)
	terminal.Region("status", -1, 1, 0, -1)
	terminal.OnChange(show)
	fmt.Println("> viewer.exe race.txt")
	if _, err := terminal.Run([]string{filepath.Join(here(), "viewer.exe"), path}, nil, "", 10*time.Second); err != nil {
		return err
	}
	cell, err := terminal.Cell(0, 1)
	if err != nil {
		return err
	}
	attribute := cell.AttributeText()
	if attribute == "" {
		attribute = "plain"
	}
	fmt.Printf("title bar: %s\n", attribute)
	for _, key := range keyList {
		fmt.Printf("> %s\n", key)
		if len(key) == 1 {
			terminal.Send(key, time.Second)
		} else if _, err := terminal.Press(key, nil, time.Second); err != nil {
			return err
		}
	}
	terminal.Send("q", time.Second)
	status, _, err := terminal.Wait(10 * time.Second)
	if err != nil {
		return err
	}
	fmt.Printf("> q -- exit status %d\n", status)
	return nil
}

var choiceDb = map[string][]string{
	"open":   {},
	"scroll": {"down", "down", "j", "k"},
}

// RETURN: nothing; the choice named is viewed and '<hwut-end>' printed --
// else the choices or the terminal's error are printed and the exit status
// is 1.
func main() {
	choice := ""
	if len(os.Args) > 1 {
		choice = os.Args[1]
	}
	keyList, ok := choiceDb[choice]
	if !ok {
		fmt.Println("choices: open, scroll")
		os.Exit(1)
	}
	if err := view(keyList); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	fmt.Println("<hwut-end>")
}
