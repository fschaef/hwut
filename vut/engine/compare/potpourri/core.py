"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'Potpourri' input chunk.

LineSequence: set of text lines where the sequence DOES NOT matter.

The two main functions of 'Potpourri' are (derived from 'InputChunk')

   .compare()           --> determines whether the chunk is equivalent to
                            another.
   .line_pairs() --> determines which lines should be best associated
                            for display.
________________________________________________________________________________
"""
from   vut.engine.compare.input.input_chunk            import InputChunk


class Potpourri(InputChunk):
    """Set of lines where the sequence does not matter.
    """
    pass
