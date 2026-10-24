#! /usr/bin/env python3
# @hwut {
#     title    = "Patriot, Dhahran 1991: 0.1 s in a 24-bit register -- drift against uptime, and the range gate"
#     choices {
#         dhahran-1991 { features = ["tenth-shown", "drift-table", "gao-reproduced", "gate-drift-shown"]
#                        tolerance { numeric_ratio = 0.002
#                                    constraints   = ["gao_dev <= 0.1 ms", "gate > 1 ms"] } }
#         consistent   { features = ["tenth-shown", "drift-table", "gao-reproduced", "gate-stays"]
#                        tolerance { numeric_ratio = 0.002
#                                    constraints   = ["gao_dev <= 0.1 ms", "gate < 1 ms"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the calculated time of the Patriot's 24-bit clock over 100 hours of
         uptime, and the error of the range-gate interval derived from it
HISTORY  On 25 February 1991, at Dhahran, Saudi Arabia, a Patriot battery
failed to track an incoming Scud; it struck an Army barracks and killed 28
American soldiers. The GAO report 'Patriot Missile Defense: Software Problem
Led to System Failure at Dhahran' (GAO/IMTEC-92-26, February 1992) found the
cause in the time base: the battery had run for about 100 hours, the
calculated time had fallen about 0.34 s behind, and the range gate was
shifted so far that the Scud lay outside it. A software fix was on its way
and reached Dhahran on 26 February. R. Skeel (SIAM News, 1992) explains the
arithmetic: 0.1 chopped in a 24-bit register is short by about 9.5e-8 per
tenth of a second; and the conversion had been improved in some places of
the code but not in all, so the errors did not cancel.

REQUIREMENT  The time interval that places the range gate does not drift
             with uptime: over 100 hours of continuous operation its error
             stays below 1 ms (a Scud covers about 1.7 m in 1 ms).

THE UNIT  '../range_gate.c' (C): the 24-bit tenth (838860 / 2^23), the
calculated time of an uptime, and the error of the interval between two
radar times 1 s apart. -DGATE=GATE_MIXED: one time through the improved
conversion, the other through the 24-bit one -- as at Dhahran.
GATE_CONSISTENT: both through the same one; the drift cancels.

WHAT IT PRINTS  The register as bits (verbatim). Then, at GAO's uptimes
(0, 1, 8, 20, 48, 72, 100 h): the calculated time, its inaccuracy, GAO's
published inaccuracy beside it, the error of the gate interval, the gate
shift in metres at about 1676 m/s (Mach 5, as GAO's text and Skeel give the
Scud's speed) with a bar of one '=' per 20 m, and GAO's own 'approximate
shift in range gate' column beside it.
WHAT IS REPRODUCED, WHAT IS NOT  GAO's INACCURACY column is reproduced to
its four decimals (law 'gao_dev'). GAO's METRES are NOT: 687 m at 100 h
implies about 2000 m/s (687 / 0.3433), not the Mach 5 of GAO's own text;
the model's 575 m follows from 1676 m/s. Both columns are printed so the
difference is in plain sight; the report does not explain it.

THE GLOBAL numeric_ratio -- SHOWN AS A WARNING  Both choices carry
'numeric_ratio = 0.002'. It does no useful work here, and the example
says so: every number that matters is protected otherwise. What it
costs: a ratio is ONE band for EVERY number of the stream, not only for
the ones you had in mind. 0.2 % of the 100 in 'uptime 100 h' lets 100.2
pass; 0.2 % of 360000 s lets the true-time column be 720 s off; a count of
500 may become 501. Tried: a unit printing the true time 0.15 % too high
(28843.2 s for 8 h) PASSED the table under the ratio. And the other
direction: a Scud speed refined from 1676 to 1679 m/s (0.18 %) FAILS -- the
8 h row's shift goes 46.0 -> 46.1 m, 0.22 %: a value rounded to one
decimal moves in steps far coarser than 0.2 % when it is small. So a ratio
is too loose for large numbers and too tight for small rounded ones at the
same time. This test keeps everything that must hold OUT of its reach: the
register's bits and integer stand in '##! verbatim', where no tolerance
applies; the requirement is a constraint over QUANTITIES -- 'gate', the worst interval
error, printed in seconds like every column of GAO's table and judged
against the requirement in milliseconds ('gate < 1 ms': the comparison
converts), and 'gao_dev', the largest distance of GAO's inaccuracy from
the model's, in seconds, against GAO's precision of four decimals of a
second written as 'gao_dev <= 0.1 ms', taken both from its inaccuracy column and from 'true time'
minus 'calculated' (that recomputation is what turns the 0.15 % mutation
red). (A choice's own 'tolerance' block replaces the test's, so the ratio
is written into each choice.)

CHOICES
    dhahran-1991  mixed conversion: the gate interval inherits the whole
                  drift, 0.34 s and about 575 m after 100 h. Law 'gate > 1 ms'.
    consistent    the same clock drifts just as much -- the calculated time
                  is still 0.34 s behind -- but the interval error stays at
                  1e-6 s. Law 'gate < 1 ms'.
    Both: 'gao_dev <= 0.1 ms' -- the model reproduces GAO's inaccuracy column.
    A unit printing the gate error's number in ms but labelled 's' (0.0010
    s for the consistent gate) breaks 'gate < 1 ms' by its value; one that
    drops the unit breaks it by its dimension.

HOW TO READ THE GOOD  The inaccuracy column equals GAO's in every row, in
both choices: the clock is the same. Only the gate columns differ: a bar
growing with uptime is the failure; no bar is the requirement.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE_DB = {"dhahran-1991": "GATE_MIXED", "consistent": "GATE_CONSISTENT"}
# GAO/IMTEC-92-26, Appendix II: uptime (h) -> inaccuracy (s)
GAO = [(0, 0.0), (1, 0.0034), (8, 0.0275), (20, 0.0687), (48, 0.1648), (72, 0.2472), (100, 0.3433)]
GAO_SHIFT_M = [0, 7, 55, 137, 330, 494, 687]     # same appendix: 'approximate shift in range gate
INTERVAL_TENTHS = 10          # two radar times 1 s apart
SCUD_M_PER_S = 1676           # about, after Skeel


def run_unit(macro):
    build = tempfile.mkdtemp(prefix="patriot-")
    try:
        exe = os.path.join(build, "gate")
        subprocess.run(["gcc", "-O2", "-Wall", "-Werror", "-DGATE=" + macro, "-o", exe,
                        os.path.join(HERE, "..", "range_gate.c")], check=True)
        text = "".join("%d %d\n" % (h, INTERVAL_TENTHS) for h, _ in GAO)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
        return [l.split() for l in out.splitlines()]
    finally:
        shutil.rmtree(build, True)


def main(choice):
    rows = run_unit(GATE_DB[choice])
    print("range gate: %s, interval between two radar times %d tenths of a second" % (GATE_DB[choice], INTERVAL_TENTHS))
    print("##! verbatim")
    print("0.1 in the 24-bit register (23 fraction bits, chopped):")
    print("    binary 0.00011001100110011001100   = 838860 / 2^23 = 0.099999904632568359375")
    print("    short by 0.8 / 2^23 = 9.5367431640625e-08 s per tenth")
    print("####")
    print()
    print("uptime    true time   calculated  inaccuracy  GAO 1992  gate interval  gate shift  GAO shift (Dhahran")
    print("     h            s            s           s         s  error s, < 0.001          m  software, compare)")
    gao_dev = gate_worst = 0.0
    for (hours, true, calc, inacc, gate_err), (_, gao), gao_m in zip(rows, GAO, GAO_SHIFT_M):
        shift = abs(float(gate_err)) * SCUD_M_PER_S
        gao_dev = max(gao_dev, abs(float(true) - float(calc) - gao), abs(float(inacc) - gao))
        gate_worst = max(gate_worst, abs(float(gate_err)))
        print(("%6s %12s %12s  %10s  %8.4f  %13.7f  %10.1f  %9d  %s"
               % (hours, true, calc, inacc, gao, abs(float(gate_err)), shift, gao_m, "=" * int(shift / 20))).rstrip())
    print("(gate shift of THIS software at about %d m/s, '=' per 20 m; GAO's shift column, for the Dhahran"
          % SCUD_M_PER_S)
    print(" software, implies about 2000 m/s and is printed as published, not reproduced)")
    print()
    print("model against GAO's inaccuracy column: largest difference ((gao_dev: %.5f s))   law <= 0.1 ms (GAO's 4 decimals)   %s"
          % (gao_dev, "kept" if gao_dev <= 0.0001 else "BROKEN"))
    print("worst gate interval error over 100 h: ((gate: %.7f s))   law < 1 ms   %s"
          % (gate_worst, "kept" if gate_worst < 0.001 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in GATE_DB:
        print("choices: %s" % ", ".join(GATE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
