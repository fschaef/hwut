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
    if   subject.__class__ is not nominal.__class__: return False, analogy_db
    elif subject.__class__ is InputChunkTerminal:    return True, analogy_db  # here: both are 'InputChunkTerminal'

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
        verdict, analogy_db = subject_line.compare(nominal_line, analogy_db)
        if not verdict:
            return False, analogy_db
    else:
        return True, analogy_db

@typechecked
def _do_potpourri(subject_line_list: tuple[Line,...], 
                  nominal_line_list: tuple[Line,...], 
                  analogy_db:        AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if both potpourris are equivalent. False, else.
                [1] analogy_db required for equivalence to hold.
    """
    subject_potpourri = subject_line_list[1:-1] # exclude [0] and [-1]:
    nominal_potpourri = nominal_line_list[1:-1] # first and last line carry Potpourri markers.

    verdict, _, new_analogy_db = potpourri_equivalence_check.do(subject_potpourri,
                                                                nominal_potpourri,
                                                                analogy_db,
                                                                abort_early_f=True)

    if verdict: return True, new_analogy_db
    else:       return False, analogy_db
