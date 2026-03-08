"""
PURPOSE
       macOS Seatbelt-based asynchronous process isolation

DESCRIPTION
       Implements macOS-specific sandboxing using Apple's Seatbelt engine 
       via sandbox-exec(1). Dynamically generates Scheme (.sb) profiles 
       in memory to enforce access controls. Provides strict filesystem 
       and network boundaries. Relies on kernel-level hooks rather than 
       dummy users or namespaces. 

       CRITIQUE/LIMITATION: macOS lacks a native CLI wrapper for resource 
       quotas (CPU time, memory) comparable to FreeBSD limits(1). CPU 
       and memory parameters from SandboxConfig are silently ignored.

DEPENDENCIES
       /usr/bin/sandbox-exec
"""
from .base import Sandbox, SandboxConfig

from typeguard import typechecked

class SandboxMacOs(Sandbox):
    @typechecked
    def __init__(self, config: SandboxConfig, work_dir: str):
        """Initializes macOS execution path. Resolves absolute working directory."""
        super().__init__(config, work_dir)
        self.sandbox_path = "/usr/bin/sandbox-exec"

    def _build_cmd(self, command_line: list[str]) -> list[str]:
        """Generates Seatbelt profile. Wraps target command."""
        
        # MAC OS SEATBELT PROFILE (Scheme language)
        # (version 1): Required profile header.
        # (deny default): Establishes strict deny-all baseline.
        profile = [
            "(version 1)",
            "(deny default)"
        ]

        # FILE SYSTEM
        # Grants global read access (matches nsjail -R /).
        profile.append("(allow file-read*)")
        # Grants basic execution rights.
        profile.append("(allow process-exec)")
        # Restricts writes exclusively to working directory.
        profile.append(f'(allow file-write* (subpath "{self.work_dir}"))')
        # Masks forbidden applications explicitly.
        for app in self.config.fs_forbidden_apps:
            profile.append(f'(deny process-exec (literal "{app}"))')
            profile.append(f'(deny file-read* (literal "{app}"))')

        # NETWORK
        if self.config.ntw_share_host_network:
            # Full stack access.
            profile.append("(allow network*)")
        else:
            # Deny-all baseline already blocks network.
            if not self.config.ntw_disable_loopback:
                # Pierces boundary specifically for localhost.
                profile.append('(allow network* (local ip "localhost:*"))')
                profile.append('(allow network* (remote ip "localhost:*"))')

        # SYSTEM/IPC (Required for standard Python/C binaries to not crash immediately)
        profile.append("(allow sysctl-read)")
        profile.append("(allow mach-lookup)")

        # command-line construction
        # -p: Passes raw profile string directly instead of file path.
        args = [self.sandbox_path, "-p", "\n".join(profile)]
        args.extend(command_line)
        args.extend(self._generate_rlimit_wrapper(RLIMIT_AS_enabled_f=False))

        return args

_generate_rlimit_wrapper_py = """
"""
def _generate_rlimit_wrapper(config, RLIMIT_AS_enabled_f: bool = False) -> list[str]:
    """RETURNS: command line extension for resource limit check. 

    NOTE: 'RLIMIT_AS' may cause crashes when interpreters are called
          with large memory requirements (even if the app is small).

    Generates inline Python script enforcing OS-level resource quotas.
    """
    
    # Calculates bytes.
    fsize_bytes = config.rsrc_max_file_size_mb * 1024 * 1024
    mem_bytes   = config.rsrc_max_memory_mb * 1024 * 1024
    cpu_sec     = config.rsrc_max_cpu_time_sec
    pids        = config.rsrc_max_pids

    # Conditionally injects strict virtual memory cap.
    rlimit_as_line = ""
    if RLIMIT_AS_enabled_f:
        rlimit_as_line = f"resource.setrlimit(resource.RLIMIT_AS, ({mem_bytes}, {mem_bytes}))"

    # Inline wrapper code. 
    # Catches ValueError/OSError if requested limits exceed hard kernel ceilings.
    wrapper_code = f"""
import os, sys, resource
try:
    resource.setrlimit(resource.RLIMIT_FSIZE, ({fsize_bytes}, {fsize_bytes}))
    {rlimit_as_line}
    resource.setrlimit(resource.RLIMIT_CPU, ({cpu_sec}, {cpu_sec}))
    resource.setrlimit(resource.RLIMIT_NPROC, ({pids}, {pids}))
except (ValueError, OSError):
    pass
os.execvp(sys.argv[1], sys.argv[1:])
"""
    return ["python3", "-c", wrapper_code.strip()]
