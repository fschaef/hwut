#! /usr/bin/env python3
# @hwut {
#     title    = "LRU cache (4 slots): hits, misses, and who gets evicted"
#     choices {
#         lru        { features = ["evicts-lru", "hit-refreshes"]
#                      tolerance { constraints = ["wrong_evictions == 0"] } }
#         lru-update { features = ["evicts-lru", "put-refreshes"]
#                      tolerance { constraints = ["wrong_evictions == 0"] } }
#         nofresh    { features = ["wrong-eviction-named"]
#                      tolerance { constraints = ["wrong_evictions > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the LRU cache's contents and evictions after each operation of one
         trace, against the evictions the specification predicts
REQUIREMENT  When the cache is full and a new key comes in, the entry evicted
             is the one used least recently -- a hit (get) and an update
             (put of a present key) both count as a use.

The unit is C ('../lru.c', static slots in a linked list), driven by
'../drive.c' with a trace of operations. One row per operation:

    step  op        result      cache, most recent first     evicted

the cache column printed by the UNIT itself (its own list, head to tail),
and in the last column the eviction judged against the specification: of
all keys in the cache before the operation, the one whose last use (get or
put) lies furthest back -- kept here in a few lines ('ok' or '!! ...').

lru         a trace that reads A and B before E comes in: C goes, not A.
lru-update  re-putting a present key refreshes it like a read does.
nofresh     the BROKEN FIXTURE '../lru_nofresh.c' (a hit no longer moves the
            entry to the head) under the 'lru' trace: the cache column stops
            reordering on hits, and every eviction after a hit is wrong --
            the GOOD file is the accepted report, '!!' on each such row.

HWUT CONCEPTS  A table whose every column is exact needs no '##! table'
region (that region earns its place with per-column rules); plain lines
are compared line by line, and the column alignment is for the reader.
Deterministic: no tolerance. The number of wrong evictions is a constraint
binding, '((wrong_evictions: N))': 'wrong_evictions == 0' for lru and
lru-update, '> 0' for nofresh -- so 'hwut.accept' refuses a re-recording
that evicts against the specification, or a nofresh that no longer shows
it. A reviewer scans the last column for '!!' and reads the cache column as
a picture of the list.
______________________________________________________________________________
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
TRACE_DB = {
    "lru":        "put A 1, put B 2, put C 3, put D 4, get A, get B, put E 5, get C, "
                  "get A, put F 6, get D, get E, put G 7, get B, get A",
    "lru-update": "put A 1, put B 2, put C 3, put D 4, put A 10, put E 5, get A, "
                  "put C 30, put F 6, get B, get C",
}
CHOICE_DB = {"lru": ("lru.c", "lru"), "lru-update": ("lru.c", "lru-update"),
             "nofresh": ("lru_nofresh.c", "lru")}


def run_unit(unit, trace):
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "drive")
        subprocess.check_call(["gcc", "-Wall", "-Werror", "-I", UNIT, "-o", exe,
                               os.path.join(UNIT, "drive.c"), os.path.join(UNIT, unit)])
        out = subprocess.run([exe], input="\n".join(op.strip() for op in trace.split(",")),
                             capture_output=True, text=True, check=True).stdout
    return [line.split() for line in out.splitlines()]


def main(choice):
    unit, trace_name = CHOICE_DB[choice]
    trace = TRACE_DB[trace_name]
    last_use = {}                  # THE SPECIFICATION: key -> step of its last use
    before = ""                    # the unit's content before the operation
    print("unit: %s, 4 slots; trace '%s'" % (unit, trace_name))
    print()
    print("step  op         result    cache (most recent first)   evicted")
    print("----  ---------  --------  --------------------------  -------")
    hit_n = wrong_n = 0
    for step, (op, key, hit, value, evicted, keys) in enumerate(run_unit(unit, trace), 1):
        expect = None
        if op == "put" and key not in before and len(before) == 4:
            expect = min(before, key=lambda k: last_use[k])
        if op == "put" or key in before:
            last_use[key] = step
        before = keys
        hit_n += hit == "hit"
        if evicted == "-" and expect is None:
            judged = "-"
            if hit == "hit" and keys[0] != key:
                judged = "-   !! hit not moved to the front"
        elif evicted == expect:
            judged = "%s   ok" % evicted
        else:
            judged = "%s   !! least recently used was %s" % (evicted, expect)
            wrong_n += 1
        cache = "[%s]" % " ".join(keys.ljust(4, "."))
        op_text = "%s %s%s" % (op, key, " " + value if op == "put" else "")
        result = "hit %s" % value if hit == "hit" else hit if hit != "-" else "-"
        print(("%4d  %-9s  %-8s  %-26s  %s" % (step, op_text, result, cache, judged)).rstrip())
    get_n = sum(1 for op in trace.split(",") if op.strip().startswith("get"))
    print()
    print("hits: %d of %d gets" % (hit_n, get_n))
    print("(cache: '.' an empty slot; result and evicted: '-' none)")
    print("evictions against the specification: ((wrong_evictions: %d))   law == 0   %s"
          % (wrong_n, "kept" if not wrong_n else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
