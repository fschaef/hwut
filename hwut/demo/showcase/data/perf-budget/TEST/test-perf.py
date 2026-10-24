#! /usr/bin/env python3
#
# @hwut {
#     title   = "Performance budget: the field splitter scales linearly"
#     choices {
#         current { features = ["correct", "linear", "throughput"]
#                   tolerance { constraints = ["exponent <= 1.5", "throughput >= 100 MB/s"] } }
#         v1      { features = ["violation-shown"]
#                   tolerance { constraints = ["exponent > 1.5", "throughput < 100 MB/s"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the time and throughput of count_fields() (../fields.c or
         ../fields_v1.c) over CSV lines of 2..32 KiB, and the fitted growth
REQUIREMENT. count_fields() splits a CSV line in place (lines of 2..32 KiB
from a log shipper):
    R1  the field count is right (exact);
    R2  time grows linearly: fitted as time ~ size^k over 2..32 KiB, k is at
        most 1.5 (the slack is for caches and branch prediction; a
        quadratic routine has k = 2);
    R3  at 32 KiB it processes at least 100 MB/s.

CHOICES -- the same lines, two builds:
    current  ../fields.c: strlen() once before the loop. All hold.
    v1       ../fields_v1.c: 'i < strlen(s)' in the loop condition, and the
             loop writes into s, so the compiler cannot hoist it: every step
             scans the rest of the line again -- quadratic. Same counts,
             R2 and R3 break.

HWUT CONCEPTS.
  * '##! table ignore=2,3,4': each row is size, fields, ns, MiB/s, bar.
    Size and field count are compared exactly (R1); the measured columns
    are shown but ignored -- they are the machine's, not the program's.
  * The budget is stated as constraint bindings: '((exponent: k))' is the
    slope of log(time) over log(size), '((throughput: m MiB/s))' the
    throughput at 32 KiB; the choice's rules judge them, never the recorded
    numbers. An exponent, not a time: it does not care how fast this
    machine is.
  * UNITS: the program measures KiB, so it prints throughput in BINARY
    units (MiB/s); the budget comes from the log shipper's sizing sheet in
    DECIMAL units, 'throughput >= 100 MB/s'. The comparison converts
    (940 MiB/s = 986 MB/s); nobody has to remember which one a column
    meant. A throughput printed in GiB/s under a 'MiB/s' label, or a time
    where a rate belongs, breaks the law. CAVEAT: pint counts bytes as
    dimensionless, so a frequency ('10 GHz') would also pass a law in
    MB/s -- the unit is checked for its value, not for being data.
  * Each time is the fastest of many repetitions inside the program, so a
    busy machine (hwut runs choices in parallel) slows the median, not the
    minimum. The thresholds sit far from both builds: linear k ~1.1,
    ~900 MiB/s; quadratic k ~1.9, ~5 MiB/s.

READING THE GOOD. The bar is log-scaled: four '=' per doubling of time (the
GOOD says so above the table). A linear routine's bars grow by 4 per row
(the size doubles); a quadratic one's by 8. The R2 and R3 lines name the
budget the binding is judged by, and end in 'holds' or 'BROKEN'. MiB/s
beside MB/s is deliberate: the program speaks binary units, the budget
decimal ones, and the comparison converts.
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

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
SIZES_KIB = (2, 4, 8, 16, 32)



def scratch(prefix):
    """RETURN: a fresh scratch directory, removed when the test ends."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path

def build(source):
    exe = os.path.join(scratch("fields-"), "fields")
    subprocess.run(["gcc", "-O2", "-o", exe, os.path.join(TOP, source)], check=True)
    return exe


def line_of(kib):
    """RETURN: a CSV line of exactly kib KiB; fixed seed: the same every run."""
    rng = random.Random(kib)
    parts, size = [], 0
    while size < kib * 1024:
        if rng.random() < 0.3:     # a quoted cell with a comma inside
            cell = '"%s,%s"' % ("x" * rng.randint(1, 5), "z" * rng.randint(1, 5))
        else:
            cell = "y" * rng.randint(1, 9)
        parts.append(cell)
        size += len(cell) + 1
    return ",".join(parts)[:kib * 1024]


def main(choice):
    source = "fields.c" if choice == "current" else "fields_v1.c"
    exe = build(source)
    print("count_fields() from %s, fastest of 30 runs per size" % source)
    print("log-time bar: log2 of the time, 4 '=' per doubling (linear: +4 per row, quadratic: +8)")
    print("##! table ignore=2,3,4")
    print("size_KiB  fields       ns    MiB/s  log-time")
    ns_db = {}
    for kib in SIZES_KIB:
        line = line_of(kib)
        out = subprocess.run([exe, "30"], input=line + "\n", capture_output=True, text=True, check=True).stdout
        bytes_, _, fields, _, ns, _ = out.split()
        ns_db[kib] = max(int(ns), 1)
        mibps = int(bytes_) / ns_db[kib] * 1e9 / 2 ** 20
        bar = "=" * max(1, round(4 * math.log2(ns_db[kib] / 500)))
        print("%8d %7s %8d %8.0f  %s" % (kib, fields, ns_db[kib], mibps, bar))
    print("####")
    xs = [math.log2(k) for k in SIZES_KIB]
    ys = [math.log2(ns_db[k]) for k in SIZES_KIB]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    mibps = 32 * 1024 / ns_db[32] * 1e9 / 2 ** 20
    ok = lambda flag: "holds" if flag else "BROKEN"
    print("R2 time grows as size^k, fitted over the five sizes: k = ((exponent: %.2f)), budget k <= 1.5   %s"
          % (slope, ok(slope <= 1.5)))
    print("R3 throughput at 32 KiB = ((throughput: %.0f MiB/s)), budget >= 100 MB/s   %s"
          % (mibps, ok(mibps * 2 ** 20 >= 100e6)))


if len(sys.argv) < 2 or sys.argv[1] not in ("current", "v1"):
    print("choices: current, v1")
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
