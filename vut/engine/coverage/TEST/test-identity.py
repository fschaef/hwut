#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TWO INTERNINGS -- a run becomes a NUMBER, a SET of runs
         becomes a number -- and the two laws that make a test id safe to
         write into a record: an id is never reused, and a rename keeps
         it.

CHOICES: allocation, rename, retire, groups, tables, faults;

DESCRIPTION:

allocation ids are handed out monotonically and once: the same Origin
           always answers the same id, a new one always answers a new
           id, and an unknown Origin can be ASKED without allocating.

rename     THE POINT OF THE WHOLE INTERNING: a rename touches the table
           and nothing else. The id is unchanged, so every record ever
           written still attributes to the right run. A rename onto a
           run another live id already holds is refused.

retire     a run that is gone keeps its ENTRY -- so an old record still
           decodes -- while the forward lookup stops finding it, and the
           id is NEVER handed out again. Reuse would make an old record
           point silently at a different test.

groups     a SET of test ids becomes one integer, because whole regions
           of a code base are reached by exactly the same handful of
           tests: pay for the DISTINCT set, not for every occurrence.
           Group 0 is the empty set, by construction.

tables     both tables written and read back: retired entries survive,
           and reading a table allocates onward from ABOVE the highest
           id it saw -- so a round trip can never reissue an id.

faults     an id that names nothing, a group that names nothing, a table
           without a version, a line that spells no id. Each refused by
           name: an unresolvable id in an index is an attribution nobody
           can check.
______________________________________________________________________________
"""
import sys
import config                                                   # noqa: F401

from vut.language_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.identity import (Origin, IdTable, GroupTable,
                                          EMPTY_GROUP, IdentityFault,
                                          parse_id_table,
                                          parse_group_table)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """
    RETURN: True,  every claim held; prints OK/FAIL per line.
            False, else.
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
            'nothing', if it raised none.
    """
    try:
        action()
    except Exception as x:
        return type(x).__name__
    return "nothing"


A = Origin(None, "test-parse.py", "basic")
B = Origin(None, "test-parse.py", "deep")
C = Origin("other/TEST", "test-other.py", None)


def filled():
    """RETURN: IdTable holding A, B and C, in that order."""
    table = IdTable()
    for origin in (A, B, C): table.id_of(origin)
    return table


# ---------------------------------------------------------------------------

def test_allocation():
    """Monotone, once, and askable without allocating."""
    table = IdTable()
    banner("three runs")
    for origin in (A, B, C):
        print("         %-32s -> %s" % (origin, table.id_of(origin)))

    banner("asking again answers the SAME id")
    print("         %-32s -> %s" % (A, table.id_of(A)))

    banner("asking about an unknown run, without allocating")
    unknown = Origin(None, "test-ghost.py", None)
    print("         %-32s -> %s"
          % (unknown, table.id_of(unknown, allocate_f=False)))
    print("         the table still holds %i id(s)" % len(table))

    ok = check([
        (table.id_of(A) == 1 and table.id_of(B) == 2 and table.id_of(C) == 3,
         "ids are handed out monotonically, from one"),
        (table.id_of(A) == 1,
         "the same run always answers the same id"),
        (table.id_of(unknown, allocate_f=False) is None,
         "an unknown run can be ASKED without being allocated"),
        (len(table) == 3,
         "and asking allocated nothing"),
        (table.origin_of(2) == B,
         "an id decodes to the run it names"),
        (table.origin_of(99) is None,
         "an id that was never allocated decodes to None"),
        (table.is_retired(99) is None,
         "and answers None to 'retired?' -- unallocated is NOT retired"),
        (table.is_retired(1) is False,
         "a live id says so"),
    ])
    verdict(ok, "an id is allocated once, monotonically, and asked "
                "without side effect.")


def test_rename():
    """A rename touches the table and no record anywhere."""
    table = filled()
    before = table.id_of(A)

    banner("rename the test file")
    fresh = table.rename(before, test="test-parser.py")
    print("INSPECT: id %s now names '%s'" % (before, fresh))
    print("         the id is unchanged: %s" % (table.id_of(fresh) == before))

    banner("rename the choice")
    table.rename(before, choice="quick")
    print("INSPECT: id %s now names '%s'" % (before, table.origin_of(before)))

    banner("the OLD name no longer resolves forward")
    print("         %-32s -> %s" % (A, table.id_of(A, allocate_f=False)))

    banner("renaming onto a run another live id holds")
    print("         raised %s"
          % raised(lambda: table.rename(before, test="test-parse.py",
                                        choice="deep")))

    ok = check([
        (table.id_of(table.origin_of(before)) == before,
         "THE ID IS UNCHANGED -- every record ever written still "
         "attributes to the right run"),
        (str(table.origin_of(before)) == "test-parser.py--quick",
         "both parts can be renamed, one call at a time"),
        (table.id_of(A, allocate_f=False) is None,
         "the old name resolves forward no more"),
        (raised(lambda: table.rename(before, test="test-parse.py",
                                     choice="deep")) == "IdentityFault",
         "a rename onto a LIVE run's name is refused: two live ids for "
         "one run would make 'which id is this' unanswerable"),
        (raised(lambda: table.rename(99, test="x")) == "IdentityFault",
         "renaming an id that was never allocated is refused"),
        (len(table) == 3,
         "and no rename ever allocated an id"),
    ])
    verdict(ok, "a rename touches one table; the records are untouched.")


def test_retire():
    """A run that is gone still decodes; its id is never reused."""
    table = filled()
    banner("retire the second run")
    gone = table.retire(2)
    print("INSPECT: id 2 named '%s'" % gone)
    print("         it still decodes:      %s" % table.origin_of(2))
    print("         it is marked retired:  %s" % table.is_retired(2))
    print("         it resolves forward:   %s"
          % table.id_of(B, allocate_f=False))

    banner("a new run gets a NEW id, never the freed one")
    fresh_id = table.id_of(Origin(None, "test-new.py", None))
    print("INSPECT: the new run -> id %s" % fresh_id)

    banner("retiring twice is not a fault -- it is already true")
    print("         raised %s" % raised(lambda: table.retire(2)))

    ok = check([
        (table.origin_of(2) == B,
         "a retired id STILL DECODES -- an old record must not become "
         "unreadable"),
        (table.is_retired(2) is True,
         "and says that it is retired"),
        (table.id_of(B, allocate_f=False) is None,
         "while the forward lookup stops finding it"),
        (fresh_id == 4,
         "THE ID IS NEVER REUSED: reuse would make an old record point "
         "silently at a different test"),
        (raised(lambda: table.retire(2)) == "nothing",
         "retiring twice is idempotent"),
        (raised(lambda: table.retire(99)) == "IdentityFault",
         "retiring an id that was never allocated is refused"),
    ])
    verdict(ok, "a retired id decodes for ever and is issued never again.")


def test_groups():
    """A set of ids becomes one integer."""
    table = GroupTable()
    banner("the empty group exists by construction")
    print("INSPECT: group of the empty set -> %s"
          % table.group_of(frozenset()))
    print("         group %s decodes to %s"
          % (EMPTY_GROUP, set(table.id_set_of(EMPTY_GROUP)) or "{}"))

    banner("three distinct sets, three groups")
    g_a  = table.group_of({1})
    g_ab = table.group_of({1, 2})
    g_b  = table.group_of({2})
    print("INSPECT: {1} -> %s   {1,2} -> %s   {2} -> %s" % (g_a, g_ab, g_b))

    banner("the SAME set, whatever order or type it arrives in")
    print("INSPECT: [2,1] -> %s   frozenset({2,1}) -> %s"
          % (table.group_of([2, 1]), table.group_of(frozenset({2, 1}))))
    print("         the table holds %i group(s)" % len(table))

    ok = check([
        (table.group_of(frozenset()) == EMPTY_GROUP,
         "the empty set is group 0 -- a value, not a hole"),
        (table.id_set_of(EMPTY_GROUP) == frozenset(),
         "and it decodes to nothing"),
        ((g_a, g_ab, g_b) == (1, 2, 3),
         "distinct sets get distinct groups, monotonically"),
        (table.group_of([2, 1]) == g_ab
         and table.group_of(frozenset({2, 1})) == g_ab,
         "one set is one group, whatever order or container it came in"),
        (len(table) == 4,
         "three sets plus the empty one -- nothing was allocated twice"),
        (table.group_of({7}, allocate_f=False) is None,
         "an unknown set can be asked without being allocated"),
        (table.id_set_of(g_ab) == frozenset({1, 2}),
         "a group decodes to its ids"),
        (raised(lambda: table.id_set_of(99)) == "IdentityFault",
         "a group that was never allocated is refused, never answered "
         "with the empty set -- that would read as 'nobody ran this'"),
    ])
    verdict(ok, "pay for the distinct set, not for every occurrence.")


def test_tables():
    """Written, read back, and safe to write again."""
    table = filled()
    table.rename(1, test="test-parser.py")
    table.retire(3)
    text = table.format()

    banner("the id table, as it is stored")
    for line in text.splitlines(): print("         | %s" % line)

    back      = parse_id_table(text)
    stable_f  = back.format() == text          # BEFORE anything is added
    banner("read back")
    for test_id, entry in back.item_iterable():
        print("         %s %s %s"
              % (test_id, "retired" if entry.retired else "live   ",
                 entry.origin))

    banner("the next allocation stands ABOVE the highest id read")
    fresh = back.id_of(Origin(None, "test-new.py", None))
    print("INSPECT: -> %s" % fresh)

    group_table = GroupTable()
    group_table.group_of({1, 2})
    group_table.group_of({2})
    group_text = group_table.format()
    banner("the group table, as it is stored")
    for line in group_text.splitlines(): print("         | %s" % line)
    group_back = parse_group_table(group_text)

    ok = check([
        (stable_f,
         "format(parse(format(x))) == format(x) -- the bytes are stable"),
        (back.origin_of(3) == C and back.is_retired(3) is True,
         "a retired entry survives the round trip, retired"),
        (back.id_of(C, allocate_f=False) is None,
         "and does not resolve forward after it"),
        (str(back.origin_of(1)) == "test-parser.py--basic",
         "a renamed entry survives under its id"),
        (fresh == 4,
         "reading a table allocates onward from ABOVE the highest id it "
         "saw -- a round trip can never reissue an id"),
        (group_back.id_set_of(1) == frozenset({1, 2})
         and group_back.id_set_of(2) == frozenset({2}),
         "the group table survives the round trip"),
        (group_back.id_set_of(EMPTY_GROUP) == frozenset(),
         "the empty group with it"),
        (group_back.group_of({3}) == 3,
         "and allocates onward from above the highest group read"),
    ])
    verdict(ok, "a table can be written, read, and written again "
                "without ever reissuing an id.")


def test_faults():
    """Every unreadable table, refused by name."""
    good = filled().format()
    case_list = [
        ("no version line",   good.replace("##VUT-TEST-IDS 1\n", "")),
        ("an id that spells no number", good.replace("T:1 ", "T:one ")),
        ("no live/retired flag",
         "##VUT-TEST-IDS 1\nT:1 -|test-a.py|-\n"),
        ("too few name parts",
         "##VUT-TEST-IDS 1\nT:1 . test-a.py\n"),
        ("an id standing twice",
         "##VUT-TEST-IDS 1\nT:1 . -|a|-\nT:1 . -|b|-\n"),
        ("a line that is no entry",
         "##VUT-TEST-IDS 1\nZ:1 . -|a|-\n"),
    ]
    banner("the id table")
    result_list = []
    for label, text in case_list:
        name = raised(lambda t=text: parse_id_table(t))
        print("         %-32s -> %s" % (label, name))
        result_list.append((name == "IdentityFault", "refused: %s" % label))

    banner("the group table")
    for label, text in (("no version line", "G:1 1,2\n"),
                        ("a group id that spells no number",
                         "##VUT-TEST-GROUPS 1\nG:x 1\n"),
                        ("a member that is no id",
                         "##VUT-TEST-GROUPS 1\nG:1 a\n"),
                        ("a line that is no group",
                         "##VUT-TEST-GROUPS 1\nZ:1 1\n")):
        name = raised(lambda t=text: parse_group_table(t))
        print("         %-32s -> %s" % (label, name))
        result_list.append((name == "IdentityFault", "refused: %s" % label))

    ok = check(result_list)
    verdict(ok, "an unreadable table is refused, never half-read.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Test ids and group ids: never reused, rename keeps "
                     "the id",
        choice_map = {
            "allocation": test_allocation,
            "rename":     test_rename,
            "retire":     test_retire,
            "groups":     test_groups,
            "tables":     test_tables,
            "faults":     test_faults,
        },
        happy      = "SUCCESS.*",
    ).run()
