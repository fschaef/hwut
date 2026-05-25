"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: The Spawner - launch a task into parallel execution and supervise it.

This module is the component's front door. It provides the four spawn
functions and the Spawner hub that backs them:

    spawn_async (callable, args, config)            -> parent terminal | None
    spawn_thread(callable, args, config)            -> parent terminal | None
    spawn_process(callable, args, config)           -> parent terminal | None
    spawn_remote_process(name_str, args, config)    -> parent terminal | None

THE SPAWNER IS A ROUTER, NOT A TERMINAL (DISCUSSION.txt D1)

The Spawner sits BETWEEN the user side and the child side - a hub of
peers, i.e. a Router. It owns an EventRouter; the router's dispatcher is
the single point where traffic in both directions is observed, and that
observation drives child-state tracking and termination. The Spawner
invents NO transport - Channel, Terminal, handshake all belong to the
'event' subsystem; the Spawner is a LAUNCH-and-SUPERVISE device only.

WHAT A spawn_* CALL RETURNS (DISCUSSION.txt D2)

ONE object: a SpawnerParentEventTerminal (a real EventTerminal plus the
supervision surface), or None on startup failure. The two outcomes share
no path - the caller gets a live, fully-attached terminal, or nothing.

THE STARTUP RACE (DISCUSSION.txt D5)

_spawn launches the child at the trampoline (NOT at the user callable
directly), then RACES the parent-side Up handshake against child-death:

    handshake completes first  -> a live channel; return the terminal.
    child dies first           -> startup failed; return None.

Because the trampoline completes the handshake before the user callable
runs, "handshake completed" provably means "the channel is live".

THE CALLABLE AND ITS ARGS (DISCUSSION.txt D4)

spawn_async/thread/process take a live Python callable; spawn_remote_
process takes a STRING import path (a live function cannot travel to
another machine). Args are ONE object - tuple or dict - never loose
parameters. Channel-and-launch knobs are the separate per-kind 'config'
object (see config.py).
________________________________________________________________________________
"""
import asyncio
import sys
import threading

from vut.engine.event.router   import EventRouter
from vut.engine.event.terminal import EventTerminal

from vut.engine.spawner.config        import (SpawnerConfig,
                                              AsyncConfig,
                                              ThreadConfig,
                                              ProcessConfig,
                                              RemoteProcessConfig)
from vut.engine.spawner.enums         import ChildState
from vut.engine.spawner.events        import (EventChildTerminationReq,
                                              EventChildTermination)
from vut.engine.spawner.handles       import (AsyncChildHandle,
                                              ThreadChildHandle,
                                              ProcessChildHandle,
                                              RemoteChildHandle)
from vut.engine.spawner.state_machine import ChildStateMachine
from vut.engine.spawner.terminals     import SpawnerParentEventTerminal
from vut.engine.spawner.trampoline    import run_trampoline, run_trampoline_entry


# ============================================================================
# The Spawner hub
# ============================================================================

class Spawner:
    """One launched child, supervised: router + handle + state machine.

    A Spawner instance backs ONE spawn. It is created inside _spawn,
    wired up, and bound into the parent terminal via
    attach_supervision(); the user holds the terminal and never names
    the Spawner directly.

    The Spawner owns:
      -- an EventRouter - the hub through which the parent terminal's
         EventChildTerminationReq reaches the supervision logic, and
         through which the Spawner observes both directions of traffic.
      -- the ChildHandle - the OS handle (PID / Task / Process), kept
         here and never surfaced to the user (DISCUSSION.txt D2).
      -- the ChildStateMachine - the FSM that turns observed events into
         ChildState transitions.

    Per DISCUSSION.txt D3, the parent's .terminate() does NOT call a
    Spawner method directly; it emits EventChildTerminationReq, and the
    Spawner picks it up through the router. The handler below is what
    the router delivers that event to.
    """

    def __init__(self, config: SpawnerConfig):
        """RETURN: a new, unwired Spawner for the given config.

        Construction only stores the config and creates the router.
        Wiring (handle, state machine, subscriptions, watchdog) is done
        by _spawn via _wire() and _start_watchdog(), once the child has
        been launched and the parent terminal exists.
        """
        self.config          = config
        self._router         = EventRouter()
        self._handle         = None      # ChildHandle, set by _wire()
        self._state_machine  = None      # ChildStateMachine, set by _wire()
        self._parent         = None      # parent terminal, set by _wire()
        self._watchdog_task  = None      # asyncio.Task, set by _start_watchdog()
        self._watchdog_ms    = 250       # poll period; see _watchdog_loop()

    # ----------------------------------------------------------------
    # Wiring
    # ----------------------------------------------------------------

    def _wire(self, parent_terminal: SpawnerParentEventTerminal,
                    handle) -> ChildStateMachine:
        """RETURN: ChildStateMachine, the freshly built and wired FSM.

        Binds the launched child's OS handle and the parent terminal
        into a ChildStateMachine, then subscribes the Spawner's
        supervision handler to EventChildTerminationReq on the parent
        terminal's dispatcher - so a parent .terminate() reaches the
        FSM (DISCUSSION.txt D3).

        Called once by _spawn after the child is launched and the
        parent handshake has completed.
        """
        self._parent = parent_terminal
        self._handle = handle

        suspend_resume = (handle.suspend, handle.resume) \
                         if handle.can_suspend else (None, None)
        killer         = handle.kill if handle.can_force_kill else None

        self._state_machine = ChildStateMachine(
            parent_terminal = parent_terminal,
            killer          = killer,
            suspend_resume  = suspend_resume,
        )

        # D3: .terminate() emits EventChildTerminationReq; the Spawner
        # acts on it here, picked up off the parent terminal's receive
        # dispatcher.
        parent_terminal.dispatcher.subscribe_on_event(
            EventChildTerminationReq,
            self._on_termination_req,
        )

        # A child may also end on its OWN initiative - work done, no
        # .terminate() ever issued. It still emits EventChildTermination;
        # this always-on subscription drives RUNNING -> TERM_OK for that
        # case (DISCUSSION.txt D7). It stands down while a .terminate()
        # is in progress; see ChildStateMachine.notify_self_completion.
        parent_terminal.dispatcher.subscribe_on_event(
            EventChildTermination,
            self._on_child_termination,
        )

        # When the FSM reaches any terminal state, stop the watchdog -
        # a verdict exists, there is nothing left to supervise.
        self._state_machine.set_on_terminal(self._stop_watchdog)

        return self._state_machine

    # ----------------------------------------------------------------
    # Supervision handler (router delivers EventChildTerminationReq here)
    # ----------------------------------------------------------------

    async def _on_termination_req(self,
                                  event: EventChildTerminationReq) -> None:
        """RETURN: None.

        Handler for the parent's termination request, delivered via the
        router (DISCUSSION.txt D3). It does two things, in order:

          1. RELAYS the request to the child over the channel, so the
             child's SpawnerChildEventTerminal sees EventChildTermination
             Req and can begin a cooperative wind-down. The parent's
             .terminate() dispatched the event only locally (to this
             Spawner); reaching the child is the Spawner's job, since
             the Spawner is the supervisor that "acts".
          2. Hands the wait_to_kill_ms grace period to the state
             machine's begin_termination(), which runs the shutdown
             sequence (TERMINATING, then the confirmation-vs-deadline
             race).

        The request's admissibility (e.g. a numeric deadline on a
        'thread') was already checked by
        SpawnerParentEventTerminal.terminate() before the event was
        ever dispatched (DISCUSSION.txt D9); by the time it arrives here
        it is known-honourable, so this handler does not re-check.

        If the relay send fails (channel already down) the shutdown
        sequence still runs: a child that cannot be reached will simply
        not confirm, and begin_termination()'s deadline path handles
        that.
        """
        # 1. Relay to the child. Best-effort: a failed relay is logged,
        #    not fatal - begin_termination()'s deadline covers it.
        try:
            sent = await self._parent.send(event)
            if not sent:
                print("Spawner._on_termination_req: could not relay the "
                      "request to the child (channel not up); the deadline "
                      "path will handle a missing confirmation.",
                      file=sys.stderr)
        except Exception as e:
            print("Spawner._on_termination_req: relay to child raised: %s"
                  % e, file=sys.stderr)

        # 2. Run the shutdown sequence.
        await self._state_machine.begin_termination(event.wait_to_kill_ms)

    async def _on_child_termination(self,
                                    event: EventChildTermination) -> None:
        """RETURN: None.

        Handler for the child's own EventChildTermination. Forwards it
        to the state machine's notify_self_completion(), which drives
        RUNNING -> TERM_OK for a child that ended on its own initiative
        (DISCUSSION.txt D7).

        When a .terminate() is in progress this is harmless: the FSM is
        in TERMINATING, where notify_self_completion() deliberately
        stands down and lets begin_termination()'s one-shot expect_event
        own the verdict. The two watchers do not collide.
        """
        await self._state_machine.notify_self_completion(event)

    # ----------------------------------------------------------------
    # Suspend / resume (parent terminal delegates here)
    # ----------------------------------------------------------------

    async def suspend_child(self) -> bool:
        """RETURN: True,  the child was suspended; FSM now SUSPENDED.
                   False, suspend failed or was not admissible.

        Thin delegation to the state machine, which checks the child is
        RUNNING and drives the OS handle. Refusal by return value
        (DISCUSSION.txt D9).
        """
        return await self._state_machine.suspend_child()

    async def resume_child(self) -> bool:
        """RETURN: True,  the child was resumed; FSM now RUNNING.
                   False, resume failed or was not admissible.

        Thin delegation to the state machine. Refusal by return value
        (DISCUSSION.txt D9).
        """
        return await self._state_machine.resume_child()

    # ----------------------------------------------------------------
    # Watchdog - liveness supervision
    # ----------------------------------------------------------------

    def _start_watchdog(self) -> None:
        """RETURN: None.

        Starts the liveness watchdog and also wires peer-down. Two
        triggers feed the same resolver:

          -- a periodic poll (every _watchdog_ms) - catches a child
             that has gone SILENT without the channel ever signalling:
             a wedged process, or an abnormally-killed one whose queue
             never closes. A purely reactive scheme would miss these.
          -- the parent terminal's peer-down callback - catches a
             channel that DID signal, without waiting for the next poll
             tick.

        Both call _resolve_silence(), which consults the child handle's
        liveness and hands an E_Liveness to the FSM. The watchdog is the
        only place process/remote abnormal death becomes a verdict; the
        in-process kinds (async/thread) also benefit, since a Task or
        thread that ends without a clean confirmation is caught here too.
        """
        # Reactive trigger: peer-down resolves immediately.
        def _on_peer_down():
            return asyncio.create_task(self._resolve_silence())
        self._parent.set_peer_down_callback(_on_peer_down)

        # Proactive trigger: the periodic poll.
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())

    async def _watchdog_loop(self) -> None:
        """RETURN: None, when the FSM has reached a terminal state.

        The periodic half of the watchdog. Every _watchdog_ms it
        consults the child handle's liveness directly - it does NOT gate
        on the terminal's is_up flag, because a peer killed abnormally
        leaves is_up True indefinitely (the channel queue never closes);
        gating on it would reproduce exactly that blind spot. The
        handle's liveness IS the signal.

        Per tick:

          handle ALIVE    healthy; nothing to do.
          handle DEAD     the child's OS context is gone. A clean
                          completion ALSO reads DEAD, and its
                          EventChildTermination may still be in flight
                          on the receive loop. So a DEAD reading is not
                          acted on immediately: the loop waits one more
                          tick as a grace period for the confirmation
                          to be processed. If the FSM has by then
                          reached a terminal state (TERM_OK), the clean
                          completion won the race and the loop simply
                          exits. If the FSM is STILL live after the
                          grace tick, no confirmation is coming ->
                          _resolve_silence() turns the DEAD reading into
                          TERM_FAILURE.
          handle UNKNOWN  the handle could not be consulted -> resolve
                          immediately (TERM_LOST_CONNECTION); there is
                          no confirmation race to wait out.

        The loop exits as soon as the FSM is terminal - by then a
        verdict exists and there is nothing left to supervise.
        """
        from vut.engine.spawner.handles import E_Liveness
        try:
            while not self._state_machine.state.is_terminal():
                await asyncio.sleep(self._watchdog_ms / 1000.0)
                if self._state_machine.state.is_terminal():
                    break

                liveness = await self._handle.is_alive()

                if liveness is E_Liveness.ALIVE:
                    continue                        # healthy; keep watching

                if liveness is E_Liveness.UNKNOWN:
                    # No information, no race to wait out - resolve now.
                    await self._resolve_silence()
                    break

                # liveness is DEAD: grant one grace tick for an
                # in-flight EventChildTermination to be processed.
                await asyncio.sleep(self._watchdog_ms / 1000.0)
                if self._state_machine.state.is_terminal():
                    break                           # clean completion won
                # Still live after the grace tick - no confirmation is
                # coming. Resolve the DEAD reading into a verdict.
                await self._resolve_silence()
                break
        except asyncio.CancelledError:
            return
        except Exception as e:
            print("Spawner._watchdog_loop: watchdog raised: %s" % e,
                  file=sys.stderr)

    async def _resolve_silence(self) -> None:
        """RETURN: None.

        Consults the child handle's liveness and hands the result to the
        FSM's notify_channel_silent(), which turns it into a terminal
        verdict (TERM_FAILURE for a DEAD child, TERM_LOST_CONNECTION for
        ALIVE / UNKNOWN - see ChildStateMachine.notify_channel_silent).

        A no-op once the FSM is terminal: the verdict is already in.
        Idempotent, so it is safe for both watchdog triggers (poll and
        peer-down) to call it, possibly more than once.
        """
        if self._state_machine.state.is_terminal():
            return
        liveness = await self._handle.is_alive()
        await self._state_machine.notify_channel_silent(liveness)

    def _stop_watchdog(self) -> None:
        """RETURN: None.

        Cancels the periodic watchdog task, if running. Called when the
        FSM reaches a terminal state - there is nothing left to watch.
        Safe to call more than once.
        """
        if self._watchdog_task is not None \
           and not self._watchdog_task.done():
            self._watchdog_task.cancel()


# ============================================================================
# The startup race
# ============================================================================

async def _spawn(launch_child,
                 parent_ecp,
                 config: SpawnerConfig,
                 make_handle) -> "SpawnerParentEventTerminal | None":
    """RETURN: SpawnerParentEventTerminal, on a successful launch -
                                           handshake complete, channel
                                           live, child supervised.
               None,                       on startup failure - the
                                           child died before the
                                           handshake completed.

    The kind-independent core of every spawn_* call (DISCUSSION.txt D5).
    Its three arguments abstract away the kind:

        launch_child  zero-arg callable that actually starts the child
                      at the trampoline and returns whatever object the
                      handle needs (a Task, a Thread, a Process).
        parent_ecp    the parent side of the ECP pair; backs the parent
                      terminal.
        make_handle   callable(launch_result) -> ChildHandle; wraps the
                      launch result in the kind's ChildHandle.

    Sequence:
      1. build the parent terminal from parent_ecp.
      2. launch the child (it boots into the trampoline).
      3. wire supervision - the FSM and its subscriptions - BEFORE the
         handshake is awaited. The subscriptions to EventChildTermination
         and EventChildTerminationReq must exist before the parent's
         receive loop can deliver anything, or an instant-completing
         child's confirmation is dispatched to an empty subscriber set
         and lost. terminal.py explicitly permits subscribing between
         construction and start().
      4. RACE: parent_terminal.start() (the Up handshake) against the
         child dying. Because the trampoline runs start() on the child
         side BEFORE the user callable, a completed handshake proves the
         channel is live.
      5. handshake won  -> attach, drive LAUNCHED -> RUNNING, return.
         child died first -> stop the half-open terminal, return None.

    No exception escapes for an ordinary startup failure: the failure
    outcome is the None return, exactly as DISCUSSION.txt D2 requires.
    """
    parent_terminal = SpawnerParentEventTerminal(parent_ecp)

    # 2. Launch the child. launch_child returns the kind's raw object.
    try:
        launch_result = launch_child()
    except Exception as e:
        print("_spawn: launching the child failed: %s" % e, file=sys.stderr)
        return None

    # 3. Wire supervision BEFORE awaiting the handshake. The FSM's
    # subscriptions must be live before the receive loop runs, so that
    # a child which completes during the handshake still has its
    # EventChildTermination observed (the dispatcher is forward-looking;
    # a subscription added later would miss it).
    handle        = make_handle(launch_result)
    spawner       = Spawner(config)
    state_machine = spawner._wire(parent_terminal, handle)
    parent_terminal.attach_supervision(spawner, state_machine)

    # 4. Race the handshake against child-death.
    handshake  = asyncio.ensure_future(parent_terminal.start())
    child_gone = asyncio.ensure_future(_await_child_gone(launch_result))

    done, pending = await asyncio.wait(
        {handshake, child_gone},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if handshake in done and not handshake.cancelled() \
       and handshake.exception() is None:
        # 5a. Handshake won - the channel is live. Cancel the death
        # watch, start the liveness watchdog (only now, with a proven
        # channel, is there a live child worth supervising), and drive
        # LAUNCHED -> RUNNING. If the child already completed during the
        # handshake, its confirmation was caught by the wired-up
        # subscription and the FSM has already advanced past LAUNCHED;
        # notify_running() is then a no-op.
        child_gone.cancel()
        spawner._start_watchdog()
        await state_machine.notify_running()
        return parent_terminal

    # 5b. The child died first (or start() raised) - startup failed.
    handshake.cancel()
    try:
        await handshake
    except (asyncio.CancelledError, Exception):
        pass
    # Best-effort close of the half-open parent terminal.
    try:
        await parent_terminal.stop()
    except Exception as e:
        print("_spawn: cleanup of half-open terminal raised: %s" % e,
              file=sys.stderr)
    print("_spawn: child died before the startup handshake completed; "
          "spawn failed.", file=sys.stderr)
    return None


async def _await_child_gone(launch_result) -> None:
    """RETURN: None, as soon as the launched child is observed to be gone.

    The death-watch side of the _spawn race. 'launch_result' is the
    kind's raw object:

        asyncio.Task        -> await it (SHIELDED - see below).
        threading.Thread    -> poll is_alive() in the executor.
        multiprocessing.Process -> poll is_alive() / join in the executor.

    The function returns when the child is no longer alive; if the child
    is healthy it simply never returns and is cancelled by _spawn once
    the handshake wins.

    SHIELDING (async kind): _spawn cancels this death-watch the moment
    the handshake wins. For a thread/process the watch only polls, so a
    cancel is harmless. For an async child, however, 'launch_result' IS
    the child Task; a bare 'await launch_result' would make this
    coroutine the Task's awaiter, and cancelling an awaiter propagates
    the cancellation DOWN into the awaited Task - the death-watch would
    kill the very child it was only meant to observe. asyncio.shield
    breaks that downward propagation: the cancel stops here, the child
    Task runs on untouched.
    """
    if isinstance(launch_result, asyncio.Task):
        try:
            await asyncio.shield(launch_result)
        except asyncio.CancelledError:
            # Either this death-watch was cancelled (handshake won) - in
            # which case the shield kept the child alive, exactly as
            # intended - or the child Task itself was cancelled, which
            # IS child-death and should fall through as the signal.
            if launch_result.cancelled():
                return
            raise
        except Exception:
            pass                                    # death is the signal
        return

    # Thread or Process: both expose is_alive(); poll without blocking
    # the loop.
    loop = asyncio.get_running_loop()
    while True:
        alive = await loop.run_in_executor(None, launch_result.is_alive)
        if not alive:
            return
        await asyncio.sleep(0.02)


# ============================================================================
# The four spawn functions
# ============================================================================

async def spawn_async(callable_thing,
                      args,
                      config: "AsyncConfig | None" = None
                      ) -> "SpawnerParentEventTerminal | None":
    """RETURN: SpawnerParentEventTerminal, on success - the child runs as
                                           an asyncio.Task on this loop.
               None,                       on startup failure.

    Launches 'callable_thing' as an asyncio Task. The child shares this
    event loop and memory; the channel is an in-process AsyncChannel
    pair.

    callable_thing -- a live Python callable. It receives a
                      SpawnerChildEventTerminal as its first argument
                      (see 'args' for the tuple-vs-dict shape).
    args           -- the callable's arguments as ONE object: a tuple
                      (passed positionally after the terminal) or a dict
                      (passed as keywords; the terminal is the keyword
                      'event_terminal'). None for no extra arguments.
    config         -- an AsyncConfig, or None for a default AsyncConfig.

    The returned terminal's .suspend()/.resume() will refuse (return
    False): an asyncio Task has no OS-level suspend. .terminate()
    accepts a numeric wait_to_kill_ms - a Task can be cancelled - but a
    cancelled Task ends in TERM_FAILURE (DISCUSSION.txt D7).
    """
    config = config if config is not None else AsyncConfig()
    parent_ecp, child_ecp = config.make_ecp_pair()

    def _launch():
        return asyncio.create_task(
            run_trampoline(child_ecp, callable_thing, args))

    return await _spawn(
        launch_child = _launch,
        parent_ecp   = parent_ecp,
        config       = config,
        make_handle  = lambda task: AsyncChildHandle(task),
    )


async def spawn_thread(callable_thing,
                       args,
                       config: "ThreadConfig | None" = None
                       ) -> "SpawnerParentEventTerminal | None":
    """RETURN: SpawnerParentEventTerminal, on success - the child runs on
                                           a worker thread.
               None,                       on startup failure.

    Launches 'callable_thing' on a dedicated worker thread. The channel
    is an in-process ThreadChannel pair (thread-safe queues).

    callable_thing -- a live Python callable; receives a
                      SpawnerChildEventTerminal first (see 'args').
    args           -- the callable's arguments as ONE object (tuple or
                      dict), or None. Same shape rule as spawn_async.
    config         -- a ThreadConfig, or None for a default ThreadConfig.

    A thread CANNOT be stopped from outside (DISCUSSION.txt D9):
    .suspend()/.resume() refuse (return False), and .terminate() accepts
    ONLY wait_to_kill_ms=None - a numeric deadline is refused (returns
    False), because there is no force-kill to back it.
    """
    config = config if config is not None else ThreadConfig()
    parent_ecp, child_ecp = config.make_ecp_pair()

    def _launch():
        # The worker thread owns its own event loop for the trampoline.
        thread = threading.Thread(
            target = lambda: run_trampoline_entry(
                child_ecp, callable_thing, args),
            daemon = True,
        )
        thread.start()
        return thread

    return await _spawn(
        launch_child = _launch,
        parent_ecp   = parent_ecp,
        config       = config,
        make_handle  = lambda thread: ThreadChildHandle(thread),
    )


async def spawn_process(callable_thing,
                        args,
                        config: "ProcessConfig | None" = None
                        ) -> "SpawnerParentEventTerminal | None":
    """RETURN: SpawnerParentEventTerminal, on success - the child runs as
                                           a separate OS process.
               None,                       on startup failure.

    Launches 'callable_thing' as a child process via multiprocessing.
    The channel is a ProcessChannel pair over multiprocessing.Queue;
    the child ECP is picklable and travels into the child process.

    callable_thing -- a live Python callable. With the 'spawn' start
                      method (the ProcessConfig default) the callable
                      and args must be picklable.
    args           -- the callable's arguments as ONE object (tuple or
                      dict), or None.
    config         -- a ProcessConfig, or None for a default
                      ProcessConfig (start method 'spawn', no cipher).

    The returned terminal supports the full supervision surface:
    .suspend()/.resume() pause/continue the process (SIGSTOP/SIGCONT),
    and .terminate() with a numeric wait_to_kill_ms force-kills the
    process if no confirmation arrives within the grace period.
    """
    config = config if config is not None else ProcessConfig()
    parent_ecp, child_ecp = config.make_ecp_pair()

    def _launch():
        import multiprocessing
        # The start method is read back from the ECP the queues were
        # built under - the ECP is the single source of truth, so the
        # Process context cannot drift from the queue context.
        start_method = child_ecp.params.get("start_method")
        ctx = multiprocessing.get_context(start_method)
        process = ctx.Process(
            target = run_trampoline_entry,
            args   = (child_ecp, callable_thing, args),
            daemon = True,
        )
        process.start()
        return process

    return await _spawn(
        launch_child = _launch,
        parent_ecp   = parent_ecp,
        config       = config,
        make_handle  = lambda process: ProcessChildHandle(process),
    )


async def spawn_remote_process(function_name: str,
                               args,
                               config: RemoteProcessConfig
                               ) -> "SpawnerParentEventTerminal | None":
    """RETURN: SpawnerParentEventTerminal, on success - the child runs as
                                           a process on a remote machine.
               None,                       on startup failure.

    Launches a function on another machine. The channel is a
    RemoteChannel pair over a TCP socket; only the child (connect-end)
    ECP is conveyed to the remote host.

    function_name -- a STRING dotted import path
                     ('package.module.function'), NOT a live callable:
                     a function object cannot travel to another machine
                     (DISCUSSION.txt D4), so the remote side resolves
                     the name by ordinary import. The remote host must
                     have the naming module installed.
    args          -- the function's arguments as ONE object (tuple or
                     dict), or None. Must be serialisable for transport.
    config        -- a RemoteProcessConfig; mandatory (host and port
                     have no default). For a real deployment pass a
                     non-identity cipher_spec - a REMOTE channel with
                     the identity cipher is PLAINTEXT on the network.

    The returned terminal supports the full supervision surface; kill
    and suspend/resume are mediated by a remote agent (see
    RemoteChildHandle).

    NOTE the actual launching of the remote process and the remote
    agent's control channel are deployment-specific and live OUTSIDE
    this function (a deploy step seeds the remote host and starts the
    connect-end). This function performs the LOCAL half: it stands up
    the listen-end parent terminal and races its handshake against a
    connect-timeout. 'launch_child' here is the deployment hook.
    """
    parent_ecp, child_ecp = config.make_ecp_pair()

    # The remote launch hook is deployment-specific; this is the
    # integration seam. It must arrange for the remote host to run
    # run_trampoline_entry(child_ecp, function_name, args) and return
    # an object exposing is_alive() plus the control sender used by
    # RemoteChildHandle.
    def _launch():
        raise NotImplementedError(
            "spawn_remote_process: the remote launch hook is "
            "deployment-specific and must be supplied by the deployment "
            "layer; see the function docstring. The local half (listen-"
            "end terminal, handshake race) is complete and ready."
        )

    def _make_handle(launch_result):
        # launch_result is expected to carry .control_send and
        # .remote_id; shape fixed by the deployment hook.
        return RemoteChildHandle(
            control_send = launch_result.control_send,
            remote_id    = launch_result.remote_id,
        )

    return await _spawn(
        launch_child = _launch,
        parent_ecp   = parent_ecp,
        config       = config,
        make_handle  = _make_handle,
    )
