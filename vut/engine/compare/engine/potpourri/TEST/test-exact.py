#! /usr/bin/env python
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Algorithm to associate EQUIVALENT lines from subject and nominal.

CHOICES: basic, analogy, wild, wild-2, border, special;

DESCRIPTION:

This algorithm only associates lines which are *EQUIVALENT* according to
defined tolerance principles. The lines can be considered as the lines of 
Potpourri. The comparison of two Potpourri-s succeeds or fails depending
on this algorithm being able to construct a valid association.

The 'friends-pairing' algorithm takes two sets of lines and tries to find the
configuration of maximum number of associations.  Due to tolerance principles a
line might match multiple other lines. Depending on the choice of the partner,
another partner might not find a match.

Example:

          subject lines     nominal lines
          [1]  100          [1]  100          # delta < 1%
          [2]  99           [2]  101          # mismatch

If the numeric tolerance is 1%, then line [1] from the subject lines could
match [1] from the nominal lines. However, since 101-99 > 1% deviation, lines
[2] and [2] cannot match. A solution here, would be

          subject lines     nominal lines
          [1]  100          [2]  101          # delta < 1%
          [2]  99           [1]  100          # delta < 1%

This test validates the 'friends-pairing' of lines in the context of comparison
tolerance principles,

Some of the tests are chosen, purposely, to be exhaustive with respect to 
computation effort. If these tests are performed in a reasonable amount of 
time, their efficiency, is somehow guaranteed.
______________________________________________________________________________
"""

import sys
import os

this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../../")
sys.path.insert(0, this_directory)

from   vut.engine.compare.configuration             import ConfigurationPatternFinder #noqa E402
import vut.engine.compare.engine.potpourri.pairing  as     pairing                    #noqa E402
from   vut.engine.compare.input.pattern_finder      import PatternFinder              #noqa E402
from   vut.engine.compare.engine.analogy_db         import AnalogyDb                  #noqa E402
from   vut.engine.compare.TEST.common               import get_Potpourri              #noqa E402

if "--hwut-info" in sys.argv:
    print("FriendsPairing: Search anyway;")
    print("CHOICES: basic, analogy, wild, wild-2, border, special;")
    sys.exit()

config = ConfigurationPatternFinder()
config.analogy_f               = True
config.numeric_tolerance_ratio = 0.011
config.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
pf                             = PatternFinder(config)

def test_pure(subject_line_list, nominal_line_list):
    print("--------------------------------")
    print("subject:", subject_line_list)
    print("nominal:", nominal_line_list)

    analogy_db = AnalogyDb()
    total_verdict, \
    db,            \
    analogy_db     = pairing.do(get_Potpourri(pf, subject_line_list, config),
                                get_Potpourri(pf, nominal_line_list, config),
                                analogy_db,
                                abort_early_f=False)

    if total_verdict:
        print("association: %s (%i)" % (total_verdict, len(db)))
    else:
        print("association: False")

    return total_verdict, db, analogy_db

def test(subject_line_list, nominal_line_list):
    total_verdict, db, analogy_db = test_pure(subject_line_list, nominal_line_list)

    def _name(cmp_info_list, i):
        if cmp_info_list and i < len(cmp_info_list): return cmp_info_list[i]
        else:                                        return "None"

    if not total_verdict: prefix = "##" # HWUT comment (ignore line)
    else:                 prefix = ""
    for ia, ib in sorted(db.items()):
        print(prefix + "   [%i] %s%s --> [%i] %s" % (ia, _name(subject_line_list, ia),
                                                     " " * (15 - len(_name(subject_line_list, ia))),
                                                     ib, _name(nominal_line_list, ib)))
    if total_verdict:
        print("AnalogyDb:")
        print(analogy_db)

if "basic" in sys.argv:
    test(["otto", "fritz"],
         ["otto", "otto"])
    test(["otto", "fritz"],
         ["otto", "fritz"])
    test(["happy", "fritz"],
         ["fritz", "funny"])
    test(["happy", "mummie", "fritz"],
         ["fritz", "mummie", "I smart", "funny"])
    test(["100", "98", "99", "101"],
         ["102", "101", "100", "99"])

if "special" in sys.argv:
    # Special case, where analogy inconsistency filtering removes some entries.
    #
    test(["((1))", "X ((2))", "((2))"],
         ["((A))", "X ((B))", "((C))"])

    # Generate a case where 'match_db' is not empty but there are not enough subjects
    # for the given number of nominals after 'extract_ultimates_and_hopeless'.
    ## REMEMBER: equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
    test(["((1))", "happy ((2))", "funny ((2))"],
         ["((A))", "funny ((B))", "smart ((C))"])
    test(["smart", "smart", "glad"],
         ["funny", "funny", "none"])
    test(["funny", "funny", "none"],
         ["smart", "smart", "glad"])

if "analogy" in sys.argv:
    test(["((1)) happy", "((2))",       "((3)) me"],
         ["((C))",       "((A)) funny", "((B)) I"])

    test(["((1))", "((2))", "((3))", "((1)) ((2))"],
         ["((C))", "((A))", "((B))", "((A)) ((B))"])

    test(["((1)) ((2))", "((2)) ((3))", "((3)) ((1))"],
         ["((C)) ((A))", "((A)) ((B))", "((B)) ((C))"])

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

if "wild-2" in sys.argv:
    a_elements = ("funny", "funny", "funny", "4711", "((1))", "((2))", "same")
    b_elements = ("happy", "funny", "glad", "4712", "((A))", "((B))", "same")
    def generate(elements):
        L = len(elements)
        for offset in range(L * 25):
            yield " ".join((elements[i % L]) for i in range(offset, offset + 3))

    a_lines = [line for line in generate(a_elements)]
    b_lines = [line for line in generate(b_elements)]
    test_pure(a_lines, b_lines)

