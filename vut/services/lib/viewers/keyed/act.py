"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ACT VOCABULARY -- what a keystroke MEANS.

DESCRIPTION
       A key never reaches the reducer; only an act does. That is what
       keeps the keymap a printable table instead of thirty meanings
       buried in thirty handler bodies, and it is what lets the
       line-based fallback speak the same language with a different
       table.

       THE THREE TAKES ARE THREE ACTS, not one act carrying a scope
       argument. Each names its own reach, so nothing has to ask at run
       time how far a take goes.
______________________________________________________________________________
"""
from enum import Enum, auto


class E_Act(Enum):
    """What the session is being asked to do."""
    MOVE_UP      = auto()   # the cursor of the active pane, one line
    MOVE_DOWN    = auto()
    PAGE_UP      = auto()   # the cursor of the active pane, one screen
    PAGE_DOWN    = auto()
    SCROLL_LEFT  = auto()   # the view sideways; no cursor moves
    SCROLL_RIGHT = auto()

    SWAP_PANE    = auto()   # which pane the movement keys drive
    ANCHOR       = auto()   # begin a range at the cursor

    TAKE_RANGE   = auto()   # the marked subject range -> the target
    TAKE_REGION  = auto()   # this region -> its associated region
    TAKE_ALL     = auto()   # the whole subject -> the whole nominal
    REMOVE       = auto()   # nominal lines, or a whole region, go (E-86)
    REDO         = auto()   # the act undone last, done again (E-89)
    RESET        = auto()   # the session as it opened (E-89)
    REPORT       = auto()   # the tolerance report window (E-91)
    GOTO         = auto()   # '<number>g': the cursor to that line (E-91)
    ELEMENT_NEXT = auto()   # the element cursor, to the next element
    ELEMENT_PREV = auto()   #   with meta information (E-87)

    SEARCH_DOWN  = auto()   # carries its term as the argument
    SEARCH_UP    = auto()

    HELP         = auto()   # show the keymap -- the table, not prose

    REALIGN      = auto()   # ask compare again; clears the stale count
    UNDO         = auto()
    EDIT         = auto()   # drop to '$EDITOR'
    DONE         = auto()   # 'q': what stands is written (E-89)
    CANCEL       = auto()

    def takes_f(self):
        """RETURN: bool, True where this act moves subject lines into the
                   nominal -- the three takes, and nothing else.
        """
        return self in (E_Act.TAKE_RANGE, E_Act.TAKE_REGION, E_Act.TAKE_ALL)

    def leaves_session_f(self):
        """RETURN: bool, True where this act ends the session's turn and
                   the hub takes over -- realign, edit, commit, cancel.
        """
        return self in (E_Act.REALIGN, E_Act.EDIT,
                        E_Act.DONE, E_Act.CANCEL)


class E_Pane(Enum):
    """Which side of the screen the movement keys drive."""
    SUBJECT = auto()
    NOMINAL = auto()

    def other(self):
        """RETURN: E_Pane, the pane that is not this one."""
        return E_Pane.NOMINAL if self is E_Pane.SUBJECT else E_Pane.SUBJECT
