#! /usr/bin/env python3
#
# @hwut {
#     title   = "The Verilog agent under iverilog"
#     choices = [ "session", "oracle", "duplicate", "refusals", "noise",
#                 "timeout", "wait", "outcome02", "uart" ]
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The Verilog agent (agent.v, phy_stdio.v) proven under iverilog, on
         every host (spec/26 delivery step 2; MAP.txt, PROTOCOL.txt).

CHOICES: session, oracle, duplicate, refusals, noise, timeout, wait,
         outcome02, uart;

    session    the session of README 20 through hwut_remote: hello, reset,
               the adder's three vectors
    oracle     THE 'x' ORACLE: the reply to 'x' equals the bytes of the
               following 'r 19 1+RW', vector after vector
    duplicate  a duplicate 'x' -- its token equals 'last' -- returns the same
               bytes and does not apply: a UUT counting its applies says 1
    refusals   '! unknown', '! syntax', '! limit' as MAP.txt 1 and
               PROTOCOL.txt 4 list them; none acts ('last' unchanged)
    noise      a CRC that fails, a byte outside the alphabet, a line over 80
               bytes: never answered, counted at map 0f
    timeout    'w 14' below max(LATENCY, RESET_CYCLES) refused; above, taken
    wait       mode 0: the agent waits for 'done' to rise
    outcome02  mode 0, 'done' later than 'timeout' cycles: outcome 02, the
               row 'timeout'
    uart       the session over phy_uart.v: a behavioural bridge turns the
               simulator's stdio into UART waveforms (top_uart.v)

The lines are sent raw where the host would never send them (a duplicate,
a malformed body). Each choice compiles its own top (TMP/), so no choice
depends on another. Without iverilog a choice exits 77: the infrastructure
this case needs is absent.
______________________________________________________________________________
"""
import os
import random
import shutil
import subprocess
import sys
import time

import config                                          # noqa: F401
from   config      import HwutRunner
from   hwut_remote import create_hub, line, link, TIMEOUT
from   hwut_remote.session import absent

HERE   = os.path.dirname(os.path.abspath(__file__))


def note(text):
    """RETURN: None. A '##' line."""
    print("##", text)


def build(name, *define, top="top.v", phy="phy_stdio.v"):
    """
    RETURN: str, the command that runs the top compiled with 'define's
            into TMP/<name>.vvp; exit 77 where iverilog is not installed.
    """
    if shutil.which("iverilog") is None or shutil.which("vvp") is None:
        absent("iverilog: not installed (the 'iverilog' package)")
    os.makedirs(os.path.join(HERE, "TMP"), exist_ok=True)
    target = os.path.join(HERE, "TMP", "%s.vvp" % name)
    flag   = ["-D%s" % d for d in define]
    if not any(d.startswith("TIMEOUT=") for d in define):
        flag.append("-DTIMEOUT=10000000")
    source = [os.path.join(HERE, top), os.path.join(HERE, "..", "agent.v"),
              os.path.join(HERE, "..", phy)]
    subprocess.run(["iverilog", "-g2005", "-o", target] + flag + source,
                   check=True)
    return "vvp -n %s" % target


class Raw:
    """The agent's stdio, line by line, without the host's ladder."""

    def __init__(self, command):
        """RETURN: None. The simulator started; its stdio is the link."""
        self.link = link.ProcessLink(command.split())
        self.link.open()
        self.reader = line.Reader()
        self.pending = []

    def send(self, token, body):
        """RETURN: str, the body of the reply with 'token'; None if none
        came within 10 s (the agent does not answer noise)."""
        self.link.send(line.encode(token, body))
        return self.wait(token)

    def send_raw(self, raw, token):
        """RETURN: str | None, the reply to the raw bytes 'raw'."""
        self.link.send(raw)
        return self.wait(token, 1.0)

    def wait(self, token, seconds=10.0):
        """RETURN: str | None, the next reply body with 'token'."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for tok, body in self.pending:
                if tok == token:
                    self.pending.remove((tok, body))
                    return body
            self.pending.extend(self.reader.feed(self.link.recv(deadline)))
        return None

    def close(self):
        """RETURN: None."""
        self.link.close()


def hub(command):
    """RETURN: Hub over the simulator, virtual time."""
    random.seed(7)
    return create_hub("launch", command, time="virtual", boot=1.0,
                      note=note, image_id=0x3f9a07c1)


def run_session():
    """RETURN: None. README 20's session."""
    with hub(build("adder")) as h:
        h.reset()
        print(h.contract())
        print("## stim = a[15:8] b[7:0]   report = sum[8:0]")
        for a, b in [(0x03, 0x04), (0xff, 0x01), (0xff, 0xff)]:
            print("%02x%02x %03x" % (a, b, h.vector((a << 8) | b)))


def run_oracle():
    """RETURN: None. Reply to 'x' against the following 'r 19 3'."""
    agent = Raw(build("adder"))
    print("hello  ", agent.send(1, "r 0 1a"))
    print("reset  ", agent.send(2, "w 3f 01"))
    token = 3
    for stim in ["0403", "01ff", "ffff", "0000", "8080"]:
        reply = agent.send(token, "x %s" % stim)
        read  = agent.send((token + 1) % 16, "r 19 3")
        print("x %s -> %-8s r 19 3 -> %-8s %s"
              % (stim, reply, read, "equal" if reply == read else "DIFFER"))
        token = (token + 2) % 16
    agent.close()


def run_duplicate():
    """RETURN: None. The same 'x' twice under one token; a counting UUT."""
    agent = Raw(build("counter", "COUNTER"))
    agent.send(1, "r 0 1a")
    print("reset          ", agent.send(2, "w 3f 01"))
    print("x 0102, token 5", agent.send(5, "x 0102"))
    print("x 0102, token 5", agent.send(5, "x 0102"), "(duplicate)")
    print("r 18 4         ", agent.send(6, "r 18 4"))
    print("x 0102, token 7", agent.send(7, "x 0102"))
    print("w 40 0000, tok 8", agent.send(8, "w 40 0000"))
    print("w 40 0000, tok 8", agent.send(8, "w 40 0000"), "(duplicate)")
    print("r 40 2         ", agent.send(9, "r 40 2"))
    agent.close()


def run_refusals():
    """RETURN: None. Each refusal; 'last' read after them."""
    agent = Raw(build("adder"))
    agent.send(1, "r 0 1a")
    agent.send(2, "w 3f 01")
    for token, body in [(3, "p"), (4, "q 0 1"), (5, "rr 0 1"), (6, "r 0"),
                        (7, "r 0 1 2"), (8, "r 0g 1"), (9, "w 40 040"),
                        (10, "x 04"), (11, "x 040302"), (12, "r 0 0"),
                        (13, "r 0 24"), (14, "r 3f 1"), (15, "r 1b 2"),
                        (3, "w 0 00"), (4, "w 3f 0102"), (5, "r 100 1"),
                        (6, "r 10000 1"), (7, "w 41 0102")]:
        print("%-12s -> %s" % (body, agent.send(token, body)))
    print("%-12s -> %s   (last 02: nothing acted)"
          % ("r 18 2", agent.send(8, "r 18 2")))
    agent.close()


def run_noise():
    """RETURN: None. Lines the agent must not answer; map 0f counts them."""
    agent = Raw(build("adder"))
    agent.send(1, "r 0 1a")
    good = line.encode(2, "r 0 4")
    for name, raw in [("crc fails",        good.replace(b"r 0 4", b"r 0 5")),
                      ("outside alphabet", b"2 R 0 4 *0000\n"),
                      ("over 80 bytes",    b"2 " + b"a" * 80 + b"\n"),
                      ("carriage return",  good[:-1] + b"\r\n"),
                      ("trailer missing",  b"2 r 0 4\n")]:
        print("%-16s -> %s" % (name, agent.send_raw(raw, 2)))
    print("%-16s -> %s   (5 lines discarded)"
          % ("r f 1", agent.send(3, "r f 1")))
    agent.close()


def run_timeout():
    """RETURN: None. 'timeout' written below and above its floor."""
    agent = Raw(build("adder"))
    agent.send(1, "r 0 1a")
    agent.send(2, "w 3f 01")
    for token, body in [(3, "w 14 03000000"), (4, "w 14 04000000"),
                        (5, "r 14 4"), (6, "w 14 80969800"),
                        (7, "r 14 4")]:
        print("%-14s -> %s" % (body, agent.send(token, body)))
    agent.close()


def run_wait():
    """RETURN: None. Mode 0: 'done' rises 5 cycles after apply."""
    with hub(build("slow", "SLOW", "DONE_AFTER=5")) as h:
        h.reset()
        print(h.contract())
        for a, b in [(0x03, 0x04), (0xff, 0xff)]:
            print("%02x%02x %03x" % (a, b, h.vector((a << 8) | b)))


def run_outcome02():
    """RETURN: None. Mode 0, 'done' after 50 cycles, 'timeout' 20."""
    with hub(build("late", "SLOW", "DONE_AFTER=50", "TIMEOUT=20")) as h:
        h.reset()
        print(h.contract())
        result = h.vector(0x0304)
        print("0304 %s" % ("timeout" if result is TIMEOUT else "%03x" % result))
        print("0304 {:03x}".format(result))


def run_uart():
    """RETURN: None. README 20's session over the UART phy."""
    with hub(build("uart", top="top_uart.v", phy="phy_uart.v")) as h:
        h.reset()
        print(h.contract())
        for a, b in [(0x03, 0x04), (0xff, 0x01), (0xff, 0xff)]:
            print("%02x%02x %03x" % (a, b, h.vector((a << 8) | b)))


HwutRunner(sys.argv, "The Verilog agent under iverilog;", {
    "session":   run_session,
    "oracle":    run_oracle,
    "duplicate": run_duplicate,
    "refusals":  run_refusals,
    "noise":     run_noise,
    "timeout":   run_timeout,
    "wait":      run_wait,
    "outcome02": run_outcome02,
    "uart":      run_uart,
}).run()
