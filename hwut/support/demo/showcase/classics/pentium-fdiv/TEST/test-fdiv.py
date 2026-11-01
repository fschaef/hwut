#! /usr/bin/env python3
# @hwut {
#     title    = "Pentium FDIV (1994): five missing cells of the SRT table, the famous divisions, and a seeded fuzz"
#     choices {
#         p5-1994     { features = ["table-drawn", "famous-divisions", "fuzz-against-exact", "wrong-named"]
#                       tolerance { constraints = ["uniform_wrong == 0", "wrong > 0"] } }
#         fixed-table { features = ["table-drawn", "famous-divisions", "fuzz-against-exact", "always-right"]
#                       tolerance { constraints = ["uniform_wrong == 0", "wrong == 0"] } }
#     }
#     caps { timeout_sec = 120 }
# }
"""
______________________________________________________________________________
SUBJECT  the quotients of the SRT divider model (flawless or with the 1994
         lookup table) for famous and fuzzed divisions
HISTORY  Thomas Nicely (Lynchburg College), summing reciprocals of twin
primes, noticed inconsistent results in June 1994 and traced them to the
Pentium's floating-point division: 1 / 824633702441 came out wrong after
some nine correct digits; he reported it on 30 October 1994. In November
Tim Coe (Vitesse), working from his own model of the flaw, found the far
worse 4195835 / 3145727 = 1.333820449... coming out as 1.333739068... --
wrong from the 5th significant digit -- and Cleve Moler publicised it
(Moler, 'Pentium Division Bug Revisited', MathWorks). Intel confirmed
that five entries of the lookup table of its radix-4 SRT divider were
missing (they held 0 instead of +2), estimated the chance of a random
division hitting them at about 1 in 9 billion, and in December 1994
offered to replace every affected chip (a charge of about 475 million
dollars). Accounts: C. Moler (MathWorks); Edelman, 'The Mathematics of the
Pentium Division Bug' (SIAM Review, 1997); Coe & Tang, 'It Takes Six Ones
to Reach a Flaw' (1995); K. Shirriff's die-level analysis (2024).

REQUIREMENT  Every division returns the quotient correct to the precision
             of the format (here: relative error below 2^-50).

THE UNIT  '../srt_divider.py': the divider at bit level -- carry-save
remainder, 7-bit remainder estimate, 4 divisor bits, digits -2..+2 --
with the full table or with the five cells Intel's table lacked. Faithful
enough that Coe's division comes out exactly as the chip printed it
(1.3337390689020376), and so does 5505001 / 294911 (18.666000929...);
Nicely's reciprocal comes out wrong too (relative error 3.7e-9; the
chip's own digits of that one are not checked here).

WHAT THE TEST PRINTS
  1. THE TABLE, upper half: rows are the remainder estimate (1/8 steps),
     columns the divisor 1.0000 .. 1.1111. '2' '1' '0' the digit, '.' a
     cell no remainder reaches, '*' a cell that should hold 2 and holds 0.
  2. FAMOUS DIVISIONS against the exact quotient (Python Fractions).
  3. A SEEDED FUZZ (deterministic_random, seed 1994), two populations:
     uniform   4000 random 24-bit dividends and divisors: why nobody's test
               suite noticed -- law 'uniform_wrong == 0' for BOTH choices.
     at-risk   for each divisor column 1000 divisors 1.dddd followed by
               twelve ones (Coe & Tang: it takes six ones) and dividends
               whose quotient lies near a third (its radix-4 digits run
               2, 2, 2 ..., which drives the remainder to the top of the
               table). Wrong results per column; each one listed with the
               number of significant digits that are still right.
     Everything is exact and repeatable: the seed fixes every operand, the
     divider is deterministic -- so the GOOD lists the very same failures
     every run.

CHOICES
    p5-1994      the flawed table: failures only in the five columns of
                 the missing cells. Law 'wrong > 0'.
    fixed-table  the table filled (Intel's correction): no failure. Law
                 'wrong == 0'.

TRIED  A mutation of the unit that bounds the reachable cells by the line
p = 8/3 d at the LEFT edge of each column (instead of the right) empties
the top cell of every column -- 21 cells -- and fails on exactly the same
14 at-risk divisions: only the five columns' cells are ever reached. This
agrees with Shirriff's finding of 16 missing entries of which 5 matter.

HOW TO READ THE GOOD  The five '*' sit on the upper edge of the 2-region,
in every third column from 1.0001 on. The at-risk row of counts is zero
except under those columns. In the list, 'right digits 4' means the result
is wrong from the 5th significant digit -- Coe's case. Table and count
rows are '##! verbatim'.
______________________________________________________________________________
"""
import os
import shutil
import sys
from fractions import Fraction as Fr

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import srt_divider as unit

CHOICE_DB = {"p5-1994": True, "fixed-table": False}
FAMOUS = [(1, 824633702441, "Nicely, Jun-Oct 1994"), (4195835, 3145727, "T. Coe, Nov 1994, via C. Moler"),
          (5505001, 294911, "Coe/Tang list"), (1, 3, "an easy one")]
LIMIT = Fr(1, 2 ** 50)


def right_digits(got, exact):
    """RETURN: number of leading significant decimal digits that agree."""
    a, b = "%.15e" % got, "%.15e" % exact
    a, b = a.split("e")[0].replace(".", ""), b.split("e")[0].replace(".", "")
    n = 0
    while n < len(a) and a[n] == b[n]:
        n += 1
    return n


def is_wrong(a, b, tab):
    q, exact = unit.fdiv(a, b, tab), Fr(a, b)
    return abs(q - exact) > exact * LIMIT, q, exact


def at_risk_pair(rng, column):
    """RETURN: (dividend, divisor) -- divisor 1.dddd 111111111111 xxxxxxx (24 bits),
               dividend such that the quotient lies near (3j + 1 or 2) / 3."""
    divisor = (1 << 23) | (column << 19) | (0xFFF << 7) | rng.next_int(0, 127)
    j = rng.next_int(1, 12)
    third = Fr(3 * j + rng.select((1, 2)), 3) * (1 + Fr(rng.next_int(-4096, 4096), 2 ** 40))
    dividend = round(divisor * third)
    return dividend, divisor


def main(choice):
    tab = unit.table(CHOICE_DB[choice])
    print("divider: radix-4 SRT, carry-save, %s table" % ("Intel's 1994" if CHOICE_DB[choice] else "full"))
    print()
    print("1. THE TABLE, upper half (row = remainder estimate p, column = divisor 1.dddd)")
    print("##! verbatim")
    print("   p   " + " ".join("%X" % k for k in range(16)))
    good = unit.table(False)
    for m in range(44, 11, -1):
        cells = []
        for k in range(16):
            if unit._valid_digits(k, m) is None:
                cells.append(".")
            elif tab[(k, m)] != good[(k, m)]:
                cells.append("*")
            else:
                cells.append(str(tab[(k, m)]))
        print("%6.3f %s" % (m / 8, " ".join(cells)))
    print("####")
    print("(cell: the quotient digit the table selects, 1 or 2; '.' unreachable; '*' should be 2, holds 0;")
    print(" column X = divisor 1.dddd with dddd = X in hex)")
    print()
    print("2. FAMOUS DIVISIONS")
    for a, b, who in FAMOUS:
        wrong, q, exact = is_wrong(a, b, tab)
        print("   %8d / %-12d = %.15e  exact %.15e  %s  (%s)"
              % (a, b, q, exact, "!! right digits %d" % right_digits(q, exact) if wrong else "ok", who))
    print()
    rng = DeterministicStream(1994)
    uniform_wrong = 0
    for _ in range(4000):
        a, b = rng.next_int(1 << 23, (1 << 24) - 1), rng.next_int(1 << 23, (1 << 24) - 1)
        uniform_wrong += is_wrong(a, b, tab)[0]
    print("3. SEEDED FUZZ (deterministic_random, seed 1994) against the exact quotient")
    print("   uniform   4000 random 24-bit pairs: wrong ((uniform_wrong: %d))   law == 0   %s"
          % (uniform_wrong, "kept" if not uniform_wrong else "BROKEN"))
    count, failure_list = [], []
    for column in range(16):
        n = 0
        for _ in range(1000):
            a, b = at_risk_pair(rng, column)
            wrong, q, exact = is_wrong(a, b, tab)
            if wrong:
                n += 1
                failure_list.append((column, a, b, q, exact))
        count.append(n)
    print("   at-risk   1000 pairs per divisor column (1.dddd + twelve ones, quotient near a third):")
    print("##! verbatim")
    print("   column  " + " ".join("%3X" % k for k in range(16)))
    print("   wrong   " + " ".join("%3d" % n for n in count))
    print("####")
    if failure_list:
        print("   col  %20s   %16s  %16s  right digits" % ("division", "quotient", "exact"))
    for column, a, b, q, exact in failure_list:
        print("   %X    %9d / %-8d   %16.12f  %16.12f  %d  !!"
              % (column, a, b, q, exact, right_digits(q, exact)))
    print("   wrong results in the at-risk population: ((wrong: %d)) of %d   law == 0   %s"
          % (sum(count), 16 * 1000, "kept" if not sum(count) else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
