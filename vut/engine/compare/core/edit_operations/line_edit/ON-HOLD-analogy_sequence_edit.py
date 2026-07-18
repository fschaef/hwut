import vut.engine.compare.associate.edit_operations.line_edit.common as     edit_operation_search
from   vut.engine.compare.associate.edit_operations.edit             import E_EditId, EditSequence
from   collections import defaultdict


def do(subject_list, nominal_list):
    """
    ASSUMPTION: All LineElements in subject and nominal are 'LineElementAnalogy'
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

    if subject_ids == nominal_ids: # Perfect alignment?
        # => every single analogy holds and corresponds
        return EditSequence(cost       = 0, 
                            sequence   = [E_EditId.GOOD] * len(subject_ids),
                            analogy_db = analogy_map)

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

from itertools import zip_longest
from collections import Counter

def find_best_analogies(subject_list, nominal_list):
    """
    Creates a 1:1 translation map based on Strict Linear Alignment.
    
    Strategy:
    1. Linear Scan (Zip): Iterate through both lists in parallel. If both
       tokens at index I are "fresh" (unmapped), map them immediately.
       This captures positional structure (e.g., C at index 3 matches 1 at index 3).
       
    2. Leftovers: Collect any tokens skipped in Phase 1 and map them 1:1 
       based on their first appearance order.
    """
    mapping = {}
    # Use set for fast O(1) lookups of 'consumed' nominal tokens.
    # Mapped subject tokens are tracked via 'mapping' keys.
    n_mentioned = set()
    
    # --- Phase 1: Strict Positional Alignment ---
    # We iterate through both lists in parallel. 
    # zip_longest ensures we process up to the end of the longer list.
    for s, n in zip_longest(subject_list, nominal_list):
        # If lengths differ, one will be None. We cannot align a gap.
        if s is None or n is None:
            continue
            
        # If both are "fresh" at this index, we lock the alignment.
        # This solves the "Slot Stealing" problem by prioritizing the exact index.
        if s not in mapping and n not in n_mentioned:
            mapping[s] = n
            n_mentioned.add(n)
            
    # --- Phase 2: Map Leftovers ---
    # Any tokens that were skipped (because their slot was taken by a previous mapping)
    # get mapped to available targets in order of first appearance.
    
    # Counter keys are insertion-ordered (Python 3.7+), so this preserves appearance order.
    # We assume standard Python dictionaries are used.
    s_left = (s for s in Counter(subject_list) if s not in mapping)
    n_left = (n for n in Counter(nominal_list) if n not in n_mentioned)
    
    # Map remaining items 1:1
    mapping.update((s, n) for s, n in zip(s_left, n_left))
        
    return mapping

def assign_token_ids(subject_list, nominal_list, analogy_map):
    # 2. Transform Subject (Apply Analogies)
    #    This aligns the subject's 'meaning' with the nominal's 'meaning'.
    transformed_subject = [analogy_map.get(x, x) for x in subject_list]

    v = defaultdict()
        
    # Fastest approach, faster than list comprehensions
    # (The whole thing operates in 'C' without list iteration)
    return list(map(v.__getitem__, transformed_subject)), \
           list(map(v.__getitem__, nominal_list))
    
