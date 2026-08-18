"""
PURPOSE
       High-density Solaris Zone process isolation

DESCRIPTION
       Implements illumos/SmartOS specific sandboxing. Uses `prctl` for 
       hard resource controls and `ppriv` to drop kernel privileges. 
       
       CRITIQUE: While full Zones are the gold standard for long-running 
       services, booting a full Zone for a 2-second test is too heavy. 
       This implementation uses the lightweight approach: a standard 
       chroot combined with strict privilege stripping (ppriv) and 
       resource controls (prctl) applied directly to the test process.
"""
from   .base import Sandbox, SandboxConfig

from   typeguard import typechecked
import os
import shutil
import tempfile
import asyncio

class SandboxIllumos(Sandbox):
    @typechecked
    def __init__(self, config: SandboxConfig, work_dir: str):
        """Initializes illumos utilities."""
        super().__init__(config, work_dir)
        self.ppriv_path = "/usr/bin/ppriv"
        self.prctl_path = "/usr/bin/prctl"

    def _build_cmd(self, command_line: list[str]) -> list[str]:
        """Constructs privilege-stripped, resource-capped execution string."""
        
        args = []

        # RESOURCES (prctl)
        # In illumos, you can prefix a command with prctl to set limits on the fly.
        # project.max-locked-memory, process.max-cpu-time, etc.
        mem_bytes = self.config.rsrc_max_memory_mb * 1024 * 1024
        cpu_sec   = self.config.rsrc_max_cpu_time_sec

        args.extend([
            self.prctl_path, 
            "-n", "process.max-cpu-time", "-v", str(cpu_sec), "-e", "deny",
            "-n", "process.max-address-space", "-v", str(mem_bytes), "-e", "deny"
        ])

        # PRIVILEGES (ppriv)
        # Drops basic privileges. 
        # e.g., prevents the process from using raw sockets, mounting filesystems, 
        # or observing other processes, even if running as root.
        args.extend([
            self.ppriv_path,
            "-e", # Execute the following command
            "-s", "EIP-basic", # Strips all privileges down to the absolute minimum
        ])

        # NETWORK
        if not self.config.ntw_share_host_network:
            # Further strips network access privileges.
            args.extend(["-s", "EIP-net_access"])

        # EXECUTION
        args.extend(command_line)

        return args

    async def _launch(self, command_line, 
                      stdout_handler, stderr_handler, stdin_reader, 
                      stop_event, backup_file_set):
        """Pre-flight OS setup -> Base execution."""
        
        # 1. OS-SPECIFIC SETUP
        await self._setup_bsd_environment()

        # 2. BASE EXECUTION
        return await super()._launch(
            command_line, stdout_handler, stderr_handler, 
            stdin_reader, stop_event, backup_file_set
        )

    async def _teardown(self, process, out_task, err_task, in_task, stop_task):
        """Base cleanup -> Post-flight OS teardown."""
        
        # 1. BASE CLEANUP
        await super()._teardown(process, out_task, err_task, in_task, stop_task)

        # 2. OS-SPECIFIC TEARDOWN
        await self._cleanup_bsd_environment()

    async def _setup_bsd_environment(self):
        """Creates ephemeral root. Mounts ro base and rw working directory."""
        
        # Generates unique mount point for this execution instance.
        self.jail_root = tempfile.mkdtemp(prefix="vut_jail_")

        # 1. MOUNT: Read-Only Base
        mnt_ro = await asyncio.create_subprocess_exec(
            "/sbin/mount", "-t", "nullfs", "-o", "ro",
            self.config.fs_root_mount, self.jail_root,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr_ro = await mnt_ro.communicate()
        
        if mnt_ro.returncode != 0:
            os.rmdir(self.jail_root)
            raise RuntimeError(f"nullfs ro mount failed: {stderr_ro.decode().strip()}")

        # 2. MOUNT: Read-Write Working Directory
        # Maps host work_dir directly into the corresponding path inside the jail_root.
        jail_work_dir = os.path.join(self.jail_root, str(self.work_dir).lstrip("/"))
        os.makedirs(jail_work_dir, exist_ok=True)
        
        mnt_rw = await asyncio.create_subprocess_exec(
            "/sbin/mount", "-t", "nullfs",
            str(self.work_dir), jail_work_dir,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr_rw = await mnt_rw.communicate()
        
        if mnt_rw.returncode != 0:
            # Reverts the first mount on failure to prevent leaks.
            await self._cleanup_bsd_environment() 
            raise RuntimeError(f"nullfs rw mount failed: {stderr_rw.decode().strip()}")

        # Adjusts configuration path for _build_cmd to use the new ephemeral root.
        self._dynamic_jail_path = self.jail_root

    async def _cleanup_bsd_environment(self):
        """Forces unmounts in reverse order. Destroys ephemeral root."""
        if not hasattr(self, 'jail_root'):
            return

        jail_work_dir = os.path.join(self.jail_root, str(self.work_dir).lstrip("/"))
        
        # 1. UNMOUNT: Read-Write Working Directory
        # -f: Forces unmount if busy (requires root).
        if os.path.ismount(jail_work_dir):
            umnt_rw = await asyncio.create_subprocess_exec("/sbin/umount", "-f", jail_work_dir)
            await umnt_rw.wait()

        # 2. UNMOUNT: Read-Only Base
        if os.path.ismount(self.jail_root):
            umnt_ro = await asyncio.create_subprocess_exec("/sbin/umount", "-f", self.jail_root)
            await umnt_ro.wait()

        # 3. DESTROY: Ephemeral directory
        shutil.rmtree(self.jail_root, ignore_errors=True)
