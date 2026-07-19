"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'verbatim' region -- byte-exact, ordered comparison.

Inside a '##! verbatim' region NO tolerance applies: no numeric epsilon, no
analogies, no visible-nothing, no equivalence patterns, no whitespace
normalization. Line k of the subject region must equal line k of the
nominal region byte-for-byte, and the line counts must agree.

Per the shared substrate contract (DOC/SEMANTICS.txt sections 2, 7): BLANK
and '##'-marked lines remain INSIGNIFICANT even here -- the equivalence
pipe never delivers them, and the association face treats them as neutral
display filler. 'Verbatim' governs how CONTENT lines compare, not which
lines take part.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.enums               import E_Chunk
from   vut.engine.compare.engine.input.input_chunk   import (
                                                 AssociationRelatedInputChunk,
                                                 EquivalenceRelatedInputChunk)
import vut.engine.compare.region.verbatim.equivalence as equivalence_verbatim
import vut.engine.compare.region.verbatim.associate   as association_verbatim


class InputChunkVerbatim(AssociationRelatedInputChunk,
                         EquivalenceRelatedInputChunk):
    def __init__(self, start_line_n, end_line_n, line_list, config,
                 params=None):
        super().__init__(E_Chunk.VERBATIM, start_line_n, end_line_n,
                         line_list, config)

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        return equivalence_verbatim.do(self, nominal, analogy_db)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_verbatim.do(self, nominal, analogy_db)
