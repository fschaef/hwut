#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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

from   vut.engine.compare.configuration    import Configuration
from   vut.auxiliary.async_helper          import AsyncIterator_ensured
from   vut.engine.compare.input.chunk_pipe import AssociationChunkPipe
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
    print(text.replace("||||", "<potpourri>"))
    print("----------------------------------")
    print("=>")
    async for x in chunk_pipe.yield_input_chunks():
        print(x)

def test(line_list):
    asyncio.run(test_core(line_list))

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
