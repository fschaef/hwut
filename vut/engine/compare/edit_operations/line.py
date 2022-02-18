"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: VUT
_______________________________________________________________________________

PURPOSE: Determining the edit operations to transform a subject 'Line'
         into the nominal 'Line'.

The transformation is expressed as a sequence of 'edit operations' on line
elements, namely:

    GOOD, SUBSTITUTE_TYPE, SUBSTITUTE, TRANSPOSE, DELETE, and INSERT.

A line element, i.e. a 'LineElement' object is an identified pattern such as
a number or an analogy. It is the result of the lexical analysis process
in './tolerance/pattern_finder.py'.

ALGORITHM:

Subject and nominal lines are represented by a sequence of 'LineElement' objects.
The algorithm walks along the two sequences with two indices 'si' and 'ni'
pointing to the 'LineElement' objects under comparison.

Example: Let the subject and nominal sequences of 'LineElement' objects be
represented by the sequences 'a h b e r' and 'a b e r'.

                           si
                           |
               subject:  a h b e r

               nominal:  a b e r
                           |
                           ni

At a given positions (si, ni), there are the following three possibilities to
proceed.

 position      edit             effect in the example above
 change        operation
---------------------------------------------------------------------------
 (si++, ni++)  SUBSTITUTE_TYPE  type of 'b' does not fit type of 'h'
               SUBSTITUTE       'b != h'. step to next two chars
               GOOD             step to next two chars
                                (assume 'b' and 'h' are equivalent)
               TRANSPOSE        switch 'h' and 'b' in nominal, then step
                                to next two chars
 (si++, ni)    DELETE           do as if 'h' was not there.
                                next compare 'b' with 'b'.
 (si,   ni++)  INSERT           do as if 'b' is inserted into subject.
                                next compare 'h' with 'e'.

Each *step* advances further to the end of the sequence. Let each step
type be associated with a specific cost. Now, the task of finding a set
of edit operations can be defined as:

   Find the sequence of *steps* that reaches the end of both sequences
   with a minimum accumulated cost.

The result is the optimal sequence of edit operations required to transform the
subject into the nominal.
_______________________________________________________________________________
"""
from  vut.engine.compare.edit_operations.edit              import E_EditId, Edit, EditSequence, list_EditGOOD_line
from  vut.engine.compare.edit_operations.core              import WorkListBase, \
                                                                  WorkItemBase, \
                                                                  position_increment_db, \
                                                                  max_cost
from  vut.engine.compare.edit_operations.separator_adaptor import SeparatorAdaptor
from  vut.engine.compare.tolerance.pattern_finder          import E_ToleranceId
from  vut.engine.compare.engine.analogy_db                 import AnalogyDb
from  vut.engine.compare.engine.core                       import E_Verdict
from  vut.external.quex.typed                              import typed

from  copy        import copy
from  enum        import IntEnum
from  collections import namedtuple, defaultdict
from  functools   import lru_cache

@lru_cache(maxsize=65536)
@typed(subject_le_seq=tuple, nominal_le_seq=tuple)
def do(subject_le_seq, nominal_le_seq, analogy_db=None):
    """RETURNS: EditSequence

    Compares the line elements of 'subject_le_seq' and 'nominal_le_seq' and
    determines the editions required to transform the former into the latter.

    where EditSequence.cost       = cost / max. cost; thus in range of [0...1].
          EditSequence.edit_list  = list of 'Edit'
          EditSequence.analogy_db = 'AnalogyDb' required for equivalences to hold.
    """
    if analogy_db is None:
        analogy_db = AnalogyDb()

    separator_db = LineSeparatorAdaptor(subject_le_seq, nominal_le_seq,
                                        cost_db[SUBSTITUTE_TYPE],
                                        cost_db[INSERT],
                                        Edit)


    if separator_db and separator_db.original_max_cost == 0.0:
        best = EditSequence(0, list_EditGOOD_line(subject_le_seq, nominal_le_seq), 
                            analogy_db)
    else:
        initial_edit_sequence = EditSequence(0, [], analogy_db)
        subject_le_seq,  \
        nominal_le_seq   = separator_db.strip_separators()
        initial_item     = WorkItem(0, 0, initial_edit_sequence)
        best             = WorkList(subject_le_seq, 
                                    nominal_le_seq, 
                                    initial_item).run()

    return best.prepare_as_best(separator_db, True)


# Shortcuts:
TRANSPOSE       = E_EditId.TRANSPOSE
GOOD            = E_EditId.GOOD
GOOD_TOLERATED  = E_EditId.GOOD_TOLERATED
GOOD_INSERT     = E_EditId.GOOD_INSERT
GOOD_DELETE     = E_EditId.GOOD_DELETE
DELETE          = E_EditId.DELETE
INSERT          = E_EditId.INSERT
NONE            = E_EditId.NONE
SUBSTITUTE      = E_EditId.SUBSTITUTE     
SUBSTITUTE_TYPE = E_EditId.SUBSTITUTE_TYPE

ANALOGY         = E_ToleranceId.ANALOGY
SEPERATOR       = E_ToleranceId.SEPERATOR
VISIBLE_NOTHING = E_ToleranceId.VISIBLE_NOTHING


class LineSeparatorAdaptor(SeparatorAdaptor):
    _pair_db = {
        (DELETE, INSERT): SUBSTITUTE_TYPE,
        (INSERT, DELETE): SUBSTITUTE_TYPE
    }
    def _is_separator(self, le):
        """RETURNS: True, if 'x' is a separator.
                    False, else.
        """
        return le.tolerance_id == SEPERATOR

    def _good_Edit(self, le_a, le_b):
        """RETURNS: The appropriate 'Edit' object for the pair of 'le_a', and 'le_b'.

        Assuming that le_a, and le_b are equivalent, the return value provides
        the according 'Edit' object, i.e. GOOD or GOOD_TOLERATED.
        """
        if le_a.string == le_b.string:
            return self.Edit(GOOD, None)            # both equal separators
        else:
            return self.Edit(GOOD_TOLERATED, None)  # separators are similar


cost_db = {
    GOOD:             0,       # good
    GOOD_TOLERATED:   0,       # good, tolerated is bettern than good insert + delete delete
    GOOD_INSERT:      1e-10,   # good insert visible nothing (slightly worse than 'good')
    GOOD_DELETE:      1e-10,   # good delete visible nothing (slightly worse than 'good')
    TRANSPOSE:        0.5,     # good, when swapped elements
    SUBSTITUTE:       1,       # good, when content is substituted
    INSERT:           1,       # bad, need to insert element
    DELETE:           1,       # bad, need to remove element
    SUBSTITUTE_TYPE:  1        # bad, need to substitute type and content of element
}

cost_INSERT_DELETE = cost_db[INSERT]

class WorkList(WorkListBase):
    def __init__(self, subject, nominal, initial_item):
        WorkListBase.__init__(self, subject, nominal, initial_item, cost_db, SUBSTITUTE_TYPE)
        self.cache = Cache()

    def _append_subject_overhead(self, item):
        visible_list   = [
            self.subject[si].tolerance_id != VISIBLE_NOTHING 
            for si in range(item.si, self.subject_length)
        ]
        extra_cost = sum(visible_list) * cost_INSERT_DELETE
        overhead   = [ 
            Edit(DELETE, None) if visible else Edit(GOOD_DELETE, None)
            for visible in visible_list
        ] 
        return self._append_overhead(item, overhead, extra_cost)

    def _append_nominal_overhead(self, item):
        visible_list   = [
            self.nominal[ni].tolerance_id != VISIBLE_NOTHING 
            for ni in range(item.ni, self.nominal_length)
        ]
        extra_cost = sum(visible_list) * cost_INSERT_DELETE
        overhead   = [ 
            Edit(INSERT, None) if visible else Edit(GOOD_INSERT, None)
            for visible in visible_list
        ] 
        return self._append_overhead(item, overhead, extra_cost)

class WorkItem(WorkListBase):
    """A 'WorkItem' corresponds to a node for the tree search algorithm
    that searches the least costly path to the end of the 'LineElement'
    sequence objects.

    It maintains:

        * Position pair (si, ni) which is investigated.

    Also, it maintains implications of previous steps:

        * list of previous edit operations.

        * subject as it might have changed due to transposition.

        * analogy required to hold for all past edit operations.

    The function '.subsequent_steps()' determines possible steps from the
    position denoted by 'self'. It does so by yielding 'WorkItem' objects
    for subsequence positions.
    """
    def __init__(self, si, ni, editions, subject_modified=None):
        WorkItemBase.__init__(self, si, ni, editions)
        self.subject_modified = subject_modified # in case of 'transpose' edits.

    def subsequent_steps(self, subject, nominal, cache):
        """YIELDS: 'WorkItems' based on possible edit operations applied on 'self'.
        """
        if self.subject_modified: subject = self.subject_modified

        verdict_id, analogy = cache.get(self.si, self.ni, 
                                        subject, nominal, 
                                        transpose_f = self.subject_modified is not None)

        subject_le = subject[self.si]
        nominal_le = nominal[self.ni]

        # IMPORTANT: Worklist is a LIFO (last in, first out).
        #
        # For performance, it is essential that 'cheap' steps are treated first.
        # => more expensive paths are cut early.
        good_id = None
        if   verdict_id == E_Verdict.MISFIT:
            yield self._step(SUBSTITUTE_TYPE)
        elif verdict_id == E_Verdict.DIFFERENT:
            yield self._step(SUBSTITUTE,
                             cost_factor = subject_le.edit_distance_relative(nominal_le))
        elif verdict_id == E_Verdict.EQUIVALENT_SUBJECT_VISIBLE_NOTHING:
            good_id = GOOD_DELETE
        elif verdict_id == E_Verdict.EQUIVALENT_NOMINAL_VISIBLE_NOTHING:
            good_id = GOOD_INSERT
        elif verdict_id == E_Verdict.EQUIVALENT:
            if not self.edit_list.analogy_db.is_consistent(analogy):
                yield self._step(SUBSTITUTE)
            elif subject_le.string       != nominal_le.string:  
                good_id = GOOD_TOLERATED
            elif subject_le.tolerance_id == ANALOGY: 
                good_id = GOOD_TOLERATED
            else:                                                     
                good_id = GOOD
        else:
            assert False

        if good_id is None:
            yield from (
                self._step(TRANSPOSE, transpose_ai=candidate_ai, subject=subject)
                for candidate_ai in range(self.si+1, len(subject))
                if subject[candidate_ai].is_equivalent(nominal_le, self.edit_list.analogy_db)
            )

        yield self._step(INSERT)
        yield self._step(DELETE)

        if good_id is not None:
            yield self._step(good_id, new_analogy = analogy)

    def _step(self, edit_id, cost_factor=1, transpose_ai=None, new_analogy=None, subject=None):
        """RETURNS: WorkItem derived from self after applying an edit operation.

        Given an edit operation 'edit_id' this function generates a modified
        version of 'self'. It adapts the indices 'si' and 'ni' according to
        the position progress related to the operation. The new 'WorkItem'
        will contain a new 'subject', and 'analogy_db' if they were changed.
        The 'edit_list' of the 'WorkItem' contains all current edit operations
        plus the edit operation 'edit_id' that produced the 'WorkItem'.
        """

        if transpose_ai is not None:
            new_subject = copy(subject) # shallow copy
            new_subject[self.si], new_subject[transpose_ai] = new_subject[transpose_ai], new_subject[self.si]
        else:
            new_subject = self.subject_modified

        if new_analogy is not None:
            new_analogy_db = self.edit_list.analogy_db.clone()
            new_analogy_db.add(new_analogy)
        else:
            new_analogy_db = self.edit_list.analogy_db

        increment_ai, increment_bi = position_increment_db[edit_id]
        return WorkItem(si         = self.si + increment_ai,
                        ni         = self.ni + increment_bi,
                        editions   = EditSequence(self.edit_list.cost + cost_db[edit_id] * cost_factor,
                                                  self.edit_list.edit_list + [ Edit(edit_id, transpose_ai) ],
                                                  new_analogy_db), 
                        subject_modified = new_subject)

    def min_cost_remaining(self, subject_length, nominal_length):
        """RETURNS: The lowest possible total cost of the remaining comparisons.

        The lowest possible cost is associated with the case that the maximum
        number of lines can be paired as 'GOOD' and the rest needs to be
        inserted/deleted.
        """
        common_n, remaining_n = self.__get_common_and_remaining(subject_length, nominal_length)

        # best case: -- all common lines are GOOD
        #            -- all remaining lines are INSERT/DELETE
        return self.edit_list.cost + cost_db[GOOD] * common_n + cost_db[INSERT] * remaining_n


    def __get_common_and_remaining(self, subject_length, nominal_length):
        """RETURNS: [0] number of possibly common elements.
                    [1] number of 'overhanging' elements (remainder).
        """
        remaining_subject_n = subject_length - self.si
        remaining_nominal_n = nominal_length - self.ni
        # let: common_n = maximum number of pairs in the remaining lines.
        common_n    = min(remaining_subject_n, remaining_nominal_n)
        remaining_n = max(remaining_subject_n, remaining_nominal_n) - common_n
        return common_n, remaining_n


class Cache(dict):
    def get(self, subject_i, nominal_i, subject_list, nominal_list, transpose_f):
        """RETURNS: [0] verdict id
                    [1] required analogy
        """
        subject = subject_list[subject_i]
        nominal = nominal_list[nominal_i]

        # Use 'id' of LineElements, rather than their index. Notably the 'transpose'
        # edit operation may switch elements to a different position.
        key    = (id(subject), id(nominal))
        result = dict.get(self, key)
        if result is None:
            result = subject.compare(nominal)
            self[key] = result
        return result

