from   vut.engine.compare.engine.analogy_db        import AnalogyDb
from   vut.engine.compare.input.input_chunk        import InputChunk
import vut.engine.compare.engine.potpourri.pairing as     pairing

from   typeguard import typechecked

@typechecked
def do(subject:    InputChunk,
       nominal:    InputChunk,
       analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:

    verdict, analogy_db = do_quick_path(subject, nominal, analogy_db)
    if verdict is not None: 
        return verdict, analogy_db

    verdict,       \
    _,             \
    new_analogy_db = pairing.do(subject, nominal, analogy_db,
                                abort_early_f=True)

    if verdict: return True, new_analogy_db
    else:       return False, analogy_db

def do_quick_path(subject, nominal, analogy_db):
    """RETURNS: [0] True, subject and nominal a definitely equal => equivalent
                    False, subject and nominal are definitely not equivalent
                    None, undecided
                [1] equivalent => the required updated analogy_db,
                    else       => some analogy_db

    1. Partition lines Lines with analogies and Lines without. 
    2. counts do not match                                    => False
    3. Non-analogy lines do not match literally (via sorting) => None, they can still be equivalent
    4. Analogy lines do not match literally (via sorting)     => None, they can still be equivalent
    5. Analogies are inconsistent                             => None, possibly lines may be sorted differently
    => True, lines are literally equal and analogies are consistent
    """
    def check_analogy_consistency(line_list, analogy_db):
        # Literal match of analogy lines => analogies must be self-mapping.
        return analogy_db.is_all_consistent(
                   (a, a)
                   for line in line_list
                   for a in line._raw.analogy_strings())

    if len(subject.analogy_line_list) != len(nominal.analogy_line_list):
        return False, analogy_db # EQUIVALENCE impossible!

    # literal equivalence of non-analogy lines
    s = { line._raw.string for line in subject.non_analogy_line_list }
    n = { line._raw.string for line in nominal.non_analogy_line_list }
    if s != n:
        if len(s) != len(n): return False, analogy_db # EQUIVALENCE impossible!
        else:                return None, analogy_db  # 'soft interpretation' may yield EQUIVALENCE

    # literal equivalence of analogy lines
    s = { line._raw.string for line in subject.analogy_line_list }
    n = { line._raw.string for line in nominal.analogy_line_list }
    if s != n:
        if len(s) != len(n): return False, analogy_db # EQUIVALENCE impossible!
        else:                return None, analogy_db  # 'soft interpretation' may yield EQUIVALENCE

    # (1) non-analogy lines are literally equal
    # (2) analogy lines are literally equal
    # => if analogies are consistent with global analogy_db 
    # => EQUIVALENCE!
    analogy_list = [
        (a, a) 
        for line in subject.analogy_line_list # one line list == the other
        for a in line._raw.analogy_strings()
    ]
    if not analogy_db.is_all_consistent(analogy_list):
        return None, analogy_db  # 'soft interpretation' may different association
    else:
        analogy_db.update(analogy_list)
        return True, analogy_db
