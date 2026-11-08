"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE LINE -- token, CRC-16, the 80-byte line, noise (PROTOCOL.txt 2).

        b x 0403 *2b95\\n
        | | \\__/  \\__/
        | |  |     +-- CRC-16/CCITT-FALSE over "b x 0403"
        | |  +-------- bytes in address order
        | +----------- verb
        +------------- token 0..f

'encode' builds a line; 'Reader' cuts a byte stream into verified lines
and counts the noise between them. Nothing here knows a verb.
______________________________________________________________________________
"""

LINE_MAX     = 80                      # bytes, trailer and '\n' included
_ALPHABET    = frozenset(b"abcdefghijklmnopqrstuvwxyz0123456789 !*\n")
_HEX         = frozenset("0123456789abcdef")


def crc16(data):
    """
    RETURN: int, the CRC-16/CCITT-FALSE of 'data' (poly 0x1021, init
            0xffff, no reflection, xorout 0): crc16(b"123456789") = 0x29b1.
    """
    crc = 0xffff
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xffff if crc & 0x8000 \
                  else (crc << 1) & 0xffff
    return crc


def encode(token, body):
    """
    RETURN: bytes, the line 'TOKEN BODY *CRC\\n' for 'token' (0..15) and
            'body' (str), the CRC over 'TOKEN BODY' as transmitted.
            ValueError, where the token is out of range or the line would
            exceed LINE_MAX.
    """
    if not 0 <= token <= 15: raise ValueError("token %r out of 0..f" % token)
    head = "%x %s" % (token, body)
    line = ("%s *%04x\n" % (head, crc16(head.encode("ascii")))).encode("ascii")
    if len(line) > LINE_MAX:
        raise ValueError("line of %i bytes exceeds %i" % (len(line), LINE_MAX))
    return line


def hex_bytes(data):
    """
    RETURN: str, 'data' as contiguous lowercase hex digit pairs, in order.
    """
    return bytes(data).hex()


def parse_bytes(text):
    """
    RETURN: bytes, the hex digit pairs of 'text' read in order, if 'text'
            is a non-empty even run of lowercase hex digits;
            None, else.
    """
    if not text or len(text) % 2 or not set(text) <= _HEX: return None
    return bytes.fromhex(text)


class Reader:
    """Cuts a byte stream into verified lines.

    A line is verified when it is at most LINE_MAX bytes, holds only the
    alphabet [a-z0-9 !*\\n], has the shape 'TOKEN BODY *CRC' and its CRC
    holds. Everything else is NOISE: counted, never answered. An empty
    line flushes a partial one and is not noise.

    'discarded_line_n', 'discarded_byte_n' count the noise; 'noise_list'
    keeps the last discarded lines (bytes) for an echo check.
    """

    def __init__(self):
        """RETURN: None. An empty reader."""
        self._buffer          = bytearray()
        self.discarded_line_n = 0
        self.discarded_byte_n = 0
        self.noise_list       = []

    def feed(self, data):
        """
        RETURN: list of (token, body): every verified line completed by
                'data', in order; the noise is counted.
        """
        result = []
        for byte in data:
            self._buffer.append(byte)
            if byte != 0x0a: continue
            raw = bytes(self._buffer)
            self._buffer.clear()
            if raw == b"\n": continue
            verified = _verified(raw)
            if verified is None: self._discard(raw)
            else:                result.append(verified)
        return result

    def _discard(self, raw):
        """RETURN: None. 'raw' counted as noise."""
        self.discarded_line_n += 1
        self.discarded_byte_n += len(raw)
        self.noise_list = (self.noise_list + [raw])[-8:]


def _verified(raw):
    """
    RETURN: (int, str), the token and body of 'raw' (one line, '\\n'
            included), if it is a verified line;
            None, else.
    """
    if len(raw) > LINE_MAX or not set(raw) <= _ALPHABET: return None
    text = raw[:-1].decode("ascii")
    head, sep, crc = text.rpartition(" *")
    if not sep or len(crc) != 4 or not set(crc) <= _HEX: return None
    if crc16(head.encode("ascii")) != int(crc, 16):      return None
    if len(head) < 3 or head[1] != " " or head[0] not in _HEX: return None
    body = head[2:]
    if not _body_f(body): return None
    return int(head[0], 16), body


def _body_f(body):
    """
    RETURN: bool, True if 'body' is words of [a-z0-9]+ separated by single
            spaces, or '!' and one such word;
            False, else.
    """
    word_list = body.split(" ")
    if word_list[0] == "!":
        word_list = word_list[1:]
        if len(word_list) != 1: return False
    return bool(word_list) and all(w and w.isalnum() and w == w.lower()
                                   and w.isascii() for w in word_list)
