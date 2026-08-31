"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE BINARY DISCIPLINE of the tree -- a writer and a
         reader of little-endian fixed-width integers, length-prefixed
         strings and escaped number streams.

Two files on disk are binary: the coverage record ('coverage/binary.py',
D-20) and the local observation database ('bookkeeper/observation.py',
E-22). Both are spelt by these two classes, so there is one place a
byte order, a string length or an escape is decided. Here, at the
foundation, because the bookkeeper stands below coverage and may not
reach up for it.

THE NUMBER STREAM. A delta-coded sequence is a stream of unsigned bytes
with one ESCAPE: 0x00..0xFE is the number itself, 0xFF says the number
follows as a little-endian uint32. A stream is packed and unpacked in
ONE 'struct' call.
______________________________________________________________________________
"""
import struct

ESCAPE = 0xFF


class CodecFault(Exception):
    """Bytes that do not spell what they claim: a string too long to
    fit, a buffer that ends early, an escape cut short. Each speller
    turns it into its own fault, naming the file."""
    pass


class Writer:
    """Appends to one buffer; every method is one 'struct' call."""

    def __init__(self):
        self.part_list = []

    def u8(self, value):    self.part_list.append(struct.pack("<B", value))
    def u16(self, value):   self.part_list.append(struct.pack("<H", value))
    def u32(self, value):   self.part_list.append(struct.pack("<I", value))

    def string(self, text):
        """RETURN: None. 'str': u16 length, UTF-8 bytes."""
        data = text.encode("utf-8")
        if len(data) > 0xFFFF:
            raise CodecFault("a string of %i bytes does not fit a 'str'"
                              % len(data))
        self.u16(len(data)); self.part_list.append(data)

    def stream(self, number_iterable):
        """RETURN: None. 'stream': u32 count of BYTES, then the escaped
        bytes -- one struct call for the whole sequence."""
        number_list = list(number_iterable)
        if not number_list or max(number_list) < ESCAPE:
            data = bytes(number_list)          # the whole stream, in C
        else:
            byte_list = []
            for value in number_list:
                if value < ESCAPE:
                    byte_list.append(value)
                else:
                    byte_list.append(ESCAPE)
                    byte_list += struct.pack("<I", value)
            data = bytes(byte_list)
        self.u32(len(data))
        self.part_list.append(data)

    def bytes(self):
        """RETURN: bytes, everything written."""
        return b"".join(self.part_list)


class Reader:
    """Reads one buffer front to back; refuses by name at the first
    byte that does not fit."""

    def __init__(self, data):
        self.data = data
        self.at   = 0

    def _take(self, fmt):
        size = struct.calcsize(fmt)
        if self.at + size > len(self.data):
            raise CodecFault("the record ends at byte %i where %i more "
                              "were expected" % (self.at, size))
        value = struct.unpack_from(fmt, self.data, self.at)
        self.at += size
        return value

    def u8(self):   return self._take("<B")[0]
    def u16(self):  return self._take("<H")[0]
    def u32(self):  return self._take("<I")[0]

    def raw(self, n):
        """RETURN: bytes, the next 'n' bytes."""
        if self.at + n > len(self.data):
            raise CodecFault("the record ends at byte %i where %i more "
                              "were expected" % (self.at, n))
        value = self.data[self.at:self.at + n]
        self.at += n
        return value

    def string(self):
        """RETURN: str, one 'str'."""
        return self.raw(self.u16()).decode("utf-8")

    def stream(self):
        """RETURN: list of int, one 'stream' decoded."""
        n    = self.u32()
        data = self.raw(n)
        if ESCAPE not in data:
            return list(data)                  # the whole stream, in C
        out, i = [], 0
        while i < n:
            b = data[i]; i += 1
            if b != ESCAPE:
                out.append(b)
            else:
                if i + 4 > n:
                    raise CodecFault("an escaped number is cut short at "
                                      "byte %i of a stream" % i)
                out.append(struct.unpack_from("<I", data, i)[0])
                i += 4
        return out


#  ----------------------------------------------------------- delta coding

