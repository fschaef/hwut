"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Associating a line from the subject stream with a line of the nominal
         stream

These associations are used for display of similar lines. Such associations
are based on the following procedures:

    -- LineSequence: edit_operation/line_sequence.py
    -- Potpourri:    friends_pairing/core.py

Displaying similar lines shall shed some light on HWUT's tolerant comparison
process while inspecting the output of unit tests.
________________________________________________________________________________
"""
from   ut.engine.compare.engine.line          import Line
from   ut.engine.compare.engine.analogy_db    import AnalogyDb
import ut.engine.compare.edit_operations.line as     edit_operations_line
from   ut.engine.quex.typed                   import typed
import sys

class LineAssociation:
    """An association of a line from the subject input stream and a line
    from the nominal input stream.
    """
    @typed(subject_seq=(None, Line), nominal_seq=(None, Line), analogy_db=(None, AnalogyDb))
    def __init__(self, subject_seq, nominal_seq, edit_list=tuple(), analogy_db=None):
        assert edit_list is None or all(isinstance(x, edit_operations_line.Edit) for x in edit_list)
        self.edit_list   = edit_list
        self.subject_seq = subject_seq
        self.nominal_seq = nominal_seq
        self.analogy_db  = analogy_db

    @staticmethod
    def empty(subject_seq):
        return LineAssociation(subject_seq = subject_seq,
                               nominal_seq = None)

    def is_empty(self):
        return self.nominal_seq is None

    def __lt__(self, other): # pragma no cover
        def adapt(mseq):
            if mseq is None: return sys.float_info.max
            else:            return mseq.line_n

        return adapt(self.subject_seq) < adapt(other.subject_seq)

