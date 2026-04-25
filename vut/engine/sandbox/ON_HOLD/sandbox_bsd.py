"""
PURPOSE
       FreeBSD jail-based asynchronous process isolation

SYNOPSIS
       class SandboxBSD(Sandbox)
       SandboxBSD(config: SandboxConfig, work_dir: str)

DESCRIPTION
       Implements FreeBSD-specific sandboxing using jail(8) and limits(1).
       Creates ephemeral environments. Avoids filesystem cloning by sharing 
       host root directly. Relies on standard UNIX file permissions and 
       privilege dropping (exec.jail_user) to restrict binary access.
       Enforces resource quotas inline via limits wrapper.

DEPENDENCIES
       /usr/sbin/jail
       /usr/bin/limits
"""
from .base import Sandbox, SandboxConfig

from typeguard import typechecked

class SandboxBSD(Sandbox):
    @typechecked
    def __init__(self, config: SandboxConfig, work_dir: str):
        """Initializes FreeBSD command paths. Sets target jail name."""
        super().__init__(config, work_dir)
        self.jail_path   = "/usr/sbin/jail"
        self.limits_path = "/usr/bin/limits"
        self.jail_name   = "sandbox_vut"
        self.jail_user   = "nobody" # Unprivileged dummy user.

    def _build_cmd(self, command_line: list[str]) -> list[str]:
        """Constructs ephemeral jail. Wraps execution with limits utility."""
        
        # -c: Creates ephemeral jail. Destroyed on exit.
        args = [self.jail_path, "-c"]
        args.append(f"name={self.jail_name}")
        
        # Maps root. Relies on host UNIX permissions for isolation.
        args.append(f"path={self.config.fs_root_mount}")

        # Drops privileges. Prevents execution of forbidden host binaries 
        # (assuming binaries restrict 'nobody' via chmod 750).
        args.append(f"exec.jail_user={self.jail_user}")

        # NETWORK
        if self.config.ntw_share_host_network:
            # Inherits host IPv4/IPv6 stack entirely.
            args.append("ip4=inherit")
            args.append("ip6=inherit")
        else:
            if self.config.ntw_macvlan_ip and self.config.ntw_macvlan_iface:
                # Binds specific IP to existing host interface (IP aliasing).
                args.append(f"interface={self.config.ntw_macvlan_iface}")
                args.append(f"ip4.addr={self.config.ntw_macvlan_ip}")
            else:
                # Strict vacuum. Requires VNET-compiled FreeBSD kernel.
                args.append("vnet=new")

        # RESOURCES
        # Wraps target command.
        # -f: Max file size (bytes). -m: Max memory (bytes). 
        # -t: CPU time (sec). -u: Max user processes.
        limit_args = [
            self.limits_path,
            "-f", str(self.config.rsrc_max_file_size_mb * 1024 * 1024),
            "-m", str(self.config.rsrc_max_memory_mb * 1024 * 1024),
            "-t", str(self.config.rsrc_max_cpu_time_sec),
            "-u", str(self.config.rsrc_max_pids),
            "--"
        ]
        
        # Merges limit wrapper with target execution string.
        full_command = limit_args + command_line
        
        # jail(8) expects 'command=' followed by actual execution arguments.
        args.append("command=" + full_command[0])
        args.extend(full_command[1:])

        return args
