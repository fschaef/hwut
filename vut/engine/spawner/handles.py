"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: ChildHandle - the kind-specific OS-handle wrapper.

DISCUSSION.txt D9, "THE KILL ASYMMETRY": contexts differ in their power
to STOP a child.

    process / remote   OS handle; hard, unconditional kill; suspendable.
    async              Task.cancel(); real but cooperative - the
                       CancelledError lands at the next await.
    thread             no force path at all.

The ChildStateMachine must stay kind-agnostic: it knows only "await a
killer" and "await a suspend/resume". This module is where that
asymmetry actually lives - one ChildHandle subclass per kind, each
exposing the same small surface:

    await handle.kill()       force-terminate the OS context
    await handle.suspend()    -> bool
    await handle.resume()     -> bool
    await handle.is_alive()   -> E_Liveness
    handle.can_force_kill     -> bool   (property)
    handle.can_suspend        -> bool   (property)

The OS handle (PID, Task, Process object) is held HERE, inside the
Spawner's reach, and is NEVER surfaced to the user (DISCUSSION.txt D2).

LIVENESS HAS THREE ANSWERS, NOT TWO

is_alive() returns E_Liveness - ALIVE / DEAD / UNKNOWN - not a bool.
The third value matters: a REMOTE handle answers by asking a remote
agent, and that question can itself fail. "I asked and could not get
an answer" is genuinely different from "alive" and from "dead", and the
Spawner's watchdog needs it: per DISCUSSION.txt D8, both ALIVE and
UNKNOWN mean "no usable information about the child" and resolve to
TERM_LOST_CONNECTION, whereas DEAD - the process is gone - resolves to
TERM_FAILURE if no confirmation preceded it (D7). A two-valued bool
could not carry that.

WHY .kill() ON A THREAD HANDLE EXISTS BUT REFUSES

A 'thread' has no kill. ThreadChildHandle.kill() is still present so the
FSM need not special-case the kind - but it is a logged no-op, and
.terminate() refuses a numeric deadline for a thread up front (D9), so
the FSM's deadline path is never actually reached for a thread.
________________________________________________________________________________
"""
import asyncio
import signal
import sys

from enum import Enum, auto


# ============================================================================
# Liveness
# ============================================================================

class E_Liveness(Enum):
    """The three possible answers to ChildHandle.is_alive().

        ALIVE    the child's OS context is confirmed running.
        DEAD     the child's OS context is confirmed gone.
        UNKNOWN  the handle could not be consulted - e.g. a remote
                 agent did not answer. NOT a synonym for either of the
                 above: it means the spawner has no information.

    The Spawner's watchdog maps these onto FSM verdicts: DEAD -> the
    child terminated (TERM_FAILURE if unconfirmed), ALIVE or UNKNOWN ->
    TERM_LOST_CONNECTION (DISCUSSION.txt D8 - "no information").
    """

    ALIVE   = auto()
    DEAD    = auto()
    UNKNOWN = auto()

    def __str__(self) -> str:
        """RETURN: str, the bare member name (e.g. 'ALIVE')."""
        return self.name


# ============================================================================
# Base
# ============================================================================

class ChildHandle:
    """Kind-specific wrapper around a child's OS handle.

    One subclass per execution kind. The Spawner constructs the matching
    subclass at launch and hands it to the ChildStateMachine as the
    'killer' (and, where applicable, the suspend/resume pair). The base
    fixes the surface; subclasses override what their kind can honour.

    Capability properties (can_force_kill, can_suspend) mirror the
    SpawnerConfig properties of the same meaning; they exist on the
    handle too so the FSM can introspect the live handle without
    reaching back to the config.
    """

    _CAN_FORCE_KILL = False
    _CAN_SUSPEND    = False

    async def kill(self) -> None:
        """RETURN: None.

        Force-terminate the child's OS context. The base implementation
        is a logged no-op (the 'thread' kind has no force path); kinds
        that CAN kill override this with the real operation.

        Idempotent: killing an already-dead context is harmless.
        """
        print("ChildHandle.kill: this kind has no force-kill path; "
              "kill() is a no-op.", file=sys.stderr)

    async def suspend(self) -> bool:
        """RETURN: True,  the child was suspended.
                   False, this kind cannot be suspended.

        Base returns False. process / remote override with the real
        OS-handle suspend.
        """
        return False

    async def resume(self) -> bool:
        """RETURN: True,  the child was resumed.
                   False, this kind cannot be resumed.

        Base returns False. process / remote override.
        """
        return False

    async def is_alive(self) -> E_Liveness:
        """RETURN: E_Liveness, the liveness of the child's OS context:
                   ALIVE   - confirmed running,
                   DEAD    - confirmed gone,
                   UNKNOWN - the handle could not be consulted.

        Consulted by the Spawner's watchdog when the channel has gone
        quiet, to decide between TERM_FAILURE (DEAD) and
        TERM_LOST_CONNECTION (ALIVE / UNKNOWN). The base returns UNKNOWN
        - a handle that exposes no liveness query carries no
        information; every concrete subclass overrides this.
        """
        return E_Liveness.UNKNOWN

    @property
    def can_force_kill(self) -> bool:
        """RETURN: True,  if kill() actually force-terminates this kind.
                   False, if kill() is a no-op for this kind.
        """
        return self._CAN_FORCE_KILL

    @property
    def can_suspend(self) -> bool:
        """RETURN: True,  if suspend()/resume() are real for this kind.
                   False, if they always refuse.
        """
        return self._CAN_SUSPEND


# ============================================================================
# async - asyncio.Task
# ============================================================================

class AsyncChildHandle(ChildHandle):
    """Handle wrapping the asyncio.Task that runs an async child.

    kill() cancels the Task. Cancellation is REAL but COOPERATIVE: the
    CancelledError is raised into the Task only when it next hits an
    await. So kill() schedules the cancel and returns; the child may
    take until its next suspension point to actually stop. A child
    ended this way lands in TERM_FAILURE - the cancel is a forced free,
    no confirmation preceded it (DISCUSSION.txt D7).

    suspend()/resume() are NOT supported: a Task has no OS-level
    suspend. They inherit the base's False.
    """

    _CAN_FORCE_KILL = True
    _CAN_SUSPEND    = False

    def __init__(self, task: asyncio.Task):
        """RETURN: a new AsyncChildHandle wrapping 'task'."""
        self._task = task

    async def kill(self) -> None:
        """RETURN: None,  once the Task's cancellation has been requested
                          and awaited to completion.

        Calls Task.cancel() and then awaits the Task so this coroutine
        does not return before the cancellation has actually unwound -
        the CancelledError (and the trampoline's __aexit__) have run by
        the time kill() returns.

        A no-op if the Task is already done.
        """
        if self._task.done():
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("AsyncChildHandle.kill: task raised during cancellation: "
                  "%s" % e, file=sys.stderr)

    async def is_alive(self) -> E_Liveness:
        """RETURN: E_Liveness, ALIVE if the child Task is still running,
                               DEAD if it has finished or been cancelled.

        Never UNKNOWN: a local asyncio.Task is always consultable via
        Task.done().
        """
        return E_Liveness.DEAD if self._task.done() else E_Liveness.ALIVE


# ============================================================================
# thread - no force path
# ============================================================================

class ThreadChildHandle(ChildHandle):
    """Handle for a thread child - no force path at all.

    A thread cannot be stopped from outside (DISCUSSION.txt D9). kill(),
    suspend() and resume() all inherit the base's refusing behaviour.
    The handle still exists so the Spawner can hand the FSM a uniform
    'killer'; it simply never does anything.

    The thread object is held only so the Spawner may join() it during
    its own teardown - that is a wait, not a kill.
    """

    _CAN_FORCE_KILL = False
    _CAN_SUSPEND    = False

    def __init__(self, thread):
        """RETURN: a new ThreadChildHandle wrapping 'thread'.

        'thread' is the threading.Thread running the child; kept for
        join() at Spawner teardown, never for termination.
        """
        self._thread = thread

    async def is_alive(self) -> E_Liveness:
        """RETURN: E_Liveness, ALIVE if the worker thread is still running,
                               DEAD if it has finished.

        Never UNKNOWN: a local threading.Thread is always consultable
        via Thread.is_alive().
        """
        return E_Liveness.ALIVE if self._thread.is_alive() \
               else E_Liveness.DEAD


# ============================================================================
# process - multiprocessing.Process
# ============================================================================

class ProcessChildHandle(ChildHandle):
    """Handle wrapping the multiprocessing.Process of a process child.

    kill() issues a hard, unconditional OS kill (Process.kill(), i.e.
    SIGKILL) and joins the process so kill() does not return before the
    OS context is gone.

    suspend()/resume() send SIGSTOP / SIGCONT to the process, which is
    a genuine OS-level pause - the basis for the SUSPENDED state.
    """

    _CAN_FORCE_KILL = True
    _CAN_SUSPEND    = True

    def __init__(self, process):
        """RETURN: a new ProcessChildHandle wrapping 'process'.

        'process' is the multiprocessing.Process; its .pid backs the
        suspend/resume signals and its .kill()/.join() back the kill.
        """
        self._process = process

    async def kill(self) -> None:
        """RETURN: None,  once the process has been killed and reaped.

        Issues Process.kill() (SIGKILL) and then joins the process in
        the executor so the asyncio loop is not blocked. After this
        returns the OS context is gone and reaped - no zombie.

        A no-op if the process is already not alive.
        """
        if not self._process.is_alive():
            return
        loop = asyncio.get_running_loop()
        self._process.kill()
        await loop.run_in_executor(None, self._process.join)

    async def is_alive(self) -> E_Liveness:
        """RETURN: E_Liveness, ALIVE if the child process is still running,
                               DEAD if it has exited.

        Never UNKNOWN: a local multiprocessing.Process is always
        consultable via Process.is_alive().
        """
        return E_Liveness.ALIVE if self._process.is_alive() \
               else E_Liveness.DEAD

    async def suspend(self) -> bool:
        """RETURN: True,  SIGSTOP was delivered to the child process.
                   False, the process has no pid / is not alive.

        Sends SIGSTOP. The process freezes until a later resume()
        (SIGCONT). Refusal (False) is by return value, never exception
        (DISCUSSION.txt D9).
        """
        pid = self._process.pid
        if pid is None or not self._process.is_alive():
            return False
        try:
            import os
            os.kill(pid, signal.SIGSTOP)
            return True
        except (ProcessLookupError, PermissionError, OSError) as e:
            print("ProcessChildHandle.suspend: SIGSTOP failed: %s" % e,
                  file=sys.stderr)
            return False

    async def resume(self) -> bool:
        """RETURN: True,  SIGCONT was delivered to the child process.
                   False, the process has no pid / is not alive.

        Sends SIGCONT, undoing a prior suspend(). Refusal by return
        value (DISCUSSION.txt D9).
        """
        pid = self._process.pid
        if pid is None or not self._process.is_alive():
            return False
        try:
            import os
            os.kill(pid, signal.SIGCONT)
            return True
        except (ProcessLookupError, PermissionError, OSError) as e:
            print("ProcessChildHandle.resume: SIGCONT failed: %s" % e,
                  file=sys.stderr)
            return False


# ============================================================================
# remote process
# ============================================================================

class RemoteChildHandle(ChildHandle):
    """Handle for a child process on another machine.

    A remote child's OS context is not reachable by a local signal.
    Force-kill and suspend/resume are therefore mediated by the remote
    side: the Spawner sends a control event, and a remote agent applies
    the actual SIGKILL / SIGSTOP / SIGCONT to the local process there.

    This class holds the SENDER of those control events (an async
    callable supplied by the Spawner) plus an opaque remote-process
    identifier. It exposes the same surface as ProcessChildHandle so the
    FSM treats remote and process kinds identically.

    The capability flags are True: a remote process CAN be force-killed
    and suspended - just not by a local syscall.
    """

    _CAN_FORCE_KILL = True
    _CAN_SUSPEND    = True

    def __init__(self, control_send, remote_id, liveness_query=None):
        """RETURN: a new RemoteChildHandle.

        control_send   -- async callable(action_str) -> bool; ships a
                          control action ('kill' / 'suspend' / 'resume')
                          to the remote agent and reports whether the
                          agent acknowledged.
        remote_id      -- opaque identifier of the remote process, for
                          diagnostics; not interpreted locally.
        liveness_query -- optional async callable() -> bool; asks the
                          remote agent whether the remote process is
                          still running (True) or gone (False). If it
                          is None, or if a call raises, is_alive()
                          answers UNKNOWN - the spawner then has no
                          information, which is itself meaningful
                          (DISCUSSION.txt D8).
        """
        self._control_send   = control_send
        self._remote_id      = remote_id
        self._liveness_query = liveness_query

    async def kill(self) -> None:
        """RETURN: None,  once the remote agent has acknowledged the kill.

        Ships a 'kill' control action to the remote agent. If the agent
        does not acknowledge, the failure is logged - from the local
        side this is indistinguishable from a lost connection, and the
        FSM's TERM_LOST_CONNECTION path is the safety net.
        """
        try:
            ok = await self._control_send("kill")
            if not ok:
                print("RemoteChildHandle.kill: remote agent did not "
                      "acknowledge kill of %r." % (self._remote_id,),
                      file=sys.stderr)
        except Exception as e:
            print("RemoteChildHandle.kill: control send failed for %r: %s"
                  % (self._remote_id, e), file=sys.stderr)

    async def suspend(self) -> bool:
        """RETURN: True,  the remote agent acknowledged the suspend.
                   False, the agent refused or the control send failed.

        Refusal by return value (DISCUSSION.txt D9).
        """
        try:
            return await self._control_send("suspend")
        except Exception as e:
            print("RemoteChildHandle.suspend: control send failed for %r: "
                  "%s" % (self._remote_id, e), file=sys.stderr)
            return False

    async def resume(self) -> bool:
        """RETURN: True,  the remote agent acknowledged the resume.
                   False, the agent refused or the control send failed.

        Refusal by return value (DISCUSSION.txt D9).
        """
        try:
            return await self._control_send("resume")
        except Exception as e:
            print("RemoteChildHandle.resume: control send failed for %r: "
                  "%s" % (self._remote_id, e), file=sys.stderr)
            return False

    async def is_alive(self) -> E_Liveness:
        """RETURN: E_Liveness, ALIVE / DEAD if the remote agent answered,
                               UNKNOWN if it could not be reached.

        Unlike the local handles, a remote handle's answer depends on a
        round-trip to a remote agent. This is the one handle that
        genuinely returns UNKNOWN: if no liveness_query was supplied, or
        the query raises (network down, agent gone), the spawner has NO
        information about the remote process - which the watchdog reads,
        per DISCUSSION.txt D8, as TERM_LOST_CONNECTION rather than a
        verdict of death.
        """
        if self._liveness_query is None:
            return E_Liveness.UNKNOWN
        try:
            alive = await self._liveness_query()
        except Exception as e:
            print("RemoteChildHandle.is_alive: liveness query failed for "
                  "%r: %s" % (self._remote_id, e), file=sys.stderr)
            return E_Liveness.UNKNOWN
        return E_Liveness.ALIVE if alive else E_Liveness.DEAD
