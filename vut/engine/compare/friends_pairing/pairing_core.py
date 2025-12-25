from vut.engine.compare.engine.analogy_db import AnalogyDb

from .result import Result

def pair_with_analogy_constraints(potential_pair_db, global_analogy_db, global_pair_db, required_pair_n) -> tuple[dict,AnalogyDb]:
    assert potential_pair_db

    db = potential_pair_db
    L  = len(db)

    work_list = []
    for subject_i, mate_list in db.items():
        for nominal_i, analogy_db in mate_list:
            verdict, new_analogy_db = get_analogy_db(global_analogy_db, analogy_db)
            if not verdict: continue
            work_list.append((frozenset({(subject_i, nominal_i)}), new_analogy_db))
    
    best_size = 0; best_pair_set = frozenset(); best_analogy_db = AnalogyDb()
    considered_set = set() 

    while work_list:
        pair_set, aggregated_analogy_db = work_list.pop()

        if len(pair_set) > best_size:
            best_size       = len(pair_set)
            best_pair_set   = pair_set
            best_analogy_db = aggregated_analogy_db
        if best_size == L:
            break

        for ia, ib, required_analogy_db in candidates(db, pair_set):
            verdict, new_analogy_db = get_analogy_db(aggregated_analogy_db, 
                                                     required_analogy_db)
            if not verdict: continue

            # Neues frozenset erstellen durch Mengen-Union
            new_pair_set = pair_set | {(ia, ib)}
            if new_pair_set not in considered_set:
                work_list.append((new_pair_set, new_analogy_db))

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

def candidates(db, pair_set):
    subjects_paired = {p[0] for p in pair_set}
    nominals_paired = {p[1] for p in pair_set}
    for subject_i, mate_list in db.items():
        if subject_i in subjects_paired: continue
        for nominal_i, analogy_db in mate_list:
            if nominal_i in nominals_paired: continue
            yield subject_i, nominal_i, analogy_db

