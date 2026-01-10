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

    # filter empty and VISIBLE_NOTHING lines.
    def _condition(line):
        if not line:                                               return False
        elif all(x.tolerance_id == VISIBLE_NOTHING for x in line): return False
        else:                                                      return True

    ## FOR EQUIVALENCE CHECK, THERE IS NO 'VISIBILE NOTHING' INVOLVED
    filtered_subject_line_list = tuple(line for line in subject.line_list if _condition(line))
    filtered_nominal_line_list = tuple(line for line in nominal.line_list if _condition(line))

    if len(filtered_nominal_line_list) != len(filtered_subject_line_list): 
        # filtered list are not of same size => impossible match
        return False, analogy_db

    if   subject.type() is E_Chunk.LINE_SEQUENCE: _do = _do_line_sequence
    elif subject.type() is E_Chunk.POTPOURRI:     _do = _do_potpourri
    else:                                         assert False

    return _do(filtered_subject_line_list, filtered_nominal_line_list, analogy_db)

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
def _do_potpourri(subject_line_list: tuple[Line,...], 
                  nominal_line_list: tuple[Line,...], 
                  analogy_db:        AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if both potpourris are equivalent. False, else.
                [1] analogy_db required for equivalence to hold.
    """
    subject_potpourri = subject_line_list # exclude [0] and [-1]:
    nominal_potpourri = nominal_line_list # first and last line carry Potpourri markers.

    verdict, _, new_analogy_db = potpourri_equivalence_check.do(subject_potpourri,
                                                                nominal_potpourri,
                                                                analogy_db,
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
    # Buckets for Subject
    def _paritition(line_list, analogy_raw_f=False):
        """RETURNS: [0] list of lines subject to analogies
                    [1] list of lines not subject to analogies
        """
        lines_w_anal_possible = []
        lines_wo_anal         = [] # Keep the Raw object to extract analogies later
        for line in line_list:
            item = line._raw if analogy_raw_f else line._raw.string
            if line._raw.may_have_analogy(): lines_w_anal_possible.append(item)
            else:                            lines_wo_anal.append(line._raw.string)
        return lines_w_anal_possible, lines_wo_anal

    def compare_raw_line_lists(lines_a, lines_b):
        lines_a.sort()
        lines_b.sort()
        return lines_a == lines_b

    def check_analogy_consistency(subject_w_anal_possible_raw, analogy_db):
        # Literal match of analogy lines => analogies must be self-mapping.
        return all(analogy_db.add_if_consistent((a, a))
                   for raw in subject_w_anal_possible_raw
                   for a in raw.analogy_strings())

    subject_w_anal_possible_raw, subject_wo_anal = _paritition(subject.line_list, analogy_raw_f=True)
    nominal_w_anal_possible, nominal_wo_anal = _paritition(nominal.line_list)

    if len(subject_wo_anal) != len(nominal_wo_anal):
        return False, analogy_db # EQUIVALENCE impossible!
    elif not compare_raw_line_lists(subject_wo_anal, nominal_wo_anal):
        return None, analogy_db  # 'soft interpretation' may yield EQUIVALENCE

    subject_w_anal_possible = [ raw.string for raw in subject_w_anal_possible_raw ]
    if not compare_raw_line_lists(subject_w_anal_possible, nominal_w_anal_possible):
        return None, analogy_db  # 'soft interpretation' may yield EQUIVALENCE
    elif not check_analogy_consistency(subject_w_anal_possible_raw, analogy_db):
        return None, analogy_db  # 'soft interpretation' may different association
    else:
        return True, analogy_db
