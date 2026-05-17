================================================================================
VUT Event Component
================================================================================

PURPOSE

    This package provides the Event system for VUT: identity, structured
    data, dispatch, and wire transport. Every interaction between
    subsystems that needs to cross a queue or a process boundary travels
    as an Event.


--------------------------------------------------------------------------------
DESIGN AT A GLANCE
--------------------------------------------------------------------------------

    Every concrete event in the system is a SUBCLASS of Event. The class
    itself plays the role of "kind metadata"; instances of the class
    carry the event data.

        +--------------------------------------------------------+
        |  E_EventCategory (functional grouping by subsystem)    |
        +--------------------------------------------------------+
                                  |
                                  v
        +--------------------------------------------------------+
        |  Event   (base class, frozen dataclass)                |
        |    +-- id        : str   (== cls.__name__, auto-set)   |
        |    +-- category  : ClassVar[E_EventCategory]           |
        |    +-- timestamp : float                               |
        |    +-- as_dict() / from_dict()    (wire I/O)           |
        |    +-- serialize() / deserialize()  (Marshaller hook)  |
        |    +-- __init_subclass__   (auto-id, auto-register,    |
        |                             collision detection)       |
        +--------------------------------------------------------+
                                  ^
                                  | (inheritance)
                                  |
        +-------------------------+--------------------------+
        |                                                    |
        |   TaskStartedEvent     ArtifactAvailableEvent      |
        |   TaskDoneEvent ------> CompilerDoneEvent          |
        |   TaskFailedEvent      ArtifactImpossibleEvent     |
        |   TaskProgressEvent    WorkflowTaskCancelledEvent  |
        |   TaskCancelledEvent   CompilerNoSourceEvent       |
        |                                                    |
        +----------------------------------------------------+
                                  |
                                  v
        +--------------------------------------------------------+
        |  CLASS_BY_ID  (module-level dict: str -> Event class)  |
        |  populated by Event.__init_subclass__ on each new class|
        +--------------------------------------------------------+
                                  ^
                                  | (lookup at deserialise time)
                                  |
        +--------------------------------------------------------+
        |  Marshaller (class-as-singleton, classmethods only)    |
        |    +-- _SPECIALISTS : frozen MappingProxyType          |
        |    +-- serialize(event) -> dict                        |
        |    +-- deserialize(wire) -> Event | None               |
        +--------------------------------------------------------+

        +--------------------------------------------------------+
        |  Router (in-process publish-subscribe)                 |
        |    +-- subscribe_on_event(id, sink)                    |
        |    +-- subscribe_on_category(category, sink)           |
        |    +-- subscribe_on_predicate(pred, sink)              |
        |    +-- unsubscribe(handle) -> bool                     |
        |    +-- publish(event)         (non-blocking)           |
        +--------------------------------------------------------+


--------------------------------------------------------------------------------
FILE LAYOUT
--------------------------------------------------------------------------------

    enums.py        E_EventCategory
    event.py        Event base class, CLASS_BY_ID, EventIdCollision
    events.py       Concrete Event subclasses
    marshaller.py   Transport (serialise / deserialise)
    router.py       In-process publish-subscribe
    __init__.py     Public surface

    README.txt      This file
    DISCUSSIONS.txt Decision history and rationale

    TEST/
      config.py     Test bootstrap
      hwut-info.dat HWUT metadata
      test-categories.py   category enum inventory
      test-events.py       construction, str, inheritance, frozen, metadata, collision
      test-marshaller.py   roundtrip, frozen-specialists, errors
      test-router.py       by_event, by_category, by_predicate, unsubscribe, sinks
      GOOD/         expected output, one file per (test, choice)


--------------------------------------------------------------------------------
KEY CONCEPTS
--------------------------------------------------------------------------------

1. ONE CLASS PER EVENT, ID DERIVED FROM CLASS NAME

   Each event kind is one Python class. The class IS the kind: its
   __name__ (e.g. "TaskDoneEvent") IS its identity. Instances carry
   the data as ordinary fields. There are no separate "payload"
   classes, no separate dispatch enum.

       class TaskDoneEvent(Event):
           category: ClassVar[E_EventCategory] = E_EventCategory.WORKFLOW
           task_id:    int
           duration_s: float

   The Event base class auto-sets cls.id = cls.__name__ in
   __init_subclass__ and registers the class in CLASS_BY_ID. Adding a
   new event is ONE step: define the class.

   Inheritance carries specialisation:

       class CompilerDoneEvent(TaskDoneEvent):
           category = E_EventCategory.COMPILATION
           source: str
           output: str

   Each concrete class gets its OWN id (its own __name__), NOT the
   parent's. Inheritance is only for sharing fields and behaviour.

   UNIQUENESS IS ENFORCED. Two subclasses with the same __name__
   raise EventIdCollision at class-definition time. This catches a
   real source of silent misrouting (subsystems independently
   defining a "DoneEvent" class).


2. CATEGORIES ARE SUBSYSTEMS

   E_EventCategory names the VUT SUBSYSTEM each event belongs to,
   not the shape of state-change:

       TEST_RESULT      outcomes of test execution
       WORKFLOW         WFM control, artifact lifecycle, task generics
       NETWORK          connection state, transport-level events
       COMPILATION      compiler / codegen events
       DIAGNOSTIC       logging, observability

   Consumers naturally filter by subsystem ("give me all WORKFLOW
   events"). Other filter axes (by id, by source, by workload) are
   expressed as predicates when the routing layer is built later.


3. PYDANTIC VIA TypeAdapter

   Event subclasses are plain @dataclass(frozen=True, kw_only=True)
   classes, NOT Pydantic BaseModel subclasses. But each subclass
   gets a Pydantic TypeAdapter (lazily, on first use) that drives
   .as_dict() and .from_dict():

       wire = event.as_dict()              # adapter.dump_python
       event = SomeClass.from_dict(wire)   # adapter.validate_python

   This buys real Pydantic validation (wrong types, missing fields,
   extra fields) at wire boundaries without forcing the entire
   inheritance tree into BaseModel.


4. MARSHALLER AS CLASS-AS-SINGLETON

   The Marshaller is a class with classmethods and a frozen
   _SPECIALISTS class attribute. There is no Marshaller()
   constructor; you cannot instantiate it. Call sites:

       wire  = Marshaller.serialize(event)   or   event.serialize()
       event = Marshaller.deserialize(wire)  or   Event.deserialize(wire)

   Synchronisation across producers and consumers is free, because
   they share the same build (same VUT version) and therefore the
   same Marshaller class configuration.

   Specialists (custom transport per event id) are declared at
   module load time in _SPECIALISTS. Currently empty; the default
   scheme handles every event correctly.


5. WIRE FORMAT (PATTERN A: external tag)

   The default wire form is a two-key envelope:

       {
           "id":   "TaskDoneEvent",                      # class __name__
           "data": {"task_id": 42, "duration_s": 1.5,    # all fields
                    "timestamp": 100.0},                 # from the class
       }

   The "id" is the Event subclass's __name__ verbatim. The "data" is
   the result of the Event class's TypeAdapter.dump_python();
   deserialisation looks up the class via CLASS_BY_ID[id] and calls
   its TypeAdapter.validate_python().

   Adding a new event kind ANYWHERE in the codebase is wire-
   transparent as long as the class name is unique. Renaming an
   existing class breaks every consumer producing or consuming that
   class on the wire - "do not rename event types lightly" is a hard
   rule, not a soft convention.


--------------------------------------------------------------------------------
ADDING A NEW EVENT
--------------------------------------------------------------------------------

One step:

    Declare an Event subclass (in events.py or in the owning
    subsystem's module). Auto-registration in CLASS_BY_ID happens
    in Event.__init_subclass__.

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
registered in CLASS_BY_ID; the Marshaller picks it up automatically;
the TypeAdapter is created on first use.

The only requirement is uniqueness of the class name across the whole
event namespace - if "MyNewEvent" already exists, class creation
raises EventIdCollision. Subsystem-specific suffixes
(NetworkConnectEvent, CompilerDoneEvent) keep the namespace honest.


--------------------------------------------------------------------------------
ROUTING AND FILTERING (Router)
--------------------------------------------------------------------------------

The Router is an in-process publish-subscribe component. Consumers
subscribe on one of three filter dimensions; the Router delivers each
event to every matching subscriber.

API:

    router = Router()

    sub = router.subscribe_on_event(TaskDoneEvent, sink)
    sub = router.subscribe_on_event("TaskDoneEvent", sink)   # also OK
    sub = router.subscribe_on_category(E_EventCategory.WORKFLOW, sink)
    sub = router.subscribe_on_predicate(lambda ev: ..., sink)

    router.unsubscribe(sub)        # returns bool; False if stale handle

    router.publish(event)          # non-blocking dispatch

SINK TYPES:

    - ASYNC CALLABLE  ('async def f(event): ...')
        Scheduled via asyncio.create_task; publish() does NOT await it.
        Callbacks may complete after publish() returns; exceptions are
        not visible to the publisher (they surface via asyncio's task
        exception handling).

    - QUEUE-LIKE      (any object with .put_nowait)
        Delivered immediately via put_nowait. QueueFull and similar
        errors are caught and logged to stderr; the event is dropped
        for that subscriber but other subscribers still receive it.

    Type-detected at subscribe time. Passing anything that is neither
    async callable nor queue-like raises TypeError at the subscribe
    call (not later at publish time).

SEMANTICS:

    - Exact-match-all: if N subscriptions match an event, all N fire.
      No "first match wins"; predictability over cleverness.

    - Snapshot iteration: subscribing or unsubscribing during a
      publish() does NOT affect the current dispatch. The snapshot
      is taken once, at the top of publish(); newly-added
      subscriptions fire on the NEXT publish.

    - Predicates that raise are skipped for that event (diagnostic
      to stderr) and the subscription remains. Other subscriptions
      are not affected.

ROUTING IS IN-PROCESS ONLY. Cross-process event bridging is a
separate concern (handled by the Marshaller for transport plus a
future bridging component). The Router does not serialise.


--------------------------------------------------------------------------------
TESTING
--------------------------------------------------------------------------------

The TEST/ directory follows the HWUT pattern. Each test file has
multiple "choices"; each choice is a focused sub-test.

To run a single choice:

    cd TEST
    python3 test-events.py construction

To run via the HWUT driver, follow whatever convention the project
uses to discover tests via hwut-info.dat.

GOOD/ holds the expected output, one file per (test-script, choice).
After running, OUT/ holds the produced output for comparison.
