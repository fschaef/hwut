"""SPDX License: MIT; (C) Frank-Rene Schäfer; Project: hwut
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
from  vut.engine.compare.edit_operations.edit  import E_EditId, Edit, EditSequence 
from   vut.engine.compare.edit_operations.core import WorkListBase, \
                                                      WorkItemBase, \
                                                      position_increment_db, \
                                                      max_cost
from   vut.engine.compare.engine.analogy_db    import AnalogyDb
from   vut.external.quex.typed                 import typed

from   enum        import IntEnum
from   collections import defaultdict
import sys


class WorkList(WorkListBase):
    def _adapt_initialization(self):
        self.min_cost = self[0].min_cost_remaining(self.subject_length, self.nominal_length)
        self.max_cost = max_cost(self.subject_length, self.nominal_length,
                                 cost_SUBSTITUTION, cost_INSERT_DELETE) + 1e-6

        self.best = EditSequence(cost=self.max_cost, edit_list=[], analogy_db=[])
        self.cost_insert_delete = cost_INSERT_DELETE

        self.cache = Cache()

    def _set_best(self, item):
        self.best = item.edit_list

    def _append_subject_overhead(self, item):
        # delete all remaining subjects to conform the nominal
        L          = self.subject_length - item.si
        overhead   = [(E_EditId.DELETE, None) ] * L
        extra_cost = L * self.cost_insert_delete
        return self._append_overhead(item, overhead, extra_cost)

    def _append_nominal_overhead(self, item):
        # insert all nominals into subject to conform nominal
        L          = self.nominal_length - item.ni
        overhead   = [(E_EditId.INSERT, None) ] * L
        extra_cost = L * self.cost_insert_delete 
        return self._append_overhead(item, overhead, extra_cost)


def do(subject_match_seq_list, nominal_match_seq_list, analogy_db=None):
    """RETURNS: EditSequence

    Determine how the sequence of subject 'Line' objects can be transformed
    into the sequence of nominal 'Line' objects. It determines a 'cost' value
    and a sequence of edit operations. The tuples indicate the operation, i.e.
    INSERT, DELETE, or SUBSTITUTE. In case of the SUBSTITUTE operation, a list
    of editions (see edit_operations/line.py) is provided that tells how the
    subject line is transformed into the nominal line.
    """
    if analogy_db is None: analogy_db = AnalogyDb()

    initial_editions = EditSequence(0, [], analogy_db)
    initial_item     = WorkItem(0, 0, editions=initial_editions)
    work_list        = WorkList(subject_match_seq_list, nominal_match_seq_list, 
                                initial_item)

    if work_list.max_cost == 0.0:
        return initial_editions
    else:
        return work_list.run()

cost_GOOD          = 0.0
cost_SUBSTITUTION  = 1.0
cost_INSERT_DELETE = 0.5 

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
        if edit_id == E_EditId.GOOD:
            self.substitute_n  = 0
            self.insert_n      = 0
            self.delete_n      = 0
            # value of GOOD decreases with number of corrections preceeding it.
            return cost_GOOD
        elif edit_id == E_EditId.SUBSTITUTE:
            if editions != self.substitute_editions:
                self.substitute_editions = editions
                self.substitute_n        = 0
            self.substitute_n += 1
            self.insert_n      = 0
            self.delete_n      = 0
            # cost of SUBSTITUTE decreases with same substitution patterns preceeding
            return relative_edit_distance / self.substitute_n
        elif edit_id == E_EditId.INSERT:
            self.substitute_n  = 0
            self.insert_n     += 1
            self.delete_n      = 0
            # cost of DELETE decreases with number of preceeding deletions number
            return cost_INSERT_DELETE / self.insert_n
        elif edit_id == E_EditId.DELETE:
            self.substitute_n  = 0
            self.insert_n      = 0
            self.delete_n     += 1
            # cost of INSERT decreases with number of preceeding deletions number
            return cost_INSERT_DELETE / self.delete_n
        else:
            assert False # pragma no cover

class WorkItem(WorkItemBase):
   def __init__(self, si, ni, editions, history=None):
       WorkItemBase.__init__(self, si, ni)
       self.edit_list = editions
       if history is None: self.history = WorkItemHistory()
       else:               self.history = history

   def __repr__(self):
       return "[%i:%i] cost: %f; %s; " % (self.si, self.ni, self.cost, [x[0].name for x in self.edit_list.edit_list])

   @property
   def cost(self):
       return self.edit_list.cost

   @cost.setter
   def cost(self, value):
       self.edit_list.cost = value

   def subsequent_steps(self, subject_list, nominal_list, cache):
       """YIELDS: 'WorkItems' based on possible edit operations applied on 'self'.
       """
       line_editions = cache.get(self.si, self.ni, subject_list, nominal_list, self.edit_list.analogy_db)
       assert isinstance(line_editions, EditSequence)

       # IMPORTANT: Worklist is a LIFO. That is, what comes last is popped
       # first from the worklist. It is essential that 'cheap' steps are
       # treated first, so that more expensive paths can be cut as early as
       # possible.
       # NOTE: Subsequent INSERT-DELETE or DELETE-INSERT do not make sense!
       #       They are equivalent to 'SUBSTITUTE'.
       if self.edit_list.last() != E_EditId.DELETE:
           yield self._step(E_EditId.INSERT)
       if self.edit_list.last() != E_EditId.INSERT:
           yield self._step(E_EditId.DELETE)

       if line_editions.cost == 0.0:
           yield self._step(E_EditId.GOOD,
                            edit_list      = line_editions.edit_list,
                            new_analogy_db = line_editions.analogy_db)
       else:
           yield self._step(E_EditId.SUBSTITUTE,
                            relative_edit_distance = line_editions.cost,
                            edit_list              = line_editions.edit_list)

   @typed(edit_id=E_EditId, edit_list=[Edit])
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

       new_editions = EditSequence(self.cost + delta_cost,
                               self.edit_list.edit_list + [ (edit_id, edit_list) ],
                               new_analogy_db)

       result = WorkItem(self.si + increment_si,
                         self.ni + increment_ni,
                         new_editions,
                         self.history.clone())
       return result

   def min_cost_remaining(self, subject_length, nominal_length):
       """RETURNS: The lowest possible total cost of the remaining comparisons.

       The lowest possible cost is associated with the case that the maximum
       number of lines can be paired as 'GOOD' and the rest needs to be
       inserted/deleted.
       """
       common_n, remaining_n = self.__get_common_and_remaining(subject_length, nominal_length)

       # best case: -- all common lines are GOOD
       #            -- all remaining lines are INSERT/DELETE
       return self.cost + cost_GOOD * common_n + cost_INSERT_DELETE * remaining_n

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
    def get(self, subject_i, nominal_i, subject_list, nominal_list, analogy_db):
        """RETURNS: Edit operations to transform subject line into the nominal line
        """
        pair = (subject_i, nominal_i)
        result = dict.get(self, pair)

        if result is not None:
            line_editions, used_analogy_db = result
            if used_analogy_db.is_all_consistent(analogy_db):
                return line_editions

        subject = subject_list[subject_i]
        nominal = nominal_list[nominal_i]

        line_editions = subject.edit_operations(nominal, analogy_db)
        self[pair]    = line_editions, analogy_db
        return line_editions

