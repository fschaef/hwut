// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package hwutvterm is A TERMINAL'S SCREEN, READ BY A TEST -- the port of
// 'python/hwut_vterm.py' (README-hwut_vterm.txt): libvterm, loaded at run
// time by 'dlopen' through cgo.
//
//	screen, err := hwutvterm.NewScreen(24, 80)
//	if err != nil { fmt.Println("NOT PROBED:", err); return }
//	defer screen.Close()
//	screen.FeedString("\x1b[1mbold\x1b[0m plain")
//	line, _ := screen.Line(0)              // "bold plain"
//	cell, _ := screen.Cell(0, 0)           // cell.BoldF == true
//	row, column := screen.Cursor()         // 0, 10
//
// NO HEADER OF THE LIBRARY IS NEEDED to build this -- only cgo's C compiler:
// its few structures are declared in 'vterm_library.c', as the Python
// binding declares them for 'ctypes', and the library is FOUND at run time
// -- under the name HWUT_LIBVTERM gives, or as the system knows it
// ('libvterm.so.0'; Debian: 'libvterm0'). Where neither loads, the
// constructor returns a *VtermError of kind 'LibraryMissing' whose text says
// how to install it.
//
// THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED -- it changed between
// libvterm's versions. Once per library a scratch terminal is fed one
// attribute at a time and the bit or the bytes that changed are where that
// attribute stands.
//
// TWO TYPES:
//
//	Screen      the grid alone: bytes in, cells out. No process.
//	Terminal    a Screen an APPLICATION RUNS IN, on a pseudo-terminal; it
//	            embeds its *Screen, so every Screen method applies to it.
//
// ERRORS: what Python raises is returned as a *VtermError: 'Kind' is
// Python's exception name -- 'LibraryMissing', 'IndexError', 'KeyError',
// 'TimeoutError', 'RuntimeError', 'OSError' -- 'Message' its text.
// Python's seconds are a time.Duration here.
// _____________________________________________________________________________
package hwutvterm

/*
#cgo LDFLAGS: -ldl
#include <stdlib.h>
#include "vterm_library.h"
*/
import "C"

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"os/exec"
	"runtime/cgo"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"

	"hwut/test_writing_support/go/pytext"
)

// LIBRARY_VARIABLE is the environment variable that names the library's
// file, where the system's search does not find it.
const LIBRARY_VARIABLE = "HWUT_LIBVTERM"

// WHAT IS THE SAME IN EVERY VERSION: six code points of four bytes, then the
// width; everything behind them is measured.
const (
	charsPerCellN = 6
	charsByteN    = 4 * charsPerCellN
	cellByteN     = 128 // room beyond any version's cell
)

// Attribute is one attribute a cell is asked for, with the SGR code that
// sets it.
type Attribute struct {
	Name string
	Sgr  string
}

// ATTRIBUTE_SGR_LIST are the attributes, in Python's 'ATTRIBUTE_SGR_DB'
// order -- the order 'Cell.AttributeText' names them in.
var ATTRIBUTE_SGR_LIST = []Attribute{
	{"bold", "1"}, {"italic", "3"}, {"underline", "4"}, {"blink", "5"},
	{"reverse", "7"}, {"conceal", "8"}, {"strike", "9"},
}

// INSTALL_HINT is what a person is told where the library is not found.
var INSTALL_HINT = strings.Join([]string{
	"HINT: install the library, or name its file:",
	"    Debian, Ubuntu   apt install libvterm0",
	"    Fedora           dnf install libvterm",
	"    Arch             pacman -S libvterm",
	"    macOS            brew install libvterm",
	"    elsewhere        export " + LIBRARY_VARIABLE + "=<path>/libvterm.so",
	"    or work inside   hwut.dev.podman.enter   (the image holds it)",
}, "\n")

// THE PROPERTIES A TERMINAL REPORTS, by libvterm's number; a flag's or a
// number's value is carried, a title's text is not.
var propertyDb = map[int]struct {
	name   string
	plainF bool
}{
	1: {"cursor-visible", true}, 2: {"cursor-blink", true}, 3: {"alternate-screen", true},
	4: {"title", false}, 5: {"icon-name", false}, 6: {"reverse-video", true},
	7: {"cursor-shape", true}, 8: {"mouse", true}, 9: {"focus-report", true},
}

// KEY_DB are the keys that are not a character, by the name a test presses
// them under ('VTermKey'; function keys stand at 256 + n).
var KEY_DB = func() map[string]int {
	db := map[string]int{
		"enter": 1, "tab": 2, "backspace": 3, "escape": 4,
		"up": 5, "down": 6, "left": 7, "right": 8,
		"insert": 9, "delete": 10, "home": 11, "end": 12,
		"pageup": 13, "pagedown": 14,
	}
	for n := 1; n <= 12; n++ {
		db["f"+strconv.Itoa(n)] = 256 + n
	}
	return db
}()

// MODIFIER_DB are the modifiers, by name.
var MODIFIER_DB = map[string]int{"shift": 1, "alt": 2, "ctrl": 4}

// VtermError is what Python raises: its exception's name and its text.
type VtermError struct {
	Kind    string
	Message string
}

// Error
//
// RETURN: string, the error's text -- what Python's 'str(error)' says.
func (self *VtermError) Error() string { return self.Message }

// vtermError
//
// RETURN: *VtermError, of 'kind', its message 'format' filled.
func vtermError(kind, format string, argument ...any) *VtermError {
	return &VtermError{Kind: kind, Message: fmt.Sprintf(format, argument...)}
}

// ------------------------------------------------------------- the library

var libraryName string // the loaded library's name; "" where none is loaded

// library
//
// RETURN: error, nil once 'libvterm' is loaded -- once -- and its functions
// found; a *VtermError 'LibraryMissing' with the install hint, else.
func library() error {
	if libraryName != "" {
		return nil
	}
	why := make([]byte, 1024)
	load := func(name string) C.int {
		text := C.CString(name)
		defer C.free(unsafe.Pointer(text))
		return C.hv_load(text, (*C.char)(unsafe.Pointer(&why[0])), C.size_t(len(why)))
	}
	whyText := func() string { return string(why[:bytes.IndexByte(why, 0)]) }
	name := os.Getenv(LIBRARY_VARIABLE)
	if name != "" {
		switch load(name) {
		case -1:
			return vtermError("LibraryMissing", "libvterm cannot be loaded from '%s' -- %s\n%s", name, whyText(), INSTALL_HINT)
		case -2:
			return vtermError("LibraryMissing", "libvterm cannot be loaded from '%s' -- no function '%s'\n%s", name, whyText(), INSTALL_HINT)
		}
	} else {
		for _, candidate := range []string{"libvterm.so.0", "libvterm.so", "libvterm.0.dylib", "libvterm.dylib"} {
			if load(candidate) == 0 {
				name = candidate
				break
			}
		}
		if name == "" {
			return vtermError("LibraryMissing", "libvterm is not installed, and '%s' names no file\n%s", LIBRARY_VARIABLE, INSTALL_HINT)
		}
	}
	libraryName = name
	return nil
}

// ResetLibrary
//
// RETURN: nothing; the library is looked for again at the next screen, and
// its layout measured again -- Python's 'hwut_vterm._library = None'.
func ResetLibrary() {
	C.hv_unload()
	libraryName = ""
	layout = nil
}

// DetectionText
//
// RETURN: string, 'libvterm found: <name>' where the library loads; the
// text of 'LibraryMissing' -- what is wrong and how to install it -- else.
func DetectionText() string {
	if err := library(); err != nil {
		return err.Error()
	}
	return "libvterm found: " + libraryName
}

// --------------------------------------------------------------- the cell

// RGB is a colour: red, green, blue. A nil *RGB is the terminal's default.
type RGB [3]uint8

// String
//
// RETURN: string, the colour as Python prints the tuple -- '(10, 20, 30)';
// 'None' for a nil *RGB, the default.
func (self *RGB) String() string {
	if self == nil {
		return "None"
	}
	return fmt.Sprintf("(%d, %d, %d)", self[0], self[1], self[2])
}

// Cell is one cell of the screen, as plain values. 'Text' is what stands
// in it -- "" for a cell nothing was written to, and for the right half of
// a wide character. 'Foreground' and 'Background' are nil where the cell
// wears the terminal's default.
type Cell struct {
	Text       string
	Width      int
	BoldF      bool
	ItalicF    bool
	UnderlineF bool
	BlinkF     bool
	ReverseF   bool
	ConcealF   bool
	StrikeF    bool
	Foreground *RGB
	Background *RGB
}

// flagList
//
// RETURN: []*bool, the cell's attribute flags, in ATTRIBUTE_SGR_LIST's order.
func (self *Cell) flagList() []*bool {
	return []*bool{&self.BoldF, &self.ItalicF, &self.UnderlineF, &self.BlinkF, &self.ReverseF, &self.ConcealF, &self.StrikeF}
}

// AttributeText
//
// RETURN: string, the attributes that are set, by name and in one fixed
// order, separated by blanks -- 'bold reverse'; "" where none is set.
func (self Cell) AttributeText() string {
	var nameList []string
	for i, flag := range self.flagList() {
		if *flag {
			nameList = append(nameList, ATTRIBUTE_SGR_LIST[i].Name)
		}
	}
	return strings.Join(nameList, " ")
}

// cellLayout is where a cell's fields stand in this library's
// 'VTermScreenCell'.
type cellLayout struct {
	offset      [7]int   // per attribute, the byte ...
	mask        [7]uint8 // ... and its bits
	foregroundI int      // offset of the foreground's red byte
	backgroundI int
	convertF    bool // colours pass 'convert_color_to_rgb' first
	defaultFg   [3]uint8
	defaultBg   [3]uint8
}

var layout *cellLayout // measured once per library

// -------------------------------------------------------------- the screen

// Screen is a terminal of RowN rows and ColumnN columns that draws what it
// is fed and lets its cells be read. 'Close' gives back the library's
// memory.
type Screen struct {
	RowN, ColumnN int
	terminal      unsafe.Pointer // VTerm*
	screen        unsafe.Pointer // VTermScreen*
	state         unsafe.Pointer // VTermState*
}

// NewScreen
//
// RETURN: (*Screen, nil), blank, the cursor at (0, 0), if success;
// (nil, *VtermError 'LibraryMissing'), where 'libvterm' is not found.
func NewScreen(rowN, columnN int) (*Screen, error) {
	if err := library(); err != nil {
		return nil, err
	}
	self := &Screen{RowN: rowN, ColumnN: columnN}
	self.terminal = C.hv_new(C.int(rowN), C.int(columnN))
	self.screen = C.hv_obtain_screen(self.terminal)
	self.state = C.hv_obtain_state(self.terminal)
	return self, nil
}

// Close
//
// RETURN: nothing; the terminal's memory is freed -- a second call does
// nothing.
func (self *Screen) Close() {
	if self.terminal == nil {
		return
	}
	C.hv_free(self.terminal)
	self.terminal, self.screen, self.state = nil, nil, nil
}

// Feed
//
// RETURN: int, the number of bytes of 'data' the terminal took -- all of
// them, where it works as documented. 'data' is what a program wrote.
func (self *Screen) Feed(data []byte) int {
	if len(data) == 0 {
		return 0
	}
	return int(C.hv_input_write(self.terminal, (*C.char)(unsafe.Pointer(&data[0])), C.size_t(len(data))))
}

// FeedString
//
// RETURN: int, as 'Feed' -- 'text' sent as the bytes it holds (UTF-8).
func (self *Screen) FeedString(text string) int { return self.Feed([]byte(text)) }

// Cursor
//
// RETURN: (int, int), the cursor's row and column, from 0.
func (self *Screen) Cursor() (int, int) {
	var row, column C.int
	C.hv_cursor(self.state, &row, &column)
	return int(row), int(column)
}

// raw
//
// RETURN: []byte, the library's own cell at that place, its colours
// resolved to red, green, blue where the layout is known and the library
// keeps them otherwise.
func (self *Screen) raw(row, column int) []byte {
	buffer := make([]byte, cellByteN)
	convertF, foregroundI, backgroundI := 0, 1, 1
	if layout != nil && layout.convertF {
		convertF, foregroundI, backgroundI = 1, layout.foregroundI, layout.backgroundI
	}
	C.hv_get_cell(self.screen, C.int(row), C.int(column), (*C.uchar)(unsafe.Pointer(&buffer[0])),
		C.size_t(len(buffer)), C.int(convertF), C.int(foregroundI), C.int(backgroundI))
	return buffer
}

// Cell
//
// RETURN: (Cell, nil), what stands at that place, if success;
// (Cell{}, *VtermError 'IndexError'), where the place is not on the screen.
func (self *Screen) Cell(row, column int) (Cell, error) {
	if !(0 <= row && row < self.RowN && 0 <= column && column < self.ColumnN) {
		return Cell{}, vtermError("IndexError", "(%d, %d) is not on a screen of %d x %d", row, column, self.RowN, self.ColumnN)
	}
	l := measured()
	raw := self.raw(row, column)
	var text strings.Builder
	for i := 0; i < charsByteN; i += 4 {
		if code := binary.LittleEndian.Uint32(raw[i:]); code != 0 && code != 0xFFFFFFFF {
			text.WriteRune(rune(code))
		}
	}
	cell := Cell{Text: text.String(), Width: int(raw[charsByteN])}
	if cell.Width == 0 {
		cell.Width = 1
	}
	for i, flag := range cell.flagList() {
		*flag = raw[l.offset[i]]&l.mask[i] != 0
	}
	colour := func(i int, standard [3]uint8) *RGB {
		if value := (RGB{raw[i], raw[i+1], raw[i+2]}); [3]uint8(value) != standard {
			return &value
		}
		return nil
	}
	cell.Foreground = colour(l.foregroundI, l.defaultFg)
	cell.Background = colour(l.backgroundI, l.defaultBg)
	return cell, nil
}

// rowText
//
// RETURN: string, the characters of 'columnN' columns from 'column' of
// 'row', blanks at its end dropped; a cell nothing was written to reads as
// a blank.
func (self *Screen) rowText(row, column, columnN int) string {
	var text strings.Builder
	for at := column; at < column+columnN; {
		cell, err := self.Cell(row, at)
		if err != nil {
			break
		}
		if cell.Text == "" {
			text.WriteString(" ")
		} else {
			text.WriteString(cell.Text)
		}
		at += max(cell.Width, 1)
	}
	return strings.TrimRightFunc(text.String(), pytext.IsSpace)
}

// Line
//
// RETURN: (string, nil), the row's characters, blanks at its end dropped --
// a cell nothing was written to reads as a blank -- if success;
// ("", *VtermError 'IndexError'), where the row is not on the screen.
func (self *Screen) Line(row int) (string, error) {
	if row < 0 || row >= self.RowN {
		return "", vtermError("IndexError", "(%d, %d) is not on a screen of %d x %d", row, 0, self.RowN, self.ColumnN)
	}
	return self.rowText(row, 0, self.ColumnN), nil
}

// LineList
//
// RETURN: []string, every row as 'Line' gives it, top first.
func (self *Screen) LineList() []string {
	result := make([]string, self.RowN)
	for row := range result {
		result[row] = self.rowText(row, 0, self.ColumnN)
	}
	return result
}

// ------------------------------------------------------ measuring the layout

// cellAfter
//
// RETURN: []byte, the raw cell (0, 0) of a fresh terminal after
// '<esc>[<sequence>m' (nothing where "") and one 'X'.
func cellAfter(sequence string) []byte {
	scratch, _ := NewScreen(2, 4)
	defer scratch.Close()
	if sequence != "" {
		scratch.FeedString("\x1b[" + sequence + "m")
	}
	scratch.FeedString("X")
	return scratch.raw(0, 0)
}

// changed
//
// RETURN: (int, uint8, true), the offset and the bits of the first byte
// behind the width in which 'raw' differs from 'plain'; (0, 0, false), none.
func changed(plain, raw []byte) (int, uint8, bool) {
	for i := charsByteN + 1; i < cellByteN; i++ {
		if plain[i] != raw[i] {
			return i, plain[i] ^ raw[i], true
		}
	}
	return 0, 0, false
}

// measured
//
// RETURN: *cellLayout, where this library's cell keeps each attribute and
// each colour -- measured once on scratch terminals, then remembered.
func measured() *cellLayout {
	if layout != nil {
		return layout
	}
	l := &cellLayout{}
	plain := cellAfter("")
	for i, attribute := range ATTRIBUTE_SGR_LIST {
		//  NOTHING MOVED: this library does not know the attribute.
		l.offset[i], l.mask[i] = charsByteN+1, 0
		if offset, bits, found := changed(plain, cellAfter(attribute.Sgr)); found {
			l.offset[i], l.mask[i] = offset, bits
		}
	}
	//  UNDERLINE IS A NUMBER OF TWO BITS (single, double, curly): any of them
	//  is 'underlined', so the double's bit joins the mask.
	double := cellAfter("21")
	for i := charsByteN + 1; i < cellByteN; i++ {
		if plain[i] != double[i] && i == l.offset[2] {
			l.mask[2] |= plain[i] ^ double[i]
		}
	}
	colourAt := func(code string) int {
		raw := cellAfter(code + ";2;1;2;3")
		if i := bytes.Index(raw[charsByteN+1:], []byte{1, 2, 3}); i >= 0 {
			return charsByteN + 1 + i
		}
		return charsByteN + 1
	}
	l.foregroundI = colourAt("38")
	l.backgroundI = colourAt("48")
	l.convertF = C.hv_convert_f() != 0
	//  THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell will be
	//  read from now on.
	layout = l
	raw := cellAfter("")
	copy(l.defaultFg[:], raw[l.foregroundI:])
	copy(l.defaultBg[:], raw[l.backgroundI:])
	return l
}

// ------------------------------------------------------------------ events

// Event is ONE THING THE TERMINAL DID, as libvterm reports it (the RAW
// layer):
//
//	Kind 'damage'    rows Row..RowEnd and columns Column..ColumnEnd changed,
//	                 ends EXCLUDED
//	     'cursor'    the cursor stands at (Row, Column); Value (bool) says
//	                 whether it is visible
//	     'property'  the property Name is now Value (an int; nil where the
//	                 value is a text)
//	     'bell'      the bell rang
type Event struct {
	Kind      string
	Row       int
	Column    int
	RowEnd    int
	ColumnEnd int
	Name      string
	Value     any
}

// String
//
// RETURN: string, the event on one line, as a test prints it.
func (self Event) String() string {
	switch self.Kind {
	case "damage":
		return fmt.Sprintf("damage    rows %d..%d  columns %d..%d", self.Row, self.RowEnd, self.Column, self.ColumnEnd)
	case "cursor":
		hidden := "  hidden"
		if visible, _ := self.Value.(bool); visible {
			hidden = ""
		}
		return fmt.Sprintf("cursor    (%d, %d)%s", self.Row, self.Column, hidden)
	case "property":
		return fmt.Sprintf("property  %s = %s", self.Name, pytext.Str(self.Value))
	}
	return self.Kind
}

// ---------------------------------------------------------------- terminal

// region is one named rectangle observed.
type region struct {
	row, rowN, column, columnN int
	told                       []string // the lines last told
}

// Terminal is A TERMINAL AN APPLICATION RUNS IN, OBSERVED BY CALLBACKS: set
// up first, then run -- the application is started on a pseudo-terminal of
// this size and cannot tell it from a terminal a person sits at.
//
//	OnEvent    RAW: every Event libvterm reports, as it happens.
//	OnChange   REGIONS: a named rectangle's text, told once it CHANGED and
//	           the application has gone QUIET (Settle without a byte); one
//	           call per changed region and pause, in the order the regions
//	           were declared.
type Terminal struct {
	*Screen
	Settle         time.Duration
	eventFList     []func(Event)
	changeFList    []func(name string, lineList []string)
	regionNameList []string
	regionDb       map[string]*region
	answer         []byte
	master         int // -1: none
	process        *os.Process
	reapedF        bool
	status         int
	endedF         bool
	handle         cgo.Handle
	callbacks      unsafe.Pointer
}

// NewTerminal
//
// RETURN: (*Terminal, nil), blank, nothing running in it, if success;
// (nil, *VtermError 'LibraryMissing'), where 'libvterm' is not found.
// 'settle' is how long the application must write nothing before its
// screen is taken as drawn (Python's default: 100 ms).
func NewTerminal(rowN, columnN int, settle time.Duration) (*Terminal, error) {
	screen, err := NewScreen(rowN, columnN)
	if err != nil {
		return nil, err
	}
	self := &Terminal{Screen: screen, Settle: settle, regionDb: map[string]*region{}, master: -1}
	//  THE CALLBACKS LIVE AS LONG AS THE TERMINAL: libvterm keeps their
	//  address and the handle that leads back here.
	self.handle = cgo.NewHandle(self)
	self.callbacks = C.hv_observe(screen.terminal, screen.screen, C.uintptr_t(self.handle))
	return self, nil
}

// OnEvent
//
// RETURN: nothing; 'callback(event)' is called with every raw Event from
// now on.
func (self *Terminal) OnEvent(callback func(Event)) {
	self.eventFList = append(self.eventFList, callback)
}

// OnChange
//
// RETURN: nothing; 'callback(name, lineList)' is called for every region
// whose text changed, once the screen is quiet.
func (self *Terminal) OnChange(callback func(name string, lineList []string)) {
	self.changeFList = append(self.changeFList, callback)
}

// Region
//
// RETURN: nothing; the rectangle 'name' is observed from now on: 'rowN' rows
// from 'row', 'columnN' columns from 'column' -- to the right edge where
// negative (Python's None). A NEGATIVE 'row' counts from the bottom: -1 is
// the last row. What stands there now is known, not news.
func (self *Terminal) Region(name string, row, rowN, column, columnN int) {
	if row < 0 {
		row += self.RowN
	}
	if columnN < 0 {
		columnN = self.ColumnN - column
	}
	if _, found := self.regionDb[name]; !found {
		self.regionNameList = append(self.regionNameList, name)
	}
	r := &region{row: row, rowN: rowN, column: column, columnN: columnN}
	r.told = self.regionLines(r)
	self.regionDb[name] = r
}

// regionLines
//
// RETURN: []string, the region's rows as they stand now, blanks at each
// row's end dropped.
func (self *Terminal) regionLines(r *region) []string {
	result := make([]string, r.rowN)
	for i := range result {
		result[i] = self.rowText(r.row+i, r.column, r.columnN)
	}
	return result
}

// RegionText
//
// RETURN: ([]string, nil), the region's rows as they stand now, blanks at
// each row's end dropped, if success; (nil, *VtermError 'KeyError'), where
// no such region was declared.
func (self *Terminal) RegionText(name string) ([]string, error) {
	r, found := self.regionDb[name]
	if !found {
		return nil, vtermError("KeyError", "'%s'", name)
	}
	return self.regionLines(r), nil
}

// Report
//
// RETURN: []string, the names of the regions whose text differs from what
// was last told -- each told to every 'OnChange' callback, in the order of
// declaration.
func (self *Terminal) Report() []string {
	var changedList []string
	for _, name := range self.regionNameList {
		r := self.regionDb[name]
		lineList := self.regionLines(r)
		if slices.Equal(lineList, r.told) {
			continue
		}
		r.told = lineList
		changedList = append(changedList, name)
		for _, callback := range self.changeFList {
			callback(name, lineList)
		}
	}
	return changedList
}

// emit
//
// RETURN: int, 1 -- libvterm's 'handled'; 'event' reached every raw
// callback.
func (self *Terminal) emit(event Event) int {
	for _, callback := range self.eventFList {
		callback(event)
	}
	return 1
}

// Feed
//
// RETURN: int, the number of bytes of 'data' the terminal took; the raw
// events of what was fed fired before this returns, what the terminal
// answered went to the application, where one runs.
func (self *Terminal) Feed(data []byte) int {
	takenN := self.Screen.Feed(data)
	C.hv_flush_damage(self.screen)
	self.forward()
	return takenN
}

// FeedString
//
// RETURN: int, as 'Feed' -- 'text' sent as the bytes it holds (UTF-8).
func (self *Terminal) FeedString(text string) int { return self.Feed([]byte(text)) }

// Answer
//
// RETURN: []byte, what the terminal said since the last call and no
// application took -- the reply to a question fed by hand, the sequence of
// a key pressed with nothing running.
func (self *Terminal) Answer() []byte {
	data := append([]byte{}, self.answer...)
	self.answer = self.answer[:0]
	return data
}

// forward
//
// RETURN: nothing; the terminal's words reached the application, if one
// runs; they wait in 'Answer' otherwise.
func (self *Terminal) forward() {
	if self.master < 0 || len(self.answer) == 0 {
		return
	}
	for done := 0; done < len(self.answer); {
		n, err := syscall.Write(self.master, self.answer[done:])
		if err == syscall.EINTR {
			continue
		}
		if err != nil {
			self.endedF = true
			break
		}
		done += n
	}
	self.answer = self.answer[:0]
}

// Send
//
// RETURN: bool, true where the application still runs after 'text' was
// typed, character by character, as a keyboard sends it, and the screen was
// read until quiet -- 'react' given to begin answering.
func (self *Terminal) Send(text string, react time.Duration) bool {
	for _, character := range text {
		C.hv_keyboard_unichar(self.terminal, C.uint32_t(character), 0)
	}
	self.forward()
	return self.Pump(react)
}

// Press
//
// RETURN: (bool, nil), true where the application still runs after 'key'
// was pressed with 'modifierList' held and the screen was read until quiet
// ('react' to begin answering); (false, *VtermError 'KeyError'), where 'key'
// or a modifier has no name here. 'key' is a name of KEY_DB ('enter', 'up',
// 'f5', ...) or one character; the modifiers are 'shift', 'alt', 'ctrl' --
// 'Press("c", []string{"ctrl"}, time.Second)' is Ctrl-C.
func (self *Terminal) Press(key string, modifierList []string, react time.Duration) (bool, error) {
	modifier := 0
	for _, name := range modifierList {
		bits, found := MODIFIER_DB[name]
		if !found {
			return false, vtermError("KeyError", "'%s'", name)
		}
		modifier |= bits
	}
	if character := []rune(key); len(character) == 1 {
		C.hv_keyboard_unichar(self.terminal, C.uint32_t(character[0]), C.int(modifier))
	} else {
		code, found := KEY_DB[key]
		if !found {
			return false, vtermError("KeyError", "'%s'", key)
		}
		C.hv_keyboard_key(self.terminal, C.int(code), C.int(modifier))
	}
	self.forward()
	return self.Pump(react), nil
}

// Run
//
// RETURN: (bool, nil), true where the application 'argv' still runs once
// its first screen stands ('start' given to draw it), if success;
// (false, *VtermError 'RuntimeError'), where one already runs here;
// (false, *VtermError 'OSError'), where it cannot be started. It runs on a
// pseudo-terminal of this terminal's size: its three streams are that
// terminal, it is the controlling one, TERM is 'xterm-256color', and LINES
// and COLUMNS are taken OUT of its environment ('env', the process's own
// where nil) -- they would overrule the size. 'cwd' "" is the present
// directory.
func (self *Terminal) Run(argv []string, env []string, cwd string, start time.Duration) (bool, error) {
	if self.process != nil {
		return false, vtermError("RuntimeError", "an application already runs in this terminal")
	}
	master, slave, err := openpty(self.RowN, self.ColumnN)
	if err != nil {
		return false, vtermError("OSError", "openpty: %s", err)
	}
	if env == nil {
		env = os.Environ()
	}
	environment := []string{}
	for _, entry := range env {
		if !strings.HasPrefix(entry, "TERM=") && !strings.HasPrefix(entry, "LINES=") && !strings.HasPrefix(entry, "COLUMNS=") {
			environment = append(environment, entry)
		}
	}
	child := exec.Command(argv[0], argv[1:]...)
	child.Stdin, child.Stdout, child.Stderr = slave, slave, slave
	child.Env = append(environment, "TERM=xterm-256color")
	child.Dir = cwd
	//  THE CHILD LEADS ITS OWN SESSION, the pseudo-terminal (its fd 0) its
	//  controlling terminal.
	child.SysProcAttr = &syscall.SysProcAttr{Setsid: true, Setctty: true, Ctty: 0}
	err = child.Start()
	slave.Close()
	if err != nil {
		syscall.Close(master)
		return false, vtermError("OSError", "%s", err)
	}
	self.master, self.process = master, child.Process
	self.reapedF, self.endedF = false, false
	return self.Pump(start), nil
}

// poll
//
// RETURN: bool, true where the application still runs; false where it
// ended (reaped, its status kept) or never ran.
func (self *Terminal) poll() bool {
	if self.process == nil || self.reapedF {
		return false
	}
	var status syscall.WaitStatus
	if pid, _ := syscall.Wait4(self.process.Pid, &status, syscall.WNOHANG, nil); pid != self.process.Pid {
		return true
	}
	self.keep(status)
	return false
}

// keep
//
// RETURN: nothing; the application is reaped, 'status' its end: the exit
// status, or minus the signal that ended it.
func (self *Terminal) keep(status syscall.WaitStatus) {
	self.reapedF = true
	if status.Signaled() {
		self.status = -int(status.Signal())
	} else {
		self.status = status.ExitStatus()
	}
}

// kill
//
// RETURN: nothing; the application is killed and reaped.
func (self *Terminal) kill() {
	var status syscall.WaitStatus
	syscall.Kill(self.process.Pid, syscall.SIGKILL)
	for {
		if _, err := syscall.Wait4(self.process.Pid, &status, 0, nil); err != syscall.EINTR {
			break
		}
	}
	self.keep(status)
}

// Pump
//
// RETURN: bool, true where the application still runs. READ UNTIL QUIET:
// up to 'first' for the application to write at all, then on until it
// wrote nothing for 'Settle'; then the changed regions are reported.
func (self *Terminal) Pump(first time.Duration) bool {
	data := make([]byte, 65536)
	wait := first
	for self.master >= 0 && !self.endedF {
		if !readableWithin(self.master, wait) {
			break
		}
		n, err := syscall.Read(self.master, data)
		if err == syscall.EINTR {
			continue
		}
		if n <= 0 { // the last writer closed: it ended
			self.endedF = true
			break
		}
		self.Feed(data[:n])
		wait = self.Settle
	}
	self.Report()
	return self.poll() && !self.endedF
}

// Expect
//
// RETURN: (int, int, nil), the row and column (in characters) where 'text'
// stands on the screen, once it does; (0, 0, *VtermError 'TimeoutError'),
// carrying the screen, where it does not within 'timeout'.
func (self *Terminal) Expect(text string, timeout time.Duration) (int, int, error) {
	deadline := time.Now().Add(timeout)
	for {
		for row, line := range self.LineList() {
			if i := strings.Index(line, text); i >= 0 {
				return row, len([]rune(line[:i])), nil
			}
		}
		if !time.Now().Before(deadline) || self.endedF || self.master < 0 {
			return 0, 0, vtermError("TimeoutError", "'%s' did not appear; the screen:\n%s", text, strings.Join(self.LineList(), "\n"))
		}
		self.Pump(self.Settle)
	}
}

// Wait
//
// RETURN: (int, true, nil), the application's exit status (minus the signal
// that ended it), once it has ended and its last words are on the screen;
// (0, false, nil), where no application was run; (0, true, *VtermError
// 'TimeoutError'), where it still ran after 'timeout' -- it is killed first.
func (self *Terminal) Wait(timeout time.Duration) (int, bool, error) {
	if self.process == nil {
		return 0, false, nil
	}
	deadline := time.Now().Add(timeout)
	for self.Pump(self.Settle) {
		if !time.Now().Before(deadline) {
			self.kill()
			return 0, true, vtermError("TimeoutError", "the application still ran after %.1f s", timeout.Seconds())
		}
	}
	until := time.Now().Add(max(time.Until(deadline), 100*time.Millisecond))
	for self.poll() {
		if !time.Now().Before(until) {
			self.kill()
			return 0, true, vtermError("TimeoutError", "the application closed its terminal and did not end")
		}
		time.Sleep(10 * time.Millisecond)
	}
	return self.status, true, nil
}

// Close
//
// RETURN: nothing; an application still running is killed, the
// pseudo-terminal closed, the terminal's memory freed -- a second call
// does nothing.
func (self *Terminal) Close() {
	if self.poll() {
		self.kill()
	}
	if self.master >= 0 {
		syscall.Close(self.master)
		self.master = -1
	}
	if self.Screen.terminal != nil {
		self.Screen.Close()
		C.free(self.callbacks)
		self.handle.Delete()
	}
}
