"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A chunk of 'LineAssociation' objects grouped by type.

A chunk of 'LineAssociation'-s either belongs to a block of 'LineSequences'
or 'Potpourri'.
________________________________________________________________________________
"""
from   ut.engine.compare.engine.line_association import LineAssociation
from   ut.engine.compare.engine.input_chunk      import E_Chunk
from   ut.engine.quex.typed                      import typed

class LineAssociationChunk:
    """List of 'LineAssociation'-s where all line are from an input chunk
    of the same type, i.e.

            type() = E_Chunk.LINE_SEQUENCE or E_Chunk.POTPOURRI

    """
    @typed(type_id=E_Chunk, lina_list=[LineAssociation])
    def __init__(self, type_id, line_association_list):
        self.__type_id               = type_id
        self.__line_association_list = line_association_list

    def type(self):
        return self.__type_id

    def line_association_list(self):
        return self.__line_association_list
