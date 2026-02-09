import os
from   pathlib import Path
from   typing import List, Optional


def get(path_env: Optional[str] = None, 
        whitelist: Optional[List[str]] = None) -> List[str]:
    whitelist_set = set(whitelist or [])
    search_dirs = {"/bin", "/usr/bin", "/usr/local/bin", "/sbin", "/usr/sbin"}
    
    if path_env:
        search_dirs.update(p for p in path_env.split(os.pathsep) if os.path.isdir(p))

    risk_keywords = {
        "ssh", "scp", "sftp", "ftp", "nc", "netcat", "curl", "wget", "telnet", "nmap", 
        "ip", "ifconfig", "route", "netstat", "ss", "dig", "nslookup", "rlogin", "login",
        "sudo", "su", "pkexec", "chmod", "chown", "mount", "umount", "passwd", "visudo",
        "shutdown", "reboot", "halt", "poweroff", "fdisk", "parted", "mkfs",
        "gdb", "strace", "ltrace", "objdump", "readelf", "nm", "kill", "pkill", "top", "htop",
        "socat", "traceroute"
    }

    def is_security_risk(entry: os.DirEntry, is_sbin: bool) -> bool:
        if any(k == entry.name or entry.name.startswith(k + ".") for k in risk_keywords):
            return True
        try:
            stat = entry.stat()
            # Returns True if SUID/SGID is set OR if it's an executable in an sbin directory
            return bool((stat.st_mode & 0o6000) or (is_sbin and (stat.st_mode & 0o111)))
        except (PermissionError, OSError):
            return False

    def concerned_files(dirs):
        for directory in dirs:
            is_sbin = 'sbin' in Path(directory).parts
            try:
                with os.scandir(directory) as it:
                    for entry in it:
                        yield is_sbin, entry
            except (PermissionError, FileNotFoundError):
                continue

    forbidden = set()
    for sbin_flag, entry in concerned_files(search_dirs):
        if entry.name in whitelist_set or entry.path in whitelist_set:
            continue
        if entry.is_file() and is_security_risk(entry, sbin_flag):
            forbidden.add(entry.path)
            
    return sorted(list(forbidden))

