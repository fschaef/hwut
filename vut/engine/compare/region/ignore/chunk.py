"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'ignore' region -- contents carry no significance.

Inside a '##! ignore' region ANY content on either side is accepted,
including differing line counts. The region FRAMING itself still matters:
an ignore region on one side with no region on the other is a structural
mismatch (not equivalent) -- only the CONTENTS are exempt from judgment.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.enums               import E_Chunk
from   vut.engine.compare.engine.input.input_chunk   import (
                                                 AssociationRelatedInputChunk,
                                                 EquivalenceRelatedInputChunk)
import vut.engine.compare.region.ignore.equivalence  as equivalence_ignore
import vut.engine.compare.region.ignore.associate    as association_ignore


class InputChunkIgnore(AssociationRelatedInputChunk,
                       EquivalenceRelatedInputChunk):
    def __init__(self, start_line_n, end_line_n, line_list, config,
                 params=None):
        super().__init__(E_Chunk.IGNORE, start_line_n, end_line_n,
                         line_list, config)

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        return equivalence_ignore.do(self, nominal, analogy_db)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_ignore.do(self, nominal, analogy_db)
