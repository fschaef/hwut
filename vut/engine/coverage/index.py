"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHO COVERED THIS LINE -- and therefore, what to run when it
         changes.

DESCRIPTION
       THE INDEX IS A DIFFERENT FOLD, NOT A RICHER MERGE. 'record.merge'
       answers "what did the suite reach", and it is LOSSY BY DESIGN: a
       union of ranges cannot say who contributed which line. This module
       answers the other question -- "which runs reached this line" --
       over the SAME per-run records, by folding them differently.

       So the attribution is not a field anybody had to add. It is THE
       KEY THE RECORD IS ALREADY STORED UNDER: (test, choice). What was
       needed was only that a record CARRY that key when it travels away
       from the store, which is why the header names it (RATIONALE D-8).

       CONSEQUENCE, and it is a rule, not a remark: THE PER-RUN RECORDS
       MUST BE KEPT. An aggregate that replaces them answers the first
       question and destroys the second.

       THE SHAPE. Per source file, a SEGMENTATION: the line axis cut at
       every point where the set of origins changes, and ONE GROUP ID per
       segment. Segments carrying equal groups are fused, so a file every
       test reaches whole is ONE segment -- not one entry per line. A
       query is a bisect.

           lines      1......10......20......30
           test A     [------------]
           test B            [--------------]
           segments   [--g1--][--g3--][--g2--]      g3 = {A, B}

       A SEGMENT CARRIES AN INTEGER, NOT A SET OF NAMES (RATIONALE D-9).
       'identity.GroupTable' decodes the group to test ids and
       'identity.IdTable' decodes those to runs -- at the EDGE, for the
       few segments a query touched, never for the whole fold. Group 0 is
       the empty set: a stretch nobody executed carries a group like any
       other.

       WHAT IT IS FOR. Given the lines a change touched -- a diff --
       'of_change()' names the runs that executed them. That is the
       selection a tester wants after an edit.

       WHAT IT IS NOT. IT NAMES WHAT CERTAINLY TOUCHED THE CODE; IT NEVER
       CLAIMS THE REST IS SAFE. A test may depend on code it never
       executed: a branch that was deleted, a data file, a dynamic
       dispatch, a configuration, an absence. Selecting only these tests
       and calling the suite green is a FALSE GREEN -- the silent failure
       of PHILOSOPHY section 7, and the one that cannot report itself.
       Every face over this index says so, or it is lying by omission.
______________________________________________________________________________
"""
from bisect import bisect_right

from .record   import union
from .identity import (Origin, IdTable, GroupTable,      # noqa: F401
                       EMPTY_GROUP, IdentityFault)


class TestIndex:
    """LINE -> the runs that executed it, per source file.

    Built by 'index_of'. Holds the segmentation and the two tables that
    decode it; holds no record and no configuration.

    TWO LEVELS OF ANSWER. 'group_of_line' and 'id_set_of_ranges' work in
    NUMBERS -- what a machine wants. 'of_line', 'of_ranges' and
    'of_change' decode to Origins -- what a person wants. The decoding
    happens at the edge, on what a query touched.
    """

    def __init__(self, file_db, id_table, group_table):
        """RETURN: TestIndex over 'file_db': path -> (boundary_tuple,
        group_tuple), with the tables that decode it."""
        self.file_db     = file_db
        self.id_table    = id_table
        self.group_table = group_table

    @property
    def path_tuple(self):
        """RETURN: tuple of str, every source file the index knows,
        sorted."""
        return tuple(sorted(self.file_db))

    # ------------------------------------------------------- in numbers

    def group_of_line(self, path, line):
        """
        RETURN: int, the GROUP ID standing at that line -- 'EMPTY_GROUP'
                where nobody executed it, or where the file is unknown.
                A group is a value; absence of coverage is group 0, not
                a missing answer.
        """
        entry = self.file_db.get(path)
        if entry is None: return EMPTY_GROUP
        boundary_tuple, group_tuple = entry
        i = bisect_right(boundary_tuple, line) - 1
        if i < 0 or i >= len(group_tuple): return EMPTY_GROUP
        return group_tuple[i]

    def id_set_of_ranges(self, path, range_tuple):
        """
        RETURN: frozenset of int, every TEST ID that executed any line of
                those half-open ranges of that file.

        The hot path: bisect to the first segment, walk while it
        overlaps, union the decoded groups. No name is formed.
        """
        entry = self.file_db.get(path)
        if entry is None: return frozenset()
        boundary_tuple, group_tuple = entry

        result = set()
        for begin, end in union(range_tuple, ()):
            i = max(0, bisect_right(boundary_tuple, begin) - 1)
            while i < len(group_tuple) and boundary_tuple[i] < end:
                if boundary_tuple[i + 1] > begin \
                   and group_tuple[i] != EMPTY_GROUP:
                    result |= self.group_table.id_set_of(group_tuple[i])
                i += 1
        return frozenset(result)

    # --------------------------------------------------------- in names

    def origin_set_of(self, id_set):
        """
        RETURN: frozenset of Origin, the runs those test ids name.

        Raises IdentityFault on an id the table never allocated: an
        unresolvable id is an attribution nobody can check, and the empty
        set would read as 'nobody ran this'.
        """
        result = set()
        for test_id in id_set:
            origin = self.id_table.origin_of(test_id)
            if origin is None:
                raise IdentityFault("test id %s stands in the index but "
                                    "in no table" % test_id)
            result.add(origin)
        return frozenset(result)

    def of_line(self, path, line):
        """
        RETURN: frozenset of Origin, the runs that executed that line.
                Empty frozenset, where the line was executed by none --
                which is NOT a claim that no test depends on it.
        """
        group_id = self.group_of_line(path, line)
        if group_id == EMPTY_GROUP: return frozenset()
        return self.origin_set_of(self.group_table.id_set_of(group_id))

    def of_ranges(self, path, range_tuple):
        """
        RETURN: frozenset of Origin, every run that executed ANY line of
                the given half-open ranges of that file.
        """
        return self.origin_set_of(self.id_set_of_ranges(path, range_tuple))

    def of_change(self, change_db):
        """
        RETURN: tuple of Origin, sorted -- every run that executed any
                line the change touched.

        'change_db' maps a source file path to the half-open ranges the
        change touched, as a diff reports them.

        THIS IS A SUGGESTION, NEVER A CLEARANCE. A run absent from this
        answer may still be affected -- by a branch that was deleted, by
        data, by an absence. Running only these and calling the suite
        green is a false green.
        """
        id_set = set()
        for path, range_tuple in change_db.items():
            id_set |= self.id_set_of_ranges(path, range_tuple)
        return tuple(sorted(self.origin_set_of(id_set)))

    # ------------------------------------------------------- the shape

    def group_segment_iterable(self, path):
        """
        YIELD: [0] (begin, end)  one half-open segment of the file
               [1] int           its group id, 'EMPTY_GROUP' for nobody
        """
        entry = self.file_db.get(path)
        if entry is None: return
        boundary_tuple, group_tuple = entry
        for i, group_id in enumerate(group_tuple):
            yield (boundary_tuple[i], boundary_tuple[i + 1]), group_id

    def segment_iterable(self, path):
        """
        YIELD: [0] (begin, end)  one half-open segment of the file
               [1] frozenset of Origin, who executed it

        In line order. The rendering face of the index; the machine face
        is 'group_segment_iterable', which forms no name.
        """
        for span, group_id in self.group_segment_iterable(path):
            if group_id == EMPTY_GROUP:
                yield span, frozenset()
            else:
                yield span, self.origin_set_of(
                    self.group_table.id_set_of(group_id))


def index_of(pair_iterable, id_table=None, group_table=None):
    """
    RETURN: TestIndex over the (Origin, CoverageRecord) pairs given.

    Only the COVERED ranges enter: the index answers who EXECUTED a
    line. What was executable and never reached belongs to the coverage
    report, not to the selection.

    Segments carrying equal groups are FUSED, so a file that one test
    reaches whole costs one segment -- the same economy the record's
    intervals buy, kept through the fold.

    'id_table' and 'group_table' are parameters so that a caller which
    already holds them -- the bookkeeper, one day (disc-8) -- hands them
    in and keeps its ids stable across builds. Omitted, fresh ones are
    made and the ids live only as long as this index.
    """
    if id_table    is None: id_table    = IdTable()
    if group_table is None: group_table = GroupTable()

    event_db = {}
    for origin, record in pair_iterable:
        test_id = id_table.id_of(origin)
        for path, entry in record.file_db.items():
            event_list = event_db.setdefault(path, [])
            for begin, end in entry.covered:
                event_list.append((begin, 1, test_id))
                event_list.append((end, -1, test_id))

    file_db = {}
    for path, event_list in event_db.items():
        #  A CLOSE BEFORE AN OPEN at the same position: two ranges that
        #  merely touch must not appear to overlap for one line.
        event_list.sort(key=lambda e: (e[0], e[1], e[2]))

        #  SWEEP: the state AFTER every event position, in line order.
        state_list = []
        active     = {}
        i, n       = 0, len(event_list)
        while i < n:
            position = event_list[i][0]
            while i < n and event_list[i][0] == position:
                _, step, test_id = event_list[i]
                active[test_id] = active.get(test_id, 0) + step
                if active[test_id] == 0: del active[test_id]
                i += 1
            state_list.append((position,
                               group_table.group_of(frozenset(active))))

        #  SEGMENTS: what stands between two consecutive positions.
        segment_list = []
        for i in range(len(state_list) - 1):
            begin, group_id = state_list[i]
            end             = state_list[i + 1][0]
            if group_id == EMPTY_GROUP: continue
            if segment_list and segment_list[-1][1] == begin \
               and segment_list[-1][2] == group_id:
                segment_list[-1] = (segment_list[-1][0], end, group_id)
            else:
                segment_list.append((begin, end, group_id))
        if not segment_list: continue

        #  THE LOOKUP: one boundary array, one group per segment, a gap
        #  between two segments carried as group 0 so that the array
        #  stays contiguous and a query stays one bisect.
        boundary_list = [segment_list[0][0]]
        group_list    = []
        for begin, end, group_id in segment_list:
            if begin > boundary_list[-1]:
                boundary_list.append(begin)
                group_list.append(EMPTY_GROUP)
            boundary_list.append(end)
            group_list.append(group_id)

        file_db[path] = (tuple(boundary_list), tuple(group_list))

    return TestIndex(file_db, id_table, group_table)
