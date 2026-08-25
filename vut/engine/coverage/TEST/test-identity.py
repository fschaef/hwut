#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE INTERNING THIS COMPONENT STILL DOES -- a SET of runs
         becomes a number -- and the two run KEYS it folds over.

CHOICES: keys, groups, tables, faults;

DESCRIPTION:

keys       'TestRunId' is what the REGISTER issued (orchestrator D-7):
           an app id, and a choice id where the test has choices. This
           component numbers no test; it carries the shape and nothing
           else. 'Gathered' pairs a found-directory with a run id for
           a fold that spans directories, and lives only that long.

groups     a SET of run keys becomes one integer, because whole regions
           of a code base are reached by exactly the same handful of
           runs: pay for the DISTINCT set, not for every occurrence.
           Group 0 is the empty set, by construction.

tables     the group table written and read back; a round trip is
           byte-stable and allocates onward from ABOVE the highest
           group it saw.

faults     a group that names nothing, a table without a version, a
           line that spells no run id, and a GATHERED key offered for
           storage. Each refused by name -- and the NAME says which
           layer caught it: 'RunIdFault' is the bookkeeper's, on the
           shape of a run id; 'IdentityFault' is this component's, on
           a group. The second is a kind of the first.

WHAT MOVED OUT. Allocation, rename and retirement of TEST ids were
tested here when this component interned them. The register owns them
now, and so does its test: 'bookkeeper/TEST/
test-test_id_db.py' (choices allocation, healing, reuse, ...). There
is no retirement any more -- removal deletes and the id returns to the
pool (orchestrator D-7, D-8).
______________________________________________________________________________
"""
import sys
import config                                                   # noqa: F401

from vut.language_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.identity import (TestRunId, Gathered,
                                          GroupTable, EMPTY_GROUP,
                                          IdentityFault,
                                          run_id_of_text,
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


A = TestRunId(1, 1)                 # as the register numbered them
B = TestRunId(1, 2)
C = Gathered("other/TEST", TestRunId(1))


def filled():
    """RETURN: GroupTable holding {A}, {A,B} and {B}, in that order --
    three distinct sets, and the empty one by construction.

    RUN IDS ONLY: a fold is over ONE directory or it is a gather;
    mixing the two kinds in one set is not a thing that happens."""
    table = GroupTable()
    for key_set in ({A}, {A, B}, {B}): table.group_of(key_set)
    return table


# ---------------------------------------------------------------------------

def test_keys():
    """The two run keys, and what each is for."""
    banner("a run id is what the REGISTER issued")
    for label, key in (("app 1, choice 1", A),
                       ("app 1, choice 2", B),
                       ("app 2, no choice", TestRunId(2))):
        print("INSPECT: %-18s -> %s" % (label, key))
    print("         this component numbers no test; it carries the")
    print("         shape, and the register decodes it to names.")

    banner("a GATHERED key qualifies one fold, and only that fold")
    print("INSPECT: %s" % C)
    print("         'other/TEST' is relative to the GATHER ROOT the")
    print("         caller chose, so it is exactly that transient.")
    print("         at the root: %s" % Gathered(None, TestRunId(3, 4)))

    banner("read back from text")
    for text in ("47", "47.66"):
        print("         %-6s -> %s" % (text, run_id_of_text(text)))

    ok = check([
        (str(A) == "1.1" and str(TestRunId(2)) == "2",
         "a run id spells app and choice, or app alone"),
        (str(C) == "other/TEST:1",
         "a gathered key spells its found-directory first"),
        (str(Gathered(None, TestRunId(3, 4))) == "3.4",
         "a record found AT the root needs no qualification"),
        (run_id_of_text("47.66") == TestRunId(47, 66),
         "the text form reads back"),
        (raised(lambda: run_id_of_text("x")) == "RunIdFault",
         "and what spells no run id is refused by the BOOKKEEPER's "
         "own fault: the shape is its, and so is the refusal"),
        (sorted([B, A, TestRunId(2)]) == [A, B, TestRunId(2)],
         "run ids order by app then choice, so a printed answer is "
         "stable"),
    ])
    verdict(ok, "the register numbers; this component carries.")


def test_groups():
    """A set of ids becomes one integer."""
    table = GroupTable()
    banner("the empty group exists by construction")
    print("INSPECT: group of the empty set -> %s"
          % table.group_of(frozenset()))
    print("         group %s decodes to %s"
          % (EMPTY_GROUP, set(table.key_set_of(EMPTY_GROUP)) or "{}"))

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
        (table.key_set_of(EMPTY_GROUP) == frozenset(),
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
        (table.key_set_of(g_ab) == frozenset({1, 2}),
         "a group decodes to its ids"),
        (raised(lambda: table.key_set_of(99)) == "IdentityFault",
         "a group that was never allocated is refused, never answered "
         "with the empty set -- that would read as 'nobody ran this'"),
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

    banner("the next allocation stands ABOVE the highest group read")
    fresh = back.group_of({TestRunId(9)})
    print("INSPECT: -> %s" % fresh)

    banner("a GATHERED key has no place in a stored table")
    gathered = GroupTable()
    gathered.group_of({C})
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
         "reading a table allocates onward from ABOVE the highest "
         "group it saw"),
        (raised(gathered.format) == "IdentityFault",
         "storing a gathered key is refused: it belongs to ONE "
         "aggregation and would freeze that view as identity"),
    ])
    verdict(ok, "one table, stable bytes, and nothing ephemeral in it.")


def test_faults():
    """Every unreadable table, refused by name."""
    good = filled().format()
    case_list = [
        ("no version line",
         good.replace("##VUT-TEST-GROUPS 2\n", "")),
        ("a group id that spells no number",
         "##VUT-TEST-GROUPS 2\nG:x 1\n"),
        ("a member that spells no run id",
         "##VUT-TEST-GROUPS 2\nG:1 a\n"),
        ("a member with too many parts",
         "##VUT-TEST-GROUPS 2\nG:1 1.2.3\n"),
        ("a line that is no group",
         "##VUT-TEST-GROUPS 2\nZ:1 1\n"),
        ("version 1: ids this component interned itself",
         "##VUT-TEST-GROUPS 1\nG:1 1,2\n"),
    ]
    banner("the group table")
    result_list = []
    for label, text in case_list:
        name = raised(lambda t=text: parse_group_table(t))
        print("         %-38s -> %s" % (label, name))
        #  'IdentityFault' IS a 'RunIdFault' (the group table reads run
        #  ids), so either name is a refusal, and the printed line says
        #  which layer caught it.
        result_list.append((name in ("IdentityFault", "RunIdFault"),
                            "refused: %s" % label))

    banner("and the group that was never allocated")
    table = filled()
    print("         %-38s -> %s"
          % ("asking for group 99", raised(lambda: table.key_set_of(99))))
    result_list.append(
        (raised(lambda: table.key_set_of(99)) == "IdentityFault",
         "never answered with the empty set -- that would read as "
         "'nobody ran this'"))

    ok = check(result_list)
    verdict(ok, "an unreadable table is refused, never half-read.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Run keys and group ids: the register numbers, "
                     "this component groups",
        choice_map = {
            "keys":       test_keys,
            "groups":     test_groups,
            "tables":     test_tables,
            "faults":     test_faults,
        },
        happy      = "SUCCESS.*",
    ).run()
