"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: A chunk of 'LinePair' objects grouped by type.

A chunk of 'LinePair'-s either belongs to a block of 'LineSequences'
or 'Potpourri'.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.line_pair import LinePair
from   vut.engine.compare.engine.input_chunk      import E_Chunk
from   vut.engine.compare.engine.analogy_db       import AnalogyDb
from   vut.external.quex.typed                    import typed

from   itertools import chain

class LinePairList(list):
    def __init__(self, iterable=None):
        if iterable is not None: 
            list.__init__(self, iterable)

    def sort(self, sort_by_subject_line_n_f):
        if sort_by_subject_line_n_f:
            key = lambda x: (1, x.nominal.line_n) if x.subject is None else (0, x.subject.line_n)
        else:
            key = lambda x: (1, x.subject.line_n) if x.nominal is None else (0, x.nominal.line_n)
        list.sort(self, key=key)
        return self

    def find_line_association(self, subject_line_n, nominal_line_n):
        for i, lina in enumerate(self):
            if lina.subject.line_n != subject_line_n: 
                continue
            elif lina.nominal.line_n != nominal_line_n:
                # 'subject.line_n' is only associated with on 'nominal.line_n'
                return None # => (subject_line_n, nominal_line_n) cannot be found
            else:
                return i
        return None

    def analogy_errors(lina_list, errors_f=True):
        """RETURNS: [0] list of indices of LinePair objects
                        in the same order as in 'lina_list'
                    [1] set of (subject, nominal)

        If 'error_f' == False, than no entries are made in 'lina_db'.
                     
        Find LinePair-s with analogy errors.  Using a dictionary prevents 
        duplicate entries.
        """
        result              = []
        subject_nominal_set = set()
        for i, lina in enumerate(lina_list):
            linas_subject_nominal_set = lina.analogy_errors()
            if not linas_subject_nominal_set: 
                continue
            if errors_f:
                result.append(i)
            subject_nominal_set.update(linas_subject_nominal_set)

        return result, subject_nominal_set

    def max_line_n(self):
        def _get(line, max_line_n):
            if line and line.line_n is not None and line.line_n > max_line_n: 
                return line.line_n
            else:
                return max_line_n
        result = 0
        for lina in self:
            result = _get(lina.subject, result)
            result = _get(lina.nominal, result)
        return result

    def indices_plain(self):
        return range(len(self))

    def indices_error(self):
        """RETURNS: list of LinePair that contain some type of errors.
        """
        return [lina_i
                for lina_i, lina in enumerate(self)
                if not lina.is_good_or_tolerated()]

    def indices_error_and_tolerated(self):
        """RETURNS: list of LinePair that contain some type of errors.
        """
        return [lina_i
                for lina_i, lina in enumerate(self)
                if not lina.is_good()]

    def indices_analogy_definitions(self, analogy_db, subject_nominal_set):
        """RETURNS: [0] list of indices of LinePair objects containing analogy
                        definitions relevant to 'subject_nominal_set'.

        Searches for LinePair-s where either the 'subject' or 'nominal' from
        the 'subject_nominal_set' occurrs.
        """
        def _enter(result, subject, analogy_db):
            if subject is None:
                return
            p = analogy_db.line_number_db.get(subject)
            if p is None:
                return
            lina_index = self.find_line_association(p.subject_line_n, p.nominal_line_n)
            if lina_index is None: 
                return
            result.append(lina_index)

        result = []
        # For those analogies where errors occur, search for the definition of the
        # original analogy.
        for subject, nominal in subject_nominal_set:
            _enter(result, subject, analogy_db)
            subject = analogy_db.get_subject(nominal)
            _enter(result, subject, analogy_db)

        return result

    def __pretty__(self):
        return "LinePairList", list(self)

class ChunkPair(LinePairList):
    """List of 'LinePair'-s where all line are from an input chunk
    of the same type, i.e.

            type() = E_Chunk.LINE_SEQUENCE or E_Chunk.POTPOURRI

    """
    @typed(type_id=E_Chunk, lina_list=[LinePair], analogy_db=AnalogyDb)
    def __init__(self, subject_type_id, nominal_type_id, line_association_list, analogy_db):
        self.__subject_type_id = subject_type_id
        self.__nominal_type_id = nominal_type_id
        self.__analogy_db      = analogy_db
        LinePairList.extend(self, line_association_list)

    @staticmethod
    def from_input_chunks(subject, nominal, analogy_db):
        """RETURNS: 'ChunkPair' generated from a subject and nominal input 
                    chunk.
        """

        if subject is None:
            subject_type   = E_Chunk.NONE
            nominal_type   = nominal.type()
            line_pair_list = [LinePair(None, x, edit_list=[]) for x in nominal.line_list]
            new_analogy_db = analogy_db
        elif nominal is None:
            subject_type   = subject.type()
            nominal_type   = E_Chunk.NONE
            line_pair_list = [LinePair(x, None, edit_list=[]) for x in subject.line_list]
            new_analogy_db = analogy_db
        else: 
            assert subject.type() == nominal.type()
            nominal_type = subject_type = subject.type()
            line_pair_list,             \
            new_analogy_db              = subject.line_associations(nominal, 
                                                                   analogy_db)

        return ChunkPair(subject_type, nominal_type, line_pair_list, new_analogy_db)

    def types(self):
        return self.__subject_type_id, self.__nominal_type_id

    def same_type(self):
        """RETURNS: E_Chunk - type id if subject and nominal have the same type.
                    None, else.
        """
        if self.__subject_type_id == self.__nominal_type_id: return self.__subject_type_id
        else:                                                return None

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
            ("<base>",     LinePairList(self)),
            ("analogy_db", self.__analogy_db)
        ]

