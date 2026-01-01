
def do(seq1_ids, seq2_ids):
    """Generic Edit Sequence Finder with Transpose Detection.
       Operates purely on Integer IDs.
    
    Args:
        seq1_ids (list[int]): Source sequence IDs
        seq2_ids (list[int]): Target sequence IDs
    Returns:
        list[dict]: List of operations with indices.
    """
    # 1. Sequence Alignment (LCS)
    #    Using difflib here, but this is compatible with rapidfuzz.distance.Levenshtein.editops
    matcher = difflib.SequenceMatcher(None, seq1_ids, seq2_ids)
    
    raw_ops = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                raw_ops.append({
                    'code': 'MATCH', 
                    'old_idx': i1+k,
                    'new_idx': j1+k,
                    'id': seq1_ids[i1+k] 
                })
        elif tag == 'replace':
            # Treat replace as Delete + Insert to allow Transpose logic to catch moves
            for k in range(i2 - i1):
                raw_ops.append({'code': 'DELETE', 'old_idx': i1+k, 'id': seq1_ids[i1+k]})
            for k in range(j2 - j1):
                raw_ops.append({'code': 'INSERT', 'new_idx': j1+k, 'id': seq2_ids[j1+k]})
        elif tag == 'delete':
            for k in range(i2 - i1):
                raw_ops.append({'code': 'DELETE', 'old_idx': i1+k, 'id': seq1_ids[i1+k]})
        elif tag == 'insert':
            for k in range(j2 - j1):
                raw_ops.append({'code': 'INSERT', 'new_idx': j1+k, 'id': seq2_ids[j1+k]})

    # 2. Transpose Detection (The "Ghost" Heuristic)
    #    Structure: Map[ID] -> List[Op] (Handling duplicates via queue)
    pending_deletes_map = defaultdict(list)
    for op in raw_ops:
        if op['code'] == 'DELETE':
            pending_deletes_map[op['id']].append(op)

    final_ops = []
    consumed_delete_indices = set()

    for op in raw_ops:
        if op['code'] == 'MATCH':
            final_ops.append(op)
            
        elif op['code'] == 'INSERT':
            ins_id = op['id']
            # Look for a matching delete
            candidates = pending_deletes_map.get(ins_id, [])
            
            # Find a candidate that hasn't been consumed yet
            found_delete = None
            for cand in candidates:
                if cand['old_idx'] not in consumed_delete_indices:
                    found_delete = cand
                    break
            
            if found_delete:
                consumed_delete_indices.add(found_delete['old_idx'])
                final_ops.append({
                    'code': 'TRANSPOSE',
                    'old_idx': found_delete['old_idx'],
                    'new_idx': op['new_idx'],
                    # id is helpful for debugging but not strictly needed in output
                    'id': ins_id 
                })
            else:
                final_ops.append(op)
                
        elif op['code'] == 'DELETE':
            # Defer processing; we add leftovers later
            pass

    # 3. Add Unconsumed Deletes
    for op in raw_ops:
        if op['code'] == 'DELETE':
            if op['old_idx'] not in consumed_delete_indices:
                final_ops.append(op)
                
    return final_ops
