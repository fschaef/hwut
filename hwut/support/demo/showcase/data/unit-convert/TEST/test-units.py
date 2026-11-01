#! /usr/bin/env python3
#
# @hwut {
#     title   = "Pressure units: accurate to 1e-9, round trips to the last bits, gauges agree with pint"
#     choices {
#         exact-table  { features = ["accurate", "round-trip"]
#                        tolerance { constraints = ["rel_err <= 1e-9", "trip_err <= 1e-14"] } }
#         legacy-table { features = ["violation-shown"]
#                        tolerance { constraints = ["rel_err > 1e-9", "trip_err <= 1e-14"] } }
#         exact-gauges  { features = ["gauges"]
#                         tolerance { constraints = ["abs(tire - 32 psi) <= 0.001 Pa",
#                                                    "abs(cuff - 120 mmHg) <= 0.001 Pa",
#                                                    "abs(altimeter - 29.92 inHg) <= 0.001 Pa",
#                                                    "abs(vacuum - 760 torr) <= 0.001 Pa"] } }
#         legacy-gauges { features = ["gauges-off"]
#                         tolerance { constraints = ["abs(tire - 32 psi) > 0.001 Pa",
#                                                    "abs(cuff - 120 mmHg) > 0.001 Pa",
#                                                    "abs(altimeter - 29.92 inHg) > 0.001 Pa",
#                                                    "abs(vacuum - 760 torr) > 0.001 Pa"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the pressure conversions of ../conv.c under one factor table: the
         unit matrix, its errors against the units' definitions, round
         trips (*-table), or four gauge readings shown in hPa (*-gauges)
REQUIREMENT. ../conv.c converts pressures through a factor table:
    R1  every conversion between the 8 units is within 1e-9 (relative) of
        the exact value from the units' definitions (psi from the pound and
        the inch, mmHg from 13595.1 kg/m3, ...);
    R2  converting there and back, through any unit, returns the value
        within 1e-14 -- float noise in the last bits, nothing more;
    R3  a gauge reading in its sensor's unit (psi, mmHg, inHg, Torr) shown
        in hPa is within 0.001 Pa of the value the unit's definition gives.

CHOICES -- one program, two tables:
    exact-table   ../units.txt: R1 and R2 hold.
    legacy-table  ../units-legacy.txt, from an old firmware header: psi
                  6894.76, mmHg 133.322, Torr = mmHg, inHg 3386.39. R1
                  breaks -- by up to 3e-6, invisible at 6 digits. R2 HOLDS:
                  a round trip proves consistency, not correctness.
    exact-gauges  ../units.txt: four readings of a hand-held gauge, each in
                  its sensor's unit, converted to the display unit hPa: R3
                  holds.
    legacy-gauges ../units-legacy.txt: the same readings -- every one off
                  by 0.04 to 0.3 Pa. The worst is the vacuum gauge: the old
                  header has Torr = mmHg, which differ by 1.4e-7.

HWUT CONCEPTS -- where float noise appears and how it is tolerated:
  * The factor check is exact text: the errors are printed rounded to a
    power of ten ('2e-16', '3e-06'), and the worst of all 56 pairs is a
    constraint binding.
  * Four worked round trips, each through a FIXED intermediate unit,
    printed to 17 digits: the last-bit noise ('0.1 bar' comes back as
    0.10000000000000001) is deterministic for one path, so it is compared
    exactly -- no tolerance is needed for what does not vary.
  * 10000 random round trips per run (clock seed, '##' comment), through
    random units, bind their worst error '((trip_err: v))', judged by
    'trip_err <= 1e-14'; their number is fixed and printed as plain text.

  * UNITS (R3, the gauges): each displayed value is a QUANTITY,
    '((tire: 2206.3223338 hPa))', and its law is written in the SENSOR's
    unit: 'abs(tire - 32 psi) <= 0.001 Pa'. hwut converts through pint, so
    the oracle is not the test's own factor table but pint's definitions
    (psi from lbf and inch, mmHg from 13.5951 g/cm3, torr = atm/760) -- an
    implementation the firmware cannot share a typo with. A value printed
    in Pa under an 'hPa' label, or in a unit of another dimension, breaks
    the law; the same value spelled '... mbar' passes, as it should. pint
    knows 'torr' but not 'Torr': the law says 'torr', the table's name
    stays 'Torr'. 0.001 Pa is two decades below what a gauge resolves and
    far above float noise.

READING THE GOOD. The matrix reads '1 <row unit> is <cell> <column unit>'.
In the factor check, 'error' is the table's relative error, 'ok' within
1e-9. In the round-trip table the 17 digits show the float noise of a
path; R2 bounds it on every path. In the gauge table each row is a reading
as the sensor gives it, the value the display shows, how far that is from
the unit's definition ('off', computed by the test from the exact table),
and the law with its verdict -- hwut judges the binding through pint, the
'off' column lets a reader see exact and legacy apart at a glance.
______________________________________________________________________________
"""
import math
import os
import random
import subprocess
import sys
import tempfile
import atexit
import shutil
import time
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
EXACT = {"Pa": F(1), "hPa": F(100), "bar": F(100000),
         "psi": F("0.45359237") * F("9.80665") / F("0.0254") ** 2,
         "atm": F(101325), "mmHg": F("13595.1") * F("9.80665") / 1000,
         "Torr": F(101325, 760), "inHg": F("13595.1") * F("9.80665") * F("0.0254")}
UNITS = list(EXACT)



def scratch(prefix):
    """RETURN: a fresh scratch directory, removed when the test ends."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path

def conv(exe, table, requests):
    text = "".join(" ".join(map(str, r)) + "\n" for r in requests)
    out = subprocess.run([exe, os.path.join(TOP, table)], input=text, capture_output=True,
                         text=True, check=True).stdout
    return [float(x) for x in out.split()]


def decade(x):
    return "0" if x == 0 else "%.0e" % x


GAUGES = [("tire", 32, "psi"), ("cuff", 120, "mmHg"), ("altimeter", 29.92, "inHg"),
          ("vacuum", 760, "Torr")]


def gauges(exe, table):
    """Prints the gauge readings as the display shows them, in hPa (R3)."""
    shown = conv(exe, table, [(v, u, "hPa") for _, v, u in GAUGES])
    print("gauge readings, sensor unit -> display (hPa); off = |display - definition|")
    for (name, v, u), x in zip(GAUGES, shown):
        off = abs(F(x) * 100 - F(str(v)) * EXACT[u])
        print("  %-10s %7s %-5s ((%s: %.7f hPa))   off %.4f Pa   law <= 0.001 Pa   %s"
              % (name, v, u, name, x, off, "holds" if off <= F(1, 1000) else "BROKEN"))


def main(choice):
    table = "units.txt" if choice.startswith("exact") else "units-legacy.txt"
    exe = os.path.join(scratch("conv-"), "conv")
    subprocess.run(["gcc", "-O2", "-o", exe, os.path.join(TOP, "conv.c")], check=True)
    print("table: %s" % table)
    if choice.endswith("gauges"):
        return gauges(exe, table)
    show = ["hPa", "bar", "psi", "atm", "mmHg", "inHg"]
    cells = conv(exe, table, [(1, a, b) for a in show for b in show])
    print("1 <row> = <cell> <column>, 7 significant digits")
    print("%-6s" % "" + "".join("%13s" % u for u in show))
    for i, a in enumerate(show):
        print("%-6s" % a + "".join("%13.7g" % cells[i * len(show) + j] for j in range(len(show))))

    pairs = [(a, b) for a in UNITS for b in UNITS if a != b]
    got = conv(exe, table, [(1, a, b) for a, b in pairs])
    rel = {p: abs(F(g) / (EXACT[p[0]] / EXACT[p[1]]) - 1) for p, g in zip(pairs, got)}
    print("factor check: 1 <unit> in Pa against the definition")
    for u in UNITS[1:]:
        e = float(rel[(u, "Pa")])
        print("  %-5s error %-6s  %s" % (u, decade(e), "ok" if e <= 1e-9 else "OFF"))
    worst = max(rel, key=rel.get)
    print("R1 worst of all %d pairs: %s -> %s, relative error ((rel_err: %s))"
          % (len(pairs), worst[0], worst[1], decade(float(rel[worst]))))

    demo = [(0.1, "bar", "psi", "inHg"), (1013.25, "hPa", "inHg", "psi"),
            (14.7, "psi", "atm", "Torr"), (760, "Torr", "mmHg", "atm")]
    there = conv(exe, table, [(v, a, b, w) for v, a, b, w in demo])
    back = conv(exe, table, [(t, b, a, w) for t, (v, a, b, w) in zip(there, demo)])
    print("round trips: value unit -> other (via) -> back")
    for (v, a, b, w), x in zip(demo, back):
        print("  %-8s %-5s %-5s (%-4s)  %.17g" % (v, a, b, w, x))
    seed = time.time_ns()
    rng = random.Random(seed)
    print("## seed %d" % seed)
    trips = [(rng.uniform(0.001, 1e6), rng.choice(UNITS), rng.choice(UNITS), rng.choice(UNITS))
             for _ in range(10000)]
    there = conv(exe, table, trips)
    back = conv(exe, table, [(t, b, a, w) for t, (v, a, b, w) in zip(there, trips)])
    err = max(abs(x / t[0] - 1) for x, t in zip(back, trips))
    print("R2 %d random round trips, worst relative error ((trip_err: %.1e))" % (len(trips), err))


CHOICES = ("exact-table", "legacy-table", "exact-gauges", "legacy-gauges")
if len(sys.argv) < 2 or sys.argv[1] not in CHOICES:
    print("choices: %s" % ", ".join(CHOICES))
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
