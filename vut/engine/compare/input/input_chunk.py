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
from   vut.engine.compare.engine.analogy_db     import AnalogyDb
from   vut.engine.compare.engine.line           import Line
from   vut.engine.compare.input.pattern_finder  import E_ToleranceId

from   abc       import ABC

VISIBLE_NOTHING = E_ToleranceId.VISIBLE_NOTHING

class InputChunk(ABC):
    """Interface definition for input chunks.

        .compare()    --> compare two InputChunk-s.
        .line_pairs() --> determine best line associations for display.

    """
    def __init__(self, chunk_type: E_Chunk, start_line_n, end_line_n, iterable, config):
        self.line_list     = tuple(iterable)
        self.start_line_n  = start_line_n
        self.end_line_n    = end_line_n
        self.configuration = config
        self.__chunk_type  = chunk_type

    def empty_clone(self):
        return self.__class__(self.__chunk_type, None, None, [], self.configuration)

    def type(self): 
        return self.__chunk_type

    def __repr__(self): 
        sep = ":" if self.__chunk_type is E_Chunk.LINE_SEQUENCE else "|"
        return "\n".join("%03i%s %s" % (line.line_n, sep, line) for line in self.line_list)

class InputChunkTerminal(InputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self, line_n):
        InputChunk.__init__(self, E_Chunk.TERMINAL, line_n, line_n+1,
                            [Line.from_string(line_n, "<InputChunkTerminal>")],
                            config=None)
    def type(self):                                    return E_Chunk.TERMINAL
    def _is_equivalent(self, other, analogy_db):       assert False
    def _associate_lines(self, nominal, analogy_db):   return [], AnalogyDb()
    def __repr__(self):                                return "InputChunkTerminal"


class InputChunkEmpty(InputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self):
        InputChunk.__init__(self, E_Chunk.EMPTY, None, None, [Line.from_nothing()], config=None)
    def type(self):                                  return E_Chunk.EMPTY
    def _is_equivalent(self, other, analogy_db):           assert False
    def _associate_lines(self, nominal, analogy_db): return [], AnalogyDb()
    def __repr__(self):                              return "InputChunkEmpty"
