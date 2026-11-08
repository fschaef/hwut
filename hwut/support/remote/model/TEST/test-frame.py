#! /usr/bin/env python3
#
# @hwut {
#     title   = "LinkHub against a fake link: the session and its ladder"
#     choices = [ "session", "corrupt", "lost_command", "lost_reply", "late", "echoed",
#                 "stale", "restarted", "busy", "silent", "duplicate", "p",
#                 "killed" ]
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Every case of PROTOCOL.txt's ladder, played against a model agent
         through a fake link that loses, corrupts, delays, doubles and
         restarts on purpose (spec/26 delivery step 1).

CHOICES: session, corrupt, lost_command, lost_reply, late, echoed, stale,
         restarted, busy, silent, duplicate, p, killed;

Each choice prints what the writer sees -- the '##' lines through 'note',
the rows, the exception that fails the choice -- and then the wire, every
line host and agent exchanged, with the fault marked. The token sequence is
fixed by seeding 'random'; nothing here reads a clock into the picture.

    session       the session of README 20: hello, reset, three vectors
    corrupt       the reply's CRC fails: noise; 'r 18 4' finds it acted
    lost_command  the 'x' never arrives: 'r 18 4' finds the previous last;
                  resent with a new token
    lost_reply    the 'x' acted, its reply is lost: 'r 18 4' gives the reply
    late          the reply comes after the next line: noted, discarded
    echoed        the link echoes: "no agent: link echoes"
    stale         the agent runs another image: "stale agent"
    restarted     the agent restarts mid-session: fresh = 1 -> bench reset,
                  reopen, hello, the choice fails
    busy          '! busy': wait one deadline, resend
    silent        three failures in a row: silent -> bench reset; the agent
                  still silent; the choice fails
    duplicate     the 'x' arrives twice: the second does not apply (a
                  counting UUT shows it)
    p             the reserved verb 'p': '! unknown', raised
    killed        hwut's watchdog ends a test whose UUT hangs: the 'x' waits
                  without bound (agent timeout 0), SIGTERM arrives, the hub
                  sends 'k', the agent aborts and answers, the link closes,
                  the process dies by SIGTERM (intend o-44, o-46)
______________________________________________________________________________
"""
import os
import random
import signal
import subprocess
import sys

import config                                          # noqa: F401
from   config      import HwutRunner
from   fake_agent  import Agent, FakeLink, IMAGE_ID
from   hwut_remote import entry, LinkHub, HubError

VECTORS = [(0x03, 0x04), (0xff, 0x01), (0xff, 0xff)]


def note(text):
    """RETURN: None. A '##' line."""
    print("##", text)


def hub_over(link, image_id=None):
    """RETURN: LinkHub over 'link', wall time, deadlines of 0.05 s."""
    values = entry.check_common("launch", {"launch": "fake", "boot": 0.3,
                                           "link_margin": 0.05})
    hub = LinkHub(link, values, note, "launch")
    return hub.expect(image_id=image_id)


def session(plan=None, agent=None, image_id=IMAGE_ID, vectors=VECTORS,
            echo_f=False, more=None):
    """RETURN: None. One session -- hello, reset, the vectors -- over a fake
    link with 'plan''s faults; the rows, the failure, then the wire."""
    random.seed(7)
    link = FakeLink(agent or Agent(), plan, echo_f=echo_f)
    try:
        with hub_over(link, image_id) as hub:
            hub.reset()
            for a, b in vectors:
                print("%02x%02x %03x" % (a, b, hub.vector((a << 8) | b)))
            if more is not None: more(hub)
    except HubError as error:
        print("FAILED: %s: %s" % (type(error).__name__, error))
    print("wire:")
    previous = None
    for text in link.wire:
        if text == previous:
            if not repeated_f: print("    ... repeated until 'boot' ends")
            repeated_f = True
            continue
        previous, repeated_f = text, False
        print("   ", text)


def counting():
    """RETURN: callable, a UUT whose report counts the applies."""
    count = [0]

    def uut(stim):
        count[0] += 1
        return bytes([count[0], 0])
    return uut


def run_p(hub):
    """RETURN: None. The reserved verb 'p' sent."""
    hub._command("p")


def hung():
    """RETURN: never. The child of 'killed': a session whose UUT hangs,
    waiting for SIGTERM."""
    random.seed(7)
    link = FakeLink(Agent(hang_f=True, timeout=0), live_f=True)
    with hub_over(link) as hub:
        hub.reset()
        print("## waiting for the UUT", flush=True)
        hub.vector(0x0403)


def run_killed():
    """RETURN: None. The child started, SIGTERM sent once it waits; what it
    printed and how it ended."""
    child = subprocess.Popen([sys.executable, os.path.abspath(__file__),
                              "--hung"], stdout=subprocess.PIPE, text=True)
    output = []
    for text in child.stdout:
        output.append(text.rstrip("\n"))
        if text.startswith("    wire: --> ") and " x " in text:
            child.send_signal(signal.SIGTERM)      # the 'x' is out: it hangs
    child.wait()
    for text in output: print(text)
    print("ended by: %s" % (signal.Signals(-child.returncode).name
                            if child.returncode < 0
                            else "exit %i" % child.returncode))


if sys.argv[1:] == ["--hung"]:
    hung()

HwutRunner(sys.argv, "LinkHub against a fake link: the session and its ladder;", {
    "session":      lambda: session(),
    "corrupt":      lambda: session({2: "corrupt_reply"}),
    "lost_command": lambda: session({3: "drop_command"}),
    "lost_reply":   lambda: session({2: "drop_reply"}),
    "late":         lambda: session({2: "late_reply"}),
    "echoed":       lambda: session(echo_f=True),
    "stale":        lambda: session(agent=Agent(image=0x12345678)),
    "restarted":    lambda: session({3: "restart"}),
    "busy":         lambda: session({2: "busy"}),
    "silent":       lambda: session({2: "silent"}),
    "duplicate":    lambda: session({2: "duplicate"}, agent=Agent(uut=counting())),
    "p":            lambda: session(vectors=[], more=run_p),
    "killed":       run_killed,
}).run()
