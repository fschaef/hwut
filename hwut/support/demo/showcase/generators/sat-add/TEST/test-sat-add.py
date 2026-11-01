#! /usr/bin/env python3
# @hwut {
#     title    = "Saturating add: every boundary pair of int32, as one matrix"
#     features = ["exact-in-range", "clamped"]
#     choices {
#         checked    { tolerance { constraints = ["wrong == 0"] } }
#         wrapcheck  { features = ["exact-in-range", "clamped", "wrong-named"]
#                      tolerance { constraints = ["wrong > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the result of sat_add (../sat_add*.c) for every boundary pair of
         int32 operands, as a 7 x 7 matrix
REQUIREMENT  sat_add(a, b) returns the exact sum a + b clamped into
             [INT32_MIN, INT32_MAX] -- for EVERY pair of 32-bit operands.

The unit is C: '../sat_add.c' (overflow decided before the addition) and
'../sat_add_wrapcheck.c' (an older library: add with wrap-around, then guess
overflow from the sign of the result). '../drive.c' applies it to the pairs
on stdin.

THE GENERATOR INSTRUCTION IS THE SPECIFICATION OF THE TESTED SPACE:

    BASIS = [ EDGES, EDGES ]       EDGES = MIN, MIN+1, -1, 0, +1, MAX-1, MAX
    for a, b in space_iterator.do(BASIS)        -> 7 x 7 = 49 points

sat_add is piecewise linear in (a, b) with three regions: no overflow,
overflow upwards (clamped to MAX), overflow downwards (clamped to MIN). The
region borders are a + b = MAX and a + b = MIN. EDGES puts points on both
sides of each border and on the extremes: MAX-1 + 1 = MAX is exact (last
point inside), MAX + 1 is clamped (first point outside), MIN + MIN is the
deepest overflow there is. -1, 0, +1 cover the sign changes a sign-based
check depends on. That is boundary-value analysis written down as data: a
reviewer checks the BASIS line, not a loop.

checked    every cell is '=' or a clamp in the right direction.
wrapcheck  MIN + MIN wraps to exactly 0: the result's sign is not
           negative-positive but ZERO, the 's > 0' guess misses it and the
           function returns 0 -- one '!' in 49 cells. A random test hits
           that pair with probability 2^-64.

HOW TO READ THE GOOD   The matrix is the picture of the three regions: 'v'
in the upper left triangle, '^' in the lower right, '=' between. A '!'
names a wrong cell; the list below it gives the numbers. The matrix is a
'##! verbatim' region because a cell's COLUMN is its operand b. All else is
exact: the unit is deterministic. The wrong cells are a binding,
'((wrong: N))', judged by the choice's law ('== 0' / '> 0').
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

#  hwut's test-writing support is a Python package below the installation
#  directory: put the directory ABOVE 'hwut/' on sys.path. Under 'hwut.run'
#  the launcher's PYTHONPATH already holds it; by hand it does not.
sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
MIN, MAX = -2**31, 2**31 - 1
EDGES = [("MIN", MIN), ("MIN+1", MIN + 1), ("-1", -1), ("0", 0), ("+1", 1),
         ("MAX-1", MAX - 1), ("MAX", MAX)]
BASIS = [EDGES, EDGES]
CHOICE_DB = {"checked": "sat_add.c", "wrapcheck": "sat_add_wrapcheck.c"}


def run_unit(source, pairs):
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "drive")
        subprocess.check_call(["gcc", "-O2", "-Wall", "-Werror", "-o", exe,
                               os.path.join(UNIT, "drive.c"), os.path.join(UNIT, source)])
        text = "".join("%d %d\n" % p for p in pairs)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
    return [int(line.split()[2]) for line in out.splitlines()]


def main(choice):
    points = list(space_iterator.do(BASIS))
    got = run_unit(CHOICE_DB[choice], [(a, b) for (_, a), (_, b) in points])
    cell, wrong = {}, []
    for ((na, a), (nb, b)), result in zip(points, got):
        exact = a + b
        want = min(MAX, max(MIN, exact))
        if result != want:
            mark = "!"
            wrong.append((na, nb, result, want))
        elif exact > MAX:
            mark = "^"
        elif exact < MIN:
            mark = "v"
        else:
            mark = "="
        cell[(na, nb)] = mark

    print("unit:   ../%s" % CHOICE_DB[choice])
    print("basis:  a in {%s}" % ", ".join(n for n, _ in EDGES))
    print("        b in {%s}" % ", ".join(n for n, _ in EDGES))
    print("space:  %d x %d = %d points (space_iterator.do, b fastest)"
          % (len(EDGES), len(EDGES), len(points)))
    print("cells:  '=' exact sum   '^' clamped to MAX   'v' clamped to MIN   '!' WRONG")
    print()
    print("##! verbatim")
    print("  a \\ b  " + "".join("%6s" % n for n, _ in EDGES))
    for na, _ in EDGES:
        print("  %-6s " % na + "".join("%6s" % cell[(na, nb)] for nb, _ in EDGES))
    print("####")
    print()
    count = dict((m, list(cell.values()).count(m)) for m in "=^v!")
    print("exact: %d   clamped up: %d   clamped down: %d"
          % (count["="], count["^"], count["v"]))
    for na, nb, result, want in wrong:
        print("!! sat_add(%s, %s) = %d, the clamped sum is %d" % (na, nb, result, want))
    print("points with a wrong result ((wrong: %d)) of %d   law == 0   %s"
          % (len(wrong), len(points), "kept" if not wrong else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
