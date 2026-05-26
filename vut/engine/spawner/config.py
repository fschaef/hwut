"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: SpawnerConfig -- parameters for the execution infrastructure

When spawning a parallel execution two things were specified, namely:

    (1) function + args  =>  WHAT to run        

    (2) config => event communication channel setup
               => process/task context setup

This module implements the classes to be used for 'config':

    SpawnerConfig -- base class
    AsyncConfig   -- for asyncio.Task execution + channel
    ThreadConfig  -- for Thread based execution + channel
    ProcessConfig -- for Process based execution + channel

    RemoteProcessConfig -- for remote process execution + channel

Main function:

    .make_ecp_pair() --> produce the event channel parameter pair for 
                         user and host (parent and child) connection
                         terminal.s
________________________________________________________________________________
"""
from vut.engine.event.channel.parameter import (EventChannelParameter,
                                                CipherSpec)


# ============================================================================
# Base
# ============================================================================

class SpawnerConfig:
    """Base of the per-kind spawn configuration objects.

    Not instantiated directly; each spawn_* function pairs with one
    concrete subclass (AsyncConfig, ThreadConfig, ProcessConfig,
    RemoteProcessConfig). The base fixes the contract every kind must
    honour:

        make_ecp_pair()        -> (parent_ecp, child_ecp)
        supports_force_kill    -> bool   (property)
        supports_suspend       -> bool   (property)
        kind_name              -> str    (property, for diagnostics)

    A subclass overrides make_ecp_pair() and the two capability
    properties; everything else about a spawn is kind-independent.
    """

    # Capability defaults. Subclasses override where their kind differs.
    _SUPPORTS_FORCE_KILL = False
    _SUPPORTS_SUSPEND    = False
    _KIND_NAME           = "base"

    def make_ecp_pair(self) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (parent_ecp, child_ecp), the mirror ECP pair for one spawn.

        parent_ecp backs the SpawnerParentEventTerminal and stays local;
        child_ecp is conveyed to the child side and backs the
        SpawnerChildEventTerminal.

        The base raises NotImplementedError; every concrete config
        overrides this with the matching EventChannelParameter.for_*
        factory call.
        """
        raise NotImplementedError(
            "SpawnerConfig.make_ecp_pair: %s must override make_ecp_pair()"
            % type(self).__name__
        )

    @property
    def supports_force_kill(self) -> bool:
        """RETURN: True,  if a child of this kind has an OS force-kill path.
                   False, if it cannot be force-killed from outside.

        process / remote -> True (OS handle, hard kill).
        async            -> True (Task.cancel(); cooperative but real).
        thread           -> False (a thread cannot be stopped from
                                   outside at all; see DISCUSSION.txt D9).

        .terminate() consults this to decide whether a numeric
        wait_to_kill_ms is honourable for this kind.
        """
        return self._SUPPORTS_FORCE_KILL

    @property
    def supports_suspend(self) -> bool:
        """RETURN: True,  if a child of this kind can be suspended/resumed.
                   False, if .suspend()/.resume() must refuse for this kind.

        Only process and remote children, which have an OS handle, can
        be suspended. async and thread return False (DISCUSSION.txt D9).
        """
        return self._SUPPORTS_SUSPEND

    @property
    def kind_name(self) -> str:
        """RETURN: str, the kind label ('async'/'thread'/'process'/'remote').

        For diagnostics and error messages only; not a wire value.
        """
        return self._KIND_NAME


# ============================================================================
# async
# ============================================================================

class AsyncConfig(SpawnerConfig):
    """Configuration for spawn_async - child runs as an asyncio.Task.

    The child shares the parent's event loop and memory; the channel is
    an in-process AsyncChannel pair. No transport security applies
    (in-process channels never serialise), so there is no cipher knob.

    FORCE-KILL: an asyncio.Task can be cancelled, but cancellation is
    cooperative - the CancelledError lands only at the child's next
    await. So supports_force_kill is True, but a cancelled Task ends in
    TERM_FAILURE (no confirmation preceded the forced cancel; D7).

    SUSPEND: not supported - a Task has no OS-level suspend.
    """

    _SUPPORTS_FORCE_KILL = True
    _SUPPORTS_SUSPEND    = False
    _KIND_NAME           = "async"

    def make_ecp_pair(self) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (parent_ecp, child_ecp), an in-process asyncio-queue pair.

        Both ECPs must be used on the SAME event loop, which holds for
        spawn_async since the child Task runs on the parent's loop.
        """
        return EventChannelParameter.for_async()


# ============================================================================
# thread
# ============================================================================

class ThreadConfig(SpawnerConfig):
    """Configuration for spawn_thread - child runs on a worker thread.

    The channel is an in-process ThreadChannel pair (thread-safe
    queue.Queue). No cipher knob - in-process, never serialised.

    FORCE-KILL: NONE. A thread cannot be stopped from outside
    (DISCUSSION.txt D9). supports_force_kill is False; .terminate()
    therefore accepts ONLY wait_to_kill_ms=None for a thread child and
    refuses (returns False) a numeric deadline.

    SUSPEND: not supported - no OS handle to suspend.
    """

    _SUPPORTS_FORCE_KILL = False
    _SUPPORTS_SUSPEND    = False
    _KIND_NAME           = "thread"

    def make_ecp_pair(self) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (parent_ecp, child_ecp), an in-process thread-queue pair."""
        return EventChannelParameter.for_thread()


# ============================================================================
# process
# ============================================================================

class ProcessConfig(SpawnerConfig):
    """Configuration for spawn_process - child runs as a child process.

    The channel is a ProcessChannel pair over multiprocessing.Queue;
    the child ECP is picklable and travels to the spawned process. A
    CipherSpec may be supplied to encrypt the (serialised) wire; it
    defaults to identity (no encryption), which is the in-process-host
    norm.

        start_method  the multiprocessing start method
                      ('spawn' / 'fork' / 'forkserver'), or None to use
                      the platform default. 'spawn' is the portable,
                      pickle-clean choice.
        cipher_spec   a CipherSpec for the serialised wire, or None for
                      identity (plaintext between local processes).

    FORCE-KILL: supported - the Spawner holds the OS handle and can
    issue an unconditional kill.

    SUSPEND: supported - the OS handle can suspend/resume the process.
    """

    _SUPPORTS_FORCE_KILL = True
    _SUPPORTS_SUSPEND    = True
    _KIND_NAME           = "process"

    def __init__(self,
                 start_method: "str | None"        = "spawn",
                 cipher_spec:  "CipherSpec | None" = None):
        """RETURN: a new ProcessConfig.

        start_method defaults to 'spawn' (portable, requires picklable
        args). cipher_spec defaults to None -> identity cipher.
        """
        self.start_method = start_method
        self.cipher_spec  = cipher_spec

    def make_ecp_pair(self) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (parent_ecp, child_ecp), a multiprocessing-queue pair.

        The cipher_spec (if any) is carried on BOTH ECPs so each side
        builds the identical Cipher at make_channel() time.

        start_method is passed to for_process() so the queues are built
        under the SAME multiprocessing context the child process will be
        started under - a queue and a process from mismatched contexts
        are rejected by Python. spawn_process reads the method back from
        the ECP params to start the child consistently.
        """
        return EventChannelParameter.for_process(
            cipher_spec  = self.cipher_spec,
            start_method = self.start_method,
        )


# ============================================================================
# remote process
# ============================================================================

class RemoteProcessConfig(SpawnerConfig):
    """Configuration for spawn_remote_process - child runs on another machine.

    The channel is a RemoteChannel pair over a TCP socket. Only the
    child (connect-end) ECP travels to the remote host; the parent
    holds the listen end.

        host         the address the two ends rendezvous on.
        port         the TCP port.
        cipher_spec  a CipherSpec for the network wire. For a REMOTE
                     channel an identity cipher means PLAINTEXT on the
                     network; a real deployment should pass a real
                     CipherSpec. Defaults to None -> identity.

    FORCE-KILL: supported - the remote side exposes an OS handle the
    Spawner can kill through the supervision path.

    SUSPEND: supported - the remote OS handle can suspend/resume.

    NOTE the function to run is named by STRING for this kind
    (DISCUSSION.txt D4): a live callable cannot travel to another
    machine, so the remote side resolves an importable path by ordinary
    import. That string is an argument of spawn_remote_process, not of
    this config.
    """

    _SUPPORTS_FORCE_KILL = True
    _SUPPORTS_SUSPEND    = True
    _KIND_NAME           = "remote"

    def __init__(self,
                 host:        str,
                 port:        int,
                 cipher_spec: "CipherSpec | None" = None):
        """RETURN: a new RemoteProcessConfig.

        host and port are mandatory - a remote rendezvous has no
        default. cipher_spec defaults to None -> identity cipher
        (PLAINTEXT on the network; supply a real spec for production).
        """
        self.host        = host
        self.port        = port
        self.cipher_spec = cipher_spec

    def make_ecp_pair(self) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (parent_ecp, child_ecp), a remote socket ECP pair.

        parent_ecp is the LISTEN end and stays local; child_ecp is the
        CONNECT end and is the one conveyed to the remote machine.
        """
        return EventChannelParameter.for_remote(
            host        = self.host,
            port        = self.port,
            cipher_spec = self.cipher_spec,
        )
