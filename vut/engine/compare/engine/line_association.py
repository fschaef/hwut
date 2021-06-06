"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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
from   vut.engine.compare.engine.line          import Line
from   vut.engine.compare.engine.analogy_db    import AnalogyDb
import vut.engine.compare.edit_operations.line as     edit_operations_line
from   vut.engine.quex.typed                   import typed
import sys

class LineAssociation:
    """An association of a line from the subject input stream and a line
    from the nominal input stream.
    """
    @typed(subject=(None, Line), nominal=(None, Line), analogy_db=(None, AnalogyDb))
    def __init__(self, subject, nominal, edit_list=tuple()):
        assert edit_list is None or all(isinstance(x, edit_operations_line.Edit) for x in edit_list)
        self.edit_list   = edit_list
        self.subject = subject
        self.nominal = nominal

    @staticmethod
    def empty(initial_subject):
        return LineAssociation(subject = initial_subject,
                               nominal = None)

    def is_empty(self):
        return self.nominal is None

    def __lt__(self, other): # pragma no cover
        def adapt(mseq):
            if mseq is None: return sys.float_info.max
            else:            return mseq.line_n

        return adapt(self.subject) < adapt(other.subject)

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineAssociation", [
            ("subject",    self.subject),
            ("nominal",    self.nominal),
            ("edit_list",  edit_operations_line.Edit_list_description(self.edit_list)),
        ]
