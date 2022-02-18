"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Classes for 'E_EditId, 'Edit' and 'EditSequence'.

An edit operation at a specific position in the subject sequence in order to
adapt to a setting of an accordin position in the nominal sequence. 

E_EditId:     identifies the operation (INSERT, DELETE, SUBSTITUTE, etc.)

Edit:         identifies names the operation and provides a possible 
              additional parameter (the transpose index, if required)

EditSequence: maintains a list of edit objects. 
"""
from  vut.engine.compare.tolerance.line_element import LineElement, E_ToleranceId
from  vut.external.quex.typed                   import typed

from  collections import namedtuple
from  enum        import IntEnum

class E_EditId(IntEnum):
    """Operations moving/substituting in subject to produce nominal.
    """
    GOOD            = 0  # Subject and nominal 'element' object are equivalent.
    GOOD_TOLERATED  = 1  # == GOOD, only that content may differ (used in diff-display).
    GOOD_INSERT     = 9  # == GOOD, nominal has a 'visible nothing' where subject has nothing.
    GOOD_DELETE     = 8  # == GOOD, subject has a 'visible nothing' where nominal has nothing.
    TRANSPOSE       = 2  # Heal: Two 'element' objects in subject are transposed.
    INSERT          = 3  # Heal: 'element' from nominal is inserted.
    DELETE          = 4  # Heal: 'element' from subject is deleted.
    SUBSTITUTE      = 5  # Bad:  Content of subject and nominal 'element' differs.
    SUBSTITUTE_TYPE = 6  # Bad:  Type of subject and nominal 'element' differs.
    NONE            = 7  # No operation

class Edit:
    def __init__(self, id, transpose_ai=None, edit_list=None):
        assert transpose_ai is None or edit_list is None
        self.id        = id
        if   transpose_ai is not None: self.__auxiliary = transpose_ai
        elif edit_list    is not None: self.__auxiliary = edit_list
        else:                          self.__auxiliary = None

    @property
    def transpose_ai(self):
        return self.__auxiliary

    @property
    def edit_list(self):
        return self.__auxiliary

class EditSequence:
    """Maintains a list of edit objects, their cost and the required analogy database.
    """
    def __init__(self, cost, edit_list, analogy_db):
        """edit_list: list of tuples (edit_id, edit_list)

        where edit_id:    E_EditId
              edit_list': list of Edit objects
        """
        assert all(isinstance(x, Edit) for x in edit_list)
        self.cost       = cost
        self.edit_list  = edit_list
        self.analogy_db = analogy_db

    def __iter__(self):
        yield from (self.cost, self.edit_list, self.analogy_db)

    def last(self):
        if not self.edit_list: return None
        else:                  return self.edit_list[-1].id

    def extend(self, edit_iterable):
        self.edit_list.extend(edit_iterable)

    @staticmethod
    def describe(raw_edit_tuple):
        if not raw_edit_tuple:
            return "[]"
        def _iterable(raw_edit_tuple):
            for i, edit in enumerate(raw_edit_tuple):
                if edit.id != E_EditId.TRANSPOSE:
                    yield edit.id.name 
                else:
                    yield "%s:%i<->%i" % (edit.id.name, i, edit.transpose_ai)
        return "[%s]" % ", ".join(_iterable(raw_edit_tuple))

    def prepare_as_best(self, separator_db=None, relative_f=False):
        if separator_db:
            if relative_f and self.cost != 0: 
                self.cost /= separator_db.original_max_cost
            self.edit_list = separator_db.reinsert_separators(self.edit_list)
        return self


def list_EditDELETE(line_element_list):
    """RETURNS: List of Edit GOOD_DELETE/DELETE objects depending on the 
                according line element being 'visible nothing' or not.

    ASSUMPTION: 'nominal_line_element_list' is empty.
    """
    def iterable(line_element_list):
        for le in line_element_list.sequence:
            if le.tolerance_id == E_ToleranceId.VISIBLE_NOTHING: yield Edit(E_EditId.GOOD_DELETE)
            else:                                                yield Edit(E_EditId.DELETE)
    return list(iterable(line_element_list))

def list_EditINSERT(nominal_line_element_list):
    """RETURNS: List of Edit GOOD_INSERT/INSERT objects depending on the 
                according line element being 'visible nothing' or not.

    ASSUMPTION: 'subject_line_element_list' is empty.
    """
    def iterable(nominal_line_element_list):
        for le in nominal_line_element_list.sequence:
            if le.tolerance_id == E_ToleranceId.VISIBLE_NOTHING: yield Edit(E_EditId.GOOD_INSERT)
            else:                                                yield Edit(E_EditId.INSERT)
    return list(iterable(nominal_line_element_list))

def list_EditGOOD(subject_line_element_list, nominal_line_element_list, func_is_visible_nothing, func_is_identical):
    """RETURNS: List of Edit GOOD/GOOD_TOLERATED/GOOD_INSERT/GOOD_DELETE 
                objects depending on the according line element being 
                'visible nothing' or not.

    ASSUMPTION: 'subject_line_element_list' and 'nominal_line_element_list' are judged
                 as 'equivalent'.
    """
    def iterable(subject_line_element_list, nominal_line_element_list, is_visible_nothing, is_identical):
        Ls, Ln = len(subject_line_element_list), len(nominal_line_element_list)
        si, ni = 0, 0
        while 1 + 1 == 2:
            if si >= Ls:
                for _ in range(Ln - ni): 
                    yield Edit(E_EditId.GOOD_INSERT)
                break
            elif ni >= Ln:
                for _ in range(Ls - si): 
                    yield Edit(E_EditId.GOOD_DELETE)
                break
            else:
                subject = subject_line_element_list[si]
                nominal = nominal_line_element_list[ni]
                if is_identical(subject, nominal): 
                    op = E_EditId.GOOD
                elif is_visible_nothing(subject):
                    if is_visible_nothing(nominal): op = E_EditId.GOOD_TOLERATED
                    else:                           op = E_EditId.GOOD_INSERT
                else:
                    if is_visible_nothing(nominal): op = E_EditId.GOOD_INSERT
                    else:                           op = E_EditId.GOOD_TOLERATED

            yield Edit(op, None)
            if   op == E_EditId.GOOD:           si += 1; ni += 1
            elif op == E_EditId.GOOD_TOLERATED: si += 1; ni += 1
            elif op == E_EditId.GOOD_INSERT:    ni += 1
            elif op == E_EditId.GOOD_DELETE:    si += 1
            else:                               assert False

    return list(iterable(subject_line_element_list, nominal_line_element_list, 
                         func_is_visible_nothing, func_is_identical))


# @typed(subject_list=[LineElement], nominal_list=[LineElement])
def list_EditGOOD_line(subject_list, nominal_list):
    return list_EditGOOD(subject_list, nominal_list,
                         lambda le:               le.tolerance_id == E_ToleranceId.VISIBLE_NOTHING,
                         lambda subject, nominal: subject.string == nominal.string)

# @typed(subject_list=[Line], nominal_list=[Line])
def list_EditGOOD_line_sequence(subject_list, nominal_list):
    return list_EditGOOD([x.sequence for x in subject_list], [x.sequence for x in nominal_list],
                         lambda le_list: 
                         all(le.tolerance_id == E_ToleranceId.VISIBLE_NOTHING for le in le_list),
                         lambda subject, nominal: 
                         len(subject) == len(nominal) \
                         and all(s.string == n.string for s, n in zip(subject, nominal)))

