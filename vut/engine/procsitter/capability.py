"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CAPABILITY BOARD -- what the procsitter CAN watch on the
         platform it stands on, announced BEFORE any call is made.

A cap that does not cap is worse than no cap (exploration R-48). Who
decides what follows from an incapability is not the procsitter: it
ANNOUNCES, and the level above compares the announcement with what the
selected tests require (exploration R-80).

    platform_name()    the platform's word, as a configuration names it
    capability_db()    cap -> can it be watched here
    UTILITY_DB         platform -> utility -> the caps it watches
    utility_of()       the utility a cap's watching rests on
    INSTALL_DB         utility -> how it comes onto a machine

THE CAPS ARE NAMED AS 'ProcsitterConfig' NAMES THEM. Three stand on the
board WITHOUT a field: 'network', 'file_handle_max_n' and
'write_directory_list' are words a test may state and nothing here
enforces, on any platform. The board says so by name, so that the
answer to "is this confined?" has ONE source.
______________________________________________________________________________
"""
import sys

try:                import resource as _resource
except ImportError: _resource = None     # e.g. Windows

try:                import psutil as _psutil
except ImportError: _psutil = None       # degradable, announced

#  Caps a test may state and the procsitter enforces NOWHERE.
UNFIELDED_CAP_TUPLE = ("file_handle_max_n", "network",
                       "write_directory_list")


def platform_name():
    """
    RETURN: str, the platform as a configuration names it: 'linux',
            'darwin', 'windows', else 'sys.platform' without its
            version digits ('freebsd13' -> 'freebsd').
    """
    name = sys.platform
    if name in ("win32", "cygwin", "msys"): return "windows"
    return name.rstrip("0123456789")


#  WHAT THE WATCHING RESTS ON: platform -> utility -> the caps it
#  watches. 'None' is every platform not named. A cap under no utility
#  of its platform is watched by the procsitter alone, or -- the
#  unfielded three -- by nothing. 'resource' is the POSIX standard
#  library's and does not exist on Windows: no entry, nothing to install.
UTILITY_DB = {
    None:      {"psutil":   ("max_memory_mb", "max_pids"),
                "resource": ("max_cpu_time_sec", "max_file_size_mb")},
    "windows": {"psutil":   ("max_memory_mb", "max_pids")},
}

#  Utility -> how it comes onto a machine; absent where it cannot.
INSTALL_DB = {"psutil": "pip install psutil"}

#  Caps a utility watches SOMEWHERE: off its platforms nothing does.
_UTILITY_CAP_SET = frozenset(name for db in UTILITY_DB.values()
                             for cap_tuple in db.values()
                             for name in cap_tuple)


def utility_of(cap, platform=None):
    """
    RETURN: str, the utility the watching of 'cap' rests on, on
                 'platform' (this one where None): 'psutil', 'resource'
            None, where no utility is needed there -- or none helps.
    """
    if platform is None: platform = platform_name()
    for utility, cap_tuple in UTILITY_DB.get(platform,
                                             UTILITY_DB[None]).items():
        if cap in cap_tuple: return utility
    return None


def capability_db(psutil_f=None, resource_f=None, platform=None):
    """
    RETURN: dict[str, bool], cap name -> True where the procsitter can
            watch it on this platform, False where the cap would stand
            unenforced.

    'psutil_f', 'resource_f' say whether the two modules the watching
    rests on are present; None asks this platform itself. 'platform'
    names the platform whose row of 'UTILITY_DB' is read; this one
    where None.
    """
    if psutil_f   is None: psutil_f   = _psutil   is not None
    if resource_f is None: resource_f = _resource is not None
    present_db = {"psutil": psutil_f, "resource": resource_f}
    board = {}
    for name in ("max_wall_clock_sec", "max_cpu_time_sec", "max_memory_mb",
                 "max_pids", "max_file_size_mb", "max_disk_mb",
                 "max_output_gap_sec", "min_free_disk_mb"):
        utility = utility_of(name, platform)
        if utility is not None: board[name] = present_db[utility]
        else:                   board[name] = name not in _UTILITY_CAP_SET
    board.update((name, False) for name in UNFIELDED_CAP_TUPLE)
    return board
