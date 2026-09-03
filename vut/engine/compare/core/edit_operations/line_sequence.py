"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________
PURPOSE: Determine edit operations to transform a subject 'LineSequence' into
         a nominal 'LineSequence'.

The transformation is expressed as a sequence of 'edit operations' on line
sequences, namely:

               GOOD, SUBSTITUTE, DELETE, and INSERT.

Notably, no 'TRANSPOSE' operation is provided since for 'LineSequence' the
sequences of lines is invariant.

ALGORITHM:

The underlying algorithm is analogous to the algorithm for finding edit
operations on 'Line's (see edit_operations/line.py) and strings (see
Levenshtein Distance).
_______________________________________________________________________________
"""
from   vut.engine.compare.core.edit_operations.edit  import (E_EditId, 
                                                                           Edit, 
                                                                           EditSequence, 
                                                                           list_EditGOOD_line_sequence, 
                                                                           list_EditGOOD_line)
from   vut.engine.compare.core.edit_operations.core  import (WorkListBase, 
                                                                           WorkItemBase, 
                                                                           position_increment_db)
from   vut.engine.compare.core.edit_operations.separator_adaptor import SeparatorAdaptor
from   vut.engine.compare.contract.semantics         import line_cost_db as cost_db
from   vut.engine.compare.contract.frozen_analogy_db import FrozenAnalogyDb
from   vut.engine.compare.reading.pattern_finder     import E_ToleranceId

from  typeguard   import typechecked

# Shortcuts:
GOOD            = E_EditId.GOOD
GOOD_TOLERATED  = E_EditId.GOOD_TOLERATED
GOOD_INSERT     = E_EditId.GOOD_INSERT
GOOD_DELETE     = E_EditId.GOOD_DELETE
DELETE          = E_EditId.DELETE
INSERT          = E_EditId.INSERT
SUBSTITUTE      = E_EditId.SUBSTITUTE     


cost_GOOD          = cost_db[GOOD]
cost_SUBSTITUTION  = cost_db[SUBSTITUTE]
cost_INSERT_DELETE = cost_db[INSERT]

@typechecked
def do(subject_match_seq_list, 
       nominal_match_seq_list, 
       analogy_db:  FrozenAnalogyDb = FrozenAnalogyDb()) -> EditSequence:
    """RETURNS: EditSequence

    NOTE: The empty 'FrozenAnalogyDb()' is a global immutable singleton.

    Determine how the sequence of subject 'Line' objects can be transformed
    into the sequence of nominal 'Line' objects. It determines a 'cost' value
    and a sequence of edit operations. The tuples indicate the operation, i.e.
    INSERT, DELETE, or SUBSTITUTE. In case of the SUBSTITUTE operation, a list
    of editions (see edit_operations/line.py) is provided that tells how the
    subject line is transformed into the nominal line.
    """

    separator_db = LineSequenceSeparatorAdaptor(subject_match_seq_list,
                                                nominal_match_seq_list,
                                                cost_db[SUBSTITUTE],
                                                cost_db[INSERT],
                                                Edit)

    if separator_db and separator_db.original_max_cost == 0.0:
        best = EditSequence(0, list_EditGOOD_line_sequence(subject_match_seq_list, nominal_match_seq_list), 
                            analogy_db)
    else:
        initial_edit_sequence = EditSequence(0, [], analogy_db)

        subject_le_seq, \
        nominal_le_seq  = separator_db.strip_separators()
        initial_item    = WorkItem(0, 0, edit_list=initial_edit_sequence)
        work_list       = WorkList(subject_le_seq, nominal_le_seq, 
                                   initial_item)
        best            = work_list.run()

    return best.prepare_as_best(separator_db, relative_f=False)

class LineSequenceSeparatorAdaptor(SeparatorAdaptor):
    _pair_db = {
        (DELETE, INSERT):       SUBSTITUTE,
        (INSERT, DELETE):       SUBSTITUTE,
        (GOOD_DELETE, INSERT):  SUBSTITUTE,
        (INSERT, GOOD_DELETE):  SUBSTITUTE,
        (DELETE, GOOD_INSERT):  SUBSTITUTE,
        (GOOD_INSERT, DELETE):  SUBSTITUTE
    }
    def _is_separator(self, line):
        """RETURN: True, if 'line' is considered a separator.
                   False, else.

        A separator is an element that matches a pattern which is equivalent
        whenever it occurs, i.e. comparison delivers 'True' with any other
        seperator. It can be taken out of the sequence and re-inserted.

        Delegates to 'Line.is_visible_nothing' -- THE shared definition of
        whole-line skippability (the Judge's pipe skips the same lines).
        """
        return line.is_visible_nothing()

    def _insert_Edit(self, ni):
        if all(x.tolerance_id == E_ToleranceId.VISIBLE_NOTHING for x in self.nominal_sequence[ni]):
            return self.Edit(GOOD_INSERT, None)
        else:
            return self.Edit(INSERT, None)

    def _delete_Edit(self, si):
        if all(x.tolerance_id == E_ToleranceId.VISIBLE_NOTHING for x in self.subject_sequence[si]):
            return self.Edit(GOOD_DELETE, None, cost=cost_INSERT_DELETE)
        else:
            return self.Edit(DELETE, None, cost=cost_INSERT_DELETE)

    def _good_Edit(self, line_a, line_b):
        """RETURNS: The appropriate 'Edit' object for the pair of 'line_a', and 'line_a'.

        Assuming that line_a, and line_a are equivalent, the return value provides
        the according 'Edit' object, i.e. GOOD or GOOD_TOLERATED.
        """
        edit_list = list_EditGOOD_line(line_a.sequence, line_b.sequence)
        if any(edit.id == GOOD_TOLERATED for edit in edit_list):
            return Edit(GOOD_TOLERATED, edit_list)
        else:
            return Edit(GOOD, edit_list)



class WorkList(WorkListBase):
    def __init__(self, subject, nominal, initial_item):
        WorkListBase.__init__(self, subject, nominal, initial_item, cost_db, SUBSTITUTE)
        self.cache = Cache()

    def _append_subject_overhead(self, item):
        # delete all remaining subjects to conform the nominal
        L          = self.subject_length - item.si
        overhead   = [ Edit(DELETE, cost=cost_INSERT_DELETE) ] * L
        extra_cost = L * cost_INSERT_DELETE
        return self._append_overhead(item, overhead, extra_cost)

    def _append_nominal_overhead(self, item):
        # insert all nominals into subject to conform nominal
        L          = self.nominal_length - item.ni
        overhead   = [ Edit(INSERT, cost=cost_INSERT_DELETE) ] * L
        extra_cost = L * cost_INSERT_DELETE
        return self._append_overhead(item, overhead, extra_cost)

class WorkItemHistory:
    """A 'WorkItemHistory' keeps track of the preceeding edit operations in
    order to determine cost. INSERT and DELETE operations become cheaper when
    they appear in a row. SUBSTITUTE operations of the same pattern, also,
    become cheaper if the appear in a row.

    The main function '.note()' determines the cost of a current edit operation
    given the history of preceding operations.
    """
    def __init__(self, substitute_n=0, insert_n=0, delete_n=0, substitute_editions=None):
       self.substitute_editions = None
       self.substitute_n        = 0
       self.insert_n            = 0
       self.delete_n            = 0

    def clone(self):
        return WorkItemHistory(self.substitute_n, self.insert_n, self.delete_n, self.substitute_editions)

    def note(self, edit_id, editions, relative_edit_distance):
        """RETURNS: Cost of edition in context of history.

        Adapts history of adjacent substutios, insertions, and deletions.
        Editions of the same kind appear in adjacent blocks, they are cheaper.
        They are not so 'bad', because in their context they are consistent.
        """
        if edit_id == GOOD:
            self.substitute_n  = 0
            self.insert_n      = 0
            self.delete_n      = 0
            # value of GOOD decreases with number of corrections preceeding it.
            return cost_GOOD
        elif edit_id == SUBSTITUTE:
            if editions != self.substitute_editions:
                self.substitute_editions = editions
                self.substitute_n        = 0
            self.substitute_n += 1
            self.insert_n      = 0
            self.delete_n      = 0
            # cost of SUBSTITUTE decreases with same substitution patterns preceeding
            return relative_edit_distance / self.substitute_n
        elif edit_id == INSERT:
            self.substitute_n  = 0
            self.insert_n     += 1
            self.delete_n      = 0
            # cost of DELETE decreases with number of preceeding deletions number
            return cost_INSERT_DELETE / self.insert_n
        elif edit_id == DELETE:
            self.substitute_n  = 0
            self.insert_n      = 0
            self.delete_n     += 1
            # cost of INSERT decreases with number of preceeding deletions number
            return cost_INSERT_DELETE / self.delete_n
        else:
            raise AssertionError("")

class WorkItem(WorkItemBase):
   def __init__(self, si, ni, edit_list, history=None):
       WorkItemBase.__init__(self, si, ni, edit_list)
       if history is None: self.history = WorkItemHistory()
       else:               self.history = history

   def __repr__(self):
       return "[%i:%i] cost: %f; %s; " % (self.si, self.ni, self.edit_list.cost, 
                                          [x[0].name for x in self.edit_list.edit_list])

   def subsequent_steps(self, subject_list, nominal_list, cache):
       """YIELDS: 'WorkItems' based on possible edit operations applied on 'self'.
       """
       line_editions = cache.get(self.si, self.ni, subject_list, nominal_list)

       if not line_editions.analogy_db.is_all_consistent(self.edit_list.analogy_db):
           # If there is a clash in analogy considerations, the comparison must be 
           # redone, such that edit operations adapt.
           line_editions = subject_list[self.si].edit_operations(nominal_list[self.ni], 
                                                                 self.edit_list.analogy_db)

       assert isinstance(line_editions, EditSequence)

       # IMPORTANT: Worklist is a LIFO. That is, what comes last is popped
       # first from the worklist. It is essential that 'cheap' steps are
       # treated first, so that more expensive paths can be cut as early as
       # possible.
       # NOTE: Concatinating INSERT-DELETE or DELETE-INSERT does not make sense!
       #       They are equivalent to 'SUBSTITUTE'.
       if self.edit_list.last() != DELETE:
           yield self._step(INSERT)

       if self.edit_list.last() != INSERT:
           yield self._step(DELETE)

       if line_editions.cost == 0.0:
           yield self._step(GOOD,
                            edit_list      = line_editions.edit_list,
                            new_analogy_db = line_editions.analogy_db)
       else:
           yield self._step(SUBSTITUTE,
                            relative_edit_distance = line_editions.cost,
                            edit_list              = line_editions.edit_list)

   def _step(self, edit_id, relative_edit_distance=None, new_analogy_db=None, edit_list=None):
       """RETURNS: WorkItem derived from self after applying an edit operation.

       Given an edit operation 'edit_id' this function generates a modified
       version of 'self'. It adapts the indices 'si' and 'ni' according to
       the position progress related to the operation. The new 'WorkItem'
       will contain a new updated 'edit_list'.
       """
       increment_si, increment_ni = position_increment_db[edit_id]

       delta_cost = self.history.note(edit_id, edit_list, relative_edit_distance)

       if new_analogy_db is not None:
           new_analogy_db = self.edit_list.analogy_db.clone().update(new_analogy_db)
       else:
           new_analogy_db = self.edit_list.analogy_db

       new_editions = EditSequence(self.edit_list.cost + delta_cost,
                                   self.edit_list.edit_list + [ Edit(edit_id, edit_list, cost=delta_cost) ],
                                   new_analogy_db)

       return WorkItem(self.si + increment_si,
                       self.ni + increment_ni,
                       new_editions,
                       self.history.clone())

   def min_cost_remaining(self, subject_length, nominal_length):
       """RETURNS: The lowest possible total cost of the remaining comparisons.

       The lowest possible cost is associated with the case that the maximum
       number of lines can be paired as 'GOOD' and the rest needs to be
       inserted/deleted.
       """
       common_n, remaining_n = self.__get_common_and_remaining(subject_length, nominal_length)

       # best case: -- all common lines are GOOD
       #            -- all remaining lines are INSERT/DELETE
       return self.edit_list.cost + cost_GOOD * common_n + cost_INSERT_DELETE * remaining_n

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
    def get(self, subject_i, nominal_i, subject_list, nominal_list):
        """RETURNS: edit operations to transform subject line into the nominal line
                    (including required analogy db)
        """
        key    = (subject_i, nominal_i)
        result = dict.get(self, key)
        if result is None:
            subject   = subject_list[subject_i]
            nominal   = nominal_list[nominal_i]
            result    = subject.edit_operations(nominal, None)
            self[key] = result
        return result

