#! /usr/bin/env python3
# @hwut {
#     title    = "Floating-point summation: order changes the last bits; Kahan stays within its bound"
#     choices {
#         orders    { features = ["orders-shown", "kahan-bound"]
#                     tolerance { constraints = ["accurate_units <= 2"] } }
#         parallel  { features = ["partials-any-order", "arrival-total"]
#                     tolerance { numeric_ratio = 1e-15
#                                 constraints   = ["partial_mismatch == 0", "known == \"yes\""] } }
#         fast-math { features = ["orders-shown", "breach-shown"]
#                     tolerance { constraints = ["accurate_units > 2"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the totals of 100000 doubles summed by ../sum.c: plain and Kahan, in
         every arrival order, in a parallel reduction, under -ffast-math
HISTORY  Floating-point addition is not associative: (a + b) + c and
a + (b + c) may differ in the last bits, so a sum depends on its order --
and in a parallel reduction the order is whatever order the workers
finish in. Kahan's compensated summation ("Further remarks on reducing
truncation errors", Comm. ACM 8:40, 1965) carries the lost low-order bits
along; its error is bounded by about 2u * sum|x_i| (u = 2^-53), independent
of n, where a plain loop's bound grows with n (Goldberg, "What Every
Computer Scientist Should Know About Floating-Point Arithmetic", ACM
Computing Surveys 23:5, 1991; Higham, "Accuracy and Stability of Numerical
Algorithms", ch. 4). Value-unsafe optimisation (-ffast-math: reassociation)
lets the compiler simplify Kahan's correction (t - s) - y to 0 -- the
"accurate" sum is then the naive one.

REQUIREMENT  sum_accurate() is within Kahan's bound of the exact sum,
2u * sum|x| (+ a term n u^2 sum|x|, below 1e-10 of it here); a parallel
total is one of the totals its arrival orders can give.

The unit is C, '../sum.c', compiled per run. Its input: 100000 doubles from
deterministic_random (seed as a comment; mixed signs, magnitudes 1e-6..1e6),
sent as hex floats so no bit is lost. The EXACT sum is computed in the test
with integers (every double is an integer multiple of 2^-1074).
    orders     the ORDER TABLE: each order's result (%.17g), its error
               against the exact sum, and that error in units of
               u * sum|x| -- Kahan's bound is 2 of them, the plain loop's is
               n - 1. In '##! verbatim': the last bits ARE the lesson.
               '((accurate_units: x))' carries the law.
    parallel   4 threads, each sums a quarter; each partial is added to the
               total when its worker finishes. The PARTIALS stand in
               '##! potpourri' -- their arrival order differs from run to
               run. The test lists the totals of all 24 arrival orders
               (verbatim; Python floats add exactly as C doubles do), and
               the unit's total is checked to be one of them
               ('((known: "yes"))'). The total itself is printed under the
               test's GLOBAL 'numeric_ratio = 1e-15', so a run whose
               workers finished in another order still passes.
               SIZE OF THE RATIO, derived: the total adds W = 4 partials in
               W - 1 = 3 roundings; each order's result is within
               (W - 1) u sum|p| of the exact sum of the partials (to first
               order in u = 2^-53; Higham, ch. 4),
               so two orders differ by at most 2 (W - 1) u sum|p| = 6u sum|p|.
               All partials are positive here, sum|p| = |total|, hence the
               relative difference is <= 6u = 6.7e-16 -- the ratio is the
               next round number above it, 1e-15. (Observed: the two
               distinct totals differ by 1 ulp, 1.3e-16.) A wider ratio would
               only widen what slips through: a total that lost one element
               of the data differs by about 2e-13.
               THE TRAP of a global ratio: it applies to EVERY number of
               the stream -- also to the deterministic partials in the
               potpourri, which may now change in their last digit
               unnoticed, and to counts and chunk bounds (harmless here
               only because 1e-15 of 100000 is far below 1). So the exactness
               the ratio gives away is taken back by a law: the test
               recomputes every partial, '((partial_mismatch: N))' must be 0.
               Verbatim regions are exempt from the ratio.
    fast-math  BROKEN: the same source compiled with -ffast-math. The
               'accurate' row equals the 'forward' row: the correction is
               gone. Law 'accurate_units > 2' -- the claim fails.

READING THE GOOD  orders: the six results differ in their last digits,
'accurate' is closest to exact; fast-math: 'accurate' = 'forward'.
______________________________________________________________________________
"""
import itertools
import os
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, COUNT, WORKERS = 19650101, 100000, 4
U = 2.0 ** -53
CHOICE_DB = {"orders": ["-O2"], "parallel": ["-O2"], "fast-math": ["-O2", "-ffast-math"]}


def values():
    rng = DeterministicStream(SEED)
    return [rng.next_float() * 10.0 ** rng.next_int(-6, 6) * (1 if rng.coin(0.6) else -1) for _ in range(COUNT)]


def exact_sum(xs):
    return Fraction(sum(int(Fraction(x) * 2 ** 1074) for x in xs), 2 ** 1074)


def naive(xs):
    s = 0.0
    for x in xs:
        s += x
    return s


def main(choice):
    xs = values()
    exact = exact_sum(xs)
    abs_sum = float(exact_sum([abs(x) for x in xs]))
    unit_err = U * abs_sum
    build = tempfile.mkdtemp()
    try:
        binary = os.path.join(build, "sum")
        subprocess.run(["gcc", "-Wall", "-Werror"] + CHOICE_DB[choice] + ["-o", binary, os.path.join(HERE, "..", "sum.c"), "-lm", "-lpthread"],
                       check=True)
        args = ["orders"] if choice != "parallel" else ["parallel", str(WORKERS)]
        out = subprocess.run([binary] + args, input="".join(x.hex() + "\n" for x in xs),
                             capture_output=True, text=True, check=True).stdout.splitlines()
    finally:
        shutil.rmtree(build)

    print("## seed %d" % SEED)
    print("unit: sum.c, gcc %s; %d doubles, magnitudes 1e-6..1e6, 60 %% positive" % (" ".join(CHOICE_DB[choice]), COUNT))
    print("exact sum      %.17g   (rounded to double)" % float(exact))
    print("u * sum|x|     %.3e   (u = 2^-53; Kahan's bound is 2 of these)" % unit_err)
    print()
    if choice != "parallel":
        print("##! verbatim")
        print("  order          result                 error vs exact   in u*sum|x|")
        for line in out:
            name, value = line.split()
            err = abs(Fraction(float(value)) - exact)
            print("  %-12s  %-21s  %14.3e   %10.2f" % (name, value, float(err), float(err) / unit_err))
        print("####")
        accurate = float(out[-1].split()[1])
        units = float(abs(Fraction(accurate) - exact)) / unit_err
        forward = [l.split()[1] for l in out if l.split()[0] == "forward"]
        if forward and forward[0] == out[-1].split()[1]:
            print("NOTE accurate == forward, bit for bit: the compensation was optimized away")
        print("sum_accurate(): error ((accurate_units: %.2f)) u*sum|x|   law <= 2   %s"
              % (units, "kept" if units <= 2 else "BROKEN"))
        return

    chunk = COUNT // WORKERS
    expected = [naive(xs[k * chunk:(k + 1) * chunk]) for k in range(WORKERS)]
    partial_list = [l for l in out if l.startswith("worker")]
    total = float(out[-1].split()[1])
    mismatch = 0
    print("PARTIALS  as the workers reported them (arrival order differs run to run)")
    print("##! potpourri")
    for l in partial_list:
        w = l.split()
        mismatch += float(w[-1]) != expected[int(w[1])]
        print(l)
    print("####")
    print("partials differing from the test's own recomputation ((partial_mismatch: %d))   law == 0   %s"
          % (mismatch, "kept" if mismatch == 0 else "BROKEN"))
    print()
    sums = {}
    for order in itertools.permutations(range(WORKERS)):
        s = 0.0
        for k in order:
            s += expected[k]
        sums.setdefault(s, []).append("".join(map(str, order)))
    print("ALL %d ARRIVAL ORDERS give %d distinct totals" % (sum(len(v) for v in sums.values()), len(sums)))
    print("##! verbatim")
    for s in sorted(sums):
        print("  %-21s  error %9.3e  %4.2f u*sum|x|   orders %s"
              % ("%.17g" % s, float(abs(Fraction(s) - exact)), float(abs(Fraction(s) - exact)) / unit_err, " ".join(sums[s])))
    print("####")
    print("unit total %.17g   (compared with a ratio of 1e-15)" % total)
    print("the unit's total is one of the arrival totals ((known: \"%s\"))   law: yes   %s"
          % ("yes" if total in sums else "no", "kept" if total in sums else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
