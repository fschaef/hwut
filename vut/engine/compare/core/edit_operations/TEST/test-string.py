#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Determine the 'edit distance' between strings.

DESCRIPTION:

The 'edit distance' measures the difference between two strings by a scalar
value. It is determined as the minimum number of operations with CHARACTERS to
transform one string into the other (https://en.wikipedia.org/wiki/Edit_distance). 
The operations are 'substitute', 'transpose', 'insert', and 'delete'.

The tests examine the edit distance in the presence of the mentioned 
necessary operations.
______________________________________________________________________________
"""
import sys

from   config import HwutRunner # noqa F401

import vut.engine.compare.core.edit_operations.string as     edit_distance_string

if "--hwut-info" in sys.argv:
    print("Strings;")
    print("CHOICES: basic, long;")
    sys.exit()

def test(a, b):
    print("subject:  '%s'" % a)
    print("nominal: '%s'" % b)
    print("=> %s" % edit_distance_string.do(a, b))

if "basic" in sys.argv:
    test("",                "")        # empty vs. empty
    test("",                "a")       # empty vs. one
    test("a",               "")        # one vs. empty
    test("a",               "a")       # one vs. one
    test("a",               "b")       # one != one
    test("baa",             "aa")      # inserted front
    test("aba",             "aa")      # inserted middle
    test("aab",             "aa")      # inserted end
    test("aa",              "baa")     # deleted front
    test("aa",              "aba")     # deleted middle
    test("aa",              "aab")     # deleted end
    test("ab",              "ba")      # transposed adjacently
    test("axxb",            "bxxa")    # transposed far
    test("1--2--3",         "2--3--1") # transpose sequence

    test(" a b ",           " a b ")   # two words (with padding)
    test(" a b ",           " b b ")   # two words different
    test("aba aa ab axxb ", " aa aba ba bxxa")

if "long" in sys.argv:
    test("12345678901234567890", "12345678901234567890")
    test("X2345678901234567890", "12345678901234567890")
    test("1234567890123456789X", "12345678901234567890")

