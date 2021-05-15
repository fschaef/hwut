#! /usr/bin/env python3
#
# PURPOSE: Comparison of two streams given by 'line_providers'
#
# This test is concerned with the outer API for the comparison of two 
# character streams. It provides the two functionalities:
#
#   -- judgement: Test whether the two streams are equivalent.
#   -- info:      Provide information how the subject stream can be 
#                 transformed into the nominal stream. This is important
#                 for the 'difference display'.
#
# The 'chunk_pipe' adapts the line providers to generate chunks of type 
# *list of lines* and *potpourri*. Each chunk type has its own comparison 
# procedures defined.
#
# SPDX-Linces: MIT; (C) Frank-Rene Schaefer.
#______________________________________________________________________________
 
import sys
import os
import re
from   io import StringIO

sys.path.insert(0, "../../../../../")

import hwut.engine.compare.engine.core               as     comperator
from   hwut.engine.compare.tolerance.chunk_pipe     import ChunkPipe
from   hwut.engine.compare.TEST.common              import prepare, \
                                                           print_match_sequences, \
                                                           print_match_sequences_lists, \
                                                           print_friends_pairing_max_result, \
                                                           get_LineSequence


if "--hwut-info" in sys.argv:
    print("ChunkPipe;")
    print("CHOICES: normal, special, comment;")
    sys.exit()

config = comperator.Configuration()
config.analogy_f               = True
config.numeric_tolerance_ratio = 0.011
config.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
chunk_pipe                     = ChunkPipe(config)

def test(line_list):
    text = "\n".join(line_list)
    print("----------------------------------")
    print(text)
    print("----------------------------------")
    print("=>")
    for x in chunk_pipe.generate(StringIO(text)):
        print(x)

if "normal" in sys.argv:
    test(["line1"])
    test(["line1", "line2"])
    test(["||||", "line2", "||||"])
    test(["||||", "line 2", "line 3", "||||",
          "line 5"])
    test(["line 1", 
          "||||", "line 3", "line 4", "||||"])
    test(["line 1", 
          "||||", "line 3", "||||",
          "line 5"])

if "special" in sys.argv:
    test([])
    test([""])
    test(["", ""])
    test(["||||"])
    test(["||||", "line"])
    test(["||||", "||||"])

if "comment" in sys.argv:
    test(["##line1"])
    test(["line1##"])
    test(["##line1", "line2"])
    test(["line1", "line2##"])
    test(["||||", "line2##", "||||"])
    test(["||||", "##line2", "||||"])
    test(["||||", "##line 2", "line 3", "||||"])
    test(["||||", "line 2", "##line 3", "||||"])
    test(["##||||", "line1", "||||", "line2"])
    test(["||||", "line1", "||||##", "line2", "||||"])
