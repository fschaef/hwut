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
        |    .id (== cls.__name__, auto-set)                       |
        |    .category (E_EventCategory)                           |
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

    enums.py              E_EventCategory
    event.py              Event base class, CLASS_BY_ID, EventIdCollision
    events.py             Concrete Event subclasses
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
      test-categories.py    1 choice
      test-events.py        6 choices
      test-marshaller.py    3 choices
      test-dispatcher.py    4 choices
      test-channel.py       4 choices
      test-terminal.py      3 choices
      test-router.py        3 choices
      GOOD/                 24 expected-output files


--------------------------------------------------------------------------------
KEY CONCEPTS
--------------------------------------------------------------------------------

1. EVENT IDENTITY = CLASS NAME

   Each event kind is one Python class. The class auto-registers in
   CLASS_BY_ID under its __name__ at class-definition time, and its
   .id class attribute is set to that name. Defining a new event
   is ONE step: define the class. EventIdCollision is raised if the
   name is already in use.

   Inheritance carries field/behaviour sharing:

       class CompilerDoneEvent(TaskDoneEvent):
           category = E_EventCategory.COMPILATION
           source: str
           output: str

   Each concrete class gets its OWN .id; the parent's id is NOT
   inherited.


2. CATEGORIES ARE SUBSYSTEMS

   E_EventCategory names the VUT subsystem each event belongs to:

       TEST_RESULT      outcomes of test execution
       WORKFLOW         WFM control, artifact lifecycle, task generics
       NETWORK          connection state, transport-level events
       COMPILATION      compiler / codegen events
       DIAGNOSTIC       logging, observability

   Consumers filter naturally by subsystem ("give me all WORKFLOW
   events"). Other filter axes (by id, by source, by workload) are
   expressed as predicates.


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
       await term.start()                     # build channel + recv loop
       await term.send(event)                 # ship to peer
       await term.stop()                      # tear down

   The receive-side dispatcher uses enforce_async_callbacks_f=True;
   sync callbacks would block the receive loop. For sync work, use
   an object-with-.send sink that pushes to a thread Queue for
   separate processing.


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

   The Router is NOT a Terminal. A Terminal is one peer; a Router is a
   hub of peers. The two solve different problems with a shared
   matching primitive.


--------------------------------------------------------------------------------
WIRE FORMAT
--------------------------------------------------------------------------------

The Marshaller's default envelope (used by ProcessQueueChannel,
RemoteChannel) is:

    {
        "id":   "TaskDoneEvent",                      # class __name__
        "data": {"task_id": 42, "duration_s": 1.5,    # all fields
                 "timestamp": 100.0},
    }

"id" is the Event subclass's __name__ verbatim. "data" is the result
of the class's TypeAdapter.dump_python(); deserialisation looks up the
class via CLASS_BY_ID[id] and validates via the same TypeAdapter.

Renaming an event class breaks every consumer producing or consuming
that class on the wire - "do not rename event types lightly" is a hard
rule, not a soft convention.


--------------------------------------------------------------------------------
ADDING A NEW EVENT
--------------------------------------------------------------------------------

One step: declare a subclass.

    @dataclass(frozen=True, kw_only=True)
    class MyNewEvent(Event):
        category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW

        subject: str
        count:   int = 0

        def __str__(self) -> str:
            return "my new thing happened to %s (%d times)" % (
                self.subject, self.count
            )

That's it. MyNewEvent.id is automatically "MyNewEvent". The class is
registered in CLASS_BY_ID; the Marshaller, Dispatcher, Terminal, and
Router pick it up automatically.

The only requirement is name uniqueness across the system. Subsystem-
specific prefixes (NetworkConnectEvent, CompilerDoneEvent) keep the
namespace honest.


--------------------------------------------------------------------------------
TYPICAL USAGE
--------------------------------------------------------------------------------

In-process two coroutines on one loop:

    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)
    b.dispatcher.subscribe_on_event(TaskDoneEvent, async_handler)
    await a.start()
    await b.start()
    await a.send(TaskDoneEvent(task_id=42, duration_s=1.5))

Cross-process (parent spawns child):

    a_ecp, b_ecp = EventChannelParameter.for_process()
    proc = multiprocessing.Process(target=child_main, args=(b_ecp,))
    proc.start()
    parent_terminal = EventTerminal(a_ecp)
    await parent_terminal.start()

    def child_main(ecp):
        async def go():
            term = EventTerminal(ecp)
            term.dispatcher.subscribe_on_event(...)
            await term.start()
            # ... use term ...
        asyncio.run(go())

WFM as a router (sketch):

    router = EventRouter()
    # Per active user order, one Terminal pair:
    user_a_ecp, user_b_ecp = EventChannelParameter.for_async()
    user_terminal = EventTerminal(user_b_ecp)
    await user_terminal.start()
    router.add_entry(
        predicate = lambda ev: getattr(ev, "task_id", None) in workload_tasks,
        terminal  = EventTerminal(user_a_ecp),
    )
    # User code holds user_terminal; subscribes its dispatcher to whatever.
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
