// @hwut {
//     title      = "A terminal's screen read by a test: libvterm through cgo."
//     build      { framework = "make", executable = "%.exe"
//                  caps { file_size_mb = 256 } }
//     choices {
//          attributes { features = ["go-vterm"] }
//          colours    { features = ["go-vterm"] }
//          events     { features = ["go-vterm"] }
//          keys       { features = ["go-vterm"] }
//          missing    { features = ["go-vterm"] }
//          regions    { features = ["go-vterm"] }
//          screen     { features = ["go-vterm"] }
//          text       { features = ["go-vterm"] }
//          unnoticed  { features = ["go-vterm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The Go port of 'python/TEST/test-hwut_vterm.py', choice for choice,
//          held against its GOOD files by '.link'. WANTS libvterm -- found at
//          run time, no header needed to build. The two APPLICATIONS a Terminal
//          runs here are the Python test's, unchanged: they are the system
//          under test, and what they print is in the shared GOOD files.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	"hwut/test_writing_support/go/hwutrunner"
	"hwut/test_writing_support/go/hwutvterm"
	"hwut/test_writing_support/go/pytext"
)

const ESC = "\x1b"

// shown prints every row that holds something, framed, then the cursor.
func shown(screen *hwutvterm.Screen) {
	for row, line := range screen.LineList() {
		if line != "" {
			fmt.Printf("    %d |%s|\n", row, line)
		}
	}
	row, column := screen.Cursor()
	fmt.Printf("    cursor (%d, %d)\n", row, column)
}

// missing prints the one line and says true where the library was not
// found ('err').
func missing(err error) bool {
	if err == nil {
		return false
	}
	fmt.Printf("NOT PROBED: %s\n", err)
	return true
}

// cell is what stands at that place of 'screen' -- a place the test knows
// to be on it.
func cell(screen *hwutvterm.Screen, row, column int) hwutvterm.Cell {
	c, err := screen.Cell(row, column)
	if err != nil {
		panic(err)
	}
	return c
}

// noneOr is the attribute text, or '(none)'.
func noneOr(text string) string {
	if text == "" {
		return "(none)"
	}
	return text
}

func runText() {
	s, err := hwutvterm.NewScreen(4, 12)
	if missing(err) {
		return
	}
	fmt.Println("-- plain, then carriage return and line feed")
	s.FeedString("hello\r\nworld")
	shown(s)
	s.Close()

	s, _ = hwutvterm.NewScreen(4, 12)
	fmt.Println("-- UTF-8: two bytes, one cell; a wide character, two")
	s.FeedString("ä日x")
	shown(s)
	for column := 0; column < 4; column++ {
		c := cell(s, 0, column)
		fmt.Printf("    column %d: %-6s width %d\n", column, pytext.StrRepr(c.Text), c.Width)
	}
	s.Close()

	s, _ = hwutvterm.NewScreen(3, 5)
	fmt.Println("-- seven characters on five columns: the line wraps")
	s.FeedString("abcdefg")
	shown(s)
	s.Close()

	s, _ = hwutvterm.NewScreen(2, 4)
	fmt.Println("-- a str is sent as UTF-8; the bytes taken are counted")
	fmt.Printf("    taken: %d\n", s.FeedString("aä"))
	fmt.Println("-- a place off the screen")
	if _, err := s.Cell(2, 0); err != nil {
		fmt.Printf("    %s: %s\n", err.(*hwutvterm.VtermError).Kind, err)
	}
	s.Close()
}

func runScreen() {
	s, err := hwutvterm.NewScreen(5, 20)
	if missing(err) {
		return
	}
	defer s.Close()
	fmt.Println("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'")
	s.FeedString("first line\r\nsecond line\r\nthird line")
	s.FeedString(ESC + "[2;4H" + "X")
	shown(s)
	fmt.Println("-- erase to the end of that line")
	s.FeedString(ESC + "[K")
	shown(s)
	fmt.Println("-- clear the screen, home, one word")
	s.FeedString(ESC + "[2J" + ESC + "[H" + "clean")
	shown(s)
}

func runAttributes() {
	s, err := hwutvterm.NewScreen(3, 20)
	if missing(err) {
		return
	}
	defer s.Close()
	for _, attribute := range hwutvterm.ATTRIBUTE_SGR_LIST {
		s.FeedString(fmt.Sprintf("%s[%sm%c%s[0m", ESC, attribute.Sgr, attribute.Name[0], ESC))
	}
	fmt.Println("-- one cell per attribute, set by its own code")
	for column, attribute := range hwutvterm.ATTRIBUTE_SGR_LIST {
		c := cell(s, 0, column)
		//  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
		said := noneOr(c.AttributeText())
		if attribute.Name == "conceal" {
			said = "conceal, or (none) on libvterm 0.1"
		}
		fmt.Printf("    %s  %s\n", pytext.StrRepr(c.Text), said)
	}
	fmt.Println("-- bold, underline and reverse at once; then reset")
	s.FeedString(fmt.Sprintf("\r\n%s[1;4;7mA%s[0mB", ESC, ESC))
	for _, column := range []int{0, 1} {
		c := cell(s, 1, column)
		fmt.Printf("    %s  %s\n", pytext.StrRepr(c.Text), noneOr(c.AttributeText()))
	}
	fmt.Println("-- double underline (SGR 21) is underlined")
	s.FeedString(ESC + "[21mD")
	fmt.Printf("    %s  %s\n", pytext.StrRepr("D"), cell(s, 1, 2).AttributeText())
}

func runColours() {
	s, err := hwutvterm.NewScreen(2, 20)
	if missing(err) {
		return
	}
	defer s.Close()
	s.FeedString(fmt.Sprintf("d%s[31mr%s[0m%s[38;5;196mp%s[0m%s[38;2;10;20;30mt%s[0m", ESC, ESC, ESC, ESC, ESC, ESC))
	s.FeedString(fmt.Sprintf("%s[48;2;1;2;3mb%s[0m", ESC, ESC))
	for column, what := range []string{"default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3"} {
		c := cell(s, 0, column)
		var said string
		//  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that one
		//  is a colour and mostly red is the claim, not its shade.
		if what == "indexed 31" {
			red, green, blue := int(c.Foreground[0]), int(c.Foreground[1]), int(c.Foreground[2])
			said = "fg mostly red: " + pytext.Bool(red > 2*max(green, blue))
		} else {
			said = fmt.Sprintf("fg %s  bg %s", c.Foreground, c.Background)
		}
		fmt.Printf("    %-18s %s  %s\n", what, pytext.StrRepr(c.Text), said)
	}
}

// THE APPLICATION UNDER OBSERVATION: it says what it sees, asks the terminal
// where the cursor is, then names every key until 'q'. The Python test's
// own, word for word.
const SEEING_APP = `
import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
`

// AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body,
// 'f' rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
const DRAWING_APP = `
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
`

func runUnnoticed() {
	os.Setenv("COLUMNS", "300")
	t, err := hwutvterm.NewTerminal(10, 44, 100*time.Millisecond)
	if missing(err) {
		return
	}
	defer t.Close()
	running, _ := t.Run([]string{"python3", "-c", SEEING_APP}, nil, "", 10*time.Second)
	fmt.Printf("-- still running after its first screen: %s\n", pytext.Bool(running))
	shown(t.Screen)
	t.Send("q", time.Second)
	status, _, _ := t.Wait(10 * time.Second)
	fmt.Printf("-- after 'q': exit status %d\n", status)
	shown(t.Screen)
}

func runKeys() {
	t, err := hwutvterm.NewTerminal(10, 44, 100*time.Millisecond)
	if missing(err) {
		return
	}
	defer t.Close()
	t.Region("read", 8, 1, 0, -1)
	pressed := "(start)"
	t.OnChange(func(name string, lineList []string) {
		fmt.Printf("    %-22s %s\n", pressed, lineList[0])
	})
	t.Run([]string{"python3", "-c", SEEING_APP}, nil, "", 10*time.Second)
	for _, press := range []struct {
		key      string
		modifier []string
	}{
		{"up", nil}, {"enter", nil}, {"tab", nil}, {"escape", nil}, {"f5", nil}, {"delete", nil},
		{"c", []string{"ctrl"}}, {"x", []string{"alt"}}, {"up", []string{"shift"}},
	} {
		pressed = strings.Join(append(append([]string{}, press.modifier...), press.key), " ")
		t.Press(press.key, press.modifier, time.Second)
	}
	pressed = "send 'ä'"
	t.Send("ä", time.Second)
	pressed = "send 'q'"
	t.Send("q", time.Second)
	t.Wait(10 * time.Second)
}

// linesRepr is the lines as Python prints a list of str.
func linesRepr(lineList []string) string { return pytext.Repr(lineList) }

func runRegions() {
	//  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
	//  ONE report on a loaded machine too.
	t, err := hwutvterm.NewTerminal(8, 30, 300*time.Millisecond)
	if missing(err) {
		return
	}
	defer t.Close()
	t.Region("head", 0, 1, 0, -1)
	t.Region("body", 2, 2, 0, -1)
	t.Region("foot", -1, 1, 0, -1)
	t.OnChange(func(name string, lineList []string) {
		fmt.Printf("    changed  %-5s %s\n", name, linesRepr(lineList))
	})
	for _, act := range []struct {
		said string
		do   func()
	}{
		{"run", func() { t.Run([]string{"python3", "-c", DRAWING_APP}, nil, "", 10*time.Second) }},
		{"'n'", func() { t.Send("n", time.Second) }},
		{"'n'", func() { t.Send("n", time.Second) }},
		{"'r': a redraw, nothing new", func() { t.Send("r", time.Second) }},
		{"'f'", func() { t.Send("f", time.Second) }},
		{"'nnn', typed at once", func() { t.Send("nnn", time.Second) }},
		{"'q'", func() { t.Send("q", time.Second) }},
	} {
		fmt.Printf("-- %s\n", act.said)
		act.do()
	}
	status, _, _ := t.Wait(10 * time.Second)
	body, _ := t.RegionText("body")
	fmt.Printf("-- exit status %d; a region asked by name: %s\n", status, linesRepr(body))
	if _, err := t.RegionText("nosuch"); err != nil {
		fmt.Printf("-- no such region: %s %s\n", err.(*hwutvterm.VtermError).Kind, err)
	}
}

func runEvents() {
	t, err := hwutvterm.NewTerminal(4, 20, 100*time.Millisecond)
	if missing(err) {
		return
	}
	defer t.Close()
	t.OnEvent(func(event hwutvterm.Event) { fmt.Printf("    %s\n", event) })
	for _, fed := range []struct{ said, data string }{
		{"'ab'", "ab"},
		{"a line feed and 'c'", "\r\nc"},
		{"the cursor to row 4, hidden", ESC + "[4;1H" + ESC + "[?25l"},
		{"the alternate screen", ESC + "[?1049h"},
		{"the bell", "\x07"},
		{"nothing that draws: a reset of attributes", ESC + "[0m"},
	} {
		fmt.Printf("-- fed: %s\n", fed.said)
		t.FeedString(fed.data)
	}
	fmt.Println("-- asked where the cursor is, nobody running: the answer waits")
	t.FeedString(ESC + "[2;5H" + ESC + "[6n")
	fmt.Printf("    answer() = %s\n", pytext.BytesRepr(t.Answer()))
	fmt.Println("-- a key pressed with nobody running")
	t.Press("f1", nil, 0)
	fmt.Printf("    answer() = %s\n", pytext.BytesRepr(t.Answer()))
}

func runMissing() {
	os.Setenv(hwutvterm.LIBRARY_VARIABLE, "/nowhere/libvterm.so")
	hwutvterm.ResetLibrary()
	s, err := hwutvterm.NewScreen(24, 80)
	if err == nil {
		fmt.Println("a Screen stands on a library that is not there")
		s.Close()
		return
	}
	//  THE SYSTEM'S OWN WORDS for the failed load are left out; what this
	//  module says -- the line, and the way to install -- stands.
	lineList := strings.Split(err.Error(), "\n")
	fmt.Printf("%s: %s\n", err.(*hwutvterm.VtermError).Kind, strings.SplitN(lineList[0], " -- ", 2)[0])
	for _, line := range lineList[1:] {
		fmt.Println(line)
	}
}

func main() {
	os.Exit(hwutrunner.New(os.Args, "A terminal's screen read by a test: libvterm through cgo.", map[string]func(){
		"text":       runText,
		"screen":     runScreen,
		"attributes": runAttributes,
		"colours":    runColours,
		"unnoticed":  runUnnoticed,
		"keys":       runKeys,
		"regions":    runRegions,
		"events":     runEvents,
		"missing":    runMissing,
	}).Run())
}
