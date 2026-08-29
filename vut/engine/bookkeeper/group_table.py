"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE GROUP TABLE of one directory -- a SET OF RUNS carries a
         NUMBER, and the number survives everything.

DESCRIPTION
       A SET OF RUNS IS A GENERALITY (bookkeeper RATIONALE B-3), like
       the run itself ('test_run_id.py'): a coverage index attributes a
       stretch of code to one, a report names one, and whatever else
       asks 'which runs, as one number' asks here. So the interning
       stands with the runs' administrator, and every consumer refers
       downward to it.

           GroupTable   set of run keys  <->  group id

       GROUPS, not sets: whole regions of a code base are reached by
       exactly the same handful of runs, so a consumer pays for the
       DISTINCT set, not for every occurrence.

       GROUP 0 IS THE EMPTY SET, allocated by construction. A stretch
       nobody executed carries a group like any other -- a VALUE, not
       a hole, not an absence, not a null.

       A GROUP ID IS ISSUED ONCE AND NEVER AGAIN. The group scope is a
       THIRD id scope beside the register's two, counting from 0 on
       its own, its next id one above the highest ever issued, ceiling
       ID_LIMIT ('test_run_id.py'). The file carries the mark ('N:').
       Nothing removes a group: a set of runs that once existed is a
       fact, and a record that names its group must decode later.

       THE KEYS. In memory a table interns ANY hashable run key: a
       'TestRunId' for a fold over one directory, or whatever an
       aggregator qualifies run ids with when it folds across
       directories (coverage 'Gathered'). ONLY 'TestRunId' KEYS ARE
       STORED: a qualified key belongs to one aggregation and would
       freeze that invocation's view of the tree as identity (coverage
       RATIONALE D-14); 'format' refuses it by name.

       THE FILE is 'GOOD/group_ids.dat', beside the register, written
       the same way: atomically, left write-protected, on every
       allocation. A MISSING file reads as an empty table (a fresh
       directory); a DAMAGED one REFUSES BY NAME.

TWO SHAPES
       GroupTable    in memory; a fold that does not persist (a gather)
                     makes one and drops it
       GroupDb       a GroupTable bound to a directory's file
______________________________________________________________________________
"""
import os
import stat
from   pathlib import Path

from   .test_run_id import (TestRunId, RunIdFault, run_id_of_text,
                            ID_LIMIT)


FILE_NAME      = "group_ids.dat"
FORMAT_VERSION = "4"
EMPTY_GROUP    = 0


class GroupFault(RunIdFault):
    """A group that names nothing where a set was required, a table
    that cannot be read, or a scope that has issued its last id.

    A KIND OF 'RunIdFault', so a caller that catches the general one
    also catches this: a bad run id inside a group and a bad group are
    the same kind of trouble -- an attribution nobody can check."""
    pass


class GroupTable:
    """A SET OF RUN KEYS <-> a GROUP ID, in memory.

    Group 0 is the EMPTY set, allocated by construction.
    """

    def __init__(self):
        """RETURN: GroupTable holding only the empty group; the next
        group id is 1."""
        self._set_db    = {frozenset(): EMPTY_GROUP}
        self._group_db  = {EMPTY_GROUP: frozenset()}
        self._next      = EMPTY_GROUP + 1
        self.generation = 0        # bumped per write (coverage D-25)

    def __len__(self):
        """RETURN: int, how many distinct groups exist, the empty one
        included."""
        return len(self._group_db)

    def group_of(self, key_set, allocate_f=True):
        """
        RETURN: int, the group id of that set of run keys -- the
                standing one, or a freshly allocated one where
                'allocate_f'.
                None, where the set is unknown and allocation was not
                asked for.

        Raises GroupFault where the scope has reached ID_LIMIT.
        """
        key = frozenset(key_set)
        standing = self._set_db.get(key)
        if standing is not None:   return standing
        if not allocate_f:         return None

        if self._next >= ID_LIMIT:
            raise GroupFault("the group scope has issued %i ids; no "
                             "more are issued" % ID_LIMIT)
        group_id = self._next
        self._next += 1
        self._set_db[key]        = group_id
        self._group_db[group_id] = key
        self._allocated()
        return group_id

    def _allocated(self):
        """RETURN: None. What follows an allocation; nothing here, a
        persisting table writes its file."""
        return None

    def key_set_of(self, group_id):
        """
        RETURN: frozenset, the run keys of that group.

        Raises GroupFault on a group that was never allocated -- an
        unresolvable group in an index is an attribution nobody can
        check, and guessing the empty set would read as 'nobody ran
        this'.
        """
        standing = self._group_db.get(group_id)
        if standing is None:
            raise GroupFault("no group %s was ever allocated" % group_id)
        return standing

    def item_iterable(self):
        """
        YIELD: [0] int    the group id, ascending
               [1] tuple  its run keys, sorted BY THEIR SPELLING

        Sorted by 'str' rather than by the keys themselves: a printed
        answer must be stable, and nothing here should CRASH if a caller
        mixes key kinds; it should merely show them.
        """
        for group_id in sorted(self._group_db):
            yield group_id, tuple(sorted(self._group_db[group_id],
                                         key=str))

    def format(self):
        """
        RETURN: str, the table as it is stored:
                    'R:<generation>'             bumped per write
                    'N:<next group id>'          the scope's mark
                    'G:<id> <run ids, comma separated>'   per group,
                ascending; the empty group's line carries nothing
                after the id.

        Raises GroupFault where a group holds a key that is no
        'TestRunId': such a key belongs to one aggregation and is not
        stored.

        MACHINE-FREE: numbers only.
        """
        line_list = ["##VUT-TEST-GROUPS " + FORMAT_VERSION,
                     "R:%i" % self.generation,
                     "N:%i" % self._next]
        for group_id, key_tuple in self.item_iterable():
            for key in key_tuple:
                if not isinstance(key, TestRunId):
                    raise GroupFault(
                        "group %i holds a qualified key ('%s'); a "
                        "qualified table is ephemeral and is not stored"
                        % (group_id, key))
            body = ",".join(str(k) for k in key_tuple)
            line_list.append("G:%i %s" % (group_id, body) if body
                             else "G:%i" % group_id)
        return "\n".join(line_list) + "\n"

    def _parse(self, text):
        """
        RETURN: None; the table filled from 'text'.

        Raises GroupFault naming the first fault: no version, a version
        this build does not read (1 and 2 kept no mark and re-issued),
        no mark, a group at or above the mark, group 0 not empty, a
        member that spells no run id, a set standing twice.
        """
        seen      = False
        mark_seen = False
        for raw in text.splitlines():
            line = raw.strip()
            if not line: continue
            if line.startswith("##"):
                if line.startswith("##VUT-TEST-GROUPS"):
                    seen    = True
                    version = line[len("##VUT-TEST-GROUPS"):].strip()
                    if version != FORMAT_VERSION:
                        raise GroupFault(
                            "group-table version '%s' is not read; this "
                            "build writes %s. Versions 1 and 2 kept no "
                            "mark; version 3 kept no generation."
                            % (version or "<none>", FORMAT_VERSION))
                continue
            head, _, body = line.partition(" ")
            if head.startswith("R:"):
                try:               self.generation = int(head[2:])
                except ValueError: raise GroupFault(
                                       "'%s' spells no generation" % line) from None
                continue
            if head.startswith("N:"):
                if mark_seen:
                    raise GroupFault("the group mark stands twice")
                try:               mark = int(head[2:])
                except ValueError: raise GroupFault("'%s' spells no mark"
                                                    % line) from None
                if mark > ID_LIMIT:
                    raise GroupFault("mark '%s' lies beyond ID_LIMIT"
                                     % line)
                mark_seen  = True
                self._next = mark
                continue
            if not head.startswith("G:"):
                raise GroupFault("unknown group-table line '%s'" % line)
            try:               group_id = int(head[2:])
            except ValueError: raise GroupFault("'%s' spells no group id"
                                                % head) from None
            key_set = frozenset(run_id_of_text(word)
                                for word in body.split(",") if word.strip())
            if group_id == EMPTY_GROUP and key_set:
                raise GroupFault("group 0 is the empty set; it holds '%s'"
                                 % body)
            if group_id in self._group_db and group_id != EMPTY_GROUP:
                raise GroupFault("group %i stands twice" % group_id)
            if key_set in self._set_db and key_set:
                raise GroupFault("the set '%s' stands twice" % body)
            self._set_db[key_set]    = group_id
            self._group_db[group_id] = key_set

        if not seen:
            raise GroupFault("the table names no format version")
        if not mark_seen:
            raise GroupFault("the table carries no mark 'N:'")
        for group_id in self._group_db:
            if group_id != EMPTY_GROUP and group_id >= self._next:
                raise GroupFault("group %i lies at or above the mark %i"
                                 % (group_id, self._next))


def parse_group_table(text):
    """
    RETURN: GroupTable, what the text says, allocating onward from its
            mark.

    Raises GroupFault naming the first fault.
    """
    table = GroupTable()
    table._parse(text)
    return table


class GroupDb(GroupTable):
    """The group table of one directory: the one door to
    'GOOD/group_ids.dat'. Every allocation PERSISTS before it returns.
    """

    def __init__(self, directory):
        """
        RETURN: GroupDb over 'directory', loaded from its
                'GOOD/group_ids.dat'. A missing file reads as the empty
                table; a damaged one raises GroupFault naming the first
                fault.
        """
        super().__init__()
        self.directory = Path(directory)
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        self._parse(text)

    @property
    def path(self):
        """RETURN: Path, the one file of this table."""
        return self.directory / "GOOD" / FILE_NAME

    def _allocated(self):
        """
        RETURN: None. The whole file, replaced atomically and left
                write-protected -- the register's own treatment. The
                GENERATION is bumped first (coverage D-25).
        """
        self.generation += 1
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR
                           | stat.S_IRGRP | stat.S_IROTH)
        temporary = path.with_suffix(".dat.tmp")
        temporary.write_text(self.format(), encoding="utf-8")
        os.replace(temporary, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
