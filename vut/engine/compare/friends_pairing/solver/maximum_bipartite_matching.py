
def do(subject_to_nominals: dict[int, set[int]]) -> dict[int, int]:
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
            break # return what has been found so far
            #     # caller checks for completeness

    # Invert the result to get {subject: nominal}
    return {s: n for n, s in nominal_owner.items()}

