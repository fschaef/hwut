================================================================================
HWUT 2.0 Spawner Component

Launching a callable into parallel execution and supervising it over the
'event' subsystem.
================================================================================

OVERVIEW
--------

The Spawner launches a callable into a parallel execution context and supervises
its lifecycle. After launch, the user's 'parent' side and the launched 'child'
side communicate solely through paired EventTerminal objects; the execution
context (asyncio Task, thread, process, remote process) and the transport are
hidden behind those terminals.

Four execution contexts ('kinds') are supported: async, thread, process, and
remote process. The same supervision surface and the same event traffic apply
to all four; the kinds differ only in their power to stop a child (see
TERMINATION).

The user holds a SpawnerParentEventTerminal. The child holds a
SpawnerChildEventTerminal. Between them sits the Spawner, which owns an
EventRouter and observes traffic in both directions:

    User
    parent side  o-<-->-o  SpawnerParentEventTerminal
                                       :
                                  .---------.
                                  | Spawner |   owns EventRouter,
                                  |         |   ChildHandle, FSM, Watchdog
                                  '---------'
                                       :
              SpawnerChildEventTerminal  o-<-->-o  child side (the callable)

The Spawner is a router, not a peer: it sits BETWEEN the two terminals rather
than being one of them. Its EventRouter's dispatcher is the single point where
all traffic is observed, and that observation drives the child-state machine.

The Spawner holds, for one launched child:

    EventRouter        the hub; carries parent <-> child traffic and is the
                       observation point for state tracking.
    ChildHandle        the OS-level handle (Task / thread / process), kept
                       inside the Spawner and never surfaced to the user.
    ChildStateMachine  turns observed events into E_ChildState transitions.
    Watchdog           background liveness supervision of the child.

The component invents no transport. Channel, terminal, handshake, and dispatcher
all belong to the 'event' subsystem; the Spawner is a launch-and-supervise
device only.


--------
SPAWNING
--------

A spawn call names WHAT to run (a callable plus its arguments) and HOW to run it
(a per-kind config). Four entry functions, one per kind:

    spawn_async         (callable, args, config)
    spawn_thread        (callable, args, config)
    spawn_process       (callable, args, config)
    spawn_remote_process(function_name_str, args, config)

callable / function_name_str:

    spawn_async / spawn_thread / spawn_process take a live Python callable.
    spawn_remote_process takes the callable's dotted import path as a STRING;
    the remote side resolves it by ordinary import, so the remote side must be
    equipped with the matching modules.

args:

    One object - a tuple/list or a dict - carrying the user arguments, never
    loose parameters mixed into the spawn call. The callable receives the
    child terminal as its FIRST argument, then the user args:

        args is a tuple / list  ->  callable(term, *args)
        args is a dict          ->  callable(event_terminal=term, **args)
        args is None            ->  callable(term)

config:

    One per-kind config object: AsyncConfig, ThreadConfig, ProcessConfig, or
    RemoteProcessConfig. It carries the event-channel setup and the
    execution-context setup. Its make_ecp_pair() produces the
    (parent_ecp, child_ecp) EventChannelParameter pair that backs the two
    terminals.

Every successful spawn call returns a SpawnerParentEventTerminal; a startup
failure returns None.


----------
TRAMPOLINE
----------

The child does not begin at the user callable directly. It begins at a framework
trampoline (run_trampoline), which:

    1. builds the SpawnerChildEventTerminal from the child ECP,
    2. start()s it - running the Up handshake,
    3. and only then invokes the user callable inside that frame.

The terminal is held as an async context manager, so its termination
confirmation is emitted on every exit path:

    async with SpawnerChildEventTerminal(child_ecp) as term:
        await invoke(callable, term, args)

    __aenter__  ->  start()  (Up handshake; subscribe to EventChildTerminationReq)
    __aexit__   ->  stop()   (emit EventChildTermination; close)

The trampoline maps the callable's outcome onto the reason carried by
EventChildTermination:

    callable returns normally           ->  COMPLETED
    callable observed a
      termination request                ->  TERMINATED
    callable raised                      ->  FAILED  (reported out, then re-raised)

For spawn_remote_process the callable arrives as a STRING and is resolved by
import before invocation. The trampoline runs in this interpreter for
async/thread; for process/remote a module-level, picklable entry
(run_trampoline_entry) boots an event loop and then runs run_trampoline.


-------
STARTUP
-------

A spawn call runs through the kind-independent core _spawn:

    1. build the parent terminal from parent_ecp,
    2. launch the child (it boots into the trampoline),
    3. wire supervision - the FSM and its event subscriptions - BEFORE the
       handshake is awaited,
    4. RACE the parent-side Up handshake against the child dying,
    5. handshake won  ->  start the Watchdog, drive LAUNCHED -> RUNNING, return
                          the parent terminal.
       child died first ->  close the half-open terminal, return None.

Because the trampoline completes the child-side handshake before the user
callable runs, a won handshake means the channel is live - not merely that a
process exists. The two outcomes share no path: a live
SpawnerParentEventTerminal, or None.


-------------------
CHILD STATE MACHINE
-------------------

The ChildStateMachine models one child's lifecycle:

            ┌───────────┐
            │ LAUNCHED  │
            └─────┬─────┘
                  │ up
                  ▼
            ┌───────────┐        resume ┌─────────────┐
            │  RUNNING  │◄──────────────│  SUSPENDED  │
            └──┬─────┬──┘               └──┬──────┬───┘
         term  │     └─────────────────────┘      │ term
               ▼                   suspend        │
            ┌───────────────┐                     │
            │  TERMINATING  │◄────────────────────┘
            └──┬─────────┬──┘
               │ confirm │ unconfirmed (=> kill)
               │         └────────────────┐
               │                          │
               ▼                          ▼
            ┌───────────────┐   ┌──────────────────────┐
            │    TERM_OK    │   │     TERM_FAILURE     │
            └───────────────┘   └──────────────────────┘

                lost   ┌───────────────────────┐
    any state ────────►│  TERM_LOST_CONNECTION │
                       └───────────────────────┘

STATES

    LAUNCHED              Internal startup state. The child has been launched
                          but its terminal has not yet completed the Up
                          handshake.

    RUNNING               Up handshake confirmed; the child is live and
                          connected.

    SUSPENDED             The child has been stopped via its OS handle.
                          Process and remote only.

    TERMINATING           .terminate(wait_to_kill_ms) has been issued; awaiting
                          the child's EventChildTermination confirmation.
                          wait_to_kill_ms numeric  -> kill the OS context after
                                                      the wait if no confirmation
                                                      arrives.
                          wait_to_kill_ms None     -> wait forever.

    TERM_OK               Terminal. The child confirmed termination
                          (EventChildTermination) BEFORE its resources were
                          freed.

    TERM_FAILURE          Terminal. Resources were freed BEFORE or WITHOUT a
                          confirmation; the functional outcome is unknown.

    TERM_LOST_CONNECTION  Terminal. The channel broke and the Spawner has no
                          information about the child whatsoever. Reachable from
                          any live state.

The terminal split TERM_OK / TERM_FAILURE turns on the ORDERING of the child's
confirmation against the freeing of its resources, not on "exited cleanly" vs
"killed".

E_ChildState.is_terminal() reports whether a state is one of the terminal three;
is_live() is its complement.

Every transition emits EventChildStateChanged(old, new) to the parent terminal,
so a caller may either poll .child_state() or await the transition via the
dispatcher's expect_* helpers.


--------
WATCHDOG
--------

The Watchdog supervises liveness: it is the only place where a child that dies
WITHOUT a clean EventChildTermination becomes a terminal E_ChildState. It is
constructed with three collaborators and holds nothing else:

    handle           the ChildHandle; its liveness() returns an E_Liveness
                     (ALIVE / DEAD / UNKNOWN) and is the liveness source.
    state_machine    the ChildStateMachine; its verdict sink, and its .state
                     tells the Watchdog when to stop.
    parent_terminal  the SpawnerParentEventTerminal; only its peer-down callback
                     is used.

Two triggers feed one resolver:

    periodic poll    every poll_ms the loop consults handle.liveness();
                     catches a child gone silent without the channel signalling.
    peer-down        the parent terminal's peer-down callback fires the resolver
                     at once when the channel itself signalled.

Both funnel into resolve_silence(), which hands an E_Liveness to the FSM. The
Watchdog reads liveness and forwards it; the ChildStateMachine owns the verdict.
The Watchdog starts once the handshake has proven the channel live and runs
until the FSM reaches a terminal state.


-----------
CHILDHANDLE
-----------

ChildHandle abstracts the OS-level execution context behind one homogeneous,
kind-agnostic API. The ChildStateMachine drives it through this API alone -
"await a kill", "await a suspend / resume" - and never touches kind specifics:

    await handle.kill()        force-terminate the OS context  -> bool
    await handle.suspend()                                     -> bool
    await handle.resume()                                      -> bool
    await handle.liveness()    -> E_Liveness (ALIVE / DEAD / UNKNOWN)
    handle.can_force_kill                                      -> bool (property)
    handle.can_suspend                                         -> bool (property)

kill / suspend / resume report success or refusal by RETURN VALUE (bool), never
by exception. The four concrete handles differ only in capability:

    AsyncChildHandle    force-kill yes (Task.cancel), suspend no
    ThreadChildHandle   force-kill no,                suspend no
    ProcessChildHandle  force-kill yes,               suspend yes
    RemoteChildHandle   force-kill yes,               suspend yes


-----------------------------------------
SpawnerParentEventTerminal(EventTerminal)
-----------------------------------------

What a spawn_* call returns: a real EventTerminal (send / dispatcher /
start / stop and the async context-manager form inherited unchanged) plus a thin
supervision surface.

   SpawnerParentEventTerminal(EventTerminal)
       .send
       .dispatcher
       .start / .stop

       + .terminate(wait_to_kill_ms)  -> bool
       + .suspend() / .resume()       -> bool   (process / remote only)
       + .child_state()               -> E_ChildState

.terminate() is a REQUEST, not an action: it emits EventChildTerminationReq
through the Spawner's router; the Spawner then drives the shutdown sequence. The
terminal stays a terminal.

The three supervision methods report success or refusal by RETURN VALUE (bool).
A refusal is a normal outcome: .terminate() returns False for a numeric deadline
on a thread; .suspend() / .resume() return False on async or thread.


----------------------------------------
SpawnerChildEventTerminal(EventTerminal)
----------------------------------------

What the trampoline builds on the child side and hands to the user callable as
its first argument. Inherits the full EventTerminal contract and adds the
child-side termination behaviour:

    .start()  ->  subscribe to EventChildTerminationReq
    .stop()   ->  emit EventChildTermination

On receiving EventChildTerminationReq it drives the cooperative wind-down and
records TERMINATED, so the EventChildTermination emitted by .stop() carries the
correct reason.


-----------
TERMINATION
-----------

.terminate(wait_to_kill_ms) starts a kind-specific shutdown. wait_to_kill_ms is
mandatory:

    numeric  ->  kill the OS context after the wait if no confirmation arrives.
    None     ->  wait forever for the confirmation.

For a thread it must be None; a thread has no force-kill path.

    Process / Remote:
        send EventChildTerminationReq; -> TERMINATING
        while wait < wait_to_kill_ms:
            EventChildTermination   ->  TERM_OK; kill OS context; exit
        kill OS context;            ->  TERM_FAILURE

    Async (Task):
        send EventChildTerminationReq; -> TERMINATING
        while wait < wait_to_kill_ms:
            EventChildTermination   ->  TERM_OK; exit
        Task.cancel();
        loop:
            EventChildTermination   ->  TERM_OK; exit
            Task observed cancelled ->  TERM_FAILURE

    Thread (wait_to_kill_ms is None):
        send EventChildTerminationReq; -> TERMINATING
        loop forever:
            EventChildTermination   ->  TERM_OK; exit

A Task.cancel() lands only at the child's next await, so the time an async child
spends in TERMINATING is not bounded by wait_to_kill_ms alone.


-----------------------------------
SPAWNER EVENTS (category "SPAWNER")
-----------------------------------

EventChildTerminationReq        parent  -> spawner   (the .terminate() request)
    wait_to_kill_ms: int | None

EventChildTermination           child   -> parent    (the child's exit report)
    reason: {COMPLETED, TERMINATED, FAILED}
        COMPLETED   work finished; no terminate was ever requested.
        TERMINATED  left because EventChildTerminationReq arrived.
        FAILED      the child's work raised; reported out cleanly.

EventChildKilled                spawner -> parent    (deadline reached, killed)
    last_state: E_ChildState,  killed_at: float,  grace_ms: int

EventChildStateChanged          spawner -> parent    (every FSM edge)
    old_state: E_ChildState,  new_state: E_ChildState


--------
EXAMPLES
--------

See the TEST directory.
