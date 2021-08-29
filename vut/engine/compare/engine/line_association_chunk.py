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

    def get_line_association(self, subject_line_n, nominal_line_n):
        for lina in self.__line_association_list:
            if lina.subject.line_n != subject_line_n: 
                continue
            elif lina.nominal.line_n != nominal_line_n:
                # 'subject.line_n' is only associated with on 'nominal.line_n'
                return # => (subject_line_n, nominal_line_n) cannot be found
            else:
                return lina

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

@typed(lina_list=[LineAssociation], sort_by_subject_f=bool)
def line_association_list_sort(lina_list, sort_by_subject_f=False):
    """RETURNS: A sorted list of 'LineAssociation' objects.

    sort_by_subject_f: sort objects by subject line numbers.
    else:              sort by nominal line number.
    """
    result = list(lina_list)
    if sort_by_subject_f:
        result.sort(key=lambda x: (1, x.nominal.line_n) if x.subject is None else (0, x.subject.line_n))
    else:
        result.sort(key=lambda x: (1, x.subject.line_n) if x.nominal is None else (0, x.nominal.line_n))
    return result

@typed(lina_chunk_list=[LineAssociationChunk])
def line_association_chunk_list_analogy_errors(lina_chunk_list, errors_f=True):
    """RETURNS: [0] lina_db: 
                    (subject line number, nominal line number) -> LineAssociation
                [1] set of (subject, nominal)

    If 'error_f' == False, than no entries are made in 'lina_db'.
                 
    Find LineAssociation-s with analogy errors.  Using a dictionary prevents 
    duplicate entries.
    """
    lina_db             = {}
    subject_nominal_set = set()
    for chunk in lina_chunk_list:
        for lina in chunk.line_association_list():
            linas_subject_nominal_set = lina.analogy_errors()
            if not linas_subject_nominal_set: 
                continue
            elif errors_f:
                lina_db[(lina.subject.line_n, lina.nominal.line_n)] = lina
            subject_nominal_set.update(linas_subject_nominal_set)

    return lina_db, subject_nominal_set

@typed(lina_chunk_list=[LineAssociationChunk])
def line_association_chunk_list_find_definitions(lina_chunk_list, subject_nominal_set):
    """RETURNS: [0] lina_db: 
                    (subject line number, nominal line number) -> LineAssociation

    Searches for LineAssociation-s where either the 'subject' or 'nominal' from
    the 'subject_nominal_set' occurrs.
    """
    def _get_lina(lina_chunk_list, subject_line_n, nominal_line_n):
        result = None
        for chunk in lina_chunk_list:
            result = chunk.get_line_association(subject_line_n, nominal_line_n)
            if result is not None: 
                break
        return result

    result = {}
    # For those analogies where errors occur, search for the definition of the
    # original analogy.
    analogy_db = lina_chunk_list[-1].analogy_db()

    for subject, nominal in subject_nominal_set:
        p = analogy_db.line_number_db.get(subject)
        if p is not None:
            result[(p.subject_line_n, p.nominal_line_n)] = _get_lina(lina_chunk_list, 
                                                                     p.subject_line_n, 
                                                                     p.nominal_line_n)
        subject = analogy_db.get_subject(nominal)
        if subject is not None:
            p = analogy_db.line_number_db.get(subject)
            result[(p.subject_line_n, p.nominal_line_n)] = _get_lina(lina_chunk_list, 
                                                                     p.subject_line_n, 
                                                                     p.nominal_line_n)

    return result

@typed(lina_chunk_list=[LineAssociationChunk], errors_f=bool, definitions_f=bool)
def line_association_chunk_list_find_entries_relevant_to_analogy_errors(lina_chunk_list, 
                                                                        errors_f=True, 
                                                                        definitions_f=True):
    """RETURNS: list of LineAssociation objects.

    Each 'LineAssociation' contains the association of a subject and a nominal line
    which is concerned with an analogy error. 
    
    errors_f:       report 'LineAssociation' containing analogy errors.
    definitions_f:  report 'LineAssociation' containing lines where analogies are
                    defined that later cause errors.
    """
    assert errors_f or definitions_f

    result, \
    subject_nominal_set = line_association_chunk_list_analogy_errors(lina_chunk_list, 
                                                                     errors_f) 

    if definitions_f:
        definition_lina_db = line_association_chunk_list_find_definitions(lina_chunk_list,
                                                                          subject_nominal_set)
        result.update(definition_lina_db)

    return list(result.values())

