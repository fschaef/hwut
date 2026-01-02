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
from   vut.engine.compare.engine.enums                 import E_Verdict, \
                                                              E_PotpourriBorder
from   vut.engine.compare.engine.chunk_pair            import LinePairList
from   vut.engine.compare.engine.input_chunk           import InputChunk, E_Chunk
from   vut.engine.compare.engine.line                  import Line
from   vut.engine.compare.engine.association.line_pair import LinePair

import vut.engine.compare.potpourri.association        as     association
import vut.engine.compare.potpourri.equivalence_check  as     equivalence_check

class Potpourri(InputChunk):
    """Set of lines where the sequence does not matter.
    """
    def type(self):
        return E_Chunk.POTPOURRI

    def __init__(self, start_line_n, end_line_n, iterable, config):
        def adapt(iterable, start_line_n, end_line_n):
            yield Line.from_potpourri(start_line_n, begin_f=True)
            yield from iterable
            yield Line.from_potpourri(end_line_n, begin_f=False)
        InputChunk.__init__(self, start_line_n, end_line_n, 
                            adapt(iterable, start_line_n, end_line_n), config)

    def _is_equivalent(self, subject_line_list, nominal_line_list, analogy_db):
        """RETURNS: [0] True, if both potpourris are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.
        """
        subject_potpourri = subject_line_list[1:-1] # exclude [0] and [-1]:
        nominal_potpourri = nominal_line_list[1:-1] # first and last line carry Potpourri markers.

        verdict, _, new_analogy_db = equivalence_check.do(subject_potpourri,
                                                          nominal_potpourri,
                                                          analogy_db,
                                                          abort_early_f=True)

        if verdict: return E_Verdict.EQUIVALENT, new_analogy_db
        else:       return E_Verdict.DIFFERENT, analogy_db

    def _associate_lines(self, nominal, analogy_db):
        """RETURNS: list 'LinePair'-s

        See 'InputChunk.association()' for further explanations.
        """
        assert len(self.line_list) >= 2 and len(nominal.line_list) >= 2
        subject_potpourri = self.line_list[1:-1]    # exclude [0] and [-1]:
        nominal_potpourri = nominal.line_list[1:-1] # first and last line carry Potpourri markers.

        core_result,   \
        new_analogy_db = association.do(subject_potpourri,
                                        nominal_potpourri,
                                        analogy_db,
                                        self.configuration.potpourri_max_comparison_count)

        result = [
            LinePair.potpourri_border(self.line_list[0], nominal.line_list[0], 
                                      E_PotpourriBorder.BEGIN)
        ]
        result.extend(LinePairList(core_result).sort(True))
        result.append(
            LinePair.potpourri_border(self.line_list[-1], nominal.line_list[-1],
                                      E_PotpourriBorder.END)
        )

        return result, new_analogy_db

    def __repr__(self): # pragma no cover
        return "\n".join("%03i| %s" % (line.line_n, line) for line in self.line_list)

