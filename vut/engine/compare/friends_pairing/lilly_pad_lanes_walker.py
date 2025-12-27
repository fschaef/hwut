"""
PURPOSE:

    The Lilly Pad Lane problem is a sequential decision process across N lanes.
    Selecting a pad at index 'i' creates a "ripple effect," sinking specific 
    pads in any lane 'j > i'.

GOAL: Find a way over lanes of lilly-pads. We can only move from one lane
      to the next. A lilly pad may trigger the SINKING of a lilly pad ahead.

      => Find a path over all lanes, i.e. select from each lane a pad 
         that is not sunk by another pad on the path.

             [ START ]
    Lane 0:  [ 0 ] [ 1 ] [ 2 ] [ 3 ] 
    Lane 1:  [ 4 ] [ 5 ] 
    Lane 2:  [ 6 ] [ 7 ] [ 8 ] 
    Lane 3:  [ 9 ] [ 10 ] [ 11 ] [ 12 ] [ 13 ]
             [  END  ]

    For example a path [ 1 ], [ 5 ], [ 6 ], [ 12 ] would be such a path to
    cross the lilly pad lanes, if no pad on this path causes another one
    to sink.

SOLUTION:

    1. CONSTRAINT PROPAGATION

    Before the walk begins, we perform a Fixed-Point Iteration. We analyze
    every pad to see if its "sink profile" would eventually make a future lane
    empty.
        
        - Muritori Identification: A pad is a 'Muritori' if its selection 
          leaves zero available pads in any future lane. These are 
          physically removed from the search space.

        - Transitive Learning: If all surviving options in a future lane 
          share a common blocker, that blocker is "inherited" by the 
          current pad. This refines our knowledge of the "ripple effect."

    2. REFINED SOLVING (DECISION VECTOR SEARCH)

    Once the board is pruned, we move through the lanes. 
        
        - Backtracking: Propagation handles individual failures. However, 
          it is possible that Pad A (Lane 0) and Pad B (Lane 1) are fine 
          separately, but together they sink all options in Lane 5. 

        - Recovery: When a "joint sink" occurs, the Decision Vector 
          retracts to the last viable lane and tries the next candidate.

RELATED CONCEPTS:

    'Arc Consistency': Ensuring every pad has at least one valid future.

    'Greedy Pathfinding': After propagation, many problems become linear (O(N)), 
                          requiring zero backtracking."

AUTHOR: Frank-Rene Schaefer
______________________________________________________________________________________
"""

from typeguard import typechecked
from functools import lru_cache

def solve(pad_db: dict[int, set[int]], pad_ids_by_lane_db: list[list[int]]):
    """
    RETURNS: pad-ids of path through all lilly pad lanes.

    Solves the Lilly Pad Lane problem using Constraint Propagation + Backtracking.
    
    Phase 1: Propagation 
             Refines the search space by identifying dead-ends (muritori) and 
             learning implied blockers (transitive closure) before searching.
             
    Phase 2: Backtracking -- brute force
             Standard DFS, but using the propagated constraints from Phase 1.
    """
    # (1) Prepare
    # Build Dense Data Structures
    lane_mask_db,   \
    pad_blocker_db, \
    full_mask       = build_dense_data_structures(pad_db, pad_ids_by_lane_db)
    
    # (2) Constraint Propagation
    #    This updates 'pad_blocker_db' with implied constraints and 
    #    identifies 'muritori' (dead pads).
    muritori, refined_blocker_db = propagate_blockers(pad_blocker_db, lane_mask_db)
    
    #    Exit early on detection of 'unsolvable' (Global Contradiction)
    if muritori is None: return None

    #    Remove 'muritori' from the database of pad options
    refined_lanes,  \
    full_mask_clean = remove_muritori(pad_ids_by_lane_db, full_mask, muritori) 

    #    Exit early on detection of 'unsolvable'
    if not refined_lanes: return None

    # (3) Search
    # Delegate to the refined solver core
    return solve_refined(refined_lanes, lane_mask_db, refined_blocker_db, full_mask_clean)
    
@typechecked
def solve_refined(refined_lanes:      list[list[int]], 
                  lane_mask_db:       list[int], 
                  refined_blocker_db: list[int], 
                  full_mask:          int):
    """RETURNS: pad-ids of path through all lilly pad lanes.

    Core backtracking solver. Executes the search using a 'Decision Vector' 
    (Partial Assignment) across lanes pruned by constraint propagation.
    """
    lane_n = len(refined_lanes)
    if lane_n == 0: return []

    # DECISION VECTOR: dynamic cursor = current Partial Assignment.
    #
    # maps: lane index (sidx) --> [current_mask, next index of pad in lane 'sidx']
    decision_vector = [[full_mask, 0]]

    while decision_vector:
        # Peek at the current tip of the vector
        current_mask, c_idx = decision_vector[-1]
        sidx = len(decision_vector) - 1

        pad_ids = refined_lanes[sidx]

        # 1. Find a floating, not yet considered, pad on this lane 
        while c_idx < len(pad_ids):
            pad_id = pad_ids[c_idx]
            if current_mask & (1 << pad_id): break # Found a FLOATING pad
            c_idx += 1

        # NOTE: 'c_idx' = index of a floating pad + 1
        #        'c_idx' will enter the decision vector as 'state[1]' 
        #        => state[1] - 1 == 'c_idx' - 1 always points to a floating pad
        
        # 2. BACKTRACK, if no unsunk pad exists.
        if c_idx >= len(pad_ids):
            decision_vector.pop()
            continue

        # 3. MAKE DECISION (Try Step)
        pad_id = pad_ids[c_idx]
        
        #    Update the cursor in the current frame to point to the NEXT option
        #    (If we retreat to this frame later, we resume from c_idx + 1)
        decision_vector[-1][1] = c_idx + 1 
        
        #    Sink forward pads 
        next_mask = current_mask & ~refined_blocker_db[pad_id]
        
        #    Forward-Checking (Lightweight)
        #    NOTE: Found muritori INDIVIDUALLY kill a future lane.
        #          Propagation cannot see that some pad A and B (Lane 5) might
        #          JOINTLY sink all pads in Lane 10. 
        feasible = all(next_mask & lane_mask_db[i] for i in range(sidx + 1, lane_n))
        if not feasible: continue

        # 4. CHECK SUCCESS
        if sidx + 1 == lane_n:
            # Reconstruct the solution path from the decision vector indices.
            # See discussion about 'c_idx' above => 'state[1] - 1' points to admissible pad -- SAFE!
            return [ refined_lanes[i][state[1] - 1] for i, state in enumerate(decision_vector) ]
            
        # 5. ADVANCE CURSOR (Push next state)
        decision_vector.append([next_mask, 0])

    return None

def build_dense_data_structures(pad_db, pad_ids_by_lane_db):
    """
    Converts sparse dict/list inputs into dense list/bitmask structures 
    for O(1) access and fast bitwise logic.
    """
    all_pads = [p for lane in pad_ids_by_lane_db for p in lane]
    if not all_pads: return [], []
    max_pad_id = max(all_pads)

    lane_mask_db = []
    for lane in pad_ids_by_lane_db:
        m = 0
        for p in lane: m |= (1 << p)
        lane_mask_db.append(m)
        
    pad_blocker_db = [0] * (max_pad_id + 1)
    for pid, blocked_set in pad_db.items():
        m = 0
        for b in blocked_set: m |= (1 << b)
        pad_blocker_db[pid] = m

    full_mask = 0
    for mask in lane_mask_db: 
        full_mask |= mask 

    return lane_mask_db, pad_blocker_db, full_mask

def remove_muritori(pad_ids_by_lane_db, full_mask, muritori):
    """
    Filters the lane definitions to exclude pads identified as dead-ends.
    Returns None if any lane becomes empty.
    """
    result = []
    for lane in pad_ids_by_lane_db:
        # Keep only pads that are NOT in muritori
        alive = [p for p in lane if p not in muritori]
        if not alive: return None # Should be caught by propagate, but safety first
        result.append(alive)

    # The 'mask of all pad_id-s' cannot contain muritori (deadly pads)
    for pad_id in muritori: full_mask &= ~(1 << pad_id)

    return result, full_mask

@typechecked
def propagate_blockers(pad_blocker_db: list[int], lane_mask_db: list[int]):
    """
    RETURNS: [0] muritori -- pads to be removed (they sink a complete lane)
                             => touching such a pad is a dead-end.
             [1] pad_blocker_db -- remaining, aggregated blocker database
                                   pad-id --> block mask
    
             None, None => contradiction is found, i.e. due to given 
                           constraints, a lane becomes ineveitably empty
                           => problem is globally UNSOLVABLE.

    Performs constraint propagation to refine the blockage masks for each pad
    via fixed-point iteration.

    This function implements a look-ahead mechanism similar to **Arc
    Consistency (AC-3)** algorithms used in Constraint Satisfaction Problems.
    It iteratively determines the transitive closure of "unavoidable
    blockages".

    The algorithm evaluates the *logical implication* of selecting a specific
    pad:
    
        1. Forward Checking: If selecting `pad_A` leaves only a subset of pads 
           (survivors) available in a future lane, `pad_A` effectively forces 
           the user to pick one of those survivors.

        2. Intersection of Consequences: If *all* survivors in that future lane 
           share a common blocker (e.g., they all block `pad_Z`), then `pad_A` 
           itself implicitly blocks `pad_Z`.

        3. Domain Pruning (Muritori): If selecting `pad_A` leaves *zero* 
           survivors in a future lane, `pad_A` is a dead-end (inconsistent state) 
           and is pruned from the solution space ("Muritori").

    The process repeats until a *Fixed Point* is reached (no further updates
    occur), ensuring the system is locally consistent.

    ARGUMENTS:

    pad_blocker_db: 
        A dense list where the index corresponds to the `pad_id`.
        Value is a bitmask representing the set of pads blocked by `pad_id`.
        Assumes `pad_id`s are sequential integers [0..N-1] for O(1) access.
        
    lane_mask_db: 
        A list of bitmasks, where each entry represents the set of all pads 
        present in a specific lane.

    """
    # Assume 'pad_blocker_db' is a dense list and the pad_ids = 0 ... N-1.
    # => very quick access
    lane_pads_list = [bitmask_to_pad_ids(m) for m in lane_mask_db]
    L              = len(lane_mask_db)
    muritori       = set() # set of pad_id-s to be taken out
    #                        # when they are touched, a whole lane sinks
    
    # [OPTIMIZATION] Reverse Iteration + Worklist Logic
    # 'limit_idx' tracks the highest lane index that changed.
    # We only need to process lanes UPSTREAM of this limit (Indices < limit_idx).
    limit_idx = L 

    while limit_idx > 0:
        current_pass_max_change = 0 # 0 means no changes occurred effectively
        
        # Merge Index and Data access:
        # Iterate backwards from limit_idx-1 down to 0.
        # zip() pairs the countdown index with the reversed slice of pad lists.
        loop_iterator = zip(range(limit_idx - 1, -1, -1), 
                            lane_pads_list[:limit_idx][::-1])

        for sidx, current_lane_pads in loop_iterator:
            
            # UNSOLVABLE CHECK: if a lane consists solely of muritories (or was empty),
            # it cannot be passed => there is no solution anyway => early abort
            if lane_mask_db[sidx] == 0: return None, None
            
            for pad_id in current_lane_pads:
                # instead of 'if pad_id in muritori', use fact that lane mask is updated)
                # => 'lane_mask_db' is single source of truth.
                pad_bit = (1 << pad_id)
                if not (lane_mask_db[sidx] & pad_bit): continue

                # if pad does not block anything -> pad_blocker_mask = 0....
                pad_blocker_mask      = pad_blocker_db[pad_id]
                pad_blocker_mask_orig = pad_blocker_mask # immutable => isolated copy

                # Iterate ONLY future lanes
                for cmp_sidx in range(sidx + 1, L):
                    cmp_lane_mask = lane_mask_db[cmp_sidx]
                    
                    # current pad: 
                    #    pad_id           -> currently considered pad (from current lane 'sidx')
                    #    pad_blocker_mask -> set of pads blocked by 'pad_id'
                    # compared pad lane:
                    #    cmp_lane_mask    -> set of pads of compared lane (from some lane > 'sidx')

                    # What pads in this lane are NOT blocked by current pad?
                    #
                    # Lane:    [X] [ ] [ ] [X] [ ]
                    #               |   |       |
                    #               '---+-------+------> in order to pass this lane, one of those
                    #                                    needs to be touched.
                    #                                    => consider blockers they have in common.
                    #
                    survivors_mask = cmp_lane_mask & ~pad_blocker_mask
                    
                    if survivors_mask == 0: 
                        # touching this pad sinks a WHOLE lane => DO NOT TOUCH AT ALL!
                        muritori.add(pad_id) 
                        # a muritori can never be considered a 'survivor'
                        lane_mask_db[sidx] &= ~(1 << pad_id)
                        
                        # Immediate check: Did we just kill the last pad in this lane?
                        if lane_mask_db[sidx] == 0: return None, None

                        # Mark this change so upstream lanes re-evaluate
                        if sidx > current_pass_max_change:
                            current_pass_max_change = sidx
                        break 
                    
                    # Get the pad_ids of the survivors of that same lane
                    survivor_pad_ids = bitmask_to_pad_ids(survivors_mask)
                    # len(survivor_ids) != 0, due to check on 'survivors_mask' before
                    
                    # Consider the intersection of the pads which are blocked by all survivors
                    # => these blockings cannot be avoided.
                    
                    # [OPTIMIZATION] Manual intersection with Early Exit
                    common_blockers = pad_blocker_db[survivor_pad_ids[0]]
                    for surv_pid in survivor_pad_ids[1:]:
                        common_blockers &= pad_blocker_db[surv_pid]
                        # If intersection becomes empty, we can stop checking
                        if common_blockers == 0: break 

                    if not (common_blockers & ~pad_blocker_mask): continue
                    
                    # If we found new implied blockers, absorb them
                    pad_blocker_mask |= common_blockers
                
                else: 
                    # Here: 'pad_id' did not sink a whole lane => can actually be considered
                    if pad_blocker_mask != pad_blocker_mask_orig:
                        pad_blocker_db[pad_id] = pad_blocker_mask
                        
                        # Track change for Worklist logic
                        if sidx > current_pass_max_change:
                            current_pass_max_change = sidx

        # Setup for next pass:
        # If nothing changed, current_pass_max_change is 0, loop terminates.
        # Otherwise, scan only lanes upstream of the change.
        limit_idx = current_pass_max_change

    return muritori, pad_blocker_db

def pad_ids_to_bitmask(int_list):
    result = 0
    for v in int_list: result |= (1 << v)
    return result
    
@lru_cache(maxsize=4096)
def bitmask_to_pad_ids(m):
    res = []
    while m:
        msb = m.bit_length() - 1
        res.append(msb)
        m &= ~(1 << msb)
    return res

def intersect_bitmasks(bitmask_iterable):
    it = iter(bitmask_iterable)
    try:                  result = next(it)
    except StopIteration: return 0 
    for m in it: result &= m
    return result
    
