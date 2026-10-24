"""ds_py.py -- the reference: hwut's DeterministicStream itself, under
whichever Python runs this file. usage: pythonX.Y ds_py.py int|gauss SEED N
          pythonX.Y ds_py.py random SEED N    (the standard 'random')"""
import os, random, shutil, sys
sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

kind, seed, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
if kind == "random":
    r = random.Random(seed)
    print("\n".join(str(r.randint(0, 999)) for _ in range(n)))
else:
    s = DeterministicStream(seed)
    if kind == "int": print("\n".join(str(s.next_int(0, 999)) for _ in range(n)))
    else:             print("\n".join("%.17g" % s.gauss(0.0, 1.0) for _ in range(n)))
