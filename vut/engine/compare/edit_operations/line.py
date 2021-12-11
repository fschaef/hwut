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

from  vut.engine.compare.edit_operations.core     import WorkListBase, WorkItemBase
from  vut.engine.compare.tolerance.pattern_finder import E_ToleranceId
from  vut.engine.compare.engine.analogy_db        import AnalogyDb
from  vut.engine.compare.engine.core              import E_Verdict, E_EditId
from  vut.external.quex.typed                     import typed

from  copy        import copy
from  enum        import IntEnum
from  collections import namedtuple, defaultdict
from  functools   import lru_cache

Edit = namedtuple("Edit", ("id", "transpose_ai"))

def Edit_none():
    return Edit(E_EditId.NONE, None)

def Edit_list_description(edit_list):
    if not edit_list:
        return "[]"
    def _iterable(edit_list):
        for i, edit in enumerate(edit_list):
            if edit.id != E_EditId.TRANSPOSE:
                yield edit.id.name 
            else:
                yield "%s:%i<->%i" % (edit.id.name, i, edit.transpose_ai)
    return "[%s]" % ", ".join(_iterable(edit_list))

EditsLine = namedtuple("EditsLine", ("cost", "edit_list", "analogy_db"))


class WorkList(WorkListBase):
    def _adapt_initialization(self):
        self.min_cost = self[0].min_cost_remaining(self.subject_length, self.nominal_length)
        self.max_cost = max_cost(self.subject_length, self.nominal_length) + 1e-6

        self.best = EditsLine(self.max_cost + 1, [], [])
        self.cost_insert_delete = cost_db[E_EditId.INSERT]

        self.cache = Cache()

    def _set_best(self, item):
        self.best = EditsLine(item.cost, item.edit_list, item.analogy_db)

    def _append_subject_overhead(self, item):
        L          = self.subject_length - item.si
        extra_cost = (self.subject_length - item.si) * self.cost_insert_delete
        overhead   = [ Edit(E_EditId.DELETE, None) ] * L
        return self._append_overhead(item, overhead, extra_cost)

    def _append_nominal_overhead(self, item):
        L          = self.nominal_length - item.ni
        extra_cost = sum(self.nominal[ni].tolerance_id != VISIBLE_NOTHING 
                         for ni in range(item.ni, self.nominal_length)) \
                     * self.cost_insert_delete 
        overhead   = [ Edit(E_EditId.INSERT, None) ] * L
        return self._append_overhead(item, overhead, extra_cost)



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

    initial_item = WorkItem(si         = 0, # index into subject 'LineElement' sequence
                            ni         = 0, # index into nominal 'LineElement' sequence
                            cost       = 0,
                            edit_list  = [],
                            analogy_db = analogy_db)

    work_list = WorkList(subject_match_seq, nominal_match_seq, initial_item)

    if seperator_db.original_max_cost == 0.0:
        return EditsLine(0, 
                         seperator_db.reinsert_seperators([]),
                         AnalogyDb())

    while work_list:
        item = work_list.pop()
        if not work_list.end_of_sequence(item): 
            work_list.produce_derived(item)

    best = work_list.best
    if best.cost != 0: cost = best.cost / seperator_db.original_max_cost
    else:              cost = 0

    return EditsLine(cost, 
                     seperator_db.reinsert_seperators(best.edit_list),
                     best.analogy_db)

# Shortcuts:
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
VISIBLE_NOTHING = E_ToleranceId.VISIBLE_NOTHING

class SeperatorAdaptor:
    """Seperators are elements of a line which appear (often) between line
    elements. Their exact 'shape' is irrelevant. Two patterns matching a 
    seperator are always equivalent. 

    IDEA: Seperate the seperators from the line element sequence in order
          to reduce the required amount of matching. Later, once the 
          edit list is determined, re-insert the seperator related 
          content.

    A seperator may be a 'SEPERATOR' or 'VISIBLE_NOTHING'. The latter
    does not cause errors if present in one and missing in the other.

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
        self.subject_sequence = subject_seq
        self.nominal_sequence = nominal_seq
        self.subject_flags    = [x.tolerance_id != SEPERATOR for x in subject_seq]
        self.nominal_flags    = [x.tolerance_id != SEPERATOR for x in nominal_seq]

        # map: index in subject content --> index in original subject sequence
        self.subject_index_map = {}
        k = 0
        for i, content_f in enumerate(self.subject_flags):
            if not content_f: continue
            self.subject_index_map[k] = i
            k += 1

        length_relevant_subject_seq = sum(self.subject_flags)
        length_relevant_nominal_seq = sum(self.nominal_flags)
        self.original_max_cost      = max_cost(length_relevant_subject_seq, 
                                               length_relevant_nominal_seq)


    def strip_separators(self):
        return \
            [ x for x, content_f in zip(self.subject_sequence, self.subject_flags) if content_f ], \
            [ x for x, content_f in zip(self.nominal_sequence, self.nominal_flags) if content_f ]  
                
    def reinsert_seperators(self, edit_list_raw):
        """RETURNS: Edit-operations considering seperators being present.

        The 'edit_list_raw' has been generated to transform all content elements
        of the subject into equivalent content elements of the nominal All
        seperators have been taken out for this purpose. This function re-inserts
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
            sequence_db = {
                # GOOD_INSERT/DELETE = 'insert/delete' visible nothing.
                #
                # Example subject sequence (V = visible nothing, S = string):
                #
                #               SV  --- GOOD_INSERT ---> VSV
                #               ^
                #               VSV --- DELETE      ---> VV    
                #                ^
                #               VV  --- GOOD_DELETE ---> V
                #                ^
                # This is equivalent to 'DELETE' at the beginning. The second case
                # works respectively.
                (GOOD_INSERT, DELETE, GOOD_DELETE): DELETE,
                (GOOD_DELETE, INSERT, GOOD_INSERT): INSERT
            }
            pair_db = {
                (DELETE, INSERT): SUBSTITUTE_TYPE,
                (INSERT, DELETE): SUBSTITUTE_TYPE
            }
            def _iterable(edit_list):
                """YIELDS: (current, look-ahead, look-ahead-ahead)
                """
                last = len(edit_list) - 1
                for i, x in enumerate(edit_iterable):
                    if i == last:       yield x, NONE, NONE
                    elif i == last -1 : yield x, edit_iterable[i+1].id, NONE
                    else:               yield x, edit_iterable[i+1].id, edit_iterable[i+2].id
                   
            skip_n = 0
            for current, ahead_id, ahead2_id in _iterable(edit_iterable):
                if skip_n: skip_n -= 1; continue

                combined_id = pair_db.get((current.id, ahead_id))
                if combined_id is not None:
                    yield Edit(combined_id, None)
                    skip_n = 1
                    continue

                combined_id = sequence_db.get((current.id, ahead_id, ahead2_id))
                if combined_id is not None:
                    yield Edit(combined_id, None)
                    skip_n = 2
                    continue

                yield current

        return list(iterable(list(self.__reinsert_seperators(edit_list_raw))))

    def __reinsert_seperators(self, edit_list_raw):
        def _insert_op(ni):
            return Edit(INSERT, None)

        def _delete_op(si):
            return Edit(DELETE, None)

        def _good_op(si, ni):
            if self.subject_sequence[si].string == self.nominal_sequence[ni].string:
                return Edit(GOOD, None)            # both equal seperators
            else:
                return Edit(GOOD_TOLERATED, None)  # seperators are similar

        def _possible_transpose_op(ei):
            edit = edit_list_raw[ei]
            if edit.id == TRANSPOSE:
                translated_si = self.subject_index_map[edit.transpose_ai]
                return Edit(TRANSPOSE, translated_si)
            else:
                return edit

        Le = len(edit_list_raw)
        Ls = len(self.subject_sequence)
        Ln = len(self.nominal_sequence)
        si = ni = ei = 0
        while 1 + 1 == 2:
            if si >= Ls:
                for tail_ni in range(ni, Ln):
                    yield _insert_op(tail_ni)
                return
            elif ni >= Ln:
                for tail_si in range(si, Ls):
                    yield _delete_op(tail_si)
                return

            s_is_content = self.subject_flags[si]
            n_is_content = self.nominal_flags[ni]

            if       s_is_content and not n_is_content: 
                edit = _insert_op(ni)

            elif not s_is_content and     n_is_content:  
                edit = _delete_op(si)

            elif not s_is_content and not n_is_content:                   
                subject_tid = self.subject_sequence[si].tolerance_id
                nominal_tid = self.nominal_sequence[ni].tolerance_id
                if   subject_tid == SEPERATOR       and nominal_tid == VISIBLE_NOTHING:
                    edit = Edit(DELETE, None)          # remove separator from subject
                elif subject_tid == VISIBLE_NOTHING and nominal_tid == SEPERATOR:
                    edit = Edit(INSERT, None)          # insert seperator into subject
                else:
                    edit = _good_op(si, ni)

            else:                                    # subject = content,   nominal = content
                edit = _possible_transpose_op(ei)
                ei += 1

            yield edit
            s_incr, n_incr = position_increment_db[edit.id]
            si += s_incr
            ni += n_incr

        
position_increment_db = {
    #                        si-increment  ni-increment
    E_EditId.GOOD:             (1,           1),    # Step over subject[si], nominal[ni]
    E_EditId.GOOD_TOLERATED:   (1,           1),    #          -- " --
    E_EditId.GOOD_INSERT:      (0,           1),    # Consider 'subject[si]' visible nothing as insertion.
    E_EditId.GOOD_DELETE:      (1,           0),    # Consider 'nominal[ni]' visible nothing as insertion.
    E_EditId.TRANSPOSE:        (1,           1),    #          -- " --
    E_EditId.INSERT:           (0,           1),    # Consider 'subject[si]' as insertion.
    #                                                 # => compare subject[si+1] with nominal[ni]
    E_EditId.DELETE:           (1,           0),    # Consider 'nominal[ni]' as insertion.
    #                                                 # => compare subject[si] with nominal[ni+1]
    E_EditId.SUBSTITUTE:       (1,           1),    # Step over subject[si], nominal[ni]
    E_EditId.SUBSTITUTE_TYPE:  (1,           1),    #          -- " --
}

cost_db = {
    E_EditId.GOOD:             0,  # good
    E_EditId.GOOD_TOLERATED:   0,  # good
    E_EditId.TRANSPOSE:        0.5,  # good, when swapped elements
    E_EditId.SUBSTITUTE:       1,  # good, when content is substituted
    E_EditId.INSERT:           1,  # bad, need to insert element
    E_EditId.DELETE:           1,  # bad, need to remove element
    E_EditId.SUBSTITUTE_TYPE:  1   # bad, need to substitute type and content of element
}

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
    def __init__(self, si, ni, cost, edit_list, analogy_db, subject_modified=None):
        WorkItemBase.__init__(self, si, ni)
        self.cost             = cost
        self.edit_list        = edit_list
        self.analogy_db       = analogy_db
        self.subject_modified = subject_modified # in case of 'transpose' edits.

    def subsequent_steps(self, subject, nominal, cache):
        """YIELDS: 'WorkItems' based on possible edit operations applied on 'self'.
        """
        if self.subject_modified: subject = self.subject_modified

        verdict_id, analogy = cache.get(self.si, self.ni, subject, nominal, 
                                        transpose_f = self.subject_modified is not None)

        subject_match = subject[self.si]
        nominal_match = nominal[self.ni]

        # IMPORTANT: Worklist is a LIFO (last in, first out).
        #
        # For performance, it is essential that 'cheap' steps are treated first.
        # => more expensive paths are cut early.
        good_id = None
        if   verdict_id == E_Verdict.MISFIT:
            yield self._step(E_EditId.SUBSTITUTE_TYPE)
        elif verdict_id == E_Verdict.DIFFERENT:
            yield self._step(E_EditId.SUBSTITUTE,
                             cost_factor = subject_match.edit_distance_relative(nominal_match))
        elif not self.analogy_db.is_consistent(analogy):
            yield self._step(E_EditId.SUBSTITUTE)
        elif   subject_match.string       != nominal_match.string:  
            good_id = E_EditId.GOOD_TOLERATED
        elif subject_match.tolerance_id == E_ToleranceId.ANALOGY: 
            good_id = E_EditId.GOOD_TOLERATED
        else:                                                     
            good_id = E_EditId.GOOD

        if good_id is None:
            yield from (
                self._step(E_EditId.TRANSPOSE, transpose_ai=candidate_ai, subject=subject)
                for candidate_ai in range(self.si+1, len(subject))
                if subject[candidate_ai].is_equivalent(nominal_match, self.analogy_db)
            )

        yield self._step(E_EditId.INSERT)
        yield self._step(E_EditId.DELETE)

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
            new_analogy_db = self.analogy_db.clone()
            new_analogy_db.add(new_analogy)
        else:
            new_analogy_db = self.analogy_db

        increment_ai, increment_bi       = position_increment_db[edit_id]
        return WorkItem(si               = self.si + increment_ai,
                        ni               = self.ni + increment_bi,
                        cost             = self.cost + cost_db[edit_id] * cost_factor,
                        edit_list        = self.edit_list + [ Edit(edit_id, transpose_ai) ],
                        analogy_db       = new_analogy_db, 
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
        return self.cost + cost_db[E_EditId.GOOD] * common_n + cost_db[E_EditId.INSERT] * remaining_n


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


def max_cost(subject_length, nominal_length):
   """RETURNS: maximum cost to transform 'subject' into 'nominal'.
   """
   common_n    = min(subject_length, nominal_length)
   remaining_n = max(subject_length, nominal_length) - common_n
   return cost_db[E_EditId.SUBSTITUTE_TYPE] * common_n + cost_db[E_EditId.INSERT] * remaining_n

def _cost_assumptions(subject_length, nominal_length):
    """RETURNS: [0] maximum possible cost for transforming subject into nominal
                [1] minimum possible cost for transforming subject into nominal
    """
    # worst case: everything is a SUBSTITUTE_TYPE error
    max_cost = max(subject_length, nominal_length) * cost_db[E_EditId.SUBSTITUTE_TYPE]

    # best case:  all are GOOD, except for a missing tail
    #             GOOD cost = 0; INSERT/DELETE cost = same
    min_cost = abs(subject_length - nominal_length) * cost_db[E_EditId.INSERT]

    return max_cost, min_cost


class Cache(dict):
    def get(self, subject_i, nominal_i, subject, nominal, transpose_f):
        subject_elm = subject[subject_i]
        nominal_elm = nominal[nominal_i]
        # Use 'id' of LineElements, rather than their index. Notably the 'traspose'
        # edit operation may switch elements to a different position.
        pair   = (id(subject_elm), id(nominal_elm))
        result = dict.get(self, pair)
        if result is not None:
            verdict_id, analogy = result
        else:
            subject_elm = subject[subject_i]
            nominal_elm = nominal[nominal_i]
            verdict_id, analogy = subject_elm.compare(nominal_elm)
            self[pair] = verdict_id, analogy
        return verdict_id, analogy

