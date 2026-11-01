#! /usr/bin/env python3
# @hwut {
#     title    = "Ariane 501 (1996): 64-bit float to 16-bit int, value range x conversion, and the flight"
#     choices {
#         ada-unprotected { features = ["range-table", "flight-strip", "failure-named"]
#                           tolerance { constraints = ["wrong_rows > 0", "bad_seconds > 0"] } }
#         c-cast          { features = ["range-table", "flight-strip", "failure-named"]
#                           tolerance { constraints = ["wrong_rows > 0", "bad_seconds > 0"] } }
#         protected       { features = ["range-table", "flight-strip", "conversion-guarded"]
#                           tolerance { constraints = ["wrong_rows == 0", "bad_seconds == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  what one float-to-int16 conversion of the SRI makes of boundary
         values of BH, and of the BH curves of a modelled flight
HISTORY  On 4 June 1996 the first Ariane 5 (flight 501) broke up about 40 s
after lift-off. The inquiry board chaired by Jacques-Louis Lions (report of
19 July 1996) found the cause in the software of the inertial reference
systems (SRI), reused from Ariane 4: an alignment function that served no
purpose after lift-off still ran, and converted the horizontal bias BH from
a 64-bit float to a 16-bit signed integer. Ariane 5's early trajectory has
a much higher horizontal velocity than Ariane 4's, BH exceeded the range,
the conversion raised an Operand Error, and no handler protected it (some
of the converted variables had protection, BH had not). Both SRIs, running
the same code, failed -- the backup first, by about 72 ms -- and the
on-board computer took their diagnostic word for flight data.

REQUIREMENT  Converting a 64-bit float to a 16-bit integer never stops the
             SRI and never yields a value of the wrong size or sign: an
             in-range value comes out rounded, an out-of-range one is clamped
             to the limit and flagged.

THE UNIT  '../sri.c' (C), one conversion per build (-DCONVERT=...):
    ada-unprotected  Ada's semantics without a handler -- what flew: out of
                     range raises Operand Error, the SRI declares failure
                     and stops (in 'flight' mode no line follows).
    c-cast           a WRAPPING conversion, built on purpose: the value
                     wraps modulo 2^16, silently -- 40000 becomes -25536.
                     This is a modelling choice, not "what C does": in C an
                     out-of-range float-to-integer conversion is undefined
                     behaviour (C11 6.3.1.4) -- the compiler may produce
                     anything. The unit goes through int64 -> uint32 ->
                     int16, which is defined, to show the silent-wrap kind
                     of failure deterministically.
    protected        clamp and flag, as the protected variables were.

WHAT THE TEST PRINTS
  1. VALUE RANGE x CONVERSION: values across the int16 boundaries (inside,
     on the limits, half a unit beyond -- Ada rounds to nearest --, far
     beyond, both signs), the right answer and what the conversion did.
  2. THE FLIGHT, H0 .. H0+40 s, one column per second, for two BH curves:
     a MODEL, not flight data -- BH grows with the square of time, the
     Ariane 5 curve fitted to cross 32767 at about H0+37 s as in the
     report, the Ariane 4 curve five times flatter. '.' a right value,
     'c' clamped and flagged, 'w' a wrapped (wrong) value, 'X' Operand
     Error, '-' no data any more: the SRI has stopped.

HOW TO READ THE GOOD  In the table every row says 'ok' or '!!'. In the
strip the Ariane 4 row is all '.', which is why the conversion 'could not'
fail on Ariane 4 and was left unprotected; the Ariane 5 row shows what each
conversion makes of the same flight. Both pictures are '##! verbatim'; all
is exact. Two verdicts, one per picture -- rows and seconds are not one
unit: '((wrong_rows: N))' and '((bad_seconds: N))'; laws '== 0' for
'protected', '> 0' for the two historical/naive ones.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CONVERT_DB = {"ada-unprotected": "ADA_UNPROTECTED", "c-cast": "C_CAST", "protected": "PROTECTED"}
VALUES = [0.0, 1234.4, 32766.6, 32767.0, 32767.4, 32767.5, 40000.0, 65535.0, 65536.0,
          1.0e6, -32768.0, -32768.4, -32768.6, -40000.0]
SECONDS = list(range(0, 41))
CURVE_DB = {"Ariane 4 BH": 4.866, "Ariane 5 BH": 24.33}      # BH = k * t^2


def build(macro, scratch):
    exe = os.path.join(scratch, "sri")
    subprocess.run(["gcc", "-O2", "-Wall", "-Werror", "-DCONVERT=" + macro, "-o", exe,
                    os.path.join(HERE, "..", "sri.c"), "-lm"], check=True)
    return exe


def run(exe, mode, values):
    text = "".join("%.1f\n" % v for v in values)
    return subprocess.run([exe, mode], input=text, capture_output=True, text=True,
                          check=True).stdout.splitlines()


def judge(value, line):
    """RETURN: (verdict, the right answer as text)."""
    r = int(value + 0.5) if value >= 0 else -int(-value + 0.5)   # half away from zero, as Ada
    if -32768 <= r <= 32767:
        return ("ok" if line == "value %d" % r else "!!"), "value %d" % r
    limit = 32767 if r > 0 else -32768
    return ("ok" if line == "clamped %d flag" % limit else "!!"), "out of range: clamp, flag"


def bh_curve(k):
    """RETURN: BH at H0 + t, t = 0 .. 40 s, to 0.1 -- as the unit reads it."""
    return [float("%.1f" % (k * t * t)) for t in SECONDS]


def main(choice):
    scratch = tempfile.mkdtemp(prefix="ariane-")
    try:
        exe = build(CONVERT_DB[choice], scratch)
        table = run(exe, "table", VALUES)
        flight_db = {name: run(exe, "flight", bh_curve(k)) for name, k in CURVE_DB.items()}
    finally:
        shutil.rmtree(scratch, True)
    wrong_rows = bad_seconds = 0
    print("conversion: %s   (BH: 64-bit float -> 16-bit signed int, -32768 .. 32767)" % choice)
    print()
    print("VALUE RANGE x CONVERSION")
    print("##! verbatim")
    print("  %12s   %-26s %-20s %s" % ("BH", "right answer", "conversion gave", "verdict"))
    for v, line in zip(VALUES, table):
        verdict, right = judge(v, line)
        wrong_rows += verdict != "ok"
        print("  %12.1f   %-26s %-20s %s" % (v, right, line, verdict))
    print("####")
    print()
    print("THE FLIGHT (model curves BH = k t^2), H0 .. H0+40 s")
    print("##! verbatim")
    print("%-12s %s" % ("H0+ s", "".join(str(t // 10) if t % 10 == 0 else " " for t in SECONDS)))
    for name, k in CURVE_DB.items():
        lines, curve = flight_db[name], bh_curve(k)
        cells = ""
        for t in SECONDS:
            if t >= len(lines) or lines[t] == "SRI_FAILED":
                cells += "-"
                continue
            verdict, _ = judge(curve[t], lines[t])
            cells += "X" if lines[t] == "OPERAND_ERROR" else "c" if lines[t].startswith("clamped") \
                     else "." if verdict == "ok" else "w"
        bad = sum(1 for c in cells if c in "Xw-")
        bad_seconds += bad
        print("%-12s %s" % (name, cells))
    print("####")
    print("(one column per second, tens of seconds on the ruler; '.' right value  'c' clamped + flagged")
    print(" 'w' wrapped, wrong  'X' Operand Error  '-' SRI stopped, no data)")
    for name, k in CURVE_DB.items():
        curve = bh_curve(k)
        first = next((t for t in SECONDS if curve[t] >= 32767.5), None)
        print("%s %s" % (name, "leaves the int16 range at H0+%d s (BH = %.1f)" % (first, curve[first])
                                if first is not None else "stays within int16 for all 40 s"))
    print("table rows wrong: ((wrong_rows: %d)) of %d   law == 0   %s"
          % (wrong_rows, len(VALUES), "kept" if not wrong_rows else "BROKEN"))
    print("flight seconds without a right or flagged value: ((bad_seconds: %d)) of %d   law == 0   %s"
          % (bad_seconds, 2 * len(SECONDS), "kept" if not bad_seconds else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CONVERT_DB:
        print("choices: %s" % ", ".join(CONVERT_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
