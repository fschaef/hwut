"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A chunk of 'LinePair' objects grouped by type.

A chunk of 'LinePair'-s either belongs to a block of 'LineSequences'
or 'Potpourri'.
________________________________________________________________________________
"""
from   vut.engine.compare.core.line_pair      import LinePair
from   vut.engine.compare.contract.enums                      import E_Chunk
from   vut.engine.compare.contract.analogy_db                 import AnalogyDb
from   vut.engine.compare.contract.frozen_analogy_db          import FrozenAnalogyDb
from   vut.engine.compare.reading.input_chunk                 import InputChunk

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
        else: 
            assert subject.type() == nominal.type()
            subject_type    = subject.type()
            nominal_type    = subject_type
            line_pair_list, \
            new_analogy_db  = subject.associate_with_nominal(nominal, analogy_db)

        return ChunkPair(subject_type, nominal_type, line_pair_list, new_analogy_db)

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
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        if self.__subject_type_id == self.__nominal_type_id: 
            type_name = self.__subject_type_id.name
        else:
            type_name = "(%s,%s)" % (self.__subject_type_id.name, self.__nominal_type_id.name)

        return "ChunkPair:%s" % type_name, [
            ("<base>",     list(self)),
            ("analogy_db", self.__analogy_db)
        ]

