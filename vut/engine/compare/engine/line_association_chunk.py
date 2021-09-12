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

from   itertools import chain

class LineAssociationChunk:
    """List of 'LineAssociation'-s where all line are from an input chunk
    of the same type, i.e.

            type() = E_Chunk.LINE_SEQUENCE or E_Chunk.POTPOURRI

    """
    @typed(type_id=E_Chunk, lina_list=[LineAssociation], analogy_db=AnalogyDb)
    def __init__(self, type_id, line_association_list, analogy_db):
        self.__type_id               = type_id
        self.__line_association_list = LineAssociationList(line_association_list)
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

    def find_indices_of_error_linas(self):
        """RETURNS: list of LineAssociation that contain some type of errors.
        """
        return [lina_i
                for lina_i, lina in enumerate(self.__line_association_list )
                if not lina.is_good()]

    def analogy_db(self):
        return self.__analogy_db

    def __pretty__(self):
        """RETURNS: Representation of object state formatted by 'vut.engine.pretty.do()'.
        """
        return "LineAssociationChunk:%s" % self.__type_id.name, [
            ("line_association_list", self.__line_association_list),
            ("analogy_db",            self.__analogy_db)
        ]

class LineAssociationList(list):
    def __init__(self, iterable=None):
        if iterable is not None: list.__init__(self, iterable)

    def sort(self, sort_by_subject_line_n_f):
        if sort_by_subject_line_n_f:
            key = lambda x: (1, x.nominal.line_n) if x.subject is None else (0, x.subject.line_n)
        else:
            key = lambda x: (1, x.subject.line_n) if x.nominal is None else (0, x.nominal.line_n)
        list.sort(self, key=key)
        return self

    def find_line_association(self, subject_line_n, nominal_line_n):
        for lina in self:
            if lina.subject.line_n != subject_line_n: 
                continue
            elif lina.nominal.line_n != nominal_line_n:
                # 'subject.line_n' is only associated with on 'nominal.line_n'
                return None # => (subject_line_n, nominal_line_n) cannot be found
            else:
                return lina
        return None

    def analogy_errors(lina_list, errors_f=True):
        """RETURNS: [0] list of LineAssociation objects
                        in the same order as in 'lina_list'
                    [1] set of (subject, nominal)

        If 'error_f' == False, than no entries are made in 'lina_db'.
                     
        Find LineAssociation-s with analogy errors.  Using a dictionary prevents 
        duplicate entries.
        """
        result              = []
        subject_nominal_set = set()
        for lina in lina_list:
            linas_subject_nominal_set = lina.analogy_errors()
            if not linas_subject_nominal_set: 
                continue
            if errors_f:
                result.append(lina)
            subject_nominal_set.update(linas_subject_nominal_set)

        return result, subject_nominal_set

    def find_definitions(self, analogy_db, subject_nominal_set):
        """RETURNS: [0] list of LineAssociation objects containing analogy
                        definitions relevant to 'subject_nominal_set'.

        Searches for LineAssociation-s where either the 'subject' or 'nominal' from
        the 'subject_nominal_set' occurrs.
        """
        def _enter(result, self, subject, analogy_db):
            if subject is None:
                return
            p = analogy_db.line_number_db.get(subject)
            if p is None:
                return
            lina = self.find_line_association(p.subject_line_n, p.nominal_line_n)
            if lina is None: 
                return
            result.append(lina)

        result = []
        # For those analogies where errors occur, search for the definition of the
        # original analogy.
        for subject, nominal in subject_nominal_set:
            _enter(result, self, subject, analogy_db)
            subject = analogy_db.get_subject(nominal)
            _enter(result, self, subject, analogy_db)

        return result

