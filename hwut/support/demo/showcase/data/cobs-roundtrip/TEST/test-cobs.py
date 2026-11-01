#! /usr/bin/env python3
#
# @hwut {
#     title   = "COBS framing: encode, decode, the same bytes -- on any frame"
#     choices {
#         current { features = ["examples", "round-trip", "no-zero", "overhead"]
#                   tolerance { constraints = ["err_short == 0", "err_long == 0", "err_edge == 0",
#                                              "zeros == 0", "over == 0"] } }
#         v1      { features = ["violation-shown"]
#                   tolerance { constraints = ["err_short == 0", "err_long > 0", "err_edge > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the frames the COBS codec (../cobs.c or ../cobs_v1.c) encodes and
         decodes: worked examples, per-class sweep counts, edge frames
REQUIREMENT. A COBS codec for a serial link (frames up to 1000 bytes):
    R1  decode(encode(f)) == f for every frame f (round-trip);
    R2  an encoded frame holds no 0x00 -- 0x00 is the frame delimiter;
    R3  overhead: at most 1 + n/254 (integer division) bytes on n bytes.

CHOICES -- the same test, two builds:
    current  ../cobs.c: all three hold.
    v1       ../cobs_v1.c, release 1.0: the decoder appends a zero after
             EVERY block, also after a full 254-byte block (code 0xFF),
             which stands for no zero. Only a run of 254 non-zero bytes
             shows it.

HWUT CONCEPTS AND WHY THE SAMPLE IS SHAPED. The worked examples are exact
text. The sweep (clock seed, '##' comment) draws three classes of fixed
size (plain text); their errors are counted separately as constraint
bindings:
    short   3000 frames of 0..64 random bytes -- a zero every 256 bytes
            on average, so a 254-byte run NEVER occurs: the v1 bug is
            invisible here (err_short == 0 for v1 too);
    long    300 frames of 0..1000 bytes with rare zeros: long runs;
    edge    fixed frames around the block length: 253, 254, 255, 508
            non-zero bytes, and 254 followed by a zero.
A sweep of short frames alone would bless v1 every time: the classes are
what makes the random test strong, and v1's law says so ('err_short == 0',
'err_long > 0').

READING THE GOOD. Examples: input bytes left, encoding right, every code
byte in brackets. The table counts per class; the edge list names each
fixed frame with 'ok' or what came back. Every count carries its law
('law == 0') and its verdict, 'kept' or 'BROKEN'.
______________________________________________________________________________
"""
import os
import random
import subprocess
import sys
import tempfile
import atexit
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
EXAMPLES = ["00", "0000", "11220033", "11223344", "11000000", ""]
EDGE_DB = {"253 x non-zero": bytes(range(1, 254)), "254 x non-zero": bytes(range(1, 255)),
           "255 x non-zero": bytes(range(1, 255)) + b"\x01",
           "508 x non-zero": bytes(range(1, 255)) * 2,
           "254 x non-zero, 00": bytes(range(1, 255)) + b"\x00"}



def scratch(prefix):
    """RETURN: a fresh scratch directory, removed when the test ends."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path

def build(source):
    exe = os.path.join(scratch("cobs-"), "cobs")
    subprocess.run(["gcc", "-O2", "-o", exe, os.path.join(TOP, source)], check=True)
    return exe


def codec(exe, mode, frames):
    """RETURN: list of bytes, one per frame, run through 'cobs <mode>'."""
    text = "".join(f.hex() + "\n" for f in frames)
    out = subprocess.run([exe, mode], input=text, capture_output=True, text=True, check=True).stdout
    return [bytes.fromhex(l) for l in out.splitlines()]


def show_codes(enc):
    """RETURN: the encoding as hex with each code byte in brackets."""
    parts, i = [], 0
    while i < len(enc):
        code = enc[i]
        parts.append("[%02X]" % code)
        parts.extend("%02X" % b for b in enc[i + 1:i + code])
        i += code
    return " ".join(parts)


def sweep(exe, frames):
    enc = codec(exe, "enc", frames)
    dec = codec(exe, "dec", enc)
    err   = sum(1 for f, d in zip(frames, dec) if f != d)
    zeros = sum(1 for e in enc if 0 in e)
    over  = sum(1 for f, e in zip(frames, enc) if len(e) > len(f) + 1 + len(f) // 254)
    return err, zeros, over


def main(choice):
    exe = build("cobs.c" if choice == "current" else "cobs_v1.c")
    print("codec: %s" % ("cobs.c" if choice == "current" else "cobs_v1.c"))
    print("worked examples          encoded, [code bytes] in brackets")
    frames = [bytes.fromhex(h) for h in EXAMPLES]
    for f, e in zip(frames, codec(exe, "enc", frames)):
        print("  %-22s %s" % (" ".join("%02X" % b for b in f) or "(empty)", show_codes(e)))

    seed = time.time_ns()
    rng = random.Random(seed)
    short = [bytes(rng.randrange(256) for _ in range(rng.randint(0, 64))) for _ in range(3000)]
    long_ = [bytes(0 if rng.random() < 0.002 else rng.randint(1, 255)
                   for _ in range(rng.randint(0, 1000))) for _ in range(300)]
    e_s, z_s, o_s = sweep(exe, short)
    e_l, z_l, o_l = sweep(exe, long_)
    print("## seed %d" % seed)
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("random frames               count   round-trip errors")
    print("  short, 0..64 any bytes     %4d   ((err_short: %d))   %s" % (len(short), e_s, law(e_s)))
    print("  long, 0..1000 few zeros    %4d   ((err_long: %d))   %s" % (len(long_), e_l, law(e_l)))
    print("encoded frames holding 0x00         ((zeros: %d))   %s" % (z_s + z_l, law(z_s + z_l)))
    print("frames over 1 + n/254 overhead      ((over: %d))   %s" % (o_s + o_l, law(o_s + o_l)))
    print("edge frames")
    edge = list(EDGE_DB.values())
    enc = codec(exe, "enc", edge)
    dec = codec(exe, "dec", enc)
    bad = 0
    for (name, f), e, d in zip(EDGE_DB.items(), enc, dec):
        if d == f:
            print("  %-20s %4d -> %4d bytes -> %4d   ok" % (name, len(f), len(e), len(d)))
        else:
            bad += 1
            k = next((i for i, (a, b) in enumerate(zip(f, d)) if a != b), min(len(f), len(d)))
            print("  %-20s %4d -> %4d bytes -> %4d   DIFFERS at byte %d: %s"
                  % (name, len(f), len(e), len(d), k, d[k:k + 3].hex(" ").upper()))
    print("edge frames wrong                   ((err_edge: %d))   %s" % (bad, law(bad)))


if len(sys.argv) < 2 or sys.argv[1] not in ("current", "v1"):
    print("choices: current, v1")
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
