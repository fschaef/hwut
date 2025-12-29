from vut.engine.compare.friends_pairing.result   import Result
from vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb

def do(db):
    """
    High-speed backtracking solver. 
    RETURNS: (dict: {subject: nominal}, AnalogyDb: final_constraints) or None
    """
    subject_i_by_sidx = sorted(db.keys())
    lane_n = len(subject_i_by_sidx)
    
    # 1. Pre-process lanes into frozen options
    lane_options = []
    for s_i in subject_i_by_sidx:
        lane_options.append([
            (nom, FrozenAnalogyDb(adb)) for nom, adb in sorted(db[s_i])
        ])

    # 2. State Vector: [Cumulative_ADB, Used_Nominals_Set, Next_Candidate_Index]
    empty_adb       = FrozenAnalogyDb({})
    decision_vector = [[empty_adb, set(), 0]]

    while decision_vector:
        sidx = len(decision_vector) - 1
        current_path_adb, used_noms, c_idx = decision_vector[-1]
        
        candidates = lane_options[sidx]
        found_candidate = None

        # --- SEARCH ---
        while c_idx < len(candidates):
            nom_i, pad_adb = candidates[c_idx]
            c_idx += 1
            
            if nom_i in used_noms: continue
            if not current_path_adb.is_all_consistent(pad_adb): continue
                
            found_candidate = (nom_i, pad_adb)
            break

        # --- BACKTRACK ---
        if found_candidate is None:
            decision_vector.pop()
            continue

        # --- COMMIT DECISION ---
        decision_vector[-1][2] = c_idx 
        new_nom, new_adb = found_candidate
        next_path_adb    = current_path_adb.merge(new_adb)
        
        # --- CHECK SUCCESS ---
        if sidx + 1 == lane_n:
            mapping = {}
            for i, state in enumerate(decision_vector):
                subj = subject_i_by_sidx[i]
                nom  = lane_options[i][state[2]-1][0]
                mapping[subj] = nom
            
            # Return the formal Result object
            return Result(
                potential_pair_db     = db,
                pair_db               = mapping, # Your PairedGraph
                analogy_constraint_db = next_path_adb,
                required_pair_n       = len(db),
                aborted_f             = False
            )

        # --- ADVANCE ---
        decision_vector.append([
            next_path_adb,
            used_noms | {new_nom},
            0
        ])

    # Failure Case: Return an 'aborted' or empty Result
    return Result(
        potential_pair_db     = db,
        pair_db               = {},
        analogy_constraint_db = empty_adb,
        required_pair_n       = len(db),
        aborted_f             = True
    )


