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

       THE RUN KEY IS WHATEVER THE FOLD WAS GIVEN, and the REGISTER
       issued it (orchestrator D-7). One directory's fold hands in
       'TestRunId's; a GATHER across directories hands in 'Gathered'
       keys -- a found-directory beside a run id, formed at gather time
       and living exactly as long as the aggregation (D-14). The index
       interns SETS of either; it numbers no test itself.

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
       The bookkeeper's 'GroupTable' decodes the group to run keys and
       its register decodes those to names -- at the EDGE, for the few
       segments a query touched, never for the whole fold. Group 0 is
       the empty set: a stretch nobody executed carries a group like any
       other.

       TWO RUN KEYS, TWO LIFETIMES (RATIONALE D-14, D-17):
           TestRunId   (app_id, choice_id|None)   PERSISTENT, per directory
           Gathered    (found-dir, TestRunId)     EPHEMERAL, per gather
       A run id is DIRECTORY-LOCAL. A fold over ONE directory takes run
       ids straight, and its group table may be the directory's own
       persisted one ('GroupDb'). A GATHER across directories qualifies
       at gather time -- the found-directory, relative to the gather
       root the caller chose -- into a 'Gathered', folds into a fresh
       in-memory table, and stores neither (todo-10).

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
import os
import sys
from bisect      import bisect_right
from dataclasses import dataclass

from .binary  import unpack_record
from .record  import (union, CoverageRecord, FileCoverage, RecordFault)
from ...bookkeeper.api import TestRunId          # noqa: F401
from ...bookkeeper.api import (GroupTable,       # noqa: F401
                                      EMPTY_GROUP, GroupFault)


RECORD_SUFFIX = ".cover"        # binary (D-20); 'hwut.cov convert' shows it


@dataclass(frozen=True, order=True)
class Gathered:
    """WHO ran, AS ONE GATHER SAW IT: a directory beside a run id.

    EPHEMERAL, NEVER STORED. 'directory' is relative to the GATHER
    ROOT, chosen by the aggregator that FOUND the record, so it is
    exactly as transient as that choice of root. Two gathers from two
    roots may spell one run differently; the run id inside does not
    move. The bookkeeper's group table refuses it for storage.

    None as 'directory' spells a record found AT the root.
    """
    directory: str | None
    run_id:    TestRunId

    def __str__(self):
        """RETURN: str, 'directory:run_id', or the run id's own
        spelling where the record stood at the root."""
        return str(self.run_id) if self.directory is None \
               else "%s:%s" % (self.directory, self.run_id)


class TestIndex:
    """LINE -> the runs that executed it, per source file.

    Built by 'index_of'. Holds the segmentation and the two tables that
    decode it; holds no record and no configuration.

    TWO LEVELS OF ANSWER. 'group_of_line' works in GROUP numbers --
    the compact form a query bisects for. 'of_line', 'of_ranges' and
    'of_change' decode the group to RUN KEYS. Decoding a run key to a
    NAME is the REGISTER's, at the edge, by whoever asked -- this
    holds no name.
    """

    def __init__(self, file_db, group_table):
        """RETURN: TestIndex over 'file_db': path -> (boundary_tuple,
        group_tuple), with the table that decodes a group."""
        self.file_db     = file_db
        self.group_table = group_table

    @property
    def run_key_set(self):
        """RETURN: frozenset, every run key the index knows."""
        result = set()
        for _, key_tuple in self.group_table.item_iterable():
            result |= set(key_tuple)
        return frozenset(result)

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

    def key_set_of_ranges(self, path, range_tuple):
        """
        RETURN: frozenset, every RUN KEY that executed any line of those
                half-open ranges of that file.

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
                    result |= self.group_table.key_set_of(group_tuple[i])
                i += 1
        return frozenset(result)

    # ------------------------------------------------------ in run keys

    def of_line(self, path, line):
        """
        RETURN: frozenset of run key, the runs that executed that line.
                Empty frozenset, where the line was executed by none --
                which is NOT a claim that no test depends on it.
        """
        group_id = self.group_of_line(path, line)
        if group_id == EMPTY_GROUP: return frozenset()
        return self.group_table.key_set_of(group_id)

    def of_ranges(self, path, range_tuple):
        """
        RETURN: frozenset of run key, every run that executed ANY line
                of the given half-open ranges of that file.
        """
        return self.key_set_of_ranges(path, range_tuple)

    def of_change(self, change_db):
        """
        RETURN: tuple of run key, sorted -- every run that executed any
                line the change touched.

        'change_db' maps a source file path to the half-open ranges the
        change touched, as a diff reports them.

        THIS IS A SUGGESTION, NEVER A CLEARANCE. A run absent from this
        answer may still be affected -- by a branch that was deleted, by
        data, by an absence. Running only these and calling the suite
        green is a false green.
        """
        key_set = set()
        for path, range_tuple in change_db.items():
            key_set |= self.key_set_of_ranges(path, range_tuple)
        return tuple(sorted(key_set))

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
               [1] frozenset of run key, who executed it

        In line order. The rendering face of the index; the machine
        face is 'group_segment_iterable', which decodes nothing.
        """
        for span, group_id in self.group_segment_iterable(path):
            if group_id == EMPTY_GROUP:
                yield span, frozenset()
            else:
                yield span, self.group_table.key_set_of(group_id)


def index_of(pair_iterable, group_table=None):
    """
    RETURN: TestIndex over the (run key, CoverageRecord) pairs given --
            a run key being a TestRunId, or a Gathered where the fold
            spans directories.

    Only the COVERED ranges enter: the index answers who EXECUTED a
    line. What was executable and never reached belongs to the coverage
    report, not to the selection.

    Segments carrying equal groups are FUSED, so a file that one test
    reaches whole costs one segment -- the same economy the record's
    intervals buy, kept through the fold.

    THE RUN KEYS ARE NOT INVENTED HERE. The REGISTER issued them
    (orchestrator D-7); this folds over what it was given and never
    numbers a test itself.

    'group_table' is a parameter so that a caller folding ONE directory
    hands in its persisted 'GroupDb' and a caller folding several keeps
    ONE table across them. Omitted, a fresh one is made and the group
    ids live as long as this index.

    THE PAIRS ARRIVE SORTED BY KEY or the GROUP ids are not
    reproducible: two gathers over one tree must allocate identically,
    so the CALLER orders (D-14). This function trusts the order given.
    """
    if group_table is None: group_table = GroupTable()

    event_db = {}
    for run_key, record in pair_iterable:
        for path, entry in record.file_db.items():
            event_list = event_db.setdefault(path, [])
            for begin, end in entry.covered:
                event_list.append((begin, 1, run_key))
                event_list.append((end, -1, run_key))

    file_db = {}
    for path, event_list in event_db.items():
        #  A CLOSE BEFORE AN OPEN at the same position: two ranges that
        #  merely touch must not appear to overlap for one line.
        event_list.sort(key=lambda e: (e[0], e[1], str(e[2])))

        #  SWEEP: the state AFTER every event position, in line order.
        state_list = []
        active     = {}
        i, n       = 0, len(event_list)
        while i < n:
            position = event_list[i][0]
            while i < n and event_list[i][0] == position:
                _, step, run_key = event_list[i]
                active[run_key] = active.get(run_key, 0) + step
                if active[run_key] == 0: del active[run_key]
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

    return TestIndex(file_db, group_table)


# ---------------------------------------------------------------- records
#
#  'record_iterable' and 'rebased' moved to 'database/index.py'
#  (session 2026-09-04): 'gather.py' needs them too, and a database-
#  side module importing this face -- built ON the database api --
#  was backwards. Re-exported below so nothing else in this module
#  changes.

def record_iterable(root, suffix=RECORD_SUFFIX):
    """
    YIELD: [0] Gathered         who made the record, AS THIS GATHER SEES
                                IT: a RUN ID the record's own header
                                names, qualified by the DIRECTORY it was
                                found in, relative to 'root'. The
                                qualification is THIS gather's and is
                                never stored (D-14).
           [1] CoverageRecord   what it says

    THE RECORD CARRIES ITS OWN IDS (D-18), so nothing here resolves a
    name: the register issued them and only the EDGE that prints an
    answer needs it to decode. A MERGED record names several runs and
    is yielded once per run -- the fold is over runs, and an aggregate
    that reached a line means every run in it reached that line.

    THE WALK IS SORTED so that the fold allocates group ids identically
    from any two invocations over one tree: found-directory first, then
    the record file's name, then the run id.

    THE SEAM. The store's naming is the BOOKKEEPER'S; walking for a
    suffix is a stand-in until this face can ask it. Nothing else in this
    module knows where a record lives.

    A file that does not parse is SKIPPED and named on stderr, and so is
    one that names NO run -- it cannot be attributed, and attributing it
    to a guess is worse than losing it. One broken record must not cost
    the whole selection, and it must not vanish either.
    """
    for base, dir_list, file_list in sorted(os.walk(root)):
        dir_list[:] = sorted(d for d in dir_list if not d.startswith("."))
        for name in sorted(file_list):
            if not name.endswith(suffix): continue
            path = os.path.join(base, name)
            try:
                with open(path, "rb") as handle:
                    record = unpack_record(handle.read())
            except (OSError, RecordFault) as fault:
                sys.stderr.write("skipped '%s': %s\n" % (path, fault))
                continue
            relative  = os.path.relpath(base, root).replace(os.sep, "/")
            directory = None if relative == "." else relative
            if not record.run:
                sys.stderr.write("skipped '%s': the record names no run\n"
                                 % path)
                continue
            for run_id in sorted(record.run):
                yield (Gathered(directory, run_id),
                       rebased(record, directory))


def rebased(record, directory):
    """
    RETURN: CoverageRecord, the same record with every source path made
            relative to the ROOT instead of to its test directory.

    'parser/TEST' + '../core.py' -> 'parser/core.py'. Without this the
    diff's paths and the record's paths never meet, and every query
    answers 'nobody' -- an empty selection that looks like an answer, and
    therefore the worst possible failure of this face.

    A record found AT the root ('directory' None) is already root
    relative and is handed back untouched.
    """
    if directory is None: return record
    file_db = {}
    for path, entry in record.file_db.items():
        fresh = os.path.normpath(os.path.join(directory, path))
        fresh = fresh.replace(os.sep, "/")
        file_db[fresh] = FileCoverage(fresh, entry.executable,
                                      entry.covered, entry.counts)
    return CoverageRecord(language=record.language, tool=record.tool,
                          source=record.source, counts_f=record.counts_f,
                          file_db=file_db, version=record.version,
                          run=record.run)

