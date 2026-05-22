"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Events that the event component emits about itself.

The event package itself ships no application-level events. Subsystems
(workflow, compile, network, tests) declare their own events in their
own modules using the `with category("..."):` context manager.

The only events shipped here are LIFECYCLE events that an EventTerminal
emits on the wire to inform its peer of its own state:

    EventTerminalUp     sent by a Terminal when its receive loop has
                        started and the Terminal is ready to send and
                        receive application events. The peer responds
                        with its own EventTerminalUp; once each side has
                        received the other's Up, the handshake is
                        complete and start() returns.

    EventTerminalDown   sent by a Terminal when it is shutting down
                        deliberately (stop() was called locally). The
                        peer's receive loop sees this and exits cleanly.
                        Down does NOT require a reply: the side that
                        sent Down is gone.

Neither event is dispatched to the Terminal's own local subscribers
when generated locally. Both ARE dispatched to local subscribers when
received from the peer - so a Router (or any other local consumer)
may subscribe to EventTerminalDown to learn that a peer is no longer
available.

These are wire-level lifecycle signals, not connection-error
indicators. A channel that fails mid-flight is a separate concern.
________________________________________________________________________________
"""

from vut.engine.event.event import Event, category


# ============================================================================
# EVENT_INFRA category - events that describe the event infrastructure
# itself (Terminals, and later other components if useful).
# ============================================================================

with category("EVENT_INFRA"):

    class EventTerminalUp(Event):
        """Lifecycle: a Terminal's receive loop has entered.

        Emitted on the wire on receive-loop entry. The receiving Terminal
        uses this to complete the symmetric Up-handshake; once both sides
        have received the other's Up, start() returns on both sides.
        """

        def __str__(self) -> str:
            return "EventTerminalUp"


    class EventTerminalDown(Event):
        """Lifecycle: a Terminal is shutting down deliberately.

        Emitted on the wire just before the channel is closed from this
        side. The peer's receive loop dispatches it locally (so local
        subscribers may react), and then exits cleanly when the channel
        signals closed.
        """

        def __str__(self) -> str:
            return "EventTerminalDown"
