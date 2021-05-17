#! /usr/bin/env python3
#
# PURPOSE: Testing 'Edit Distance' computation.
#
# The concept of 'edit distance' measures the differece of two strings in
# terms of necessary operations in order to transform one string into the
# other. Operations are: substitute, transpose, insert, and delete.
#
# Tests: -- Computation of the edit distance between two strings.
#        -- Determination of correct edit operations for two lists of 'LineElement'
#           objects.
#
# The edit operations may later be used for the display of differences between
# two lines.
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________

import sys
import os
import re

sys.path.insert(0, "../../../../../")

import ut.engine.compare.edit_operations.string  as     edit_distance_string
import ut.engine.compare.edit_operations.line  as     edit_distance_line
from   ut.engine.compare.TEST.common           import prepare, print_match_sequences

if "--hwut-info" in sys.argv:
    print("Edit Distance;")
    print("CHOICES: string, match_sequence, match_sequence2, match_sequence-analogies;")
    sys.exit()

def test_mseq(a, b):
    subject = list(prepare(a))
    nominal = list(prepare(b, True))
    print_match_sequences(subject, nominal)

    print("=>")
    cost, edit_list, analogy_db = edit_distance_line.do(subject, nominal)
    assert cost <= 1
    print("Cost: %.6f" % cost)
    for i, edit in enumerate(edit_list):
        if edit.transpose_ai is not None:
            print("[%i] %s (%s)" % (i, edit.id.name, edit.transpose_ai))
        else:
            print("[%i] %s"      % (i, edit.id.name))
    if len(analogy_db):
        print("AnalogyDb:")
        print(repr(analogy_db))
    print()

if "string" in sys.argv:
    def test(a, b):
        print("subject:  '%s'" % a)
        print("nominal: '%s'" % b)
        print("=> %s" % edit_distance_string.do(a, b))

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

if "match_sequence" in sys.argv:
    test_mseq("",    "")        # empty vs. empty
    test_mseq("",    "s")       # empty vs. one
    test_mseq("s",   "")        # one vs. empty
    test_mseq("s",   "s")       # one vs. one
    test_mseq("s",   "n")       # one != one
    test_mseq("nss", "ss")      # inserted front
    test_mseq("sns", "ss")      # inserted middle
    test_mseq("ssn", "ss")      # inserted end
    test_mseq("ss",  "nss")     # deleted front
    test_mseq("ss",  "sns")     # deleted middle
    test_mseq("ss",  "ssn")     # deleted end
    test_mseq("sn",  "ns")      # trsnsposed sdjscently
    test_mseq("snx", "ysn")
    test_mseq("sex", "yse")

if "match_sequence2" in sys.argv:
    test_mseq("s",   "s")
    test_mseq("s",   "S")
    test_mseq("Sss", "ss")
    test_mseq("sSs", "ss")
    test_mseq("ssS", "ss")
    test_mseq("ss",  "Sss")
    test_mseq("ss",  "sSs")
    test_mseq("ss",  "ssS")
    test_mseq("sS",  "Ss")

if "match_sequence-analogies" in sys.argv:
    test_mseq("xy", "yx")
    test_mseq("xx", "zx")
    test_mseq("xyx", "zzx")      # transpose analogies

