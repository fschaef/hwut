#! /usr/bin/env python
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Algorithm to associate SIMILAR lines from subject and nominal.

CHOICES: basic, restricted_cmp;

DESCRIPTION:

The 'friends_pairing/similar' match algorithm associates as many lines as
possible, i.e. the number of associations is

              max(subject line number, nominal line number)

First, equivalent lines are associated. 

Seconds, associations are done according to similarity in terms of their 'edit
distance'. That is, it is measured how many editions of (SUBSTITUTE, DELETE,
INSERT, TRANSPOSE) are necessary to transform the subject into the nominal 
line. Line pairs which require less of edit operations than others are 
considered more similar.  

Third, if there are more lines of one kind than the other, it associates the
existing lines with 'None'.

'restricted_cmp' tests on the restricted amount of comparisons. This is 
introduced in order to avoid a computational overload in case of many
similar lines.
______________________________________________________________________________
"""
import sys
import os

this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../..")
sys.path.insert(0, this_directory)

from   vut.engine.compare.configuration                import ConfigurationPatternFinder      #noqa E402
import vut.engine.compare.region.potpourri.best_match as     association                     #noqa E402
from   vut.engine.compare.engine.input.pattern_finder         import PatternFinder                   #noqa E402
from   vut.engine.compare.engine.analogy_db            import AnalogyDb                       #noqa E402

from   vut.engine.compare.TEST.common import get_Potpourri, print_friends_pairing_max_result #noqa E402

if "--hwut-info" in sys.argv:
    print("FriendsPairingMax: Search anyway;")
    print("CHOICES: basic, restricted_cmp;")
    sys.exit()

config = ConfigurationPatternFinder()
config.analogy_f               = True
config.numeric_tolerance_ratio = 0.011
config.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
pf                             = PatternFinder(config)

def test_pure(subject_line_list, nominal_line_list, max_comparison_count):
    print("--------------------------------")
    print("subject:", subject_line_list)
    print("nominal:", nominal_line_list)

    analogy_db = AnalogyDb()
    line_associations, \
    analogy_db         = association.do(get_Potpourri(pf, subject_line_list, config),
                                        get_Potpourri(pf, nominal_line_list, config),
                                        analogy_db,
                                        max_comparison_count)

    return line_associations, analogy_db

def test(subject_line_list, nominal_line_list, max_comparison_count=100):
    line_associations, analogy_db = test_pure(subject_line_list, nominal_line_list,
                                              max_comparison_count)

    print_friends_pairing_max_result(subject_line_list, nominal_line_list,
                                     -1.0, sorted(line_associations), analogy_db)

if "basic" in sys.argv:
    test([],
         ["otto", "otto"])
    test(["otto", "fritz"],
         [])
    test(["otto"],
         ["otto", "otto"])
    test(["otto", "fritz"],
         ["otto"])
    test(["otto", "fritz"],
         ["otto", "otto"])
    test(["otto", "fritz"],
         ["otto", "fritz"])
    test(["happy", "fritz"],
         ["fritz", "funny"])
    test(["happy", "mummie", "fritz"],
         ["fritz", "mummie", "I smart", "funny"])
    test(["fritz", "mummie", "I smart", "funny"],
         ["happy", "mummie", "fritz"])

    test(["98", "99", ],
         ["102", "101", "100", "99"])

    test(["100", "98", "99", "101"],
         ["102", "99"])

    test(["((1))", "((2))", "((2))", "((3))"],
         ["((A))", "((B))", "((C))", "((D))"])

    test(["a", "b", "c", "d", "e", "f"],
         ["x", "y", "z"])

if "restricted_cmp" in sys.argv:
    # Special case, where analogy inconsistency filtering removes some entries.
    #
    test(["A ((1))", "B ((2))", "C ((2))", "D ((3))"],
         ["a ((A))", "B ((B))", "c ((C))", "d ((D))"],
         max_comparison_count=1)

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
    total_verdict, _, analogy_db = test_pure(subject, nominal)

    for subject_term, nominal_term in sorted(analogy_db.items()):
        print("  %s <-> %s" % (subject_term, nominal_term))

    # A large set of analogies where a contradictions is inserted, so that
    # the pairing must fail.
    size = 5
    bad_subject = ["((3)) ((2)) ((1))"] + [ "((%i)) ((%i)) ((%i))" % (i % 25, (i+1) % 25, (i+2) % 25) for i in range(1,size) ]
    bad_nominal = ["((z)) ((y)) ((x))"] + [ "((%s)) ((%s)) ((%s))" % (chr(i % 25 + ord('a')), chr((i+1)%25 + ord('a')), chr((i+2)%25 + ord('a'))) for i in range(0,size-1) ]
    total_verdict, _, analogy_db = test_pure(bad_subject, bad_nominal)

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

if "DEBUG" in sys.argv:
    test(["I smart", "funny"],
         ["happy"])
