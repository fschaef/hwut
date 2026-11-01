#! /usr/bin/env python3
# @hwut {
#     title    = "Myers' triangle (1979): every side triple of a boundary basis, truth x answer"
#     choices {
#         right   { features = ["whole-space", "classified-right"]
#                   tolerance { constraints = ["mismatches == 0"] } }
#         lt      { features = ["whole-space", "mismatch-named"]
#                   tolerance { constraints = ["mismatches > 0"] } }
#         int-sum { features = ["whole-space", "mismatch-named"]
#                   tolerance { constraints = ["mismatches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the classification one triangle program gives for each of 343
         triples of int sides, against the definition
HISTORY  Glenford J. Myers opens 'The Art of Software Testing' (Wiley, 1979)
with a self-assessment: a program reads three integers, the sides of a
triangle, and prints whether it is scalene, isosceles or equilateral. Write
the test cases. Myers lists about fourteen questions a good set answers --
an invalid triangle (1, 2, 4), the degenerate one (1, 2, 3) where a + b = c,
all PERMUTATIONS of both, a zero side, a negative side -- and reports that
experienced programmers score poorly. It became the standard first example
of boundary-value testing.

REQUIREMENT  For every triple of int sides, the program answers 'invalid'
             unless all sides are positive and each pair sums to MORE than
             the third (a + b = c is a line, not a triangle); otherwise it
             answers equilateral / isosceles / scalene.

THE TESTED SPACE IS A GENERATOR INSTRUCTION -- Myers' questions as data:

    SIDES = -1, 0, 1, 2, 3, 4, MAX            (MAX = 2^31 - 1)
    for a, b, c in space_iterator.do([SIDES] * 3)       -> 7^3 = 343 triples

-1 and 0 are the sign boundary; 1 2 3 the degenerate triangle, 1 2 4 the
impossible one, 2 3 4 scalene, 2 2 3 isosceles, 2 2 4 a degenerate
isosceles; the full product contains every PERMUTATION of each; MAX makes
'a + b' overflow a 32-bit int. The truth comes from Python's unbounded
integers; the unit is C ('../triangle*.c', compiled per run, -fwrapv so that
int overflow wraps as the machine does instead of being undefined).

CHOICES
    right    ../triangle.c: sums in 64 bit, 'a + b <= c' is invalid.
    lt       ../triangle_lt.c: the textbook slip '<' for '<=': the
             degenerate triples (1 2 3, 2 2 4, 1 1 2 ...) pass as triangles.
    int-sum  ../triangle_int.c: the sums in int: MAX + MAX wraps negative,
             so (MAX, MAX, MAX) and (MAX, MAX, 1) are called invalid.

HOW TO READ THE GOOD  The MATRIX: rows are the truth (invalid split by its
reason), columns the program's answer. Every count belongs on the
diagonal; an off-diagonal cell is written '[n]'. Below it each mismatch,
once per set of sides (sorted), with how many of its permutations the unit
got wrong. The matrix is '##! verbatim' (a cell's column is its meaning);
all is exact: the unit is deterministic. The verdict is the binding
'((mismatches: N))': 'right' holds the law 'mismatches == 0', the broken
fixtures 'mismatches > 0'.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT_DB = {"right": "triangle.c", "lt": "triangle_lt.c", "int-sum": "triangle_int.c"}
MAX = 2**31 - 1
SIDES = [-1, 0, 1, 2, 3, 4, MAX]
ROWS = ["invalid: side <= 0", "invalid: a+b < c", "invalid: a+b = c",
        "equilateral", "isosceles", "scalene"]
ANSWERS = ["invalid", "equilateral", "isosceles", "scalene"]


def truth(a, b, c):
    """RETURN: (row of the matrix, the right answer) -- unbounded integers."""
    if min(a, b, c) <= 0:
        return ROWS[0], "invalid"
    x, y, z = sorted((a, b, c))
    if x + y < z:
        return ROWS[1], "invalid"
    if x + y == z:
        return ROWS[2], "invalid"
    kind = "equilateral" if x == z else "isosceles" if x == y or y == z else "scalene"
    return kind, kind


def run_unit(source, triples):
    build = tempfile.mkdtemp(prefix="triangle-")
    try:
        exe = os.path.join(build, "triangle")
        subprocess.run(["gcc", "-O2", "-fwrapv", "-Wall", "-Werror", "-o", exe,
                        os.path.join(HERE, "..", source)], check=True)
        text = "".join("%d %d %d\n" % t for t in triples)
        return subprocess.run([exe], input=text, capture_output=True, text=True,
                              check=True).stdout.split()
    finally:
        shutil.rmtree(build, True)


def name(v):
    return "MAX" if v == MAX else str(v)


def main(choice):
    triples = list(space_iterator.do([SIDES] * 3))
    answers = run_unit(UNIT_DB[choice], triples)
    cell_db = {}                                   # (row, answer) -> count
    miss_db = {}                                   # sorted sides -> [answer, truth, n]
    for t, said in zip(triples, answers):
        row, right = truth(*t)
        cell_db[(row, said)] = cell_db.get((row, said), 0) + 1
        if said != right:
            key = tuple(sorted(t))
            miss_db.setdefault(key, [said, right, 0])[2] += 1

    print("unit: %s   sides from SIDES = %s  (MAX = 2^31-1)"
          % (UNIT_DB[choice], " ".join(name(v) for v in SIDES)))
    print("space: space_iterator over SIDES^3 = %d triples, all permutations included" % len(triples))
    print()
    print("##! verbatim")
    print("%-20s|%s" % ("truth \\ program says", "".join("%13s" % a for a in ANSWERS)))
    print("-" * 20 + "+" + "-" * 13 * len(ANSWERS))
    for row in ROWS:
        right = "invalid" if row.startswith("invalid") else row
        cells = ""
        for a in ANSWERS:
            n = cell_db.get((row, a), 0)
            cells += "%13s" % ("." if n == 0 else str(n) if a == right else "[%d]" % n)
        print("%-20s|%s" % (row, cells))
    print("####")
    print("(every count belongs in its row's own column; '[n]' = n triples answered wrongly)")
    print()
    for key in sorted(miss_db):
        said, right, n = miss_db[key]
        a, b, c = sorted(key)
        cause = ("%s + %s overflows int" % (name(b), name(c)) if b + c > MAX
                 else "%s + %s = %s: a line, not a triangle" % (name(a), name(b), name(c)) if a > 0 and a + b == c
                 else "")
        print(("MISMATCH  sides %-22s %d permutation(s)  program: %-11s truth: %-11s %s"
               % (" ".join(name(v) for v in key), n, said, right, cause)).rstrip())
    miss_n = sum(v[2] for v in miss_db.values())
    print("mismatches: ((mismatches: %d)) of %d triples   law == 0   %s" % (miss_n, len(triples), "kept" if not miss_n else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in UNIT_DB:
        print("choices: %s" % ", ".join(UNIT_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
