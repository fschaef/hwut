"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Events of the Spawner component, category "SPAWNER".

    EventChildTerminationReq   parent  -> spawner   the .terminate() request
    EventChildTermination      child   -> parent    the child's exit report
    EventChildResourcesFreed   spawner -> parent    OS context reclaimed
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

    class EventChildResourcesFreed(Event):
        """The child's OS context was reclaimed; spawner -> parent.

        Reports ONE fact: the execution context (Task / thread / process
        / remote process) has been freed and no longer occupies any OS
        resource. It says nothing about the supervision verdict - that
        is EventChildStateChanged's job - and nothing about the task
        outcome - that rides on EventChildTermination.reason.

        It is emitted on EVERY freeing path. The after_deadline flag is
        the only thing that distinguishes them:

            after_deadline=False  routine reclamation AFTER a clean
                                  confirmation - the child had already
                                  reported termination; the kill is pure
                                  bookkeeping that frees the husk.
            after_deadline=True   the wait_to_kill_ms deadline elapsed
                                  WITHOUT a confirmation; this freeing is
                                  the force-kill, and the paired verdict
                                  is TERM_FAILURE - the child's results
                                  cannot be relied upon.

            last_state  the E_ChildState the FSM was in when the freeing
                        was issued.
            freed_at    wall-clock time of the freeing (time.time()).
        """

        last_state:     E_ChildState
        freed_at:       float
        after_deadline: bool

        def __str__(self) -> str:
            return "EventChildResourcesFreed(last_state=%s, freed_at=%.3f, " \
                   "after_deadline=%s)" % (self.last_state, self.freed_at,
                                           self.after_deadline)


    class EventChildStateChanged(Event):
        """The child-state machine took one transition; spawner -> parent.
        """

        old_state: E_ChildState   # state left by this transition
        new_state: E_ChildState   # state entered by this transition

        def __str__(self) -> str:
            return "EventChildStateChanged(%s -> %s)" \
                   % (self.old_state, self.new_state)
