#! /usr/bin/env python3
#
# PURPOSE: Tolerance LineElement objects;
#
# A line is processed by the tolerance pattern finder and transformed into a
# list of 'LineElement' objects. This test checks on the functionality of all
# derivatives of 'LineElement' objects, as they are mainly:
#
#    .compare()            --> E_Verdict
#    .edit_operations()    --> Number between 0 and 1
#    .string()             --> String that matched the pattern.
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________

import sys

sys.path.insert(0, "../../../../../")

from   ut.engine.compare.tolerance.match import LineElementString, \
                                                  LineElementNumber, \
                                                  LineElementEquivalencePattern, \
                                                  LineElementAnalogy, \
                                                  E_ToleranceId


if "--hwut-info" in sys.argv:
    print("Tolerance: ComperatorLineElement;")
    print("CHOICES: LineElementString, LineElementNumber, LineElementEquivalencePattern, LineElementAnalogy;")
    sys.exit()

choice = sys.argv[1]

def compare(first, second):
    verdict, analogy = first.compare(second)
    return "(%s, %s)" % (verdict.name, analogy)

def test(good_subject, bad_subject, nominal):
    misfit_subject = LineElementString(0, 0, "")
    if good_subject.tolerance_id == E_ToleranceId.STRING:
        misfit_subject.tolerance_id = E_ToleranceId.ANALOGY
    print("GOOD.compare:            %s"   % compare(good_subject, nominal))
    print("GOOD.string:             '%s'" % good_subject.string)
    print("GOOD.difference_cost:    %.6f" % good_subject.edit_distance_relative(nominal))
    print("GOOD.representation:     %s"   % good_subject)
    print("FAILURE.compare:         %s"   % compare(bad_subject, nominal))
    print("FAILURE.string:          '%s'" % bad_subject.string)
    print("FAILURE.difference_cost: %.6f" % bad_subject.edit_distance_relative(nominal))
    print("FAILURE.representation:  %s"   % bad_subject)
    print("MISFIT.compare:          %s"   % compare(misfit_subject, nominal))
    print("NOMINAL.string:          '%s'" % nominal.string)
    print("NOMINAL.difference_cost: %.6f" % nominal.edit_distance_relative(nominal))
    print("NOMINAL.representation:  %s"   % nominal)

if choice == "LineElementString":
    test(LineElementString(6, 10,  "A fox jumps high"),
         LineElementString(3, 11,  "An elephant does not jump"),
         LineElementString(11, 16, "Mice don't jump"))
    test(LineElementString(6, 6,   "A fox jumps high"), # Empty:
         LineElementString(3, 11,  "An elephant does not jump"),
         LineElementString(11, 16, "Mice don't jump"))
    test(LineElementString(6, 10,  "A fox jumps high"),
         LineElementString(3, 11,  "An elephant does not jump"),
         LineElementString(11, 11, "Mice don't jump"))  # Empty:

if choice == "LineElementNumber":
    test(LineElementNumber(6, 10,  "A fox 4712 high"),
         LineElementNumber(3, 7,   "An 5000 13  does not jump"),
         LineElementNumber(11, 16, "Mice don't 4711", 0.01))

if choice == "LineElementEquivalencePattern":
    test(LineElementEquivalencePattern(2, 5, "A fox jumps high", (1,2,3)),
         LineElementEquivalencePattern(2, 6, "A mize not jump", (7,8)),
         LineElementEquivalencePattern(0, 4, "Mice don't", (3,4,5)))

if choice == "LineElementAnalogy":
    test(LineElementAnalogy(2, 9,  "A ((fox)) jumps"),
         LineElementAnalogy(0, 29, "((there is no false analogy))"),
         LineElementAnalogy(0, 9,  "((mouse))"))
