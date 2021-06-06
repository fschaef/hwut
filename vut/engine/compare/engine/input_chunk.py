"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Interpretations of input as 'LineSequence' and 'Potpourri' chunks.

The 'chunk_pipe' (engine/chunk_pipe.py) interprets an input stream as sequences
of 'InputChunk' objects. The 'InputChunk' defines the interface for the two
derived classes representing the two types of input chunks:

-- LineSequence: set of text lines where the sequence matters.
-- Potpourri:    set of text lines where the sequence does not matter.

The two main functions of an 'InputChunk' are

   .compare()           --> determines whether the chunk is equivalent to
                            another.
   .line_associations() --> determines which lines should be best associated
                            for display.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.core                   import E_Verdict
from   vut.engine.compare.engine.analogy_db             import AnalogyDb
from   vut.engine.compare.engine.line                   import Line
from   vut.engine.compare.engine.line_association       import LineAssociation
from   vut.engine.compare.edit_operations.line_sequence import E_EditLineSequence, EditsLineSequence

from   enum      import Enum
from   abc       import ABC, abstractmethod

class E_Chunk(Enum):
    LINE_SEQUENCE        = 0
    POTPOURRI            = 1
    TERMINAL             = 2
    EMPTY                = 4
    VOID                 = 4711

class InputChunk(ABC):
    """Interface definition for input chunks.

        .compare()           --> compare two InputChunk-s.
        .line_associations() --> determine best line associations for display.

    """
    def __init__(self, start_line_n, end_line_n, iterable, config):
        self.line_list     = tuple(iterable)
        self.start_line_n  = start_line_n
        self.end_line_n    = end_line_n
        self.configuration = config

    def compare(self, nominal, analogy_db) -> E_Verdict:
        """RETURNS: [0] True, if both sequences are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.

        The 'analogy_db' contains analogies imposed from lines which are
        equivalent. If the test fails ([0] == False), the analogy database is
        irrelevant, since the global comparison needs to stop. For display
        (see .line_associations()), this different.
        """
        if self.__class__ != nominal.__class__:
            return E_Verdict.DIFFERENT, analogy_db
        elif self.__class__ == InputChunkTerminal:
            return E_Verdict.EQUIVALENT, analogy_db  # here: both are 'InputChunkTerminal'
        elif len(self.line_list) != len(nominal.line_list):
            return E_Verdict.DIFFERENT, analogy_db
        else:
            return self._compare(nominal, analogy_db)

    def line_associations(self, nominal, analogy_db):
        """RETURNS: [0] list of 'LineAssociation'-s
                    [1] required analogy_db

        Each 'LineAssociation' informs about what two lines are to be displayed
        side-by-side to clarify the comparison process and its verdicts. A line
        may be associated with 'None', meaning that there is no line one the
        other side of the display. 'LineAssociation' objects also report about
        the development of the analogy database.
        """
        if self.__class__ == nominal.__class__:
            result,        \
            new_analogy_db = self._line_associations(nominal, analogy_db)
        else:
            # Comparison of 'LineSequence' and 'Potpourri' is flawed,
            # Show first nominal compared to nothing, then subject compared to nothing.
            result = [
                LineAssociation(None, nominal_seq, edit_list=[])
                for nominal_seq in nominal.line_list
            ]
            result.extend(
                LineAssociation(subject_seq, None, edit_list=[])
                for subject_seq in self.line_list
            )
            new_analogy_db = AnalogyDb()
        return result, new_analogy_db

    @abstractmethod
    def type(self): pass

    @abstractmethod
    def _compare(self, other, analogy_db):  pass

    @abstractmethod
    def _line_associations(self, nominal, analogy_db): pass


class InputChunkTerminal(InputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self, line_n):
        InputChunk.__init__(self, line_n, line_n+1,
                            [Line.from_string(line_n, "<end>")],
                            config=None)
    def type(self):                                    return E_Chunk.TERMINAL
    def _compare(self, other, analogy_db):             assert False
    def _line_associations(self, nominal, analogy_db): return [], AnalogyDb()
    def __repr__(self):                                return "InputChunkTerminal"


class InputChunkEmpty(InputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self):
        InputChunk.__init__(self, None, None, [Line.from_nothing()], config=None)
    def type(self):                                    return E_Chunk.EMPTY
    def _compare(self, other, analogy_db):             assert False
    def _line_associations(self, nominal, analogy_db): return [], AnalogyDb()
    def __repr__(self):                                return "InputChunkEmpty"
