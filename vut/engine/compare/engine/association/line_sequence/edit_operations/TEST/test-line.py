#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Edit distance and edit operations between Line-objects.

CHOICES: basic, special, analogies;

DESCRIPTION:

A 'Line' object is an interpretation of a line of text in terms of
'LineElement'-s. The edit operation investigations determine how
'LineElement'-s need to be modified in order to transform one line into the
other. Operations are 'substitute', 'transpose', 'insert', and 'delete'.

The output of these investigations is a list of edit operations together with
the accumulated 'cost', i.e. a measure for the edit distance. Also, the
required 'analogy_db' is returned which contains the necessary analogies
for equivalences to hold.
______________________________________________________________________________
"""
import sys
from   copy import copy

sys.path.insert(0, "../" * 8)

import vut.engine.compare.engine.association.line_sequence.edit_operations.line   as     edit_distance_line
from   vut.engine.compare.TEST.common            import prepare, print_match_sequences

if "--hwut-info" in sys.argv:
    print("Lines;")
    print("CHOICES: basic, visible-nothing, special, analogies;")
    sys.exit()

def test_mseq(a, b):
    subject = tuple(prepare(a))
    nominal = tuple(prepare(b, True))
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

if "basic" in sys.argv:
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
    test_mseq("sn",  "ns")      # transposed adjacently
    test_mseq("snx", "ysn")
    test_mseq("sex", "yse")

if "visible-nothing" in sys.argv:
    def test_mseqx(a, b): 
        test_mseq("".join(a), "".join(b))
    test_mseq("v",   "v")
    test_mseq("V",   "v")
    test_mseq("vs",   "vs")
    test_mseq("vs",   "sv")
    test_mseq("vS",   "vs")
    test_mseq("vS",   "sv")

    vstr = list("vvv")
    for p in range(3):
        str0 = copy(vstr); str0[p] = "s"
        str1 = copy(vstr); str1[p] = "s"
        test_mseqx(str0, str1)
    for p in range(3):
        str0 = copy(vstr); str0[p] = "s"
        str1 = copy(vstr); str1[p] = "S"
        test_mseqx(str0, str1)

    vstr = list("SsS")
    for p in range(3):
        str0 = copy(vstr); str0[p] = "v"
        str1 = copy(vstr); str1[p] = "v"
        test_mseqx(str0, str1)
    for p in range(3):
        str0 = copy(vstr); str0[p] = "v"
        str1 = copy(vstr); str1[p] = "V"
        test_mseqx(str0, str1)

if "special" in sys.argv:
    test_mseq("s",   "s")
    test_mseq("s",   "S")
    test_mseq("Sss", "ss")
    test_mseq("sSs", "ss")
    test_mseq("ssS", "ss")
    test_mseq("ss",  "Sss")
    test_mseq("ss",  "sSs")
    test_mseq("ss",  "ssS")
    test_mseq("sS",  "Ss")

if "analogies" in sys.argv:
    test_mseq("xy", "yx")
    test_mseq("xx", "zx")
    test_mseq("xyx", "zzx")      # transpose analogies

