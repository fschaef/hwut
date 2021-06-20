"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A chunk of 'LineAssociation' objects grouped by type.

A chunk of 'LineAssociation'-s either belongs to a block of 'LineSequences'
or 'Potpourri'.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.line_association import LineAssociation
from   vut.engine.compare.engine.input_chunk      import E_Chunk
from   vut.engine.compare.engine.analogy_db       import AnalogyDb
from   vut.external.quex.typed                    import typed

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

    def max_line_n(self):
        def _get(line, max_line_n):
            if line and line.line_n is not None and line.line_n > max_line_n: 
                return line.line_n
            else:
                return max_line_n
        result = 0
        for lina in self.__line_association_list:
            result = _get(lina.subject, result)
            result = _get(lina.nominal, result)
        return result

    def analogy_db(self):
        return self.__analogy_db

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineAssociationChunk:%s" % self.__type_id.name, [
            ("line_association_list", self.__line_association_list),
            ("analogy_db",            self.__analogy_db)
        ]

