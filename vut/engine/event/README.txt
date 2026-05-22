================================================================================
HWUT 2.0 Event Component

Event definition and communication system.
================================================================================

--------------------------------------------------------------------------------
ABSTRACT
--------------------------------------------------------------------------------

This component provides a way for defining, sending, and receiving events
between async tasks, threads, processes, and remote processes homogenously.

(*) Terminal:

  Users interact, i.e. send and receive, events via a 'Terminal'. The modality
  of the event transport are completely hidden from the user in a 'Channel'.
   
                                  .-------.
      User A o----o Terminal o---[ Channel ]----o Terminal o---o User B
                                  '-------' 

  The core API of the Terminal consists of two functions:

     .send(event)
     .dispatcher.subscribe_on_*(*, handler_func)

  The dispatcher (class Dispatcher) allows for subscription on events, event
  categories, or arbitrarily defined predicates. It is the heart of the 
  Event infrastructure:

                         Dispatcher
                       .-------------.
                       | condition 1 ----> executer
         Event ------->| condition 2 ----> executer
                       |     :       ----> executer
                       | condition N ----> executer
                       '-------------'

(*) Router, Channel, Marshaller:

  Connections between terminals are solely implemented using general
  'EventChannels', that establish connections between different kinds of
  process execution contexts, such as threads, processes, remote processes, and
  async tasks.
                               .-------.
                Terminal o----[ Channel ]----o Terminal
                               '-------'

  A Marshaller handles the streaming and reception of events in 'byte streams'
  required for the communication channels. 

                            Terminal
               .---------------------------------.
      Event ---+-> Marshaller ---> byte stream --+->--.      .---------
               |                                 |     >----[  Channel 
      Event <--+-- Marshaller <--- byte stream --+-<--'      '---------
               '---------------------------------'


  An EventRouter can fan events from multiple Terminals to multiple Terminals
  based on predicates (events, categories, general predicates) relying on the
  same dispatcher as the Terminal.

                  .-------------------------.                      .-----
    Terminal o----o Terminal 1   Terminal K o-----o Terminal o----[ Channel
                  |    :             :      |                      '-----
    Terminal o----o Terminal I   Terminal N o-----o Terminal
                  '-------------------------'

(*) Topology

   While the main 'occurence' of Events evolves around event dispatching,
   the given set of classes allows for an easy implementation of communication
   network topologies like the following, locally and remotely with
   and without encryption.

           T = Terminal  [C] = Channel  dashed box = Router

                .---------.                     .---------.
      T o--[C]--o T     T o---[C]---o T o--[C]--o T     T o--[C]--o T
                |       T o---[C]---o T         |         |
      T o--[C]--o T     T o                     |       T o--[C]--o T
                |    T    |                     |    T    |
                '----o----'                     '----o----'
                     |                               |
                    [C]                             [C]
                     |                               |
                .----o----.                          o
      T o--[C]--o T  T  T o--[C]--o T                T
                |         |                        
      T o--[C]--o T     T o--[C]--o T              
                |    T    |                        
                '----o----'                       
                     |                             
                    [C]                            
                     |
                     o
                     T

--------------------------------------------------------------------------------
CLASS HIERARCHIE
--------------------------------------------------------------------------------

        .-------------.
        | Event       |
        |  .category  |
        |  .id        |
        '------+------'
               |
               +----- EventCompilerFailed(.path, .error_msg)
               +----- EventTestExecuted(.verdict)

        .---------------.
        | EventChannel  |
        |  .send        |
        |  .receive     |
        |  .close       |
        '-------+-------'
                |
                +----- AsyncChannel       in-process, async tasks
                +----- ThreadChannel      in-process, threads
                +----- ProcessChannel     cross-process
                +----- RemoteChannel      cross-machine

        .---------------------------.
        | EventChannelParameter     |
        |  .for_async               |
        |  .for_thread              |
        |  .for_process             |
        |  .for_remote              |
        '---------------------------'

        .-----------------.
        | EventTerminal   |
        |  .send          |
        |  .dispatcher    |
        |  .start         |
        |  .stop          |
        '-----------------'

        .---------------------.
        | EventRouter         |
        |  .add_entry         |
        |  .remove_entry      |
        |  .publish           |
        |  .publish_from      |
        '---------------------'

    The EventDispatcher (predicate-to-sink matcher) is the shared
    matching primitive, used both INSIDE a Terminal (for its
    receive-side fan-out) and INSIDE a Router (for its outgoing
    selection). One filter API; two contexts.

--------------------------------------------------------------------------------
FILE LAYOUT
--------------------------------------------------------------------------------

    __init__.py      Public surface
    README.txt       This file
    DISCUSSIONS.txt  Decision history and rationale
    event.py         Event base class, category() context manager,
                     CLASS_BY_ID, lookup_event_class, all_event_classes,
                     all_categories, EventIdCollision,
                     EventDefinitionOutsideCategoryContext,
                     EventRegistrationLocked
    events.py        Concrete Event subclasses, organised by category
    dispatcher.py    EventDispatcher, Subscription
    terminal.py      EventTerminal

    ./channel/

       router.py     EventRouter
       channel.py    EventChannel ABC, AsyncChannel,
                     ThreadChannel, ProcessChannel,
                     RemoteChannel
       parameter.py  EventChannelParameter
                     => generate appropriate connection and Terminal
                        on 'the other side'. 
       cipher.py     Cipher base class for:
                     IdentityCipher, FernetCipher, NaClBoxCipher, TLSCipher. 
       marshaller.py Marshaller serialization, deserialization

--------------------------------------------------------------------------------
KEY CONCEPTS
--------------------------------------------------------------------------------

Events:

An event is something that informs. A base class implements the minimum
elements of an event, namely its identifier (.id) and its category (.category).
These are elements based on which we can route the information to its
appropriate executor or other 'customers'.

Every concrete event in the system must be derived from the base class while
possibly carrying more detailed information about an event by in further class
members.

Events are defined in category context, thus setting the category member
automatically.

       with category("TASK"):

           class EventAborted(Event):
               message: str

           class EventProgress(Event):
               progress_percent:   float
               execution_time:     float
               estimated_end_time: float

           class EventTerminated(Event):
               ...

Instances of events are then ready to be passed to dispatchers, terminals,
received by terminals and routed through routers.

NOTE: Category "EVENT_INFRA" is only used by the event infrastructure
      and not by users.


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

The Marshaller's default envelope (used by ProcessChannel,
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
ENCRYPTION
--------------------------------------------------------------------------------

The serialising channels (ProcessChannel, RemoteChannel) can
encrypt their wire payload. Encryption is a pluggable Cipher inside
the Channel; it transforms the serialised bytes on send (encrypt)
and receive (decrypt). The default is no encryption.

Cipher is a CHANNEL-INTERNAL concept. It is NOT exported from this
package - most users never name it. Encryption is configured
indirectly: pass a CipherSpec to a channel-parameter factory.

    from vut.engine.event.channel_parameter import (
        EventChannelParameter, CipherSpec,
    )

    # No encryption (the default) - plaintext on the wire:
    a_ecp, b_ecp = EventChannelParameter.for_process()

    # Symmetric encryption, key read locally from an env var:
    spec = CipherSpec.fernet_env("VUT_FERNET_KEY")
    a_ecp, b_ecp = EventChannelParameter.for_process(cipher_spec=spec)

The CipherSpec is a picklable, SECRET-FREE recipe: it names the
cipher kind and a key REFERENCE (env-var name or file path), never
the key bytes. The key is resolved locally - on whichever side
builds the channel - inside make_channel(). A secret carried in a
pickled or transmitted ECP would leak; for a remote channel it would
mean sending the key over the channel it is meant to secure.

CipherSpec factories:

    CipherSpec.identity()                  no encryption (default)
    CipherSpec.fernet_ephemeral()          symmetric, ephemeral key
                                           exchange - encrypted but
                                           NOT authenticated
    CipherSpec.fernet_env(env_var)         symmetric, key from an
                                           environment variable
    CipherSpec.fernet_file(key_path)       symmetric, key from a file
    CipherSpec.nacl_box_env(priv, peer)    public-key (PyNaCl Box);
                                           pin the peer key for
                                           authentication
    CipherSpec.tls(certfile, keyfile,      TLS via ssl
                   cafile, server_side,
                   verify)

The crypto handshake runs inside the channel before make_channel()
returns - the channel is fully secured before the Terminal sees it.
The Terminal is entirely unaware of the Cipher.

In-process channels (for_async, for_thread) never serialise and
ignore any CipherSpec; they are always plaintext-in-memory, which
is correct - there is no wire to protect.

SECRECY IS NOT IDENTITY. An ephemeral key exchange with no
pre-shared anchor encrypts the channel but does NOT verify who the
peer is - a man-in-the-middle can handshake with each side
separately. Authentication needs a pre-shared anchor: a shared
Fernet key, a pinned NaCl peer key, or a verified TLS certificate.
For local transports identity does not matter; for RemoteChannel it
does. See cipher.py's module header for the full discussion.


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
