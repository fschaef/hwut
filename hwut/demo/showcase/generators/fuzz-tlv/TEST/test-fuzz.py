#! /usr/bin/env python3
# @hwut {
#     title    = "TLV walker under a reproducible mutation fuzzer (DeterministicStream + a guard page)"
#     features = ["reproducible", "operators-spread"]
#     choices {
#         bounded  { features = ["reproducible", "operators-spread", "no-overread"]
#                    tolerance { constraints = ["overread == 0"] } }
#         trusting { features = ["reproducible", "operators-spread", "overread-reproduced"]
#                    tolerance { constraints = ["overread > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the outcome (parsed, rejected, OVERREAD) of tlv_walk (../tlv*.c) on
         3000 fuzzed blocks, per mutation operator
REQUIREMENT  tlv_walk never reads outside the block it is given, whatever
             the bytes; a malformed block is answered with -1.

The unit is C: '../tlv.c' and '../tlv_trusting.c' (release 2.3, which trusts
the length byte of a record). '../drive.c' copies every case into a heap
block so that it ends right at a PROT_NONE guard page (the Electric-Fence
trick): the first byte read past the block faults, the fault is caught and
the case is reported as OVERREAD, and the run goes on with the next case.

THE GENERATOR INSTRUCTION -- the tested space, as one sentence:

    stream = DeterministicStream(2026); 3000 cases; per case:
        block    = stream.select(corpus)                (../corpus.txt)
        operator = stream.select_unchosen(OPERATORS, marker)
        operator(block, stream)       position and byte from the stream

The six operators are the classic byte-level mutations: flip one bit, set a
byte to 00 or FF (FF in a length byte is "255 bytes follow"), cut the block
short, insert a byte, repeat a byte. select_unchosen with one
SelectionMarker hands every operator out once before any repeats, so the
3000 cases split EXACTLY 500 per operator -- the spread is a property of
the generator, not luck, and the GOOD can state it exactly. Every count is
exact: the stream is the same on every machine, so the 3000 inputs are;
seed + case number reproduce any case without a stored file.

bounded   3000 cases: parsed or rejected, 0 overreads.
trusting  the length byte is trusted: the overreads are counted per
          operator, and the first one is printed as its reproducer --
          seed, case, operator, the block in hex.

HOW TO READ THE GOOD   The matrix operator x outcome must read 0 in the
'OVERREAD' column (a 0, never a blank: hwut folds blanks, and an empty
column would let the numbers slide into it). Each row sums to 500, the
total row to 3000. The overreads are a binding, '((overread: N))', judged
by the choice's law ('overread == 0' / '> 0'). Below: the reproducer, if
any. Everything else is exact.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import (DeterministicStream,
                                                                   SelectionMarker)

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
SEED, CASES = 2026, 3000
CHOICE_DB = {"bounded": "tlv.c", "trusting": "tlv_trusting.c"}


def flip_bit(b, s):
    i = s.next_int(0, len(b) - 1); b[i] ^= 1 << s.next_int(0, 7)


def byte_00(b, s):
    b[s.next_int(0, len(b) - 1)] = 0x00


def byte_ff(b, s):
    b[s.next_int(0, len(b) - 1)] = 0xFF


def cut_short(b, s):
    del b[s.next_int(0, len(b) - 1):]


def insert_byte(b, s):
    b.insert(s.next_int(0, len(b)), s.next_int(0, 255))


def repeat_byte(b, s):
    i = s.next_int(0, len(b) - 1); b.insert(i, b[i])


OPERATORS = [flip_bit, byte_00, byte_ff, cut_short, insert_byte, repeat_byte]


def generate():
    corpus = [bytes.fromhex(line.strip()) for line in open(os.path.join(UNIT, "corpus.txt"))
              if line.strip() and not line.startswith("#")]
    stream, marker = DeterministicStream(SEED), SelectionMarker()
    cases = []
    for k in range(CASES):
        block = bytearray(stream.select(corpus))
        op = stream.select_unchosen(OPERATORS, marker)
        op(block, stream)
        cases.append((k, op.__name__, bytes(block)))
    return cases


def run_unit(source, cases):
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "drive")
        subprocess.check_call(["gcc", "-O1", "-Wall", "-Werror", "-o", exe,
                               os.path.join(UNIT, "drive.c"), os.path.join(UNIT, source)])
        text = "".join("%d %s\n" % (k, block.hex() or "-") for k, _, block in cases)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
    result = dict(line.split() for line in out.splitlines())
    overread = set(int(k) for k, v in result.items() if v == "OVERREAD")
    return dict((int(k), int(v)) for k, v in result.items() if v != "OVERREAD"), overread


def main(choice):
    cases = generate()
    result, overread = run_unit(CHOICE_DB[choice], cases)
    print("generator: DeterministicStream(%d), %d cases, corpus ../corpus.txt" % (SEED, CASES))
    print("           block = select(corpus); operator = select_unchosen(OPERATORS, marker)")
    print("unit:      ../%s, each block ending at a guard page" % CHOICE_DB[choice])
    print()
    print("  %-12s %7s %9s %9s %7s" % ("operator", "parsed", "rejected", "OVERREAD", "total"))
    total = [0, 0, 0, 0]
    for op in OPERATORS:
        mine = [k for k, name, _ in cases if name == op.__name__]
        bad = sum(1 for k in mine if k in overread)
        parsed = sum(1 for k in mine if k not in overread and result.get(k, -1) >= 0)
        rejected = len(mine) - bad - parsed
        total = [t + v for t, v in zip(total, (parsed, rejected, bad, len(mine)))]
        print("  %-12s %7d %9d %9d %7d" % (op.__name__, parsed, rejected, bad, len(mine)))
    print("  %-12s %7d %9d %9d %7d" % tuple(["total"] + total))
    print()
    print("cases read outside the block ((overread: %d)) of %d   law == 0   %s"
          % (len(overread), CASES, "kept" if not overread else "BROKEN"))
    if overread:
        k = min(overread)
        _, name, block = cases[k]
        print("first reproducer: DeterministicStream(%d), case %d, operator %s" % (SEED, k, name))
        print("    block (%d bytes): %s" % (len(block), " ".join("%02x" % c for c in block)))
        print("    the walker touched the guard page right after byte %d" % (len(block) - 1))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
