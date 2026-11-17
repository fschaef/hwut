"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A chunk of 'LinePair' objects grouped by type.

A chunk of 'LinePair'-s either belongs to a block of 'LineSequences'
or 'Potpourri'.
________________________________________________________________________________
"""
from .line_pair import LinePair, display_twin
from .edit_operations.edit import Edit, E_EditId
import hwut.engine.compare.region.unaccepted.associate as association_unaccepted
from ..contract.enums import E_Chunk, BAD_CHUNK_SET
from ..contract.analogy_db import AnalogyDb
from ..contract.frozen_analogy_db import FrozenAnalogyDb
from ..reading.input_chunk import InputChunk

from   typeguard import typechecked

class ChunkPair(list):
    """List of 'LinePair'-s where all line are from an input chunk
    of the same type, i.e.

            type() = E_Chunk.LINE_SEQUENCE or E_Chunk.POTPOURRI

    """
    @typechecked
    def __init__(self,
                 subject_type_id:       E_Chunk,
                 nominal_type_id:       E_Chunk,
                 line_association_list: list,
                 analogy_db:            AnalogyDb | FrozenAnalogyDb | None):
        self.__subject_type_id = subject_type_id
        self.__nominal_type_id = nominal_type_id
        self.__analogy_db      = analogy_db
        super().extend(line_association_list)

    @typechecked
    @staticmethod
    def from_input_chunks(subject:    InputChunk | None,
                          nominal:    InputChunk | None,
                          analogy_db: AnalogyDb | None) -> "ChunkPair":
        """RETURNS: 'ChunkPair' generated from a subject and nominal input
                    chunk.
        """
        if subject is None:
            subject_type    = E_Chunk.NONE
            nominal_type    = nominal.type()
            line_pair_list  = [LinePair(None, n, []) for n in nominal.line_list]
            new_analogy_db  = analogy_db
        elif nominal is None:
            subject_type    = subject.type()
            nominal_type    = E_Chunk.NONE
            line_pair_list  = [LinePair(s, None, []) for s in subject.line_list]
            new_analogy_db  = analogy_db
        elif subject.type() == nominal.type():
            subject_type    = subject.type()
            nominal_type    = subject_type
            line_pair_list, \
            new_analogy_db  = subject.associate_with_nominal(nominal, analogy_db)
        else:
            #  AN 'unaccepted' NOMINAL TAKES WHATEVER STANDS OPPOSITE
            #  (C-9). Every other handler says HOW a stretch is to be
            #  read, and two readings cannot both claim one line;
            #  'unaccepted' says only WHETHER anybody has looked, which
            #  is a statement about the nominal's history and not about
            #  how to read the subject.
            #
            #  The association is driven from the NOMINAL's side here,
            #  because the dispatch elsewhere runs off the subject's
            #  type and the subject is an ordinary chunk. The argument
            #  order is unchanged: subject first, nominal second.
            assert nominal.type() in BAD_CHUNK_SET
            subject_type    = subject.type()
            nominal_type    = nominal.type()
            line_pair_list, \
            new_analogy_db  = association_unaccepted.do(subject, nominal,
                                                        analogy_db)

        head, tail = _framing_pair_list(subject, nominal,
                                        subject_type == nominal_type)
        return ChunkPair(subject_type, nominal_type,
                         head + line_pair_list + tail, new_analogy_db)

    def types(self):
        return self.__subject_type_id, self.__nominal_type_id

    def is_equivalent(self):
        """RETURNS: True, if the chunk pair as a whole preserves equivalence:
                          every contained 'LinePair' is equivalent (and, where
                          both sides exist, the chunk types agree).
                    False, else.

        This is the Lawyer's side of THE LAW (see 'contract/semantics.py'):

            is_equivalent(subject, nominal) is True
                <=>  every ChunkPair of associate(subject, nominal)
                     '.is_equivalent()'.

        NOTE: a type 'mismatch' involving E_Chunk.NONE only means the chunk is
        one-sided. For OUTER text that is decided by the line pairs (a chunk
        of purely insignificant lines is display filler, hence neutral). A
        one-sided REGION however is a FRAMING mismatch: a region must find
        its counterpart -- even an empty one (see DOC/SEMANTICS.txt sec. 7).
        """
        if self.__subject_type_id != self.__nominal_type_id:
            if E_Chunk.NONE not in (self.__subject_type_id,
                                    self.__nominal_type_id):
                return False
            present = (self.__subject_type_id
                       if self.__nominal_type_id is E_Chunk.NONE
                       else self.__nominal_type_id)
            if present not in (E_Chunk.LINE, E_Chunk.LINE_SEQUENCE):
                return False           # one-sided REGION: framing mismatch
        return all(line_pair.is_equivalent() for line_pair in self)

    def analogy_db(self):
        return self.__analogy_db

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'hwut.engine.pretty.do()'.
        """
        if self.__subject_type_id == self.__nominal_type_id:
            type_name = self.__subject_type_id.name
        else:
            type_name = "(%s,%s)" % (self.__subject_type_id.name, self.__nominal_type_id.name)

        return "ChunkPair:%s" % type_name, [
            ("<base>",     list(self)),
            ("analogy_db", self.__analogy_db)
        ]



def _framing_pair_list(subject: InputChunk | None,
                       nominal: InputChunk | None,
                       same_type_f: bool) -> tuple[list, list]:
    """RETURN: [0] list[LinePair], the pair of the regions' SHEBANG lines,
               [1] list[LinePair], the pair of their '####' lines -- each
                   [] where neither side is a region.

    A REGION'S FRAMING LINES ARE LINES OF BOTH STREAMS (regression-4):
    they are paired like any other line, so that every line of either
    stream stands in exactly one 'LinePair'. Before, only the content
    was paired; the keyed screen, building its rows from the pairs
    alone, showed the frames as partnerless and two equal files as
    '2 differ'.

    Both sides framed BY THE SAME HANDLER: GOOD where the texts are equal; GOOD_TOLERATED
    where they differ (spacing, parameters) -- whether the region's lines
    agree is the handler's verdict, carried by the content pairs, and a
    frame never adds one of its own (THE LAW: the Judge does not compare
    frame texts). Otherwise -- one side framed (a one-sided region, an
    ordinary chunk facing an 'unaccepted' one), or two handlers facing
    each other ('##! verbatim' against a virgin's '##! unaccepted') --
    every frame stands ONE-SIDED and differs, as the chunk pair does
    ('ChunkPair.is_equivalent'): a frame is never partnered with a frame
    of another handler.
    """
    s_frame = getattr(subject, "framing", None)
    n_frame = getattr(nominal, "framing", None)
    if s_frame is None and n_frame is None:
        return [], []

    def pair(s, n):
        s = display_twin(s) if s is not None else None
        n = display_twin(n) if n is not None else None
        if s is None or n is None:
            edit_id = E_EditId.DELETE if n is None else E_EditId.INSERT
            return [LinePair(s, n, (Edit(edit_id),), cost=1.0,
                             seq_edit_id=edit_id)]
        if s._string == n._string:
            edit_id, cost = E_EditId.GOOD,           0.0
        else:
            edit_id, cost = E_EditId.GOOD_TOLERATED, 0.0
        return [LinePair(s, n, (Edit(edit_id),), cost=cost,
                         seq_edit_id=edit_id)]

    s_begin, s_end = s_frame if s_frame is not None else (None, None)
    n_begin, n_end = n_frame if n_frame is not None else (None, None)
    if s_frame is not None and n_frame is not None and same_type_f:
        return pair(s_begin, n_begin), pair(s_end, n_end)

    def alone(s, n):
        return (pair(s, None) if s is not None else []) \
             + (pair(None, n) if n is not None else [])

    return alone(s_begin, n_begin), alone(s_end, n_end)
