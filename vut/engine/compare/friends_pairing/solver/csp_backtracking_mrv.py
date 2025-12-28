from functools import lru_cache
from vut.engine.compare.friends_pairing.result import Result
from vut.engine.compare.engine.analogy_db      import AnalogyDb

def do(potential_pair_db, global_analogy_db, global_pair_db, required_pair_n) -> tuple[dict,AnalogyDb]:
    if not potential_pair_db:
        return Result({}, global_pair_db, global_analogy_db, required_pair_n, True)

    # 1. FIXED ORDERING (The "Sudoku" strategy)
    # Sort subjects by "constriction" (fewest partners first).
    # This prevents the algorithm from wasting time on easy subjects 
    # before realizing a hard subject is impossible.
    subj_order = sorted(potential_pair_db.keys(), 
                        key=lambda s: len(potential_pair_db[s]))
    L = len(subj_order)
    
    # 2. THE EXPLICIT STACK
    # Each entry: (subject_index, current_pairs_dict, current_adb, used_nominals_set)
    # Start at index 0 (the first subject in our sorted list)
    stack = [(0, {}, global_analogy_db, frozenset())]

    best_pairs = {}
    best_adb = global_analogy_db

    while stack:
        idx, pairs, adb, used_noms = stack.pop()

        # Update best seen (Partial results are valid fallback)
        if len(pairs) > len(best_pairs):
            best_pairs, best_adb = pairs, adb

        # SUCCESS: Found a full matching
        if idx == L:
            return Result({}, global_pair_db | best_pairs, best_adb, 
                          required_pair_n, False)

        # 3. SELECT NEXT SUBJECT
        # We don't search for "who is next". The list decides.
        s_i = subj_order[idx]
        
        # 4. BRANCHING
        # Try every nominal partner for s_i
        # We iterate in REVERSE so the first option is popped first (LIFO behavior)
        candidates = potential_pair_db[s_i]
        
        # Optimization: Sort candidates to try "easiest" analogies first if possible, 
        # or just reverse the list.
        for n_i, local_adb in reversed(candidates):
            
            # A. Structural Check (Fast O(1))
            if n_i in used_noms:
                continue

            # B. Analogy Check (Evolving Constraint)
            # This is where we check if the path is still valid
            verdict, new_adb = get_analogy_db(adb, local_adb)
            if not verdict:
                continue

            # C. Push Next State
            # We move to idx + 1 (Next subject in strict order)
            # 'pairs | {s_i: n_i}' creates a NEW dict efficiently
            # 'used_noms | {n_i}' creates a NEW set efficiently
            stack.append((idx + 1, 
                          pairs | {s_i: n_i}, 
                          new_adb, 
                          used_noms | {n_i}))

    # If stack empties and we haven't returned, we didn't find a full match.
    return Result({}, global_pair_db | best_pairs, best_adb, 
                  required_pair_n, True)

@lru_cache(maxsize=4096)
def get_analogy_db(aggregated_analogy_db, required_analogy_db):
    if not required_analogy_db:
        return True, (aggregated_analogy_db.clone() if aggregated_analogy_db else None)
    elif not aggregated_analogy_db:
        return True, required_analogy_db
    elif aggregated_analogy_db.is_all_consistent(required_analogy_db):
        return True, aggregated_analogy_db.merge(required_analogy_db)
    else:
        return False, None

