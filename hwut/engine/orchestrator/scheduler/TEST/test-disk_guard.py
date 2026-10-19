#! /usr/bin/env python3
#
# @hwut {
#     title      = "Disk guard: room before a start, a wait, a refusal"
#     choices {
#         room    { features = ["disk-room-before-start"] }
#         wait    { features = ["disk-room-before-start"] }
#         refused { features = ["disk-room-before-start"] }
#     }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DISK GUARD (D-24) -- a case starts where its disk has room
         for it above the floor, waits where a running case may make
         room, and is refused where none can.

CHOICES: room, wait, refused;

DESCRIPTION:

room     two cases on one disk of 1000 MB free, floor 128, need 200
         each: both granted; a third needing 700 waits until both
         have ended.

wait     a case short of room waits; the running one ends and gives its
         reservation back; the waiter is granted.

refused  nothing stands reserved and the disk is short: refused at once,
         with its numbers.

The free space is a number handed in: what stands on this machine's
disk has no business in a nominal.
______________________________________________________________________________
"""
import asyncio
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from hwut.engine.orchestrator.scheduler.disk_guard import CDiskGuard


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def said(answer):
    """RETURN: str, an answer as a line: granted, or refused and why."""
    if answer.granted_f: return "granted %.0f MB" % answer.need_mb
    return "REFUSED: " + answer.text().replace(answer.mount, "<disk>")


def test_room():
    """RETURN: None. Two fit; a third is short while they stand."""
    async def body(path):
        guard = CDiskGuard(lambda p: 1000.0)
        a = await guard.reserve(path, 200.0, 128.0)
        b = await guard.reserve(path, 200.0, 128.0)
        print("    a: %s" % said(a))
        print("    b: %s" % said(b))
        print("    reserved: %.0f MB" % guard.reserved_mb(a.device))
        third = asyncio.ensure_future(guard.reserve(path, 700.0, 128.0))
        await asyncio.sleep(0.05)
        print("    c (700 MB) while a, b stand: %s"
              % ("waits" if not third.done() else said(third.result())))
        guard.release(a)
        await asyncio.sleep(0.05)
        print("    c after a ends: %s"
              % ("waits" if not third.done() else said(third.result())))
        guard.release(b)
        c = await third
        print("    c after b ends: %s" % said(c))
        guard.release(c)
        print("    reserved: %.0f MB" % guard.reserved_mb(a.device))
    banner("1000 MB free, floor 128")
    with tempfile.TemporaryDirectory() as path: asyncio.run(body(path))


def test_wait():
    """RETURN: None. The waiter is granted when the runner ends."""
    async def body(path):
        guard = CDiskGuard(lambda p: 400.0)
        first  = await guard.reserve(path, 200.0, 128.0)
        print("    first:  %s" % said(first))
        second = asyncio.ensure_future(guard.reserve(path, 200.0, 128.0))
        await asyncio.sleep(0.05)
        print("    second: %s" % ("waits" if not second.done() else "?"))
        guard.release(first)
        print("    second: %s" % said(await second))
    banner("400 MB free, floor 128, need 200 each")
    with tempfile.TemporaryDirectory() as path: asyncio.run(body(path))


def test_refused():
    """RETURN: None. Nothing to wait for: refused, with numbers."""
    async def body(path):
        guard = CDiskGuard(lambda p: 180.0)
        answer = await guard.reserve(path, 200.0, 128.0)
        print("    %s" % said(answer))
        print("    reserved: %.0f MB" % guard.reserved_mb(answer.device))
        guard.release(answer)
    banner("180 MB free, floor 128, need 200")
    with tempfile.TemporaryDirectory() as path: asyncio.run(body(path))


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Disk guard: room before a start, a wait, a refusal;", {
        "room":    test_room,
        "wait":    test_wait,
        "refused": test_refused,
    }).run()
