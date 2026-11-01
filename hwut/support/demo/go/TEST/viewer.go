// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// A TERMINAL FILE VIEWER -- the program 'screen.go' tests; no test itself.
// 'viewer.py' of the Python demonstration, in Go ('make viewer.exe').
//
//     viewer.exe <file>
//
// Full screen, on the terminal's alternate screen: a title bar (reverse
// video), as many lines of the file as fit, and a status line: the keys
// flush left, the lines shown flush right. Keys: 'j' or down one line
// further, 'k' or up one line back, 'q' quits.
//
// Go's standard library has no 'termios' module: the raw mode and the
// terminal's size are system calls ('ioctl' TCGETS, TCSETS, TIOCGWINSZ).
// _____________________________________________________________________________

package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

// RETURN: nothing. Draws the whole screen with the file's line 'top' first.
func draw(out *bufio.Writer, name string, lineList []string, top, rowN, columnN int) {
	bodyN := rowN - 2
	shown := lineList[top:min(top+bodyN, len(lineList))]
	out.WriteString("\x1b[H\x1b[2J")
	title := fmt.Sprintf("%-*s", columnN, " "+name)
	fmt.Fprintf(out, "\x1b[7m%s\x1b[0m\r\n", cut(title, columnN))
	for _, line := range shown {
		out.WriteString(cut(line, columnN) + "\r\n")
	}
	out.WriteString(strings.Repeat("\r\n", bodyN-len(shown)))
	where := fmt.Sprintf("lines %d-%d of %d", top+1, top+len(shown), len(lineList))
	keys := "j k q"
	fmt.Fprintf(out, "\x1b[%d;1H%s%*s", rowN, keys, columnN-1-len(keys), where)
	out.Flush()
}

// TCSETSW is Linux's ioctl for TCSADRAIN, which Go's syscall does not name.
const TCSETSW = 0x5403

// RETURN: string, 'text' cut to its first 'n' characters.
func cut(text string, n int) string {
	runeList := []rune(text)
	if len(runeList) > n {
		return string(runeList[:n])
	}
	return text
}

// RETURN: nothing; the ioctl 'request' is done on 'fd' with 'argument', else
// the program ends with status 1.
func ioctl(fd int, request uintptr, argument unsafe.Pointer) {
	if _, _, errno := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), request, uintptr(argument)); errno != 0 {
		fmt.Fprintf(os.Stderr, "viewer.go: ioctl: %s\n", errno)
		os.Exit(1)
	}
}

// RETURN: int, 0 once 'q' was pressed.
func run(path string) int {
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "viewer.go: %s\n", err)
		return 1
	}
	lineList := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	var size struct{ row, column, x, y uint16 }
	ioctl(1, syscall.TIOCGWINSZ, unsafe.Pointer(&size))
	rowN, columnN := int(size.row), int(size.column)
	var saved syscall.Termios
	ioctl(0, syscall.TCGETS, unsafe.Pointer(&saved))
	raw := saved // as Python's 'tty.setraw'
	raw.Iflag &^= syscall.BRKINT | syscall.ICRNL | syscall.INPCK | syscall.ISTRIP | syscall.IXON
	raw.Oflag &^= syscall.OPOST
	raw.Cflag &^= syscall.CSIZE | syscall.PARENB
	raw.Cflag |= syscall.CS8
	raw.Lflag &^= syscall.ECHO | syscall.ICANON | syscall.IEXTEN | syscall.ISIG
	raw.Cc[syscall.VMIN], raw.Cc[syscall.VTIME] = 1, 0
	ioctl(0, syscall.TCSETS, unsafe.Pointer(&raw))
	out := bufio.NewWriter(os.Stdout)
	out.WriteString("\x1b[?1049h")
	defer func() {
		out.WriteString("\x1b[?1049l")
		out.Flush()
		ioctl(0, TCSETSW, unsafe.Pointer(&saved))
	}()
	top, key := 0, make([]byte, 8)
	for {
		draw(out, filepath.Base(path), lineList, top, rowN, columnN)
		n, err := os.Stdin.Read(key)
		if err != nil {
			return 1
		}
		switch string(key[:n]) {
		case "q":
			return 0
		case "j", "\x1b[B":
			top = min(top+1, max(0, len(lineList)-(rowN-2)))
		case "k", "\x1b[A":
			top = max(top-1, 0)
		}
	}
}

// RETURN: nothing; exits with the viewer's status.
func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: viewer.exe <file>")
		os.Exit(2)
	}
	os.Exit(run(os.Args[1]))
}
