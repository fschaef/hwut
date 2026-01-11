from   vut.engine.compare.engine.enums                 import E_Chunk
import vut.engine.compare.engine.equivalence_check.line_sequence as line_sequence_check
import vut.engine.compare.engine.equivalence_check.potpourri     as potpourri_check
from   vut.engine.compare.engine.analogy_db            import AnalogyDb
from   vut.engine.compare.input.pattern_finder         import E_ToleranceId
from   vut.engine.compare.input.input_chunk            import InputChunk, \
                                                              InputChunkTerminal

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
    match subject.type():
        case E_Chunk.LINE:
            return line_sequence_check.do(subject, nominal, analogy_db)
        case E_Chunk.POTPOURRI:
            return potpourri_check.do(subject, nominal, analogy_db)
        case _:
            assert False, f"{subject.type().name} not supported for equivalence check!"
