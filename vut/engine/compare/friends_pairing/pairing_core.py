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
        can_match(subject, visited)

    # Invert the result to get {subject: nominal}
    return {s: n for n, s in nominal_owner.items()}

def solve_analogy_constraint_matching(potential_pair_db, global_analogy_db, global_pair_db, required_pair_n) -> tuple[dict,AnalogyDb]:
    assert potential_pair_db

    db = potential_pair_db
    L  = len(db)

    work_list = []
    for subject_i, mate_list in db.items():
        for nominal_i, analogy_db in mate_list:
            verdict, new_analogy_db = get_analogy_db(global_analogy_db, analogy_db)
            if not verdict: continue
            work_list.append((frozenset({(subject_i, nominal_i)}), new_analogy_db, frozenset({nominal_i})))
    
    best_size = 0; best_pair_set = frozenset(); best_analogy_db = AnalogyDb()
    considered_set = set() 

    while work_list:
        pair_set, aggregated_analogy_db, used_nominals = work_list.pop()

        if len(pair_set) > best_size:
            best_size       = len(pair_set)
            best_pair_set   = pair_set
            best_analogy_db = aggregated_analogy_db
        if best_size == L:
            break

        for ia, ib, required_analogy_db in candidates(db, pair_set, used_nominals):
            verdict, new_analogy_db = get_analogy_db(aggregated_analogy_db, 
                                                     required_analogy_db)
            if not verdict: continue

            # Neues frozenset erstellen durch Mengen-Union
            new_pair_set = pair_set | {(ia, ib)}
            if new_pair_set not in considered_set:
                work_list.append((new_pair_set, 
                                  new_analogy_db, 
                                  used_nominals | {ib}))

    return Result(potential_pair_db     = {},
                  pair_db               = global_pair_db | dict(best_pair_set), 
                  analogy_constraint_db = best_analogy_db,
                  required_pair_n       = required_pair_n,
                  aborted_f             = best_size != L)

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

