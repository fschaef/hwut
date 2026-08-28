"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       MUTUAL EXCLUSION over ONE directory, between PROCESSES.

DESCRIPTION
       'MkdirMutex' guards a directory: the lock is placed when access
       to the resource is required and removed when the access is
       released. 'mkdir' of a lock sub directory decides the winner --
       it creates or it fails, never half, so no second mechanism is
       needed.

       THE STATE IS A FILE. Inside the lock sub directory the holder is
       recorded as

           { "pid":      the holder's process id,
             "started":  when that process started,
             "acquired": when the lock was taken }

       The PAIR (pid, started) identifies the holder -- a process id
       alone does not, since the system reuses them. 'acquired' makes
       the mutex HOLDER-TIME-AWARE: 'holder_age_sec()' answers how long
       the lock has been held. A holder file without 'acquired' (written
       by an earlier hand) answers None -- absence is data.

       LIVENESS IS ASKED, NOT INFERRED. A lock whose recorded holder no
       longer exists is broken and re-taken: no expiry, no heart beat,
       no clock skew, and a crashed holder leaves no lock behind it.
       Where the platform cannot report process start times, no lock is
       taken at all and '.taken' says so -- the reduced capability is
       REPORTED, never pretended to.

       NON-RECURSIVE. A mutex has ONE lock site per holder: the holder
       that locks again has lost track of its own critical section.
       Re-acquisition by the live holder itself raises
       'DirectoryDeadlock' -- named at once, never waited out.

       TWO OPTIONAL POLICIES, both OFF by default:

           wait_sec       > 0: a contender polls until the deadline
                          before reporting busy. Default 0: busy is
                          reported immediately, never queued.
           max_hold_sec   set: a LIVE holder whose 'acquired' lies
                          further back is treated as gone and its lock
                          broken. Default None: liveness alone decides.
______________________________________________________________________________
"""
import json
import os
import time
from   pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


LOCK_DIRECTORY_NAME = ".hwut-lock"
_HOLDER_FILE_NAME   = "holder.json"


def _process_start_time(pid):
    """
    RETURN: float, when process 'pid' started, as a POSIX timestamp.
            None,  the pair cannot be had on this platform, or no such
                   process exists.

    The pair (pid, start time) is what identifies a process: a process id
    alone does not, since the system reuses them.
    """
    if psutil is not None:
        try:
            return psutil.Process(pid).create_time()
        except Exception:
            return None
    try:                                              # Linux, no psutil
        with open("/proc/%i/stat" % pid, "rb") as fh:
            field_list = fh.read().rpartition(b")")[2].split()
        ticks = float(field_list[19])
        with open("/proc/uptime", "r") as fh:
            uptime = float(fh.read().split()[0])
        return time.time() - uptime + ticks / os.sysconf("SC_CLK_TCK")
    except Exception:
        return None


def liveness_can_be_asked():
    """
    RETURN: True,  this platform reports when a process started.
            False, it does not -- so no lock is taken at all.

    A system that cannot report a start time cannot support concurrent
    holders. The reduced capability is REPORTED, never pretended to.
    """
    return _process_start_time(os.getpid()) is not None


class DirectoryBusy(RuntimeError):
    """Another LIVE process holds this directory. Raised rather than
    waited out: a caller that wants to queue can decide that for
    itself."""
    pass


class DirectoryDeadlock(DirectoryBusy):
    """The LIVE holder of this directory is the acquiring process
    itself. The mutex is non-recursive: one lock site per holder, and a
    holder locking again has lost track of its own critical section.
    Named at once, never waited out."""
    pass


class MkdirMutex:
    """Mutual exclusion over one directory, between processes.

    Use as a context manager. Where liveness cannot be asked, the mutex
    is a no-op and '.taken' says so.
    """

    def __init__(self, directory, lock_directory_name=LOCK_DIRECTORY_NAME,
                 wait_sec=0.0, poll_sec=0.05, max_hold_sec=None):
        """
        RETURN: MkdirMutex, not yet acquired.

        'directory'            the resource.
        'lock_directory_name'  name of the lock sub directory.
        'wait_sec'             how long a contender polls a foreign live
                               holder before reporting busy; 0: at once.
        'poll_sec'             the polling interval of that wait.
        'max_hold_sec'         set: a live holder held longer than this
                               is treated as gone; None: liveness alone
                               decides.
        """
        self.directory    = Path(directory)
        self.path         = self.directory / lock_directory_name
        self.wait_sec     = wait_sec
        self.poll_sec     = poll_sec
        self.max_hold_sec = max_hold_sec
        self.taken        = False

    def holder(self):
        """
        RETURN: dict, the recorded holder {'pid', 'started'[, 'acquired']}.
                None, no holder is recorded or it cannot be read.
        """
        try:
            with open(self.path / _HOLDER_FILE_NAME, "r") as fh:
                return json.load(fh)
        except Exception:
            return None

    def holder_age_sec(self):
        """
        RETURN: float, seconds since the recorded holder acquired.
                None,  no holder is recorded, or its record carries no
                       acquisition time -- absence is data, never zero.
        """
        holder = self.holder()
        if holder is None:               return None
        if "acquired" not in holder:     return None
        return time.time() - holder["acquired"]

    def _held_by_self(self, holder):
        """
        RETURN: True,  the recorded holder is THIS process.
                False, else.
        """
        if holder is None:                        return False
        if holder.get("pid", -1) != os.getpid():  return False
        started = _process_start_time(os.getpid())
        if started is None:                       return False
        return abs(started - holder.get("started", 0.0)) <= 1.0

    def _holder_is_gone(self, holder):
        """
        RETURN: True,  no process of that id started at that time exists
                       -- or, with 'max_hold_sec' set, the live holder
                       has held longer than allowed. The recorded holder
                       is gone.
                False, the holder is alive within its allowance, or the
                       question cannot be answered -- in which case the
                       lock STANDS.

        Never infers death from elapsed time, unless 'max_hold_sec'
        asked for exactly that.
        """
        if holder is None: return True            # a lock naming nobody
        started = _process_start_time(holder.get("pid", -1))
        if started is None: return True            # no such process
        recorded = holder.get("started")
        if recorded is None:
            #  A LOCK THAT CANNOT NAME ITS HOLDER IS NOT A CLAIM, and
            #  it is GONE. A record without a start time -- an older
            #  version's, a half-written one, a hand-edited one --
            #  cannot be compared against any process, so no future
            #  run and no cleaning could ever break it: it would block
            #  the directory for ever.
            #
            #  THE SAME ANSWER A MISSING RECORD ALREADY GETS, two
            #  lines above. An unreadable claim and an absent one are
            #  the same claim.
            #
            #  NOTE the narrow window this shares with the absent
            #  case: 'acquire' makes the directory and THEN writes the
            #  record, so a live holder is briefly unnameable. That
            #  race predates this line and is answered where it
            #  belongs -- 'acquire' retries, up to 'attempt_max'.
            return True
        try:
            if abs(started - recorded) > 1.0: return True
        except TypeError:
            #  A RECORD OF THE WRONG SHAPE, for the same reason: it
            #  cannot be compared, so it cannot be honoured.
            return True
        if self.max_hold_sec is not None:
            age = self.holder_age_sec()
            if age is not None and age > self.max_hold_sec: return True
        return False

    def acquire(self, attempt_max=3):
        """
        RETURN: True,  the mutex is held by this process.
                False, another live process holds it (still, after
                       'wait_sec' of polling).

        Raises DirectoryDeadlock when the live holder is this process
        itself -- the mutex is non-recursive.

        'mkdir' decides the winner: it creates or it fails, never half.
        A stale lock -- one whose holder is gone -- is removed and the
        attempt repeated, at most 'attempt_max' times. A loser of that
        race simply fails its next 'mkdir', so removal needs no
        agreement between removers.
        """
        if not liveness_can_be_asked():
            self.taken = False
            return True                            # no lock on this platform
        deadline = time.monotonic() + self.wait_sec
        attempt_n = 0
        while True:
            try:
                self.path.mkdir(parents=True)
            except FileExistsError:
                holder = self.holder()
                if self._holder_is_gone(holder):
                    attempt_n += 1
                    if attempt_n > attempt_max: return False
                    self._break()
                    continue
                if self._held_by_self(holder):
                    raise DirectoryDeadlock(
                        "directory '%s' is already held by this very "
                        "process" % self.directory)
                if time.monotonic() < deadline:
                    time.sleep(self.poll_sec)
                    continue
                return False
            with open(self.path / _HOLDER_FILE_NAME, "w") as fh:
                json.dump({"pid":      os.getpid(),
                           "started":  _process_start_time(os.getpid()),
                           "acquired": time.time()}, fh)
            self.taken = True
            return True

    def _break(self):
        """RETURN: None. Removes a lock whose holder is gone."""
        try:
            (self.path / _HOLDER_FILE_NAME).unlink()
        except OSError:
            pass
        try:
            self.path.rmdir()
        except OSError:
            pass

    def release(self):
        """RETURN: None. Removes this process's lock. Idempotent."""
        if not self.taken: return
        self._break()
        self.taken = False

    def __enter__(self):
        """
        RETURN: self, with the mutex held.

        Raises DirectoryBusy when another live process holds it, and
        DirectoryDeadlock when that live process is this one. This is
        THE way to take the mutex -- 'acquire'/'release' exist for it,
        and a caller that used them directly would have to repeat the
        release in a 'finally' of its own.
        """
        if not self.acquire():
            raise DirectoryBusy("test directory '%s' is held by a live "
                                "process" % self.directory)
        return self

    def __exit__(self, *_):
        """RETURN: False, exceptions propagate."""
        self.release()
        return False
