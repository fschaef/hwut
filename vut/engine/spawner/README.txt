================================================================================
HWUT 2.0 Spawner Component

Launching tasks into parallel execution over the event infrastructure.
================================================================================

OVERVIEW
--------

This component launches a task/process/function to be executed in parallel.
After the launch the communication between the user's 'parent' process and the
'child' process is agnostic of the communication channel or the nature of the
execution context. It relies on the 'event' subsystem.

The user, that launched the task, communicates via 'parent event terminal' and
the child process via a 'child event terminal'.

    User
    parent process o-<-->-o SpawnerParentEventTerminal
                                         :
                                   .-----------.
                                  [  Transport  ]
                                   '-----------'
                                         :
                              SpawnerChildEventTerminal o-<-->-o child process

The 'Spawner' functions as a router between the user's parent terminal and the
child's terminal. To some extent it monitors their traffic and communicates
with both sides.

Concerns:

  -- building the terminal pair (setting up event channel parameters etc.)
  -- launching the child, instantiating an EventTerminal based 
     the event channel parameters
  -- startup handshake between parent and child terminal
  -- holding the OS handle(s)
  -- running the child-state machine
  -- process a 'terminate' call from the user

Communication between user and the child's process happens solely through the 
EventTerminal objects.

--------
SPAWNING
--------

Every spawning results in a 'SpawnerParentEventTerminal' by means of which the
user may communicate with the child's process. Following functions are provided
for spawning:

      spawn_async (callable, args, config) 
      spawn_thread(callable, args, config) 
      spawn_process(callable, args, config)
      spawn_remote_process(function_name_str, args, config)

callable/function_name_str:

    The first three functions receive an ordinary Python callable, the remote 
    process invocation takes the name of the function and its arguments in order
    to resolve it through module import (remote side must be equipped with
    according modules).

args:

    Arguments are specified in terms of tuples or dict-s. The remote function
    must receive an 'SpawnerChildEventTerminal' as first argument (when named
    in a dict, it is called 'event_terminal').

config:

    Configuration parameters to specify the Event transport and Execution
    Context.

The child on the other side is instantiated and receives an instantiated
'SpawnerChildEventTerminal' as first argument.


-------------------
CHILD STATE MACHINE
-------------------

The spawner attempts to track the state of the child process in terms
of the following state machine:

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
               │         ├────────────────┐
               │                          │ 
               ▼                          ▼
            ┌───────────────┐   ┌──────────────────────┐
            │    TERM_OK    │   │     TERM_FAILURE     │
            └───────────────┘   └──────────────────────┘

            any state ──lost──►┌───────────────────────┐
                               │  TERM_LOST_CONNECTION │
                               └───────────────────────┘

The above state machine specifies the states and transitions that make up the
lifecycle of a parallel-operating child launched by the 'spawner'. It is
elegantly implemented relying on event's dispatcher 'expect' functionality and
asyncio coroutines.

STATES

    LAUNCHED              Internal startup state. The child has been launched
                          but its terminal has not yet completed the Up
                          handshake. 

    RUNNING               Up handshake confirmed; the child is live and connected.

    SUSPENDED             The child has been stopped via its OS handle.
                          Process/remote only 

    TERMINATING           .terminate(wait_to_kill_ms) has been issued; wait
                          for the child's confirmation of proper termination.
                          
                          wait_to_kill_ms = numeric => kill process after 
                              wait time, if no confirmation is received.
                          wait_to_kill_ms = None => wait for ever.

    TERM_OK               Terminal. Child reported its termination and,
                          therefore ended with mutual agreement.

    TERM_FAILURE          Terminal. Child did not confirm proper termination
                          and its process has been forcefully terminated. 

    TERM_LOST_CONNECTION  Terminal. Whenever the channel connection breaks, 
                           this state is entered (except from TERM_OK). 
                          Here, no information about the child is available
                          whatsoever.

Every transition additionally emits EventChildStateChanged(old, new), to the
user's terminal, so a caller may either poll .child_state() or await the change
via the dispatcher's expect_* helpers.


-----------------------------------------
SpawnerParentEventTerminal(EventTerminal)
-----------------------------------------

A call to a 'spawn_*()' function delivers either 'None' upon failure, or a
SpawnerParentEventTerminal. Any technicalities, such as OS handles, are hidden
from the end user.

   SpawnerParentEventTerminal(EventTerminal)  
       .send
       .dispatcher
       .start/ .stop 
    
       + .terminate(wait_to_kill_ms) -> bool
       + .suspend() / .resume()      -> bool (ONLY for 'process'/'remote') 
       + .child_state()              -> ChildState

.terminate()
   => sends 'EventChildTerminationReq' to the spawner. Spawner initiates
      child shutdown (see state machine). 

----------------------------------------
SpawnerChildEventTerminal(EventTerminal)
----------------------------------------

Built by the trampoline on the 'other' side of the user's context. 

.start() => subscribe to 'EventChildTerminationReq'
.stop()  => send nice 'EventChildTermination'

When a SpawnerChildEventTerminal receives an EventChildTerminationReq it
drives the cooperate wind-down. The trampoline calls the thing to be
called from inside a context manager, as show below:

   async with SpawnerChildEventTerminal(ecp) as term:
       await callable_thing.run(term, task_args)

__aenter__ => start() 
__aexit__  => stop()

-----------
TERMINATION
-----------

Forced termination is incited via a call to 

   terminal.terminate(wait_to_kill_ms)

where the 'wait_to_kill_ms' is an argument to be specified mandatorily.
In conclusion with the 'thread' context model, it may only be 'None', 
because a thread can never be killed. An async-Task may be forcefully
cancelled, but the time that it remains in TERMINATING mode cannot be 
determined, because it needs to hit an 'await' point before it becomes
effective.

Remote and Process: 
  - send EventChildTerminationReq
  - TERMINATING 
  - while wait time < wait_to_kill_ms
  -   if EventChildTermination
  -      => TERM_OK; 
  -      kill child process
  -      <exit>
  - kill child process
  - => TERM_FAILURE

Thread: 
  - send EventChildTerminationReq
  - => TERMINATING 
  - forever (wait_to_kill_ms must be 'None')
  -    if EventChildTermination
  -       TERM_OK
  -       <exit>

async.Task: 
  - send EventChildTerminationReq
  - => TERMINATING 
  - while wait time < wait_to_kill_ms
  -    if EventChildTermination
  -       TERM_OK
  -       <exit>
  - cancel Task
  - forever  
  -    if EventChildTermination
  -       TERM_OK
  -    if task cancelled done
  -       TERM_FAILURE

-----------------------------------
SPAWNER EVENTS (category "SPAWNER")
-----------------------------------

EventChildTerminationReq        parent  -> spawner
    wait_to_kill_ms: int | None
    (internal from user's terminal to spawner)

EventChildTermination      child   -> parent
    reason: {COMPLETED, TERMINATED, FAILED}

    COMPLETED  - work finished; no terminate was ever requested.
    TERMINATED - left because EventChildTerminationReq arrived.
    FAILED     - the child's work raised; reported out cleanly.

EventChildKilled           spawner -> parent
    last_state: ChildState,  killed_at: float,  grace_ms: int
    -- 'wait_to_kill_ms' deadline reached
    -- OS - context terminated 
    -- no guarantee about child's resource deallocation or anything

EventChildStateChanged     spawner -> parent
    old_state: ChildState,  new_state: ChildState
    Emitted on every FSM edge.

--------
EXAMPLES
--------

See the examples in TEST directory.


