// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE PSEUDO-TERMINAL, by the system calls 'os.openpty' makes: '/dev/ptmx'
// opened, unlocked, its slave named and opened, the window size set.
// _____________________________________________________________________________
package hwutvterm

import (
	"fmt"
	"os"
	"syscall"
	"time"
	"unsafe"
)

// ioctl
//
// RETURN: error, nil where 'request' on 'fd' with 'argument' succeeded; the
// system's error, else.
func ioctl(fd int, request uintptr, argument unsafe.Pointer) error {
	if _, _, errno := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), request, uintptr(argument)); errno != 0 {
		return errno
	}
	return nil
}

// openpty
//
// RETURN: (int, *os.File, nil), the master's descriptor (close-on-exec) and
// the slave, a terminal of 'rowN' rows and 'columnN' columns, if success;
// (-1, nil, error), else.
func openpty(rowN, columnN int) (int, *os.File, error) {
	master, err := syscall.Open("/dev/ptmx", syscall.O_RDWR|syscall.O_NOCTTY|syscall.O_CLOEXEC, 0)
	if err != nil {
		return -1, nil, err
	}
	unlock, number := int32(0), uint32(0)
	if err = ioctl(master, syscall.TIOCSPTLCK, unsafe.Pointer(&unlock)); err == nil {
		err = ioctl(master, syscall.TIOCGPTN, unsafe.Pointer(&number))
	}
	if err != nil {
		syscall.Close(master)
		return -1, nil, err
	}
	slave, err := os.OpenFile(fmt.Sprintf("/dev/pts/%d", number), os.O_RDWR|syscall.O_NOCTTY, 0)
	if err != nil {
		syscall.Close(master)
		return -1, nil, err
	}
	size := [4]uint16{uint16(rowN), uint16(columnN), 0, 0}
	ioctl(int(slave.Fd()), syscall.TIOCSWINSZ, unsafe.Pointer(&size))
	return master, slave, nil
}

// readableWithin
//
// RETURN: bool, true where 'fd' has something to read -- or its end --
// within 'wait'; false where 'wait' passed first.
func readableWithin(fd int, wait time.Duration) bool {
	deadline := time.Now().Add(wait)
	for {
		var ready syscall.FdSet
		ready.Bits[fd/64] |= 1 << (uint(fd) % 64)
		left := max(time.Until(deadline), 0)
		timeout := syscall.NsecToTimeval(left.Nanoseconds())
		n, err := syscall.Select(fd+1, &ready, nil, nil, &timeout)
		if err == syscall.EINTR {
			continue
		}
		return err == nil && n > 0
	}
}
