"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:

Separators are elements of a line which appear (often) between line
elements. Their exact 'shape' is irrelevant. Two patterns matching a 
separator are always equivalent. 

IDEA: Separate the separators from the line element sequence in order
      to reduce the required amount of matching. Later, once the 
      edit list is determined, re-insert the separator related 
      content.

The constructor takes to line element sequences, subject and nominal.
It then strips out the separators, but stores their original position.

strip_separators(): returns the two line element sequences for 
                    subject and nominal where the separators are 
                    stripped.

Now, edit operations are determined based on the 'content' sequences
without any separators.

reinsert_separators(raw_edit_list): produces an edit list that takes
                                    the existence of sperators into
                                    consideration.

"""
from  vut.engine.compare.edit_operations.core     import max_cost, \
                                                         position_increment_db
from  vut.engine.compare.edit_operations.edit     import E_EditId
from  vut.engine.compare.tolerance.pattern_finder import E_ToleranceId

TRANSPOSE       = E_EditId.TRANSPOSE
GOOD            = E_EditId.GOOD
GOOD_TOLERATED  = E_EditId.GOOD_TOLERATED
GOOD_INSERT     = E_EditId.GOOD_INSERT
GOOD_DELETE     = E_EditId.GOOD_DELETE
DELETE          = E_EditId.DELETE
INSERT          = E_EditId.INSERT
NONE            = E_EditId.NONE
SUBSTITUTE_TYPE = E_EditId.SUBSTITUTE_TYPE

SEPERATOR       = E_ToleranceId.SEPERATOR

class SeparatorAdaptor:
    def __init__(self, subject_seq, nominal_seq, 
                 cost_SUBSTITUTION, cost_INSERT_DELETE, 
                 Edit_constructor):
        self.subject_sequence = subject_seq
        self.nominal_sequence = nominal_seq
        subject_flags         = [not self._is_separator(x) for x in subject_seq]
        nominal_flags         = [not self._is_separator(x) for x in nominal_seq]

        # map: index in subject content --> index in original subject sequence
        self.subject_index_map = {}
        k = 0
        for i, content_f in enumerate(subject_flags):
            if not content_f: continue
            self.subject_index_map[k] = i
            k += 1

        length_relevant_subject_seq = sum(subject_flags)
        length_relevant_nominal_seq = sum(nominal_flags)
        self.original_max_cost      = max_cost(length_relevant_subject_seq, 
                                               length_relevant_nominal_seq,
                                               cost_SUBSTITUTION, 
                                               cost_INSERT_DELETE)

        self.Edit = Edit_constructor

    def strip_separators(self):
        return \
            [x for x in self.subject_sequence if not self._is_separator(x)], \
            [x for x in self.nominal_sequence if not self._is_separator(x)]  
                
    def reinsert_separators(self, edit_list_raw):
        """RETURNS: Edit-operations considering separators being present.

        The 'edit_list_raw' has been generated to transform all content elements
        of the subject into equivalent content elements of the nominal All
        separators have been taken out for this purpose. This function re-inserts
        the separators and provides an according list of edit operations based
        on the edit operations derived from the content comparison.
        """
        def iterable(edit_iterable):
            """Ensure, that adjacent 'DELETE' and 'INSERTS' are combined into 
            'SUBSTITUTE_TYPE' operations.  The cases of adjacent 'INSERT/DELETE' 
            operations come from separators being inserted into the list. 
            Separators are always of different type than content => 'SUBSTITUTE_TYPE' 
            is safe to use.
            """
            def _iterable(edit_list):
                """YIELDS: (current, look-ahead, look-ahead-ahead)
                """
                if not edit_list:
                    return
                for i, x in enumerate(edit_iterable[:-1]):
                    yield x, edit_iterable[i+1].id
                yield edit_iterable[-1], NONE
                   
            skip_n = 0
            for current, ahead_id in _iterable(edit_iterable):
                if skip_n: skip_n -= 1; continue

                combined_id = self._pair_db.get((current.id, ahead_id))
                if combined_id is not None:
                    yield self.Edit(combined_id, None) 
                    skip_n = 1
                    continue

                yield current

        return list(iterable(list(self.__reinsert_separators(edit_list_raw))))

    def _insert_Edit(self, ni):
        return self.Edit(INSERT, None)

    def _delete_Edit(self, si):
        return self.Edit(DELETE, None)

    def __reinsert_separators(self, edit_list_raw):
        def _insert_op(ni):
            return self._insert_Edit(ni)

        def _delete_op(si):
            return self._delete_Edit(si)

        def _good_op(si, ni):
            return self._good_Edit(self.subject_sequence[si], self.nominal_sequence[ni])

        def _from_edit_list(ei):
            edit = edit_list_raw[ei]
            if edit.id == TRANSPOSE:
                translated_si = self.subject_index_map[edit.transpose_ai]
                return self.Edit(TRANSPOSE, translated_si)
            else:
                return edit

        Le = len(edit_list_raw)
        Ls = len(self.subject_sequence)
        Ln = len(self.nominal_sequence)
        si = ni = ei = 0

        while si < Ls or ni < Ln:
            if si < Ls: s_is_separator = self._is_separator(self.subject_sequence[si])
            else:       s_is_separator = False
            if ni < Ln: n_is_separator = self._is_separator(self.nominal_sequence[ni])
            else:       n_is_separator = False

            if       s_is_separator and not n_is_separator: edit = _delete_op(si)
            elif not s_is_separator and     n_is_separator: edit = _insert_op(ni)
            elif     s_is_separator and n_is_separator:     edit = _good_op(si, ni)
            else:                                           edit = _from_edit_list(ei); ei += 1

            yield edit
            s_incr, n_incr = position_increment_db[edit.id]
            si += s_incr
            ni += n_incr
        
    _pair_db = {} # must be defined by derived class

    def _is_separator(self, x):
        """RETURNS: True, if 'x' is a separator.
                    False, else.
        """
        return False
        
    def _good_Edit(self, subject, nominal):
        """RETURNS: The appropriate 'Edit' object for the pair of 'subject', and 'nominal'.

        Assuming that subject, and nominal are equivalent, the return value provides
        the according 'Edit' object, i.e. GOOD or GOOD_TOLERATED.
        """
        assert False
