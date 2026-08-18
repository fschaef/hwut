"""
PURPOSE
       Abstract base class for asynchronous, isolated process execution

DESCRIPTION

       Provides OS-agnostic lifecycle management for sandboxed applications.
       Orchestrates asynchronous subprocess spawning, bi-directional I/O
       stream routing, file backups, and graceful teardown.

       Requires derivation. Child classes must implement `_build_cmd` to
       translate configuration into native kernel isolation commands
       (e.g., nsjail, sandbox-exec).

ARGUMENTS (run)

       command_line     Target executable and arguments as single string.
       stdout_handler   Async callback receiving stdout byte chunks.
       stderr_handler   Async callback receiving stderr byte chunks.
       stdin_reader     Async stream reader piping data to process stdin.
       stop_event       Async event. Triggers premature process termination.
       backup_file_set  Set of filenames to duplicate before execution.
"""
import vut.engine.sandbox.dangerous_executables as dangerous_executables

import asyncio
import logging
import shlex
import datetime
from   dataclasses import dataclass, field
from   typing      import List, Optional, Callable, Awaitable, Iterable
from   pathlib     import Path
from   typeguard   import typechecked
from   abc         import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    # RESOURCES:
    rsrc_max_file_size_mb: int = 10
    rsrc_max_memory_mb: int    = 512
    rsrc_max_pids: int         = 32
    rsrc_max_cpu_time_sec: int = 60

    # FILE SYSTEM:
    fs_root_mount: str           = "/"
    fs_forbidden_apps: List[str] = field(default_factory=dangerous_executables.get)

    # NETWORK:
    #    Network isolation flags.
    ntw_share_host_network: bool = False  # Disables isolation. Shares host network stack.
    ntw_disable_loopback: bool   = False  # Drops default loopback (127.0.0.1) in isolated netns.

    #    MACVLAN -- Media Access Control Virtual Local Area Network
    ntw_macvlan_iface: str = ""  # Host interface for MACVLAN bridge (e.g., 'eth0').
    ntw_macvlan_ip: str    = ""  # Static IP for jailed interface (e.g., '191.168.1.50').
    ntw_macvlan_gw: str    = ""  # Default gateway for jailed interface.


class Sandbox(ABC):
    def __init__(self, config, work_dir: str):
        self.config   = config
        self.work_dir = Path(work_dir).resolve()  # -> absolute path

    @abstractmethod
    def _build_cmd(self, command_line: List[str]) -> List[str]:
        """Translates config into OS-specific sandbox command arguments."""
        pass

    @typechecked
    async def run(self,
                  command_line:    str,
                  stdout_handler:  None | Callable[[bytes], Awaitable[None]],
                  stderr_handler:  None | Callable[[bytes], Awaitable[None]],
                  stdin_reader:    None | asyncio.StreamReader = None,
                  stop_event:      None | asyncio.Event = None,
                  backup_file_set: None | Iterable[str] = None) -> int:
        """
        RETURN: int, exit code returned by the sandboxed process.

        Orchestrates setup, execution, and teardown of the sandboxed subprocess.
        """
        process,  \
        out_task, \
        err_task, \
        in_task,  \
        stop_task = await self._launch(command_line,
                                       stdout_handler, stderr_handler, stdin_reader,
                                       stop_event, backup_file_set)

        exit_code = await process.wait()

        await self._teardown(process, out_task, err_task, in_task, stop_task)

        return exit_code

    async def _launch(self, command_line,
                      stdout_handler, stderr_handler, stdin_reader,
                      stop_event, backup_file_set):
        """SETUP: -- backup files (for those requested)
                  -- readers for stdout, stderr.
                  -- 'pass-through' for stdin of the process.
                  -- task to kill process on 'stop_event'.
        """
        if backup_file_set:
            self._backup_files(backup_file_set)

        process = await asyncio.create_subprocess_exec(
            *self._build_cmd(shlex.split(command_line)),
            stdin  = asyncio.subprocess.PIPE,
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.PIPE,
            cwd    = self.work_dir
        )

        out_task = (asyncio.create_task(self._handle_stream(process.stdout, stdout_handler))
                    if stdout_handler
                    else asyncio.create_task(self._drain(process.stdout)))

        err_task = (asyncio.create_task(self._handle_stream(process.stderr, stderr_handler))
                    if stderr_handler
                    else asyncio.create_task(self._drain(process.stderr)))

        in_task  = asyncio.create_task(self._handle_stdin(process.stdin, stdin_reader))

        async def kill_process_on_event(event):
            if event is None: return
            await event.wait()
            if process.returncode is None:
                process.terminate()

        stop_task = asyncio.create_task(kill_process_on_event(stop_event))

        return process, out_task, err_task, in_task, stop_task

    async def _teardown(self, process, out_task, err_task, in_task, stop_task):
        """CLEAN: -- Drains natural streams.
                  -- Force-cancels blockers.
                  -- Triggers transport closure.
        """
        await asyncio.gather(out_task, err_task)

        in_task.cancel()
        stop_task.cancel()

        await asyncio.gather(in_task, stop_task, return_exceptions=True)

        await self._close_stdin_transport(process)

    async def _close_stdin_transport(self, process):
        """Closes writable stdin pipe. Awaits OS acknowledgment preventing FD leaks."""
        if not process.stdin: return
        process.stdin.close()
        await process.stdin.wait_closed()

    def _backup_files(self, filenames: Iterable[str]):
        """Renames watched files. Injects timestamp before execution."""
        timestamp = datetime.datetime.now().strftime("%Yy%mm%dd-%Hh%Mm%Ss")
        for name in filenames:
            p = self.work_dir / name
            if p.exists():
                backup_path = p.with_name(f"{p.name}-{timestamp}.BACKUP")
                p.rename(backup_path)

    @typechecked
    async def _handle_stream(self, stream: asyncio.StreamReader,
                             handler: Callable[[bytes], Awaitable[None]]):
        """Reads stream asynchronously. Passes chunks to handler."""
        try:
            while not stream.at_eof():
                data = await stream.read(4096)
                if data:
                    await handler(data)
        except Exception:
            logger.warning("Stream read error", exc_info=True)

    async def _drain(self, stream: asyncio.StreamReader):
        """Silently consumes a stream to prevent the subprocess blocking on a full pipe."""
        try:
            while not stream.at_eof():
                await stream.read(4096)
        except Exception:
            logger.warning("Stream drain error", exc_info=True)

    @typechecked
    async def _handle_stdin(self, writer: asyncio.StreamWriter,
                            reader: Optional[asyncio.StreamReader]):
        """Pipes data from reader to process stdin. Closes writer on EOF."""
        if not reader: return
        try:
            while not reader.at_eof():
                data = await reader.read(4096)
                if not data: break
                writer.write(data)
                await writer.drain()
            if writer.can_write_eof():
                writer.write_eof()
            await writer.drain()
            writer.close()
        except Exception:
            logger.warning("Stdin pipe error", exc_info=True)
