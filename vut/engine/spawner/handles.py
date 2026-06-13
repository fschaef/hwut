"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: ChildHandle - Abstract the OS handle for execution context:

The ChildStateMachine must stay context-agnostic: it knows only "await a
killer" and "await a suspend/resume". The specifics of handles related 
to context are hidden behind a 'ChildHandle' object, exposing a 
homogenous API: 

    await handle.kill()       force-terminate the OS context
    await handle.suspend()    -> bool
    await handle.resume()     -> bool
    await handle.liveness()   -> E_Liveness (ALIVE, DEAD, UNKNOWN)
    handle.can_force_kill     -> bool   (property)
    handle.can_suspend        -> bool   (property)

NOTES: 

    'E_Liveness.UNKNOWN': could not get an answer whether the child is alive.

    .kill(), .suspend(), .resume(): do not work in all contexts. 
        If they don't, they return 'False' upon call -- not an exception.
________________________________________________________________________________
"""
import asyncio
import signal
import sys
from   abc import ABC

from vut.engine.spawner.enums import E_Liveness


class ChildHandle(ABC):
    """Kind-specific wrapper around a child's execution context handle.
    """
    _CAN_FORCE_KILL = False
    _CAN_SUSPEND    = False

    async def kill(self) -> bool:
        """RETURN: True,  a force-kill was initiated for this kind.
                   False, this kind has no force-kill path; nothing done.

        Force-terminate the child's execution context, i.e. free any
        system resources related to the child's execution. The base has
        no force path and returns False; kinds that can force-kill
        override this and return True. Selection by capability
        (handle.can_force_kill) means the base kill() is not used as a
        killer - it is the honest default for a kind with no force path.

        Idempotent: killing an already-dead context is harmless.
        """
        print("ChildHandle.kill(): this kind has no force-kill path; "
              "kill() is a no-op.", file=sys.stderr)
        return False

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

    async def liveness(self) -> E_Liveness:
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

    kill() is supported only cooperatively.

    suspend()/resume() are NOT supported: a Task has no OS-level
    suspend. They inherit the base's False.
    """

    _CAN_FORCE_KILL = True
    _CAN_SUSPEND    = False

    def __init__(self, task: asyncio.Task):
        """RETURN: a new AsyncChildHandle wrapping 'task'."""
        self._task = task

    async def kill(self) -> bool:
        """RETURN: True, always - an asyncio.Task is cancellable, so the
                         force-kill (Task.cancel + await) is always
                         initiated. Cancellation is cooperative (the
                         CancelledError lands at the next await), so a
                         cancelled Task ends in TERM_FAILURE.

        A no-op returning True if the Task is already done.
        """
        if self._task.done():
            return True
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("AsyncChildHandle.kill: task raised during cancellation: "
                  "%s" % e, file=sys.stderr)
        return True

    async def liveness(self) -> E_Liveness:
        """RETURN: E_Liveness, ALIVE if the child Task is still running,
                               DEAD if it has finished or been cancelled.

        Never UNKNOWN: a local asyncio.Task is always consultable via
        Task.done().
        """
        return E_Liveness.DEAD if self._task.done() else E_Liveness.ALIVE


class ThreadChildHandle(ChildHandle):
    """Handle for a thread child - no force path at all.

    .kill()               -- not supported.
    .suspend(), .resume() -- not supported
    """

    _CAN_FORCE_KILL = False
    _CAN_SUSPEND    = False

    def __init__(self, thread):
        """RETURN: a new ThreadChildHandle wrapping 'thread'.

        'thread' is the threading.Thread running the child; kept for
        join() at Spawner teardown, never for termination.
        """
        self._thread = thread

    async def liveness(self) -> E_Liveness:
        """RETURN: E_Liveness, ALIVE if the worker thread is still running,
                               DEAD if it has finished.

        Never UNKNOWN: a local threading.Thread is always consultable
        via Thread.is_alive().
        """
        return E_Liveness.ALIVE if self._thread.is_alive() \
               else E_Liveness.DEAD

class ProcessChildHandle(ChildHandle):
    """Handle wrapping the multiprocessing.Process of a process child.
    """

    _CAN_FORCE_KILL = True
    _CAN_SUSPEND    = True

    def __init__(self, process):
        """RETURN: a new ProcessChildHandle wrapping 'process'.

        'process' is the multiprocessing.Process; its .pid backs the
        suspend/resume signals and its .kill()/.join() back the kill.
        """
        self._process = process

    async def kill(self) -> bool:
        """RETURN: True, always - a process has an OS handle, so the
                         force-kill is always initiated.

        Issues Process.kill() (SIGKILL) and then joins the process in the
        executor so the asyncio loop is not blocked. After this returns the OS
        context is gone and reaped - no zombie.

        A no-op returning True if the process is already not alive.
        """
        if not self._process.is_alive():
            return True
        loop = asyncio.get_running_loop()
        self._process.kill()
        await loop.run_in_executor(None, self._process.join)
        return True

    async def liveness(self) -> E_Liveness:
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


class RemoteChildHandle(ChildHandle):
    """Handle for a child process on another machine.

    Contains sender of remote control events, and a remote agent applies the
    actual SIGKILL / SIGSTOP / SIGCONT to the local process there.
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
                          is None, or if a call raises, liveness()
                          answers UNKNOWN - the spawner then has no
                          information, which is itself meaningful
                          (DISCUSSION.txt D8).
        """
        self._control_send   = control_send
        self._remote_id      = remote_id
        self._liveness_query = liveness_query

    async def kill(self) -> bool:
        """RETURN: True,  the remote agent acknowledged the kill.
                   False, the agent did not acknowledge, or the control
                          send failed - from the local side this is
                          indistinguishable from a lost connection, and
                          the FSM's TERM_LOST_CONNECTION path is the
                          safety net.

        Ships a 'kill' control action to the remote agent.
        """
        try:
            ok = await self._control_send("kill")
            if not ok:
                print("RemoteChildHandle.kill: remote agent did not "
                      "acknowledge kill of %r." % (self._remote_id,),
                      file=sys.stderr)
            return bool(ok)
        except Exception as e:
            print("RemoteChildHandle.kill: control send failed for %r: %s"
                  % (self._remote_id, e), file=sys.stderr)
            return False

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

    async def liveness(self) -> E_Liveness:
        """RETURN: E_Liveness, ALIVE / DEAD if the remote agent answered,
                               UNKNOWN if it could not be reached.

        Initiates round-trip query about the child's liveness.
        """
        if self._liveness_query is None:
            return E_Liveness.UNKNOWN
        try:
            alive = await self._liveness_query()
        except Exception as e:
            print("RemoteChildHandle.liveness: liveness query failed for "
                  "%r: %s" % (self._remote_id, e), file=sys.stderr)
            return E_Liveness.UNKNOWN
        return E_Liveness.ALIVE if alive else E_Liveness.DEAD
