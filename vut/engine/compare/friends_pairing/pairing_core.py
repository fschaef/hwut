from vut.engine.compare.engine.analogy_db import AnalogyDb

from .result import Result

def pair_with_analogy_constraints(potential_pair_db, analogy_constraint_db, pair_db, required_pair_n) -> tuple[dict,AnalogyDb]:
    assert potential_pair_db

    db                  = potential_pair_db
    L                   = len(db)
    subject_singles_all = set(db)
    analogy_db          = analogy_constraint_db

    work_list = [
        (ia, {}, analogy_db) for ia in subject_singles_all
    ]
    best_size = 0; best_couples = {}; best_analogy_db = AnalogyDb()

    abort_f = False
    while work_list and not abort_f:
        ia, couples, analogy_db = work_list.pop()

        remaining_subject_singles = subject_singles_all.difference(couples.keys())
        remaining_subject_singles.remove(ia)
        remaining_nominal_singles = db.remaining_nominal_singles(ia, couples, analogy_db)

        for ib, required_analogy_db in sorted(remaining_nominal_singles):
            if required_analogy_db:
                new_analogy_db = analogy_db.clone().extend(required_analogy_db, ia, ib)
            else:
                new_analogy_db = analogy_db

            new_couples     = dict(couples)  # isolate 'couple' database
            new_couples[ia] = ib

            if len(new_couples) > best_size:
                best_size       = len(new_couples)
                best_couples    = new_couples
                best_analogy_db = new_analogy_db
            if best_size == L:
                abort_f = True
                break

            work_list.extend(
                (ia, new_couples, new_analogy_db)
                for ia in remaining_subject_singles
            )

    return Result(potential_pair_db     = {},
                  pair_db               = pair_db | best_couples, 
                  analogy_constraint_db = best_analogy_db,
                  required_pair_n       = required_pair_n,
                  aborted_f             = best_size != L)

