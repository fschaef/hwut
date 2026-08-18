"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
"""
from enum import Enum, auto

class E_ChildState(Enum):
    LAUNCHED             = auto()   # startup; Up handshake not yet complete
    RUNNING              = auto()   # Up confirmed; child live and connected
    SUSPENDED            = auto()   # stopped via OS handle (process/remote)
    TERMINATING          = auto()   # .terminate() issued; awaiting confirmation
    # Terminal states:
    TERM_OK              = auto()   # terminal; child confirmed termination
    TERM_FAILURE         = auto()   # terminal; freed without confirmation
    TERM_LOST_CONNECTION = auto()   # terminal; channel broke, no information

    def is_terminal(self) -> bool:
        """RETURN: True,  if this state is one of the terminal three
                          (TERM_OK, TERM_FAILURE, TERM_LOST_CONNECTION).
                   False, if this state is still live and may transition.
        """
        return self in (E_ChildState.TERM_OK,
                        E_ChildState.TERM_FAILURE,
                        E_ChildState.TERM_LOST_CONNECTION)

    def is_live(self) -> bool:
        return not self.is_terminal()

    def __str__(self) -> str:
        """RETURN: str, the bare member name (e.g. 'RUNNING')."""
        return self.name


class E_Liveness(Enum):
    ALIVE   = auto()  # child's OS context confirmed running
    DEAD    = auto()  #         ...        confirmed gone
    UNKNOWN = auto()  #         ...        not knowable

    def __str__(self) -> str:
        """RETURN: str, the bare member name (e.g. 'ALIVE')."""
        return self.name

class E_TerminationReason(Enum):
    # The TASK's own outcome (Level 1) - distinct from the supervision
    # verdict E_ChildState.TERM_* (Level 2). These names describe what
    # happened to the WORK and deliberately do not echo a verdict word.
    DONE          = auto() # work finished.
    TERMINATED    = auto() # work unfinished; a termination request was observed.
    UNACCOMPLISHED = auto() # work did not get done (the callable raised).

    def __str__(self) -> str:
        """RETURN: str, the bare member name (e.g. 'DONE')."""
        return self.name

