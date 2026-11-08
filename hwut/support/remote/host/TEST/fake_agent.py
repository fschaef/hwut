"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A FAKE LINK TO A MODEL AGENT, with faults injected on purpose --
         what 'test-frame.py' and 'test-plugin.py' drive LinkHub against.

    agent = Agent(uut=adder)            the map of MAP.txt, an 8-bit adder
    link  = FakeLink(agent, plan)       'plan': command index -> a fault

The agent answers as MAP.txt and PROTOCOL.txt say: noise counted, a
duplicate 'w' or 'x' does not act, every reply the content of a read.
Every line on the wire is recorded in 'link.wire' for the picture.

FAULTS (by the index of the line the host sends, 0 = the hello):

    drop_command   the agent never sees the line
    drop_reply     the agent acts; its reply is lost
    corrupt_reply  the reply's last report digit is flipped (CRC fails)
    late_reply     the reply arrives only after the host's next line
    restart        the agent restarts before it reads the line
    busy           the agent answers '! busy' and does not act
    silent         the agent stops answering, from this line on
    duplicate      the line arrives twice
______________________________________________________________________________
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hwut_remote      import line as line_            # noqa: E402
from hwut_remote.link import Link                     # noqa: E402

IMAGE_ID = 0x3f9a07c1


def adder(stim):
    """RETURN: bytes, the report of an 8-bit adder: a = stim[1], b = stim[0],
    sum[8:0] little-endian in two bytes."""
    total = stim[0] + stim[1]
    return bytes([total & 0xff, total >> 8])


class Agent:
    """The map and the verbs of MAP.txt, in Python, for a fake link."""

    def __init__(self, uut=adder, sw=2, rw=2, image=IMAGE_ID, latency=1,
                 clock=50_000_000, timeout=10_000_000, proto=1):
        """RETURN: None. An agent at its start: last ff, fresh 1."""
        self.uut, self.sw, self.rw = uut, sw, rw
        self.image, self.latency   = image, latency
        self.clock, self.proto     = clock, proto
        self.timeout_start         = timeout
        self.start()

    def start(self):
        """RETURN: None. Agent start: last ff, status 80 (fresh), the report
        zero, the noise count zero."""
        self.last     = 0xff
        self.status   = 0x80
        self.report   = bytes(self.rw)
        self.stim     = bytes(self.sw)
        self.timeout  = self.timeout_start
        self.discard  = 0
        self.reader   = line_.Reader()

    def mode(self):
        """RETURN: int, the mode byte: [0] sample, [7:2] LATENCY (o-42)."""
        return (self.latency << 2) | (1 if self.latency else 0)

    def map_bytes(self):
        """RETURN: bytes, offsets 00 .. 19 + RW of the map."""
        head = (b"hwut" + self.proto.to_bytes(4, "little")
                + self.image.to_bytes(4, "little")
                + bytes([self.sw, self.rw, self.mode(), min(self.discard, 0xff)])
                + self.clock.to_bytes(4, "little")
                + self.timeout.to_bytes(4, "little")
                + bytes([self.last, self.status]))
        return head + self.report

    def receive(self, data):
        """RETURN: list of bytes, the reply lines to the lines in 'data'."""
        before   = self.reader.discarded_line_n
        verified = self.reader.feed(data)
        self.discard += self.reader.discarded_line_n - before
        return [line_.encode(token, self.answer(token, body))
                for token, body in verified]

    def answer(self, token, body):
        """RETURN: str, the reply body to the verified line 'token body'."""
        word = body.split(" ")
        verb = word[0]
        if verb == "r" and len(word) == 3: return self.read(word[1], word[2])
        if verb == "w" and len(word) == 3: return self.write(token, word[1],
                                                             word[2])
        if verb == "x" and len(word) == 2: return self.apply(token, word[1])
        if verb in ("r", "w", "x"):        return "! syntax"
        return "! unknown"

    def read(self, address, length):
        """RETURN: str, the hex of 'r address length', or a refusal."""
        try:
            address, length = int(address, 16), int(length, 16)
        except ValueError:
            return "! syntax"
        data = self.map_bytes()
        if length == 0 or length > 35 or address + length > len(data):
            return "! limit"
        return line_.hex_bytes(data[address:address + length])

    def write(self, token, address, text):
        """RETURN: str, the status after 'w address bytes', or a refusal."""
        data = line_.parse_bytes(text)
        try:
            address = int(address, 16)
        except ValueError:
            return "! syntax"
        if data is None: return "! syntax"
        if token == self.last: return "%02x" % self.status    # duplicate
        if address == 0x3f and len(data) == 1:
            self.last   = token
            self.status = 0x00                     # outcome 00, fresh 0
            return "%02x" % self.status
        if address == 0x14 and len(data) == 4:
            self.last    = token
            self.timeout = int.from_bytes(data, "little")
            return "%02x" % self.status
        if address == 0x40 and len(data) == self.sw:
            self.last = token
            self.stim = data
            return "%02x" % self.status
        return "! limit"

    def apply(self, token, text):
        """RETURN: str, status and report after 'x bytes', or a refusal."""
        data = line_.parse_bytes(text)
        if data is None:          return "! syntax"
        if len(data) != self.sw:  return "! limit"
        if token != self.last:                     # a duplicate never acts
            self.last   = token
            self.stim   = data
            self.report = self.uut(data)
            self.status = (self.status & 0x80) | 0x01
        return "%02x%s" % (self.status, line_.hex_bytes(self.report))


class FakeLink(Link):
    """A Link to an Agent in this process; 'plan' injects faults by the
    index of the line the host sends; 'echo_f' makes the link echo every
    line and the agent never answer."""

    def __init__(self, agent, plan=None, echo_f=False, eof_at=None):
        """RETURN: None."""
        self.agent   = agent
        self.plan    = dict(plan or {})
        self.echo_f  = echo_f
        self.eof_at  = eof_at
        self.queue   = bytearray()
        self.later   = []
        self.index   = -1
        self.silent  = False
        self.wire    = []
        self.open_n  = 0

    def open(self):
        """RETURN: None. The agent starts on every open (a launch)."""
        self.open_n += 1
        self.agent.start()
        self.queue.clear()
        self.later = []

    def send(self, data):
        """RETURN: None. Each line of 'data' to the agent, faults applied."""
        for raw in data.split(b"\n")[:-1]:
            raw += b"\n"
            if raw == b"\n": continue
            self.index += 1
            if self.eof_at is not None and self.index >= self.eof_at:
                raise EOFError("the process ended")
            fault = self.plan.get(self.index)
            self.wire.append("--> %s%s" % (raw.decode().rstrip(),
                                          "   [%s]" % fault if fault else ""))
            self.queue += b"".join(self.later)
            for reply in self.later:
                self.wire.append("<-- %s   [late]" % reply.decode().rstrip())
            self.later = []
            if self.echo_f:
                self.queue += raw
                continue
            if fault == "restart":
                self.agent.start()
            if fault in ("drop_command",) or self.silent: continue
            if fault == "silent":
                self.silent = True
                continue
            if fault == "busy":
                token = int(raw[:1], 16)
                reply_list = [line_.encode(token, "! busy")]
            else:
                reply_list = self.agent.receive(raw)
                if fault == "duplicate": reply_list += self.agent.receive(raw)
            for reply in reply_list:
                self._deliver(reply, fault)

    def _deliver(self, reply, fault):
        """RETURN: None. 'reply' queued, lost, corrupted or held back."""
        text = reply.decode().rstrip()
        if fault == "drop_reply":
            self.wire.append("<-X %s   [lost]" % text)
            return
        if fault == "corrupt_reply":
            head, _, crc = text.rpartition(" *")
            last = "0" if head[-1] != "0" else "1"
            text = head[:-1] + last + " *" + crc
            reply = (text + "\n").encode()
        if fault == "late_reply":
            self.later.append(reply)
            self.wire.append("<.. %s   [held]" % text)
            return
        self.wire.append("<-- %s" % text)
        self.queue += reply

    def recv(self, deadline):
        """RETURN: bytes queued; else b"" once 'deadline' passed."""
        if self.queue:
            data = bytes(self.queue)
            self.queue.clear()
            return data
        remaining = deadline - time.monotonic()
        if remaining > 0: time.sleep(min(remaining, 0.05))
        return b""

    def close(self):
        """RETURN: None."""
        self.wire.append("--- close")
