import os
from   typing import List, Optional
from   pathlib import Path


def get(path_env:  Optional[str]       = "", 
        whitelist: Optional[List[str]] = None) -> List[str]:
    """
    RETURN: List[str], sorted absolute paths of all security-risk executables.

    Scans the default system binary directories plus any valid directories
    found in path_env, and collects every executable considered a sandbox
    security risk (matched by known-dangerous name, SUID/SGID bit, or sbin
    executable status). Entries whose name or absolute path appear in
    whitelist are excluded from the result.
    """
    whitelist_set = set(whitelist or [])

    search_dirs = set(_DEFAULT_SEARCH_DIRS)
    search_dirs.update(p for p in path_env.split(os.pathsep) if os.path.isdir(p))

    forbidden = set()
    for sbin_flag, entry in __get_concerned_files(search_dirs):
        if entry.name in whitelist_set or entry.path in whitelist_set:
            continue
        elif entry.is_file() and __is_security_risk(entry, sbin_flag):
            forbidden.add(entry.path)
            
    return sorted(list(forbidden))


# Immutable defaults — never mutated, so safe to share across calls and tests.
_DEFAULT_SEARCH_DIRS = frozenset({
    "/bin", "/usr/bin", "/usr/local/bin", "/sbin", "/usr/sbin"
})

_RISK_KEYWORDS = frozenset({
    "ssh", "scp", "sftp", "ftp", "nc", "netcat", "curl", "wget", "telnet", "nmap",
    "ip", "ifconfig", "route", "netstat", "ss", "dig", "nslookup", "rlogin", "login",
    "sudo", "su", "pkexec", "chmod", "chown", "mount", "umount", "passwd", "visudo",
    "shutdown", "reboot", "halt", "poweroff", "fdisk", "parted", "mkfs",
    "gdb", "strace", "ltrace", "objdump", "readelf", "nm", "kill", "pkill", "top", "htop",
    "socat", "traceroute"
})


def __is_security_risk(entry: os.DirEntry, is_sbin: bool) -> bool:
    """
    RETURN: True,  if the entry matches one of the three criteria
            False, else.

    Executables raising PermissionError / OSError on stat() are not treated as
    risky, because they cannot be executed in practice.

    Classifies a single filesystem entry as a security risk by checking three
    independent criteria in order: name matches a known-dangerous tool
    (exact or "<keyword>.<ext>" form), SUID/SGID bit is set, or any
    executable bit is set while the entry resides in an sbin directory.
    """
    if any(k == entry.name or entry.name.startswith(k + ".") for k in _RISK_KEYWORDS):
        return True
    try:
        stat = entry.stat()
        return bool((stat.st_mode & 0o6000) or (is_sbin and (stat.st_mode & 0o111)))
    except (PermissionError, OSError):
        return False


def __get_concerned_files(directory_set):
    """
    YIELD: [0] bool        sbin-flag
           [1] os.DirEntry concerned path found in 'directory_set'

    Iterates over every filesystem entry in each directory in directory_set and
    yields it together with a boolean indicating whether its parent directory is
    an sbin directory ('sbin' appears as a path component).
    Directories raising PermissionError or FileNotFoundError are silently skipped.
    """
    for directory in directory_set:
        is_sbin = 'sbin' in Path(directory).parts
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    yield is_sbin, entry
        except (PermissionError, FileNotFoundError):
            continue
