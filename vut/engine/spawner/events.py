"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Events of the Spawner component, category "SPAWNER".

Four events, all under one category. Per DISCUSSION.txt D10 the class
names do NOT repeat the "spawner" prefix - the category already says it.
Renaming a class or moving its category breaks every wire consumer, so
the names below are frozen.

    EventChildTerminationReq   parent  -> spawner   the .terminate() request
    EventChildTermination      child   -> parent    the child's exit report
    EventChildKilled           spawner -> parent    deadline reached, killed
    EventChildStateChanged     spawner -> parent    every FSM edge

Per event.py: concrete Event subclasses are written WITHOUT @dataclass
(the EventMeta metaclass applies dataclass(frozen=True, kw_only=True)),
with fields as plain annotations. The base supplies the 'timestamp'
field; subclasses add their own.
________________________________________________________________________________
"""
from enum import Enum, auto

from vut.engine.event.event   import Event, category
from vut.engine.spawner.enums import E_ChildState


# ============================================================================
# Reason enum for EventChildTermination
# ============================================================================

class E_TerminationReason(Enum):
    COMPLETED  = auto() # work finished. 
    TERMINATED = auto() # work unfinished, termination request came early.
    FAILED     = auto() # failed to produce work

    def __str__(self) -> str:
        """RETURN: str, the bare member name (e.g. 'COMPLETED')."""
        return self.name


# ============================================================================
# SPAWNER category - child-supervision events.
# ============================================================================
with category("SPAWNER"):

    class EventChildTerminationReq(Event):
        """Request to terminate the child; parent -> spawner.

        Emitted by SpawnerParentEventTerminal.terminate(). It is a
        REQUEST only (DISCUSSION.txt D2/D3): the parent terminal emits
        it through the router and the Spawner, not the terminal, acts on
        it. Designing the hand-off as an event rather than a local
        method call is what lets the Spawner move off the parent's
        context later without rewriting the parent contract (D3).

        wait_to_kill_ms is the grace period before a force-kill:
            int   -- milliseconds to wait for the child's confirmation
                     before killing the OS context.
            None  -- wait forever; never force-kill. MANDATORY value for
                     a 'thread' child, which has no force path at all.
        """

        wait_to_kill_ms: "int | None"

        def __str__(self) -> str:
            return "EventChildTerminationReq(wait_to_kill_ms=%s)" \
                   % (self.wait_to_kill_ms,)


    class EventChildTermination(Event):
        """The child's own report that it has terminated; child -> parent.

        Emitted on the wire by the child side as it winds down. Its
        arrival is the CONFIRMATION the Spawner's TERMINATING state
        waits for: receiving it before resources are forcibly freed is
        exactly what distinguishes TERM_OK from TERM_FAILURE (see
        DISCUSSION.txt D7).

        'reason' is the child's functional verdict on itself; see
        E_TerminationReason.
        """

        reason: E_TerminationReason

        def __str__(self) -> str:
            return "EventChildTermination(reason=%s)" % (self.reason,)


    class EventChildKilled(Event):
        """The child's OS context was force-terminated; spawner -> parent.

        Emitted when the wait_to_kill_ms deadline was reached and the
        Spawner killed the OS context. It records the circumstances of
        the kill; it does NOT itself promise anything about the child's
        functional state or resource cleanup - that is precisely what
        was unknown at kill time.

            last_state  the E_ChildState the FSM was in when the kill
                        was issued.
            killed_at   wall-clock time of the kill (time.time()).
            grace_ms    the wait_to_kill_ms value that elapsed before
                        the kill.

        A kill following a TERM_OK confirmation is NOT a contradiction
        (DISCUSSION.txt D7): the child already reported functional
        completion; the kill is pure reclamation of the OS context.
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

        Emitted on EVERY edge of the FSM (DISCUSSION.txt D6), so a
        caller may either poll SpawnerParentEventTerminal.child_state()
        or await a specific transition via the dispatcher's expect_*
        helpers.

            old_state  the E_ChildState left by this transition.
            new_state  the E_ChildState entered by this transition.
        """

        old_state: E_ChildState
        new_state: E_ChildState

        def __str__(self) -> str:
            return "EventChildStateChanged(%s -> %s)" \
                   % (self.old_state, self.new_state)
