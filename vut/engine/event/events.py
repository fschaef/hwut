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

    EventInfo           a per-event-TYPE descriptor sent ahead of the
                        first occurrence of each event type on the wire
                        (see EventTerminal._ensure_event_info). Carries
                        the wire-format version for that type. The
                        receiver caches it and rejects any event whose
                        type it has not first seen an EventInfo for.

EVENT_INFRA events are NEVER dispatched to a Terminal's local
subscribers - neither the ones it sends NOR the ones it receives. They
are consumed entirely inside the receive loop (handshake, peer-down,
event-info caching). To learn that a peer has gone, register a
callback via add_peer_down_callback(); subscribing to EventTerminalUp
/ EventTerminalDown / EventInfo on .dispatcher will never fire.

These are wire-level lifecycle and metadata signals, not
connection-error indicators. A channel that fails mid-flight is a
separate concern.
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
        side. The peer's receive loop consumes it internally (it fires
        peer-down callbacks) and then exits cleanly when the channel
        signals closed. It is NOT dispatched to local subscribers.
        """

        def __str__(self) -> str:
            return "EventTerminalDown"


    class EventInfo(Event):
        """Metadata: describes one event TYPE before its first use.

        Sent ahead of the first occurrence of event type 'event_id' on
        the wire. Carries the wire-format version the sender uses for
        that type. The receiver caches (event_id -> version) and rejects
        any subsequent event of a type for which no EventInfo was seen.

        Version-only today; the field set is deliberately open to grow
        (encoding kind, field schema, ...) without a new event type -
        add fields here and bump the relevant type's WIRE_VERSION.
        """
        event_id: str
        version:  int

        def __str__(self) -> str:
            return "EventInfo(%s v%d)" % (self.event_id, self.version)

