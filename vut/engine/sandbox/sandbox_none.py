"""
NAME
       SandboxWindowsWSB - Native Windows micro-VM process isolation

SYNOPSIS
       class SandboxWindowsWSB(Sandbox)
       SandboxWindowsWSB(config: SandboxConfig, work_dir: str)

DESCRIPTION
       Implements native sandboxing via Windows Sandbox (.wsb). Dynamically 
       generates XML configuration. Maps host directories. Toggles virtual 
       network adapters.

       CRITIQUE: WSB is designed for GUI desktop testing, not CLI pipelines. 
       Standard output, error streams, and exit codes remain trapped inside 
       the VM and will not pipe back to the Python asyncio readers. Resource 
       limits (CPU/RAM) cannot be explicitly capped via the .wsb file.
       Requires Windows feature "Windows Sandbox" to be enabled.
"""
from .base import Sandbox
from typeguard import typechecked

class SandboxNone(Sandbox):
    @typechecked
    def __init__(self, config, work_dir: str):
        """Initializes passthrough environment. Retains base class signature."""
        super().__init__(config, work_dir)

    def _build_cmd(self, command_line: list[str]) -> list[str]:
        """Returns raw command line. Injects zero isolation wrappers."""
        
        # Returns exact target payload. No wrappers, no limits.
        return command_line
