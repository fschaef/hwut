
MATCH     = 0
TRANSPOSE = 1
INSERT    = 2
DELETE    = 3
REPLACE   = 4

def extract_matches_and_transposes(s, n):
    """s, n: lists of int IDs (same length, cursor-aligned)

    RETURNS: [0] edit-ops: list of (opcode, i, j)
             [1] s_remain: list of remaining s IDs
             [2] n_remain: list of remaining n IDs
    """
    used = [False] * max(len(s), len(n))
    ops  = []

    # SPEED: binding global functions to local variables
    ops_append = ops.append 

    # fast path: MATCH
    for i, (a, b) in enumerate(zip(s, n)):
        if a == b:
            used[i] = True
            ops_append((MATCH, i, i))

    # transpose detection (first-match wins)
    last_unmatched_s = {}
    last_unmatched_n = {}

    # SPEED: binding global functions to local variables
    last_unmatched_s_get = last_unmatched_s.get
    last_unmatched_n_get = last_unmatched_n.get
    last_unmatched_s_pop = last_unmatched_s.pop
    last_unmatched_n_pop = last_unmatched_n.pop
    for i in range(len(s)):
        if used[i]: continue

        a = s[i]
        b = n[i]

        # check if this closes a transpose
        js = last_unmatched_n_get(a)
        jn = last_unmatched_s_get(b)

        if js is not None and jn is not None and js == jn:
            j = js
            used[i] = used[j] = True
            ops_append((TRANSPOSE, j, i))
            last_unmatched_s_pop(b, None)
            last_unmatched_n_pop(a, None)
        else:
            last_unmatched_s[a] = i 
            last_unmatched_n[b] = i 

    # build residue for Levenshtein
    s_remain = [s[i] for i in range(len(s)) if not used[i]]
    n_remain = [n[i] for i in range(len(n)) if not used[i]]

    return ops, s_remain, n_remain

def merge_ops(pre_ops, s_used, n_used, lev_ops):
    """RETURNS: final edit operations list of ops with original indices

    Merge MATCH / TRANSPOSE ops with Levenshtein ops on the residue.

    ARGS: 

      pre_ops: list of (opcode, i, j)
               MATCH and TRANSPOSE detected in step (1), using original indices
      s_used:  list[bool]
               True for subject positions already consumed (MATCH / TRANSPOSE)
      n_used:  list[bool]
               True for nominal positions already consumed
      lev_ops: list of (op, si, ni)
               Levenshtein.editops on the reduced sequences
    """

    # build index maps: reduced index -> original index
    s_map = [i for i, u in enumerate(s_used) if not u]
    n_map = [i for i, u in enumerate(n_used) if not u]

    final_ops = list(pre_ops)

    for op, si, ni in lev_ops:
        match op:
            case "equal":   final_ops.append((MATCH, s_map[si], n_map[ni]))
            case "delete":  final_ops.append((DELETE, s_map[si], -1))
            case "insert":  final_ops.append((INSERT, -1, n_map[ni]))
            case "replace": final_ops.append((REPLACE, s_map[si], n_map[ni]))

    # optional: sort by original positions for display
    final_ops.sort(key=lambda x: (x[1] if x[1] != -1 else float("inf"),
                                  x[2] if x[2] != -1 else float("inf")))

    return final_ops
