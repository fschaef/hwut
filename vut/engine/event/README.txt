================================================================================
VUT Event Component
================================================================================

PURPOSE

    This package provides the Event system for VUT: identity, structured
    data, in-process dispatch, point-to-point transport across processes
    or machines, and one-to-many routing. Every interaction between
    subsystems that needs to cross a queue or process boundary travels
    as an Event.


--------------------------------------------------------------------------------
DESIGN AT A GLANCE
--------------------------------------------------------------------------------

    Three layers, each with one concern:

        +----------------------------------------------------------+
        |  Event   (identity + data)                               |
        |    Frozen dataclass per concrete event kind.             |
        |    .category   (str, set by surrounding category() block)|
        |    .id         (composite "<category>.<__name__>",       |
        |                 auto-set at registration)                |
        +----------------------------------------------------------+
                              |
                              v  (carried in)
        +----------------------------------------------------------+
        |  EventChannel  (point-to-point transport)                |
        |    Async send / receive / close.                         |
        |    Subclasses per transport flavour:                     |
        |      AsyncQueueChannel    in-process, asyncio.Queue      |
        |      ThreadQueueChannel   in-process, thread queue       |
        |      ProcessQueueChannel  cross-process, mp.Queue +      |
        |                           Marshaller                     |
        |      RemoteChannel        cross-machine, socket +        |
        |                           Marshaller                     |
        |  EventChannelParameter (ECP)                             |
        |    Single class. for_async / for_thread / for_process /  |
        |    for_remote factories each return a PAIR of ECPs.      |
        |    EventTerminal(ecp) is the protocol-agnostic           |
        |    constructor.                                          |
        +----------------------------------------------------------+
                              |
                              v  (owned by)
        +----------------------------------------------------------+
        |  EventTerminal  (one end of a Channel)                   |
        |    .send(event)        ship to peer                      |
        |    .dispatcher         receive-side EventDispatcher      |
        |    .start() / .stop()  manage receive loop               |
        +----------------------------------------------------------+
                                   |
              +--------------------+--------------------+
              |                                         |
              v  (one peer per Terminal)                v
        +----------+                              +----------+
        |  peer A  |  ...  many Terminals, one    |  peer B  |
        +----------+       Channel each           +----------+
              |                                         |
              v  (all owned by)                         v
        +----------------------------------------------------------+
        |  EventRouter  (hub of Terminals)                         |
        |    .add_entry(predicate, terminal,                       |
        |               source_terminal_list=None) -> handle       |
        |    .remove_entry(handle) -> bool                         |
        |    .publish(event)                                       |
        |    .publish_from(source, event)                          |
        |  Internally an EventDispatcher whose sinks are Terminals.|
        +----------------------------------------------------------+

    The EventDispatcher (predicate-to-sink matcher) is the shared
    matching primitive, used both INSIDE a Terminal (for its
    receive-side fan-out) and INSIDE a Router (for its outgoing
    selection). One filter API; two contexts.


--------------------------------------------------------------------------------
FILE LAYOUT
--------------------------------------------------------------------------------

    event.py              Event base class, category() context manager,
                          CLASS_BY_ID, lookup_event_class, all_event_classes,
                          all_categories, EventIdCollision,
                          EventDefinitionOutsideCategoryContext,
                          EventRegistrationLocked
    events.py             Concrete Event subclasses, organised by category
    marshaller.py         Marshaller (wire serialisation; used internally
                          by ProcessQueueChannel and RemoteChannel)

    dispatcher.py         EventDispatcher, Subscription
    channel.py            EventChannel ABC, AsyncQueueChannel,
                          ThreadQueueChannel, ProcessQueueChannel,
                          RemoteChannel
    channel_parameter.py  EventChannelParameter, E_TransportKind
    terminal.py           EventTerminal
    router.py             EventRouter

    __init__.py           Public surface

    README.txt            This file
    DISCUSSIONS.txt       Decision history and rationale

    TEST/
      test-category.py      5 choices (context manager behaviour)
      test-events.py        5 choices (shipped events + lock)
      test-marshaller.py    3 choices
      test-dispatcher.py    4 choices
      test-channel.py       4 choices
      test-terminal.py      5 choices (incl. handshake, context_manager)
      test-router.py        4 choices (incl. peer_down_removes)
      GOOD/                 30 expected-output files


--------------------------------------------------------------------------------
KEY CONCEPTS
--------------------------------------------------------------------------------

1. EVENTS LIVE INSIDE CATEGORY CONTEXTS

   A category is a user-defined string. Event classes are defined
   inside a `with category("NAME"):` block; every class in the
   block joins that category:

       from vut.engine.event import Event, category

       with category("MY_SUBSYSTEM"):
           class EventThingHappened(Event):
               subject: str

   On class creation:
       -- .category    is stamped from the open block
       -- .id          is composite ("MY_SUBSYSTEM.EventThingHappened")
       -- The class is registered in CLASS_BY_ID under its composite id
       -- A duplicate name in the SAME category raises EventIdCollision
       -- The SAME name in a DIFFERENT category is fine

   Defining an Event subclass outside any open category raises
   EventDefinitionOutsideCategoryContext.

   Adding a new event is ONE step: declare the class inside the
   appropriate `with category(...)` block.

   Inheritance carries fields and behaviour. The child's category
   comes from its OWN `with category(...)` block, not from its
   parent:

       with category("PARENT_CAT"):
           class EventBase(Event):
               task_id: int
       with category("CHILD_CAT"):
           class EventDerived(EventBase):            # parent in PARENT_CAT
               extra: str
       # EventBase.id    == "PARENT_CAT.EventBase"
       # EventDerived.id == "CHILD_CAT.EventDerived"


2. CATEGORIES ARE USER-DEFINED STRINGS

   Categories carve the event namespace by subsystem (or any other
   grouping the user finds natural). The event package itself does
   not ship a closed set; subsystems declare their own.

   Example categories a project might use:

       "WORKFLOW"      task lifecycle, artifact production
       "COMPILATION"   compiler / codegen events
       "NETWORK"       connection state, transport-level events
       "TEST_RESULT"   outcomes of test execution
       "DIAGNOSTIC"    logging, observability

   Consumers filter naturally by category ("subscribe to everything
   in WORKFLOW"); other filter axes (by id, by source, by workload)
   are expressed as predicates.

   The wire id is the composite "<category>.<class_name>". Categories
   may not contain a '.' (reserved as the separator).

   Categories may span files. Multiple `with category("WORKFLOW"):`
   blocks in different modules each contribute events to the WORKFLOW
   category. Same-name collisions within the category still raise.

   THE EVENT PACKAGE SHIPS ONE CATEGORY: "EVENT_INFRA"

   The package itself defines only EventTerminalUp and
   EventTerminalDown (in category EVENT_INFRA) - the wire-level
   lifecycle messages a Terminal uses to talk about itself to its
   peer. All application events live in user code.


3. PYDANTIC VIA TypeAdapter

   Event subclasses are plain @dataclass(frozen=True, kw_only=True)
   classes, NOT BaseModel. Each subclass lazily gets a Pydantic
   TypeAdapter on first as_dict() / from_dict() use. This buys real
   Pydantic validation at wire boundaries without forcing every Event
   class into the BaseModel hierarchy.


4. EVENTDISPATCHER: PREDICATE-TO-SINK MATCHING

   The Dispatcher is the foundational matching primitive. It supports
   three subscribe shapes and three sink kinds:

       subscribe_on_event(class_or_name, sink)
       subscribe_on_category(category,   sink)
       subscribe_on_predicate(fn,        sink)

       sinks may be:  - async callable (scheduled via create_task)
                      - sync callable  (called inline)
                      - object with .send(event)

   At construction, enforce_async_callbacks_f=True rejects sync
   callables - intended for low-latency contexts (Terminal receive
   loops).


5. EVENTCHANNEL: BIDIRECTIONAL POINT-TO-POINT

   A Channel is the wire between two Terminals. Async send/receive/close
   regardless of underlying transport. Subclasses per transport flavour
   (asyncio.Queue, thread Queue, multiprocessing.Queue, socket).

   When a Channel ends, the transport ends. There is no transport-layer
   notion to keep alive past the Channel's lifetime.


6. EVENTCHANNELPARAMETER: PROTOCOL-AGNOSTIC CONSTRUCTION

   ECP is a single class with classmethod factories per transport.
   Each factory returns a PAIR of ECPs - one for each side of the
   connection.

       a_ecp, b_ecp = EventChannelParameter.for_async()
       a_ecp, b_ecp = EventChannelParameter.for_thread()
       a_ecp, b_ecp = EventChannelParameter.for_process()
       a_ecp, b_ecp = EventChannelParameter.for_remote(host, port)

   The ECP is passable through the spawning mechanism that creates the
   peer:
       - asyncio: pair stays on one loop, no spawning needed
       - thread: pair is shared between main thread and worker thread
       - process: pair is pickled across multiprocessing.spawn
       - remote: one ECP travels (somehow) to the remote machine

   EventTerminal(ecp) is the SAME constructor for all of them.


7. EVENTTERMINAL: ONE END OF A CHANNEL

   Constructed with an ECP; channel construction is deferred to
   start() because some channels (RemoteChannel) build asynchronously.

       term = EventTerminal(ecp)
       term.dispatcher.subscribe_on_*(...)    # local handlers
       await term.start()                     # build, recv loop, HANDSHAKE
       await term.send(event)                 # ship to peer
       await term.stop()                      # send Down, tear down

   Or as an async context manager (start/stop run on enter/exit, also
   on exception):

       async with EventTerminal(ecp) as term:
           term.dispatcher.subscribe_on_event(SomeEvent, handler)
           await term.send(some_event)

   HANDSHAKE (Up / Down lifecycle)

   start() does not return until the peer has confirmed it is up. On
   entry of the receive loop, each side sends EventTerminalUp on the
   wire. start() blocks in state UP_PENDING until the peer's Up
   arrives, then transitions to UP and returns.

   The protocol is symmetric: both sides send Up; both sides wait for
   the other's Up. There is no client/server role. Because both sides
   block, both starts must run concurrently (use asyncio.gather):

       await asyncio.gather(a.start(), b.start())   # correct
       await a.start(); await b.start()             # deadlock

   stop() sends EventTerminalDown on the wire (best-effort), cancels
   the receive loop, and closes the channel. The peer's receive loop
   sees the Down and exits cleanly. Down receives no reply: the side
   that sent it is gone.

   The receive-side dispatcher uses enforce_async_callbacks_f=True;
   sync callbacks would block the receive loop. For sync work, use
   an object-with-.send sink that pushes to a thread Queue for
   separate processing.

   EVENT_INFRA events received from the peer are handled internally
   (state transitions). They are NOT forwarded to the user's
   .dispatcher; subscribing to EventTerminalUp / EventTerminalDown
   on .dispatcher will never fire. To learn that a peer has gone
   down, register a callback via set_peer_down_callback(). The
   EventRouter uses this hook to auto-remove entries when peers
   close.


8. EVENTROUTER: HUB OF TERMINALS

       router = EventRouter()
       handle = router.add_entry(
                    predicate            = lambda ev: ...,
                    terminal             = some_terminal,
                    source_terminal_list = [t1, t2, None],   # optional
                )
       router.publish(event)              # source=None
       router.publish_from(src, event)    # tagged with origin
       router.remove_entry(handle)        # -> bool

   Internally an EventDispatcher whose sinks are RouterEntry wrappers
   around Terminals. Predicate matching is the same as Dispatcher's;
   source_terminal_list adds an origin filter (None means "matches
   local publish() calls").

   PEER-DOWN AUTO-REMOVAL

   add_entry() wires a peer-down callback on the Terminal. When the
   peer of that Terminal sends EventTerminalDown, the Router
   automatically removes the entry. The dispatch table stays clean
   as peers disconnect; the caller does not need to track which
   entries are stale.

   The Router is NOT a Terminal. A Terminal is one peer; a Router is a
   hub of peers. The two solve different problems with a shared
   matching primitive.


--------------------------------------------------------------------------------
WIRE FORMAT
--------------------------------------------------------------------------------

The Marshaller's default envelope (used by ProcessQueueChannel,
RemoteChannel) is:

    {
        "id":   "EVENT_INFRA.EventTerminalUp",   # composite "<category>.<class>"
        "data": {"timestamp": 100.0},            # all fields
    }

"id" is the Event subclass's composite identity ("<category>.<__name__>")
as stamped by Event.__init_subclass__. "data" is the result of the
class's TypeAdapter.dump_python(); deserialisation looks up the class
via CLASS_BY_ID[wire_id] (one flat-dict access) and validates via the
same TypeAdapter.

Renaming an event class OR changing its category breaks every
consumer producing or consuming that class on the wire - "do not
rename event types or move their categories lightly" is a hard
rule, not a soft convention.

For specialist serialisation, see marshaller.py's _SPECIALISTS hook
and the Construct future-direction note in its module header.


--------------------------------------------------------------------------------
ADDING A NEW EVENT
--------------------------------------------------------------------------------

Wrap the subclass declaration in a `with category(...)` block:

    from vut.engine.event import Event, category

    with category("WORKFLOW"):

        @dataclass(frozen=True, kw_only=True)
        class EventThingHappened(Event):
            subject: str
            count:   int = 0

            def __str__(self) -> str:
                return "thing happened to %s (%d times)" % (
                    self.subject, self.count
                )

That's it. EventThingHappened.id is automatically
"WORKFLOW.EventThingHappened". The class is registered in
CLASS_BY_ID; the Marshaller, Dispatcher, Terminal, and Router pick it
up automatically.

Multiple files may contribute to the same category; just open a
`with category("WORKFLOW"):` block at the top of each module.
Name uniqueness is required within a category; the same name in
different categories has different wire ids and is fine.


--------------------------------------------------------------------------------
TYPICAL USAGE
--------------------------------------------------------------------------------

In-process two coroutines on one loop. The example declares its own
event type since the package itself ships only EVENT_INFRA events:

    from vut.engine.event import Event, category, EventTerminal, EventChannelParameter

    with category("DEMO"):
        @dataclass(frozen=True, kw_only=True)
        class EventGreeting(Event):
            text: str

    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)
    b.dispatcher.subscribe_on_event(EventGreeting, async_handler)
    # Both starts run concurrently; each blocks on peer Up.
    await asyncio.gather(a.start(), b.start())
    await a.send(EventGreeting(text="hello"))

Cross-process (parent spawns child):

    a_ecp, b_ecp = EventChannelParameter.for_process()
    proc = multiprocessing.Process(target=child_main, args=(b_ecp,))
    proc.start()
    parent_terminal = EventTerminal(a_ecp)
    await parent_terminal.start()       # blocks until child terminal also up

    def child_main(ecp):
        async def go():
            term = EventTerminal(ecp)
            term.dispatcher.subscribe_on_event(...)
            await term.start()          # blocks until parent terminal up
            # ... use term ...
        asyncio.run(go())

WFM as a router (sketch):

    router = EventRouter()
    # Per active user order, one Terminal pair:
    user_a_ecp, user_b_ecp = EventChannelParameter.for_async()
    user_terminal       = EventTerminal(user_b_ecp)
    router_side         = EventTerminal(user_a_ecp)
    # Both sides start concurrently (each blocks on peer Up).
    await asyncio.gather(user_terminal.start(), router_side.start())
    router.add_entry(
        predicate = lambda ev: getattr(ev, "task_id", None) in workload_tasks,
        terminal  = router_side,
    )
    # User code holds user_terminal; subscribes its dispatcher to whatever.
    # When user_terminal stops, the Router auto-removes router_side.
    return user_terminal


--------------------------------------------------------------------------------
TESTING
--------------------------------------------------------------------------------

The TEST/ directory follows the HWUT pattern. Each test file has
multiple "choices"; each choice is a focused sub-test.

To run a single choice:

    cd TEST
    python3 test-terminal.py pair

GOOD/ holds expected output, one file per (test-script, choice).
After running, OUT/ holds produced output for comparison.
