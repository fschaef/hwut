#! /usr/bin/env python
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Unit Test for 'propagate_blockers' constraint propagation.

CHOICES: basic, dead_end, chain, oscillation, missing_keys, unsolvable;

DESCRIPTION:

This test verifies the constraint propagation logic used to optimize the
search space in the 'friends_pairing' algorithm.

The test prints the result of the propagation. The correctness is verified
by the HWUT framework comparing the output against a golden reference file.
Context hints are provided via '##' comments.
______________________________________________________________________________
"""
import sys
import os

# Adopt path before imports --> disable code check error E402
this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../../")
sys.path.insert(0, this_directory)

from vut.engine.compare.region.potpourri.solver.csp_arc_consistency import (propagate_blockers,  #noqa E402
                                                                     bitmask_to_pad_ids, 
                                                                     pad_ids_to_bitmask)

if "--hwut-info" in sys.argv:
    print("Propagate Blockers: Constraint Propagation;")
    print("CHOICES: basic, dead_end, chain, oscillation, missing_keys, unsolvable;")
    sys.exit()

def print_db(label, db_list):
    print("%s" % label)
    # Check if list is empty or effectively empty (all zeros)
    if not db_list or all(mask == 0 for mask in db_list):
        print("    <empty>")
        return
    
    for pid, mask in enumerate(db_list):
        if mask == 0: continue
        blocked_ids = bitmask_to_pad_ids(mask)
        print("    [%02d] blocks: %s" % (pid, blocked_ids))

def test(lane_definition, initial_blockers):
    """
    Executes the algorithm and prints the result state.
    Expectations are checked by the framework via diff.
    """
    # 1. Determine Max Pad ID to size the dense list
    all_pads = [p for lane in lane_definition for p in lane]
    max_id   = max(all_pads) if all_pads else 0
    if initial_blockers:
        max_id = max(max_id, max(initial_blockers.keys()))

    # 2. Setup Data Structures
    lane_mask_db = [pad_ids_to_bitmask(lane) for lane in lane_definition]
    
    # Create Dense List (Initialize with 0)
    pad_blocker_db = [0] * (max_id + 1)
    for pid, blocked_list in initial_blockers.items():
        pad_blocker_db[pid] = pad_ids_to_bitmask(blocked_list)

    print("--------------------------------")
    print("Lanes:")
    for i, lane in enumerate(lane_definition):
        print("  Lane %d: %s" % (i, lane))
    
    print_db("\nInitial Blockers:", pad_blocker_db)

    # 3. Run Algorithm
    muritori, final_db = propagate_blockers(pad_blocker_db, lane_mask_db)

    # 4. Print Results
    if muritori is None and final_db is None:
        print("\nResult: UNSOLVABLE (Lane became empty)")
        return

    m_sorted = sorted(list(muritori))
    print("\nMuritori (Dead Pads):")
    print("  %s" % (m_sorted if m_sorted else "<None>"))

    print("\nBlockers (Final):")
    # final_db is now a list, print directly using helper
    print_db("  (Active Constraints)", final_db)
    print()


# ---------------------------------------------------------------------------
# SCENARIOS
# ---------------------------------------------------------------------------
# Rewritten for dense IDs (0, 1, 2...) instead of sparse (1, 10, 20...)

if "basic" in sys.argv:
    print("## Scenario 1: No conflicts.")
    test(
        lane_definition = [ [0], [1, 2], [3] ],
        initial_blockers = { 1: [3], 2: [] }
    )
    
    print("## Scenario 2: Implicit Blocking (Forced Move).")
    print("## Pad 0 MUST go to Pad 1. Pad 1 blocks 2. Thus 0 blocks 2.")
    test(
        lane_definition = [ [0], [1], [2] ],
        initial_blockers = { 1: [2] }
    )

if "dead_end" in sys.argv:
    print("## Scenario 1: Immediate Death.")
    print("## Pad 0 blocks all options in Lane 1 (Pads 1, 2).")
    test(
        lane_definition = [ [0], [1, 2] ],
        initial_blockers = { 0: [1, 2] }
    )
    
    print("## Scenario 2: Distant Death.")
    print("## Pad 0 skips Lane 1 (valid), but kills Lane 2.")
    test(
        lane_definition = [ [0], [1], [2] ],
        initial_blockers = { 0: [2] }
    )

if "chain" in sys.argv:
    print("## Scenario: Chain Propagation.")
    print("## 0 forces 2; 2 forces 4; 4 blocks 5.")
    print("## Result: 0 inherits blockers and eventually kills the only path in Lane 3.")
    # Old: [1], [10, 11], [20, 21], [30] -> New: [0], [1, 2], [3, 4], [5]
    test(
        lane_definition = [ [0], [1, 2], [3, 4], [5] ],
        initial_blockers = {
            0:  [2], # Forces move to 1? No, 0->2 implies 0 blocks 2.
                     # If 0 blocks 2, and Lane 1 is [1, 2], then 0 MUST go to 1.
            1:  [4], # 1 blocks 4. Lane 2 is [3, 4]. So 1 forces 3.
            3:  [5], # 3 blocks 5. Lane 3 is [5]. So 3 is a dead end.
            2: [], 4: [] 
        }
    )

if "oscillation" in sys.argv:
    print("## Scenario 1: Intersection Convergence.")
    print("## Pad 0 has survivors [1, 2]. Both block 3. Pad 0 learns to block 3.")
    test(
        lane_definition = [ [0], [1, 2], [3, 4] ],
        initial_blockers = { 1: [3], 2: [3] }
    )
    
    print("## Scenario 2: Partial Overlap.")
    print("## Blockers differ ({3} vs {4}). Intersection empty. No propagation.")
    test(
        lane_definition = [ [0], [1, 2], [3, 4] ],
        initial_blockers = { 1: [3], 2: [4] }
    )

if "missing_keys" in sys.argv:
    print("## Scenario 1: Missing key in DB (blocks nothing).")
    print("## Pad 1 blocks 3. Pad 2 missing (blocks nothing). Intersection empty.")
    test(
        lane_definition = [ [0], [1, 2], [3] ],
        initial_blockers = { 1: [3] } # 2 is missing (implicitly 0)
    )
    
    print("## Scenario 2: Missing key causes death.")
    print("## Pad 0 blocks 2. Pad 1 (missing) allows survival in Lane 1.")
    print("## But Pad 0 is checked against Lane 2 and kills [2].")
    test(
        lane_definition = [ [0], [1], [2] ],
        initial_blockers = { 0: [2] }
    )

if "unsolvable" in sys.argv:
    print("## Scenario 1: Immediate Empty Lane.")
    print("## Pad 0 kills the only option in Lane 1. Lane 0 becomes empty.")
    test(
        lane_definition = [ [0], [1], [2] ],
        initial_blockers = { 0: [1] }
    )

    print("## Scenario 2: The 'Pincer' (Simultaneous Death).")
    print("## Lane 1 has [1, 2]. Both independently block [3] (Lane 2).")
    print("## Both die. Lane 1 becomes empty. Abort.")
    test(
        lane_definition = [ [0], [1, 2], [3] ],
        initial_blockers = { 
            1: [3], 
            2: [3] 
        }
    )

    print("## Scenario 3: Complex Feedback Loop.")
    print("## Lane 0:[0] -> Lane 1:[1, 2] -> Lane 2:[3]")
    print("## 1. Pad 0 blocks 2 (forces 1).")
    print("## 2. Pad 1 blocks 3 (it is a dead end).")
    print("## Execution:")
    print("##   - Pad 0 propagates: learns that via 1, it effectively blocks 3.")
    print("##   - Pad 1 dies (leads to dead end at Lane 2). Lane 1 loses 1.")
    print("##   - Loop restarts.")
    print("##   - Pad 0 checks Lane 1: Only [2] remains.")
    print("##   - Pad 0 blocks 2 (explicitly). Survivors: {}.")
    print("##   - Pad 0 dies. Lane 0 becomes empty. Abort.")
    test(
        lane_definition = [ [0], [1, 2], [3] ],
        initial_blockers = { 
            0:  [2], # Forces 1
            1:  [3]  # 1 is a dead end
        }
    )
