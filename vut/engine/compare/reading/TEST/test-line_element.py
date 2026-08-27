#! /usr/bin/env python3
#
# hwut {
#     title      = "Tolerance: LineElement-s"
#     choices    = ["LineElementAnalogy",
#                   "LineElementEquivalencePattern", "LineElementNumber",
#                   "LineElementString", "NumberBand"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
____________________________________________________________________________

PURPOSE: Functionality of 'LineElement'-s;

CHOICES: LineElementString, LineElementNumber, NumberBand,
         LineElementEquivalencePattern, LineElementAnalogy;

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

from   config import HwutRunner # noqa F401

from   vut.engine.compare.reading.line_element import LineElementString, \
                                                  LineElementNumber, \
                                                  LineElementEquivalencePattern, \
                                                  LineElementAnalogy, \
                                                  E_ToleranceId


if "--hwut-info" in sys.argv:
    print("Tolerance: LineElement-s;")
    print("CHOICES: LineElementString, LineElementNumber, NumberBand, LineElementEquivalencePattern, LineElementAnalogy;")
    sys.exit()

choice = sys.argv[1]

def compare(first, second):
    verdict, analogy = first.compare(second)
    return "(%s, %s)" % (verdict.name, analogy)

def test(good_subject, bad_subject, nominal):
    misfit_subject = LineElementString("")
    if good_subject.tolerance_id == E_ToleranceId.STRING:
        misfit_subject.tolerance_id = E_ToleranceId.ANALOGY
    print("GOOD.compare:            %s"   % compare(good_subject, nominal))
    print("GOOD.string:             '%s'" % good_subject._string)
    print("GOOD.difference_cost:    %.6f" % good_subject.edit_distance_relative(nominal))
    print("GOOD.representation:     %s"   % good_subject)
    print("FAILURE.compare:         %s"   % compare(bad_subject, nominal))
    print("FAILURE.string:          '%s'" % bad_subject._string)
    print("FAILURE.difference_cost: %.6f" % bad_subject.edit_distance_relative(nominal))
    print("FAILURE.representation:  %s"   % bad_subject)
    print("MISFIT.compare:          %s"   % compare(misfit_subject, nominal))
    print("NOMINAL.string:          '%s'" % nominal._string)
    print("NOMINAL.difference_cost: %.6f" % nominal.edit_distance_relative(nominal))
    print("NOMINAL.representation:  %s"   % nominal)

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

if choice == "NumberBand":
    RATIO = 0.01

    print("The tolerance band belongs to the NOMINAL, the 'pole':")
    print()
    print("             band radius = abs(nominal) * ratio")
    print()
    print("             <---------|--------->")
    print("        -----+---------O---------+------------> number line")
    print("                    nominal            subject inside: EQUIVALENT")
    print()
    print("A radius carries no sign. The price of substituting subject for")
    print("nominal is 'max(|s-n| - band, 0) / max(|s|, |n|)', capped at 1.")
    print()
    print("ratio: %.2f" % RATIO)

    def number(Text):
        return LineElementNumber(Text, RATIO)

    print()
    print("(1) THE BAND, STRADDLING ZERO -- sign-symmetric rows adjacent")
    print()
    print("     nominal      band    subject      |s-n|   verdict")
    print("    --------   -------   --------   --------   ----------")
    for nom_txt, sub_txt in (("100.0",  "100.4"),
                             ("-100.0", "-100.4"),
                             ("100.0",  "102.0"),
                             ("-100.0", "-102.0"),
                             ("-100.0", "-100.0"),
                             ("0.0",    "0.0")):
        nom, sub   = number(nom_txt), number(sub_txt)
        verdict, _ = sub.compare(nom)
        print("    %8s   %7.2f   %8s   %8.1f   %s"
              % (nom_txt, nom.epsilon, sub_txt,
                 abs(sub.number - nom.number), verdict.name))

    print()
    print("(2) THE SAME NUMBER, TWO SPELLINGS")
    print()
    print("     nominal      subject     verdict")
    print("    ---------   ---------    ----------")
    for nom_txt, sub_txt in (("100.00",  "100.0"),
                             ("-100.00", "-100.0"),
                             ("-100.0",  "-100"),
                             ("-100.4",  "-1.004e2")):
        nom, sub   = number(nom_txt), number(sub_txt)
        verdict, _ = sub.compare(nom)
        print("    %9s   %9s    %s" % (nom_txt, sub_txt, verdict.name))

    print()
    print("(3) THE PRICE OF SUBSTITUTION -- in [0, 1], 0 inside the band")
    print()
    print("     nominal      subject      price   remark")
    print("    --------   ----------   --------   -------------------------")
    for nom_txt, sub_txt, remark in (
            ("100.0",  "100.4",     "inside the band"),
            ("-100.0", "-100.4",    "inside the band"),
            ("-100.0", "-102.0",    "just outside"),
            ("1.0",    "10.0",      "overshoot, ranked"),
            ("1.0",    "100000.0",  "far overshoot, ranked"),
            ("1.0",    "-100.0",    "opposite signs, capped"),
            ("0.0",    "5.0",       "pole at zero, capped"),
            ("5.0",    "0.0",       "subject at zero")):
        nom, sub = number(nom_txt), number(sub_txt)
        print("    %8s   %10s   %8.6f   %s"
              % (nom_txt, sub_txt, sub.edit_distance_relative(nom), remark))

if choice == "LineElementEquivalencePattern":
    test(LineElementEquivalencePattern("A fox jumps high"[2:5], (1,2,3)),
         LineElementEquivalencePattern("A mize not jump"[2:6], (7,8)),
         LineElementEquivalencePattern("Mice don't"[0:4], (3,4,5)))

if choice == "LineElementAnalogy":
    test(LineElementAnalogy("A ((fox)) jumps"[2:9]),
         LineElementAnalogy("((there is no false analogy))"[0:29]),
         LineElementAnalogy("((mouse))"[0:9]))
