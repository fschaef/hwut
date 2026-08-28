#! /usr/bin/env python3
#
# @hwut {
#     title      = "The group table: a set of runs is a number, issued once"
#     choices    = ["faults", "groups", "persisted", "tables"]
#     eq-pattern = ["SUCCESS.*"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE GROUP TABLE -- a SET of runs becomes a number, the number
         is issued once, and the table lives in one write-protected
         file.

CHOICES: groups, tables, persisted, faults;

groups     a set of run keys becomes one integer, because whole regions
           of a code base are reached by exactly the same handful of
           runs: pay for the DISTINCT set, not for every occurrence.
           Group 0 is the empty set, by construction; the scope counts
           on from 1, monotonically, and the ceiling refuses by name.

tables     the group table written and read back; a round trip is
           byte-stable and allocates onward from the MARK it read.

persisted  'GroupDb' writes 'GOOD/group_ids.dat' on every allocation
           and reads it back; a reload does not lower the mark.

faults     a group that names nothing, a table without a version or
           mark, a line that spells no run id, a group at its mark, a
           qualified key offered for storage. Each refused by name --
           and the NAME says which layer caught it: 'RunIdFault' on the
           shape of a run id, 'GroupFault' on a group. The second is a
           kind of the first.

WHAT MOVED IN. This table was the coverage component's 'identity.py'
(coverage RATIONALE D-15) until a set of runs was recognised as no more
a coverage concept than a run is (bookkeeper B-3). What stayed there
is 'Gathered', the aggregator's qualification of a run id, tested in
'coverage/TEST/test-index.py'.
______________________________________________________________________________
"""
import os
import shutil
import stat
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.bookkeeper.test_run_id import (TestRunId,      # noqa E402
                                                 ID_LIMIT)
from   vut.engine.bookkeeper.group_table import (GroupTable,     # noqa E402
                                                 GroupDb,
                                                 EMPTY_GROUP,
                                                 FILE_NAME,
                                                 parse_group_table)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """
    RETURN: True,  every claim held.
            False, at least one did not.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def raised(action):
    """
    RETURN: str, the name of the exception 'action' raised.
            'nothing', where it raised none.
    """
    try:               action()
    except Exception as fault: return type(fault).__name__
    return "nothing"


A = TestRunId(0, 0)
B = TestRunId(0, 1)


class Qualified:
    """A run key that is NOT a TestRunId -- what an aggregator across
    directories hands in. Hashable, spelled, never stored."""
    def __init__(self, directory, run_id):
        self.directory, self.run_id = directory, run_id

    def __hash__(self):     return hash((self.directory, self.run_id))
    def __eq__(self, o):    return (self.directory, self.run_id) \
                                   == (o.directory, o.run_id)
    def __str__(self):      return "%s:%s" % (self.directory, self.run_id)


def filled(table=None):
    """RETURN: GroupTable holding {A}, {A,B} and {B}, in that order --
    three distinct sets, and the empty one by construction."""
    if table is None: table = GroupTable()
    for key_set in ({A}, {A, B}, {B}): table.group_of(key_set)
    return table


# ---------------------------------------------------------------------------

def test_groups():
    """A set of ids becomes one integer."""
    table = GroupTable()
    banner("the empty group exists by construction")
    print("INSPECT: group of the empty set -> %s"
          % table.group_of(frozenset()))
    print("         group %s decodes to %s"
          % (EMPTY_GROUP, set(table.key_set_of(EMPTY_GROUP)) or "{}"))

    banner("three distinct sets, three groups")
    g_a  = table.group_of({A})
    g_ab = table.group_of({A, B})
    g_b  = table.group_of({B})
    print("INSPECT: {A} -> %s   {A,B} -> %s   {B} -> %s" % (g_a, g_ab, g_b))

    banner("the SAME set, whatever order or container it arrives in")
    print("INSPECT: [B,A] -> %s   frozenset({B,A}) -> %s"
          % (table.group_of([B, A]), table.group_of(frozenset({B, A}))))
    print("         the table holds %i group(s)" % len(table))

    banner("the ceiling")
    full = GroupTable()
    full._next = ID_LIMIT
    ceiling = raised(lambda: full.group_of({A}))
    print("INSPECT: a scope at ID_LIMIT asked to issue -> %s" % ceiling)

    ok = check([
        (table.group_of(frozenset()) == EMPTY_GROUP,
         "the empty set is group 0 -- a value, not a hole"),
        (table.key_set_of(EMPTY_GROUP) == frozenset(),
         "and it decodes to nothing"),
        ((g_a, g_ab, g_b) == (1, 2, 3),
         "distinct sets get distinct groups, monotonically from 1"),
        (table.group_of([B, A]) == g_ab
         and table.group_of(frozenset({B, A})) == g_ab,
         "one set is one group, whatever order or container it came in"),
        (len(table) == 4,
         "three sets plus the empty one -- nothing was allocated twice"),
        (table.group_of({TestRunId(7)}, allocate_f=False) is None,
         "an unknown set can be asked without being allocated"),
        (table.key_set_of(g_ab) == frozenset({A, B}),
         "a group decodes to its keys"),
        (raised(lambda: table.key_set_of(99)) == "GroupFault",
         "a group that was never allocated is refused, never answered "
         "with the empty set -- that would read as 'nobody ran this'"),
        (ceiling == "GroupFault",
         "the 2**32nd group is refused by name"),
    ])
    verdict(ok, "pay for the distinct set, not for every occurrence.")


def test_tables():
    """The group table written, read back, and written again."""
    table = filled()
    text  = table.format()

    banner("the group table, as it is stored")
    for line in text.splitlines(): print("         | %s" % line)

    back     = parse_group_table(text)
    stable_f = back.format() == text        # BEFORE anything is added
    banner("read back")
    for group_id, key_tuple in back.item_iterable():
        print("         %s -> %s"
              % (group_id, ", ".join(str(k) for k in key_tuple) or "{}"))

    banner("the next allocation is the MARK that was read")
    fresh = back.group_of({TestRunId(9)})
    print("INSPECT: -> %s" % fresh)

    banner("a QUALIFIED key has no place in a stored table")
    gathered = GroupTable()
    gathered.group_of({Qualified("other/TEST", A)})
    print("         raised %s" % raised(gathered.format))

    ok = check([
        (stable_f,
         "format(parse(format(x))) == format(x) -- the bytes are "
         "stable"),
        (back.key_set_of(1) == frozenset({A}),
         "a group decodes to the run ids it was made of"),
        (back.key_set_of(EMPTY_GROUP) == frozenset(),
         "the empty group survives the round trip"),
        (fresh == 4,
         "reading a table allocates onward from its mark"),
        (raised(gathered.format) == "GroupFault",
         "storing a qualified key is refused: it belongs to ONE "
         "aggregation and would freeze that view as identity"),
    ])
    verdict(ok, "one table, stable bytes, and nothing ephemeral in it.")


def test_persisted():
    """'GroupDb' over a directory: the file, and the mark across reloads."""
    directory = tempfile.mkdtemp()
    db = GroupDb(directory)
    banner("a fresh directory")
    print("INSPECT: %i group(s); file on disk: %s"
          % (len(db), os.path.isfile(db.path)))

    filled(db)
    banner("after three allocations")
    print("INSPECT: file on disk: %s" % os.path.isfile(db.path))
    for line in db.path.read_text().splitlines():
        print("         | %s" % line)
    protected_f = not (os.stat(db.path).st_mode & stat.S_IWUSR)

    back  = GroupDb(directory)
    fresh = back.group_of({TestRunId(1)})
    banner("reloaded, then one more")
    print("INSPECT: group of {1} -> %s; {A,B} still -> %s"
          % (fresh, back.group_of({A, B}, allocate_f=False)))

    ok = check([
        (os.path.isfile(os.path.join(directory, "GOOD", FILE_NAME)),
         "the file is on disk the moment the first group is born"),
        (protected_f, "and left write-protected"),
        (back.group_of({A, B}, allocate_f=False) == 2,
         "a reload decodes what was stored"),
        (fresh == 4,
         "the mark is persisted: a reload does not lower it"),
        (GroupDb(directory).group_of({TestRunId(1)}, allocate_f=False) == 4,
         "and the allocation after the reload was persisted too"),
    ])
    shutil.rmtree(directory)
    verdict(ok, "one file, atomically replaced, write-protected.")


def test_faults():
    """Every unreadable table, refused by name."""
    H    = "##VUT-TEST-GROUPS 4\n"
    good = filled().format()
    case_list = [
        ("no version line",                 good.replace(H, "")),
        ("version 2: no mark, re-issuing",  "##VUT-TEST-GROUPS 2\nG:1 1\n"),
        ("version 1: self-interned ids",    "##VUT-TEST-GROUPS 1\nG:1 1,2\n"),
        ("version 3: no generation",         "##VUT-TEST-GROUPS 3\nN:2\nG:1 0.0\n"),
        ("a generation that spells no number",
                                             H + "R:many\nN:1\nG:0\n"),
        ("no mark at all",                  H + "G:0\nG:1 0.0\n"),
        ("a mark standing twice",           H + "N:2\nN:2\nG:1 0.0\n"),
        ("a mark that spells no number",    H + "N:x\nG:0\n"),
        ("a mark beyond the ceiling",       H + "N:%i\n" % (ID_LIMIT + 1)),
        ("a group id that spells no number", H + "N:2\nG:x 1\n"),
        ("a member that spells no run id",  H + "N:2\nG:1 a\n"),
        ("a member with too many parts",    H + "N:2\nG:1 1.2.3\n"),
        ("a line that is no group",         H + "N:2\nZ:1 1\n"),
        ("group 0 holding a run",           H + "N:2\nG:0 1\n"),
        ("a group standing twice",          H + "N:3\nG:1 1\nG:1 2\n"),
        ("a set standing twice",            H + "N:3\nG:1 1\nG:2 1\n"),
        ("a group at its mark (would re-issue)",
                                            H + "N:1\nG:1 1\n"),
    ]
    banner("the group table")
    result_list = []
    for label, text in case_list:
        name = raised(lambda t=text: parse_group_table(t))
        print("         %-38s -> %s" % (label, name))
        #  'GroupFault' IS a 'RunIdFault' (the table reads run ids), so
        #  either name is a refusal; the printed line says which layer.
        result_list.append((name in ("GroupFault", "RunIdFault"),
                            "refused: %s" % label))

    banner("and the group that was never allocated")
    table = filled()
    print("         %-38s -> %s"
          % ("asking for group 99", raised(lambda: table.key_set_of(99))))
    result_list.append(
        (raised(lambda: table.key_set_of(99)) == "GroupFault",
         "never answered with the empty set -- that would read as "
         "'nobody ran this'"))

    ok = check(result_list)
    verdict(ok, "an unreadable table is refused, never half-read.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The group table: a set of runs is a number, issued once",
        choice_map = {
            "groups":    test_groups,
            "tables":    test_tables,
            "persisted": test_persisted,
            "faults":    test_faults,
        },
        happy      = "SUCCESS.*",
    ).run()
