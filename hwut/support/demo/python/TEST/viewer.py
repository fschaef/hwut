#! /usr/bin/env python3
"""
______________________________________________________________________________
A TERMINAL FILE VIEWER -- the program 'screen.py' tests; no test itself.

    viewer.py <file>

Full screen, on the terminal's alternate screen: a title bar (reverse
video), as many lines of the file as fit, and a status line: the keys
flush left, the lines shown flush right. Keys: 'j' or down one line
further, 'k' or up one line back, 'q' quits.
______________________________________________________________________________
"""
import os
import sys
import termios
import tty


def draw(out, name, line_list, top, row_n, column_n):
    """RETURN: None. Draws the whole screen with the file's line 'top'
    first."""
    body_n = row_n - 2
    shown  = line_list[top:top + body_n]
    out.write("\x1b[H\x1b[2J")
    out.write("\x1b[7m%s\x1b[0m\r\n" % (" " + name).ljust(column_n)[:column_n])
    for line in shown:
        out.write(line[:column_n] + "\r\n")
    out.write("\r\n" * (body_n - len(shown)))
    where  = "lines %d-%d of %d" % (top + 1, top + len(shown), len(line_list))
    keys   = "j k q"
    out.write("\x1b[%d;1H%s%s" % (row_n, keys, where.rjust(column_n - 1 - len(keys))))
    out.flush()


def main(path):
    """RETURN: int, 0 once 'q' was pressed."""
    with open(path) as fh:
        line_list = fh.read().splitlines()
    column_n, row_n = os.get_terminal_size(sys.stdout.fileno())
    out, fd = sys.stdout, sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)
    out.write("\x1b[?1049h")
    top = 0
    try:
        while True:
            draw(out, os.path.basename(path), line_list, top, row_n, column_n)
            key = os.read(fd, 8)
            if   key == b"q":                 break
            elif key in (b"j", b"\x1b[B"):    top = min(top + 1, max(0, len(line_list) - (row_n - 2)))
            elif key in (b"k", b"\x1b[A"):    top = max(top - 1, 0)
    finally:
        out.write("\x1b[?1049l")
        out.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
