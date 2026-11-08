#! /usr/bin/env python3
#
# @hwut {
#     title   = "The line: CRC-16, encoding, noise"
#     choices = [ "crc", "encode", "noise", "bytes" ]
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The line of PROTOCOL.txt 2 against its check values (spec/26
         delivery step 1).

CHOICES: crc, encode, noise, bytes;

    crc      CRC-16/CCITT-FALSE: check("123456789") = 29b1, and every line
             the documents print, COMPUTED here: a document's CRC is never
             typed
    encode   lines built from token and body; a token out of 0..f and a
             line over 80 bytes refused
    noise    the Reader: a verified line; a CRC that fails; a line over 80
             bytes; '\\r'; a byte outside the alphabet; a malformed body; an
             empty line flushing a partial one -- each counted
    bytes    hex digit pairs read and written in address order
______________________________________________________________________________
"""
import sys

import config                                          # noqa: F401
from   config      import HwutRunner
from   hwut_remote import line

DOCUMENT_LINES = [
    "b x 0403", "b 010700", "6 x ffff", "6 01fe01", "6 01fe03", "7 r 18 4",
    "7 0601fe01", "3 x 0403", "4 r 18 4", "4 02010700", "5 x 0403",
    "5 010700", "8 x 0403", "8 810700", "9 r 0 1a",
    "9 6877757401000000c1079a3f0202010080f0fa0280969800ff80",
    "a w 3f 01", "a 00", "c x 01ff", "c 010001", "d x ffff", "d 01fe01",
    "7 k", "7 00",
]


def run_crc():
    """RETURN: None. The check value, then every documented line's CRC."""
    print("check(\"123456789\") = %04x" % line.crc16(b"123456789"))
    for text in DOCUMENT_LINES:
        print("crc(%-58s) = %04x" % ('"%s"' % text, line.crc16(text.encode())))


def run_encode():
    """RETURN: None. Lines encoded; the two refusals."""
    for token, body in [(0xb, "x 0403"), (0, "r 0 1a"), (0xf, "! busy")]:
        print(repr(line.encode(token, body)))
    for token, body in [(16, "r 0 1"), (1, "x " + "ab" * 40)]:
        try:
            line.encode(token, body)
        except ValueError as error:
            print("refused:", error)


def run_noise():
    """RETURN: None. One stream through the Reader: what is verified, what
    is counted."""
    good = line.encode(0xb, "010700")
    case_list = [
        ("verified",          good),
        ("crc fails",         good.replace(b"0107", b"0108")),
        ("over 80 bytes",     _long_line()),
        ("carriage return",   good[:-1] + b"\r\n"),
        ("outside alphabet",  b"b X 0403 *2b95\n"),
        ("malformed body",    line.encode(2, "x  0403")),
        ("empty line",        b"\n"),
        ("partial, flushed",  b"b x 04"),
        ("verified after",    line.encode(0xc, "010001")),
    ]
    reader = line.Reader()
    for name, raw in case_list:
        found = reader.feed(raw if name != "partial, flushed" else raw + b"\n")
        print("%-17s -> %-24s lines %i, bytes %i"
              % (name, found, reader.discarded_line_n,
                 reader.discarded_byte_n))


def _long_line():
    """RETURN: bytes, a line of 81 bytes whose CRC holds."""
    head = "1 " + "ab" * 36 + "c"
    return ("%s *%04x\n" % (head, line.crc16(head.encode()))).encode()


def run_bytes():
    """RETURN: None. Bytes to hex and back; what is no byte run."""
    print(line.hex_bytes(bytes([0x04, 0x03])), line.hex_bytes(b"hwut"))
    for text in ["0403", "6877", "", "040", "04G3", "04 03"]:
        print("%-6r -> %r" % (text, line.parse_bytes(text)))


HwutRunner(sys.argv, "The line: CRC-16, encoding, noise;", {
    "crc":    run_crc,
    "encode": run_encode,
    "noise":  run_noise,
    "bytes":  run_bytes,
}).run()
