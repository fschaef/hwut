# You likely need to install this: pip install pyrsistent
from pyrsistent import pmap, pset
from functools import lru_cache
from vut.engine.compare.engine.potpourri.result import Result

def do(potential_pair_db, global_analogy_db, global_pair_db, required_pair_n) -> Result:
    if not potential_pair_db:
        return Result({}, global_pair_db, global_analogy_db, required_pair_n, True)

    # 1. FIXED ORDERING (MRV)
    subj_order = sorted(potential_pair_db.keys(), 
                        key=lambda s: len(potential_pair_db[s]))
    L = len(subj_order)
    
    # 2. THE EXPLICIT STACK
    # CHANGE: Use pmap() and pset() for O(1) memory updates
    stack = [(0, pmap(), global_analogy_db, pset())]

    best_pairs = pmap()
    best_adb = global_analogy_db

    while stack:
        idx, pairs, adb, used_noms = stack.pop()

        if len(pairs) > len(best_pairs):
            best_pairs, best_adb = pairs, adb

        if idx == L:
            # Convert back to standard dict for the result
            return Result({}, global_pair_db | dict(best_pairs), best_adb, 
                          required_pair_n, False)

        s_i = subj_order[idx]
        candidates = potential_pair_db[s_i]
        
        # 4. BRANCHING
        for n_i, local_adb in reversed(candidates):
            
            if n_i in used_noms:
                continue

            verdict, new_adb = get_analogy_db(adb, local_adb)
            if not verdict:
                continue

            # CRITICAL CHANGE:
            # pairs.set(k, v) returns a NEW pmap, but shares memory with the old one.
            # NO COPYING HAPPENS HERE. Memory usage is near zero for this step.
            stack.append((idx + 1, 
                          pairs.set(s_i, n_i), 
                          new_adb, 
                          used_noms.add(n_i)))

    return Result({}, global_pair_db | dict(best_pairs), best_adb, 
                  required_pair_n, True)

@lru_cache(maxsize=4096)
def get_analogy_db(aggregated_analogy_db, required_analogy_db):
    if not required_analogy_db:
        # Clone check handled by class or caller
        return True, (aggregated_analogy_db if aggregated_analogy_db else None)
    elif not aggregated_analogy_db:
        return True, required_analogy_db
    elif aggregated_analogy_db.is_all_consistent(required_analogy_db):
        return True, aggregated_analogy_db.merge(required_analogy_db)
    else:
        return False, None
