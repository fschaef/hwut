#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: END TO END -- 'orchestrator(root, wish, ...)' over the REAL
         dispatcher: real bash processes under procsitter, a real make,
         a real pype filter; the report stream held against the
         vocabulary, byte for byte.

The FIXTURE TREE provokes every verdict the wire knows:

    test-ok.sh          matches its GOOD                -> ok
    test-diff.sh        differs from its GOOD           -> test-failed
                                                           + report
    test-built.c  make  Makefile target broken          -> build-failed
        + its test      never dispatched                -> unsupported,
                                                           cause named
    test-noise.sh       noisy stdout, pype strips it    -> ok IFF the
                        pype RAN (the verdict is the proof)
    test-m.sh           depends on a file that is not   -> misdep
                        there
    test-app.sh         INTERACTIVE, choices a and b:      one SESSION
                        the standing process serves both   + ok per
                        over the stdin/stdout protocol     choice
    test-dead.sh        INTERACTIVE, dies before the    -> test-failed,
                        protocol; its choice never runs    report names
                                                           the fall

CHOICES: stream, frame, nostore;

DESCRIPTION:

stream   the whole fixture under one wish: the full event stream as
         JSON lines, then the fold. Deterministic: stated clock,
         worker bound 1, root-relative paths.

frame    'on_entry' fails: nothing dispatched, 'on_exit' still runs.

nostore  the store knob (n-1): record=False -- the same run, and the
         store holds NO candidate afterwards; record=None (default)
         stores every subject beside its freshness sidecar.
______________________________________________________________________________
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.plan.wish       import Wish
from vut.engine.orchestrator.run.orchestrate import orchestrator
from vut.engine.orchestrator.run.dispatcher  import \
                                             test_run_dispatcher_factory
from vut.engine.orchestrator.run.summary     import fold


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def fixture(entry_command="true"):
    """
    RETURN: str, the root of the fixture tree described above, for the
            caller to remove. 'entry_command' is what 'on_entry' runs.
    """
    root = tempfile.mkdtemp(prefix="vut_e2e_")
    test = os.path.join(root, "suite", "TEST")
    good = os.path.join(test, "GOOD")
    os.makedirs(good)

    def put(directory, name, content, executable=False):
        path = os.path.join(directory, name)
        with open(path, "w") as fh: fh.write(content)
        if executable: os.chmod(path, 0o755)

    put(test, "hwut.conf",
        'hwut {\n'
        '    ignore   = ["Makefile", "strip_noise.py"]\n'
        '    on_entry = "%s"\n'
        '    on_exit  = "true"\n'
        '    dependency { "test-m.sh" = ["required.dat"] }\n'
        '}\n' % entry_command)
    put(test, "test-ok.sh",
        '#!/bin/bash\n'
        '# hwut { title = "Ok" }\n'
        'echo "steady line"\n', executable=True)
    put(good, "test-ok.stdout",    "steady line\n")
    put(test, "test-diff.sh",
        '#!/bin/bash\n'
        '# hwut { title = "Diff" }\n'
        'echo "what the run says"\n', executable=True)
    put(good, "test-diff.stdout",  "what the GOOD expects\n")
    put(test, "test-built.c",
        '/* hwut { title = "Built"\n'
        '          build { framework = "make"'
        '                  executable = "app" } } */\n')
    put(test, "Makefile",
        'app:\n\tfalse\n')
    put(test, "test-noise.sh",
        '#!/bin/bash\n'
        '# hwut { title = "Noise"\n'
        '#        pype  = "python3 strip_noise.py" }\n'
        'echo "NOISE-1234 kept line"\n', executable=True)
    put(test, "strip_noise.py",
        'import re, sys\n'
        'for line in sys.stdin:\n'
        '    sys.stdout.write(re.sub(r"NOISE-\\d+ ", "", line))\n')
    put(good, "test-noise.stdout", "kept line\n")
    put(test, "test-app.sh",
        '#!/bin/bash\n'
        '# hwut { title = "App"  interactive = yes\n'
        '#        choices = ["a", "b"] }\n'
        'while read cmd token out err; do\n'
        '    [ "$cmd" = run ] || continue\n'
        '    echo "choice $token served" > "$out"\n'
        '    : > "$err"\n'
        '    echo "done $token 0"\n'
        'done\n'
        'echo bye\n', executable=True)
    put(good, "test-app--a.stdout", "choice a served\n")
    put(good, "test-app--b.stdout", "choice b served\n")
    put(test, "test-dead.sh",
        '#!/bin/bash\n'
        '# hwut { title = "Dead"  interactive = yes\n'
        '#        choices = ["x"] }\n'
        'exit 7\n', executable=True)
    put(good, "test-dead--x.stdout", "never\n")
    put(test, "test-m.sh",
        '#!/bin/bash\n'
        '# hwut { title = "Misdep" }\n'
        'echo never\n', executable=True)
    return root


def run(root, record=None):
    """
    RETURN: list[dict|None], the whole stream of one run over the REAL
            dispatcher, the closing 'None' included.
    """
    count = [0]
    def clock():
        count[0] += 1
        return "T%02d" % count[0]

    async def main():
        queue = orchestrator(root, Wish(),
                             test_run_dispatcher_factory(record=record),
                             worker_max_n=1, clock=clock)
        event_list = []
        while True:
            item = await queue.get()
            event_list.append(item)
            if item is None: return event_list
    return asyncio.run(main())


def show(event_list):
    """RETURN: None. Every event as one sorted JSON line."""
    for item in event_list:
        if item is None: print("    None")
        else:            print("    %s" % json.dumps(item,
                                                     sort_keys=True))


def test_stream():
    """RETURN: None. The whole wire over real processes."""
    root = fixture()
    try:
        event_list = run(root)
        banner("the stream")
        show(event_list)
        summary = fold(event_list)
        banner("folded")
        print("    good_f=%s fail_n=%s" % (summary.good_f,
                                           summary.fail_n))
        for key in sorted(summary.failure_db()):
            cause = summary.cause_db.get(key)
            text = "    FAILED %-28s %s" % ("%s %s" % key,
                                            summary.failure_db()[key])
            if cause: text += "  <= %s" % cause
            print(text)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_frame():
    """RETURN: None. A broken 'on_entry': nothing dispatched."""
    root = fixture(entry_command="false")
    try:
        event_list = run(root)
        banner("the stream")
        show(event_list)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_nostore():
    """RETURN: None. The store knob, both positions."""
    def candidate_count(root):
        store_dir = os.path.join(root, "suite", "TEST")
        count = 0
        for base, _dirs, files in os.walk(store_dir):
            count += sum(1 for name in files
                         if base != os.path.join(store_dir, "GOOD")
                         and name.endswith((".stdout",)))
        return count

    banner("record=False: the store stays empty")
    root = fixture()
    try:
        run(root, record=False)
        print("    candidates after the run: %d" % candidate_count(root))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    banner("record default: every subject stored, sidecar beside it")
    root = fixture()
    try:
        run(root)
        n_candidate = candidate_count(root)
        n_sidecar   = 0
        for base, _dirs, files in os.walk(os.path.join(root, "suite")):
            n_sidecar += sum(1 for name in files
                             if name.endswith(".when"))
        print("    candidates: %d   freshness sidecars: %d"
              % (n_candidate, n_sidecar))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "End to end: the wire over real processes;", {
        "stream":  test_stream,
        "frame":   test_frame,
        "nostore": test_nostore,
    }).run()
