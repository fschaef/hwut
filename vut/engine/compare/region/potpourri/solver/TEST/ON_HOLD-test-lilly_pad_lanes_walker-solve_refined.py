#! /usr/bin/env python
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Unit Test for 'solve_refined' backtracking search.

DESCRIPTION:
Verifies that the solver correctly navigates accumulated conflicts.
The output displays the 'Blocker Map' so the logic of the walk is traceable.
______________________________________________________________________________
"""
import sys
import os

# Adopt path for imports (Adjust to your project structure)
this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../../")
sys.path.insert(0, this_directory)

from vut.engine.compare.engine.potpourri.solver.csp_arc_consistency import ( #noqa E402
                                                                     solve_refined, 
                                                                     pad_ids_to_bitmask)

if "--hwut-info" in sys.argv:
    print("Solver Refined: Traceable Backtracking Search;")
    print("CHOICES: basic, pincer, chain, dead_end;")
    sys.exit(0)

def print_blocker_map(refined_blocker_db, refined_lanes):
    """Visualizes which pad sinks which future pads."""
    print("\nBLOCKER MAP (Constraints):")
    for pid, mask in enumerate(refined_blocker_db):
        if mask == 0: continue
        
        # Identify which future pads are hit by this mask
        targets = []
        for l_idx, lane in enumerate(refined_lanes):
            hit_in_lane = [p for p in lane if (mask & (1 << p))]
            if hit_in_lane:
                targets.append(f"Lane {l_idx}:{hit_in_lane}")
        
        if targets:
            print(f"  Pad [{pid}] sinks -> " + " | ".join(targets))

def run_test(label, refined_lanes, initial_blockers):
    print("==================================================================")
    print(f"## TEST CASE: {label}")
    
    # 1. Prepare Inputs
    lane_n = len(refined_lanes)
    lane_mask_db = [pad_ids_to_bitmask(lane) for lane in refined_lanes]
    
    all_pads = [p for l in refined_lanes for p in l]
    max_id = max(all_pads) if all_pads else 0
    
    refined_blocker_db = [0] * (max_id + 1)
    for pid, blocked in initial_blockers.items():
        refined_blocker_db[pid] = pad_ids_to_bitmask(blocked)
        
    full_mask = 0
    for m in lane_mask_db: full_mask |= m

    # 2. Display the board and the "hidden" mines
    print("BOARD LAYOUT:")
    for i, l in enumerate(refined_lanes):
        print(f"  Lane {i:2}: {l}")
    
    print_blocker_map(refined_blocker_db, refined_lanes)
    
    # 3. Solve
    path = solve_refined(refined_lanes, lane_mask_db, refined_blocker_db, full_mask)
    
    # 4. Report Result
    print("\nSEARCH RESULT:")
    if path is None:
        print("  => UNSOLVABLE: Solver exhausted all branches via backtracking.")
    else:
        print(f"  => SUCCESS: {path}")
    print("==================================================================\n")

# ---------------------------------------------------------------------------
# SCENARIOS
# ---------------------------------------------------------------------------
if "basic" in sys.argv:
    # Minimal case: Three lanes, one constraint that doesn't block the path.
    run_test(
        "Basic (Direct Path)",
        refined_lanes = [
            [10], 
            [20], 
            [30]
        ],
        initial_blockers = {
        }
    )
if "pincer" in sys.argv:
    # This scenario requires backtracking because 0 and 1 are fine individually,
    # but their combination leaves Lane 2 empty.
    run_test(
        "Pincer (Accumulated Death)",
        refined_lanes = [
            [0, 5],    # Lane 0: 5 is the 'safe' backup
            [1],       # Lane 1: Forced path
            [10, 11]   # Lane 2: Target lane
        ],
        initial_blockers = {
            0: [11],   # 0 sinks 11
            1: [10]    # 1 sinks 10
        }
    )

if "chain" in sys.argv:
    # Tests long-range dependencies across multiple lanes
    run_test(
        "Long Distance Chain",
        refined_lanes = [
            [0], 
            [1, 2], 
            [10, 20], 
            [100]
        ],
        initial_blockers = {
            0: [10],   # Step 0 forces Lane 2 to use Pad 20
            2: [100]   # But Pad 2 in Lane 1 sinks Pad 100 in Lane 3
        }
    )

if "dead_end" in sys.argv:
    run_test(
        "Total Dead End",
        refined_lanes = [
            [0], 
            [10]
        ],
        initial_blockers = {
            0: [10]
        }
    )
