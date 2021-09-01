"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'Potpourri' input chunk.

LineSequence: set of text lines where the sequence DOES NOT matter.

The two main functions of 'Potpourri' are (derived from 'InputChunk')

   .compare()           --> determines whether the chunk is equivalent to
                            another.
   .line_associations() --> determines which lines should be best associated
                            for display.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.core             import E_Verdict, \
                                                         E_PotpourriBorder
from   vut.engine.compare.engine.input_chunk      import InputChunk, E_Chunk
from   vut.engine.compare.engine.line             import Line
from   vut.engine.compare.engine.line_association import LineAssociation
import vut.engine.compare.friends_pairing.similar as     friends_pairing_max
import vut.engine.compare.friends_pairing.exact   as     friends_pairing

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

    def _compare(self, nominal, analogy_db):
        """RETURNS: [0] True, if both potpourris are equivalent. False, else.
                    [1] analogy_db required for equivalence to hold.
        """
        subject_potpourri = self.line_list[1:-1]    # exclude [0] and [-1]:
        nominal_potpourri = nominal.line_list[1:-1] # first and last line carry Potpourri markers.

        verdict, _, new_analogy_db = friends_pairing.do(subject_potpourri,
                                                        nominal_potpourri,
                                                        analogy_db,
                                                        abort_f=True)

        if verdict: return E_Verdict.EQUIVALENT, new_analogy_db
        else:       return E_Verdict.DIFFERENT, analogy_db

    def _line_associations(self, nominal, analogy_db):
        """RETURNS: list 'LineAssociation'-s

        See 'InputChunk.line_associations()' for further explanations.
        """
        assert len(self.line_list) >= 2 and len(nominal.line_list) >= 2
        subject_potpourri = self.line_list[1:-1]    # exclude [0] and [-1]:
        nominal_potpourri = nominal.line_list[1:-1] # first and last line carry Potpourri markers.

        core_result,   \
        new_analogy_db = friends_pairing_max.do(subject_potpourri,
                                                nominal_potpourri,
                                                analogy_db,
                                                self.configuration.potpourri_max_comparison_count)

        result = [
            LineAssociation.potpourri_border(self.line_list[0], nominal.line_list[0], 
                                             E_PotpourriBorder.BEGIN)
        ]
        result.extend(core_result)
        result.append(
            LineAssociation.potpourri_border(self.line_list[-1], nominal.line_list[-1],
                                             E_PotpourriBorder.END)
        )

        return result, new_analogy_db

    def __repr__(self): # pragma no cover
        return "\n".join("%03i| %s" % (line.line_n, line) for line in self.line_list)

