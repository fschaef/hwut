"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'MatchDb'

CHOICES: analogy_interferences, extract_ultimates, pairing;

DESCRIPTION:

The 'MatchDb' maintains possible matches between subject and nominal lines.

 map: subject line number --> (nominal line number, analogy_db)

That is, for each line number in the subject, there is a list of line numbers
indicating the nominal lines that match that line. Additionally, the
analogy_db tells what analogies are require for the equivalence to hold.

-- 'pairing' finds distinct matches between subject lines and nominal lines.
             That is, it transforms a configuration of possible matches into
             a setup of fixed relationships.

-- 'extract_ultimates' find those entries in the database for which there is
             no ulternative and extracts them into a 'couples' dictionary.

-- 'analogy_interferences' removes entries from the database which are
             inconsistent with a given analogy database.
______________________________________________________________________________
"""

import sys
import os

this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../")
sys.path.insert(0, this_directory)

from   vut.engine.compare.friends_pairing.match_db import (
    UnpairedCandidateGraph,
    PairedGraph,
    Result,
    extract_ultimates_and_hopeless,
    pairing,
)
from   vut.engine.compare.engine.analogy_db import AnalogyDb

from   copy import copy


if "--hwut-info" in sys.argv:
    print("MatchDb;")
    print("CHOICES: analogy_interferences, extract_ultimates, pairing;")
    sys.exit()


# ---------------------------------------------------------------------------
# helpers (internal only; outputs must remain unchanged)
# ---------------------------------------------------------------------------

def _required_pair_n(db: UnpairedCandidateGraph) -> int:
    """Equivalent to old MatchDb.max_size constructed from iterable."""
    return max(len(db), db.count_nominals())


def _state_from_db(db: UnpairedCandidateGraph, analogy_db: AnalogyDb) -> Result:
    """Create a state object for the functional pipeline in match_db.py.good."""
    return Result(
        potential_pair_db     = db,
        pair_db               = PairedGraph(),
        analogy_constraint_db = analogy_db,
        required_pair_n       = _required_pair_n(db),
        aborted_f             = False,
    )


# ---------------------------------------------------------------------------
# pairing
# ---------------------------------------------------------------------------

if "pairing" in sys.argv:
    def test(name, match_db, analogy_db):
        print("---( %s )-----------------------------" % name)
        print("BEFORE: {")
        print(match_db)
        print("}")
        if len(analogy_db):
            print("analogy_db:", analogy_db)

        state   = _state_from_db(match_db, analogy_db)
        outcome = pairing(state)

        # Keep output identical: print "couples" only (no verdict line).
        couples = dict(outcome.pair_db)
        analogy_db = outcome.analogy_constraint_db

        print("AFTER: --> {")
        if len(match_db): print(match_db)
        print("}")
        print("couples: ")
        if couples is not None:
            for ia, ib in sorted(couples.items()):
                print("  %02i <-> %02i" % (ia, ib))
        else:
            print("<None>")
        print()

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (1,   [(100, AnalogyDb([("otto",  "heinz")])),    # removed upon '1' extracted
               (101, AnalogyDb([("mark",  "heinz")]))]),
        (2,   [(100, AnalogyDb([("otto",  "heinz")])),    # removed upon '1' extracted
               (101, AnalogyDb([("mark",  "otto")]))]),
    ])
    match_db_copy = copy(match_db)
    test("basic", match_db, AnalogyDb())


# ---------------------------------------------------------------------------
# extract_ultimates
# ---------------------------------------------------------------------------

if "extract_ultimates" in sys.argv:
    def test(name, match_db, analogy_db, abort_f=False):
        print("---( %s )-----------------------------" % name)
        print("BEFORE: {")
        print(match_db)
        print("}")
        if len(analogy_db):
            print("analogy_db:", analogy_db)

        state   = _state_from_db(match_db, analogy_db)
        outcome = extract_ultimates_and_hopeless(state, abort_f)

        couples = dict(outcome.pair_db)

        print("AFTER: --> {")
        if len(match_db): print(match_db)
        print("}")
        print("couples: ")
        if couples is not None:
            for ia, ib in sorted(couples.items()):
                print("  %02i <-> %02i" % (ia, ib))
        else:
            print("<None>")
        print()

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (1,   [(101, AnalogyDb([("otto", "heinz")]))
        ]),
    ])
    test("one entry", match_db, AnalogyDb())

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (1,   [(101, AnalogyDb([("otto", "heinz")]))
        ]),
    ])
    test("one entry consistent with analogy_db", match_db, AnalogyDb({ "otto":  "heinz" }))

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (1,   [(101, AnalogyDb([("otto", "heinz")]))
        ]),
    ])
    match_db_copy = copy(match_db)
    test("one entry inconsistent with analogy_db", match_db, AnalogyDb({ "max":  "heinz" }))
    test("one entry inconsistent with analogy_db (abort)", match_db_copy, AnalogyDb({ "max":  "heinz" }), abort_f=True)

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "heinz")]))]),  # ultimate
        (1,   [(100, AnalogyDb([("otto", "heinz")])),    # removed upon '1' extracted
               (101, AnalogyDb([("mark", "heinz")]))]),
    ])
    match_db_copy = copy(match_db)
    test("one entry, when removed makes other alternativeless", match_db, AnalogyDb())
    test("one entry, when removed makes other alternativeless (abort)", match_db_copy, AnalogyDb(), abort_f=True)

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "heinz")]))]),    # ultimate
        (1,   [(100, AnalogyDb([("otto", "heinz")])),      # removed upon '1' extracted
               (101, AnalogyDb([("mark", "otto")]))]),
        (2,   [(100, AnalogyDb([("otto", "heinz")])),      # removed upon '1' extracted
               (101, AnalogyDb([("fritz", "otto")])), # removed open '2' extracted
               (102, AnalogyDb([("mark", "otto")]))]),
        (3,   [(100, AnalogyDb([("otto", "heinz")])),      # removed upon '1' extracted
               (101, AnalogyDb([("friedhelm", "fritz")])), # removed upon '2' extracted
               (102, AnalogyDb([("friedhelm", "fritz")])), # removed upon '3' extracted
               (103, AnalogyDb([("mark", "otto")]))]),
    ])
    test("iterative ultimate creation", match_db, AnalogyDb())

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "heinz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")])),
               (101, AnalogyDb([("mark", "otto")]))]),
        (2,   [(100, AnalogyDb([("otto", "heinz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
    ])
    test("remove nominal with only one mating candidate", match_db, AnalogyDb())

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "fritz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")]))]),
        (2,   [(101, AnalogyDb([("otto", "heinz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
    ])
    test("remove nominals with contradicting analogy_db", match_db, AnalogyDb())

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (0,   [(101, AnalogyDb([("otto",   "fritz")]))]),
        (1,   [(100, AnalogyDb([("mark",   "heinz")]))]),
        (2,   [(100, AnalogyDb([("otto",  "heinz")])),
               (101, AnalogyDb([("mark",  "heinz")]))])
    ])
    match_db_copy = copy(match_db)
    test("a removed nominal leaves entry hopeless", match_db, AnalogyDb())
    test("a removed nominal leaves entry hopeless (ABORT EARLY)", match_db_copy, AnalogyDb(), abort_f=True)

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (0,   [(101, AnalogyDb([("otto", "fritz")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")])),
               (101, AnalogyDb([("mark", "heinz")]))])
    ])
    match_db_copy = copy(match_db)
    test("nominal deletion produces ultimate with inconsistent analogy_db", match_db, AnalogyDb())
    test("nominal deletion produces ultimate with inconsistent analogy_db (abort)", match_db_copy, AnalogyDb(), abort_f=True)

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "heinz")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")]))]),
    ])
    match_db_copy = copy(match_db)
    test("nominal already taken", match_db, AnalogyDb(), abort_f=False)
    test("nominal already taken (abort)", match_db_copy, AnalogyDb(), abort_f=True)


# ---------------------------------------------------------------------------
# analogy_interferences
# ---------------------------------------------------------------------------

if "analogy_interferences" in sys.argv:
    def test(match_db, analogy_db):
        print("--------------------------------")
        print("BEFORE: {")
        print(match_db)
        print("}")

        match_db_2 = copy(match_db)

        verdict = match_db.remove_pairs_with_analogy_interferences(analogy_db, abort_early_f=False)

        print("AFTER: --> %s {" % verdict)
        print(match_db)
        print("}")

        verdict = match_db_2.remove_pairs_with_analogy_interferences(analogy_db, abort_early_f=True)
        print("AFTER(abort=True): --> %s {" % verdict)
        if verdict:
            print(match_db_2)
        print("}")

    match_db = UnpairedCandidateGraph([
        # ia: ib:   analogy_list:
        (1,   [
            (100, AnalogyDb([("otto", "fritz"), ("lucia", "anabella")])),
            (101, AnalogyDb([("otto", "heinz")]))
        ]),
        (3,   [
            (101, AnalogyDb([("otto", "heinz"), ("lucia", "anabella")])),
            (100, AnalogyDb([("otto", "fritz")]))
        ])
    ])

    test(match_db, AnalogyDb({ "otto":  "fritz" }))
    test(match_db, AnalogyDb({ "otto":  "egon", "lucia": "diana" }))
