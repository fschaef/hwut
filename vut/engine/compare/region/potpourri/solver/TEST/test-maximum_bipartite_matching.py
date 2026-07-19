#! /usr/bin/env python3
import sys
import os
import time

# Standard VUT path injection
this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../../../")
sys.path.insert(0, this_directory)

# Import the algorithm under test
from   vut.engine.compare.region.potpourri.solver.maximum_bipartite_matching import do   #noqa E402
import scenario_generator                                             as     gen  #noqa E402

if "--hwut-info" in sys.argv:
    print("Bipartite Matching: Augmenting Path Algorithm;")
    print("CHOICES: basic, stress, chain;")
    sys.exit()

def run_test(name, adj):
    print(f"--- Scenario: {name} ---")
    start = time.time()
    result = do(adj)
    end = time.time()
    
    # We print the size and a subset of the mapping for large tests to keep logs readable
    print(f"Matching Size: {len(result)}")
    if len(result) < 15:
        for s in sorted(result.keys()):
            print(f"  [{s}] -> {result[s]}")
    else:
        # Just print boundaries for large sets
        keys = sorted(result.keys())
        print(f"  First: [{keys[0]}] -> {result[keys[0]]}")
        print(f"  Last:  [{keys[-1]}] -> {result[keys[-1]]}")
    
    # Asserting deterministic results (sorting in 'do' ensures this)
    # HWUT will catch any performance regressions via time if we had a monitor,
    # but for now, we focus on correctness.
    print("Status: Done")
    print("## time: ", start - end)

if "basic" in sys.argv:
    # Simple cases
    run_test("Simple 1-to-1", {0: {10}, 1: {11}})
    run_test("Conflict 2-to-1", {0: {10}, 1: {10}})
    run_test("Cross Match", {0: {10, 11}, 1: {10}})

if "stress" in sys.argv:
    # High volume tests
    N = 2000
    run_test(f"Large Pipe ({N})", gen.pipe_graph(100*N))
    run_test(f"Complete Bipartite ({N})", gen.complete_bipartite(N))
    run_test(f"Sudoku Pivot ({N})", gen.sudoku_pivot(N))

if "chain" in sys.argv:
    # Testing the 'Edge Flipping' logic
    # This is where the iterative DFS is put to work
    N = 50000
    run_test(f"Long Augmenting Path ({N})", gen.long_augmenting_path(N))
    run_test(f"Bottleneck ({N})", gen.the_bottleneck(N))
