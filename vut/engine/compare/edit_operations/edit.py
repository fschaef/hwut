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

Edit = namedtuple("Edit", ("id", "transpose_ai"))

class EditSequence:
    """Maintains a list of edit objects, their cost and the required analogy database.
    """
    def __init__(self, cost, edit_list, analogy_db):
        """edit_list: list of tuples (edit_id, edit_list)

        where edit_id:    E_EditId
              edit_list': list of Edit objects
        """
        assert all(isinstance(first, E_EditId) for first, _ in edit_list)
        self.cost       = cost
        self.edit_list  = edit_list
        self.analogy_db = analogy_db

    def __iter__(self):
        yield from (self.cost, self.edit_list, self.analogy_db)

    def last(self):
        if not self.edit_list: return None
        else:                  return self.edit_list[-1][0]

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


