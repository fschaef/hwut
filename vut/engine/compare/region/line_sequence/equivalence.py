from __future__ import annotations
from vut.engine.compare.contract.analogy_db  import AnalogyDb
from vut.engine.compare.contract.semantics   import commit_analogies
from vut.engine.compare.engine             import constraints

def do(subject:    InputChunk,    #noqa F821
       nominal:    InputChunk,    #noqa F821
       analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, subject and nominal are equal => equivalent
                    False, subject and nominal are not equivalent
                [1] equivalent => the required updated analogy_db,
                    else       => some analogy_db

    STATEFUL CONSTRAINTS ('engine/constraints.py'): after a pair of lines
    is found equivalent, its '((name: value))' bindings enter the constraint
    space -- a subject-side violation turns the verdict False (red cell); a
    nominal-side violation raises loudly (broken specification). On a
    non-equivalent pair the space is killed: no binding after the Judge's
    abort point is ever processed (mirrored by the Lawyer -- THE LAW).
    """
    verdict, analogy_db = _judge(subject, nominal, analogy_db)

    context = constraints.context_get()
    if context is not None and context.alive:
        if not verdict:
            context.kill()
        elif not constraints.enter_line(context,
                                        subject.line_list[0],
                                        nominal.line_list[0]):
            return False, analogy_db
    return verdict, analogy_db

def _judge(subject, nominal, analogy_db):
    """RETURNS: [0] True, subject and nominal lines are equivalent (text
                    and analogies alone -- constraints judged by caller)
                    False, else
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
        verdict = commit_analogies(analogy_db, analogy_list)
        return verdict, analogy_db

    analogy_list = []
    assert len(subject.line_list) < 2 and len(nominal.line_list) < 2
    for subject_line, nominal_line in zip(subject.line_list, nominal.line_list, strict=False):
        verdict, new_analogy_list = subject_line.is_equivalent(nominal_line, analogy_db)
        if not verdict:
            return False, analogy_db
        analogy_list.extend(new_analogy_list)

    # subject line is equivalent to nominal line under the constraint
    # of the given analogies
    verdict = commit_analogies(analogy_db, analogy_list)
    return verdict, analogy_db
