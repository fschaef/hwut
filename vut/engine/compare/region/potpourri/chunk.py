"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'potpourri' region -- the chunk class for order-free comparison.

Inside a '##! potpourri' region the subject's content lines match the
nominal's content lines in any order. Parameters arrive registry-resolved
(shebang > Configuration.region['potpourri'] > spec default):

    max_comparisons   pair-evaluation budget (default 128)
    subset            subject is a subset of the nominal
    duplicates        literal repetitions collapse before matching

Equivalence and association delegate to 'equivalence.py' and 'associate.py'
of this directory.
________________________________________________________________________________
"""
from   typing                                   import Iterable
from   vut.engine.compare.contract.enums          import E_Chunk
from   vut.engine.compare.engine.line           import Line
from   vut.engine.compare.reading.input_chunk   import (
                                                 AssociationRelatedInputChunk,
                                                 EquivalenceRelatedInputChunk)
import vut.engine.compare.region.potpourri.equivalence as equivalence_check_potpourri
import vut.engine.compare.region.potpourri.associate   as association_potpourri


class InputChunkPotpourri(AssociationRelatedInputChunk, EquivalenceRelatedInputChunk):
    def __init__(self, start_line_n, end_line_n, line_list: Iterable[Line],
                 config, params=None):
        super().__init__(E_Chunk.POTPOURRI, start_line_n, end_line_n, line_list, config)

        # 'params' arrives fully resolved from the registry (shebang >
        # Configuration.region['potpourri'] > spec default). 'params=None'
        # happens only on DIRECT construction (unit tests, legacy factory)
        # -- then the spec default applies.
        if params is not None and params.get("max_comparisons") is not None:
            self.max_comparison_count = params["max_comparisons"]
        else:
            self.max_comparison_count = 128
        self.subset_f     = bool(params and params.get("subset"))
        self.duplicates_f = bool(params and params.get("duplicates"))

        # partition line list: lines with and without analogies
        self.analogy_line_list = []
        self.non_analogy_line_list = []
        for line in line_list:
            if line.has_analogy(): self.analogy_line_list.append(line)
            else:                  self.non_analogy_line_list.append(line)

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        """called by super().is_equivalent_to_nominal()"""
        return equivalence_check_potpourri.do(self, nominal, analogy_db)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_potpourri.do(self, nominal, analogy_db)
