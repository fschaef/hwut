"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE PROCSITTER'S CONFIGURATION -- the per-call contract.

Every member is a CAP the procsitter ENFORCES, or the environment
overlay it hands the call. A call's ENVIRONMENTAL needs -- network
reach, bound ports, writable paths beyond the work dir -- are NOT
here: ensuring them is the ORCHESTRATOR's job (it owns the
environment), ABOVE this level. The procsitter neither records nor
enforces them.
______________________________________________________________________________
"""
from dataclasses import dataclass


@dataclass
class ProcsitterConfig:
    """THE PER-CALL CONTRACT: every field is a CAP the procsitter
    ENFORCES.

    max_wall_clock_sec   the call's total lifetime, from launch to end.
                         Bounds a call that is WORKING.

    max_cpu_time_sec     CPU seconds of the whole process group
                         (RLIMIT_CPU). A call that spins is caught here
                         even where the wall clock has room.

    max_memory_mb        resident set size of the whole process group,
                         watched. Exceeding it ends the call.

    max_pids             processes the call may hold at once
                         (RLIMIT_NPROC): the fork-bomb cap.

    max_file_size_mb     PER FILE (RLIMIT_FSIZE) -- one file the call
                         writes may not grow past this.

    max_disk_mb          TOTAL allocation under the work dir, walked by
                         the watchdog over st_blocks: the many-files
                         loop cap, which a per-file limit cannot catch.

    max_output_gap_sec   SILENCE cap: no output on either production
                         port for this long ends the call. 'None' --
                         the default -- switches it off. Measured from
                         launch, reset by every chunk. Bounds a call
                         that is WAITING, where the wall clock bounds
                         one that is working.

                         SILENCE IS WHAT THE WIRE HEARS, not what the
                         application intends: a BLOCK-BUFFERED call
                         delivers nothing until it ends or its buffer
                         fills, and to this cap it is silent however
                         busy it is. An application that means to be
                         heard flushes.

    min_free_disk_mb     free-space FLOOR of the work dir's filesystem.
                         Below it the call is terminated so the OS
                         stays operable, whoever caused the shortage.

    scratch_dir          THE SCRATCH GROUND of the call: made empty
                         before the spawn and exported as 'TMPDIR' (and
                         'TMP', 'TEMP'), so that what the call creates
                         through the platform's temp-file machinery
                         lands here and is ATTRIBUTABLE to it. Listed
                         after exit: what still stands is the call's
                         leftovers ('ProcsitterResult.created_tuple').
                         'None': the parent's temp ground, unobserved.

    env                  ENVIRONMENT OVERLAY: a dict merged OVER the
                         parent's environment at spawn; 'None' inherits
                         it unchanged. The framework speaks to the
                         application here -- e.g. R-70's
                         'HWUT_NO_TERMINAL', set where a pype owns the
                         stream's terminal token.
    """
    max_wall_clock_sec: float = 300.0
    max_cpu_time_sec:   int   = 300
    max_memory_mb:      int   = 512
    max_pids:           int   = 32
    max_file_size_mb:   int   = 10
    max_disk_mb:        int   = 100
    max_output_gap_sec: float | None = None
    min_free_disk_mb:   int   = 128
    env:                dict  | None = None
    scratch_dir:        str   | None = None
