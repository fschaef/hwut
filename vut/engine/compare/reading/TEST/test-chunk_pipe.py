#! /usr/bin/env python3
#
# @hwut {
#     title      = "ChunkPipe"
#     choices    = ["comment", "normal", "special"]
#     tolerance { regions = false
#                 #  THE REGISTRY IS NOT THIS UNIT'S BEHAVIOUR. The
#                 #  error names the offending handler and calls it
#                 #  unknown -- that is what is under test. WHICH
#                 #  handlers happen to be registered is a fact about
#                 #  another module, and it moved once already (the
#                 #  keyed merge added 'unaccepted'). Tolerated, so
#                 #  that the name and the clause stay pinned exactly.
#                 eq_pattern = ["known handlers: [a-z, \\-]+"] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
____________________________________________________________________________

PURPOSE: ChunkPipe: Text lines to LineSequence and Potpourri,

A chunk pipe reads lines from a 'line provider', i.e. an object with a member
function '.readline()'. The chunk pipe uses the 'PatternFinder' to produce a
'Line' object from a line of text. It groups lines of text into 'LineSequence'
and 'Potpourri' objects.

By default, a chunk pipe is in the 'LineSequence' generation mode, that is
any incoming line is pushed into a 'LineSequence' object where the sequence
of appearance matters. A region shebang '##! <handler>' opens a region whose
lines are collected for the named handler (e.g. 'potpourri', where the
sequence of appearance does not matter); the line '####' closes it and the
pipe returns to 'LineSequence' mode. Broken framing (missing '####', stray
'####', nesting) raises a loud 'RegionSyntaxError'.
______________________________________________________________________________
"""
import sys
from   io import StringIO

from   config import HwutRunner # noqa F401

from   vut.engine.compare.configuration    import Configuration
from   vut.auxiliary.async_helper          import AsyncIterator_ensured
from   vut.engine.compare.reading.chunk_pipe import AssociationChunkPipe
from   vut.engine.compare.region.registry         import RegionSyntaxError
import asyncio

if "--hwut-info" in sys.argv:
    print("ChunkPipe;")
    print("CHOICES: normal, special, comment;")
    sys.exit()

config = Configuration()
config.pattern_finder.analogy_f               = True
config.pattern_finder.numeric_tolerance_ratio = 0.011
config.pattern_finder.equivalent_pattern_list = [ r"funny|happy", r"funny|smart", r"funny|glad", r"I|me" ]

async def test_core(line_list):
    text = "\n".join(line_list)
    chunk_pipe = AssociationChunkPipe(config, AsyncIterator_ensured(StringIO(text)))
    print("----------------------------------")
    print(text)
    print("----------------------------------")
    print("=>")
    try:
        async for x in chunk_pipe.yield_input_chunks():
            print(x)
    except RegionSyntaxError as e:
        print("RegionSyntaxError: %s" % e)

def test(line_list):
    asyncio.run(test_core(line_list))

if "normal" in sys.argv:
    test(["line1"])
    test(["line1", "line2"])
    test(["##! potpourri", "line2", "####"])
    test(["##! potpourri", "line 2", "line 3", "####",
          "line 5"])
    test(["line 1",
          "##! potpourri", "line 3", "line 4", "####"])
    test(["line 1",
          "##! potpourri", "line 3", "####",
          "line 5"])

if "special" in sys.argv:
    test([])
    test([""])
    test(["", ""])
    # strict framing: EOF inside an open region is a LOUD error
    test(["##! potpourri"])
    test(["##! potpourri", "line"])
    # an empty region is legal and yields an empty chunk
    test(["##! potpourri", "####"])
    # stray region end and nesting are LOUD errors
    test(["line", "####"])
    test(["##! potpourri", "##! potpourri", "####"])
    # unknown handler is a LOUD error
    test(["##! quacksalber", "####"])

if "comment" in sys.argv:
    test(["##line1"])
    test(["line1##"])
    test(["##line1", "line2"])
    test(["line1", "line2##"])
    test(["##! potpourri", "line2##", "####"])
    test(["##! potpourri", "##line2", "####"])
    test(["##! potpourri", "##line 2", "line 3", "####"])
    test(["##! potpourri", "line 2", "##line 3", "####"])
    # '#####' (5+) is commentary, NOT a region end; '####x' likewise
    test(["#####", "line1", "##! potpourri", "line2", "####"])
    test(["##! potpourri", "line1", "####x", "line2", "####"])
