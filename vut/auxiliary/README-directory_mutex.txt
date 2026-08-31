==============================================================================
directory_mutex -- MUTUAL EXCLUSION OVER ONE DIRECTORY, BETWEEN PROCESSES
==============================================================================

    from vut.auxiliary.directory_mutex import MkdirMutex, DirectoryBusy

    with MkdirMutex(directory):
        ...                          # the directory admits one live holder


1  THE MECHANISM
______________________________________________________________________________

'mkdir' of a lock sub directory ('TMP/lock') decides the winner: it
creates or it fails, never half. Inside, the holder is recorded:

    holder.json    { "pid":      the holder's process id,
                     "started":  when that process started,
                     "acquired": when the lock was taken }

The pair (pid, started) identifies the holder. 'acquired' feeds
'holder_age_sec()'. A record without 'acquired' answers age None.

A lock whose recorded holder no longer exists is broken and re-taken.
Liveness is asked from the system, never inferred from elapsed time.
Where the platform reports no process start times, no lock is taken and
'.taken' says so.


2  THE INTERFACE
______________________________________________________________________________

    MkdirMutex(directory,
               lock_directory_name = "TMP/lock",
               wait_sec            = 0.0,
               poll_sec            = 0.05,
               max_hold_sec        = None)

    with mutex: ...        acquire on entry, release on exit; a foreign
                           live holder raises 'DirectoryBusy'
    acquire()  -> bool     True: held. False: a foreign live holder
                           stands (still, after 'wait_sec' of polling)
    release()              removes this process's lock; idempotent
    holder()   -> dict     the recorded holder, or None
    holder_age_sec()       seconds since acquisition, or None
    .taken     -> bool     whether this instance holds

NON-RECURSIVE. One lock site per holder. The live holder acquiring its
own directory again raises 'DirectoryDeadlock', a 'DirectoryBusy'.

POLICIES, both off by default:

    wait_sec       > 0: a contender polls a foreign live holder until
                   the deadline, then reports busy. 0: busy at once.
    max_hold_sec   set: a live holder whose 'acquired' lies further
                   back is treated as gone and its lock broken.
                   None: liveness alone decides.


3  USERS
______________________________________________________________________________

test_run's 'DirectoryLock' (vut/engine/test_run/store.py) is the face of
this class inside that component; 'Store.lock()' hands it out.
