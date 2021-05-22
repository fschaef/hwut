"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
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

from   ut.engine.compare.friends_pairing.match_db        import MatchDb
from   ut.engine.compare.engine.analogy_db               import AnalogyDb

from   copy import copy

if "--hwut-info" in sys.argv:
    print("MatchDb;")
    print("CHOICES: analogy_interferences, extract_ultimates, pairing;")
    sys.exit()

if "pairing" in sys.argv:
    def test(name, match_db, analogy_db):
        print("---( %s )-----------------------------" % name)
        print("BEFORE: {")
        print(match_db)
        print("}")
        if len(analogy_db):
            print("analogy_db:", analogy_db)

        verdict, couples, analogy_db = match_db.pairing(analogy_db)

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

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (1,   [(100, AnalogyDb([("otto",  "heinz")])),    # removed upon '1' extracted
               (101, AnalogyDb([("mark",  "heinz")]))]),
        (2,   [(100, AnalogyDb([("otto",  "heinz")])),    # removed upon '1' extracted
               (101, AnalogyDb([("mark",  "otto")]))]),
    ])
    match_db_copy = copy(match_db)
    test("basic", match_db, AnalogyDb())

if "extract_ultimates" in sys.argv:
    def test(name, match_db, analogy_db, abort_f=False):
        print("---( %s )-----------------------------" % name)
        print("BEFORE: {")
        print(match_db)
        print("}")
        if len(analogy_db):
            print("analogy_db:", analogy_db)

        couples = match_db.extract_ultimates_and_hopeless(analogy_db, abort_f)

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

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (1,   [(101, AnalogyDb([("otto", "heinz")]))
        ]),
    ])
    test("one entry", match_db, AnalogyDb())

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (1,   [(101, AnalogyDb([("otto", "heinz")]))
        ]),
    ])
    test("one entry consistent with analogy_db", match_db, AnalogyDb({ "otto":  "heinz" }))

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (1,   [(101, AnalogyDb([("otto", "heinz")]))
        ]),
    ])
    match_db_copy = copy(match_db)
    test("one entry inconsistent with analogy_db", match_db, AnalogyDb({ "max":  "heinz" }))
    test("one entry inconsistent with analogy_db (abort)", match_db_copy, AnalogyDb({ "max":  "heinz" }), abort_f=True)

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "heinz")]))]),  # ultimate
        (1,   [(100, AnalogyDb([("otto", "heinz")])),    # removed upon '1' extracted
               (101, AnalogyDb([("mark", "heinz")]))]),
    ])
    match_db_copy = copy(match_db)
    test("one entry, when removed makes other alternativeless", match_db, AnalogyDb())
    test("one entry, when removed makes other alternativeless (abort)", match_db_copy, AnalogyDb(), abort_f=True)

    match_db = MatchDb.from_iterable([
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

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "heinz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")])),
               (101, AnalogyDb([("mark", "otto")]))]),
        (2,   [(100, AnalogyDb([("otto", "heinz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
    ])
    test("remove nominal with only one mating candidate", match_db, AnalogyDb())

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "fritz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")]))]),
        (2,   [(101, AnalogyDb([("otto", "heinz")])),
               (102, AnalogyDb([("mark", "otto")]))]),
    ])
    test("remove nominals with contradicting analogy_db", match_db, AnalogyDb())

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (0,   [(101, AnalogyDb([("otto",   "fritz")]))]),
        (1,   [(100, AnalogyDb([("mark",   "heinz")]))]),
        (2,   [(100, AnalogyDb([("otto",  "heinz")])),
               (101, AnalogyDb([("mark",  "heinz")]))])
    ])
    match_db_copy = copy(match_db)
    test("a removed nominal leaves entry hopeless", match_db, AnalogyDb())
    test("a removed nominal leaves entry hopeless (abort)", match_db_copy, AnalogyDb(), abort_f=True)

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (0,   [(101, AnalogyDb([("otto", "fritz")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")])),
               (101, AnalogyDb([("mark", "heinz")]))])
    ])
    match_db_copy = copy(match_db)
    test("nominal deletion produces ultimate with inconsistent analogy_db", match_db, AnalogyDb())
    test("nominal deletion produces ultimate with inconsistent analogy_db (abort)", match_db_copy, AnalogyDb(), abort_f=True)

    match_db = MatchDb.from_iterable([
        # ia: ib:   analogy_list:
        (0,   [(100, AnalogyDb([("otto", "heinz")]))]),
        (1,   [(100, AnalogyDb([("otto", "heinz")]))]),
    ])
    match_db_copy = copy(match_db)
    test("nominal already taken", match_db, AnalogyDb(), abort_f=False)
    test("nominal already taken (abort)", match_db_copy, AnalogyDb(), abort_f=True)

if "analogy_interferences" in sys.argv:
    def test(match_db, analogy_db):
        print("--------------------------------")
        print("BEFORE: {")
        print(match_db)
        print("}")

        match_db_2 = match_db.clone()
        verdict = match_db._filter_analogy_interference(analogy_db, abort_f=False)

        print("AFTER: --> %s {" % verdict)
        print(match_db)
        print("}")

        verdict = match_db_2._filter_analogy_interference(analogy_db, abort_f=True)
        print("AFTER(abort=True): --> %s {" % verdict)
        if verdict:
            print(match_db_2)
        print("}")

    match_db = MatchDb.from_iterable([
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

