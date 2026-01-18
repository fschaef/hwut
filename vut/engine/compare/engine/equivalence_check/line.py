from __future__ import annotations
from vut.engine.compare.engine.analogy_db  import AnalogyDb

def do(subject:    InputChunk,    #noqa F821
       nominal:    InputChunk,    #noqa F821
       analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, subject and nominal a definitely equal => equivalent
                    False, subject and nominal are definitely not equivalent
                    None, undecided
                [1] equivalent => the required updated analogy_db,
                    else       => some analogy_db
    """
    if len(subject.line_list) != len(nominal.line_list):
        return False, analogy_db
    # In 'equivalence check mode' subject and nominal proceed line by line
    # assert len(subject.line_list) == 1 and len(nominal.line_list) == 1

    verdict, analogy_list = subject.line_list[0].is_literally_equivalent_to(nominal.line_list[0])

    if verdict:
        # if lines are textually equal, the analogies must hold
        # if not => definitely not equivalent in the global frame
        return analogy_db.extend_if_consistent(analogy_list)

    analogy_set = set()
    for subject_line, nominal_line in zip(subject.line_list, nominal.line_list):
        verdict, analogy_list = subject_line.is_equivalent(nominal_line, analogy_db)
        if not verdict:
            return False, analogy_db
        analogy_set.update(analogy_list)
    else:
        return analogy_db.extend_if_consistent(analogy_set)

