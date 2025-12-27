from typeguard import typechecked

def solve(pad_db: dict[int, set[int]], pad_ids_by_lane_db: list[list[int]]):
    """Solves the Lilly Pad Lane problem iteratively using internal bitmasks.
    
    [0] pad_db:             Mapping of pad_id to its 'sunk' pads.
    [1] pad_ids_by_lane_db: Lanes containing their respective pad_ids.
    """
    num_lanes = len(pad_ids_by_lane_db)

    # Lane bitmasks: 
    #    lane index (sidx) --> bitmask representing the pads in the lane
    lane_mask_db = [ bitmasks(lane_pads) for lane_pads in pad_ids_by_lane_db ]
        
    # Blocking bitmasks
    #    pad_id --> bitmask representing the pads that are blocked by it
    pad_blocker_db = {
        pad_id: bitmask(blocked_pad_ids)
        for pad_id, blocked_pad_ids in pad_db.items()
    }

    # Total universe of pads
    full_mask = (1 << sum(len(l) for l in pad_ids_by_lane_db)) - 1

    # STACK: [sidx, current_mask, candidate_idx]
    stack = [[0, full_mask, 0]]
    path  = []

    while stack:
        sidx, current_mask, c_idx = stack[-1]

        # Filter pads in this lane that are still "above water"
        lane_candidates = [p for p in pad_ids_by_lane_db[sidx] if (current_mask & (1 << p))]

        if c_idx >= len(lane_candidates):
            stack.pop()
            if path: path.pop()
            continue

        # Try next pad
        pad_id = lane_candidates[c_idx]
        stack[-1][2] += 1 # Update c_idx on the stack
        
        # Apply sink
        next_mask = current_mask & ~pad_blocker_db[pad_id]
        
        # Forward-Checking: Did we sink any future lane?
        feasible = True
        for f_sidx in range(sidx + 1, num_lanes):
            if not (next_mask & lane_mask_db[f_sidx]):
                feasible = False
                break
        
        if not feasible:
            continue

        # Commit
        path.append(pad_id)
        if sidx + 1 == num_lanes:
            return path
            
        stack.append([sidx + 1, next_mask, 0])

    return None

@typechecked
def propagate_blockers(pad_blocker_db: list[int], lane_mask_db):
    """RETURNS: [0] set of pad_id-s to be taken out.
                    => when they are touched a whole lane sinks.
                [1] updated 'pad_blocker_db': 
                    pad_id --> bitmask representing block pads

    Propagates blockers by looking at the intersections of surviving options.
    """
    # Assume 'pad_blocker_db' is a dense list and the pad_ids = 0 ... N-1.
    # => very quick access
    lane_pads_list = [bitmask_to_pad_ids(m) for m in lane_mask_db]
    L              = len(lane_mask_db)
    muritori       = set() # set of pad_id-s to be taken out
    #                      # when they are touched, a whole lane sinks
    changed        = [True] * L
    while True in changed:
        first_sidx = changed.index(True)
        changed[first_sidx:] = [False] * (L - first_sidx)

        # Iterate lanes starting from the first changed one
        for sidx, current_lane_pads in enumerate(lane_pads_list[first_sidx:], start=first_sidx):
            for pad_id in current_lane_pads:
                if pad_id in muritori: continue

                # if pad does not block anything -> pad_blocker_mask = 0....
                pad_blocker_mask      = pad_blocker_db[pad_id]
                pad_blocker_mask_orig = pad_blocker_mask # immutable => isolated copy

                # Iterate ONLY future lanes
                for cmp_lane_mask in lane_mask_db[sidx+1:]:
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
                        # if a lane consists solely of muritories, it cannot be passed
                        # => there is no solution anyway => early abort
                        if lane_mask_db[sidx] == 0: return None, None
                        break
                    
                    # Get the pad_ids of the survivors of that same lane
                    survivor_pad_ids = bitmask_to_pad_ids(survivors_mask)
                    # len(survivor_ids) != 0, due to check on 'survivors_mask' before
                    
                    # Consider the intersection of the pads which are blocked by all survivors
                    # => these blockings cannot be avoided.
                    survivor_blocker_mask = intersect_bitmasks(pad_blocker_db[p] for p in survivor_pad_ids)

                    if not (survivor_blocker_mask & ~pad_blocker_mask): continue
                    
                    # If we found new implied blockers, absorb them
                    pad_blocker_mask |= survivor_blocker_mask

                else:
                    # Here: 'pad_id' did not sink a whole lane => can actually be considered
                    if pad_blocker_mask != pad_blocker_mask_orig:
                        pad_blocker_db[pad_id] = pad_blocker_mask
                        changed[sidx] = True
                        
    return muritori, pad_blocker_db

def pad_ids_to_bitmask(int_list):
    result = 0
    for v in int_list: result |= (1 << v)
    return result
    
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
    
