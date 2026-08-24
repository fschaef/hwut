"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: SELECT -- turn the set of what exists plus a stated wish into the
         flat per-choice sequence of what runs.

'get_test_cases(CTestAppSet) -> CTestCaseSequence' is the whole interface.
What a task list holds and how it decides stays open; the two shapes here
are the first inhabitants, not the boundary.

A task that names an application or a choice the set does not carry is
refused at the door, by name.
______________________________________________________________________________
"""
from .configuration_tree import CTestCase, CTestCaseSequence


class SelectionError(Exception):
    """A wish naming what does not exist."""


class CTestTaskList:
    """The interface. One member function fixes the contract."""

    def get_test_cases(self, app_set):
        """
        RETURN: CTestCaseSequence, the cases this task list selects out
                of 'app_set'.
        """
        raise NotImplementedError


class CTestTaskListAll(CTestTaskList):
    """Everything: every choice of every application, files sorted,
    choices sorted within a file."""

    def get_test_cases(self, app_set):
        """RETURN: CTestCaseSequence, every (file, choice) of the set."""
        case_list = []
        for app in app_set:
            for choice in _sorted_choices(app):
                case_list.append(_case(app, choice, app_set))
        return CTestCaseSequence(tuple(case_list))


class CTestTaskListNamed(CTestTaskList):
    """A stated subset: file -> list of choice names, or 'None' for every
    choice of that file."""

    def __init__(self, task_db):
        """RETURN: CTestTaskListNamed over 'task_db':
        source file -> None | list of choice names."""
        self.task_db = task_db

    def get_test_cases(self, app_set):
        """
        RETURN: CTestCaseSequence, the named cases.

        Raises SelectionError, by name, for a file or a choice the set
        does not carry.
        """
        case_list = []
        for file in sorted(self.task_db):
            app = app_set.app_db.get(file)
            if app is None:
                raise SelectionError(
                    "'%s' is not a test application of this directory; "
                    "it offers: %s"
                    % (file, ", ".join(sorted(app_set.app_db)) or "nothing"))
            wanted = self.task_db[file]
            if wanted is None:
                choice_list = _sorted_choices(app)
            else:
                choice_list = []
                for choice in wanted:
                    if choice not in app.choice_db:
                        raise SelectionError(
                            "'%s' has no choice '%s'; it offers: %s"
                            % (file, choice,
                               ", ".join(_printable_choices(app))))
                    choice_list.append(choice)
            for choice in choice_list:
                case_list.append(_case(app, choice, app_set))
        return CTestCaseSequence(tuple(case_list))


def _case(app, choice, app_set):
    """
    RETURN: CTestCase, one (file, choice) with its resolved record and
            its '[MISDEP]' marking.

    A case whose dependencies cannot be met is SELECTED and reported; it
    is not silently dropped, and the wish that named it is not refused.
    """
    return CTestCase(source_file = app.source_file,
                     choice      = choice,
                     parameters  = app.choice_db[choice],
                     origin      = app.origin,
                     position    = app.position,
                     misdep_f    = (app.source_file, choice)
                                   in app_set.misdep_set)


def _sorted_choices(app):
    """RETURN: list, the app's choice names sorted; '[None]' for the
    choice-less application."""
    if None in app.choice_db: return [None]
    return sorted(app.choice_db)


def _printable_choices(app):
    """RETURN: list[str], the choice names; '-' for the choice-less."""
    return ["-" if name is None else name
            for name in _sorted_choices(app)]
