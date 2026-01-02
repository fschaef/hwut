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
from   vut.engine.compare.engine.enums          import E_Verdict, \
                                                       E_Chunk
from   vut.engine.compare.engine.analogy_db     import AnalogyDb
from   vut.engine.compare.engine.line           import Line
from   vut.engine.compare.input.pattern_finder  import E_ToleranceId

from   abc       import ABC, abstractmethod

VISIBLE_NOTHING = E_ToleranceId.VISIBLE_NOTHING

class InputChunk(ABC):
    """Interface definition for input chunks.

        .compare()    --> compare two InputChunk-s.
        .line_pairs() --> determine best line associations for display.

    """
    def __init__(self, start_line_n, end_line_n, iterable, config):
        self.line_list     = tuple(iterable)
        self.start_line_n  = start_line_n
        self.end_line_n    = end_line_n
        self.configuration = config

    def empty_clone(self):
        return self.__class__(None, None, [], self.configuration)

    def is_equivalent(self, nominal, analogy_db) -> E_Verdict:
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.

        The 'analogy_db' contains analogies imposed from lines which are
        equivalent. If the test fails ([0] == False), the analogy database is
        irrelevant, since the global comparison needs to stop. For display
        (see .line_pairs()), this different.
        """
        if self.__class__ != nominal.__class__:
            return E_Verdict.DIFFERENT, analogy_db
        elif self.__class__ == InputChunkTerminal:
            return E_Verdict.EQUIVALENT, analogy_db  # here: both are 'InputChunkTerminal'

        # filter empty and VISIBLE_NOTHING lines.
        def _condition(line):
            if not line:                                               return False
            elif all(x.tolerance_id == VISIBLE_NOTHING for x in line): return False
            else:                                                      return True

        subject_line_list = tuple(line for line in self.line_list if _condition(line))
        if len(nominal.line_list) < len(subject_line_list): 
            # 'nominal_line_list' will only shrink. 
            # if it is already longer => impossible match.
            return E_Verdict.DIFFERENT, analogy_db

        nominal_line_list = tuple(line for line in nominal.line_list if _condition(line))
        if len(nominal_line_list) != len(subject_line_list): 
            # filtered list are not of same size => impossible match
            return E_Verdict.DIFFERENT, analogy_db

        else:
            return self._is_equivalent(subject_line_list, nominal_line_list, analogy_db)

    def associate(self, nominal, analogy_db):
        """RETURNS: [0] list of 'LinePair'-s
                    [1] required analogy_db

        Each 'LinePair' informs about what two lines are to be displayed
        side-by-side to clarify the comparison process and its verdicts. A line
        may be associated with 'None', meaning that there is no line one the
        other side of the display. 'LinePair' objects also report about
        the development of the analogy database.
        """
        assert self.__class__ == nominal.__class__
        return self._associate_lines(nominal, analogy_db)

    @abstractmethod
    def type(self): pass

    @abstractmethod
    def _associate_lines(self, nominal, analogy_db): pass


class InputChunkTerminal(InputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self, line_n):
        InputChunk.__init__(self, line_n, line_n+1,
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
        InputChunk.__init__(self, None, None, [Line.from_nothing()], config=None)
    def type(self):                                  return E_Chunk.EMPTY
    def _is_equivalent(self, other, analogy_db):           assert False
    def _associate_lines(self, nominal, analogy_db): return [], AnalogyDb()
    def __repr__(self):                              return "InputChunkEmpty"
