"""SPDX License: MIT; (C) Frank-Rene Schäfer; Project: VUT
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
The algorithm walks along the two sequences with two indices 'ai' and 'bi'
pointing to the 'LineElement' objects under comparison.

Example: Let the subject and nominal sequences of 'LineElement' objects be
represented by the sequences 'a h b e r' and 'a b e r'.

                           ai
                           |
               subject:  a h b e r

               nominal:  a b e r
                           |
                           bi

At a given positions (ai, bi), there are the following three possibilities to
proceed.

 position      edit             effect in the example above
 change        operation
---------------------------------------------------------------------------
 (ai++, bi++)  SUBSTITUTE_TYPE  type of 'b' does not fit type of 'h'
               SUBSTITUTE       'b != h'. step to next two chars
               GOOD             step to next two chars
                                (assume 'b' and 'h' are equivalent)
               TRANSPOSE        switch 'h' and 'b' in nominal, then step
                                to next two chars
 (ai++, bi)    DELETE           do as if 'h' was not there.
                                next compare 'b' with 'b'.
 (ai,   bi++)  INSERT           do as if 'b' is inserted into subject.
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

from  vut.engine.compare.tolerance.pattern_finder import E_ToleranceId
from  vut.engine.compare.engine.analogy_db        import AnalogyDb
from  vut.engine.compare.engine.core              import E_Verdict
from  vut.external.quex.typed                     import typed

from  copy        import copy
from  enum        import IntEnum
from  collections import namedtuple, defaultdict
from  functools   import lru_cache

class E_EditLine(IntEnum):
    """Operations moving/substituting 'LineElements'.
    """
    GOOD            = 0  # Subject and nominal 'LineElement' object are equivalent.
    GOOD_TOLERATED  = 1  # == GOOD, only that content may differ (used in diff-display).
    TRANSPOSE       = 2  # Heal: Two 'LineElement' objects in subject are transposed.
    INSERT          = 3  # Heal: 'LineElement' from nominal is inserted.
    DELETE          = 4  # Heal: 'LineElement' from subject is deleted.
    SUBSTITUTE      = 5  # Bad:  Content of subject and nominal 'LineElement' differs.
    SUBSTITUTE_TYPE = 6  # Bad:  Type of subject and nominal 'LineElement' differs.
    NONE            = 7  # No operation

Edit = namedtuple("Edit", ("id", "transpose_ai"))

def Edit_none():
    return Edit(E_EditLine.NONE, None)

def Edit_list_description(edit_list):
    if not edit_list:
        return "[]"
    def _iterable(edit_list):
        for i, edit in enumerate(edit_list):
            if edit.id != E_EditLine.TRANSPOSE:
                yield edit.id.name 
            else:
                yield "%s:%i<->%i" % (edit.id.name, i, edit.transpose_ai)
    return "[%s]" % ", ".join(_iterable(edit_list))

EditsLine = namedtuple("EditsLine", ("cost", "edit_list", "analogy_db"))

@lru_cache(maxsize=65536)
@typed(subject_match_seq=tuple, nominal_match_seq=tuple)
def do(subject_match_seq, nominal_match_seq, analogy_db=None):
    """RETURNS: EditsLine

    Compares the line elements of 'subject_match_seq' and 'nominal_match_seq' and
    determines the editions required to transform the former into the latter.

    where EditsLine.cost       = cost / max. cost; thus in range of [0...1].
          EditsLine.edit_list  = list of 'Edit'
          EditsLine.analogy_db = 'AnalogyDb' required for equivalences to hold.
    """
    if analogy_db is None:
        analogy_db = AnalogyDb()

    seperator_db = SeperatorAdaptor(subject_match_seq, nominal_match_seq)
    subject_match_seq, nominal_match_seq = seperator_db.strip_separators()

    work_list = WorkList(subject_match_seq, nominal_match_seq, analogy_db)
    if work_list.max_cost == 0.0:
        return EditsLine(0, [], AnalogyDb())

    while work_list:
        item = work_list.pop()
        work_list.produce_next(item)

    return work_list.get_best(seperator_db)

class WorkList(list):
    def __init__(self, subject_match_seq, nominal_match_seq, analogy_db):
        self.append(
            WorkItem(list(subject_match_seq),
                     ai         = 0, # index into subject 'LineElement' sequence
                     bi         = 0, # index into nominal 'LineElement' sequence
                     cost       = 0,
                     edit_list  = [],
                     analogy_db = analogy_db)
        )

        self.subject_length = len(subject_match_seq)
        self.nominal_length = len(nominal_match_seq)
        max_cost, min_cost = _cost_assumptions(self.subject_length, 
                                               self.nominal_length)

        self.best = EditsLine(max_cost + 2, [], [])
        self.max_cost = max_cost
        self.min_cost = min_cost

        self.nominal_match_seq = nominal_match_seq
        self.best_cost_db = defaultdict(lambda: 1e37)
        self.best_cost_db[(0,0)] = 0

    def produce_next(self, item):
        if item.cost > self.best.cost:
            # already worse => no chance of winning.
            pass
        elif item.ai == self.subject_length:
            # reached end of subject => INSERT to reach end of nominal
            if _append_overhead(self.best, item, self.nominal_length - item.bi, E_EditLine.INSERT):
                self.best = EditsLine(item.cost, item.edit_list, item.analogy_db)
                if self.best.cost == self.min_cost: 
                    self.clear() # => termination
                else:
                    work_list = _cut_worse(self.best.cost, self)
        elif item.bi == self.nominal_length:
            # reached end of nominal => DELETE to cut tail of subject
            if _append_overhead(self.best, item, self.subject_length - item.ai, E_EditLine.DELETE):
                self.best = EditsLine(item.cost, item.edit_list, item.analogy_db)
                if self.best.cost == self.min_cost: 
                    self.clear() # => termination
                else:
                    work_list = _cut_worse(self.best.cost, self)
        else:
            # setup exploration of subsequence steps
            for new_item in item.subsequent_steps(self.nominal_match_seq):
                if self.best_cost_db[(new_item.ai, new_item.bi)] <= new_item.cost:
                    # The version with 'cost < new_item.editions.cost' will produce a better total solution.
                    continue
                self.best_cost_db[(new_item.ai, new_item.bi)] = new_item.cost
                self.append(new_item)

    def get_best(self, seperator_db):
        return EditsLine(self.best.cost / seperator_db.original_max_cost, 
                         seperator_db.reinsert_seperators(self.best.edit_list),
                         self.best.analogy_db)


def _cut_worse(cost, work_list):
    """RETURNS: list of work list items where cost >= given 'cost'.
    """
    return [
        item for item in work_list if item.cost < cost
    ]

TRANSPOSE      = E_EditLine.TRANSPOSE
GOOD           = E_EditLine.GOOD
GOOD_TOLERATED = E_EditLine.GOOD_TOLERATED
DELETE         = E_EditLine.DELETE
INSERT         = E_EditLine.INSERT
SEPERATOR      = E_ToleranceId.SEPERATOR

class SeperatorAdaptor:
    """Seperators are elements of a line which appear (often) between line
    elements. Their exact 'shape' is irrelevant. Two patterns matching a 
    seperator are always equivalent. 

    IDEA: Seperate the seperators from the line element sequence in order
          to reduce the required amount of matching. Later, once the 
          edit list is determined, re-insert the seperator related 
          content.

    The constructor takes to line element sequences, subject and nominal.
    It then strips out the seperators, but stores their original position.

    strip_separators(): returns the two line element sequences for 
                        subject and nominal where the seperators are 
                        stripped.

    Now, edit operations are determined based on the 'content' sequences
    without any seperators.
   
    reinsert_seperators(raw_edit_list): produces an edit list that takes
                                        the existence of sperators into
                                        consideration.
    """
    def __init__(self, subject_seq, nominal_seq):
        self.subject_sequence    = subject_seq
        self.nominal_sequence    = nominal_seq
        self.subject_seperators, \
        self.subject_flags       = self.__map(subject_seq)

        # map: index in subject content --> index in original subject sequence
        self.subject_index_map = {}
        k = 0
        for i, content_f in enumerate(self.subject_flags):
            if not content_f: continue
            self.subject_index_map[k] = i
            k += 1

        self.nominal_seperators, \
        self.nominal_flags       = self.__map(nominal_seq)

        length_relevant_subject_seq = sum(self.subject_flags)
        length_relevant_nominal_seq = sum(self.nominal_flags)
        self.original_max_cost      = _cost_assumptions(length_relevant_subject_seq, 
                                                        length_relevant_nominal_seq)[0]


    @staticmethod
    def __map(sequence):
        content    = []
        flags      = []
        for i, x in enumerate(sequence):
            if x.tolerance_id == SEPERATOR:
                flags.append(False)
            else:
                content.append(x)
                flags.append(True)
        return content, flags

    def strip_separators(self):
        return \
            [ s for i, s in enumerate(self.subject_sequence) if self.subject_flags[i] ], \
            [ n for i, n in enumerate(self.nominal_sequence) if self.nominal_flags[i] ]  
                
    def reinsert_seperators(self, edit_list_raw):
        """RETURNS: Edit-operations considering seperators being present.

        The 'edit_list_raw' has been generated to transform all content elements
        of the subject into equivalent content elements of the nominal All
        seperators have been taken out for this purpose. This function re-inserts
        the separators and provides an according list of edit operations based
        on the edit operations derived from the content comparison.
        """
        return list(self.__reinsert_seperators(edit_list_raw))

    def __reinsert_seperators(self, edit_list_raw):
        Le = len(edit_list_raw)
        Ls = len(self.subject_sequence)
        Ln = len(self.nominal_sequence)
        si = ni = ei = 0
        while 1 + 1 == 2:
            if si >= Ls:
                for _ in range(Ln-ni):
                    yield Edit(INSERT, None)
                return
            elif ni >= Ln:
                for _ in range(Ls-si):
                    yield Edit(DELETE, None)
                return
            s_flag = self.subject_flags[si]
            n_flag = self.nominal_flags[ni]

            if not s_flag and n_flag: 
                yield Edit(DELETE, None)   # DELETE seperator in subject
                s_incr, n_incr = 1, 0

            elif s_flag and not n_flag:
                yield Edit(INSERT, None)   # INSERT seperator in subject
                s_incr, n_incr = 0, 1

            elif not s_flag:              
                # both are separators
                if self.subject_sequence[si].string == self.nominal_sequence[ni].string:
                    yield Edit(GOOD, None)            # both equal seperators
                else:
                    yield Edit(GOOD_TOLERATED, None)  # seperators are similar
                s_incr, n_incr = 1, 1

            else:
                # both are content
                edit = edit_list_raw[ei]
                if edit.id == TRANSPOSE:
                    translated_si = self.subject_index_map[edit.transpose_ai]
                    yield Edit(TRANSPOSE, translated_si)
                else:
                    yield edit
                s_incr, n_incr = position_increment_db[edit.id]
                ei += 1

            si += s_incr
            ni += n_incr

        
position_increment_db = {
    #                        ai-increment  bi-increment
    E_EditLine.GOOD:             (1,           1),    # Step over subject[ai], nominal[bi]
    E_EditLine.GOOD_TOLERATED:   (1,           1),    #          -- " --
    E_EditLine.TRANSPOSE:        (1,           1),    #          -- " --
    E_EditLine.INSERT:           (0,           1),    # Consider 'subject[ai]' as insertion.
    #                                                 # => compare subject[ai+1] with nominal[bi]
    E_EditLine.DELETE:           (1,           0),    # Consider 'nominal[bi]' as insertion.
    #                                                 # => compare subject[ai] with nominal[bi+1]
    E_EditLine.SUBSTITUTE:       (1,           1),    # Step over subject[ai], nominal[bi]
    E_EditLine.SUBSTITUTE_TYPE:  (1,           1),    #          -- " --
}

cost_db = {
    E_EditLine.GOOD:             0,  # good
    E_EditLine.GOOD_TOLERATED:   0,  # good
    E_EditLine.TRANSPOSE:        0.5,  # good, when swapped elements
    E_EditLine.SUBSTITUTE:       1,  # good, when content is substituted
    E_EditLine.INSERT:           1,  # bad, need to insert element
    E_EditLine.DELETE:           1,  # bad, need to remove element
    E_EditLine.SUBSTITUTE_TYPE:  1   # bad, need to substitute type and content of element
}

class WorkItem:
   """A 'WorkItem' corresponds to a node for the tree search algorithm
   that searches the least costly path to the end of the 'LineElement'
   sequence objects.

   It maintains:

       * Position pair (ai, bi) which is investigated.

   Also, it maintains implications of previous steps:

       * list of previous edit operations.

       * subject as it might have changed due to transposition.

       * analogy required to hold for all past edit operations.

   The function '.subsequent_steps()' determines possible steps from the
   position denoted by 'self'. It does so by yielding 'WorkItem' objects
   for subsequence positions.
   """
   def __init__(self, subject, ai, bi, cost, edit_list, analogy_db):
       self.subject    = subject
       self.ai         = ai
       self.bi         = bi
       self.cost       = cost
       self.edit_list  = edit_list
       self.analogy_db = analogy_db

   def subsequent_steps(self, nominal_match_seq):
       """YIELDS: 'WorkItems' based on possible edit operations applied on 'self'.
       """
       subject_match = self.subject[self.ai]
       nominal_match = nominal_match_seq[self.bi]

       verdict_id, analogy = subject_match.compare(nominal_match)

       # IMPORTANT: Worklist is a LIFO (last in, first out).
       #
       # For performance, it is essential that 'cheap' steps are treated first.
       # => more expensive paths are cut early.
       good_id = None
       if   verdict_id == E_Verdict.MISFIT:
           yield self._step(E_EditLine.SUBSTITUTE_TYPE)
       elif verdict_id == E_Verdict.DIFFERENT:
           yield self._step(E_EditLine.SUBSTITUTE,
                            cost_factor = subject_match.edit_distance_relative(nominal_match))
       elif not self.analogy_db.is_consistent(analogy):
           yield self._step(E_EditLine.SUBSTITUTE)
       elif   subject_match.string       != nominal_match.string:  
           good_id = E_EditLine.GOOD_TOLERATED
       elif subject_match.tolerance_id == E_ToleranceId.ANALOGY: 
           good_id = E_EditLine.GOOD_TOLERATED
       else:                                                     
           good_id = E_EditLine.GOOD

       if good_id is None:
           yield from (
               self._step(E_EditLine.TRANSPOSE, transpose_ai=candidate_ai)
               for candidate_ai in range(self.ai+1, len(self.subject))
               if self.subject[candidate_ai].is_equivalent(nominal_match, self.analogy_db)
           )

       yield self._step(E_EditLine.INSERT)
       yield self._step(E_EditLine.DELETE)

       if good_id is not None:
           yield self._step(good_id, new_analogy = analogy)

   def _step(self, edit_id, cost_factor=1, transpose_ai=None, new_analogy=None):
       """RETURNS: WorkItem derived from self after applying an edit operation.

       Given an edit operation 'edit_id' this function generates a modified
       version of 'self'. It adapts the indices 'ai' and 'bi' according to
       the position progress related to the operation. The new 'WorkItem'
       will contain a new 'subject', and 'analogy_db' if they were changed.
       The 'edit_list' of the 'WorkItem' contains all current edit operations
       plus the edit operation 'edit_id' that produced the 'WorkItem'.
       """

       if transpose_ai is not None:
           new_subject = copy(self.subject) # shallow copy
           new_subject[self.ai], new_subject[transpose_ai] = new_subject[transpose_ai], new_subject[self.ai]
       else:
           new_subject = self.subject

       if new_analogy is not None:
           new_analogy_db = self.analogy_db.clone()
           new_analogy_db.add(new_analogy)
       else:
           new_analogy_db = self.analogy_db

       increment_ai, increment_bi = position_increment_db[edit_id]
       return WorkItem(subject    = new_subject,
                       ai         = self.ai + increment_ai,
                       bi         = self.bi + increment_bi,
                       cost       = self.cost + cost_db[edit_id] * cost_factor,
                       edit_list  = self.edit_list + [ Edit(edit_id, transpose_ai) ],
                       analogy_db = new_analogy_db)


def _cost_assumptions(subject_length, nominal_length):
    """RETURNS: [0] maximum possible cost for transforming subject into nominal
                [1] minimum possible cost for transforming subject into nominal
    """
    # worst case: everything is a SUBSTITUTE_TYPE error
    max_cost = max(subject_length, nominal_length) * cost_db[E_EditLine.SUBSTITUTE_TYPE]

    # best case:  all are GOOD, except for a missing tail
    #             GOOD cost = 0; INSERT/DELETE cost = same
    min_cost = abs(subject_length - nominal_length) * cost_db[E_EditLine.INSERT]

    return max_cost, min_cost


def _append_overhead(best, item, overhead, edit_id):
    """RETURNS: True, if 'item' is better than 'best'.
                False, else.

    Appends edit operations the the 'edit_list' if 'item' and updates
    the 'cost' according to edit operation 'edit_id'.
    """
    item.cost += cost_db[edit_id] * overhead
    item.edit_list.extend([Edit(edit_id, None)] * overhead)
    return item.cost < best.cost

