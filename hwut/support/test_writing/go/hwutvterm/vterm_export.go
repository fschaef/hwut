// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE CALLBACKS libvterm calls, through 'vterm_library.c', on the Go
// terminal the handle names.
// _____________________________________________________________________________
package hwutvterm

/*
#include <stddef.h>
#include <stdint.h>
*/
import "C"

import (
	"runtime/cgo"
	"strconv"
	"unsafe"
)

// terminalOf
//
// RETURN: *Terminal, the one 'handle' names.
func terminalOf(handle C.uintptr_t) *Terminal { return cgo.Handle(handle).Value().(*Terminal) }

// hwutVtermDamage
//
// RETURN: C.int, 1 (handled) -- rows startRow..endRow, columns
// startCol..endCol (ends excluded) changed: a "damage" Event reached every
// raw callback of the terminal.
//
//export hwutVtermDamage
func hwutVtermDamage(handle C.uintptr_t, startRow, endRow, startCol, endCol C.int) C.int {
	return C.int(terminalOf(handle).emit(Event{Kind: "damage", Row: int(startRow), Column: int(startCol),
		RowEnd: int(endRow), ColumnEnd: int(endCol)}))
}

// hwutVtermCursor
//
// RETURN: C.int, 1 (handled) -- the cursor moved to (row, column), visible
// or not: a "cursor" Event reached every raw callback.
//
//export hwutVtermCursor
func hwutVtermCursor(handle C.uintptr_t, row, column, visible C.int) C.int {
	return C.int(terminalOf(handle).emit(Event{Kind: "cursor", Row: int(row), Column: int(column), Value: visible != 0}))
}

// hwutVtermProperty
//
// RETURN: C.int, 1 (handled) -- the property 'number' changed to 'value'
// (carried where it is a flag or a number): a "property" Event reached
// every raw callback.
//
//export hwutVtermProperty
func hwutVtermProperty(handle C.uintptr_t, number, value C.int) C.int {
	name, plainF := "", false
	if entry, found := propertyDb[int(number)]; found {
		name, plainF = entry.name, entry.plainF
	} else {
		name = "property-" + strconv.Itoa(int(number))
	}
	event := Event{Kind: "property", Name: name}
	if plainF {
		event.Value = int(value)
	}
	return C.int(terminalOf(handle).emit(event))
}

// hwutVtermBell
//
// RETURN: C.int, 1 (handled) -- the bell rang: a "bell" Event reached
// every raw callback.
//
//export hwutVtermBell
func hwutVtermBell(handle C.uintptr_t) C.int {
	return C.int(terminalOf(handle).emit(Event{Kind: "bell"}))
}

// hwutVtermOutput
//
// RETURN: nothing; the 'length' bytes the TERMINAL said -- a key's
// sequence, the answer to a question -- were collected for the application.
//
//export hwutVtermOutput
func hwutVtermOutput(handle C.uintptr_t, data *C.char, length C.size_t) {
	self := terminalOf(handle)
	self.answer = append(self.answer, C.GoBytes(unsafe.Pointer(data), C.int(length))...)
}
