"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
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
from   ut.engine.compare.engine.core                   import E_Verdict
from   ut.engine.compare.engine.line                   import Line
from   ut.engine.compare.engine.line_association       import LineAssociation
import ut.engine.compare.friends_pairing.max           as     friends_pairing_max
import ut.engine.compare.friends_pairing.exact          as     friends_pairing
import ut.engine.compare.edit_operations.line_sequence as     edit_operations_line_sequence
from   ut.engine.compare.edit_operations.line_sequence import E_EditLineSequence, EditsLineSequence

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

    def type(self):
        return E_Chunk.VOID

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
        """RETURNS: list of 'LineAssociation'-s

        Each 'LineAssociation' informs about what two lines are to be displayed
        side-by-side to clarify the comparison process and its verdicts. A line
        may be associated with 'None', meaning that there is no line one the
        other side of the display. 'LineAssociation' objects also report about
        the development of the analogy database.
        """
        if self.__class__ == nominal.__class__:
            return self._line_associations(nominal, analogy_db)

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
        return result

    @classmethod
    def contrary(cls):
        if cls == LineSequence: return Potpourri
        else:                   return LineSequence

    @abstractmethod
    def _compare(self, other, analogy_db):  pass

    @abstractmethod
    def _line_associations(self, nominal, analogy_db): pass



class LineSequence(InputChunk):
    """Set of lines where the sequence matters.
    """
    def type(self):
        return E_Chunk.LINE_SEQUENCE

    def _compare(self, nominal, analogy_db) -> E_Verdict:
        """RETURNS: [0] True, if 'self' and 'nominal' are equivalent.
                        False, else.
                    [1] AnalogyDb required for the equivalents of [0] to hold.
        """
        for subject_line, nominal_line in zip(self.line_list, nominal.line_list):
            verdict, analogy_db = subject_line.compare(nominal_line, analogy_db)
            if verdict == False:
                return E_Verdict.DIFFERENT, analogy_db
        else:
            return E_Verdict.EQUIVALENT, analogy_db

    def _line_associations(self, nominal, analogy_db):
        """RETURNS: list 'LineAssociation'-s

        See 'InputChunk.line_associations()' for further explanations.
        """
        editions = edit_operations_line_sequence.do(self.line_list,
                                                    nominal.line_list,
                                                    analogy_db)
        assert isinstance(editions, EditsLineSequence)

        if not editions.edit_list:
            return []

        def iterable(edit_line_list):
            si, ni = 0, 0
            for edit_id, edit_list in edit_line_list:
                if   edit_id == E_EditLineSequence.GOOD or edit_id == E_EditLineSequence.SUBSTITUTE:
                    subject_seq = self.line_list[si]
                    nominal_seq = nominal.line_list[ni]
                elif edit_id == E_EditLineSequence.INSERT:
                    subject_seq = None # nominal inserted, no counterpart in subject
                    nominal_seq = nominal.line_list[ni]
                elif edit_id == E_EditLineSequence.DELETE:
                    subject_seq = self.line_list[si]
                    nominal_seq = None # subject inserted, no counterpart in nominal
                else:
                    assert False # pragma: no cover

                yield subject_seq, nominal_seq, edit_list
                s_incr, n_incr = edit_operations_line_sequence.position_increment_db[edit_id]
                si += s_incr
                ni += n_incr

        return [
            LineAssociation(subject_seq, nominal_seq, edit_list, analogy_db)
            for subject_seq, nominal_seq, edit_list in iterable(editions.edit_list)
        ]

    def __repr__(self): # pragma no cover
        return "\n".join("%03i: %s" % (line.line_n, line) for line in self.line_list)


class Potpourri(InputChunk):
    """Set of lines where the sequence does not matter.
    """
    def type(self):
        return E_Chunk.POTPOURRI

    def __init__(self, start_line_n, end_line_n, iterable, config):
        def adapt(iterable, start_line_n, end_line_n):
            yield Line.from_potpourri(start_line_n, begin_f=True)
            yield from iterable
            yield Line.from_potpourri(end_line_n, begin_f=False)
        InputChunk.__init__(self, start_line_n, end_line_n, adapt(iterable, start_line_n, end_line_n), config)

    def _compare(self, nominal, analogy_db):
        """RETURNS: [0] True, if both potpourris are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.
        """
        subject_potpourri = self.line_list[1:-1]    # exclude [0] and [-1]:
        nominal_potpourri = nominal.line_list[1:-1] # first and last line carry Potpourri markers.

        verdict, _, new_analogy_db = friends_pairing.do(subject_potpourri,
                                                        nominal_potpourri,
                                                        analogy_db,
                                                        abort_f=True)

        if verdict: return E_Verdict.EQUIVALENT, new_analogy_db
        else:       return E_Verdict.DIFFERENT, analogy_db

    def _line_associations(self, nominal, analogy_db):
        """RETURNS: list 'LineAssociation'-s

        See 'InputChunk.line_associations()' for further explanations.
        """
        assert len(self.line_list) >= 2 and len(nominal.line_list) >= 2
        subject_potpourri = self.line_list[1:-1]    # exclude [0] and [-1]:
        nominal_potpourri = nominal.line_list[1:-1] # first and last line carry Potpourri markers.

        core_result,   \
        new_analogy_db = friends_pairing_max.do(subject_potpourri,
                                                nominal_potpourri,
                                                analogy_db,
                                                self.configuration.potpourri_max_comparison_count)

        result = [
            LineAssociation(self.line_list[0], nominal.line_list[0], edit_list=[])
        ]
        result.extend(core_result)
        result.append(
            LineAssociation(self.line_list[-1], nominal.line_list[-1], edit_list=[])
        )

        return result

    def __repr__(self): # pragma no cover
        return "\n".join("%03i| %s" % (line.line_n, line) for line in self.line_list)

class InputChunkTerminal(InputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self, line_n):
        InputChunk.__init__(self, line_n, line_n+1,
                            [Line.from_string(line_n, "<end>")],
                            config=None)
    def type(self):                                    return E_Chunk.TERMINAL
    def _compare(self, other, analogy_db):             assert False
    def _line_associations(self, nominal, analogy_db): return []
    def __repr__(self):                                return "InputChunkTerminal"

class InputChunkEmpty(InputChunk):
    """Input chunk that marks the end of an input stream.
    """
    def __init__(self):
        InputChunk.__init__(self, None, None, [Line.from_nothing()], config=None)
    def type(self):                                    return E_Chunk.EMPTY
    def _compare(self, other, analogy_db):             assert False
    def _line_associations(self, nominal, analogy_db): return []
    def __repr__(self):                                return "InputChunkEmpty"
