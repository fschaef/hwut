#! /usr/bin/env python3
# @hwut {
#     title    = "Apollo 11: counter increments steal memory cycles (AGC sequencer in Verilog, under Verilator)"
#     features = ["every-pulse-counted", "priority-order", "cycle-budget"]
#     choices {
#         rr-quiet   { tolerance { constraints = ["lost == 0", "stolen <= 100 ms"] } }
#         rr-phase   { tolerance { constraints = ["lost == 0", "stolen > 100 ms"] } }
#         clear-all  { features = ["every-pulse-counted", "lost-named"]
#                      tolerance { constraints = ["lost > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the memory cycles of one second of flight as the AGC counter
         sequencer (../counters*.v, verilated) spends them: a timeline of
         pulses and stolen cycles, and per counter the pulses in, counted
         and lost
REQUIREMENT  R1 every pulse that reaches a counter is counted, none is lost;
             R2 a waiting counter is served by priority TIME1 > CDUT > CDUS,
                one per memory cycle -- every cycle as the reference model
                (one latch per counter, cleared when it is served) spends it;
             R3 counting takes at most 100 ms of memory cycles per second
                (10 %: the budget assumed here for the program's spare time).

THE APOLLO 11 STORY. During the lunar descent the guidance computer raised
1202 and 1201 alarms: the Executive had no core set (1202) or VAC area (1201)
left for a new job, because the jobs did not finish in time. A large part of
the missing time was stolen by counters. The rendezvous radar's angle
counters (CDUT, CDUS) were fed by CDUs whose 800 Hz excitation was not
phase-locked to the computer's; they then pulsed at their maximum rate,
6400 pulses per second each, although the antenna stood still. An AGC pulse
does not interrupt the program: it sets a pending latch, and the sequencer
steals the next memory cycle (11.72 us) to increment the counter cell. Two
counters at 6400 pps take 12800 cycles per second: 150 ms, 15 % of the
computer. (Modelled as increments only; the real counts went up and down.)

The unit is Verilog: '../counters.v' (latch cleared only for the counter
served) and '../counters_clearall.v' (one line "simplified": a served cycle
clears every latch). '../drive.cpp' is the Verilator test bench, one clock
per memory cycle. The test application builds it once per choice (about
4 s, without optimisation) in a private temporary directory, computes the
pulse trains, and judges the cycles the unit reports.

rr-quiet   radar CDUs in phase: the antenna tracks slowly, CDUT 40 pps, CDUS
           25 pps, TIME1 100 Hz. Every pulse counted; about 2 ms stolen.
rr-phase   the Apollo 11 case: CDUT and CDUS at 6400 pps. Every pulse still
           counted -- the hardware is right -- but 150 ms per second are
           gone: R3 BROKEN. That is the overload, not a logic error.
clear-all  the defective sequencer under the rr-phase pulses. When TIME1 and
           a CDU wait in the same cycle, the CDU pulse vanishes: R1 and R2
           BROKEN. 6400 pps is exactly 64 per TIME1 period, so a CDUT pulse
           shares the cycle of every TIME1 pulse: 100 lost per second.
           Under rr-quiet pulses it loses nothing (measured), so only the
           loaded fixture can find this defect.

HOW TO READ THE GOOD   The timeline is a '##! verbatim' region: a column is
one memory cycle, and the unit's row stands above the reference model's. It
shows the window around the first cycle that differs from the model, or
else around the first moment two counters wait at once. Times and
rates carry units; the laws are written in them. The counts are exact (the
pulse trains are computed, not random); 'lost', 'diverging' and 'stolen' are
bindings; the choice's laws judge 'lost' and 'stolen'.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
MCT = 12 / 1.024e6                    # one memory cycle: 12 pulses of 1.024 MHz, s
CYCLES = 85333                        # one second of flight, in memory cycles
COUNTERS = ["TIME1", "CDUT", "CDUS"]
SCENARIO = {   # rates in pulses per second, phase in pulse periods
    "rr-quiet": {"TIME1": (100, 0.0), "CDUT": (40, 0.3), "CDUS": (25, 0.6)},
    "rr-phase": {"TIME1": (100, 0.0), "CDUT": (6400, 0.0), "CDUS": (6400, 0.5)},
}
CHOICE_DB = {"rr-quiet": ("counters.v", "rr-quiet"),
             "rr-phase": ("counters.v", "rr-phase"),
             "clear-all": ("counters_clearall.v", "rr-phase")}
GLYPH = {"TIME1": "1", "CDUT": "T", "CDUS": "S"}
WINDOW = 72


def pulse_cycles(rate, phase):
    """The memory cycles in which the pulses of one train arrive."""
    cycles, k = [], 0
    while True:
        c = int((k + phase) / rate / MCT)
        if c >= CYCLES:
            return cycles
        cycles.append(c)
        k += 1


def run_unit(source, trains):
    if shutil.which("verilator") is None:
        print("!! verilator is not installed: this example needs it (apt install verilator)")
        print("<hwut-end>")
        sys.exit(1)
    bits = [[0, 0, 0] for _ in range(CYCLES)]
    for i, name in enumerate(COUNTERS):
        for c in trains[name]:
            bits[c][i] = 1
    with tempfile.TemporaryDirectory() as build:
        flags = "OPT_FAST=-O0 OPT_SLOW=-O0 OPT_GLOBAL=-O0"
        subprocess.run(["verilator", "--cc", "--exe", "--build", "-j", "2",
                        "-Mdir", build, "-MAKEFLAGS", flags, "--top-module", "counters",
                        os.path.join(UNIT, "drive.cpp"), os.path.join(UNIT, source),
                        "-o", "drive"],
                       check=True, capture_output=True, env=dict(os.environ, LC_ALL="C"))
        text = "".join("%d %d %d\n" % tuple(b) for b in bits)
        out = subprocess.run([os.path.join(build, "drive")], input=text,
                             capture_output=True, text=True, check=True).stdout
    slots, final = out.split("\n")[:2]
    return slots, dict(zip(COUNTERS, map(int, final.split())))


def reference(trains):
    """The requirement as a model: one pending latch per counter, set by a
    pulse, cleared when that counter is served; one counter per memory cycle,
    TIME1 > CDUT > CDUS. Returns the cycle string and the first cycle after
    which two counters wait at once."""
    arrivals = [set(trains[n]) for n in COUNTERS]
    pend, out, crowded = [False] * 3, [], None
    for c in range(CYCLES):
        served = next((i for i in range(3) if pend[i]), None)
        out.append("." if served is None else GLYPH[COUNTERS[served]])
        if served is not None:
            pend[served] = False
        for i in range(3):
            pend[i] = pend[i] or c in arrivals[i]
        if crowded is None and sum(pend) >= 2:
            crowded = c
    return "".join(out), crowded


def main(choice):
    source, scenario = CHOICE_DB[choice]
    trains = {n: pulse_cycles(*SCENARIO[scenario][n]) for n in COUNTERS}
    slots, final = run_unit(source, trains)

    print("unit:      ../%s, verilated, driven by ../drive.cpp" % source)
    print("scenario:  %s   %s" % (scenario, "   ".join(
        "%s %d Hz" % (n, SCENARIO[scenario][n][0]) for n in COUNTERS)))
    print("flight:    1 s = %d memory cycles of %.2f us" % (CYCLES, MCT * 1e6))
    model, crowded = reference(trains)
    diverging = [c for c in range(CYCLES) if slots[c] != model[c]]
    if diverging:
        focus, why = diverging[0], "first cycle that differs from the reference model"
    elif crowded is not None:
        focus, why = crowded, "first cycle after which two counters wait at once"
    else:
        focus, why = trains["TIME1"][0], "no two counters ever wait at once; first TIME1 pulse"
    start = max(0, focus - 8)
    start -= start % 10
    end = start + WINDOW
    print("timeline:  memory cycles %d..%d (%s)" % (start, end - 1, why))
    print("legend:    '|' a pulse arrives   cycle: '.' program  '1' TIME1  'T' CDUT  'S' CDUS")
    print("           reference: the cycles as the requirement model R1/R2 spends them")
    print()
    print("##! verbatim")
    ruler = "".join(("%-10d" % c) for c in range(start, end, 10))[:WINDOW]
    print("  cycle         " + ruler)
    for n in COUNTERS:
        hits = set(trains[n])
        print("  pulse %-7s " % n + "".join("|" if c in hits else " " for c in range(start, end)))
    print("  memory cycle  " + slots[start:end])
    print("  reference     " + model[start:end])
    print("####")
    print()
    print("  counter   rate       pulses   counted   lost   cycles stolen")
    lost_total, stolen_cycles = 0, 0
    lost_named = []
    for n in COUNTERS:
        pulses = len(trains[n])
        stolen = slots.count(GLYPH[n])
        lost = pulses - final[n]
        lost_total += lost
        stolen_cycles += stolen
        if lost:
            lost_named.append((n, lost))
        print("  %-8s %5d Hz   %6d    %6d   %4d   %6d" % (n, SCENARIO[scenario][n][0],
                                                       pulses, final[n], lost, stolen))
    print()
    for n, lost in lost_named:
        higher = set().union(*(set(trains[h]) for h in COUNTERS[:COUNTERS.index(n)]))
        shared = len(set(trains[n]) & higher)
        print("!! %s: %d pulses lost; %d of its pulses arrived in the same cycle as a higher-priority pulse"
              % (n, lost, shared))
    print("R1 pulses lost ((lost: %d))   law == 0   %s"
          % (lost_total, "kept" if lost_total == 0 else "BROKEN"))
    print("R2 cycles that differ from the reference model ((diverging: %d))   law == 0   %s"
          % (len(diverging), "kept" if not diverging else "BROKEN"))
    stolen_ms = stolen_cycles * MCT * 1000
    print("R3 counting took ((stolen: %.1f ms)) of 1 s (%.1f %%)   law <= 100 ms   %s"
          % (stolen_ms, stolen_ms / 10, "kept" if stolen_ms <= 100 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
