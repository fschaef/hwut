#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHO COVERED THIS LINE -- the fold that answers what to run when
         code changes, and the honesty about what it does NOT answer.

CHOICES: segments, query, change, economy, lossy, honest;

DESCRIPTION:

segments   the line axis cut where the SET OF ORIGINS changes, and one
           set per segment. Two runs overlapping in the middle produce
           three segments; a stretch nobody executed is CARRIED as a
           segment naming nobody, never skipped; two runs that merely
           TOUCH share no line.

query      'of_line' and 'of_ranges' over the segmentation: a line
           nobody executed answers the EMPTY set, a line outside every
           known file answers the empty set, and neither is a claim.

change     'of_change' -- the diff's line ranges in, the runs that
           executed them out, sorted. This is the selection a tester
           wants after an edit.

economy    a file one run reaches WHOLE costs ONE segment, not one entry
           per line: the same economy the record's intervals buy, kept
           through the fold.

lossy      why the index is a DIFFERENT FOLD and not a richer merge:
           'record.merge' unions the ranges and thereby destroys who
           contributed which line. Shown side by side, on the same two
           records.

honest     the index answers over runs it was BUILT from, and the empty
           answer is not a clearance. A run that depends on code it never
           executed is invisible here -- and a face that selects on this
           alone must say so.
______________________________________________________________________________
"""
import sys
import config                                                   # noqa: F401

from vut.language_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.record import (ranges_of, FileCoverage,
                                        CoverageRecord, merge)
from vut.engine.coverage.index    import TestIndex, index_of
from vut.engine.coverage.identity import (TestRunId, Gathered,
                                          EMPTY_GROUP)


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


def record_of(test, choice, file_db):
    """
    RETURN: CoverageRecord, of one run; 'file_db' maps a path to the
            LINES it covered.
    """
    return CoverageRecord(
        language = "python", tool = "coverage",
        source   = "coverage.py-json", counts_f = False,
        test     = test, choice = choice,
        file_db  = {path: FileCoverage(path, ranges_of(line_iterable),
                                       ranges_of(line_iterable))
                    for path, line_iterable in file_db.items()})


def named(origin_set):
    """RETURN: str, the origins of a set, sorted, comma separated."""
    return ",".join(sorted(str(o) for o in origin_set)) or "<nobody>"


#  TWO RUNS THAT OVERLAP IN THE MIDDLE OF ONE FILE.
A_ORIGIN = TestRunId(1, 1)
B_ORIGIN = TestRunId(1, 2)
C_ORIGIN = Gathered("engine/TEST", TestRunId(2))

A_RECORD = record_of("test-parse.py", "basic",
                     {"core.py": range(1, 11), "only_a.py": range(1, 4)})
B_RECORD = record_of("test-parse.py", "deep",
                     {"core.py": range(6, 21)})
C_RECORD = record_of("test-other.py", None,
                     {"core.py": range(40, 43)})


def the_index():
    """RETURN: TestIndex over the three reference runs."""
    return index_of([(A_ORIGIN, A_RECORD),
                     (B_ORIGIN, B_RECORD),
                     (C_ORIGIN, C_RECORD)])


# ---------------------------------------------------------------------------

def test_segments():
    """The line axis, cut where the origin set changes."""
    index = the_index()
    banner("core.py -- A covers 1..10, B covers 6..20, C covers 40..42")
    for (begin, end), origin_set in index.segment_iterable("core.py"):
        print("         [%3i,%3i)  %s" % (begin, end, named(origin_set)))

    banner("two runs that merely TOUCH do not overlap")
    touching = index_of([
        (A_ORIGIN, record_of("t", "a", {"x.py": range(1, 6)})),
        (B_ORIGIN, record_of("t", "b", {"x.py": range(6, 11)}))])
    for (begin, end), origin_set in touching.segment_iterable("x.py"):
        print("         [%3i,%3i)  %s" % (begin, end, named(origin_set)))

    segment_list = list(index.segment_iterable("core.py"))
    touch_list   = list(touching.segment_iterable("x.py"))
    ok = check([
        (len(segment_list) == 5,
         "overlap in the middle cuts core.py into five segments: "
         "A, A+B, B, the GAP, C"),
        (segment_list[0][0] == (1, 6)
         and segment_list[0][1] == frozenset([A_ORIGIN]),
         "1..5 belongs to A alone"),
        (segment_list[1][0] == (6, 11)
         and segment_list[1][1] == frozenset([A_ORIGIN, B_ORIGIN]),
         "6..10 belongs to both"),
        (segment_list[2][0] == (11, 21)
         and segment_list[2][1] == frozenset([B_ORIGIN]),
         "11..20 belongs to B alone"),
        (segment_list[3][0] == (21, 40)
         and segment_list[3][1] == frozenset(),
         "the gap is CARRIED, not skipped: 21..39 names nobody, and "
         "says so"),
        (segment_list[4][0] == (40, 43)
         and segment_list[4][1] == frozenset([C_ORIGIN]),
         "40..42 belongs to C, beyond the gap"),
        (len(touch_list) == 2
         and touch_list[0][1] == frozenset([A_ORIGIN])
         and touch_list[1][1] == frozenset([B_ORIGIN]),
         "ranges that touch at 6 share NO line"),
        (index.path_tuple == ("core.py", "only_a.py"),
         "every file that anybody reached is in the index"),
    ])
    verdict(ok, "the segmentation cuts exactly where authorship changes.")


def test_query():
    """Reading the index: one line, and a span."""
    index = the_index()
    banner("one line at a time")
    for line in (1, 6, 15, 30, 41):
        print("         core.py:%-3i -> %s" % (line, named(index.of_line("core.py", line))))

    banner("a span")
    for label, range_tuple in (("4..7",   ((4, 8),)),
                               ("22..30", ((22, 31),)),
                               ("1..100", ((1, 101),))):
        print("         core.py %-7s -> %s"
              % (label, named(index.of_ranges("core.py", range_tuple))))

    banner("a file nobody measured")
    print("         ghost.py:1 -> %s" % named(index.of_line("ghost.py", 1)))

    ok = check([
        (index.of_line("core.py", 1) == frozenset([A_ORIGIN]),
         "line 1 -> A"),
        (index.of_line("core.py", 6) == frozenset([A_ORIGIN, B_ORIGIN]),
         "line 6 -> A and B"),
        (index.of_line("core.py", 15) == frozenset([B_ORIGIN]),
         "line 15 -> B"),
        (index.of_line("core.py", 30) == frozenset(),
         "line 30, in the gap, -> nobody"),
        (index.of_line("core.py", 41) == frozenset([C_ORIGIN]),
         "line 41 -> C"),
        (index.of_ranges("core.py", ((4, 8),))
         == frozenset([A_ORIGIN, B_ORIGIN]),
         "a span crossing a cut collects both"),
        (index.of_ranges("core.py", ((22, 31),)) == frozenset(),
         "a span wholly inside the gap collects nobody"),
        (index.of_ranges("core.py", ((1, 101),))
         == frozenset([A_ORIGIN, B_ORIGIN, C_ORIGIN]),
         "a span over the whole file collects everybody"),
        (index.of_line("ghost.py", 1) == frozenset(),
         "an unknown file answers the empty set, and never raises"),
    ])
    verdict(ok, "a query is a bisect, and an empty answer is a value.")


def test_change():
    """The selection: a diff in, the runs to perform out."""
    index = the_index()

    banner("an edit inside the shared region")
    change_db = {"core.py": ranges_of([7, 8])}
    print("INSPECT: %s -> %s"
          % (change_db, [str(o) for o in index.of_change(change_db)]))

    banner("an edit in two files at once")
    change_db = {"core.py": ranges_of([15]), "only_a.py": ranges_of([2])}
    both = index.of_change(change_db)
    print("INSPECT: %s" % [str(o) for o in both])

    banner("an edit nobody ever executed")
    lonely = index.of_change({"core.py": ranges_of([30])})
    print("INSPECT: %s -- and this is NOT a clearance" % [str(o) for o in lonely])

    ok = check([
        ([str(k) for k in index.of_change({"core.py": ranges_of([7, 8])})]
         == ["1.1", "1.2"],
         "an edit in the shared region names both runs -- as the "
         "REGISTER numbered them; the names are its to decode"),
        (len(both) == 2,
         "an edit across files names the union of their runs"),
        (lonely == (),
         "an edit nobody executed names nobody"),
        (index.of_change({}) == (),
         "an empty change names nobody"),
        (str(C_ORIGIN) == "engine/TEST:2",
         "a gathered key spells its found-directory and run id"),
        (str(A_ORIGIN) == "1.1",
         "and a plain run id spells app and choice, nothing more"),
    ])
    verdict(ok, "a change names the runs that certainly touched it.")


def test_economy():
    """One segment for a file one run reaches whole."""
    whole = index_of([(A_ORIGIN,
                       record_of("t", "a", {"big.py": range(1, 5001)}))])
    segment_list = list(whole.segment_iterable("big.py"))
    banner("5000 lines, one run")
    for (begin, end), origin_set in segment_list:
        print("         [%i,%i)  %s" % (begin, end, named(origin_set)))

    banner("5000 lines, two runs splitting it in half")
    halved = index_of([
        (A_ORIGIN, record_of("t", "a", {"big.py": range(1, 2501)})),
        (B_ORIGIN, record_of("t", "b", {"big.py": range(2501, 5001)}))])
    print("         segments: %i" % len(list(halved.segment_iterable("big.py"))))

    ok = check([
        (len(segment_list) == 1,
         "a file one run reaches whole costs ONE segment, not 5000"),
        (segment_list[0][0] == (1, 5001),
         "and that segment spans the file"),
        (len(list(halved.segment_iterable("big.py"))) == 2,
         "two runs splitting a file cost two segments"),
        (len(whole.file_db["big.py"][0]) == 2,
         "the boundary array of one segment holds two numbers"),
        (whole.file_db["big.py"][1] == (1,),
         "and the segment carries ONE INTEGER, not a set of names"),
    ])
    verdict(ok, "the fold keeps the economy the intervals bought.")


def test_lossy():
    """Why this is a fold and not a merge."""
    merged = merge([A_RECORD, B_RECORD])
    index  = the_index()

    banner("merge answers WHAT the suite reached")
    print("INSPECT: core.py covered = %s"
          % (merged.file_db["core.py"].covered,))
    print("         test = '%s'  choice = '%s'"
          % (merged.test, merged.choice))
    print("         -- who covered line 3? the merged record cannot say.")

    banner("the index answers WHO reached it")
    print("INSPECT: core.py:3  -> %s" % named(index.of_line("core.py", 3)))
    print("         core.py:15 -> %s" % named(index.of_line("core.py", 15)))

    ok = check([
        (merged.file_db["core.py"].covered == ((1, 21),),
         "merge unions the ranges -- the whole span, one range"),
        (merged.test == "test-parse.py",
         "provenance that agrees is carried"),
        (merged.choice == "basic,deep",
         "provenance that differs is JOINED -- the mixture is visible, "
         "but not per line"),
        (index.of_line("core.py", 3) == frozenset([A_ORIGIN]),
         "the index keeps per line what the merge folds away"),
        (index.of_line("core.py", 15) == frozenset([B_ORIGIN]),
         "and it distinguishes the two runs the merge fused"),
    ])
    verdict(ok, "two questions, two folds, one set of per-run records.")


def test_honest():
    """What the empty answer is, and what it is not."""
    index = the_index()

    banner("the index knows only the runs it was built from")
    partial = index_of([(A_ORIGIN, A_RECORD)])
    print("INSPECT: built from A alone, core.py:15 -> %s"
          % named(partial.of_line("core.py", 15)))
    print("         built from all,     core.py:15 -> %s"
          % named(index.of_line("core.py", 15)))

    banner("an empty answer is not a clearance")
    print("         core.py:30 -> %s" % named(index.of_line("core.py", 30)))
    print("         A run may depend on code it never EXECUTED: a branch")
    print("         that was deleted, a data file, a dynamic dispatch, an")
    print("         absence. Selecting on this alone and calling the suite")
    print("         green is a FALSE GREEN -- PHILOSOPHY section 7.")

    ok = check([
        (partial.of_line("core.py", 15) == frozenset(),
         "a run absent from the build is absent from every answer"),
        (index.of_line("core.py", 15) == frozenset([B_ORIGIN]),
         "and present once it is built in"),
        (index.of_line("core.py", 30) == frozenset(),
         "an unexecuted line names nobody -- a fact, not a verdict"),
        (index_of([]).path_tuple == (),
         "an index over no record knows no file"),
    ])
    verdict(ok, "the index states what it saw, and claims nothing beyond.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The coverage index: who executed this line, and what "
                     "to run when it changes",
        choice_map = {
            "segments": test_segments,
            "query":    test_query,
            "change":   test_change,
            "economy":  test_economy,
            "lossy":    test_lossy,
            "honest":   test_honest,
        },
        happy      = "SUCCESS.*",
    ).run()
