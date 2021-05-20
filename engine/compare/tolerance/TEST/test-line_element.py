#! /usr/bin/env python3
"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
____________________________________________________________________________

PURPOSE: Functionality of 'LineElement'-s;

CHOICES: LineElementString, LineElementNumber, LineElementEquivalencePattern, 
         LineElementAnalogy;

DESCRIPTION:

A 'LineElement' is carries an interpretation of a pattern in text. This ca
be a number, whitespace, or some customer defined equivalence pattern.
Tolerance, or the judgement about equivalence, is built upon the concept
that each type of line element has its specific way of comparison. Comparison
is supported by 'LineElement'-s with the following member functions:

 .compare(other) -> [0] boolean verdict (True=equivalent, False=else)
                    [1] analogy required for an equivalence to hold

 .string         -> string that matched the pattern of the line element.

 .edit_distance_relative(other) -> [0..1] indicating the 'cost of difference'
                                   this value is based on the edit distance
                                   between 'self' and 'other'. It is normalized
                                   with the max. possible edit distance based
                                   on 'len(self)' and 'len(other)'.

The following tests check the behavior of each 'LineElement' type with
respect to these functions for the cases

  * GOOD:     'self' and 'other' are equivalent.
  * FAILURE:  'self' and 'other' are different in content.
  * MISFIT:   'self' and 'other' are misfitting types.
  * NOMINAL:  'self' and 'other' are identical (subject == nominal)
_____________________________________________________________________________
"""

import sys

sys.path.insert(0, "../../../../../")

from   ut.engine.compare.tolerance.line_element import LineElementString, \
                                                  LineElementNumber, \
                                                  LineElementEquivalencePattern, \
                                                  LineElementAnalogy, \
                                                  E_ToleranceId


if "--hwut-info" in sys.argv:
    print("Tolerance: LineElement-s;")
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
