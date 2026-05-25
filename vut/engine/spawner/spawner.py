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

from vut.engine.spawner.config        import (SpawnerConfig,
                                              AsyncConfig,
                                              ThreadConfig,
                                              ProcessConfig,
                                              RemoteProcessConfig)
from vut.engine.spawner.events        import EventChildTerminationReq
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
         E_ChildState transitions.

    Per DISCUSSION.txt D3, the parent's .terminate() does NOT call a
    Spawner method directly; it emits EventChildTerminationReq, and the
    Spawner picks it up through the router. The handler below is what
    the router delivers that event to.
    """

    def __init__(self, config: SpawnerConfig):
        """RETURN: a new, unwired Spawner for the given config.

        Construction only stores the config and creates the router.
        Wiring (handle, state machine, subscriptions) is done by
        _spawn via _wire(), once the child has been launched and the
        parent terminal exists.
        """
        self.config         = config
        self._router        = EventRouter()
        self._handle        = None      # ChildHandle, set by _wire()
        self._state_machine = None      # ChildStateMachine, set by _wire()
        self._parent        = None      # parent terminal, set by _wire()

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

        parent_terminal.dispatcher.subscribe_on_event(
            EventChildTerminationReq,
            self._on_termination_req,
        )

        return self._state_machine

    # ----------------------------------------------------------------
    # Supervision handler (router delivers EventChildTerminationReq here)
    # ----------------------------------------------------------------
    async def _on_termination_req(self,
                                  event: EventChildTerminationReq) -> None:
        """RETURN: None.

        Handler for the parent's termination request. Hands the
        wait_to_kill_ms grace period to the state machine's
        begin_termination(), which runs the shutdown sequence
        (TERMINATING, then the confirmation-vs-deadline race).

        The request's admissibility (e.g. a numeric deadline on a
        'thread') was already checked by
        SpawnerParentEventTerminal.terminate() before the event was
        ever emitted (DISCUSSION.txt D9); by the time it arrives here
        it is known-honourable, so this handler does not re-check.
        """
        await self._state_machine.begin_termination(event.wait_to_kill_ms)

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
    # Connection-loss wiring
    # ----------------------------------------------------------------
    def _arm_connection_loss(self) -> None:
        """RETURN: None.

        Registers a peer-down callback on the parent terminal so that a
        broken channel drives the FSM to TERM_LOST_CONNECTION
        (DISCUSSION.txt D8).

        A DELIBERATE peer Down that follows a confirmed TERM_OK is
        harmless: notify_connection_lost() is a no-op once the FSM is
        already terminal, so a normal post-confirmation close does not
        get mis-reported as a lost connection.
        """
        def _on_peer_down():
            # Schedule on the loop; the callback itself may be sync.
            return asyncio.create_task(
                self._state_machine.notify_connection_lost())
        self._parent.set_peer_down_callback(_on_peer_down)


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
      3. RACE: parent_terminal.start() (the Up handshake) against the
         child dying. Because the trampoline runs start() on the child
         side BEFORE the user callable, a completed handshake proves the
         channel is live.
      4. handshake won  -> wire supervision, attach, return the terminal.
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

    # 3. Race the handshake against child-death.
    handshake = asyncio.ensure_future(parent_terminal.start())
    child_gone = asyncio.ensure_future(_await_child_gone(launch_result))

    done, pending = await asyncio.wait(
        {handshake, child_gone},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if handshake in done and not handshake.cancelled() \
       and handshake.exception() is None:
        # 4a. Handshake won - the channel is live. Cancel the death
        # watch and wire up supervision.
        child_gone.cancel()
        handle  = make_handle(launch_result)
        spawner = Spawner(config)
        state_machine = spawner._wire(parent_terminal, handle)
        spawner._arm_connection_loss()
        parent_terminal.attach_supervision(spawner, state_machine)
        await state_machine.notify_running()        # LAUNCHED -> RUNNING
        return parent_terminal

    # 4b. The child died first (or start() raised) - startup failed.
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

        asyncio.Task        -> await it directly.
        threading.Thread    -> poll is_alive() in the executor.
        multiprocessing.Process -> poll is_alive() / join in the executor.

    The function returns when the child is no longer alive; if the child
    is healthy it simply never returns and is cancelled by _spawn once
    the handshake wins.
    """
    if isinstance(launch_result, asyncio.Task):
        try:
            await launch_result
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
        ctx = multiprocessing.get_context(config.start_method)
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
