#! /usr/bin/env python3
# @hwut {
#     title    = "Gimli Glider (Air Canada 143, 1983): fuel computed with pounds per litre as kilograms per litre"
#     choices {
#         metric      { features = ["sheet-shown", "density-plausible", "fuel-enough"]
#                       tolerance { constraints = ["density >= 0.775 kg/L", "density <= 0.840 kg/L",
#                                                  "on_board >= 22300 kg"] } }
#         pounds      { features = ["sheet-shown", "density-plausible", "unit-converted", "fuel-enough"]
#                       tolerance { constraints = ["density >= 0.775 kg/L", "density <= 0.840 kg/L",
#                                                  "on_board >= 22300 kg"] } }
#         gimli-1983  { features = ["sheet-shown", "shortfall-named"]
#                       tolerance { constraints = ["density > 0.840 kg/L", "on_board < 22300 kg"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the fuel sheet computed at Montreal for Flight 143 from the
         dripstick reading, and the fuel physically on board once it was
         followed, against the fuel the flight plan required
HISTORY  On 23 July 1983 Air Canada Flight 143, a new Boeing 767 flying
Montreal - Ottawa - Edmonton, ran out of fuel at 41,000 ft over Red Lake,
Ontario. The crew glided it to the former air base at Gimli, Manitoba; all
69 people on board survived. The fuel gauges were inoperative, so the fuel
was measured with dripsticks and the load computed by hand. The 767 was
among Air Canada's first aircraft to use metric fuel figures, and the
flight plan asked for 22,300 kg; but the density used to turn litres into
mass was 1.77 -- the figure for POUNDS per litre -- where the kilogram
figure was about 0.80. At Montreal 7,682 L were taken for 13,597 kg, so
only 4,917 L were added; the aircraft left with about 22,300 lb (about
10,100 kg), less than half the fuel it needed. (Ottawa repeated the check
with the same mistake.) Reference: the Board of Inquiry into Air Canada
Flight 143, final report (1985); the figures used here are the widely
published ones (e.g. the summary in Wikipedia's 'Gimli Glider').

REQUIREMENT  After refuelling, the fuel on board is at least the 22,300 kg
             the flight plan requires -- and the density that turns the
             dripstick litres into mass is a density of jet fuel.

THE UNIT  '../fuel_sheet.awk' (awk), the hand computation as a program:
dripstick litres x density = mass on board, the mass to add, and the litres
for the refueller. It computes in the unit the density NAMES (kilograms for
kg/L, pounds for lb/L). Its inputs are the sheets in '../sheets/'. THE TEST
then does what the aircraft did: it fills the tanks as the sheet says and
weighs them at the fuel's real density (about 0.803 kg/L).

CHOICES
    metric      0.803 kg/L: 20,089 L added, 22,300 kg on board.
    pounds      the refueller's 1.77 under its OWN unit, lb/L: the sheet
                computes in pounds (49,163 lb required), adds 20,094 L --
                the units do the work, and the fuel is right.
    gimli-1983  1.77 written as kg/L, the sheet of 1983: 4,917 L added,
                about 22,300 lb = 10,117 kg on board.

THE LAWS, IN THE SOURCES' UNITS  Two quantities are bound. The density
the sheet used, '((density: 1.77 lb/L))', is judged in kg/L against the
range of jet fuel (Jet A / Jet A-1: about 0.775 .. 0.840 kg/L at 15 degC):
1.77 lb/L is 0.803 kg/L and holds it; 1.77 kg/L -- the right number
under the wrong unit -- breaks it by its VALUE: no jet fuel is that heavy.
The fuel on board is printed in POUNDS, '((on_board: 22304.2 lb))', and
judged against the flight plan in KILOGRAMS: 'on_board >= 22300 kg'. The
comparison converts: 22,304 lb is 10,117 kg, and the law fails exactly as
the aircraft did. gimli-1983 states the violation: 'density > 0.840 kg/L'
and 'on_board < 22300 kg'.

HOW TO READ THE GOOD  The sheet's lines as computed, then the tanks: a
bar per 1000 kg for the fuel required and the fuel on board ('#'), the
shortfall named with '!!'. Everything is deterministic and exact.
______________________________________________________________________________
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
CHOICE_DB = {"metric": "montreal-metric.txt", "pounds": "montreal-pounds.txt",
             "gimli-1983": "montreal-1983.txt"}
TRUE_KG_PER_L = 0.803          # the fuel's density that day, about
KG_PER_LB = 0.45359237         # exact by definition
REQUIRED_KG = 22300


def main(choice):
    sheet = os.path.join(UNIT, "sheets", CHOICE_DB[choice])
    out = subprocess.run(["awk", "-f", os.path.join(UNIT, "fuel_sheet.awk"), sheet],
                         capture_output=True, text=True, check=True).stdout
    step = dict((w[0], w[1:]) for w in (line.split() for line in out.splitlines()))
    dripstick = next(int(line.split()[1]) for line in open(sheet) if line.startswith("dripstick"))
    added = int(step["add"][0])

    print("fuel sheet: sheets/%s, computed by fuel_sheet.awk" % CHOICE_DB[choice])
    print("    dripsticks       %6d L" % dripstick)
    d_value, d_unit = step["density"]
    d_kg_l = float(d_value) * (KG_PER_LB if d_unit == "lb/L" else 1)
    print("    density used     ((density: %s %s)) = %.3f kg/L   law: jet fuel 0.775 .. 0.840 kg/L   %s"
          % (d_value, d_unit, d_kg_l, "kept" if 0.775 <= d_kg_l <= 0.840 else "!! BROKEN"))
    print("    on board         %6s %s   (dripstick litres x density)" % tuple(step["on-board"]))
    print("    required         %6s %s" % tuple(step["required"]))
    print("    to add           %6s %s" % tuple(step["to-add"]))
    print("    litres to add    %6d L" % added)
    print()
    kg = (dripstick + added) * TRUE_KG_PER_L
    lb = kg / KG_PER_LB
    print("the tanks after refuelling: %d L at the fuel's real %.3f kg/L" % (dripstick + added, TRUE_KG_PER_L))
    print("    fuel on board    ((on_board: %.1f lb)) = %.0f kg   law >= %d kg   %s"
          % (lb, kg, REQUIRED_KG, "kept" if kg >= REQUIRED_KG else "!! BROKEN"))
    print("    (one '#' per 1000 kg)")
    print("    required  %-24s %6d kg" % ("#" * round(REQUIRED_KG / 1000), REQUIRED_KG))
    print("    on board  %-24s %6.0f kg" % ("#" * round(kg / 1000), kg))
    if kg < REQUIRED_KG:
        print("!! short by %.0f kg: on board is %.0f %% of the fuel required"
              % (REQUIRED_KG - kg, 100 * kg / REQUIRED_KG))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
