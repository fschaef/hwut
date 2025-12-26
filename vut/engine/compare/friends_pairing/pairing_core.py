from vut.engine.compare.engine.analogy_db import AnalogyDb

from .result import Result

def solve_unconstrained_matching(subject_to_nominals: dict[int, set[int]]) -> dict[int, int]:
    """
    Finds the maximum bipartite matching using the Augmenting Path algorithm.
    
    This implementation uses Depth-First Search (DFS) to find augmenting paths 
    in the bipartite graph. It is a specific application of the Ford-Fulkerson 
    method for Maximum Flow problems where capacities are 1.

    Algorithm:
        Based on Berge's Lemma (1957): A matching M is maximum if and only if 
        there exists no augmenting path with respect to M.

    Complexity:
        Time: O(E * V) in the worst case, where E is edges (possible pairs) 
              and V is vertices (subjects + nominals). 
              For typical dense graphs, this performs significantly faster than 
              general backtracking.
    
    References:
        - Berge, C. (1957). "Two Theorems in Graph Theory". 
          Proc. Natl. Acad. Sci. USA, 43(9), 842-844.
        - Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2009). 
          "Introduction to Algorithms" (3rd ed.), Section 26.2: Maximum Bipartite Matching.

    Args:
        subject_to_nominals: Adjacency list mapping Subject_ID -> Set[Nominal_ID]

    Returns:
        A dictionary representing the Maximum Matching: {Subject_ID: Nominal_ID}
    """
    # Track who owns which nominal: {nominal_id: subject_id}
    nominal_owner = {}

    def can_match(u: int, visited_nominals: set) -> bool:
        # Try every nominal 'v' that subject 'u' can accept
        for v in subject_to_nominals[u]:
            if v in visited_nominals:
                continue
            visited_nominals.add(v)

            # CORE LOGIC:
            # 1. Is nominal 'v' free? -> Take it!
            # 2. Is nominal 'v' taken? -> Ask the current owner to move.
            if v not in nominal_owner or can_match(nominal_owner[v], visited_nominals):
                nominal_owner[v] = u
                return True
        return False

    # Main Loop: Try to find a match for every subject
    # Sorting keys ensures deterministic behavior (useful for UTs)
    for subject in sorted(subject_to_nominals.keys()):
        visited = set() # Reset visited for each new path attempt

        if not can_match(subject, visited):
            # EARLY ABORT: If can_match returns False, it means there is no 
            # augmenting path for this subject. Based on Berge's Lemma, 
            # a perfect matching is now impossible.
            return None

    # Invert the result to get {subject: nominal}
    return {s: n for n, s in nominal_owner.items()}

def solve_analogy_constraint_matching(potential_pair_db, global_analogy_db, global_pair_db, required_pair_n) -> tuple[dict,AnalogyDb]:
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

def get_analogy_db(aggregated_analogy_db, required_analogy_db):
    if aggregated_analogy_db:
        if required_analogy_db:
            if aggregated_analogy_db.is_all_consistent(required_analogy_db):
                return True, aggregated_analogy_db.clone_updated(required_analogy_db)
            else:
                return False, None
        else:
            return True, aggregated_analogy_db.clone()
    else:
        if required_analogy_db:
            return True, required_analogy_db.clone()
        else:
            return True, None

def candidates(db, pair_set, used_nominals):
    subjects_paired = {p[0] for p in pair_set}
    # Computed along the path: used_nominals = {p[1] for p in pair_set} 
    for subject_i, mate_list in db.items():
        if subject_i in subjects_paired: continue
        for nominal_i, analogy_db in mate_list:
            if nominal_i in used_nominals: continue
            yield subject_i, nominal_i, analogy_db

