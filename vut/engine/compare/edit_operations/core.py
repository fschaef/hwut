"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: VUT
_______________________________________________________________________________

PURPOSE: Classes and algorithms for finding edit sequences.

An 'edit sequence' is a sequence of edit operations applied to a subject
sequence such that it is transformed into a nominal sequence. An edit operation
consists of a change operation (GOOD, INSERT, DELETE, ...) and an according
increment of the pointers into the subject list and the nominal lists.

ALGORITHM:

The algorithm is explained in 'line.py' of this directory. It is basically
the same for both, lines and line sequences. This module provides the 
base required base classes. Both, 'line.py' and 'line_sequence.py' implement
derived classes of:


  WorkItemBase:
      
     Maintains the indices 'si' and 'ni' pointing to positions in the
     subject and the nominal sequence. An 'edit_list' documents the
     edit operations how this position has been reached. 

  WorkListBase: 
   
     A container that maintains the list of 'WorkItems'. It takes work items,
     one by one, and derived further work items derived from them. A step
     considers of finding a list of possible operations given the current
     positions (si, ni). For each possible operation, the current edit sequence
     is extended by one and it builds a new work item.

Eventually, a work item is derived which reaches the end of one or both
sequences.  If its according 'edit_list' is less costy than the best, the best
is adapted.  This continues until no work item remains on the list.

OPTIMIZATION:

Caches store comparisons of elements in subject and nominal. More likely to win
edit operations are added first. WorkItem's with no chance of winning are cut
of early.

_______________________________________________________________________________
"""

from   vut.engine.compare.edit_operations.edit  import E_EditId, EditSequence

from   collections import defaultdict
from   abc         import ABC, abstractmethod

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


position_increment_db = {
    #                 si-increment  ni-increment
    GOOD:             (1,           1),    # Step over subject[si], nominal[ni]
    GOOD_TOLERATED:   (1,           1),    #          -- " --
    GOOD_INSERT:      (0,           1),    # Consider 'subject[si]' visible nothing as insertion.
    GOOD_DELETE:      (1,           0),    # Consider 'nominal[ni]' visible nothing as insertion.
    TRANSPOSE:        (1,           1),    #          -- " --
    INSERT:           (0,           1),    # Consider 'subject[si]' as insertion.
    #                                      # => compare subject[si+1] with nominal[ni]
    DELETE:           (1,           0),    # Consider 'nominal[ni]' as insertion.
    #                                      # => compare subject[si] with nominal[ni+1]
    SUBSTITUTE:       (1,           1),    # Step over subject[si], nominal[ni]
    SUBSTITUTE_TYPE:  (1,           1),    #          -- " --
}

class WorkItemBase(ABC):
    """WorkItem used in the 'WorkListBase'. It contains indices into the subject
    and the nominal list. The functions required are mentioned here as an abstract
    methed.
    """
    def __init__(self, si, ni, edit_sequence):
        self.si        = si
        self.ni        = ni
        self.edit_list = edit_sequence

    @abstractmethod
    def subsequent_steps(self, subject, nominal, cache): 
        """YIELDS: WorkItemBase objects

        This function yields subsequence positions (si, ni) based on the current
        position and application of edit operations.
        """
        return

    @abstractmethod
    def min_cost_remaining(self, subject_length, nominal_length): 
        """RETURNS: Minimal cost that can be achieved starting from the given 
                    position.
        """
        return

class WorkListBase(list):
    """Implements a work list finding optimate edit operations to transform a
    subject sequence into a nominal sequence. The work list is applied to both,
    lists of LineElement-s and lists of Line-s.

    This class does some optimizations in order to filter out hopeless paths.
    Work items are not followed if:

    -- The estimated best cost of a work item is less than the best cost which
       has been already achieved.

    -- The already accumulated cost of a position (si, ni) is higher than what
       has been achieved now. Thus, it can never be better than the previous one.

    -- When a new best value is achieved all entries which a minimum expected
       cost higher than that are removed from the work list.

    The work list terminates the loop by being empty. This may be due to
    exhaustion (all work items treated), or by 'clearing' when it is impossible
    to achieve a better result.
    """
    def __init__(self, subject, nominal, initial_item, cost_db, substitute_op_worst):
        self.subject = subject
        self.nominal = nominal

        self.subject_length = len(subject)
        self.nominal_length = len(nominal)

        self.best_cost_db = defaultdict(lambda: 1e37)
        self.best_cost_db[(0,0)] = 0

        self.append(initial_item)

        # Determine min and max cost without considering the actual content
        self.min_cost = self[0].min_cost_remaining(self.subject_length, 
                                                   self.nominal_length)
        self.max_cost = max_cost(self.subject_length, 
                                 self.nominal_length,
                                 cost_db[substitute_op_worst],
                                 cost_db[INSERT]) + 1e-6

        self.best     = EditSequence(self.max_cost, [], [])

    def run(self) -> EditSequence:
        while self:
            item = self.pop()
            if not self.end_of_sequence(item): 
                self.produce_derived(item)
        return self.best

    def end_of_sequence(self, item):
        """RETURNS: True, if the item may be used for deriving subsequent steps.
                    False, else.
            
        Checks whether it makes further sense to follow the path of 'item'. If the 
        cost is already higher than the best cost, the item is ommitted and no derived
        steps are produced. If one index reaches the end of its sequence, the total cost
        is computed and compared with the best. If it is better, the 'best' is adapted.
        """
        if item.edit_list.cost > self.best.cost:
            # already worse => no chance of winning.
            return True
        elif item.si == self.subject_length: # reached end of subject => INSERT to reach end of nominal
            if self._append_nominal_overhead(item):
                self.__record_best(item)
            return True
        elif item.ni == self.nominal_length: # reached end of nominal => DELETE to cut tail of subject
            if self._append_subject_overhead(item):
                self.__record_best(item)
            return True
        else:
            return False

    def produce_derived(self, item):
        for new_item in item.subsequent_steps(self.subject, self.nominal, self.cache):
            if new_item.min_cost_remaining(self.subject_length, self.nominal_length) >= self.best.cost:
                continue
            elif self.best_cost_db[(new_item.si, new_item.ni)] <= new_item.edit_list.cost:
                # The version with 'cost < new_item.editions.cost' will produce a better total solution.
                continue
            self.best_cost_db[(new_item.si, new_item.ni)] = new_item.edit_list.cost
            self.append(new_item)

    def __record_best(self, item):
        self.best = item.edit_list
        if self.best.cost == self.min_cost: 
            self.clear() # => termination
            return
        # Remove any entry which is already worse than the best.
        for i, item in reversed(list(enumerate(self))):
            if item.edit_list.cost >= self.best.cost: del self[i]

    def _append_overhead(self, item, overhead, extra_cost):
        """RETURNS: True, if 'item' is better than 'best'.
                    False, else.

        Appends edit operations the the 'edit_list' if 'item' and updates
        the 'cost' according to edit operation 'edit_id'.
        """
        item.edit_list.cost += extra_cost
        item.edit_list.extend(overhead)
        return item.edit_list.cost < self.best.cost

def max_cost(subject_length, nominal_length, cost_substitute_type, cost_insert):
   """RETURNS: maximum cost to transform 'subject' into 'nominal' without 
               considering the actual content.
   """
   common_n    = min(subject_length, nominal_length)
   remaining_n = max(subject_length, nominal_length) - common_n
   return cost_substitute_type * common_n + cost_insert * remaining_n

