#! /usr/bin/env python3
# @hwut {
#     title    = "DeterministicStream: the same fuzz stream on every interpreter and language?"
#     choices {
#         integers { features = ["ints-everywhere", "random-not-portable"]
#                    tolerance { constraints = ["differing == 0"] } }
#         gauss    { features = ["gauss-libm", "gauss-printed"] }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the DeterministicStream draws for one seed as each producer (Python
         versions, C, JavaScript) makes them, against python 3.13's
REQUIREMENT  A stream that a GOOD file records -- the inputs of a fuzz run,
             a noise sequence -- is reproduced EXACTLY wherever the test
             runs: another Python version, or the firmware (C) and web
             front end (JavaScript) that replay the host's stream.

hwut's 'deterministic_random.DeterministicStream' promises "a platform-
independent random number generator": the Park-Miller MINSTD recurrence
state' = 48271 * state mod (2^31 - 1), integer arithmetic only. This test
holds it to that promise. The reference is the module itself, imported
under Python 3.11, 3.12 and 3.13 ('../ds_py.py'); the ports are
'../ds_port.c' (gcc, glibc's libm) and '../ds_port.js' (node, V8's own
math). The ports are ten lines each: THAT is what a platform-independent
generator buys -- the stream can be replayed outside Python.

THE GENERATOR INSTRUCTION is a seed and a count: 'seed 42, 100000 draws'.
That line is the whole description of the stream; whoever has it, has the
stream. Five producers per kind are compared over all 100000 values (a
checksum each), so a divergence anywhere in the stream shows.

integers  next_int(0, 999): identical on all five. The standard 'random'
          (Mersenne Twister) gives the same randint() on 3.11..3.13 here,
          but its documentation guarantees only random() across versions,
          its API moves (randrange(10.0): a value with a warning in 3.11, a
          TypeError from 3.12), and no ten-line port of it exists.
gauss     gauss(0, 1) uses log, cos and sqrt. Printed with all 17 digits,
          C/glibc equals Python (same libm), V8 differs in the last bit of
          about 6 % of the values. That is the accepted violation: the
          module's gauss is NOT bit-exact across math libraries. Printed at
          12 decimals or fewer, all 100000 agree -- so a GOOD that prints
          gauss values must round them (and a rounding border can still
          flip one, rarely).

HOW TO READ THE GOOD   One row per producer; the checksum column must be
the same top to bottom. In 'gauss', the count matrix says how many of the
100000 values differ from Python 3.13's when printed with the format of the
column; '0' everywhere is portable. Interpreter versions are printed so a
reader sees what was compared; this machine has python3.11..3.13, gcc and
node -- elsewhere the GOOD would differ in the 'absent' rows, by intent.
______________________________________________________________________________
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
SEED, N = 42, 100000
FORMATS = ["%.17g", "%.15g", "%.12f", "%.9f", "%.6f"]


def producers(build):
    exe = os.path.join(build, "ds_port")
    subprocess.check_call(["gcc", "-O2", "-o", exe, os.path.join(UNIT, "ds_port.c"), "-lm"])
    result = []
    for version in ("3.11", "3.12", "3.13"):
        python = shutil.which("python" + version)
        result.append(("python " + version, [python, os.path.join(UNIT, "ds_py.py")] if python else None))
    result.append(("C, gcc + glibc libm", [exe]))
    node = shutil.which("node")
    result.append(("JavaScript, node", [node, os.path.join(UNIT, "ds_port.js")] if node else None))
    return result


def draw(argv, kind):
    if argv is None:
        return None
    out = subprocess.run(argv + [kind, str(SEED), str(N)], capture_output=True, text=True, check=True)
    return out.stdout.split()


def checksum(values):
    return hashlib.sha1("\n".join(values).encode()).hexdigest()[:12]


def run_integers(build):
    print("stream: seed %d, %d draws of next_int(0, 999)" % (SEED, N))
    print()
    print("  %-22s %-44s %s" % ("producer", "first 10 draws", "sha1 of all"))
    sums = []
    for name, argv in producers(build):
        values = draw(argv, "int")
        if values is None:
            print("  %-22s absent" % name)
            continue
        sums.append((name, checksum(values)))
        print("  %-22s %-44s %s" % (name, " ".join(values[:10]), checksum(values)))
    reference = dict(sums).get("python 3.13")
    differing = sum(1 for _, c in sums if c != reference)
    print("producers whose stream differs from python 3.13's ((differing: %d)) of %d   law == 0   %s"
          % (differing, len(sums), "kept: one stream (sha1 %s)" % reference if not differing else "BROKEN"))
    print()
    print("the standard 'random': random.Random(%d).randint(0, 999)" % SEED)
    for version in ("3.11", "3.12", "3.13"):
        python = shutil.which("python" + version)
        values = draw([python, os.path.join(UNIT, "ds_py.py")], "random")
        probe = subprocess.run([python, "-W", "ignore", "-c",
                                "import random\n"
                                "try: print(random.Random(%d).randrange(10.0))\n"
                                "except Exception as e: print(type(e).__name__)" % SEED],
                               capture_output=True, text=True).stdout.strip()
        print("  %-22s %-44s %s   randrange(10.0) -> %s"
              % ("python " + version, " ".join(values[:10]), checksum(values), probe))
    print("  %-22s no port: CPython's seeding (init_by_array) and _randbelow live in CPython" % "C, JavaScript")


def run_gauss(build):
    print("stream: seed %d, %d draws of gauss(0, 1) -- log, cos, sqrt of the platform" % (SEED, N))
    print("cells:  how many of the %d values differ from python 3.13's, printed with" % N)
    print()
    table = [(name, draw(argv, "gauss")) for name, argv in producers(build)]
    reference = dict(table)["python 3.13"]
    ref_text = dict((fmt, [fmt % float(b) for b in reference]) for fmt in FORMATS)
    worst = dict((fmt, 0) for fmt in FORMATS)
    print("  %-24s" % "producer" + "".join("%9s" % f for f in FORMATS) + "   first difference (17 digits)")
    for name, values in table:
        if values is None:
            print("  %-22s absent" % name)
            continue
        counts, first = [], "-"
        for fmt in FORMATS:
            counts.append(sum(fmt % float(a) != b for a, b in zip(values, ref_text[fmt])))
            worst[fmt] = max(worst[fmt], counts[-1])
        for i, (a, b) in enumerate(zip(values, reference)):
            if float(a) != float(b):
                first = "#%d: %s vs %s" % (i, "%.17g" % float(a), "%.17g" % float(b))
                break
        label = name + (" (reference)" if name == "python 3.13" else "")
        print(("  %-24s" % label + "".join("%9d" % c for c in counts) + "   " + first).rstrip())
    print()
    portable = [fmt for fmt in FORMATS if worst[fmt] == 0]
    if worst["%.17g"]:
        print("!! gauss is not bit-exact across math libraries: up to %d of %d values differ in full precision"
              % (worst["%.17g"], N))
    print("portable when printed as: %s" % (", ".join(portable) if portable else "none"))


def main(choice):
    with tempfile.TemporaryDirectory() as build:
        CHOICE_DB[choice](build)


CHOICE_DB = {"integers": run_integers, "gauss": run_gauss}

if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
