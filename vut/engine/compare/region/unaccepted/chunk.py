"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'unaccepted' region -- contents NOT YET JUDGED, so every
         comparison meeting them FAILS (E-58).

    ##! unaccepted
    <lines nobody has looked at>
    ####

A nominal may carry such a region after a PARTIAL acceptance: the
author took some lines of a candidate and left the rest as they were
found. Those lines are not tolerated, not ignored, not compared -- they
are UNDECIDED, and a run meeting them fails until someone decides. That
failure is the region's whole purpose: it is the opposite of the
'ignore' region, which passes anything.

THE '!' IS LOAD-BEARING: '## unaccepted' would be an IGNORED commentary
line and would pass silently. '##!' is REGION_BEGIN, recognised before
the ignored-line rule ('reading/line_scanner.py').

WHICH SIDE: the region belongs in a NOMINAL. A subject carrying it is
a test application that printed the framing itself -- refused as a
fault, never compared.
________________________________________________________________________________
"""
from   vut.engine.compare.contract.enums               import E_Chunk
from   vut.engine.compare.reading.input_chunk          import (
                                                 AssociationRelatedInputChunk,
                                                 EquivalenceRelatedInputChunk)
import vut.engine.compare.region.unaccepted.equivalence as equivalence_unaccepted
import vut.engine.compare.region.unaccepted.associate   as association_unaccepted


class InputChunkUnaccepted(AssociationRelatedInputChunk,
                           EquivalenceRelatedInputChunk):
    """A stretch nobody has judged. Equivalence: never. Association:
    every pair shown as differing, with the region named."""

    def __init__(self, start_line_n, end_line_n, line_list, config,
                 params=None):
        super().__init__(E_Chunk.UNACCEPTED, start_line_n, end_line_n,
                         line_list, config)

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        return equivalence_unaccepted.do(self, nominal, analogy_db)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_unaccepted.do(self, nominal, analogy_db)
