#! /usr/bin/env python3
# @hwut {
#     title    = "UART byte FIFO against a model: a structured space (capacity x load) filled with seeded random operations"
#     features = ["model-agrees", "cell-seeds"]
#     choices {
#         modulo { features = ["model-agrees", "cell-seeds", "index-wraps"]
#                  tolerance { constraints = ["diverging == 0"] } }
#         mask   { features = ["model-agrees", "cell-seeds", "index-wraps", "divergence-named"]
#                  tolerance { constraints = ["diverging > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the agreement of the UART byte FIFO (../rb.c or ../rb_mask.c) with a
         bounded-queue model, per capacity x load cell
REQUIREMENT  The byte FIFO behaves like a bounded queue for every capacity
             1..64 a driver may choose: push refuses only when full, pop
             only when empty, bytes come out in the order they went in.

The unit is C: '../rb.c' (index wrap with %) and '../rb_mask.c' (the "fast"
wrap with '& (cap - 1)', right only for powers of two). The model is a
Python list with a capacity check.

THE GENERATOR INSTRUCTIONS -- structure from space_iterator, content from
DeterministicStream:

    CAPACITY = [1, 2, 3, 4, 5, 7, 8, 64]      edges, powers of two and not
    LOAD     = push-heavy 0.7 | balanced 0.5 | pop-heavy 0.3   (P(push))
    for cap, load in space_iterator.do([CAPACITY, LOAD]):          24 cells
        stream = DeterministicStream(seed_of("cap=%d load=%s"))
        operations: push stream.next_int(0, 255) if stream.coin(P) else pop
        UNTIL 512 bytes went in

The STRUCTURED part names what must be covered and is reviewed as the
matrix's axes: one capacity per class (1, powers of two, others, the
maximum) under every load (mostly full, mostly empty, in between). The
capacities 6 and 9..63 are not run: they stand for their classes, and the
requirement's "every capacity" rests on that split. The RANDOM part fills
each cell with operations nobody has to write. The WALK LENGTH is a border
too: an index kept in a byte goes wrong only when it wraps 255 -> 0, after
256 bytes. A fixed number of operations would not get there where the
FIFO sits full and refuses (push-heavy); so a cell walks until 512 bytes
went in -- every index passes two byte wraps, whatever the load -- and the
GOOD prints the shortest and the longest walk. Each cell has its
OWN seed, a CRC32 of the cell's name: adding a capacity later does not
change the operations of the cells that were there (a single stream walked
across the cells would). The seed is mapped into 1..2^31-2, the seeds on
which the generator is alive (see ../../seed-sweep).

modulo  every cell agrees with the model: law 'diverging == 0'.
mask    exactly the columns 3, 5, 7 diverge -- under every load -- and
        1, 2, 4, 8, 64 agree: the matrix itself says "power of two". The
        first divergence of each cell is the operation number; the first
        failing cell is printed as its operation history. Law
        'diverging > 0'.

HOW TO READ THE GOOD   Rows: load; columns: capacity; 'ok' or the number
of the first operation where FIFO and model answer differently ('##!
verbatim': a cell's column is its capacity). Below it, for the first
failing cell, the last operations before the divergence. All exact, except
the binding '((diverging: N))', judged by the law.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
CAPACITY = [1, 2, 3, 4, 5, 7, 8, 64]
LOAD = [("push-heavy", 0.7), ("balanced", 0.5), ("pop-heavy", 0.3)]
TRAVEL = 512        # bytes pushed per cell: two turns of an 8-bit index
CHOICE_DB = {"modulo": "rb.c", "mask": "rb_mask.c"}


def seed_of(name):
    return 1 + zlib.crc32(name.encode()) % (2**31 - 2)


def operations(cap, load):
    """Seeded operations until TRAVEL pushes were accepted (the model's fill
    level decides acceptance, so refused pushes do not count)."""
    (load_name, p_push) = load
    stream = DeterministicStream(seed_of("cap=%d load=%s" % (cap, load_name)))
    ops, n, pushed = [], 0, 0
    while pushed < TRAVEL:
        if stream.coin(p_push):
            ops.append(("+", stream.next_int(0, 255)))
            if n < cap:
                n, pushed = n + 1, pushed + 1
        else:
            ops.append(("-", None))
            n = max(0, n - 1)
    return ops


def model(cap, ops):
    queue, answers = [], []
    for op, v in ops:
        if op == "+":
            answers.append("full" if len(queue) == cap else "ok")
            if len(queue) < cap:
                queue.append(v)
        else:
            answers.append(str(queue.pop(0)) if queue else "empty")
    return answers


def run_unit(source, cells):
    script = []
    for cap, _, ops in cells:
        script.append("cap %d" % cap)
        script += ["+ %d" % v if op == "+" else "-" for op, v in ops]
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "drive")
        subprocess.check_call(["gcc", "-O2", "-Wall", "-Werror", "-I", UNIT, "-o", exe,
                               os.path.join(UNIT, "drive.c"), os.path.join(UNIT, source)])
        out = subprocess.run([exe], input="\n".join(script) + "\n", capture_output=True,
                             text=True, check=True).stdout.split()
    answers = []
    for _, _, ops in cells:
        answers.append(out[:len(ops)])
        out = out[len(ops):]
    return answers


def main(choice):
    cells = [(cap, load, operations(cap, load)) for cap, load in space_iterator.do([CAPACITY, LOAD])]
    answers = run_unit(CHOICE_DB[choice], cells)
    first = {}
    for (cap, load, ops), got in zip(cells, answers):
        want = model(cap, ops)
        diff = [i for i in range(len(ops)) if got[i] != want[i]]
        first[(cap, load[0])] = (diff[0] if diff else None, ops, got, want)

    print("unit:  ../%s against a bounded-queue model" % CHOICE_DB[choice])
    walks = sorted((len(ops), cap, load[0]) for cap, load, ops in cells)
    print("space: CAPACITY %s x LOAD %s = %d cells"
          % (CAPACITY, [n for n, _ in LOAD], len(cells)))
    print("walk:  seeded operations until %d bytes went in (two turns of an 8-bit index)" % TRAVEL)
    print("       shortest %d ops (capacity %d, %s), longest %d ops (capacity %d, %s)"
          % (walks[0] + walks[-1]))
    print("cells: 'ok' agrees with the model; 'op N' = first operation that differs")
    print()
    print("##! verbatim")
    print("  load \\ capacity " + "".join("%7d" % c for c in CAPACITY))
    for name, p in LOAD:
        row = []
        for cap in CAPACITY:
            k = first[(cap, name)][0]
            row.append("ok" if k is None else "op %d" % (k + 1))
        print("  %-10s P=%.1f " % (name, p) + "".join("%7s" % r for r in row))
    print("####")
    print()
    failing = [(cap, name) for name, _ in LOAD for cap in CAPACITY if first[(cap, name)][0] is not None]
    if failing:
        cap, name = failing[0]
        k, ops, got, want = first[(cap, name)]
        print("first diverging cell: capacity %d, %s, seed %d"
              % (cap, name, seed_of("cap=%d load=%s" % (cap, name))))
        print("     op  action    FIFO    model")
        if k - 5 > 0:
            print("    (ops 1-%d agree)" % (k - 5))
        for i in range(max(0, k - 5), k + 1):
            op, v = ops[i]
            print(("    %3d  %-8s  %-6s  %-6s%s" % (i + 1, "push %d" % v if op == "+" else "pop", got[i], want[i],
                                                  "   <- differs" if got[i] != want[i] else "")).rstrip())
        bad_caps = sorted(set(c for c, _ in failing))
        power = lambda c: c & (c - 1) == 0
        pattern = ""
        if not any(power(c) for c in bad_caps) and all(c in bad_caps for c in CAPACITY if not power(c)):
            pattern = " -- exactly the capacities that are not a power of two"
        print("!! the FIFO is no bounded queue for capacities %s%s" % (bad_caps, pattern))
    print("cells that diverge from the model ((diverging: %d)) of %d   law == 0   %s"
          % (len(failing), len(cells), "kept" if not failing else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
