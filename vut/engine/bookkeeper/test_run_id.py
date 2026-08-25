"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT A TEST RUN IS, as a number -- the shape every component
         refers to a run by.

DESCRIPTION
       A TEST RUN IS A GENERALITY, not a coverage concept. It is what
       the runner performed, what the base records, what a report
       names, and what a coverage record attributes work to. So the
       shape belongs where the runs are ADMINISTERED -- here, with the
       register that issues the numbers ('test_id_db.py') and the book
       that keeps their results ('bookkeeper.py') -- and every other
       component refers DOWNWARD to it.

       TWO PARTS, because a test application and its choices are two
       levels and rename at two levels:

           app_id     the test application
           choice_id  the choice, WITHIN that application; None where
                      the test has none

       Spelled '47' and '47.66'. THE NAMES ARE NOT HERE: the register
       holds 'app_id o--o name' and 'choice_id o--o name', and a run
       id cannot be decoded without it. That is the point -- a rename
       moves a name and leaves every id standing.

       DIRECTORY-LOCAL. A run id is unique inside its own test
       directory by construction and means nothing outside it. What
       qualifies a run id ACROSS directories is the business of
       whoever aggregates, at the moment it aggregates, and is never
       stored (coverage RATIONALE D-14).
______________________________________________________________________________
"""
from dataclasses import dataclass


#  THE CEILING OF EVERY ID SCOPE (bookkeeper RATIONALE B-2): app ids,
#  choice ids, group ids each count from 0 and never reach this. A scope
#  that would issue it refuses by name. Ids are never re-issued, so a
#  scope's count only grows; 2**32 is more tests, choices or groups than
#  one directory will ever hold.
ID_LIMIT = 2 ** 32


class RunIdFault(ValueError):
    """A text that spells no run id. Named where it is met: a run id
    nobody can resolve is an attribution nobody can check."""
    pass


@dataclass(frozen=True, order=True)
class TestRunId:
    """WHO ran, as the register numbered it: the application's id, and
    the choice's where the test has choices.

    Spelled '47', or '47.66' with a choice. Carries no name; the
    register decodes it.
    """
    app_id:    int
    choice_id: int | None = None

    def __str__(self):
        """RETURN: str, 'app_id', or 'app_id.choice_id' with a choice."""
        return "%i" % self.app_id if self.choice_id is None \
               else "%i.%i" % (self.app_id, self.choice_id)


def run_id_of_text(text):
    """
    RETURN: TestRunId, what '47' or '47.66' spells.

    Raises RunIdFault where it spells neither.
    """
    part_list = text.strip().split(".")
    try:
        if len(part_list) == 1: return TestRunId(int(part_list[0]))
        if len(part_list) == 2:
            return TestRunId(int(part_list[0]), int(part_list[1]))
    except ValueError:
        pass
    raise RunIdFault("'%s' spells no run id" % text)
