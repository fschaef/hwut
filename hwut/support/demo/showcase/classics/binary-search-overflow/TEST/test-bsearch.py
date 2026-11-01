#! /usr/bin/env python3
# @hwut {
#     title    = "Bloch 2006: binary search on arrays near 2^31 -- the midpoint overflows"
#     choices {
#         div2 { features = ["index-space", "overflow-named"]
#                tolerance { constraints = ["failures > 0"] } }
#         ushr { features = ["index-space", "every-search-right"]
#                tolerance { constraints = ["failures == 0"] } }
#         sub  { features = ["index-space", "every-search-right"]
#                tolerance { constraints = ["failures == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the answers of one binarySearch implementation for keys present
         and absent, over array lengths up to 2^31 - 1
HISTORY  On 2 June 2006 Joshua Bloch wrote on the Google Research blog
("Extra, Extra - Read All About It: Nearly All Binary Searches and
Mergesorts are Broken") that the binary search he had written for the JDK's
java.util.Arrays -- and the one in Bentley's 'Programming Pearls' -- fails
for arrays of more than about 2^30 elements: in 'int mid = (low + high) / 2'
the sum overflows to a negative int, and the program throws
ArrayIndexOutOfBoundsException. The bug had sat there for about nine years,
until arrays that large became common. His fixes: 'low + ((high - low) / 2)'
and, in Java, '(low + high) >>> 1'.

REQUIREMENT  binarySearch finds every key of a sorted int[] of ANY legal
             length (up to 2^31 - 1), and reports every absent key by its
             insertion point -- the midpoint never leaves [low, high].

THE UNIT  '../bsearch.c': the JDK algorithm in C with Java's int (32 bit,
wrapping: -fwrapv). The array is virtual, a[i] = i, so that lengths near
2^31 need no 8 GiB; the accessor checks bounds as the JVM does. The choice
selects the midpoint line (-DMIDPOINT=...).

THE TESTED SPACE  space_iterator over [LENGTHS, KEYS]:
    LENGTHS  0, 1, 2, 3, 7, 8, 1000         -- the requirement says ANY
             length: the empty array, the smallest ones, a typical one;
             2^30, 2^30+2, 3*2^29, 2^31-1   -- where low + high can
             first exceed 2^31 - 1, and the largest legal length
    KEYS     0, n/2, 3n/4, n-2, n-1, n       -- the bottom, the middle, the
             upper half (where low grows past 2^30), the top, and the
             first absent key above the top
The truth is a[i] = i: key 0 <= k < n is found at k; k = n is absent,
insertion point n; for tiny n a key below 0 (n-2 at n = 1) is absent,
insertion point 0.

CHOICES
    div2   '(low + high) / 2' as in Bloch's post: every search into the
           upper half of a long array dies with a negative index.
    ushr   Java's '>>>' fix: the sum is read unsigned, then halved.
    sub    'low + (high - low) / 2': the sum never forms.

HOW TO READ THE GOOD  The matrix: lengths down, keys across; 'ok' is a
right answer, 'AIOOBE' a search that ended out of bounds, 'WRONG' a wrong
answer. Under it, each failure with low, high, the wrapped sum and the
midpoint that left the array. Rows up to 2^30 are all 'ok' in every choice:
there low + high <= 2^31 - 2. '##! verbatim' around the matrix (columns are
keys); all else exact. The verdict is '((failures: N))': law 'failures == 0'
for the fixes, 'failures > 0' for the historical line.
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
MID_DB = {"div2": ("MID_DIV2", "int mid = (low + high) / 2;"),
          "ushr": ("MID_USHR", "int mid = (low + high) >>> 1;"),
          "sub":  ("MID_SUB",  "int mid = low + (high - low) / 2;")}
LENGTHS = [("0", 0), ("1", 1), ("2", 2), ("3", 3), ("7", 7), ("8", 8), ("1000", 1000),
           ("2^30", 2**30), ("2^30+2", 2**30 + 2), ("3*2^29", 3 * 2**29), ("2^31-1", 2**31 - 1)]
KEYS = [("0", lambda n: 0), ("n/2", lambda n: n // 2), ("3n/4", lambda n: 3 * n // 4),
        ("n-2", lambda n: n - 2), ("n-1", lambda n: n - 1), ("n", lambda n: n)]


def run_unit(macro, pairs):
    build = tempfile.mkdtemp(prefix="bsearch-")
    try:
        exe = os.path.join(build, "bsearch")
        subprocess.run(["gcc", "-O2", "-fwrapv", "-Wall", "-Werror", "-DMIDPOINT=" + macro,
                        "-o", exe, os.path.join(HERE, "..", "bsearch.c")], check=True)
        text = "".join("%d %d\n" % p for p in pairs)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
        return out.splitlines()
    finally:
        shutil.rmtree(build, True)


def judge(n, key, line):
    word = line.split()
    if word[0] == "AIOOBE":
        return "AIOOBE"
    if 0 <= key < n:
        right = "found %d" % key
    else:
        right = "absent insert %d" % (0 if key < 0 else n)
    return "ok" if line.startswith(right + " ") else "WRONG"


def main(choice):
    macro, source_line = MID_DB[choice]
    space = list(space_iterator.do([LENGTHS, KEYS]))
    pairs = [(n, kf(n)) for (_, n), (_, kf) in space]
    lines = run_unit(macro, pairs)
    print("midpoint: %s    array: a[i] = i, int indices (32 bit, wrapping)" % source_line)
    print("space: space_iterator over %d lengths x %d keys = %d searches" % (len(LENGTHS), len(KEYS), len(space)))
    print()
    print("##! verbatim")
    print("length n  \\ key " + "".join("%8s" % k for k, _ in KEYS))
    failure_list = []
    for i, (length_name, n) in enumerate(LENGTHS):
        row = ""
        for j, (key_name, _) in enumerate(KEYS):
            k = i * len(KEYS) + j
            verdict = judge(n, pairs[k][1], lines[k])
            row += "%8s" % verdict
            if verdict != "ok":
                failure_list.append((length_name, key_name, lines[k]))
        print("%-16s%s" % (length_name, row))
    print("####")
    print("(n-1 is the last element; key n is absent: the answer is its insertion point n;")
    print(" AIOOBE = ArrayIndexOutOfBoundsException: the midpoint left the array)")
    print()
    group = []                                 # one line per length and arithmetic
    for length_name, key_name, line in failure_list:
        w = line.split()
        what = ("low %s + high %s = %s in int -> mid %s, outside the array (probe %s)"
                % (w[4], w[6], w[8], w[2], w[10]) if w[0] == "AIOOBE" else "wrong answer: " + line)
        if group and group[-1][0] == length_name and group[-1][2] == what:
            group[-1][1].append(key_name)
        else:
            group.append((length_name, [key_name], what))
    for length_name, key_list, what in group:
        print("FAIL  n = %-7s keys %-24s %s" % (length_name, ", ".join(key_list), what))
    print("searches failed: ((failures: %d)) of %d   law == 0   %s"
          % (len(failure_list), len(space), "kept" if not failure_list else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in MID_DB:
        print("choices: %s" % ", ".join(MID_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
