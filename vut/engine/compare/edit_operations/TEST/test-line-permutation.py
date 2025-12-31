#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Edit operations for different cases of line elements interferring.

CHOICES: different    -- categories of LineElement-s are different.
         different-2 -- same as 'different', but with bordering line elements.
         same        -- categories are the same.

DESCRIPTION:

This test checks on different LineElement types inteferring and ensuring that
the resulting edit sequence is meaningful. Currently the different types
of 'LineElement'-s dependent on their 'E_ToleranceId':

        STRING              
        VISIBLE_NOTHING     
        ANALOGY              
        NUMERIC              
        EQUIVALENCE_PATTERN  
        SEPERATOR            

This enumeration is checked upon entry, such that all tests fail if the
enumeration struct is different.

The tests checks for all possible combinations of how a subject line element
of such a type might hit on a nominal element type. Additionally, the
empty line element sequence occurs (coded as '-1' below).

AUTHOR: 2021, Frank-Rene Schaefer.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../../")

from    vut.engine.compare.tolerance.line_element import E_ToleranceId, \
                                                        LineElement, \
                                                        LineElementString
import vut.engine.compare.edit_operations.line   as      edit_operations_line

from    itertools import combinations

if "--hwut-info" in sys.argv:
    print("Lines: Permutation LineElement-types;")
    print("CHOICES: different, different-2, different-good-2, different-void-2, same;")
    sys.exit()

E_ToleranceId_member_list              = ['STRING', 'VISIBLE_NOTHING', 'ANALOGY', 'NUMERIC', 'EQUIVALENCE_PATTERN', 'SEPERATOR']
E_ToleranceId_when_tests_where_written = set(E_ToleranceId_member_list)
E_ToleranceId_current                  = set(E_ToleranceId.__members__.keys())
assert E_ToleranceId_current == E_ToleranceId_when_tests_where_written

def get_example(tolerance_id, example_str="4711"):
    assert tolerance_id in E_ToleranceId

    if tolerance_id == E_ToleranceId.STRING:
        return LineElementString(example_str)
    else:
        # Simulate a match and use the new from_match factory
        return LineElement.from_match(tolerance_id, example_str, 0.1, {1,2,3})

tolerance_db = {
   0: E_ToleranceId.STRING,
   1: E_ToleranceId.VISIBLE_NOTHING,
   2: E_ToleranceId.ANALOGY,
   3: E_ToleranceId.NUMERIC,
   4: E_ToleranceId.EQUIVALENCE_PATTERN,
   5: E_ToleranceId.SEPERATOR
}

def stringy(x):
    return "%s:%s" % (x.tolerance_id.name, x._string)

def call(subject, nominal):
    result  = edit_operations_line.do(subject, nominal)
    print("      subject:  " + repr([stringy(x) for x in subject]).replace("'", "")[1:-1])
    print("      nominal:  " + repr([stringy(x) for x in nominal]).replace("'", "")[1:-1])
    print("      => edits: " + repr([x.id.name for x in result.edit_list]).replace("'", "")[1:-1])

call_n = 0
def test_core(subject, nominal):
    global call_n
    call_n += 1
    print("--(%i)------------------------------------------------------------------" % call_n)
    call(subject, nominal)
    print()
    call(nominal, subject)


if "different" in sys.argv:
    def test(a, b):
        subject = tuple() if a == -1 else (get_example(tolerance_db[a]),)
        nominal = tuple() if b == -1 else (get_example(tolerance_db[b]),)
        test_core(subject, nominal)

    for a, b in combinations([-1] + list(range(len(tolerance_db))), 2):
        if a >= b: continue
        test(a, b)

if "different-2" in sys.argv:
    def test(a, b):
        subject = tuple() if a == -1 else (get_example(tolerance_db[a]),)
        nominal = tuple() if b == -1 else (get_example(tolerance_db[b]),)
        new_subject = subject 
        new_nominal = nominal + subject
        # new_subject = subject + subject 
        # new_nominal = subject + nominal + subject
        test_core(new_subject, new_nominal)

    for a, b in combinations(range(len(tolerance_db)), 2):
        if a >= b: continue
        test(a, b)

if "different-good-2" in sys.argv:
    def test(a, b):
        subject = tuple() if a == -1 else (get_example(tolerance_db[a]),)
        nominal = tuple() if b == -1 else (get_example(tolerance_db[b]),)
        new_subject = nominal + subject 
        new_nominal = nominal + nominal + subject
        # new_subject = subject + subject 
        # new_nominal = subject + nominal + subject
        test_core(new_subject, new_nominal)

    for a, b in combinations(range(len(tolerance_db)), 2):
        if a >= b: continue
        test(a, b)

if "different-void-2" in sys.argv:
    def test(a, b):
        subject = tuple() if a == -1 else (get_example(tolerance_db[a]),)
        nominal = tuple() if b == -1 else (get_example(tolerance_db[b]),)
        new_subject = subject + subject 
        new_nominal = nominal + nominal + subject
        # new_subject = subject + subject 
        # new_nominal = subject + nominal + subject
        test_core(new_subject, new_nominal)

    for a, b in combinations(range(len(tolerance_db)), 2):
        if a >= b: continue
        test(a, b)

elif "same" in sys.argv:
    def test(a, b):
        subject = tuple() if a == -1 else (get_example(tolerance_db[a]),)
        nominal = tuple() if b == -1 else (get_example(tolerance_db[b]),)
        test_core(subject, nominal)
    for a in [-1] + list(range(len(tolerance_db))):
        test(a, a)
