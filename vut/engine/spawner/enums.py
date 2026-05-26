"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Spawner enumerations.

Two enums live here:

    E_ChildState   the states of the child-state machine the Spawner
                   runs to track a launched child.
    E_Liveness     the three-valued answer to "is the child's OS
                   context still alive?" - consulted by the Spawner's
                   watchdog to choose a terminal verdict.

Both are plain leaf enums with no dependency on the rest of the
component, which is why they share this module: handles.py,
state_machine.py and spawner.py all import from here, so neither enum
can live in any of those without risking an import cycle.

E_CHILDSTATE
------------
The state set and its transitions are specified in README.txt (section
"CHILD STATE MACHINE") and motivated in DISCUSSION.txt (D6, D7, D8). The
short version:

    LAUNCHED              internal startup; child launched, Up handshake
                          not yet complete.
    RUNNING               Up handshake confirmed; child live and connected.
    SUSPENDED             child stopped via its OS handle (process/remote
                          only).
    TERMINATING           .terminate() issued; awaiting the child's
                          confirmation of proper termination.
    TERM_OK               terminal; child CONFIRMED termination - it ended
                          in mutual agreement.
    TERM_FAILURE          terminal; resources freed BEFORE or WITHOUT any
                          confirmation - functional outcome unknown.
    TERM_LOST_CONNECTION  terminal; the channel broke - the Spawner has NO
                          information about the child at all.

________________________________________________________________________________
"""
from enum import Enum, auto


class E_ChildState(Enum):
    """Lifecycle state of a Spawner-launched child.

    The three TERM_* members are terminal: once entered, no transition
    leaves them. Every other member is live and may transition onward
    (and any live state may fall to TERM_LOST_CONNECTION).

    is_terminal() answers whether a given member is one of the terminal
    three, so callers polling .child_state() can stop polling without
    hard-coding the member set.
    """

    LAUNCHED             = auto()   # startup; Up handshake not yet complete
    RUNNING              = auto()   # Up confirmed; child live and connected
    SUSPENDED            = auto()   # stopped via OS handle (process/remote)
    TERMINATING          = auto()   # .terminate() issued; awaiting confirmation
    TERM_OK              = auto()   # terminal; child confirmed termination
    TERM_FAILURE         = auto()   # terminal; freed without confirmation
    TERM_LOST_CONNECTION = auto()   # terminal; channel broke, no information

    def is_terminal(self) -> bool:
        """RETURN: True,  if this state is one of the terminal three
                          (TERM_OK, TERM_FAILURE, TERM_LOST_CONNECTION).
                   False, if this state is still live and may transition.

        Lets a caller polling .child_state() decide when to stop without
        repeating the terminal-member set at the call site.
        """
        return self in (E_ChildState.TERM_OK,
                         E_ChildState.TERM_FAILURE,
                         E_ChildState.TERM_LOST_CONNECTION)

    def is_live(self) -> bool:
        """RETURN: True,  if this state is live (the child may still be
                          running or about to run).
                   False, if this state is terminal.

        The exact complement of is_terminal(); provided so call sites
        read positively where that is clearer.
        """
        return not self.is_terminal()

    def __str__(self) -> str:
        """RETURN: str, the bare member name (e.g. 'RUNNING')."""
        return self.name


# ============================================================================
# E_Liveness - the three-valued liveness answer
# ============================================================================

class E_Liveness(Enum):
    """The three possible answers to ChildHandle.is_alive().

        ALIVE    the child's OS context is confirmed running.
        DEAD     the child's OS context is confirmed gone.
        UNKNOWN  the handle could not be consulted - e.g. a remote
                 agent did not answer. NOT a synonym for either of the
                 above: it means the spawner has no information.

    The Spawner's watchdog maps these onto FSM verdicts: DEAD -> the
    child terminated (TERM_FAILURE if unconfirmed), ALIVE or UNKNOWN ->
    TERM_LOST_CONNECTION (DISCUSSION.txt D8 - "no information").

    Lives here, beside E_ChildState, because it is a plain leaf enum
    with no dependency on the rest of the component: handles.py,
    state_machine.py and spawner.py all import it, so it cannot live in
    any of them without risking an import cycle.
    """

    ALIVE   = auto()
    DEAD    = auto()
    UNKNOWN = auto()

    def __str__(self) -> str:
        """RETURN: str, the bare member name (e.g. 'ALIVE')."""
        return self.name
