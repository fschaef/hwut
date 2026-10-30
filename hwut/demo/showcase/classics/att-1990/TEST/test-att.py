#! /usr/bin/env python3
# @hwut {
#     title    = "AT&T (1990): a 'break' that left the whole 'switch' -- one reset cascading through the network"
#     choices {
#         jan-1990    { features = ["network-drawn", "first-steps-told", "cascade-named"]
#                       tolerance { constraints = ["cascade > 0"] } }
#         break-fixed { features = ["network-drawn", "first-steps-told", "no-cascade"]
#                       tolerance { constraints = ["cascade == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  which switches of a long-distance network reset, and when, in the
         60 s after one switch resets -- drawn as a strip per switch
HISTORY  On 15 January 1990 about half of the long-distance calls in AT&T's
network failed for some nine hours. One 4ESS switch in New York reset
after a fault; when it came back it resumed traffic and its neighbours
received its messages. A software update rolled out weeks before had put a
C 'break' inside an 'if' inside a 'case': meant to leave the 'if', it left
the whole 'switch' statement. A neighbour that received a second message
from the recovering switch while still busy with the first skipped setting
up its pointers, worked on with stale ones, overwrote its own data and
reset -- and, coming back, did the same to ITS neighbours. Engineers
stopped the cascade by reducing the message load and returning to the
previous software.

REQUIREMENT  A switch's recovery messages never reset a neighbour: after one
             switch resets, it is the only one that does.

THE UNIT  '../handler.c', C, the incoming-message step, compiled per run
into a shared library (FIXED=0 as shipped, FIXED=1 corrected). 'In
service' is sent to the status map through the write buffer: the map
changes once the buffer is written, when the receiver is no longer busy.

        switch (message) {
        case MSG_INCOMING:
            if (out_of_service[sender]) {
                if (!write_busy) in_service_request[sender] = 1;
                else             break;     /* leaves the SWITCH */
            }
            parameter = parameter_buffer;   /* set up the pointers */
            break;
        }
        if (parameter == 0) return 1;       /* stale: data overwritten */

THE NETWORK  Twelve switches S01..S12, each linked to the switches one and
three places away on a ring (four neighbours). A step is 100 ms. A reset
takes 4 s; meanwhile the neighbours mark the switch out of service. Back,
it sends each neighbour two messages: the first after 0..5 steps, the
second 1..5 steps later -- drawn from DeterministicStream(1990), so the
same on every machine. A message keeps its receiver busy for 3 steps; the
handler is called with 'write_busy' while it is. At t = 0 S01 resets.

WHAT THE TEST PRINTS
  1. THE FIRST STEPS of what happens, one line per reset: when, which
     switch, and the message that reset it.
  2. THE STRIP: one row per switch, one column per second of 60:
     'R' a reset began, '-' down, '.' in service.
  3. The binding '((cascade: N))', the resets after the first one.

CHOICES
    jan-1990     the 'break' as shipped: neighbours of every recovering
                 switch reset in turn; the strip fills with R and -.
    break-fixed  the 'break' gone: S01 resets, comes back, nothing follows.

HOW TO READ THE GOOD  Everything is exact: the timing is drawn, not
measured. A row with a single R and a block of '-' is S01's own reset; any
further R is a reset its recovery caused. Laws: 'cascade > 0' for the
shipped handler -- the violation report --, 'cascade == 0' for the fixed.
______________________________________________________________________________
"""
import ctypes
import heapq
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE        = os.path.dirname(os.path.abspath(__file__))
UNIT        = os.path.join(HERE, "..")
CHOICE_DB   = {"jan-1990": 0, "break-fixed": 1}
SWITCH_N    = 12
STEP_S      = 0.1
DOWN_STEPS  = 40
BUSY_STEPS  = 3
HORIZON     = 600                 # steps: 60 s
FIRST_SHOWN = 8


def build(fixed, scratch):
    """RETURN: ctypes function 'handle' of '../handler.c', compiled with
    FIXED=<fixed> into 'scratch'."""
    library = os.path.join(scratch, "handler-%d.so" % fixed)
    subprocess.run(["gcc", "-O1", "-Wall", "-Werror", "-shared", "-fPIC",
                    "-DFIXED=%d" % fixed, "-o", library,
                    os.path.join(UNIT, "handler.c")], check=True)
    handle = ctypes.CDLL(library).handle
    handle.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int),
                       ctypes.POINTER(ctypes.c_int)]
    handle.restype  = ctypes.c_int
    return handle


def neighbours(i):
    """RETURN: list of int, the switches linked to switch 'i'."""
    return sorted(set((i + d) % SWITCH_N for d in (-3, -1, 1, 3)))


def simulate(handle):
    """
    RETURN: [0] list of (step, switch, sender), every reset in order --
                sender None for the first one
            [1] list of list of str, per switch the state of every step:
                'R' reset begins, '-' down, '.' in service
    """
    stream     = DeterministicStream(1990)
    map_list     = [(ctypes.c_int * SWITCH_N)() for _ in range(SWITCH_N)]
    request_list = [(ctypes.c_int * SWITCH_N)() for _ in range(SWITCH_N)]
    down_until = [-1] * SWITCH_N
    busy_until = [-1] * SWITCH_N
    state      = [["."] * HORIZON for _ in range(SWITCH_N)]
    event_list, reset_list, serial = [], [], [0]

    def push(step, kind, *data):
        serial[0] += 1
        heapq.heappush(event_list, (step, serial[0], kind) + data)

    def reset(step, i, sender):
        reset_list.append((step, i, sender))
        down_until[i] = step + DOWN_STEPS
        for s in range(step, min(step + DOWN_STEPS, HORIZON)):
            state[i][s] = "-"
        if step < HORIZON: state[i][step] = "R"
        for j in neighbours(i):
            map_list[j][i] = 1                     # j marks i out of service
        push(step + DOWN_STEPS, "back", i)

    reset(0, 0, None)
    while event_list:
        step, _, kind, *data = heapq.heappop(event_list)
        if step >= HORIZON: break
        if kind == "back":
            i = data[0]
            for j in neighbours(i):
                first = step + stream.next_int(0, 5)
                push(first, "message", j, i)
                push(first + stream.next_int(1, 5), "message", j, i)
        elif kind == "map":                         # 'in service' written
            j, sender = data
            map_list[j][sender] = 0
        else:
            j, sender = data
            if step < down_until[j]: continue      # a reset switch hears nothing
            busy = 1 if step < busy_until[j] else 0
            busy_until[j] = max(busy_until[j], step) + BUSY_STEPS
            if handle(sender, busy, map_list[j], request_list[j]):
                reset(step, j, sender)
            elif request_list[j][sender]:
                request_list[j][sender] = 0
                push(busy_until[j], "map", j, sender)
    return reset_list, state


def name(i):
    """RETURN: str, the name of switch 'i', 'S01' .. 'S12'."""
    return "S%02d" % (i + 1)


def run(fixed):
    """RETURN: None. Simulates the network with the choice's handler and
    prints the first steps, the strip and the binding."""
    with tempfile.TemporaryDirectory() as scratch:
        reset_list, state = simulate(build(fixed, scratch))
    print("handler.c FIXED=%d   %d switches, 4 neighbours each   S01 resets at t = 0"
          % (fixed, SWITCH_N))
    print()
    print("1. THE FIRST STEPS")
    print("##! verbatim")
    for step, i, sender in reset_list[:FIRST_SHOWN]:
        why = "the first fault" if sender is None else \
              "second message from %s while busy with the first" % name(sender)
        print("   t = %5.1f s   %s resets   (%s)" % (step * STEP_S, name(i), why))
    if len(reset_list) > FIRST_SHOWN:
        print("   ... %d resets more" % (len(reset_list) - FIRST_SHOWN))
    if len(reset_list) == 1:
        print("   t = %5.1f s   S01 back in service; its neighbours process its messages"
              % (DOWN_STEPS * STEP_S))
    print("####")
    print()
    print("2. THE STRIP, one column per second ('R' reset begins, '-' down, '.' in service)")
    print("##! verbatim")
    print("       0         10        20        30        40        50        60 s")
    for i in range(SWITCH_N):
        row = ""
        for second in range(HORIZON // 10):
            cell = state[i][second * 10:second * 10 + 10]
            row += "R" if "R" in cell else "-" if "-" in cell else "."
        print("   %s %s" % (name(i), row))
    print("####")
    cascade = len(reset_list) - 1
    hit = len(set(i for _, i, _ in reset_list))
    print()
    print("switches that reset: %d of %d" % (hit, SWITCH_N))
    print("resets after the first ((cascade: %d))   law == 0   %s"
          % (cascade, "kept" if cascade == 0 else "BROKEN"))


choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_DB:
    print("choices: %s" % ", ".join(CHOICE_DB))
    sys.exit(1)
run(CHOICE_DB[choice])
print("<hwut-end>")
