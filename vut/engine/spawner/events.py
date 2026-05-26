"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Events of the Spawner component, category "SPAWNER".

    EventChildTerminationReq   parent  -> spawner   the .terminate() request
    EventChildTermination      child   -> parent    the child's exit report
    EventChildKilled           spawner -> parent    deadline reached, killed
    EventChildStateChanged     spawner -> parent    every FSM edge
________________________________________________________________________________
"""

from vut.engine.event.event   import Event, category
from vut.engine.spawner.enums import E_ChildState, E_TerminationReason


with category("SPAWNER"):

    class EventChildTerminationReq(Event):
        wait_to_kill_ms: "int | None" # [ms] to wait for 'EventChildTermination'
        #                             #      after that: kill OS context
        #                             # None = wait forever until 'EventChildTermination'

        def __str__(self) -> str:
            return "EventChildTerminationReq(wait_to_kill_ms=%s)" \
                   % (self.wait_to_kill_ms,)


    class EventChildTermination(Event):
        """The child's own report that it has terminated.
        """

        reason: E_TerminationReason

        def __str__(self) -> str:
            return "EventChildTermination(reason=%s)" % (self.reason,)

    class EventChildKilled(Event):
        """The child's OS context was force-terminated; spawner -> parent.

        Emitted when the wait_to_kill_ms deadline was reached and the
        Spawner killed the OS context. 

            last_state  the E_ChildState the FSM was in when the kill
                        was issued.
            killed_at   wall-clock time of the kill (time.time()).
            grace_ms    the wait_to_kill_ms value that elapsed before
                        the kill.

        EventChildKilled means definited: something went wrong and one cannot
        rely on the child's results.
        """

        last_state: E_ChildState
        killed_at:  float
        grace_ms:   int

        def __str__(self) -> str:
            return "EventChildKilled(last_state=%s, killed_at=%.3f, " \
                   "grace_ms=%s)" % (self.last_state, self.killed_at,
                                     self.grace_ms)


    class EventChildStateChanged(Event):
        """The child-state machine took one transition; spawner -> parent.
        """

        old_state: E_ChildState   # state left by this transition
        new_state: E_ChildState   # state entered by this transition

        def __str__(self) -> str:
            return "EventChildStateChanged(%s -> %s)" \
                   % (self.old_state, self.new_state)
