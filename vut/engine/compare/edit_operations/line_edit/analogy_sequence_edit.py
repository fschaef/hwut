import vut.engine.compare.edit_operations.line_edit.common as edit_operation_search
from   collections import defaultdict


def do(subject_list, nominal_list):
    """
    Orchestrates the Analogy Edit Distance process.
    
    1. Solves Analogies (Constraint Satisfaction).
    2. Maps Subject to Nominal space.
    3. Encodes everything to Integers.
    4. Calls Generic Edit Sequence solver.
    5. Decodes Integers back to original Line Elements.
    
    Args:
        subject_list (list[str]): List of strings from Subject.
        nominal_list (list[str]): List of strings from Nominal.
        
    Returns:
        tuple: (cost, edit_sequence, analogy_map)
    """
    # 1. Establish the Vocabulary (Global Constraints)
    analogy_map = find_best_analogies(subject_list, nominal_list)
    
    
    # 2. Integer Encoding (Tokenization)
    #    Create a shared vocabulary for both lists to feed into the generic solver.
    subject_ids, \
    nominal_ids  = assign_token_ids(subject_list, nominal_list, analogy_map)

    # 3. Calculate Structure (Generic ID-based Solver)
    #    This returns indices: {'code': 'TRANSPOSE', 'old_idx': 0, 'new_idx': 2, ...}
    raw_edit_sequence = edit_operation_search.do(subject_ids, nominal_ids)
    
    # 4. Hydration (Decode Indices to Objects)
    final_sequence = []
    
    for op in raw_edit_sequence:
        code   = op['code']
        new_op = {'code': code}
        
        # 'old_idx' refers to the Subject List
        if 'old_idx' in op:
            idx = op['old_idx']
            new_op['old_idx'] = idx
            new_op['item']    = subject_list[idx]  # Use ORIGINAL subject item
            
        # 'new_idx' refers to the Nominal List
        if 'new_idx' in op:
            idx = op['new_idx']
            new_op['new_idx'] = idx
            new_op['target']  = nominal_list[idx] # Use Nominal item as target
            
        final_sequence.append(new_op)
    
    # 5. Cost Calculation
    cost = sum(1 for op in final_sequence if op['code'] != 'MATCH')
    
    return cost, final_sequence, analogy_map

def find_best_analogies(subject_list, nominal_list):
    """
    Creates a 1:1 translation map.
    
    Strategy: "Positional Proximity > Appearance Order"
    
    Greedy Minimum Distance:
       Tokens are mapped based on the distance between their 
       first appearance indices.
       - A token at index 3 prefers a target at index 3 (Distance 0).
       - This prevents early tokens from "stealing" perfectly aligned 
         later matches.
    """
    if not subject_list or not nominal_list:
        return {}

    # 1. Identify First Appearances (O(N))
    # We manually build these to get indices.
    s_first_idx = {}
    for i, item in enumerate(subject_list):
        if item not in s_first_idx:
            s_first_idx[item] = i
            
    n_first_idx = {}
    for i, item in enumerate(nominal_list):
        if item not in n_first_idx:
            n_first_idx[item] = i
            
    mapping = {}
    mapped_n = set()
    
    # --- Greedy Minimum Distance ---
    # Prepare list of candidates with their indices
    s_candidates = list(s_first_idx.items())
    n_candidates = list(n_first_idx.items())
    
    # Generate all possible pairs with their distance
    # Structure: (distance, s_index, s_item, n_item)
    pairs = []
    for s_item, s_idx in s_candidates:
        for n_item, n_idx in n_candidates:
            dist = abs(s_idx - n_idx)
            pairs.append((dist, s_idx, s_item, n_item))
            
    # Sort by Distance (asc), then by Subject Index (asc) for stability
    # This prioritizes perfect positional matches (dist 0), then close ones.
    pairs.sort(key=lambda x: (x[0], x[1]))
    
    # Greedy Selection
    for _, _, s_item, n_item in pairs:
        if s_item not in mapping and n_item not in mapped_n:
            mapping[s_item] = n_item
            mapped_n.add(n_item)
            
    return mapping

def assign_token_ids(subject_list, nominal_list, analogy_map):
    # 2. Transform Subject (Apply Analogies)
    #    This aligns the subject's 'meaning' with the nominal's 'meaning'.
    transformed_subject = [analogy_map.get(x, x) for x in subject_list]

    v = defaultdict()
    v.default_factory = v.__len__
        
    # Fastest approach, faster than list comprehensions
    # (The whole thing operates in 'C' without list iteration)
    return list(map(v.__getitem__, transformed_subject)), \
           list(map(v.__getitem__, nominal_list))
    
