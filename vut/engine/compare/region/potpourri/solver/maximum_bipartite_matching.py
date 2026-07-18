"""
PURPOSE:
    Finds the maximum bipartite matching using the Augmenting Path algorithm
    (Iterative implementation).

ALGORITHM:
    Ford-Fulkerson / Hopcroft-Karp logic using Iterative DFS.
    
    We search for an "Augmenting Path": a path starting at an unmatched subject,
    alternating between unmatched and matched edges, and ending at an unmatched 
    nominal. If such a path exists, we can "flip" the edges along the path to 
    increase the total matching size by 1.

COMPLEXITY:
    Time: O(E * V) in worst case (standard DFS behavior).
    Space: O(V) for stack and tracking maps.
"""

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
    # nominal_owner: maps Nominal_ID -> Subject_ID (The primary result)
    nominal_owner = {} 
    
    # subject_match: maps Subject_ID -> Nominal_ID 
    # (Inverse map required for efficient O(1) path reconstruction without recursion)
    subject_match = {}

    # Try to find an augmenting path for every subject
    # Sorting ensures deterministic behavior
    for start_node in sorted(subject_to_nominals.keys()):
        
        # 1. ITERATIVE DFS
        # ----------------
        # We look for a path from 'start_node' to ANY free nominal.
        
        stack = [start_node]
        
        # pred: nominal -> subject
        # Keeps track of the path: "We reached nominal 'v' from subject 'u'"
        # This doubles as our 'visited' set for nominals.
        pred = {} 
        
        augmenting_path_end = None

        while stack:
            u = stack.pop()
            
            # Get candidates (nominals) for subject 'u'
            candidates = subject_to_nominals.get(u, [])
            
            for v in candidates:
                if v in pred:
                    continue # Already visited this nominal in this traversal
                
                # Record the path step: u -> v
                pred[v] = u
                
                if v not in nominal_owner:
                    # CASE 1: 'v' is free! 
                    # We found an augmenting path ending at 'v'.
                    augmenting_path_end = v
                    break
                else:
                    # CASE 2: 'v' is taken. 
                    # We must try to move the current owner of 'v' to a different nominal.
                    # Push the current owner onto the stack.
                    stack.append(nominal_owner[v])
            
            if augmenting_path_end is not None:
                break # Stop DFS, we found a path

        # 2. PATH RECONSTRUCTION (Backtracking)
        # -------------------------------------
        # If we found an augmenting path, we traverse 'pred' backwards 
        # to flip the edges and update the matching.
        
        if augmenting_path_end is None: continue

        curr_nom = augmenting_path_end
        
        # Iterate backwards until we hit the start of the chain
        while curr_nom is not None:
            # Who reached this nominal?
            new_subj = pred[curr_nom]
            
            # If 'new_subj' was previously matched to 'old_nom', 
            # we need to process 'old_nom' in the next iteration 
            # (because 'old_nom' just became free).
            old_nom = subject_match.get(new_subj)
            
            # Commit the new match
            nominal_owner[curr_nom] = new_subj
            subject_match[new_subj] = curr_nom
            
            # Move to the previous link in the chain
            curr_nom = old_nom

    # Return only the subject->nominal mapping as requested
    return {s: n for n, s in nominal_owner.items()}

