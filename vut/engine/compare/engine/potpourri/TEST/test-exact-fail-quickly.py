#! /usr/bin/env python
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Failling early on EXACT matching algorithm.

CHOICES: basic, analogy, wild, border;

DESCRIPTION:

This test checks for the circumstances under which the exact matching algorithm
can fail without a detailed similarity analysis.
______________________________________________________________________________
"""

import sys
import os

# adopt path before imports --> disable code check error E402
this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../../")
sys.path.insert(0, this_directory)

from   vut.engine.compare.configuration               import ConfigurationPatternFinder #noqa E402
import vut.engine.compare.engine.potpourri.equivalence_check as     equivalence_check   #noqa E402
from   vut.engine.compare.input.pattern_finder        import PatternFinder              #noqa E402
from   vut.engine.compare.engine.analogy_db           import AnalogyDb                  #noqa E402
from   vut.engine.compare.TEST.common                 import get_Potpourri              #noqa E402

if "--hwut-info" in sys.argv:
    print("FriendsPairing: fail quickly;")
    print("CHOICES: basic, analogy, wild, border;")
    sys.exit()

config = ConfigurationPatternFinder()
config.analogy_f = True
config.numeric_tolerance_ratio = 0.011
config.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]

pf = PatternFinder(config)

def test_pure(subject_line_list, nominal_line_list):
    print("--------------------------------")
    print("subject:", subject_line_list)
    print("nominal:", nominal_line_list)

    analogy_db = AnalogyDb()
    total_verdict, db, analogy_db = equivalence_check.do(get_Potpourri(pf, subject_line_list, config),
                                                         get_Potpourri(pf, nominal_line_list, config),
                                                         AnalogyDb(),
                                                         abort_early_f=True)

    if not total_verdict and (db or analogy_db):
        # Quick fail sets objects to 'None'
        print("db: %s; analogy_db: %s;" % ("None" if db is None else "size %i" % len(db),
                                           "None" if analogy_db is None else "size %i" % len(db)))

    print("association: %s" % (total_verdict))

    return total_verdict, db, analogy_db

def test(subject_line_list, nominal_line_list):
    total_verdict, db, analogy_db = test_pure(subject_line_list, nominal_line_list)

    def _name(cmp_info_list, i):
        if cmp_info_list: return cmp_info_list[i]
        else:            return None

    if not total_verdict: prefix = "##" # HWUT comment (ignore line)
    else:                 prefix = ""
    if total_verdict:
        for ia, ib in sorted(db.items()):
            print(prefix + "   [%i] %s%s --> [%i] %s" % (ia, _name(subject_line_list, ia),
                                                         " " * (15 - len(_name(subject_line_list, ia))),
                                                         ib, _name(nominal_line_list, ib)))
if "basic" in sys.argv:
    test(["otto"], ["otto"])
    test(["otto"], ["fritz"])
    test(["otto"], [])
    test(["otto"], [""])
    test([""], ["fritz"])
    test(["otto"], [])
    test([], ["fritz"])
    test(["otto", "heinz"],  ["fritz"])
    test(["funny", "happy", "glad"], ["happy", "glad", "glad"])      # funny matchs all, happy only happy
    test(["funny", "funny", "funny"], ["glad", "glad", "something"]) # funny matchs all, happy only happy
    # A little special: Every subject has its counterpart.
    # But, when unique couples are extracted, the analogies fail
    # and the last one remains without match.
    test(["fit ((1))", "fitter ((2))", "misfit ((1))"],
         ["fit ((A))", "fitter ((B))", "misfit ((C))"])
    # A little special: analogies at the end are interfering with analogies
    # of ultimate couples.
    test(["fit ((1))", "funny ((2))", "happy ((1))"],
         ["fit ((A))", "happy ((B))", "funny ((C))"])

if "analogy" in sys.argv:
    test(["((1)) happy", "((2))",       "((3)) me"],
         ["((C))",       "((A)) funny", "((B)) I"])

    test(["((1))", "((2))", "((3))", "((1)) ((2))"],
         ["((C))", "((A))", "((B))", "((A)) ((B))"])

    test(["((1)) ((2))", "((2)) ((3))", "((3)) ((1))"],
         ["((C)) ((A))", "((A)) ((B))", "((B)) ((C))"])

    # A large set of analogies where a contradictions is inserted, so that
    # the pairing must fail.
    size = 5
    bad_subject = ["((3)) ((2)) ((1))"] + [ "((%i)) ((%i)) ((%i))" % (i % 25, (i+1) % 25, (i+2) % 25) for i in range(1,size) ]
    bad_nominal = ["((z)) ((y)) ((x))"] + [ "((%s)) ((%s)) ((%s))" % (chr(i % 25 + ord('a')), chr((i+1)%25 + ord('a')), chr((i+2)%25 + ord('a'))) for i in range(0,size-1) ]
    total_verdict, db, analogy_db = test_pure(bad_subject, bad_nominal)

if "wild" in sys.argv:
    # Subject and nominal are subject to numeric tolerances. Each element may
    # fit with at least two elements of the counterpart. In particular the
    # boarders differ, namely for example
    #
    #    min(subject) = 1001 and min(nominal) = 1000
    #
    # Thus, subject's 1001 needs to be associated with nominal's 1000. Therefore,
    # nominal's 1000 is no longer available for subject's 1000, etc.
    size = 100
    subject = [ "%s" % (100 + i) for i in range(1,size) ]
    nominal = [ "%s" % (100 + i) for i in range(0,size-1) ]
    test_pure(subject, nominal)

    # A large set of analogies that imposes constraints in terms of
    # overlapping conditions. For example:
    #
    #    subject:                      nominal:
    #    "((1)) ((2)) ((3))"           "((a)) ((b)) ((c))"
    #    "((2)) ((3)) ((4))"           "((b)) ((c)) ((d))"
    #    ...                           ...
    #
    # If lines were associated as seen above, then '1 = a', '2 = b', '3 = c',
    # and '4 = d'. It now depends whether further pairs can be built
    # without any contradiction...
    size = 100
    subject = [ "((%i)) ((%i)) ((%i))" % (i % 25, (i+1) % 25, (i+2) % 25) for i in range(1,size) ]
    nominal = [ "((%s)) ((%s)) ((%s))" % (chr(i % 25 + ord('a')), chr((i+1)%25 + ord('a')), chr((i+2)%25 + ord('a'))) for i in range(0,size-1) ]
    total_verdict, db, analogy_db = test_pure(subject, nominal)

    for subject_term, nominal_term in sorted(analogy_db.items()):
        print("  %s <-> %s" % (subject_term, nominal_term))

    # A large set of analogies where a contradictions is inserted, so that
    # the pairing must fail.
    size = 5
    bad_subject = ["((3)) ((2)) ((1))"] + [ "((%i)) ((%i)) ((%i))" % (i % 25, (i+1) % 25, (i+2) % 25) for i in range(1,size) ]
    bad_nominal = ["((z)) ((y)) ((x))"] + [ "((%s)) ((%s)) ((%s))" % (chr(i % 25 + ord('a')), chr((i+1)%25 + ord('a')), chr((i+2)%25 + ord('a'))) for i in range(0,size-1) ]
    total_verdict, db, analogy_db = test_pure(bad_subject, bad_nominal)

if "border" in sys.argv:

    test([], [])

    test([""], [])
    test([],   [""])

    test([""], [""])

    test(["x", "y"], [])

    test([],         ["x", "y"])
    test(["x", "y"], [])

    test(["x", "x"], ["x"])
    test(["x"],      ["x", "x"])

    test(["happy", "funny"], ["happy"])
    test(["funny"],          ["happy", "funny"])

    test(["((1))", "((2))"], ["((A))"])
    test(["((A))"],          ["((1))", "((2))"])

    test(["one ((A))", "two ((A))"], ["one ((1))", "two ((2))"])

    test(["happy ((A)) ((B))", "happy ((A)) ((C))"],
         ["funny ((1)) ((2))", "funny ((2)) ((1))"])

    test(["funny ((A)) ((D))", "happy ((A)) ((B))", "glad ((C)) ((D))"],
         ["smart ((4)) ((1))", "happy ((1)) ((2))", "glad ((3)) ((4))"])

    test(["funny ((B)) ((A))", "happy ((A)) ((B))", "glad ((C)) ((D))"],
         ["smart ((2)) ((1))", "happy ((1)) ((2))", "glad ((3)) ((4))"])

    # Introduces for special coverage case:
    # "funny ((B)) ((A))" matches against three, which are removed, since the others
    # match uniquely agains each one of its alternatives. As a result "funny ((B)) ((A))"
    # remains without alternative, and is deleted.
    test(["funny ((B)) ((A))", "happy ((A)) ((B))", "smart ((C)) ((D))", "glad ((B)) ((A))", "something ((B)) ((A))"],
         ["something ((2)) ((1))", "happy ((1)) ((2))", "smart ((3)) ((4))", "glad ((2)) ((1))", "something ((2)) ((1))"])

