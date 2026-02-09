import vut.engine.sandbox.dangerous_executables as dangerous_executables

import asyncio
import os
import shlex
import datetime
from   dataclasses import dataclass, field
from   typing      import List, Optional, Callable, Awaitable
from   pathlib     import Path

@dataclass
class SandboxConfig:
    max_memory_mb: int     = 512
    max_pids: int          = 32
    max_cpu_time_sec: int  = 60
    nsjail_path: str       = "/usr/bin/nsjail"
    root_mount: str        = "/"
    network_enabled: bool  = False

    # Mask specific binaries by mounting /dev/null over them
    forbidden_binaries: List[str] = field(default_factory=dangerous_executables.get)

class Sandbox:
    def __init__(self, config: SandboxConfig, work_dir: str):
        self.config = config
        self.work_dir = Path(work_dir).resolve()

    def _build_nsjail_args(self, command_line: List[str]) -> List[str]:
        curr_uid = os.getuid()
        curr_gid = os.getgid()

        args = [self.config.nsjail_path,
                "--quiet",
                "--mode",             "o",
                "--uid_mapping",      f"0:{curr_uid}:1",
                "--gid_mapping",      f"0:{curr_gid}:1",
                "--user",             "0",
                "--group",            "0",
                "--chroot",           "/",
                "-R",                 self.config.root_mount,
                "-M",                 f"{self.work_dir}:{self.work_dir}",
                "--cwd",              str(self.work_dir),
                "--cgroup_mem_max",   str(self.config.max_memory_mb * 1024 * 1024),
                "--cgroup_pids_max",  str(self.config.max_pids),
                "--time_limit",       str(self.config.max_cpu_time_sec)]

        if not self.config.network_enabled:
            args.append("--disable_clone_newnet")
        
        for bin_path in self.config.forbidden_binaries:
            if os.path.exists(bin_path):
                args.extend(["-R", f"/dev/null:{bin_path}"])

        args.extend(["--"])
        args.extend(command_line)
        return args

    def _backup_files(self, filenames: List[str]):
        """Renames existing watched files to include a timestamp before execution."""
        timestamp = datetime.datetime.now().strftime("%Yy%mm%dd-%Hh%Mm%Ss")
        for name in filenames:
            p = self.work_dir / name
            if p.exists():
                backup_path = p.with_name(f"{p.name}-{timestamp}.BACKUP")
                p.rename(backup_path)

    async def _handle_stream(self, stream: asyncio.StreamReader, handler: Callable[[bytes], Awaitable[None]]):
        """Asynchronously reads from a stream and passes data to the handler."""
        try:
            while not stream.at_eof():
                data = await stream.read(4096)
                if data:
                    await handler(data)
        except Exception:
            pass

    async def _handle_stdin(self, writer: asyncio.StreamWriter, reader: Optional[asyncio.StreamReader]):
        """Feeds data from a reader to the process's stdin."""
        if not reader:
            return
        try:
            while not reader.at_eof():
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
            if writer.can_write_eof():
                writer.write_eof()
            await writer.drain()
            writer.close()
        except Exception:
            pass

    async def run(self,
                  command_line: str,
                  stdout_handler: Callable[[bytes], Awaitable[None]],
                  stderr_handler: Callable[[bytes], Awaitable[None]],
                  watch_files: List[str],
                  stdin_reader: Optional[asyncio.StreamReader] = None,
                  file_handler: Optional[Callable[[str, bytes], Awaitable[None]]] = None,
                  stop_event: Optional[asyncio.Event] = None) -> int:
        
        # 1. Pre-execution: Backup existing files
        self._backup_files(watch_files)

        # 2. Start Process
        process = await asyncio.create_subprocess_exec(
            *self._build_nsjail_args(shlex.split(command_line)),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # 3. IO and Termination Monitoring
        tasks = [
            asyncio.create_task(self._handle_stream(process.stdout, stdout_handler)),
            asyncio.create_task(self._handle_stream(process.stderr, stderr_handler)),
            asyncio.create_task(self._handle_stdin(process.stdin, stdin_reader))
        ]

        async def monitor_stop():
            if stop_event:
                await stop_event.wait()
                if process.returncode is None:
                    process.terminate()

        stop_task = asyncio.create_task(monitor_stop())
        
        # 4. Await Completion
        exit_code = await process.wait()
        
        # Cleanup tasks
        stop_task.cancel()
        for t in tasks:
            t.cancel()

        # 5. Post-execution: Process watched files
        if file_handler:
            for name in watch_files:
                p = self.work_dir / name
                if p.exists() and p.is_file():
                    try:
                        await file_handler(name, p.read_bytes())
                    except Exception:
                        pass

        return exit_code
