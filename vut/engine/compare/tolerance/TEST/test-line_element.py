#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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

from   vut.engine.compare.tolerance.line_element import LineElementString, \
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
    if good_subject.tolerance_id == E_ToleranceId.STRING:
        misfit_subject = LineElementAnalogy("")
    else:
        misfit_subject = LineElementString("")
    print("## SUBJECT.PASS:    ", good_subject._content)
    print("## SUBJECT.FAIL:    ", bad_subject._content)
    print("## SUBJECT.MISFIT:  ", misfit_subject._content)
    print("## NOMINAL:         ", nominal._content)
    print("GOOD.compare:            %s"   % compare(good_subject, nominal))
    print("GOOD.string:             '%s'" % good_subject.string)
    print("GOOD.difference_cost:    %.2f" % good_subject.edit_distance_relative(nominal))
    print("GOOD.representation:     %s"   % good_subject)
    print("FAILURE.compare:         %s"   % compare(bad_subject, nominal))
    print("FAILURE.string:          '%s'" % bad_subject.string)
    print("FAILURE.difference_cost: %.2f" % bad_subject.edit_distance_relative(nominal))
    print("FAILURE.representation:  %s"   % bad_subject)
    print("MISFIT.compare:          %s"   % compare(misfit_subject, nominal))
    print("NOMINAL.string:          '%s'" % nominal.string)
    print("NOMINAL.difference_cost: %.2f" % nominal.edit_distance_relative(nominal))
    print("NOMINAL.representation:  %s"   % nominal)
    print("##-------------------------------")

if choice == "LineElementString":
    test(LineElementString("A fox jumps high"[6:10]),
         LineElementString("An elephant does not jump"[3:11]),
         LineElementString("Mice don't jump"[11:16]))
    test(LineElementString("A fox jumps high"[6:6]), # Empty:
         LineElementString("An elephant does not jump"[3:11]),
         LineElementString("Mice don't jump"[11:16]))
    test(LineElementString("A fox jumps high"[6:10]),
         LineElementString("An elephant does not jump"[3:11]),
         LineElementString("Mice don't jump"[11:11]))  # Empty:

if choice == "LineElementNumber":
    test(LineElementNumber("A fox 4712 high"[6:10]),
         LineElementNumber("An 5000 13  does not jump"[3:7]),
         LineElementNumber("Mice don't 4711"[11:16], 0.01))

if choice == "LineElementEquivalencePattern":
    test(LineElementEquivalencePattern("A fox jumps high"[2:5], (1,2,3)),
         LineElementEquivalencePattern("A mize not jump"[2:6], (7,8)),
         LineElementEquivalencePattern("Mice don't"[0:4], (3,4,5)))

if choice == "LineElementAnalogy":
    test(LineElementAnalogy("A ((fox)) jumps"[2:9]),
         LineElementAnalogy("((there is no false analogy))"[0:29]),
         LineElementAnalogy("((mouse))"[0:9]))
