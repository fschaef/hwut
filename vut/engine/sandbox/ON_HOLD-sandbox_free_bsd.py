from   .base import Sandbox, SandboxConfig
import os
from  typeguard import typechecked
import asyncio

class SandboxFreeBSD(Sandbox):
    @typechecked
    def __init__(self, config: SandboxConfig, work_dir: str):
        super().__init__(config, work_dir)
        self.jail_path = "/usr/sbin/jail"
        self.rctl_path = "/usr/bin/rctl"
        # Unique ID for this execution instance
        self.jid       = f"hwut_jail_{os.getpid()}"

    async def _launch(self, *args, **kwargs):
        """Pre-execution: Injects resource limits (rctl)."""
        # RAM and PIDs are enforced via RCTL (FreeBSD's cgroups equivalent)
        # jail:<name>:<resource>:<action>=<amount>
        mem_bytes = self.config.rsrc_max_memory_mb * 1024 * 1024
        
        # Apply limits (requires root)
        rules = [
            f"jail:{self.jid}:memoryuse:deny={mem_bytes}",
            f"jail:{self.jid}:maxproc:deny={self.config.rsrc_max_pids}"
        ]
        
        for rule in rules:
            cmd = await asyncio.create_subprocess_exec(self.rctl_path, "-a", rule)
            await cmd.wait()
            
        return await super()._launch(*args, **kwargs)

    async def _teardown(self, *args, **kwargs):
        """Post-execution: Flushes rctl rules."""
        await super()._teardown(*args, **kwargs)
        # Cleanup resource rules to prevent kernel memory leaks
        cmd = await asyncio.create_subprocess_exec(self.rctl_path, "-r", f"jail:{self.jid}")
        await cmd.wait()

    def _build_cmd(self, command_line: list[str]) -> list[str]:
        """Constructs jail(8) arguments mapping SandboxConfig."""
        
        # -c: Create ephemeral jail
        args = [
            self.jail_path, "-c",
            f"name={self.jid}",
            "host.hostname=sandbox.vut",
            f"path={self.config.fs_root_mount}", # Base RO root
            "exec.jail_user=nobody",            # Unprivileged drop
            "persist=0"                          # Destroy on process exit
        ]

        # FILE SYSTEM: Working Dir & Forbidden Apps
        # Note: FreeBSD jail(8) doesn't have inline bind-mount flags like nsjail.
        # It assumes the host has already mounted nullfs into the 'path'.
        # (See the _setup_bsd_environment we wrote earlier).

        # NETWORK: VNET (Virtual Network Stack)
        if self.config.ntw_share_host_network:
            args.append("ip4=inherit")
            args.append("ip6=inherit")
        else:
            # vnet=new: Creates a private network stack (Net Namespace peer)
            args.append("vnet=new")
            if self.config.ntw_macvlan_iface:
                # Assigns host physical interface to jail stack
                args.append(f"vnet.interface={self.config.ntw_macvlan_iface}")
            
            # Loopback toggle
            if self.config.ntw_disable_loopback:
                args.append("exec.prestart=ifconfig lo0 down")
            else:
                args.append("exec.prestart=ifconfig lo0 up")

        # RESOURCES: CPU Time & File Size
        # Handled via limits(1) wrapper inside the jail
        limit_cmd = [
            "/usr/bin/limits",
            "-t", str(self.config.rsrc_max_cpu_time_sec),
            "-f", str(self.config.rsrc_max_file_size_mb * 1024),
            "--"
        ]

        # Combine with target command
        full_cmd = limit_cmd + command_line
        
        args.append("command=" + full_cmd[0])
        args.extend(full_cmd[1:])
        
        return args
