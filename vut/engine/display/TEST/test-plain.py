#! /usr/bin/env python3
#
# @hwut {
#     title      = "Tier 1, the plain console report, over scripted streams"
#     choices    = ["allgreen", "badge", "empty", "fault", "mixed",
#                   "tiers", "unknown", "words"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TIER-1 RENDERER over SCRIPTED event streams -- lists of
         dicts through the receiver and the fold; no process runs. The
         'when' instants are SCRIPTED ISO instants, so the clock
         column is byte-exact and no wall clock enters a GOOD.

CHOICES: allgreen, mixed, words, fault, empty, unknown, tiers;

DESCRIPTION:

allgreen  a small tree, everything ok: the flow, the roll-call, no
          FAILURES block.

mixed     two directories, the end-to-end fixture's whole verdict set:
          [SKIP ] for the never-begun (missing dependency, not
          supported), the parallel count rising and falling over
          interleaved runs, phrases inline on the failing lines, the
          cause named, the closing blocks.

words     every report word the operations know, one failing line
          each -- the phrase table read end to end; a word the table
          does not know prints with its hyphens opened.

fault     faults at the tree and in a directory: never swallowed, in
          the flow and counted.

empty     a wish that selects nothing: the note, a directory of zero
          nodes, the roll-call of zeros.

unknown   the stability promise: an UNKNOWN KIND is ignored, an
          UNKNOWN VERDICT reads not-ok, a MISFIT event becomes a
          fault line and the stream walks on.

tiers     one failing stream under VERBOSE, QUIET and SILENT: what
          each adds or drops; SILENT writes nothing to stdout and the
          faults to stderr, prefixed and nicknamed.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.display.plain               import E_Tier, render
from vut.engine.operations.result           import E_TestRunResult
from vut.engine.protocol.vocabulary import event


WIDTH = 78


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def when(second):
    """
    RETURN: str, a scripted ISO-8601 instant, 'second' seconds into
            the stream -- deterministic, so the clock column is too.
    """
    return "2026-08-19T10:%02d:%02d+00:00" % divmod(second, 60)


def show(stream, tier=E_Tier.PLAIN):
    """
    RETURN: None. The stream rendered at width 78, transparent ink;
            stdout lines verbatim, stderr lines marked; the fold's
            closing word after.
    """
    out_list, error_list = [], []
    summary = render(stream, out_list.append, error_list.append,
                     width=WIDTH, colour_f=False, tier=tier)
    for line in out_list:   print(line)
    for line in error_list: print("stderr> %s" % line)
    print("[fold: good_f=%s fail_n=%s verdict_n=%d fault_n=%d]"
          % (summary.good_f, summary.fail_n, len(summary.verdict_db),
             len(summary.fault_tuple)))


def test_allgreen():
    """RETURN: None. Everything ok; no FAILURES block."""
    d = "suite/TEST"
    stream = [
        event("tree-begun", when(0), directory_list=[d]),
        event("dir-begun",  when(0), directory=d, node_n=3),
        event("frame",      when(0), directory=d, role="on_entry",
              good=True),
        event("run-begun",  when(1), directory=d,
              node="session[test-app.sh]", node_kind="SESSION"),
        event("run-ended",  when(2), directory=d,
              node="session[test-app.sh]", node_kind="SESSION",
              good=True, verdict="ok"),
        event("run-begun",  when(2), directory=d, node="test-app.sh a",
              node_kind="TEST"),
        event("run-ended",  when(4), directory=d, node="test-app.sh a",
              node_kind="TEST", good=True, verdict="ok"),
        event("run-begun",  when(4), directory=d, node="test-ok.sh",
              node_kind="TEST"),
        event("run-ended",  when(5), directory=d, node="test-ok.sh",
              node_kind="TEST", good=True, verdict="ok"),
        event("frame",      when(5), directory=d, role="on_exit",
              good=True),
        event("dir-done",   when(5), directory=d, good=True,
              fail_db={}),
        event("tree-done",  when(5), good=True, fail_n=0),
        None,
    ]
    banner("all green")
    show(stream)


def _mixed_stream():
    """
    RETURN: list, the end-to-end fixture's verdict set as a scripted
            stream, a second directory after it -- interleaved starts,
            every failure flavour, the walk order of the wire.
    """
    d1, d2 = "time-stamping-pio-tests/TEST", "compare/TEST"
    return [
        event("tree-begun", when(0), directory_list=[d1, d2]),
        event("fault",      when(0), directory=d1,
              text="hwut.conf:1:7: DIRECTORY: 'dependency' names "
                   "'required.dat', which this directory does not "
                   "offer"),
        event("dir-begun",  when(0), directory=d1, node_n=16),
        event("run-ended",  when(1), directory=d1, node="test-m.sh",
              node_kind="TEST", good=False, verdict="misdep"),
        event("frame",      when(1), directory=d1, role="on_entry",
              good=True),
        event("run-begun",  when(1), directory=d1,
              node="build[make test-built.c]", node_kind="BUILD"),
        event("run-ended",  when(3), directory=d1,
              node="build[make test-built.c]", node_kind="BUILD",
              good=False, verdict="build-failed",
              report="build-failed"),
        event("run-ended",  when(3), directory=d1, node="test-built.c",
              node_kind="TEST", good=False, verdict="unsupported",
              cause="build[make test-built.c]"),
        event("run-begun",  when(3), directory=d1, node="test-app.sh a",
              node_kind="TEST"),
        event("run-begun",  when(4), directory=d1, node="test-app.sh b",
              node_kind="TEST"),
        event("run-ended",  when(5), directory=d1, node="test-app.sh a",
              node_kind="TEST", good=True, verdict="ok"),
        event("run-begun",  when(5), directory=d1, node="test-cut.sh",
              node_kind="TEST"),
        event("run-ended",  when(6), directory=d1, node="test-app.sh b",
              node_kind="TEST", good=True, verdict="ok"),
        event("run-ended",  when(7), directory=d1, node="test-cut.sh",
              node_kind="TEST", good=False, verdict="test-failed",
              report="terminated-without-hwut-end"),
        event("run-begun",  when(7), directory=d1, node="test-dead.sh x",
              node_kind="TEST"),
        event("run-ended",  when(8), directory=d1, node="test-dead.sh x",
              node_kind="TEST", good=False, verdict="test-failed",
              report="test-app-contained"),
        event("run-begun",  when(8), directory=d1, node="test-diff.sh",
              node_kind="TEST"),
        event("run-ended",  when(9), directory=d1, node="test-diff.sh",
              node_kind="TEST", good=False, verdict="test-failed",
              report="not-equivalent-with-nominal"),
        event("run-begun",  when(9), directory=d1, node="test-ok.sh",
              node_kind="TEST"),
        event("run-ended",  when(10), directory=d1, node="test-ok.sh",
              node_kind="TEST", good=True, verdict="ok"),
        event("frame",      when(10), directory=d1, role="on_exit",
              good=True),
        event("dir-done",   when(10), directory=d1, good=False,
              fail_db={"test-m.sh": "MISDEP"}),
        event("dir-begun",  when(10), directory=d2, node_n=1),
        event("frame",      when(10), directory=d2, role="on_entry",
              good=True),
        event("run-begun",  when(11), directory=d2,
              node="test-region.py nested", node_kind="TEST"),
        event("run-ended",  when(12), directory=d2,
              node="test-region.py nested", node_kind="TEST",
              good=True, verdict="ok"),
        event("frame",      when(12), directory=d2, role="on_exit",
              good=True),
        event("dir-done",   when(12), directory=d2, good=True,
              fail_db={}),
        event("tree-done",  when(12), good=False, fail_n=6),
        None,
    ]


def test_mixed():
    """RETURN: None. The whole verdict set, two directories."""
    banner("the mixed tree")
    show(_mixed_stream())


def test_words():
    """RETURN: None. Every report word, one failing line each; one
    word nobody taught, hyphens opened."""
    d = "suite/TEST"
    stream = [event("tree-begun", when(0), directory_list=[d]),
              event("dir-begun",  when(0), directory=d, node_n=1)]
    second = 0
    word_list = [member.value for member in E_TestRunResult
                 if member is not E_TestRunResult.OK]
    word_list.append("a-token-nobody-taught")
    for index, word in enumerate(word_list):
        node    = "test-%02d.sh" % index
        second += 1
        stream.append(event("run-begun", when(second), directory=d,
                            node=node, node_kind="TEST"))
        stream.append(event("run-ended", when(second), directory=d,
                            node=node, node_kind="TEST", good=False,
                            verdict="test-failed", report=word))
    stream.append(event("dir-done",  when(second), directory=d,
                        good=False, fail_db={}))
    stream.append(event("tree-done", when(second), good=False,
                        fail_n=len(word_list)))
    stream.append(None)
    banner("every report word")
    show(stream)


def test_fault():
    """RETURN: None. Faults at the tree and in a directory."""
    d = "suite/TEST"
    stream = [
        event("tree-begun", when(0), directory_list=[d]),
        event("fault",      when(0), directory=".",
              text="the task file names 'gone/', which is not there"),
        event("dir-begun",  when(0), directory=d, node_n=1),
        event("run-begun",  when(1), directory=d, node="test-ok.sh",
              node_kind="TEST"),
        event("run-ended",  when(2), directory=d, node="test-ok.sh",
              node_kind="TEST", good=True, verdict="ok"),
        event("fault",      when(2), directory=d,
              text="OSError: the directory vanished mid-walk"),
        event("dir-done",   when(2), directory=d, good=False,
              fail_db={}),
        event("tree-done",  when(2), good=False, fail_n=0),
        None,
    ]
    banner("faults, never swallowed")
    show(stream)


def test_empty():
    """RETURN: None. A wish that selects nothing."""
    d = "suite/TEST"
    stream = [
        event("tree-begun", when(0), directory_list=[d]),
        event("report",     when(0), directory=d,
              text="the selection is empty: no test case answers "
                   "the wish"),
        event("dir-begun",  when(0), directory=d, node_n=0),
        event("dir-done",   when(0), directory=d, good=True,
              fail_db={}),
        event("tree-done",  when(0), good=True, fail_n=0),
        None,
    ]
    banner("an empty selection")
    show(stream)


def test_unknown():
    """RETURN: None. The stability promise on display."""
    d = "suite/TEST"
    stream = [
        event("tree-begun", when(0), directory_list=[d]),
        event("dir-begun",  when(0), directory=d, node_n=2),
        {"format": 99, "kind": "telemetry", "when": when(1),
         "payload": "an event kind of a NEWER wire"},
        event("run-begun",  when(1), directory=d, node="test-q.sh",
              node_kind="TEST"),
        event("run-ended",  when(2), directory=d, node="test-q.sh",
              node_kind="TEST", good=False, verdict="quarantined"),
        {"format": 1, "kind": "run-ended", "when": when(2),
         "directory": d, "node": "test-r.sh", "node_kind": "TEST",
         "good": True},
        event("dir-done",   when(2), directory=d, good=False,
              fail_db={}),
        event("tree-done",  when(2), good=False, fail_n=1),
        None,
    ]
    banner("unknown kind ignored; unknown verdict reads not-ok; "
           "a misfit is a fault")
    show(stream)


def test_tiers():
    """RETURN: None. VERBOSE adds the swallowed; QUIET drops the flow;
    SILENT drops stdout and keeps the fault on stderr."""
    d = "suite/TEST"
    stream = [
        event("tree-begun", when(0), directory_list=[d]),
        event("fault",      when(0), directory=d,
              text="hwut.conf:2:3: DIRECTORY: a broken statement"),
        event("dir-begun",  when(0), directory=d, node_n=2),
        event("frame",      when(0), directory=d, role="on_entry",
              good=True),
        event("run-begun",  when(1), directory=d, node="test-a.sh",
              node_kind="TEST"),
        event("run-ended",  when(2), directory=d, node="test-a.sh",
              node_kind="TEST", good=True, verdict="ok"),
        event("run-begun",  when(2), directory=d, node="test-b.sh",
              node_kind="TEST"),
        event("run-ended",  when(3), directory=d, node="test-b.sh",
              node_kind="TEST", good=False, verdict="test-failed",
              report="test-app-stalled"),
        event("frame",      when(3), directory=d, role="on_exit",
              good=False),
        event("dir-done",   when(3), directory=d, good=False,
              fail_db={}),
        event("tree-done",  when(3), good=False, fail_n=2),
        None,
    ]
    banner("VERBOSE")
    show(list(stream), tier=E_Tier.VERBOSE)
    banner("QUIET")
    show(list(stream), tier=E_Tier.QUIET)
    banner("SILENT")
    show(list(stream), tier=E_Tier.SILENT)


def test_badge():
    """RETURN: None. E-97 corrected: the parallelism rides on EVERY flow
               line, after the verdict column, as '||n' -- so it FALLS
               as runs end. MEASURED before: drawn on the START line
               only, it showed '|8|' for the rest of the run and never
               came down."""
    from vut.engine.display.plain import CPlainFlow
    from vut.engine.display.word import CInk
    out = []
    f = CPlainFlow(write=out.append, width=WIDTH, ink=CInk(False), start_delay=0)
    f.on_tree_begun(when(0), ["suite/TEST"])
    for i, name in enumerate("abc"):
        f.on_run_begun(when(1 + i), "suite/TEST", "test-%s.sh" % name, "RUN")
    f.on_run_begun(when(4), "suite/TEST", "test-d.sh", "RUN")
    for name, good_f in (("b", True), ("a", False), ("c", True), ("d", True)):
        f.on_run_ended(when(6), "suite/TEST", "test-%s.sh" % name, "RUN",
                       good_f, "ok" if good_f else "fail")
    f.on_run_begun(when(10), "suite/TEST", "test-e.sh", "RUN")
    f.on_run_ended(when(11), "suite/TEST", "test-e.sh", "RUN", True, "ok")
    for line in out: print(line)

    #  THE COUNT BELONGS TO THE EVENT, NOT TO THE PRINTING. A START is
    #  HELD until its run proves slow; read at print time, six STARTs
    #  released together all said '||8' (MEASURED on a real tree).
    banner("held STARTs, released together: each says what IT saw")
    out = []
    f = CPlainFlow(write=out.append, width=WIDTH, ink=CInk(False),
                   start_delay=2.0)
    f.on_tree_begun(when(0), ["suite/TEST"])
    for i, name in enumerate("abcde"):
        f.on_run_begun(when(1 + i), "suite/TEST", "test-%s.sh" % name, "RUN")
    f.on_tick(when(8))
    f.on_run_ended(when(9),  "suite/TEST", "test-a.sh", "RUN", True, "ok")
    f.on_run_ended(when(10), "suite/TEST", "test-b.sh", "RUN", True, "ok")
    for line in out: print(line)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Tier 1, the plain console report, over scripted "
               "streams;", {
        "allgreen": test_allgreen,
        "mixed":    test_mixed,
        "words":    test_words,
        "fault":    test_fault,
        "empty":    test_empty,
        "unknown":  test_unknown,
        "tiers":    test_tiers,
        "badge":    test_badge,
    }).run()
