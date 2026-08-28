#! /usr/bin/env python3
#
# @hwut {
#     title      = "Orchestrator: the report stream of a run"
#     choices    = ["broken", "empty", "frame", "stream"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE OUTER FACE -- 'orchestrator(root, wish, ...)': the report
         stream of a whole run, event by event, and the summary folded
         from it.

The dispatcher is a TICK DISPATCHER (no process, no wall time); the
clock is stated ('T01', 'T02', ...): the stream is byte-blessable.

CHOICES: stream, broken, frame, empty;

DESCRIPTION:

stream   two directories, everything stands: the full event stream as
         JSON lines, then the folded summary.

broken   a build breaks: its own 'run-ended  verdict=build-failed',
         one 'verdict=unsupported  cause=...' per test it fails, the
         [MISDEP] case's 'run-ended' -- everything that leads to
         executability reported as the test it is (O-3).

frame    'on_entry' fails in one directory: nothing dispatched there,
         'on_exit' still runs, the other directory unaffected.

empty    a wish matching nothing anywhere: 'report' events, empty
         plans, 'tree-done  good=true'.
______________________________________________________________________________
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.plan.wish          import Wish
from vut.language_support.python.script_runner import tree_boundary  # noqa: E402
from vut.engine.orchestrator.run.orchestrate    import orchestrator
from vut.engine.orchestrator.run.summary        import fold
from vut.engine.orchestrator.scheduler.scheduler import I_Dispatcher


class TickDispatcher(I_Dispatcher):
    """One tick of nothing per piece of work; the answer is what
    'verdict_db' states, True where it states nothing."""

    def __init__(self, verdict_db=None):
        """RETURN: TickDispatcher over 'verdict_db': node name or
        script role -> the answer."""
        self.verdict_db = verdict_db or {}

    async def _answer(self, key):
        """RETURN: bool, the stated answer after one tick."""
        await asyncio.sleep(0)
        return self.verdict_db.get(key, True)

    async def run_script(self, role, command):
        """RETURN: bool, the frame script's stated answer."""
        return await self._answer(role)

    async def run_build(self, node):
        """RETURN: bool, the build's stated answer."""
        return await self._answer(node.name())

    async def open_session(self, node):
        """RETURN: bool, the launch's stated answer."""
        return await self._answer(node.name())

    async def close_session(self, node):
        """RETURN: None."""

    async def run_test(self, node):
        """RETURN: bool, the verdict's stated answer."""
        return await self._answer(node.name())





def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def tree_of(file_db):
    """
    RETURN: str, the root of a tree holding 'file_db' (relative path
            -> content), for the caller to remove.
    """
    root = tempfile.mkdtemp(prefix="vut_orch_")
    #  THE TREE'S BOUNDARY: the climb stops here; a tree without
    #  a 'hwut-root.conf' above it is refused.
    tree_boundary(root)
    for relative, content in file_db.items():
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as _fh:
            _fh.write(content)
    return root


def clock_of():
    """RETURN: callable, a stated clock: 'T01', 'T02', ..."""
    count = [0]
    def clock():
        count[0] += 1
        return "T%02d" % count[0]
    return clock


def run(root, wish, verdict_db=None):
    """
    RETURN: list[dict|None], the whole stream of one run, the closing
            'None' included.
    """
    async def main():
        queue = orchestrator(root, wish,
                             lambda directory, entry:
                                 TickDispatcher(verdict_db),
                             worker_max_n=1, clock=clock_of())
        event_list = []
        while True:
            item = await queue.get()
            event_list.append(item)
            if item is None: return event_list
    return asyncio.run(main())


def show(event_list):
    """RETURN: None. Every event as one sorted JSON line; the closing
    'None' shown as such."""
    for item in event_list:
        if item is None: print("    None")
        else:            print("    %s" % json.dumps(item,
                                                     sort_keys=True))


def show_summary(event_list):
    """RETURN: None. The fold of the stream."""
    summary = fold(event_list)
    print("    good_f=%s fail_n=%s" % (summary.good_f, summary.fail_n))
    print("    directories: %s" % ", ".join(summary.directory_tuple))
    for key in sorted(summary.failure_db()):
        cause = summary.cause_db.get(key)
        text = "    FAILED %-28s %s" % ("%s %s" % key,
                                          summary.failure_db()[key])
        if cause: text += "  <= %s" % cause
        print(text)


TWO_DIRECTORY_TREE = {
    "alpha/TEST/hwut.conf": 'hwut { on_entry = "prep.sh"\n'
                            '       dependency { "test-b.py" = '
                            '["test-a.py"] } }\n',
    "alpha/TEST/test-a.py": '# @hwut { title = "A"  build = "make" }\n',
    "alpha/TEST/test-b.py": '# @hwut { title = "B" }\n',
    "beta/TEST/test-z.py":  '# @hwut { title = "Z" }\n',
}


def test_stream():
    """RETURN: None. The whole stream, then the fold."""
    root = tree_of(TWO_DIRECTORY_TREE)
    try:
        banner("everything stands")
        event_list = run(root, Wish())
        show(event_list)
        banner("folded")
        show_summary(event_list)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_broken():
    """RETURN: None. A broken build and an unsatisfiable case."""
    root = tree_of(dict(TWO_DIRECTORY_TREE, **{
        "alpha/TEST/hwut.conf":
            'hwut { dependency { "test-b.py" = ["test-a.py"]\n'
            '                    "test-m.py" = ["test-ghost.py"] } }\n',
        "alpha/TEST/test-m.py": '# @hwut { title = "M" }\n'}))
    try:
        banner("build broken; one case unsatisfiable")
        event_list = run(root, Wish(),
                         {"build[make test-a.py]": False})
        show(event_list)
        banner("folded")
        show_summary(event_list)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_frame():
    """RETURN: None. 'on_entry' failing in one directory."""
    root = tree_of(TWO_DIRECTORY_TREE)
    try:
        banner("alpha's frame does not stand; beta runs")
        event_list = run(root, Wish(), {"on_entry": False})
        show(event_list)
        banner("folded")
        show_summary(event_list)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_empty():
    """RETURN: None. A wish matching nothing anywhere."""
    root = tree_of(TWO_DIRECTORY_TREE)
    try:
        banner("a glob matching nothing")
        event_list = run(root, Wish(glob_tuple=("test-*.pt",)))
        show(event_list)
        banner("folded")
        show_summary(event_list)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Orchestrator: the report stream of a run;", {
        "stream": test_stream,
        "broken": test_broken,
        "frame":  test_frame,
        "empty":  test_empty,
    }).run()
