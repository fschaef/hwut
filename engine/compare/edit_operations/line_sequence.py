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
from   ut.engine.compare.edit_operations.line import Edit, EditsLine
from   ut.engine.compare.engine.analogy_db    import AnalogyDb
from   ut.engine.quex.typed                   import typed

from   enum        import IntEnum
import sys

class E_EditLineSequence(IntEnum):
    """Operations moving/substituting 'Lines'.
    """
    GOOD        = 0  # Subject and nominal 'LineElement' object are equivalent.
    INSERT      = 1  # Heal: 'LineElement' from nominal is inserted.
    DELETE      = 2  # Heal: 'LineElement' from subject is deleted.
    SUBSTITUTE  = 3  # Bad:  Content of subject and nominal 'LineElement' differs.


class EditsLineSequence:
    def __init__(self, cost, edit_list, analogy_db):
        """edit_list: list of tuples (edit_id, edit_list)

                      where     'edit_id' is an 'E_EditLineSequence'
                            and 'edit_list' is a list of 'Edit' objects
        """
        assert all(isinstance(first, E_EditLineSequence)
                   for first, _ in edit_list)
        assert all(isinstance(x, Edit)
                   for _, second in edit_list
                   if second is not None
                   for x in second)
        self.cost       = cost
        self.edit_list  = edit_list
        self.analogy_db = analogy_db


def do(subject_match_seq_list, nominal_match_seq_list, analogy_db=None):
    """RETURNS: EditsLineSequence

    Determine how the sequence of subject 'Line' objects can be transformed
    into the sequence of nominal 'Line' objects. It determines a 'cost' value
    and a sequence of edit operations. The tuples indicate the operation, i.e.
    INSERT, DELETE, or SUBSTITUTE. In case of the SUBSTITUTE operation, a list
    of editions (see edit_operations/line.py) is provided that tells how the
    subject line is transformed into the nominal line.
    """
    if analogy_db is None: analogy_db = AnalogyDb()

    subject_length = len(subject_match_seq_list)
    nominal_length = len(nominal_match_seq_list)

    initial_item = WorkItem(ai=0, bi=0, editions=EditsLineSequence((0, 0), [], analogy_db))
    work_list = [ initial_item ]

    min_cost, max_cost = _cost_assumptions(initial_item, subject_length, nominal_length)

    best = EditsLineSequence(cost=(sys.float_info.max, sys.float_info.max), edit_list=[], analogy_db=[])
    while work_list:
        item = work_list.pop()

        if item.min_cost_remaining(subject_length, nominal_length) > best.cost:
            pass
        if item.ai == subject_length:
            if _append_overhead(best, item.editions, nominal_match_seq_list[item.bi:], E_EditLineSequence.INSERT):
                best = item.editions
                if best.cost == min_cost: break
        elif item.bi == nominal_length:
            if _append_overhead(best, item.editions, subject_match_seq_list[item.ai:], E_EditLineSequence.DELETE):
                best = item.editions
                if best.cost == min_cost: break
        else:
            work_list.extend(
                item.subsequent_steps(subject_match_seq_list, nominal_match_seq_list)
            )

    return best


position_increment_db = {
    #                        ai-increment  bi-increment
    E_EditLineSequence.GOOD:         (1,           1),    # Step over subject[ai], nominal[bi]
    E_EditLineSequence.SUBSTITUTE:   (1,           1),    # Step over subject[ai], nominal[bi]
    E_EditLineSequence.INSERT:       (0,           1),    # Must insert before 'subject[ai]' to fix.
    E_EditLineSequence.DELETE:       (1,           0),    # Must insert before 'nominal[bi]' to fix.
}


cost_GOOD_major             = -1.0
cost_SUBSTITUTION_major     =  0.0
cost_SUBSTITUTION_minor_max =  1.0   # relative edit distance <= 1.0
cost_INSERT_DELETE_major    =  0.0
cost_INSERT_DELETE_minor    =  1.0


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
        if edit_id == E_EditLineSequence.GOOD:
            self.substitute_n  = 0
            self.insert_n      = 0
            self.delete_n      = 0
            # value of GOOD decreases with number of corrections preceeding it.
            return (cost_GOOD_major, 0)
        elif edit_id == E_EditLineSequence.SUBSTITUTE:
            if editions != self.substitute_editions:
                self.substitute_editions = editions
                self.substitute_n        = 0
            self.substitute_n += 1
            self.insert_n      = 0
            self.delete_n      = 0
            assert relative_edit_distance <= cost_SUBSTITUTION_minor_max
            # cost of SUBSTITUTE decreases with same substitution patterns preceeding
            return (cost_SUBSTITUTION_major, relative_edit_distance / self.substitute_n)
        elif edit_id == E_EditLineSequence.INSERT:
            self.substitute_n  = 0
            self.insert_n     += 1
            self.delete_n      = 0
            # cost of DELETE decreases with number of preceeding deletions number
            return (cost_INSERT_DELETE_major, cost_INSERT_DELETE_minor / self.insert_n)
        elif edit_id == E_EditLineSequence.DELETE:
            self.substitute_n  = 0
            self.insert_n      = 0
            self.delete_n     += 1
            # cost of INSERT decreases with number of preceeding deletions number
            return (cost_INSERT_DELETE_major, cost_INSERT_DELETE_minor / self.delete_n)
        else:
            assert False # pragma no cover

class WorkItem:
   def __init__(self, ai, bi, editions, history=None):
       self.ai         = ai
       self.bi         = bi
       self.editions = editions
       if history is None:
           self.history = WorkItemHistory()
       else:
           self.history = history

   def subsequent_steps(self, subject_list, nominal_list):
       """YIELDS: 'WorkItems' based on possible edit operations applied on 'self'.
       """
       subject = subject_list[self.ai]
       nominal = nominal_list[self.bi]

       line_editions = subject.edit_operations(nominal, self.editions.analogy_db)
       assert isinstance(line_editions, EditsLine)

       # IMPORTANT: Worklist is a LIFO. That is, what comes last is popped
       # first from the worklist. It is essential that 'cheap' steps are
       # treated first, so that more expensive paths can be cut as early as
       # possible.
       yield self._step(E_EditLineSequence.INSERT)
       yield self._step(E_EditLineSequence.DELETE)

       if line_editions.cost == 0.0:
           yield self._step(E_EditLineSequence.GOOD,
                            edit_list      = line_editions.edit_list,
                            new_analogy_db = line_editions.analogy_db)
       else:
           yield self._step(E_EditLineSequence.SUBSTITUTE,
                            relative_edit_distance = line_editions.cost,
                            edit_list              = line_editions.edit_list)

   @typed(edit_id=E_EditLineSequence, edit_list=[Edit])
   def _step(self, edit_id, relative_edit_distance=None, new_analogy_db=None, edit_list=None):
       """RETURNS: WorkItem derived from self after applying an edit operation.

       Given an edit operation 'edit_id' this function generates a modified
       version of 'self'. It adapts the indices 'ai' and 'bi' according to
       the position progress related to the operation. The new 'WorkItem'
       will contain a new updated 'edit_list'.
       """
       increment_ai, increment_bi = position_increment_db[edit_id]

       delta_cost = self.history.note(edit_id, edit_list, relative_edit_distance)

       if new_analogy_db is not None:
           new_analogy_db = self.editions.analogy_db.clone().update(new_analogy_db)
       else:
           new_analogy_db = self.editions.analogy_db

       new_editions = EditsLineSequence(_cost_add(self.editions.cost, delta_cost),
                                        self.editions.edit_list + [ (edit_id, edit_list) ],
                                        new_analogy_db)

       result = WorkItem(self.ai + increment_ai,
                         self.bi + increment_bi,
                         new_editions,
                         self.history.clone())
       return result

   def min_cost_remaining(self, subject_length, nominal_length):
       """RETURNS: The lowest possible total cost of the remaining comparisons.

       The lowest possible cost is associated with the case that the maximum
       number of lines can be paired as 'GOOD' and the rest needs to be
       inserted/deleted.
       """
       remaining_subject_n = subject_length - self.ai
       remaining_nominal_n = nominal_length - self.bi
       # let: common_n = maximum number of pairs in the remaining lines.
       common_n    = min(remaining_subject_n, remaining_nominal_n)
       remaining_n = max(remaining_subject_n, remaining_nominal_n) - common_n

       # best case: -- all common lines are GOOD
       #            -- all remaining lines are INSERT/DELETE
       cost_common = (cost_GOOD_major * common_n, 0)

       return _cost_add(cost_common, _cost_overhead(remaining_n))

def _append_overhead(best, editions, remaining_list, overhead_edit_id):
    """RETURNS: True, if the edit_operations is better then 'best'.
                False, else.

    Determines the 'cost' and 'edit operations' for the remaing lines for which
    their is no counterpart (e.g. nominal lines when there are no more subject
    lines). It assigns them to the 'edit_operations' and compares it with the
    'best'.
    """
    N = len(remaining_list)
    editions.cost = _cost_add(editions.cost, _cost_overhead(N))
    editions.edit_list.extend([(overhead_edit_id, None)] * len(remaining_list))
    return editions.cost < best.cost

def _cost_add(cost_a, cost_b):
    return (cost_a[0] + cost_b[0], cost_a[1] + cost_b[1])

def _cost_assumptions(initial_item, subject_length, nominal_length):
    """RETURNS: [0] minimum cost to transform 'subject' into 'nominal'.
                [1] maximum cost.
    """
    min_cost    = initial_item.min_cost_remaining(subject_length, nominal_length)

    # worst case: -- all possibly paired lines require a SUBSTITION with a
    #                relative edit distance of 1.0 (== max).
    #             -- remaining lines require INSERT/DELETE
    common_n    = min(subject_length, nominal_length)
    cost_common = (cost_SUBSTITUTION_major * common_n, cost_SUBSTITUTION_minor_max * common_n)
    remaining_n = max(subject_length, nominal_length) - common_n
    max_cost    = _cost_add(cost_common, _cost_overhead(remaining_n))
    return min_cost, max_cost

def _cost_overhead(remaining_n):
    """RETURNS: cost of 'remaining_n' lines when either subject or nominal is
                exhausted.
    """
    major = cost_INSERT_DELETE_major * remaining_n
    # Cost reduces by repetition: x/1 + x/2 + x/3 .... N = x*(1/1 + 1/2 + 1/3 + ...)
    minor = cost_INSERT_DELETE_minor * sum(1/x for x in range(1, remaining_n+1))
    return (major, minor)
