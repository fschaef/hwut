"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A chunk of 'LinePair' objects grouped by type.

A chunk of 'LinePair'-s either belongs to a block of 'LineSequences'
or 'Potpourri'.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.association.line_pair      import LinePair
from   vut.engine.compare.engine.enums                      import E_Chunk
from   vut.engine.compare.engine.analogy_db                 import AnalogyDb
from   vut.engine.compare.engine.frozen_analogy_db          import FrozenAnalogyDb
from   vut.engine.compare.input.input_chunk                 import InputChunk

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

