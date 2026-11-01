#! /usr/bin/env python3
#
# @hwut {
#     title   = "Sorting records by one key: equal keys keep their input order"
#     choices {
#         merge-c { features = ["by-key", "stable"]
#                   tolerance { constraints = ["unsorted == 0", "reordered == 0"] } }
#         sort-s  { features = ["by-key", "stable"]
#                   tolerance { constraints = ["unsorted == 0", "reordered == 0"] } }
#         qsort-c { features = ["by-key"]
#                   tolerance { constraints = ["unsorted == 0", "reordered == 0"] } }
#         sort-k  { features = ["violation-shown"]
#                   tolerance { constraints = ["unsorted == 0", "reordered > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the order one sorter (sortrec merge/qsort, sort -k, sort -s) gives
         the records of one input, sorted by dept
REQUIREMENT. Records 'name,dept' sorted by dept:
    R1  come out in dept order (by-key);
    R2  records with the same dept keep their input order (stable) -- the
        second pass of a 'sort by name, then by dept' relies on it.

CHOICES -- four sorters, one question:
    merge-c  ../sortrec.c 'merge', a merge sort that takes the left one of
             two equals: holds.
    sort-s   GNU 'sort -s -t, -k2,2': holds.
    qsort-c  ../sortrec.c 'qsort', the C library's qsort(): NOT a stable
             sorter -- ISO C promises nothing about equal keys. It is a
             portability canary, linked to 'by-key' only, never to 'stable':
             glibc 2.39 happens to sort by merging when it can allocate, the
             GOOD pins what this platform does, and a libc that sorts in
             place (musl, glibc 2.37) turns it red -- a warning that code
             relying on it is not portable, not a bug in qsort().
    sort-k   GNU 'sort -t, -k2,2' without -s: equal keys fall through to the
             LAST-RESORT comparison of the whole line, so they come out by
             name -- R2 breaks on nearly every random array.

HWUT CONCEPTS. The picture is a fixed sample of 12 records whose tags (the
input line numbers) show the order inside each dept: exact text. The law is
judged on 300 random arrays per run (clock seed, '##' comment): the counts
of broken arrays are constraint bindings, judged by the choice's rule; the
number of arrays is fixed and printed as plain text. 'sort-k' states the
violation as its law ('reordered > 0'), so its accepted page is the report.

READING THE GOOD. Left the input with tags, right the output. Under it, per
dept, the tags in output order: increasing means 'kept'. The random-array
counts carry their law and verdict. The qsort-c page says on its face that
the stability it shows is this libc's, not a promise of ISO C.
______________________________________________________________________________
"""
import os
import random
import string
import subprocess
import sys
import tempfile
import atexit
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
SAMPLE = [("zoe", "ops"), ("bob", "sales"), ("ann", "dev"), ("kim", "ops"), ("al", "sales"),
          ("max", "dev"), ("eve", "ops"), ("dan", "sales"), ("cy", "dev"), ("ben", "ops"),
          ("ida", "sales"), ("lou", "dev")]



def scratch(prefix):
    """RETURN: a fresh scratch directory, removed when the test ends."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path

def command(choice):
    if choice in ("merge-c", "qsort-c"):
        exe = os.path.join(scratch("sortrec-"), "sortrec")
        subprocess.run(["gcc", "-O2", "-o", exe, os.path.join(TOP, "sortrec.c")], check=True)
        return [exe, choice[:-2]]
    if choice == "sort-s":
        return ["sort", "-s", "-t,", "-k2,2"]
    return ["sort", "-t,", "-k2,2"]


def run(cmd, records):
    text = "".join("%s,%s\n" % r for r in records)
    out = subprocess.run(cmd, input=text, capture_output=True, text=True, check=True,
                         env=dict(os.environ, LC_ALL="C")).stdout
    return [tuple(line.split(",")) for line in out.splitlines()]


def judge(records, result):
    """RETURN: (sorted_ok, kept_ok, per-dept tag lists in output order)."""
    tag_db = {r: i + 1 for i, r in enumerate(records)}
    group_db = {}
    for r in result:
        group_db.setdefault(r[1], []).append(tag_db[r])
    keys = [r[1] for r in result]
    return keys == sorted(keys), all(t == sorted(t) for t in group_db.values()), group_db


def main(choice):
    cmd = command(choice)
    print("sorter: %s" % " ".join(os.path.basename(c) for c in cmd))
    if choice == "qsort-c":
        print("NOTE qsort(): ISO C promises no stability -- 'kept' below pins THIS libc's")
        print("     behaviour (glibc 2.39 merges when it can allocate); it is not guaranteed")
    result = run(cmd, SAMPLE)
    print("##! verbatim")
    print("  tag  input           |  output          tag")
    for k, (rin, rout) in enumerate(zip(SAMPLE, result)):
        print("  %3d  %-5s %-8s  |  %-5s %-8s  %3d" % (k + 1, rin[0], rin[1], rout[1], rout[0],
                                                      SAMPLE.index(rout) + 1))
    print("####")
    sorted_ok, kept_ok, group_db = judge(SAMPLE, result)
    print("by dept: %s" % ("in order" if sorted_ok else "OUT OF ORDER"))
    for dept in sorted(group_db):
        tags = group_db[dept]
        print("  %-6s tags %-14s %s" % (dept, " ".join(map(str, tags)),
                                         "kept" if tags == sorted(tags) else "REORDERED"))

    seed = time.time_ns()
    rng = random.Random(seed)
    unsorted = reordered = 0
    n = 300
    for _ in range(n):
        names = set()
        while len(names) < 60:
            names.add("".join(rng.choice(string.ascii_lowercase) for _ in range(4)))
        records = [(name, rng.choice(("dev", "ops", "sales"))) for name in names]
        sorted_ok, kept_ok, _ = judge(records, run(cmd, records))
        unsorted += not sorted_ok
        reordered += not kept_ok
    print("## seed %d" % seed)
    print("random arrays: %d of 60 records, 3 depts" % n)
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("  not in dept order        ((unsorted: %d))   %s" % (unsorted, law(unsorted)))
    print("  equal depts reordered    ((reordered: %d))   %s" % (reordered, law(reordered)))


if len(sys.argv) < 2 or sys.argv[1] not in ("merge-c", "sort-s", "qsort-c", "sort-k"):
    print("choices: merge-c, sort-s, qsort-c, sort-k")
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
