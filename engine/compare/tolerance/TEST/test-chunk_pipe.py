#! /usr/bin/env python3
"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
____________________________________________________________________________

PURPOSE: ChunkPipe: Text lines to LineSequence and Potpourri,

A chunk pipe reads lines from a 'line provider', i.e. an object with a member
function '.readline()'. The chunk pipe uses the 'PatternFinder' to produce a
'Line' object from a line of text. It groups lines of text into 'LineSequence'
and 'Potpourri' objects.

By default, a chunk pipe is in the 'LineSequence' generation mode, that is
any incoming line is pushed into a 'LineSequence' object where the sequence
of appearance matters. A line starting with a Porpourri marker (i.e. '||||')
sets the chunk pipe into 'Potpourri' mode. In that mode all incoming lines
are pushed into a 'Potpourri' object, where the actual sequence of appearance
does not matter. When in Potpourri mode, the occurrence of a marker, again,
sets the chunk pipe back into the 'LineSequence' mode.
______________________________________________________________________________
"""
import sys
from   io import StringIO

sys.path.insert(0, "../../../../../")

import ut.engine.compare.engine.core          as     comperator
from   ut.engine.compare.tolerance.chunk_pipe import ChunkPipe
from   ut.engine.compare.TEST.common          import print_match_sequences, \
                                                     print_match_sequences_lists, \
                                                     print_friends_pairing_max_result, \
                                                     get_LineSequence


if "--hwut-info" in sys.argv:
    print("ChunkPipe;")
    print("CHOICES: normal, special, comment;")
    sys.exit()

config = comperator.Configuration()
config.pattern_finder.analogy_f               = True
config.pattern_finder.numeric_tolerance_ratio = 0.011
config.pattern_finder.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]
chunk_pipe = ChunkPipe(config)

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
