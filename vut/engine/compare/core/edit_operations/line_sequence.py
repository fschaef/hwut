"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________
PURPOSE: Determine edit operations to transform a subject 'LineSequence' into
         a nominal 'LineSequence'.

The transformation is expressed as a sequence of 'edit operations' on line
sequences, namely:

               GOOD, SUBSTITUTE, DELETE, and INSERT.

Nothing is reordered: the order of lines is the order of the output.

ALGORITHM:

ANCHORED FIRST (intend 19, phase one; L-1, L-2). Within the chunk pair
this call is given -- never across chunks -- lines that are EQUAL and
UNIQUE on both sides pair up, and the longest run of such pairs standing
in order on both sides is kept (patience diff, Cohen 2007). The beginning
and the end anchor virtually, and every anchor grows over neighbours
literally equal on both sides (Heckel 1978), so an identical first line
anchors even where it is not unique. A line carrying an analogy never
anchors: whether it matches depends on bindings made elsewhere.

The SECTIONS between anchors, and each anchor as its own 1x1 section,
are then aligned by the search below, IN ORDER, each starting from the
analogy bindings its predecessor ended with. A chunk without anchors is
one section: the whole search, as before.

The search is analogous to the algorithm for finding edit operations on
'Line's (see edit_operations/line.py) and strings (see Levenshtein
Distance).
_______________________________________________________________________________
"""
from   vut.engine.compare.core.edit_operations.edit  import (E_EditId,
                                                                           Edit,
                                                                           EditSequence,
                                                                           list_EditGOOD_line_sequence,
                                                                           list_EditGOOD_line)
from   vut.engine.compare.core.edit_operations.core  import (WorkListBase,
                                                                           WorkItemBase,
                                                                           position_increment_db,
                                                                           search_budget,
                                                                           SearchBudgetSpent)
from   vut.engine.compare.core.edit_operations.separator_adaptor import SeparatorAdaptor
from   vut.engine.compare.contract.semantics         import line_cost_db as cost_db
from   vut.engine.compare.contract.frozen_analogy_db import FrozenAnalogyDb
from   vut.engine.compare.reading.pattern_finder     import E_ToleranceId

from  typeguard   import typechecked
from  rapidfuzz   import fuzz

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
       analogy_db:  FrozenAnalogyDb = FrozenAnalogyDb(),
       matching=None) -> EditSequence:
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
        best            = _aligned_by_sections(subject_le_seq,
                                               nominal_le_seq,
                                               anchor_list_of(subject_le_seq,
                                                              nominal_le_seq),
                                               initial_edit_sequence,
                                               matching)

    return best.prepare_as_best(separator_db, relative_f=False)

def _anchor_key(line):
    """
    RETURN: tuple, the line's EQUIVALENCE CLASS as a key: two lines with
                   the same key are equivalent under every tolerance, and
                   two lines with different keys are not.
            None,  where no key can say that, and the line never anchors:
                   it holds an equivalence pattern (matched by
                   intersecting pattern sets, which is not transitive), a
                   number with a tolerance, an analogy or a constraint
                   binding (whose match depends on bindings made
                   elsewhere).

    THE LITERAL TEXT IS NOT THE KEY. 'glad' and 'happy' under an
    equivalence pattern are different text and one class; keyed by text,
    the unique 'glad' of one side pairs with the unique 'glad' of the
    other while the right partner was a 'happy' -- measured, by
    'test-consistency-fuzz.py consistency'.
    """
    key = []
    for element in line.sequence:
        kind = element.tolerance_id
        if   kind == E_ToleranceId.VISIBLE_NOTHING: continue
        elif kind == E_ToleranceId.SEPERATOR:       key.append(("sep",))
        elif kind == E_ToleranceId.STRING:          key.append(("s", element._string))
        elif kind == E_ToleranceId.NUMERIC and element.epsilon == 0.0:
                                                    key.append(("n", element.number))
        else:                                       return None
    #  A LINE WITHOUT CONTENT HAS NO IDENTITY: empty, whitespace, or
    #  ignored by the comment markers, it equals every other such line,
    #  and anchoring one to another only picks a partner at random.
    return tuple(key) if key else None


def anchor_list_of(subject, nominal):
    """
    RETURN: list[(int, int)], the ANCHORS of one chunk pair: (si, ni)
            pairs strictly increasing in both, each a pair of lines that
            is certainly the same line.

    PATIENCE: a line whose key occurs exactly once on each side pairs up;
    of those pairs, the longest chain increasing in both indices is kept
    (the rest cross it). HECKEL: from every anchor, and from the virtual
    begin (-1, -1) and end (len, len), the anchoring grows over
    neighbours whose keys are equal, forward and backward, until it meets
    an unequal pair or another anchor.
    """
    s_key = [_anchor_key(line) for line in subject]
    n_key = [_anchor_key(line) for line in nominal]
    count_db = {}
    for side, key_list in ((0, s_key), (1, n_key)):
        for key in key_list:
            if key is None: continue
            count_db.setdefault(key, [0, 0])[side] += 1
    n_index_db = {key: ni for ni, key in enumerate(n_key)
                  if key is not None and count_db[key] == [1, 1]}
    candidate_list = [(si, n_index_db[key]) for si, key in enumerate(s_key)
                      if key is not None and count_db[key] == [1, 1]]

    #  The longest chain increasing in 'ni' (candidates already increase
    #  in 'si'): patience sorting, O(k log k).
    import bisect
    pile_top, pile_of, back = [], [], [None] * len(candidate_list)
    for i, (_si, ni) in enumerate(candidate_list):
        p = bisect.bisect_left(pile_top, ni)
        back[i] = pile_of[p - 1] if p else None
        if p == len(pile_top): pile_top.append(ni); pile_of.append(i)
        else:                  pile_top[p] = ni;    pile_of[p] = i
    chain, i = [], (pile_of[-1] if pile_of else None)
    while i is not None:
        chain.append(candidate_list[i]); i = back[i]
    chain.reverse()

    #  Heckel's growth, between consecutive fixed points.
    anchor_set = set(chain)
    fixed = [(-1, -1)] + chain + [(len(subject), len(nominal))]
    for (a_s, a_n), (b_s, b_n) in zip(fixed, fixed[1:]):
        si, ni = a_s + 1, a_n + 1                       # forward
        while si < b_s and ni < b_n and s_key[si] is not None \
              and s_key[si] == n_key[ni]:
            anchor_set.add((si, ni)); si += 1; ni += 1
        lo_s, lo_n = si, ni
        si, ni = b_s - 1, b_n - 1                       # backward
        while si >= lo_s and ni >= lo_n and s_key[si] is not None \
              and s_key[si] == n_key[ni]:
            anchor_set.add((si, ni)); si -= 1; ni -= 1
    return sorted(anchor_set)


def _aligned_by_sections(subject, nominal, anchor_list, initial,
                         matching=None):
    """
    RETURN: EditSequence, the whole chunk pair aligned section by
            section: the stretch before each anchor, then the anchor as a
            1x1 section, and the stretch after the last -- IN ORDER, each
            from the analogy bindings the previous one ended with. Costs
            add; edit lists concatenate.

    A section is SEARCHED within 'diff_display_parameters.search_budget' expansions;
    where the search spends it, PHASE TWO aligns the section instead.
    """
    if matching is None:
        from vut.engine.compare.configuration import ConfigurationDiffDisplayParameters
        matching = ConfigurationDiffDisplayParameters()
    aligner = _Aligner(subject, nominal, matching)
    cost, edit_list, analogy_db = 0, [], initial.analogy_db
    si = ni = 0
    for a_s, a_n in anchor_list + [(len(subject), len(nominal))]:
        for span in ((si, a_s, ni, a_n), (a_s, a_s + 1, a_n, a_n + 1)):
            part = aligner.section(*span, analogy_db)
            cost += part.cost
            edit_list.extend(part.edit_list)
            analogy_db = part.analogy_db
        si, ni = a_s + 1, a_n + 1
    return EditSequence(cost, edit_list, analogy_db)


class _Aligner:
    """
    ONE CHUNK PAIR's sections, aligned by the budgeted search or, where
    the budget runs out, by PHASE TWO (intend 19, o-6, o-7; compare
    C-16): pairs 'clearly the closest' anchor first, else the n cheapest,
    non-crossing; what lies between them is aligned the same way, again.

    A pair's cost is the FUZZ RATIO of the two lines' uniform strings,
    averaged with 'context_k' lines either side: about 1 us a pair, where
    the element cost is ~3.6 ms and measured no more accurate. The
    alternative to pairing is DELETE + INSERT, 1.0; so a pair's runner-up
    is never worse than 1.0, and no pair at 1.0 or above anchors.
    """
    def __init__(self, subject, nominal, matching):
        self.S, self.N, self.m = subject, nominal, matching
        self.base_db = {}

    def section(self, s0, s1, n0, n1, analogy_db, pool=None):
        """RETURN: EditSequence, S[s0:s1] against N[n0:n1]: the search
        within the budget, else phase two.

        ONE POOL PER SECTION: the searches phase two tries on the gaps it
        leaves share what the section had left, so a large section spends
        at most one budget on searching, however deep phase two recurses;
        a spent pool sends the gaps straight to phase two."""
        if s0 >= s1 and n0 >= n1:
            return EditSequence(0, [], analogy_db)
        if pool is None: pool = [self.m.search_budget]
        if pool[0] > 0:
            item = WorkItem(0, 0, edit_list=EditSequence(0, [], analogy_db))
            try:
                with search_budget(pool):
                    return WorkList(self.S[s0:s1], self.N[n0:n1], item).run()
            except SearchBudgetSpent:
                pass
        return self._phase_two(s0, s1, n0, n1, analogy_db, pool)

    def _pair(self, i, j, analogy_db):
        """RETURN: EditSequence, S[i] against N[j] by the search -- or, where
        even that one pair's element alignment spends the budget, the
        whole line deleted and the whole nominal line inserted."""
        item = WorkItem(0, 0, edit_list=EditSequence(0, [], analogy_db))
        try:
            with search_budget(self.m.search_budget):
                return WorkList(self.S[i:i + 1], self.N[j:j + 1], item).run()
        except SearchBudgetSpent:
            return EditSequence(2 * cost_INSERT_DELETE,
                                [Edit(DELETE, cost=cost_INSERT_DELETE),
                                 Edit(INSERT, cost=cost_INSERT_DELETE)],
                                analogy_db)

    def _base(self, i, j):
        """RETURN: float in [0, 1], the fuzz cost of S[i] against N[j]."""
        key = (i, j)
        c = self.base_db.get(key)
        if c is None:
            c = 1.0 - fuzz.ratio(self.S[i].uniform_string(),
                                 self.N[j].uniform_string()) / 100.0
            self.base_db[key] = c
        return c

    def _cost(self, i, j):
        """RETURN: float, the base cost averaged with 'context_k' lines."""
        k, total, n = self.m.context_k, 0.0, 0
        for d in range(-k, k + 1):
            if 0 <= i + d < len(self.S) and 0 <= j + d < len(self.N):
                total += self._base(i + d, j + d); n += 1
        return total / n

    def _phase_two(self, s0, s1, n0, n1, analogy_db, pool):
        """RETURN: EditSequence, S[s0:s1] against N[n0:n1] by phase two."""
        chosen = self._chosen(s0, s1, n0, n1)
        if not chosen:
            #  NOTHING PAIRS BELOW DELETE + INSERT: every line goes.
            return EditSequence(
                (s1 - s0 + n1 - n0) * cost_INSERT_DELETE,
                [Edit(DELETE, cost=cost_INSERT_DELETE)] * (s1 - s0)
                + [Edit(INSERT, cost=cost_INSERT_DELETE)] * (n1 - n0),
                analogy_db)
        cost, edit_list = 0, []
        ps, pn = s0, n0
        for i, j in chosen + [(s1, n1)]:
            gap = self.section(ps, i, pn, j, analogy_db, pool)
            cost += gap.cost; edit_list.extend(gap.edit_list)
            analogy_db = gap.analogy_db
            if (i, j) != (s1, n1):
                pair = self._pair(i, j, analogy_db)
                cost += pair.cost; edit_list.extend(pair.edit_list)
                analogy_db = pair.analogy_db
            ps, pn = i + 1, j + 1
        return EditSequence(cost, edit_list, analogy_db)

    def _chosen(self, s0, s1, n0, n1):
        """RETURN: list[(i, j)], phase two's anchors in the section,
        non-crossing, ascending: the pairs clearly the closest where any
        is, else the 'lowest_n' cheapest; empty where none is below 1.0."""
        C = {(i, j): self._cost(i, j)
             for i in range(s0, s1) for j in range(n0, n1)}
        def two_smallest(values):
            """RETURN: (float, float), the smallest and the next, 1.0-capped."""
            a = b = 1.0
            for v in values:
                if v < a:   a, b = v, a
                elif v < b: b = v
            return a, b
        row = {i: two_smallest(C[i, j] for j in range(n0, n1))
               for i in range(s0, s1)}
        col = {j: two_smallest(C[i, j] for i in range(s0, s1))
               for j in range(n0, n1)}
        outlier = [(i, j) for (i, j), c in C.items()
                   if c < 1.0 and c == row[i][0] and c == col[j][0]
                   and min(row[i][1], col[j][1]) - c >= self.m.margin]
        if outlier:
            return _longest_chain(outlier)
        taken = []
        for c, i, j in sorted((c, i, j) for (i, j), c in C.items() if c < 1.0):
            if all((i - a) * (j - b) > 0 for a, b in taken):
                taken.append((i, j))
                if len(taken) == self.m.lowest_n: break
        return sorted(taken)


def _longest_chain(pair_list):
    """RETURN: list[(i, j)], the longest chain of 'pair_list' increasing in
    both indices (patience sorting)."""
    import bisect
    pair_list = sorted(pair_list)
    top, index, back = [], [], [None] * len(pair_list)
    for x, (_i, j) in enumerate(pair_list):
        p = bisect.bisect_left(top, j)
        back[x] = index[p - 1] if p else None
        if p == len(top): top.append(j); index.append(x)
        else:             top[p] = j;    index[p] = x
    out, x = [], (index[-1] if index else None)
    while x is not None:
        out.append(pair_list[x]); x = back[x]
    return out[::-1]


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

def _step_cost(edit_id, relative_edit_distance):
    """
    RETURN: float, the price of one line-level edit, the same wherever it
            stands: GOOD 'cost_GOOD', SUBSTITUTE the lines' relative edit
            distance, INSERT and DELETE 'cost_INSERT_DELETE' each.

    FLAT, BY RULING (intend 19, o-2). A run of k missing lines costs k
    times the price of one. Whether a block should cost less than its
    lines -- affine or concave gap costs -- is left open until anchoring
    is measured.
    """
    if   edit_id == GOOD:       return cost_GOOD
    elif edit_id == SUBSTITUTE: return relative_edit_distance
    elif edit_id in (INSERT, DELETE): return cost_INSERT_DELETE
    raise AssertionError("no line-level price for %s" % edit_id)

class WorkItem(WorkItemBase):
   def __init__(self, si, ni, edit_list):
       WorkItemBase.__init__(self, si, ni, edit_list)

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

       delta_cost = _step_cost(edit_id, relative_edit_distance)

       if new_analogy_db is not None:
           new_analogy_db = self.edit_list.analogy_db.clone().update(new_analogy_db)
       else:
           new_analogy_db = self.edit_list.analogy_db

       new_editions = EditSequence(self.edit_list.cost + delta_cost,
                                   self.edit_list.edit_list + [ Edit(edit_id, edit_list, cost=delta_cost) ],
                                   new_analogy_db)

       return WorkItem(self.si + increment_si,
                       self.ni + increment_ni,
                       new_editions)

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

