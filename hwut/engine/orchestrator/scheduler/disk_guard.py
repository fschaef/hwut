"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DISK GUARD -- a case starts only where its disk has room for
         it (D-24). ONE guard serves the process, as the disks it watches
         are the host's: every dispatcher of a run asks the same one.

    answer = await HOST_DISK_GUARD.reserve(path, need_mb, floor_mb)
    if answer.granted_f: ... run ...; HOST_DISK_GUARD.release(answer)
    else:                ... not run: answer.text() says why

A DISK IS A FILESYSTEM ('st_dev' of the path). What stands RESERVED on it
is the sum of the needs of the cases running there. A case may start
where

    free - reserved  >=  floor + need

and 'need' is the caller's word: 'max(2 x disk_mb, the last peak this
machine observed)'. Where it may not start and something stands reserved
on its disk, it WAITS: a running case ends and gives its reservation
back. Where nothing stands reserved, nothing will come free by waiting,
and the answer is a refusal with its numbers.

THE RESERVATION IS PESSIMISTIC. A running case has already spent part of
what it reserved, and the free space shows it; counted twice, the guard
delays a start it might have allowed. It never admits one it should not.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CDiskAnswer:
    """What the guard said to one request."""
    granted_f: bool
    device:    object        # 'st_dev' of the path; None where unknown
    need_mb:   float
    floor_mb:  float
    free_mb:   float | None  # what stood free when it was decided
    mount:     str = ""      # the path the decision was taken for

    def text(self):
        """
        RETURN: str, the refusal's numbers, e.g. 'free 180 MB on /work;
                needs 200 MB above the floor of 128 MB'.
        """
        return ("free %.0f MB on %s; needs %.0f MB above the floor of "
                "%.0f MB" % (self.free_mb or 0.0, self.mount,
                             self.need_mb, self.floor_mb))


def free_mb_of(path):
    """
    RETURN: float, free megabytes on the filesystem holding 'path'.
            None, where it cannot be measured.
    """
    try:
        return shutil.disk_usage(path).free / (1024.0 * 1024.0)
    except OSError:
        return None


class CDiskGuard:
    """The reservations standing on each disk of this host."""

    def __init__(self, free_mb_f=None):
        """
        RETURN: CDiskGuard, nothing reserved. 'free_mb_f(path)' measures
                a disk's free megabytes; 'free_mb_of' where None (a test
                hands in its own).
        """
        self.free_mb_f     = free_mb_f or free_mb_of
        self.held_db       = {}                    # device -> MB reserved
        self._waiter_list  = []

    def reserved_mb(self, device):
        """RETURN: float, what stands reserved on 'device'."""
        return self.held_db.get(device, 0.0)

    async def reserve(self, path, need_mb, floor_mb):
        """
        RETURN: CDiskAnswer -- granted (and 'need_mb' held on the disk of
                'path' until 'release') where the disk has room for it;
                refused where it has not and nothing stands reserved
                there whose ending could make room. Waits in between.

        A disk that cannot be measured grants: the guard holds back only
        on what it can see.
        """
        try:    device = os.stat(path).st_dev
        except  OSError: device = None
        while True:
            free = self.free_mb_f(path)
            held = self.reserved_mb(device)
            if free is None or device is None \
               or free - held >= floor_mb + need_mb:
                self.held_db[device] = held + need_mb
                return CDiskAnswer(True, device, need_mb, floor_mb, free,
                                   str(path))
            if held <= 0.0:
                return CDiskAnswer(False, device, need_mb, floor_mb, free,
                                   str(path))
            future = asyncio.get_running_loop().create_future()
            self._waiter_list.append(future)
            await future

    def release(self, answer):
        """
        RETURN: None. The reservation 'answer' holds is given back; every
                waiter asks again. A refused answer holds nothing.
        """
        if not answer.granted_f: return
        left = self.reserved_mb(answer.device) - answer.need_mb
        if left > 1e-9: self.held_db[answer.device] = left
        else:           self.held_db.pop(answer.device, None)
        waiter_list, self._waiter_list = self._waiter_list, []
        for future in waiter_list:
            if not future.done(): future.set_result(None)


#  THE HOST'S ONE GUARD: the disks are the host's, not a directory's.
HOST_DISK_GUARD = CDiskGuard()
