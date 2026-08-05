"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Interpretations of input as 'LineSequence' and 'Potpourri' chunks.

The 'chunk_pipe' (engine/chunk_pipe.py) interprets an input stream as sequences
of 'InputChunk' objects. The 'InputChunk' defines the interface for the two
derived classes representing the two types of input chunks:

-- LineSequence: set of text lines where the sequence matters.
-- Potpourri:    set of text lines where the sequence does not matter.

The two main functions of an 'InputChunk' are

   .compare()    --> determines whether the chunk is equivalent to
                     another.
   .line_pairs() --> determines which lines should be best associated
                     for display.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.enums          import E_Chunk
from   vut.engine.compare.engine.line           import Line
from   vut.engine.compare.reading.pattern_finder  import E_ToleranceId
from   vut.engine.compare.engine.analogy_db     import AnalogyDb
from   vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb
import vut.engine.compare.region.line_sequence.equivalence      as equivalence_check_line
import vut.engine.compare.region.potpourri.equivalence as equivalence_check_potpourri
from   vut.engine.compare.core.line_pair       import LinePair
import vut.engine.compare.region.line_sequence.associate   as association_line_sequence
import vut.engine.compare.region.potpourri.associate       as association_potpourri

from   abc       import ABC
from   typing    import Iterable
from   typeguard import typechecked

VISIBLE_NOTHING = E_ToleranceId.VISIBLE_NOTHING

class InputChunk(ABC):
    """Interface definition for input chunks.

        .compare()    --> compare two InputChunk-s.
        .line_pairs() --> determine best line associations for display.

    """
    @typechecked
    def __init__(self, chunk_type: E_Chunk, start_line_n, end_line_n, line_list: Iterable[str], config):
        self.start_line_n  = start_line_n
        self.end_line_n    = end_line_n
        self.configuration = config
        self._chunk_type  = chunk_type
        self.__line_list   = tuple(line_list)

    def is_terminal(self):
        return False

    def is_error(self):
        return False

    @property
    def line_list(self):
        return self.__line_list

    def type(self): 
        return self._chunk_type

    def __repr__(self): 
        sep = ":" if self._chunk_type is E_Chunk.LINE_SEQUENCE else "|"
        return "\n".join("%03i%s %s" % (line.line_n, sep, line) for line in self.line_list)

class InputChunkVoid(InputChunk):
    def __init__(self):    self._chunk_type = E_Chunk.VOID
    def __repr__(self):    return "InputChunkVoid"

class EquivalenceRelatedInputChunk(InputChunk):
    @typechecked
    def is_equivalent_to_nominal(self, nominal, analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb | FrozenAnalogyDb]:
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.

        The 'analogy_db' contains analogies imposed from lines which are
        equivalent. If the test fails ([0] == False), the analogy database is
        irrelevant, since the global comparison needs to stop. For display
        (see .line_pairs()), this different.
        """
        if self.__class__ is not nominal.__class__: 
            return False, analogy_db
        return self._is_equivalent_to_nominal(nominal, analogy_db)

class AssociationRelatedInputChunk(InputChunk):
    @typechecked
    def associate_with_nominal(self, nominal, analogy_db: AnalogyDb) -> tuple[list[LinePair], AnalogyDb]:
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.

        The 'analogy_db' contains analogies imposed from lines which are
        equivalent. If the test fails ([0] == False), the analogy database is
        irrelevant, since the global comparison needs to stop. For display
        (see .line_pairs()), this different.
        """
        if self.__class__ is not nominal.__class__: 
            return False, analogy_db
        return self._associate_with_nominal(nominal, analogy_db)

class InputChunkLineSequence(AssociationRelatedInputChunk):
    @typechecked
    def __init__(self, start_line_n, end_line_n, line_list: Iterable[Line], config):
        super().__init__(E_Chunk.LINE_SEQUENCE, start_line_n, end_line_n, line_list, config)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_line_sequence.do(self, nominal, analogy_db)

class InputChunkTerminal(EquivalenceRelatedInputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self):    self._chunk_type = E_Chunk.TERMINAL
    def is_terminal(self): return True
    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        """called by super().is_equivalent_to_nominal()"""
        return True, analogy_db
    def __repr__(self):    return "InputChunkTerminal"

class InputChunkError(InputChunkTerminal):
    """Terminal that CARRIES AN ERROR (e.g. RegionSyntaxError) out of the
    async producer. The zip stage re-raises it in the consumer's context --
    a broken region framing must fail LOUDLY, never look like end-of-stream.
    """
    def __init__(self, error):
        self._chunk_type = E_Chunk.TERMINAL
        self.error       = error
    def is_error(self): return True
    def __repr__(self): return "InputChunkError(%r)" % (self.error,)

class InputChunkPotpourri(AssociationRelatedInputChunk, EquivalenceRelatedInputChunk):
    def __init__(self, start_line_n, end_line_n, line_list: Iterable[Line],
                 config, params=None):
        super().__init__(E_Chunk.POTPOURRI, start_line_n, end_line_n, line_list, config)

        # 'params' arrives fully resolved from the registry (shebang >
        # Configuration.region['potpourri'] > spec default). 'params=None'
        # happens only on DIRECT construction (unit tests, legacy factory)
        # -- then the spec default applies.
        if params is not None and params.get("max_comparisons") is not None:
            self.max_comparison_count = params["max_comparisons"]
        else:
            self.max_comparison_count = 128
        self.subset_f     = bool(params and params.get("subset"))
        self.duplicates_f = bool(params and params.get("duplicates"))

        # partition line list: lines with and without analogies
        self.analogy_line_list = []
        self.non_analogy_line_list = []
        for line in line_list:
            if line.has_analogy(): self.analogy_line_list.append(line)
            else:                  self.non_analogy_line_list.append(line)

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        """called by super().is_equivalent_to_nominal()"""
        return equivalence_check_potpourri.do(self, nominal, analogy_db)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_potpourri.do(self, nominal, analogy_db)

class InputChunkLine(EquivalenceRelatedInputChunk):
    # @typechecked -- too expensive
    def __init__(self, line_n, line: Line, config):
        super().__init__(E_Chunk.LINE, line_n, line_n, [line], config)

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        """called by super().is_equivalent_to_nominal()"""
        return equivalence_check_line.do(self, nominal, analogy_db)

def InputChunk_factory(chunk_type: E_Chunk, start_line_n, end_line_n, line_list: Iterable[Line], config):
    """RETURNS: InputChunk derivate depending on 'chunk_type'
    """
    match chunk_type:
        case E_Chunk.POTPOURRI:
            result = InputChunkPotpourri(start_line_n, end_line_n, line_list, config)
        case E_Chunk.LINE_SEQUENCE:
            result = InputChunkLineSequence(start_line_n, end_line_n, line_list, config)
        case E_Chunk.LINE:
            result = InputChunkLine(start_line_n, line_list[0], config)
        case _:
            result = InputChunk(chunk_type, start_line_n, end_line_n, line_list, config)

    return result

