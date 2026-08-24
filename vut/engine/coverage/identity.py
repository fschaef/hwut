"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TWO INTERNINGS -- a run becomes a NUMBER, and a SET of runs
         becomes a number.

DESCRIPTION
       A segmentation that carried Origins would carry the same test
       NAME thousands of times, and a rename would have to rewrite every
       record that ever mentioned it. Two tables remove both:

           IdTable      Origin  <-> TEST ID     one number per run
           GroupTable   set of TEST IDs <-> GROUP ID

       A segment then carries ONE INTEGER. A query reads the group id,
       the GroupTable decodes it to test ids, and the IdTable decodes
       those to names -- at the edge, once, for the few segments a query
       actually touched.

       WHY GROUPS AND NOT SETS. The number of DISTINCT origin sets in a
       suite is far smaller than the number of segments: whole regions of
       a code base are reached by exactly the same handful of tests.
       Interning the set is therefore the same trick the intervals are --
       pay for the DISTINCT thing, not for every occurrence.

       GROUP 0 IS THE EMPTY SET, always, allocated by construction. A
       stretch nobody executed is group 0, and that is a VALUE -- not a
       hole, not an absence, not a null.

THE TWO LAWS OF A TEST ID
       (1) AN ID IS NEVER REUSED. Allocation is monotone and a retired
           id keeps its entry. Reuse would make an OLD record point
           silently at a DIFFERENT test -- a false attribution, and the
           kind that reports nothing.
       (2) A RENAME KEEPS THE ID. The name is an attribute of the entry,
           never the identity. That is the whole point of the interning:
           a rename touches ONE table, not every record.

WHOSE TABLE IS IT
       THE BOOKKEEPER'S, eventually: it already owns the naming of a test
       directory, and a rename service must go through the same door or
       there are two truths. This module holds the MECHANISM and a
       serialisation; it deliberately does NOT reach into the
       bookkeeper's base. Which side allocates, and at what scope, is
       DISCUSSIONS disc-8 -- and settling it edits the bookkeeper, so it
       waits for a quiet tree.
______________________________________________________________________________
"""
from dataclasses import dataclass, replace


EMPTY_GROUP = 0


class IdentityFault(ValueError):
    """An id table that cannot be read, or an id that names nothing where
    a name was required. Named where it is met: an unresolvable id in a
    coverage index is a report attributing work to a test that may not be
    the one that did it."""
    pass


@dataclass(frozen=True, order=True)
class Origin:
    """WHO ran: the key a record is stored under, plus the place it was
    stored.

    'directory' is supplied by the AGGREGATOR, not by the record: a
    record's paths are relative to its test directory and name no
    machine (RATIONALE D-4), so what disambiguates two 'core.py' comes
    from where the aggregator FOUND it. None where one directory is
    indexed and nothing needs disambiguating.
    """
    directory: str | None
    test:      str
    choice:    str | None

    def __str__(self):
        """RETURN: str, 'directory:test--choice', the parts that exist."""
        stem = self.test if self.choice is None \
               else "%s--%s" % (self.test, self.choice)
        return stem if self.directory is None \
               else "%s:%s" % (self.directory, stem)


@dataclass(frozen=True)
class Entry:
    """ONE test id's entry: who it is, and whether it still exists.

    'retired' marks a run that is gone -- deleted, or renamed out of
    existence. The entry STAYS so that an old record still decodes to
    the run that made it; only forward lookup stops finding it.
    """
    origin:  Origin
    retired: bool = False


class IdTable:
    """TEST ID <-> Origin, with the two laws: no reuse, rename keeps the
    id.

    'first_id' exists so that a caller which partitions the id space --
    one range per directory, say -- can say so. Ids are allocated
    monotonically from it and never handed out twice.
    """

    def __init__(self, first_id=1):
        """RETURN: IdTable, empty, allocating from 'first_id'."""
        self._entry_db = {}      # id -> Entry
        self._id_db    = {}      # Origin -> id   (LIVE entries only)
        self._next     = first_id

    def __len__(self):
        """RETURN: int, how many ids were ever allocated, retired ones
        included."""
        return len(self._entry_db)

    def id_of(self, origin, allocate_f=True):
        """
        RETURN: int, the id of 'origin' -- the standing one, or a freshly
                allocated one where 'allocate_f'.
                None, where it is unknown and allocation was not asked
                for.
        """
        standing = self._id_db.get(origin)
        if standing is not None:   return standing
        if not allocate_f:         return None

        test_id = self._next
        self._next += 1
        self._entry_db[test_id] = Entry(origin)
        self._id_db[origin]     = test_id
        return test_id

    def origin_of(self, test_id):
        """
        RETURN: Origin, whose id that is -- RETIRED ONES INCLUDED, so an
                old record still decodes.
                None, where the id was never allocated.
        """
        entry = self._entry_db.get(test_id)
        return None if entry is None else entry.origin

    def is_retired(self, test_id):
        """
        RETURN: True,  that id names a run that no longer exists.
                False, it is live.
                None,  the id was never allocated -- which is not the
                       same as retired, and must not read as one.
        """
        entry = self._entry_db.get(test_id)
        return None if entry is None else entry.retired

    def rename(self, test_id, test=None, choice=None, directory=None):
        """
        RETURN: Origin, the entry's new one. THE ID IS UNCHANGED -- that
                is the whole purpose of the interning: a rename touches
                this table and no record anywhere.

        Only the parts given are changed. A rename onto an Origin that
        another LIVE id already holds is refused: two live ids for one
        run would make 'which id is this test' unanswerable.

        Raises IdentityFault on an unknown id, or on a collision.
        """
        entry = self._entry_db.get(test_id)
        if entry is None:
            raise IdentityFault("no test id %s was ever allocated" % test_id)

        fresh = replace(entry.origin,
                        **{k: v for k, v in (("test", test),
                                             ("choice", choice),
                                             ("directory", directory))
                           if v is not None})
        standing = self._id_db.get(fresh)
        if standing is not None and standing != test_id:
            raise IdentityFault(
                "renaming id %s to '%s' collides with live id %s"
                % (test_id, fresh, standing))

        self._id_db.pop(entry.origin, None)
        self._entry_db[test_id] = Entry(fresh, entry.retired)
        if not entry.retired: self._id_db[fresh] = test_id
        return fresh

    def retire(self, test_id):
        """
        RETURN: Origin, the run that is now gone.

        The entry STAYS -- an old record must still decode -- but the
        forward lookup stops finding it, and the id is never handed out
        again. Retiring twice is not a fault; it is already true.

        Raises IdentityFault on an unknown id.
        """
        entry = self._entry_db.get(test_id)
        if entry is None:
            raise IdentityFault("no test id %s was ever allocated" % test_id)
        self._id_db.pop(entry.origin, None)
        self._entry_db[test_id] = Entry(entry.origin, True)
        return entry.origin

    def item_iterable(self):
        """
        YIELD: [0] int    the test id, ascending
               [1] Entry  its entry, retired ones included
        """
        for test_id in sorted(self._entry_db):
            yield test_id, self._entry_db[test_id]

    def format(self):
        """
        RETURN: str, the table as it is stored: one line per id,
                'T:<id> <flag> <directory>|<test>|<choice>', ascending.
                '-' spells an absent directory or the choice-less test,
                '!' marks a retired entry and '.' a live one.

        MACHINE-FREE like everything else here: names and numbers, no
        paths outside the tree, no timestamps.
        """
        line_list = ["##VUT-TEST-IDS 1"]
        for test_id, entry in self.item_iterable():
            origin = entry.origin
            line_list.append(
                "T:%i %s %s|%s|%s"
                % (test_id, "!" if entry.retired else ".",
                   origin.directory if origin.directory is not None else "-",
                   origin.test,
                   origin.choice if origin.choice is not None else "-"))
        return "\n".join(line_list) + "\n"


def parse_id_table(text):
    """
    RETURN: IdTable, what the text says -- retired entries included, and
            allocating onward from ONE ABOVE THE HIGHEST id it read, so
            that reading and writing a table can never reissue an id.

    Raises IdentityFault naming the first fault.
    """
    table   = IdTable()
    seen    = False
    highest = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("##"):
            if line.startswith("##VUT-TEST-IDS"): seen = True
            continue
        if not line.startswith("T:"):
            raise IdentityFault("unknown id-table line '%s'" % line)
        head, _, body = line[2:].partition(" ")
        try:               test_id = int(head)
        except ValueError: raise IdentityFault("'%s' spells no id" % head)
        flag, _, names = body.strip().partition(" ")
        if flag not in (".", "!"):
            raise IdentityFault("id %i carries no live/retired flag"
                                % test_id)
        part_list = names.split("|")
        if len(part_list) != 3:
            raise IdentityFault("id %i names no directory|test|choice"
                                % test_id)
        directory, test, choice = part_list
        origin = Origin(None if directory == "-" else directory,
                        test,
                        None if choice == "-" else choice)
        if test_id in table._entry_db:
            raise IdentityFault("id %i stands twice" % test_id)
        table._entry_db[test_id] = Entry(origin, flag == "!")
        if flag == ".": table._id_db[origin] = test_id
        highest = max(highest, test_id)

    if not seen:
        raise IdentityFault("the table names no format version")
    table._next = highest + 1
    return table


class GroupTable:
    """A SET OF TEST IDS <-> a GROUP ID.

    Group 0 is the EMPTY set, allocated by construction: a stretch
    nobody executed carries a group like any other, and the query needs
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

    def group_of(self, id_set, allocate_f=True):
        """
        RETURN: int, the group id of that set of test ids -- the standing
                one, or a freshly allocated one where 'allocate_f'.
                None, where the set is unknown and allocation was not
                asked for.
        """
        key = frozenset(id_set)
        standing = self._set_db.get(key)
        if standing is not None:   return standing
        if not allocate_f:         return None

        group_id = self._next
        self._next += 1
        self._set_db[key]        = group_id
        self._group_db[group_id] = key
        return group_id

    def id_set_of(self, group_id):
        """
        RETURN: frozenset of int, the test ids of that group.

        Raises IdentityFault on a group that was never allocated -- an
        unresolvable group in an index is an attribution nobody can
        check, and guessing the empty set would read as 'nobody ran
        this'.
        """
        standing = self._group_db.get(group_id)
        if standing is None:
            raise IdentityFault("no group %s was ever allocated" % group_id)
        return standing

    def item_iterable(self):
        """
        YIELD: [0] int   the group id, ascending
               [1] tuple of int, its test ids, ascending
        """
        for group_id in sorted(self._group_db):
            yield group_id, tuple(sorted(self._group_db[group_id]))

    def format(self):
        """
        RETURN: str, the table as it is stored: 'G:<id> <ids, comma
                separated>' per group, ascending; the empty group's line
                carries no id after the space.
        """
        line_list = ["##VUT-TEST-GROUPS 1"]
        for group_id, id_tuple in self.item_iterable():
            body = ",".join("%i" % i for i in id_tuple)
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
            if line.startswith("##VUT-TEST-GROUPS"): seen = True
            continue
        if not line.startswith("G:"):
            raise IdentityFault("unknown group-table line '%s'" % line)
        head, _, body = line[2:].partition(" ")
        try:               group_id = int(head)
        except ValueError: raise IdentityFault("'%s' spells no group id"
                                               % head)
        try:
            id_set = frozenset(int(x) for x in body.split(",") if x.strip())
        except ValueError:
            raise IdentityFault("group %i names something that is no id"
                                % group_id)
        table._set_db[id_set]        = group_id
        table._group_db[group_id]    = id_set
        highest = max(highest, group_id)

    if not seen:
        raise IdentityFault("the table names no format version")
    table._next = highest + 1
    return table
