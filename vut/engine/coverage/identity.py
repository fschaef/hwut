"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHO RAN, as a number the REGISTER issued -- and a SET of runs
         as a number this component issues.

DESCRIPTION
       COVERAGE DOES NOT NAME TESTS AND DOES NOT NUMBER THEM. The
       register of a test directory does both
       ('bookkeeper/test_id_db.py', bookkeeper RATIONALE D-7):
       it holds 'app_id o--o name' and 'choice_id o--o name', issues
       the ids at first accept, and leaves them standing through a
       rename. What arrives here is the RESULT of that -- a
       'TestRunId' -- and what leaves here is the same, decoded to
       names by the register at the very edge, by whoever asked.

       ONE INTERNING REMAINS, and it is this component's own:

           GroupTable   set of run keys  <->  GROUP ID

       A segment of the line axis carries ONE INTEGER, its group. The
       older design interned TWICE, because a segment carrying test
       NAMES would carry them thousands of times; the register removed
       the first interning by issuing numbers itself, so only the SET
       interning is left. GROUPS, not sets, because whole regions of a
       code base are reached by exactly the same handful of runs: pay
       for the DISTINCT set, not for every occurrence.

       GROUP 0 IS THE EMPTY SET, allocated by construction. A stretch
       nobody executed carries a group like any other -- a VALUE, not
       a hole, not an absence, not a null.

TWO KEYS, TWO LIFETIMES (RATIONALE D-14 here, D-7 in the orchestrator)
       TestRunId   (app_id, choice_id|None)   PERSISTENT, per directory
       Gathered    (found-dir, TestRunId)     EPHEMERAL, per gather

       A run id is DIRECTORY-LOCAL: unique inside its own test
       directory by construction, meaningless outside it. A fold over
       ONE directory therefore takes run ids straight. A GATHER across
       directories qualifies at gather time -- the found-directory,
       relative to the gather root the caller chose -- and that
       qualification is never stored.

WHERE THE VALUE TYPE LIVES
       'TestRunId' is NOT this component's. A TEST RUN IS A GENERALITY
       -- the runner performs one, the base records one, a report names
       one -- so the shape stands with the runs' administrator, in the
       'bookkeeper' COMPONENT ('bookkeeper/test_run_id.py'), and this
       refers DOWNWARD to it like every other consumer. What is this
       component's own is 'Gathered' and the group interning: how a
       GATHER qualifies run ids across directories is a question only
       an aggregator asks.
______________________________________________________________________________
"""
from dataclasses import dataclass

from ..bookkeeper.test_run_id import (TestRunId,        # noqa: F401
                                      run_id_of_text, RunIdFault)


EMPTY_GROUP = 0


class IdentityFault(RunIdFault):
    """A group that names nothing where a set was required.

    A KIND OF 'RunIdFault' (bookkeeper), so a caller that catches the
    general one also catches this: a bad run id inside a group and a
    bad group are the same kind of trouble -- an attribution nobody
    can check."""
    pass


@dataclass(frozen=True, order=True)
class Gathered:
    """WHO ran, AS ONE GATHER SAW IT: a directory beside a run id.

    EPHEMERAL, NEVER STORED. 'directory' is relative to the GATHER
    ROOT, chosen by the aggregator that FOUND the record, so it is
    exactly as transient as that choice of root. Two gathers from two
    roots may spell one run differently; the run id inside does not
    move.

    None as 'directory' spells a record found AT the root.
    """
    directory: str | None
    run_id:    TestRunId

    def __str__(self):
        """RETURN: str, 'directory:run_id', or the run id's own
        spelling where the record stood at the root."""
        return str(self.run_id) if self.directory is None \
               else "%s:%s" % (self.directory, self.run_id)


class GroupTable:
    """A SET OF RUN KEYS <-> a GROUP ID.

    A 'run key' is a TestRunId, or a Gathered where the fold spans
    directories; this table does not care which, and never forms one.

    Group 0 is the EMPTY set, allocated by construction: a stretch
    nobody executed carries a group like any other, and a query needs
    no special case for 'nobody'.
    """

    def __init__(self):
        """RETURN: GroupTable holding only the empty group."""
        self._set_db   = {frozenset(): EMPTY_GROUP}
        self._group_db = {EMPTY_GROUP: frozenset()}
        self._next     = EMPTY_GROUP + 1

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
        """
        key = frozenset(key_set)
        standing = self._set_db.get(key)
        if standing is not None:   return standing
        if not allocate_f:         return None

        group_id = self._next
        self._next += 1
        self._set_db[key]        = group_id
        self._group_db[group_id] = key
        return group_id

    def key_set_of(self, group_id):
        """
        RETURN: frozenset, the run keys of that group.

        Raises IdentityFault on a group that was never allocated -- an
        unresolvable group in an index is an attribution nobody can
        check, and guessing the empty set would read as 'nobody ran
        this'.
        """
        standing = self._group_db.get(group_id)
        if standing is None:
            raise IdentityFault("no group %s was ever allocated"
                                % group_id)
        return standing

    def item_iterable(self):
        """
        YIELD: [0] int    the group id, ascending
               [1] tuple  its run keys, sorted BY THEIR SPELLING

        Sorted by 'str' rather than by the keys themselves: a printed
        answer must be stable, and a fold is one-directory or a gather
        -- but nothing here should CRASH if a caller mixes the two, it
        should merely show them.
        """
        for group_id in sorted(self._group_db):
            yield group_id, tuple(sorted(self._group_db[group_id],
                                         key=str))

    def format(self):
        """
        RETURN: str, the table as it is stored: 'G:<id> <run ids, comma
                separated>' per group, ascending; the empty group's
                line carries nothing after the space.

        Raises IdentityFault where a group holds a GATHERED key: that
        key belongs to one aggregation (D-14) and storing it would
        freeze one invocation's view of the tree as if it were
        identity.
        """
        line_list = ["##VUT-TEST-GROUPS 2"]
        for group_id, key_tuple in self.item_iterable():
            for key in key_tuple:
                if not isinstance(key, TestRunId):
                    raise IdentityFault(
                        "group %i holds a gathered key ('%s'); a "
                        "gathered table is ephemeral and is not stored"
                        % (group_id, key))
            body = ",".join(str(k) for k in key_tuple)
            line_list.append("G:%i %s" % (group_id, body) if body
                             else "G:%i" % group_id)
        return "\n".join(line_list) + "\n"


def parse_group_table(text):
    """
    RETURN: GroupTable, what the text says, allocating onward from one
            above the highest group it read.

    Raises IdentityFault naming the first fault.
    """
    table   = GroupTable()
    seen    = False
    highest = EMPTY_GROUP
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("##"):
            if line.startswith("##VUT-TEST-GROUPS"):
                seen    = True
                version = line[len("##VUT-TEST-GROUPS"):].strip()
                if version != "2":
                    raise IdentityFault(
                        "group-table version '%s' is not read; this "
                        "build writes 2. Version 1 held ids this "
                        "component interned itself; a group holds RUN "
                        "IDS now (D-7)." % (version or "<none>"))
            continue
        if not line.startswith("G:"):
            raise IdentityFault("unknown group-table line '%s'" % line)
        head, _, body = line[2:].partition(" ")
        try:               group_id = int(head)
        except ValueError: raise IdentityFault("'%s' spells no group id"
                                               % head)
        key_set = frozenset(run_id_of_text(word)
                            for word in body.split(",") if word.strip())
        table._set_db[key_set]    = group_id
        table._group_db[group_id] = key_set
        highest = max(highest, group_id)

    if not seen:
        raise IdentityFault("the table names no format version")
    table._next = highest + 1
    return table
