from .base                   import Sandbox, SandboxConfig
from .sandbox_linux          import SandboxLinux
from .sandbox_none           import SandboxNone
## from .sandbox_bsd            import SandboxBSD
## from .sandbox_free_bsd       import SandboxFreeBSD
## from .sandbox_dragonfly_bsd  import SandboxDragonFlyBSD
## from .sandbox_net_bsd        import SandboxNetBSD
## from .sandbox_mac_os         import SandboxMacOs
## from .sandbox_solaris        import SandboxIllumos
## from .sandbox_unikernel      import SandboxUnikernel
## from .sandbox_redox_os       import SandboxRedoxOs

import sys

def create_sandbox(config: SandboxConfig, work_dir: str) -> Sandbox:
    """Dispatches Sandbox instantiation via a functional lookup database."""
    
    platform_name = sys.platform.lower()

    # The Sandbox Registry Database
    # Format: (Predicate Lambda, Sandbox Class)
    sandbox_db = [
        (lambda p: p.startswith("linux"),                 SandboxLinux),
        ## UNTESTED: 
        ## (lambda p: "darwin" in p,                         SandboxMacOs),
        ## (lambda p: "solaris" in p,                        SandboxIllumos),
        ## (lambda p: "freebsd" in p,                        SandboxFreeBSD),
        ## (lambda p: "netbsd" in p,                         SandboxNetBSD),
        ## (lambda p: "dragonfly" in p,                      SandboxDragonFlyBSD),
        ## (lambda p: "bsd" in p,                            SandboxBSD),
        ## (lambda p: "redox" in p,                          SandboxRedoxOs),
        ## # Unikernel detection usually requires a config flag rather than just OS
        ## (lambda p: getattr(config, 'unikernel_f', False), SandboxUnikernel),
    ]

    for check, cls in sandbox_db:
        if check(platform_name): return cls(config, work_dir)
    return SandboxNone(config, work_dir) # Windows
