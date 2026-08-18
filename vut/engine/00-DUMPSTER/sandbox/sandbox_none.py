"""
NAME
       SandboxNone - No-op passthrough sandbox

SYNOPSIS
       class SandboxNone(Sandbox)
       SandboxNone(config: SandboxConfig, work_dir: str)

DESCRIPTION
       Fallback sandbox used when no platform-specific implementation is
       available (e.g. Windows). Executes the target command directly in
       the host environment with zero isolation wrappers, no resource caps,
       and no filesystem restrictions.

       CRITIQUE: Provides no security boundary whatsoever. Intended solely
       as a development convenience and explicit no-op placeholder. Should
       never be used in production environments where process isolation is
       required.
"""
from .base   import Sandbox
from typeguard import typechecked


class SandboxNone(Sandbox):
    @typechecked
    def __init__(self, config, work_dir: str):
        """Initializes passthrough environment. Retains base class signature."""
        super().__init__(config, work_dir)

    def _build_cmd(self, command_line: list[str]) -> list[str]:
        """
        RETURN: List[str], the unmodified command line with no isolation wrappers applied.

        Returns exact target payload. No wrappers, no limits.
        """
        return command_line
