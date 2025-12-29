#! /usr/bin/env python3
import sys
import os
import time

# Standard VUT path injection
this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../../")
sys.path.insert(0, this_directory)
from   vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb
import scenario_generator_adb as gen

# Import your algorithm module
from vut.engine.compare.friends_pairing.solver.csp_backtracking_mrv import do

if "--hwut-info" in sys.argv:
    print("CSP Backtracking MRV: Friends Pairing Stress Test;")
    print("CHOICES: soduko, backtracking, massive-pipe, lane-trap;")
    sys.exit()

def test(name, potential_db):
    print(f"--- CSP Scenario: {name} ---")
    # Initial state: Empty analogy DB, empty pair DB
    global_adb = FrozenAnalogyDb()
    global_pdb = {}
    required_n = len(potential_db)

    start = time.time()
    res = do(potential_db, global_adb, global_pdb, required_n)
    end = time.time()
    
    print(f"  Success:  {not res.aborted_f}")
    print(f"  Matching: {len(res.pair_db)}/{required_n}")
    print(f"##Time:     {end - start} [sec]")
    
    # In HWUT, we print results for the golden master
    if not res.aborted_f:
        c = 0
        for s_i in sorted(res.pair_db.keys()):
            print(f"    [{s_i}] -> {res.pair_db[s_i]}")
            c += 1
            if c == 10: print("..."); break
            
    else:
        print("    FAILED to find full consistent matching.")

if "soduko" in sys.argv:
    test("Sudoku MRV Trap (5000 nodes)", gen.mrv_trap(5000))

elif "backtracking" in sys.argv:
    test("Backtracking Lock (15 depth)", gen.combinatorial_explosion(15))

elif "massive-pipe" in sys.argv:
    test("Massive Pipe (5k)", gen.analogy_pipe(5000))

elif "lane-trap" in sys.argv:
    n = 10000
    test(f"Lane Trap {n}:", gen.lane_trap(n))
