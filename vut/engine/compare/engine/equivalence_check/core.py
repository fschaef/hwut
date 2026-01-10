from   vut.engine.compare.engine.enums                 import E_Chunk
from   vut.engine.compare.engine.analogy_db            import AnalogyDb
from   vut.engine.compare.engine.line                  import Line
from   vut.engine.compare.input.pattern_finder         import E_ToleranceId
from   vut.engine.compare.input.input_chunk            import InputChunk, \
                                                              InputChunkTerminal
import vut.engine.compare.engine.potpourri.equivalence_check  as     potpourri_equivalence_check

from  typeguard import typechecked

VISIBLE_NOTHING = E_ToleranceId.VISIBLE_NOTHING

@typechecked
def do(subject: InputChunk, nominal: InputChunk, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if both sequences are equivalent. False, else.
                [1] analogy_db required for equivalence to hold.

    The 'analogy_db' contains analogies imposed from lines which are
    equivalent. If the test fails ([0] == False), the analogy database is
    irrelevant, since the global comparison needs to stop. For display
    (see .line_pairs()), this different.
    """
    if   subject.type() is not nominal.type():    return False, analogy_db
    elif subject.__class__ is InputChunkTerminal: return True, analogy_db  # here: both are 'InputChunkTerminal'

    # NOTE: The 'quick path' functions are only quick, if they appear before
    #       '.sequence' properties are referenced. The referencing of these 
    #       properties triggers a (lazy) lexical analysis of the line!
    elif subject.type() == E_Chunk.LINE_SEQUENCE:
        verdict, analogy_db = _do_line_sequence_quick_path(subject, nominal, analogy_db)
        if verdict is not None: 
            return verdict, analogy_db
       
        # verdict is False => not equal, but possibly equivanent ...
    elif subject.type() == E_Chunk.POTPOURRI:
        verdict, new_analogy_db = _do_potpourri_quick_path(subject, nominal, analogy_db)
        if verdict is True: return True, new_analogy_db
        # verdict is False => not equal, but possibly equivanent ...

    if   subject.type() is E_Chunk.LINE_SEQUENCE: 
        return _do_line_sequence(subject.line_list, nominal.line_list,
                                 analogy_db)
    elif subject.type() is E_Chunk.POTPOURRI:     
        return _do_potpourri(subject, nominal, analogy_db)
    else:                                         
        assert False

@typechecked
def _do_line_sequence(subject_line_list: tuple[Line,...], 
                      nominal_line_list: tuple[Line,...], 
                      analogy_db:        AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if 'self' and 'nominal' are equivalent.
                    False, else.
                [1] AnalogyDb required for the equivalents of [0] to hold.
    """
    for subject_line, nominal_line in zip(subject_line_list, nominal_line_list):
        verdict, analogy_db = subject_line.is_equivalent(nominal_line, analogy_db)
        if not verdict:
            return False, analogy_db
    else:
        return True, analogy_db

def _do_line_sequence_quick_path(subject, nominal, analogy_db):
    """RETURNS: [0] True, subject and nominal a definitely equal => equivalent
                    False, subject and nominal are definitely not equivalent
                    None, undecided
                [1] equivalent => the required updated analogy_db,
                    else       => some analogy_db
    """
    if len(subject.line_list) != len(nominal.line_list):
        return False, analogy_db
    # In 'equivalence check mode' subject and nominal proceed line by line
    assert len(subject.line_list) == 1 and len(nominal.line_list) == 1

    verdict, analogy_list = subject.line_list[0].compare_raw(nominal.line_list[0])

    if verdict:
        # if lines are textually equal, the analogies must hold
        # if not => definitely not equivalent in the global frame
        for analogy in analogy_list:
            if not analogy_db.add_if_consistent(analogy):
                return False, analogy_db
        return True, analogy_db
    else:
        return None, analogy_db 

@typechecked
def _do_potpourri(subject:     InputChunk,
                  nominal:     InputChunk,
                  analogy_db:  AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if both potpourris are equivalent. False, else.
                [1] analogy_db required for equivalence to hold.
    """
    verdict, _, new_analogy_db = potpourri_equivalence_check.FUTURE_DO(subject, nominal, analogy_db,
                                                                       abort_early_f=True)

    if verdict: return True, new_analogy_db
    else:       return False, analogy_db

def _do_potpourri_quick_path(subject, nominal, analogy_db):
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
