"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A chunk of 'LineAssociation' objects grouped by type.

A chunk of 'LineAssociation'-s either belongs to a block of 'LineSequences'
or 'Potpourri'.
________________________________________________________________________________
"""
from   ut.engine.compare.engine.line_association import LineAssociation
from   ut.engine.compare.engine.input_chunk      import E_Chunk
from   ut.engine.compare.engine.analogy_db       import AnalogyDb
from   ut.engine.quex.typed                      import typed

class LineAssociationChunk:
    """List of 'LineAssociation'-s where all line are from an input chunk
    of the same type, i.e.

            type() = E_Chunk.LINE_SEQUENCE or E_Chunk.POTPOURRI

    """
    @typed(type_id=E_Chunk, lina_list=[LineAssociation], analogy_db=AnalogyDb)
    def __init__(self, type_id, line_association_list, analogy_db):
        self.__type_id               = type_id
        self.__line_association_list = line_association_list
        self.__analogy_db            = analogy_db

    def type(self):
        return self.__type_id

    def line_association_list(self):
        return self.__line_association_list

    def analogy_db(self):
        return self.__analogy_db

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'ut.engine.pretty.do()'.
        """
        return "LineAssociationChunk:%s" % self.__type_id.name, [
            ("line_association_list", self.__line_association_list),
            ("analogy_db",            self.__analogy_db)
        ]

